#!/usr/bin/env python3
"""Reviewed #763 cold-checkpoint and reversible durable-state primitives.

This module does NOT enable a service, restore NAS, refresh auth, or promote staging.
The cutover controller must supply exclusive-owner/writer evidence before calling
these primitives. Payloads are inert data. No staged-table purge is reused.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile

_spec = importlib.util.spec_from_file_location('hermes_state_stage', Path(__file__).with_name('state-stage.py'))
stage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stage)
DATABASES = stage.DATABASES
LEASE_TABLES = ('gateway_heartbeats', 'compression_locks', 'session_turn_leases')
MAX_TOTAL = stage.MAX_TOTAL


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative(name):
    p = PurePosixPath(name)
    require(isinstance(name, str) and not p.is_absolute() and p.as_posix() == name
            and all(x not in {'.', '..'} for x in p.parts)
            and not any(x in name for x in '\\' + '\x00\r\n\t'), 'unsafe relative path')
    return name


def signature(path):
    stage.safe(path, owner=os.getuid())
    s = path.stat()
    return {'sha256': stage.digest(stage.read_private(path, owner=os.getuid())),
            'mode': stat.S_IMODE(s.st_mode), 'mtime_ns': s.st_mtime_ns,
            'uid': s.st_uid, 'gid': s.st_gid}


def checkpoint(root, names, *, exclusive_owner):
    """Cold-copy allowlisted bytes, including every present DB WAL, under exclusion.

    Never opens source SQLite: the NAS host's older SQLite is NOT suitable for
    parsing/checkpointing these stores. Normalize/validate ONLY a private copy
    using the pinned native interpreter after transport.
    """
    require(exclusive_owner is True, 'exclusive stopped owner required')
    stage.safe(root, directory=True, owner=os.getuid())
    selected = set(map(relative, names))
    require(set(DATABASES).issubset(selected), 'seven databases required')
    for db in DATABASES:
        for suffix in ('-wal', '-shm', '-journal'):
            p = root / (db + suffix)
            stage.safe(p, missing=True, owner=os.getuid() if p.exists() else None)
            if p.exists():
                require(suffix != '-journal', 'hot rollback journal requires review')
                selected.add(db + suffix)
    before = {n: signature(root / n) for n in sorted(selected)}
    data = {n: stage.read_private(root / n, owner=os.getuid()) for n in sorted(selected)}
    require(len(data) <= stage.MAX_ENTRIES and sum(map(len, data.values())) <= MAX_TOTAL,
            'checkpoint bounds')
    require(before == {n: signature(root / n) for n in sorted(selected)}, 'cold source drift')
    for db in DATABASES:
        for suffix in ('-wal', '-shm', '-journal'):
            require((db + suffix in selected) == (root / (db + suffix)).exists(), 'DB sidecar membership drift')
    receipt = {'schemaVersion': 1, 'kind': 'COHERENT_STOPPED_OWNER_CHECKPOINT',
               'version': stage.VERSION, 'revision': stage.REVISION,
               'files': before, 'queuePolicy': 'PRESERVE_DELIVERED_NO_REPLAY_UNKNOWN_STOP'}
    return data, receipt


def validate_checkpoint(data, receipt):
    require(receipt.get('schemaVersion') == 1
            and receipt.get('kind') == 'COHERENT_STOPPED_OWNER_CHECKPOINT'
            and receipt.get('version') == stage.VERSION and receipt.get('revision') == stage.REVISION
            and receipt.get('queuePolicy') == 'PRESERVE_DELIVERED_NO_REPLAY_UNKNOWN_STOP',
            'checkpoint identity')
    require(set(data) == set(receipt['files']) and set(DATABASES).issubset(data)
            and len(data) <= stage.MAX_ENTRIES, 'checkpoint membership')
    require(sum(map(len, data.values())) <= MAX_TOTAL, 'checkpoint bounds')
    for n, b in data.items():
        relative(n)
        require(isinstance(b, bytes) and stage.digest(b) == receipt['files'][n]['sha256'], 'checkpoint checksum')


def normalized_databases(data, receipt):
    """Validate/normalize disposable copies; preserve ALL delivered ledger rows."""
    validate_checkpoint(data, receipt)
    require(sqlite3.sqlite_version_info >= (3, 51, 3), 'native SQLite WAL safety floor')
    outputs, checks = {}, {}
    with tempfile.TemporaryDirectory(prefix='hermes763-verify-') as tmp:
        root = Path(tmp)
        root.chmod(0o700)
        for db in DATABASES:
            p = root / db
            p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            p.write_bytes(data[db]); p.chmod(0o600)
            # SHM is generated, not durable. A private copy reconstitutes it.
            if db + '-wal' in data:
                Path(str(p) + '-wal').write_bytes(data[db + '-wal'])
                Path(str(p) + '-wal').chmod(0o600)
            c = sqlite3.connect(p)
            try:
                before = stage.db_checks(c, db)
                if db == 'state.db':
                    require(all(before['counts'].get(t, 0) == 0 for t in LEASE_TABLES),
                            'unclassified lifecycle leases; no automatic purge')
                    require(before['counts'].get('async_delegations', 0) == 0,
                            'delegation classification required')
                    rows = c.execute('SELECT state,count(*) FROM delivery_obligations GROUP BY state').fetchall()
                    require(all(s == 'delivered' for s, _ in rows),
                            'actionable/uncertain delivery requires exact owner review')
                    for t in ('messages_fts', 'messages_fts_trigram'):
                        if t in before['counts']:
                            c.execute('INSERT INTO '+t+'('+t+') VALUES(?)', ('integrity-check',))
                    c.commit()
                c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                c.execute('PRAGMA journal_mode=DELETE')
                after = stage.db_checks(c, db)
                require(before['schema'] == after['schema'] and before['counts'] == after['counts'],
                        'durable schema/history changed')
                outputs[db] = c.serialize()
                checks[db] = {'integrity': 'PASS', 'foreignKeys': 'PASS',
                              'schema': after['schema'], 'durableCountsPreserved': True}
            finally:
                c.close()
    return outputs, checks


def logical_rows(data, name):
    """Private-only schema/row fingerprints: do not return rows or contents."""
    c = sqlite3.connect(':memory:')
    try:
        c.deserialize(data)
        result = stage.db_checks(c, name)
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_schema WHERE type='table'")]
        rows = {}
        for table in tables:
            # FTS shadow tables carry generated indexes; validate those via FTS
            # integrity checks, not via physical row/page arrangement.
            if table.startswith('messages_fts'):
                continue
            q = 'SELECT * FROM "' + table.replace('"', '""') + '"'
            values = c.execute(q).fetchall()
            blobs = sorted(repr(v).encode() for v in values)
            rows[table] = hashlib.sha256(b'\x00'.join(blobs)).hexdigest()
        return {'schema': result['schema'], 'counts': result['counts'], 'rowHashes': rows}
    finally:
        c.close()


def mapped_plan(data, receipt, *, destination, namespace, mapping):
    """Exact reviewed mapping, never archive extraction or payload execution."""
    validate_checkpoint(data, receipt)
    require(namespace == 'production/baseline-0.21.2', 'distinct production namespace required')
    stage.safe(destination, directory=True, owner=os.getuid())
    require(len(mapping) == len(set(mapping.values())), 'duplicate destination')
    result = {}
    for source, target in mapping.items():
        relative(source); relative(target)
        require(source in data and not source.endswith(('-wal', '-shm', '-journal')), 'unapproved mapping source')
        result[target] = data[source]
    require(set(DATABASES).issubset(mapping), 'all durable stores must be mapped')
    for n in result:
        p = destination / n
        stage.safe(p, missing=True, owner=os.getuid() if p.exists() else None)
    return result


def atomic_durable(path, data, expected):
    """Keep existing parent modes and target owner/mode; never stage.mkdir NAS.

    Existing parents may intentionally have different modes. Normalizing their
    modes as a side effect would invalidate a retained NAS checkpoint. New
    private parents are 0700; new data files are 0600. Existing file metadata is
    retained in the journal and mode/owner/group carried to the replacement.
    """
    stage.safe(path, missing=True, owner=os.getuid() if path.exists() else None)
    mode = expected['mode'] if expected is not None else 0o600
    if path.exists() and stage.read_private(path) == data:
        return False
    stage.safe(path.parent, directory=True, missing=True)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    stage.safe(path.parent, directory=True, owner=os.getuid())
    fd, name = tempfile.mkstemp(prefix='.production-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            os.fchmod(out.fileno(), mode)
            if expected is not None:
                current = os.fstat(out.fileno())
                if (current.st_uid, current.st_gid) != (expected['uid'], expected['gid']):
                    os.fchown(out.fileno(), expected['uid'], expected['gid'])
            out.write(data); out.flush(); os.fsync(out.fileno())
        # A cooperative writer holds the shared reservation. CAS is rechecked
        # immediately before replace as well; an unexcluded writer is a blocker,
        # not a claim that Python can atomically compare-and-rename two files.
        require((signature(path) if path.exists() else None) == expected, 'concurrent CAS drift')
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def apply_cas(root, plan, expected, *, restore_authorized, evidence):
    """Bounded reverse/forward apply; retain exact preimages and fail closed.

    Caller may set restore_authorized only from John's incident-specific approval
    for an authoritative restore. A cutover GO is not that approval. The journal
    is retained INCOMPLETE on interruption; no retry deletes or repairs it.
    """
    require(restore_authorized is True, 'exact application/restore authority required')
    stage.safe(root, directory=True, owner=os.getuid())
    stage.safe(evidence, directory=True, owner=os.getuid())
    require(set(plan) == set(expected), 'CAS membership')
    transaction = evidence / 'transaction.json'
    require(not transaction.exists(), 'transaction already exists; recovery review required')
    for name, wanted in expected.items():
        relative(name)
        p = root / name
        current = signature(p) if p.exists() else None
        require(current == wanted, 'target CAS drift')
        require(isinstance(plan[name], bytes), 'plan data required')
    preimages = evidence / 'preimages'
    preimages.mkdir(mode=0o700)
    for n, s in expected.items():
        if s is not None:
            p = preimages / n
            p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            stage.atomic(p, stage.read_private(root / n))
    journal = {'schemaVersion': 1, 'status': 'INCOMPLETE', 'expected': expected,
               'proposed': {n: stage.digest(b) for n, b in plan.items()}}
    stage.atomic(transaction, stage.encoded(journal))
    changed = 0
    for name, data in plan.items():
        p = root / name
        require((signature(p) if p.exists() else None) == expected[name], 'concurrent CAS drift')
        changed += atomic_durable(p, data, expected[name])
    require(all(stage.digest(stage.read_private(root / n)) == stage.digest(b) for n, b in plan.items()), 'apply readback')
    journal['status'] = 'COMPLETE'
    stage.atomic(transaction, stage.encoded(journal))
    return {'changedFiles': changed, 'readback': 'PASS', 'preimages': 'RETAINED'}


def validate_reverse(checkpoint_data, checkpoint_receipt, incident_data, incident_receipt, current_nas):
    """NAS must remain the exact checkpoint branch, or STOP for manual merge."""
    validate_checkpoint(checkpoint_data, checkpoint_receipt)
    validate_checkpoint(incident_data, incident_receipt)
    require(current_nas == checkpoint_receipt['files'], 'NAS branch diverged; manual reconciliation required')
    require(set(checkpoint_data).issubset(incident_data), 'incident lost durable checkpoint members')
    normalized, checks = normalized_databases(incident_data, incident_receipt)
    # The source was stopped: the entire native authoritative branch is retained,
    # not a union that could silently drop new rows or collide IDs.
    return normalized, checks
