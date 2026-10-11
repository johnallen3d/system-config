#!/usr/bin/env python3
"""#763 shared local inode/per-file reservation protocol, fail-closed.

Not a distributed lock: maintenance/acceptance/recovery requires fresh timed
manual exclusion and real all-peer metadata. Normal gateway/tasks/05:00 writes
retain NAS same-file human nonoverlap plus actual local/direct clean metadata.
All adapters use THIS SAME coordinator directory across private /tmp namespaces.
An unadapted writer is a blocker. These primitives do not install adapters, approve
restores, enable a capability, pause Syncthing, or write vault content themselves.
"""
from __future__ import annotations
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import secrets

_spec = importlib.util.spec_from_file_location('hermes_production_state', Path(__file__).with_name('production-state.py'))
state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(state)
require = state.require
PEERS = ('omarchy', 'mac', 'nas')
WRITERS = {'gateway', 'brief', 'omarchy-tasks', 'mac-tasks', 'editors', 'mobile-icloud'}
NAMESPACE = 'production/baseline-0.21.2'


def scope_check(scope, files, now):
    require(scope.get('schemaVersion') == 1 and scope.get('namespace') == NAMESPACE
            and scope.get('coordinator') == 'omarchy', 'writer scope identity')
    require(isinstance(scope.get('nonce'), str) and 24 <= len(scope['nonce']) <= 128, 'writer scope nonce')
    require(scope.get('manualConfirmationSource') == 'JOHN_EXECUTION_WINDOW'
            and set(scope.get('excludedWriters', [])) == WRITERS, 'fresh manual writer exclusion required')
    start, expiry = scope.get('confirmedAt'), scope.get('expiresAt')
    require(isinstance(start, (int, float)) and isinstance(expiry, (int, float))
            and start <= now < expiry and 0 < expiry - start <= 600,
            'timed writer scope expired/invalid; no eternal exclusion')
    require(set(scope.get('files', [])) == set(files) and len(files) == len(set(files))
            and 0 < len(files) <= 8, 'exact per-file reservation scope')
    for name in files:
        state.relative(name)
        require(not name.startswith('.') and not any(p.startswith('.') for p in Path(name).parts),
                'hidden/config paths are not approved vault content')


def peer_check(observation, wanted, now):
    require(set(observation) == set(PEERS), 'all actual peers required')
    for i, peer in enumerate(PEERS):
        row = observation[peer]
        require(isinstance(row.get('observedAt'), (int, float))
                and 0 <= now - row['observedAt'] <= 5, 'fresh actual peer observation required')
        adjacent = {PEERS[j] for j in range(3) if abs(i-j) == 1}
        require(row.get('folderID') == 'notes' and row.get('type') == 'sendreceive'
                and row.get('paused') is False and row.get('state') == 'idle'
                and row.get('connectedPeers') == sorted(adjacent)
                and row.get('completion') == 100
                and all(row.get(k) == 0 for k in ('needItems', 'needBytes', 'errors', 'pullErrors')),
                'peer convergence/topology not clean')
        # Existing Syncthing metadata is convergence evidence, not remote byte
        # verification or writer exclusion. Exact bytes are checked locally by
        # manifest/CAS/readback; human same-file exclusion remains mandatory.
        require(row.get('conflicts') == [], 'peer conflict; stop all writers')


def normal_scope_check(scope, files, now):
    """Existing NAS normal-write policy, NOT an eternal human freeze receipt.

    John must not edit the same file on another peer during this operation. A
    scheduled brief does not invent a fresh human confirmation on every run.
    Runtime ownership and local guards are independently checked by the adapter.
    """
    require(scope.get('schemaVersion') == 1 and scope.get('namespace') == NAMESPACE
            and scope.get('coordinator') == 'omarchy'
            and scope.get('kind') == 'NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION', 'normal writer policy identity')
    require(isinstance(scope.get('nonce'),str) and 24 <= len(scope['nonce']) <= 128, 'writer scope nonce')
    require(set(scope.get('files',[])) == set(files) and len(files) == len(set(files))
            and 0 < len(files) <= 8, 'exact normal per-file scope')
    for name in files:
        state.relative(name)
        require(not any(p.startswith('.') for p in Path(name).parts), 'hidden paths not approved vault content')
    require('manualConfirmationSource' not in scope and 'expiresAt' not in scope,
            'normal policy must not claim a timed human lease')


def normal_peer_check(observation, wanted, now):
    """Actual local/direct Syncthing metadata; never claims downstream byte hashes."""
    require(isinstance(observation.get('observedAt'),(int,float))
            and 0 <= now-observation['observedAt'] <= 5, 'fresh local Syncthing observation required')
    require(observation.get('folder') == 'notes' and observation.get('type') == 'sendreceive'
            and observation.get('state') == 'idle' and observation.get('localConvergence') is True
            and observation.get('directPeerConvergence') is True
            and observation.get('directPeerCount') == 1
            and all(observation.get(k) == 0 for k in ('conflicts','temporary','special')),
            'normal local/direct sync or conflict stop')


def manifest(vault, files):
    state.stage.safe(vault, directory=True, owner=os.getuid())
    result = {}
    for name in files:
        state.relative(name)
        p = vault / name
        state.stage.safe(p, missing=True, owner=os.getuid() if p.exists() else None)
        result[name] = state.signature(p) if p.exists() else None
    return result


def hashes(entries):
    return {n: None if s is None else s['sha256'] for n, s in entries.items()}


def verify_binding(path, fd):
    state.stage.safe(path, owner=os.getuid())
    current, held = path.stat(), os.fstat(fd)
    require((current.st_dev, current.st_ino) == (held.st_dev, held.st_ino), 'shared lock replaced')


@contextlib.contextmanager
def held_lock(path):
    """Stable shared inode; never delete/recreate a lock after releasing it."""
    state.stage.safe(path, missing=True, owner=os.getuid() if path.exists() else None)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        s = os.fstat(fd)
        require(s.st_uid == os.getuid() and s.st_nlink == 1 and s.st_mode & 0o777 == 0o600,
                'shared lock owner/mode/inode')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('writer reservation already held') from None
        verify_binding(path, fd)
        yield fd
        verify_binding(path, fd)
    finally:
        os.close(fd)


class Reservation:
    def __init__(self, coordinator, vault, files, scope, observer, clock, bindings, scope_validator=scope_check, peer_validator=peer_check):
        self.coordinator, self.vault, self.files = coordinator, vault, files
        self.scope, self.observer, self.clock = scope, observer, clock
        self.bindings = bindings
        self.scope_validator, self.peer_validator = scope_validator, peer_validator
        self.expected = manifest(vault, files)
        self.complete_called = False

    def check_bindings(self):
        for path, fd in self.bindings:
            verify_binding(path, fd)

    def check(self):
        self.check_bindings()
        self.scope_validator(self.scope, self.files, self.clock())
        require(manifest(self.vault, self.files) == self.expected,
                'reserved file CAS drift; stop, retain both branches')
        self.peer_validator(self.observer(self.files), hashes(self.expected), self.clock())

    def complete(self, final):
        """Called after helper write/readback and the selected policy's convergence.

        `final` is the reviewed writer's exact postimage signature set, not a
        fresh read accepted blindly. No success if an outside writer changed it.
        """
        self.check_bindings()
        self.scope_validator(self.scope, self.files, self.clock())
        require(set(final) == set(self.files) and manifest(self.vault, self.files) == final,
                'writer postimage readback mismatch')
        self.peer_validator(self.observer(self.files), hashes(final), self.clock())
        self.final = final
        self.complete_called = True


@contextlib.contextmanager
def reserve(coordinator, vault, files, *, scope, observer, clock=time.time, _normal=False):
    """Hold global + exact file locks through write/readback/sync acknowledgment.

    Caller supplies the observer, which must query current policy-required metadata;
    cached peer-health JSON is not authority. Any incomplete/stopped reservation
    remains a sticky review gate; retry cannot silently clear it or overwrite it.
    """
    coordinator, vault, files = Path(coordinator), Path(vault), tuple(files)
    require(coordinator.parts[-3:] == ('hermes-native', 'production', 'baseline-0.21.2'),
            'canonical production coordinator namespace required')
    state.stage.safe(coordinator, directory=True, owner=os.getuid())
    require(coordinator.stat().st_mode & 0o777 == 0o700, 'private shared coordinator required')
    scope_validator = normal_scope_check if _normal else scope_check
    peer_validator = normal_peer_check if _normal else peer_check
    scope_validator(scope, files, clock())
    locks = coordinator / 'file-locks'
    state.stage.safe(locks, directory=True, missing=True, owner=os.getuid() if locks.exists() else None)
    locks.mkdir(mode=0o700, exist_ok=True)
    history = coordinator / 'reservation-evidence'
    state.stage.safe(history, directory=True, missing=True, owner=os.getuid() if history.exists() else None)
    history.mkdir(mode=0o700, exist_ok=True)
    nonce_file = history / (hashlib.sha256(scope['nonce'].encode()).hexdigest()+'.json')
    journal = coordinator / 'writer-reservation.json'
    record = None
    try:
        with contextlib.ExitStack() as stack:
            paths = [coordinator / 'writer.lock'] + [
                locks / (hashlib.sha256(n.encode()).hexdigest()+'.lock') for n in sorted(files)]
            bindings = [(p, stack.enter_context(held_lock(p))) for p in paths]
            state.stage.safe(journal, missing=True, owner=os.getuid() if journal.exists() else None)
            if journal.exists():
                previous = json.loads(state.stage.read_private(journal, owner=os.getuid()))
                previous_file = history / (hashlib.sha256(previous['nonce'].encode()).hexdigest()+'.json')
                require(state.stage.read_private(previous_file, owner=os.getuid()) == state.stage.encoded(previous),
                        'reservation evidence incomplete/drifted')
                if previous.get('status') != 'COMPLETE':
                    review=coordinator/'controller/acceptance-noeffect-continuation.json'
                    require(review.exists(), 'incomplete/stopped reservation requires review')
                    reconciled=json.loads(state.stage.read_private(review,owner=os.getuid()))
                    require(not _normal and reconciled.get('kind')=='HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION'
                            and reconciled.get('namespace')==NAMESPACE
                            and reconciled.get('reservationSha256')==state.stage.digest(state.stage.encoded(previous))
                            and tuple(previous.get('expected',{}))==tuple(files)
                            and state.stage.read_private(Path(reconciled['archive'])/'writer-reservation.json',owner=os.getuid())
                                == state.stage.encoded(previous),
                            'only exact reviewed no-effect acceptance reservation; unknown work never cleared')
            state.stage.safe(nonce_file, missing=True, owner=os.getuid() if nonce_file.exists() else None)
            require(not nonce_file.exists(), 'reservation nonce replay refused')
            reservation = Reservation(coordinator, vault, files, scope, observer, clock, bindings, scope_validator, peer_validator)
            reservation.check()
            record = {'schemaVersion': 1, 'namespace': NAMESPACE, 'nonce': scope['nonce'],
                      'status': 'ACTIVE', 'expected': reservation.expected,
                      'policy': 'NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION' if _normal else 'JOHN_EXECUTION_WINDOW',
                      'convergenceEvidence': 'LOCAL_AND_DIRECT_METADATA' if _normal else 'ALL_PEER_METADATA'}
            if not _normal:
                record.update(confirmedAt=scope['confirmedAt'], expiresAt=scope['expiresAt'])
            preimages = history/(nonce_file.stem+'.preimages')
            require(not preimages.exists(), 'writer preimage nonce collision')
            state.stage.mkdir(preimages)
            for name, expected in reservation.expected.items():
                if expected is not None:
                    state.stage.atomic(preimages/name,state.stage.read_private(vault/name,owner=os.getuid()))
                    require(state.stage.digest(state.stage.read_private(preimages/name)) == expected['sha256'],
                            'writer retained preimage mismatch')
            reservation.check()
            record['preimages'] = str(preimages)
            record['retentionDaysMinimum'] = 14
            state.stage.atomic(journal, state.stage.encoded(record))
            state.stage.atomic(nonce_file, state.stage.encoded(record))
            yield reservation
            require(reservation.complete_called, 'policy-specific postimage acknowledgment required')
            scope_validator(scope, files, clock())
            require(manifest(vault, files) == reservation.final, 'writer changed after acknowledgment')
            peer_validator(observer(files), hashes(reservation.final), clock())
            reservation.check_bindings()
        # COMPLETE only after every lock's exit inode check passed. Until then
        # ACTIVE remains a sticky gate, even if release/check is interrupted.
        record['status'] = 'COMPLETE'; record['postimages'] = reservation.final
        state.stage.atomic(nonce_file, state.stage.encoded(record))
        state.stage.atomic(journal, state.stage.encoded(record))
    except BaseException:
        if record is not None:
            record['status'] = 'STOPPED_REVIEW_REQUIRED'
            state.stage.atomic(journal, state.stage.encoded(record))
            state.stage.atomic(nonce_file, state.stage.encoded(record))
        raise


@contextlib.contextmanager
def normal_reserve(coordinator, vault, files, *, observer, clock=time.time):
    """Normal gateway/tasks/05:00 brief, using the already accepted NAS policy.

    Maintenance/acceptance/recovery callers MUST use reserve() instead. This
    route independently requires actual live native ownership, not a caller's
    claim that a human freeze is permanent. Same-file cross-peer nonoverlap is
    still the human operating contract; metadata does not create a global lock.
    """
    coordinator, files = Path(coordinator), tuple(files)
    def actual_local_observation(names):
        owner = json.loads(state.stage.read_private(coordinator/'controller/ownership.json',owner=os.getuid()))
        require(owner.get('namespace') == NAMESPACE and owner.get('owner') == 'native'
                and owner.get('phase') == 'NATIVE_LIVE' and owner.get('vaultWrites') == 'ENABLED'
                and owner.get('normalWriterPolicy') == 'NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION',
                'actual live normal-writer ownership required')
        return observer(names)
    scope = {'schemaVersion':1,'namespace':NAMESPACE,'coordinator':'omarchy',
             'kind':'NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION','nonce':secrets.token_hex(24),'files':list(files)}
    with reserve(coordinator,vault,files,scope=scope,observer=actual_local_observation,clock=clock,_normal=True) as reservation:
        yield reservation
