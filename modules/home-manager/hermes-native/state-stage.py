#!/usr/bin/env python3
"""#760 restricted staging, never an authoritative transfer or transport launcher.

Export is read-only on the NAS; SQLite online backups are consistent PER DATABASE,
not globally coherent. Import retains original private snapshots and quarantines
work/authorization/code. No archive member is executed or extracted by tar.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import fcntl
import hashlib
import io
import json
import logging
import os
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath

VERSION = '0.21.2'
REVISION = 'a19160bbf02dc37c57ff47cf0eaa4a3ab8ee43dc'
DATABASES = ('state.db', 'shared-state.db', 'kanban.db', 'response_store.db',
             'runs_idempotency.db', 'cron/notepad.db', 'cron/executions.db')
STATE_FILES = ('SOUL.md', 'memories/MEMORY.md', 'memories/USER.md', 'sessions/sessions.json')
NOTEBOOK_FILES = ('config.json', 'profiles/default/context.json', 'profiles/default/storage_state.json')
PRIVATE_SKILLS = ('software-development/local-slash-commands', 'note-taking/obsidian-dashboard-integrity',
                  'health/macro-aware-meal-planning', 'productivity/personal-daily-operations',
                  'productivity/calendar-note-reconciliation', 'productivity/shopping-research')
QUARANTINE_FILES = ('config.yaml', 'cron/jobs.json', 'scripts/morning-brief.sh',
                    'channel_directory.json', 'gateway_state.json', 'gateway/telegram-offset.json',
                    'plugins/macros/plugin.yaml', 'plugins/macros/__init__.py',
                    'skills/health/food/SKILL.md', 'skills/health/food/scripts/adjust-food-log',
                    'skills/productivity/imessage-search/SKILL.md')
QUARANTINE_TREES = ('pending', 'pending_messages', 'pairing', 'gateway', 'platforms',
                    'photon', 'plans', 'skins', 'hooks')
TRANSIENT_TABLES = ('gateway_heartbeats', 'compression_locks', 'session_turn_leases',
                    'async_delegations', 'delivery_obligations')
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_ENTRIES = 4096
METADATA = Path('/home/johna/.config/hermes-native/runtime.json')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_config(data):
    # Native seed/overlays are JSON (valid YAML); NAS config uses installed
    # PyYAML. This keeps synthetic stdlib tests independent of host packages.
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        import yaml
        return yaml.safe_load(data)


def safe(path, directory=False, missing=False, owner=None):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('absolute path required')
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise ValueError('symlink refused')
    try:
        info = path.stat()
    except FileNotFoundError:
        if missing:
            return
        raise
    if owner is not None and info.st_uid != owner:
        raise ValueError('unexpected owner')
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('directory required')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('single-link regular file required')


def read_private(path, owner=None):
    safe(path, owner=owner)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > MAX_FILE:
            raise ValueError('file limit')
        data = stream.read(MAX_FILE + 1)
        after = os.fstat(stream.fileno())
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if signature(before) != signature(after) or len(data) > MAX_FILE:
        raise ValueError('source moved during read')
    return data


def mkdir(path):
    safe(path, directory=True, missing=True)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Every newly created ancestor below the selected roots is checked by the
    # caller's preflight. Existing ownership is never recursively changed.
    path.chmod(0o700)


def atomic(path, data, mode=0o600):
    safe(path, missing=True, owner=os.getuid() if path.exists() else None)
    mkdir(path.parent)
    if path.exists() and read_private(path) == data and stat.S_IMODE(path.stat().st_mode) == mode:
        return False
    fd, name = tempfile.mkstemp(prefix='.stage-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.chmod(name, mode)
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


def db_checks(connection, name):
    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise ValueError('database integrity failed')
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise ValueError('database foreign keys failed')
    tables = sorted(r[0] for r in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'"))
    schema = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name").fetchall()
    counts = {t: connection.execute('SELECT count(*) FROM "' + t.replace('"', '""') + '"').fetchone()[0]
              for t in tables}
    result = {'integrity': 'PASS', 'foreignKeys': 'PASS', 'schema': digest(encoded(schema)), 'counts': counts}
    if name == 'state.db':
        if not {'schema_version', 'sessions', 'messages', 'messages_fts_trigram'}.issubset(tables):
            raise ValueError('baseline state schema missing')
        orphaned = connection.execute('SELECT count(*) FROM messages m LEFT JOIN sessions s ON s.id=m.session_id WHERE s.id IS NULL').fetchone()[0]
        if orphaned:
            raise ValueError('orphaned messages')
        result['messageSessionRelationships'] = 'PASS'
        result['schemaVersionRows'] = connection.execute('SELECT * FROM schema_version').fetchall()
        if result['schemaVersionRows'] != [(30,)]:
            raise ValueError('pinned Hermes 0.21.2 state schema 30 required')
    return result


def snapshot_db(path, name):
    safe(path, owner=os.getuid())
    # mode=ro incorporates the live WAL. immutable=1 would IGNORE it and is
    # deliberately never used on the authoritative source. No checkpoint,
    # migration, DELETE, journal-mode or application initialization on source.
    source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=15)
    # A memory backup inherits a WAL-format header; SQLite cannot deserialize
    # that serialized image without a WAL directory. Use a private scratch DB
    # solely to normalize the COPY with supported journal_mode=DELETE. Never
    # edit header bytes or change/checkpoint the live source journal mode.
    scratch = tempfile.TemporaryDirectory(prefix='hermes760-sqlite-', dir='/tmp')
    Path(scratch.name).chmod(0o700)
    destination = Path(scratch.name) / 'snapshot.db'
    target = sqlite3.connect(destination)
    destination.chmod(0o600)
    started = time.monotonic()
    def progress(status, remaining, total):
        if time.monotonic() - started > 90:
            raise TimeoutError('bounded online backup exceeded')
    try:
        source.execute('PRAGMA query_only=ON')
        source.backup(target, pages=256, progress=progress, sleep=0.01)
        target.execute('PRAGMA journal_mode=DELETE')
        result = db_checks(target, name)
        if name == 'state.db':
            for table in ['messages_fts', 'messages_fts_trigram']:
                target.execute('INSERT INTO ' + table + '(' + table + ') VALUES(?)', ('integrity-check',))
            target.commit()
            result['ftsIntegrity'] = 'PASS'
        data = target.serialize()
        result['walObservedBytes'] = Path(str(path) + '-wal').stat().st_size if Path(str(path) + '-wal').exists() else 0
        return data, result
    finally:
        target.close(); source.close(); scratch.cleanup()


def selected_auth(data):
    auth = json.loads(data)
    provider = auth.get('providers', {}).get('openai-codex')
    if not isinstance(provider, dict) or not isinstance(provider.get('tokens'), dict):
        raise ValueError('selected provider shape')
    if not all(isinstance(provider['tokens'].get(k), str) and provider['tokens'][k]
               for k in ['access_token', 'refresh_token']):
        raise ValueError('selected provider tokens absent')
    # No unrelated API-key pool, provider, CLI login or workstation profile.
    result = {k: auth[k] for k in ['version', 'updated_at'] if k in auth}
    result.update(active_provider='openai-codex', providers={'openai-codex': provider},
                  credential_pool={'openai-codex': auth.get('credential_pool', {}).get('openai-codex', [])})
    return encoded(result)


def export_payload(root):
    safe(root, directory=True, owner=os.getuid())
    if sqlite3.sqlite_version_info < (3, 51, 3):
        raise ValueError('SQLite WAL safety floor')
    if root == Path('/opt/data') and read_private(Path('/opt/hermes/.hermes_build_sha')).decode().strip() != REVISION:
        raise ValueError('source build revision changed')
    config = load_config(read_private(root / 'config.yaml', owner=os.getuid()))
    if config.get('_config_version') != 44 or config.get('model', {}).get('provider') != 'openai-codex':
        raise ValueError('source baseline/provider changed')
    files, stable, tree_shapes = {}, {}, {}
    def shape(path):
        result = []
        for parent, dirs, names in os.walk(path, followlinks=False):
            for name in sorted(dirs + names):
                q = Path(parent) / name
                info = q.lstat()
                result.append((str(q.relative_to(path)), stat.S_IFMT(info.st_mode), info.st_uid))
        return sorted(result)
    def add(relative, category, required=False):
        path = root / relative
        safe(path, missing=not required, owner=os.getuid() if path.exists() else None)
        if not path.exists():
            return
        data = read_private(path, owner=os.getuid())
        stable[relative] = digest(data)
        key = category + '/' + relative
        if key in files and files[key] != data:
            raise ValueError('duplicate moved source')
        files[key] = data
    def tree(relative, category):
        path = root / relative
        safe(path, directory=True, missing=True, owner=os.getuid() if path.exists() else None)
        if not path.exists():
            return
        tree_shapes[relative] = shape(path)
        for parent, dirs, names in os.walk(path, followlinks=False):
            for d in dirs:
                safe(Path(parent) / d, directory=True, owner=os.getuid())
            for name in names:
                q = Path(parent) / name
                # Do not migrate source lifecycle locks or any cached code.
                if q.suffix == '.lock' or q.name == '.lock' or q.name.startswith('.lock.'):
                    continue
                add(str(q.relative_to(root)), category)
    checks = {}
    for name in DATABASES:
        data, checks[name] = snapshot_db(root / name, name)
        files['databases/' + name] = data
    for name in STATE_FILES:
        add(name, 'state', required=name == 'SOUL.md')
    for name in NOTEBOOK_FILES:
        add('.notebooklm/' + name, 'credentials', required=True)
    auth_bytes = read_private(root / 'auth.json', owner=os.getuid())
    stable['auth.json'] = digest(auth_bytes)
    files['credentials/auth.json'] = selected_auth(auth_bytes)
    tree('gogcli/config', 'credentials'); tree('gogcli/data/keyring', 'credentials')
    # OAuth client files are part of gog's config/data, never browser profiles.
    for name in ['gogcli/data/credentials.json', 'gogcli/data/credentials-personal.json', 'gogcli/config/credentials.json']:
        add(name, 'credentials')
    for name in QUARANTINE_FILES:
        add(name, 'quarantine')
    for name in QUARANTINE_TREES:
        tree(name, 'quarantine')
    for name in PRIVATE_SKILLS:
        tree('skills/' + name, 'quarantine')
    if len(files) > MAX_ENTRIES or sum(map(len, files.values())) > MAX_TOTAL:
        raise ValueError('payload bound')
    # The ordinary files, including auth/config/memory/queues, must remain byte
    # stable over the export. A live source can change AFTER this observation.
    for relative, checksum in stable.items():
        if digest(read_private(root / relative, owner=os.getuid())) != checksum:
            raise ValueError('source moved; refresh export')
    for relative, expected_shape in tree_shapes.items():
        if shape(root / relative) != expected_shape:
            raise ValueError('source directory membership moved; refresh export')
    manifest = {'schemaVersion': 1, 'kind': 'NON_AUTHORITATIVE_STAGING', 'version': VERSION,
                'revision': REVISION, 'consistency': 'PER_DATABASE_ONLINE_BACKUP_NOT_GLOBAL',
                'ordinaryFilesStable': True, 'databases': checks,
                'files': {key: {'sha256': digest(data), 'size': len(data)} for key, data in files.items()},
                'excluded': ['.env', 'Telegram token/identities', 'gog keyring password', 'nonselected provider pools',
                             'live WAL/SHM/locks/PIDs/heartbeats', 'logs/request dumps/backups',
                             'caches/binaries/browser profiles', 'nested notes mount', 'unknown state retained on NAS'],
                'queuePolicy': 'QUARANTINE_NO_REPLAY; active DB claims/obligations removed ONLY from staging copy'}
    files['manifest.json'] = encoded(manifest)
    return files


def write_tar(files, stream):
    with tarfile.open(fileobj=stream, mode='w|', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            member = tarfile.TarInfo(name); member.size = len(data); member.mode = 0o600
            member.uid = member.gid = 1000
            archive.addfile(member, io.BytesIO(data))


def allowed_member(name):
    if name == 'manifest.json':
        return True
    if name.startswith('databases/'):
        return name.removeprefix('databases/') in DATABASES
    if name.startswith('state/'):
        return name.removeprefix('state/') in STATE_FILES
    if name == 'credentials/auth.json':
        return True
    if name.startswith('credentials/.notebooklm/'):
        return name.removeprefix('credentials/.notebooklm/') in NOTEBOOK_FILES
    if name in {'credentials/gogcli/config/config.json', 'credentials/gogcli/config/credentials.json'}:
        return True
    if name.startswith('credentials/gogcli/data/keyring/'):
        relative = name.removeprefix('credentials/gogcli/data/keyring/')
        return '/' not in relative and not relative.startswith('.') and not relative.endswith('.lock')
    if name in {'credentials/gogcli/data/credentials.json', 'credentials/gogcli/data/credentials-personal.json'}:
        return True
    if name.startswith('quarantine/'):
        relative = name.removeprefix('quarantine/')
        return relative in QUARANTINE_FILES or any(relative.startswith(p + '/') for p in QUARANTINE_TREES) or any(
            relative.startswith('skills/' + p + '/') for p in PRIVATE_SKILLS)
    return False


def read_tar(stream):
    files, total = {}, 0
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for member in archive:
            name = member.name; pure = PurePosixPath(name)
            if (pure.is_absolute() or str(pure) != name or any(c in name for c in '\\' + '\n\r\t\x00') or any(p in {'.', '..'} for p in pure.parts)
                    or not member.isreg() or member.uid != 1000 or member.gid != 1000
                    or not allowed_member(name) or name in files or member.size < 0 or member.size > MAX_FILE):
                raise ValueError('unsafe/unapproved archive member')
            total += member.size
            if total > MAX_TOTAL or len(files) >= MAX_ENTRIES:
                raise ValueError('archive bounds')
            data = archive.extractfile(member).read(MAX_FILE + 1)
            if len(data) != member.size:
                raise ValueError('truncated archive')
            files[name] = data
    manifest = json.loads(files.pop('manifest.json'))
    if (manifest.get('kind') != 'NON_AUTHORITATIVE_STAGING' or manifest.get('version') != VERSION
            or manifest.get('revision') != REVISION or not manifest.get('ordinaryFilesStable')
            or manifest.get('consistency') != 'PER_DATABASE_ONLINE_BACKUP_NOT_GLOBAL'):
        raise ValueError('manifest baseline/gate')
    if manifest['files'] != {name: {'sha256': digest(data), 'size': len(data)} for name, data in files.items()}:
        raise ValueError('manifest mismatch')
    if any('databases/' + n not in files for n in DATABASES):
        raise ValueError('seven databases required')
    # Independently reapply selected-provider filtering; never trust producer labels.
    if selected_auth(files['credentials/auth.json']) != files['credentials/auth.json']:
        raise ValueError('nonselected credential refused')
    for name in NOTEBOOK_FILES:
        if 'credentials/.notebooklm/' + name not in files:
            raise ValueError('minimal NotebookLM state missing')
    return files, manifest


def metadata():
    m = json.loads(METADATA.read_text())
    if (m['version'] != VERSION or m['revision'] != REVISION or m['gatewayEnabled']
            or m['productionStateTransferred'] or m['vaultSafety']['productionWrites'] != 'DISABLED'):
        raise ValueError('installed safety/baseline gate')
    expected = {
        'state': '/home/johna/.local/state/hermes-native/staging/baseline-0.21.2',
        'home': '/home/johna/.local/share/hermes-native/staging/baseline-0.21.2/home',
        'config': '/home/johna/.config/hermes-native/staging/baseline-0.21.2',
        'cache': '/home/johna/.cache/hermes-native/staging/baseline-0.21.2'}
    if (m['paths'] != expected or m['environment']['NOTEBOOKLM_HOME'] != expected['home'] + '/.notebooklm'
            or m['environment']['GOG_HOME'] != expected['state'] + '/gogcli'
            or m['stateStaging']['archives'] != '/home/johna/.local/state/hermes-native/state-imports/baseline-0.21.2'):
        raise ValueError('metadata-selected root mismatch')
    for path in [*m['paths'].values(), m['stateStaging']['archives']]:
        safe(Path(path), directory=True, missing=True, owner=os.getuid() if Path(path).exists() else None)
    return m


def prepare_database(data, name):
    c = sqlite3.connect(':memory:')
    try:
        c.deserialize(data)
        original = db_checks(c, name)
        removed = {}
        if name == 'state.db':
            for table in ['messages_fts', 'messages_fts_trigram']:
                c.execute('INSERT INTO ' + table + '(' + table + ') VALUES(?)', ('integrity-check',))
            c.commit()
            for table in TRANSIENT_TABLES:
                if table in original['counts']:
                    removed[table] = original['counts'][table]
                    c.execute('DELETE FROM ' + table)
            c.commit()
        c.execute('PRAGMA journal_mode=DELETE')
        result = db_checks(c, name)
        if result['schema'] != original['schema']:
            raise ValueError('unexpected schema mutation')
        return c.serialize(), result, removed
    finally:
        c.close()


def merged_config(existing, source, state):
    config = load_config(existing)
    original = load_config(source)
    if config.get('_config_version') != 44 or original.get('_config_version') != 44:
        raise ValueError('config schema mismatch')
    model = original.get('model')
    if (not isinstance(model, dict) or model.get('provider') != 'openai-codex'
            or model.get('base_url') != 'https://chatgpt.com/backend-api/codex'
            or not isinstance(model.get('default'), str) or len(model['default']) > 128):
        raise ValueError('selected model mismatch')
    config['model'] = {key: model[key] for key in ['provider', 'default', 'base_url']}
    # Only the selected model is merged now. All other NAS preferences remain
    # privately preserved for explicit review; managed policy/isolation wins.
    if (config.get('platforms', {}).get('telegram', {}).get('enabled') is not False
            or config.get('mcp_servers') or config.get('platform_toolsets') != {'cli': [], 'telegram': []}
            or config.get('terminal') != {'backend': 'local', 'cwd': str(state / 'workspace')}):
        raise ValueError('offline overlay drift')
    return encoded(config)


def targets(files, m, existing):
    state, home = Path(m['paths']['state']), Path(m['paths']['home'])
    writes, checks, removed = {}, {}, {}
    for key, data in files.items():
        if key.startswith('databases/'):
            relative = key.removeprefix('databases/')
            output, checks[relative], dropped = prepare_database(data, relative)
            writes[state / relative] = output
            removed.update(dropped)
        elif key.startswith('state/'):
            writes[state / key.removeprefix('state/')] = data
        elif key.startswith('credentials/.notebooklm/'):
            writes[home / '.notebooklm' / key.removeprefix('credentials/.notebooklm/')] = data
        elif key.startswith('credentials/'):
            writes[state / key.removeprefix('credentials/')] = data
    writes[state / 'config.yaml'] = merged_config(existing, files['quarantine/config.yaml'], state)
    return writes, checks, removed


def foundation_seed(path, state):
    if path == state / 'SOUL.md':
        from hermes_cli.default_soul import DEFAULT_SOUL_MD
        return read_private(path) == DEFAULT_SOUL_MD.encode()
    if path == state / 'state.db':
        if any(Path(str(path) + suffix).exists() for suffix in ['-wal', '-shm', '-journal']):
            return False
        c = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_schema WHERE type='table'")]
            known = {'schema_version', 'system_prompts', 'sessions', 'messages', 'sqlite_sequence',
                     'session_model_usage', 'state_meta', 'gateway_routing', 'gateway_hygiene_state',
                     'conversation_generations', *TRANSIENT_TABLES}
            return bool(tables) and all(t in known or t.startswith('messages_fts') for t in tables) and all(
                c.execute('SELECT count(*) FROM "' + t.replace('"', '""') + '"').fetchone()[0] == 0 for t in tables)
        finally:
            c.close()
    return False


def import_payload(stream, m):
    files, manifest = read_tar(stream)
    state = Path(m['paths']['state']); archives = Path(m['stateStaging']['archives'])
    mkdir(archives)
    lock = archives / '.import.lock'; safe(lock, missing=True)
    with lock.open('a+b') as held:
        held.flush(); os.chmod(lock, 0o600); fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt_path = state / 'state-staging.json'; safe(receipt_path, missing=True)
        previous = json.loads(read_private(receipt_path)) if receipt_path.exists() else None
        if previous:
            verify_receipt(previous, m)
        existing = read_private(state / 'config.yaml', owner=os.getuid())
        writes, checks, removed = targets(files, m, existing)
        if previous and set(previous['files']) - {str(p) for p in writes}:
            raise ValueError('source removed an imported path; retain target and require review')
        before = {}
        before_attributes = {}
        def attributes(path):
            info = path.stat()
            return {'mode': stat.S_IMODE(info.st_mode), 'mtime_ns': info.st_mtime_ns,
                    'ctime_ns': info.st_ctime_ns, 'uid': info.st_uid, 'gid': info.st_gid,
                    'inode': info.st_ino, 'device': info.st_dev}
        for path in writes:
            safe(path, missing=True, owner=os.getuid() if path.exists() else None)
            # Imported paths are exclusively owned by this receipt. First import
            # permits only config and explicitly recognized empty/default seeds.
            if path.exists() and not previous and path != state / 'config.yaml' and not foundation_seed(path, state):
                raise ValueError('unowned existing state preserved')
            before[str(path)] = digest(read_private(path)) if path.exists() else None
            before_attributes[str(path)] = attributes(path) if path.exists() else None
            for parent in path.parents:
                if parent in {state, Path(m['paths']['home'])}:
                    break
                safe(parent, directory=True, missing=True, owner=os.getuid() if parent.exists() else None)
        bundle = Path(tempfile.mkdtemp(prefix='import-760-', dir=archives)); bundle.chmod(0o700)
        for key, data in files.items():
            atomic(bundle / 'source' / key, data)
        atomic(bundle / 'manifest.json', encoded(manifest))
        # Preserve exact native preimages before any target modification. Retained
        # namespace is never automatically deleted, restored or made authoritative.
        for path in writes:
            if path.exists():
                root = state if state in path.parents else Path(m['paths']['home'])
                label = 'state' if root == state else 'home'
                atomic(bundle / 'target-before' / label / path.relative_to(root), read_private(path))
        journal_path = archives / 'transaction.json'
        safe(journal_path, missing=True)
        if journal_path.exists() and json.loads(read_private(journal_path)).get('status') != 'COMPLETE':
            raise ValueError('incomplete prior import; private recovery review required')
        journal = {'status': 'INCOMPLETE', 'bundle': str(bundle), 'before': before,
                   'beforeAttributes': before_attributes,
                   'proposed': {str(p): digest(d) for p, d in writes.items()}}
        atomic(journal_path, encoded(journal))
        # Source copies independently pass the native SQLite/FTS schema gate.
        # A failure/crash leaves a fail-closed private preimage/CAS journal; a
        # later invocation refuses rather than silently overwrite partial state.
        changed = 0
        for path, data in writes.items():
            current = digest(read_private(path)) if path.exists() else None
            if (current != before[str(path)] or
                    (attributes(path) if path.exists() else None) != before_attributes[str(path)]):
                raise ValueError('concurrent target movement; stopped')
            # Normalize every newly created nested private parent, not unrelated
            # existing home/config trees or the separately mounted live vault.
            for parent in reversed(path.parents):
                if parent == state or parent == Path(m['paths']['home']) or state in parent.parents or Path(m['paths']['home']) in parent.parents:
                    mkdir(parent)
            changed += atomic(path, data)
        receipt = {'schemaVersion': 1, 'kind': 'NON_AUTHORITATIVE_STAGING',
                   'sourceBundle': str(bundle), 'sourceManifestSha256': digest(encoded(manifest)),
                   'version': VERSION, 'revision': REVISION, 'ordinaryFilesStable': True,
                   'consistency': manifest['consistency'], 'queuePolicy': manifest['queuePolicy'],
                   'files': {str(p): digest(d) for p, d in writes.items()}, 'databases': checks,
                   'stagingOnlyRemovedClaims': removed, 'productionStateTransferred': False,
                   'polling': 'DISABLED', 'delivery': 'DISABLED', 'vaultWrites': 'DISABLED',
                   'codexRefresh': 'FORBIDDEN_WHILE_NAS_OWNS_ROTATING_GRANT',
                   'preferences': 'Selected provider/model merged; other NAS preferences preserved privately only'}
        atomic(bundle / 'receipt.json', encoded(receipt)); atomic(receipt_path, encoded(receipt))
        verify_receipt(receipt, m)
        journal['status'] = 'COMPLETE'
        atomic(journal_path, encoded(journal))
        return {'import': 'PASS', 'databases': len(checks), 'changedFiles': changed,
                'quarantineArtifacts': sum(k.startswith('quarantine/') for k in files),
                'claimTablesQuarantined': len(removed), 'authoritative': False,
                'consistency': manifest['consistency'], 'queueReplay': 'DISABLED'}


def verify_receipt(receipt, m):
    if receipt.get('kind') != 'NON_AUTHORITATIVE_STAGING' or receipt.get('productionStateTransferred') is not False:
        raise ValueError('receipt staging gate')
    roots = [Path(m['paths']['state']), Path(m['paths']['home'])]
    for name, checksum in receipt['files'].items():
        p = Path(name)
        if p.resolve(strict=True) != p or not any(root in p.parents for root in roots):
            raise ValueError('receipt path containment')
        safe(p, owner=os.getuid())
        if stat.S_IMODE(p.stat().st_mode) != 0o600 or digest(read_private(p)) != checksum:
            raise ValueError('staged private drift/permissions')
        for parent in p.parents:
            if parent in roots or any(root in parent.parents for root in roots):
                safe(parent, directory=True, owner=os.getuid())
                if stat.S_IMODE(parent.stat().st_mode) != 0o700:
                    raise ValueError('private parent mode')
    if 'stateStaging' in m:
        bundle = Path(receipt['sourceBundle'])
        if bundle.parent != Path(m['stateStaging']['archives']):
            raise ValueError('source bundle containment')
        original_manifest = read_private(bundle / 'manifest.json', owner=os.getuid())
        if digest(original_manifest) != receipt['sourceManifestSha256']:
            raise ValueError('original snapshot manifest changed')
        manifest = json.loads(original_manifest)
        for relative, info in manifest['files'].items():
            if not allowed_member(relative):
                raise ValueError('original manifest path refused')
            p = bundle / 'source' / relative
            data = read_private(p, owner=os.getuid())
            if digest(data) != info['sha256'] or len(data) != info['size'] or stat.S_IMODE(p.stat().st_mode) != 0o600:
                raise ValueError('original private rollback snapshot changed')
    state = roots[0]
    if read_private(state / '.env'):
        raise ValueError('staging dotenv must remain empty')
    for name in ['pending', 'pending_messages']:
        p = state / name; safe(p, directory=True, missing=True)
        if p.exists() and any(p.iterdir()):
            raise ValueError('live queued files refused')
    config = load_config(read_private(state / 'config.yaml'))
    if config.get('platforms', {}).get('telegram', {}).get('enabled') is not False or config.get('mcp_servers'):
        raise ValueError('transport/MCP staging gate')
    jobs = json.loads(read_private(state / 'cron/jobs.json'))
    if any(j.get('enabled', True) or j.get('deliver') or j.get('failure_deliver') or j.get('next_run_at')
           for j in jobs['jobs']):
        raise ValueError('schedule/delivery gate')
    for name in DATABASES:
        p = state / name
        if any(Path(str(p) + suffix).exists() or Path(str(p) + suffix).is_symlink()
               for suffix in ['-wal', '-shm', '-journal']):
            raise ValueError('staged database sidecars refused; no live owner permitted')
        c = sqlite3.connect(p.as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            result = db_checks(c, name)
            if result['schema'] != receipt['databases'][name]['schema'] or result['counts'] != receipt['databases'][name]['counts']:
                raise ValueError('staged schema/count drift')
        finally:
            c.close()
    return {'stateCheck': 'PASS', 'databases': 7, 'privatePathsPermissions': 'PASS',
            'selectedProvider': 'openai-codex', 'queueReplay': 'DISABLED', 'authoritative': False}


def provision_password(m, stream):
    data = stream.read(16385)
    if not data or len(data) > 16384 or b'\x00' in data:
        raise ValueError('canonical secret unavailable')
    path = Path(m['environment']['GOG_HOME']) / 'keyring-password'
    safe(path.parent, directory=True, owner=os.getuid())
    atomic(path, data)
    return {'canonicalGogPassword': 'PROVISIONED_PRIVATE_FILE', 'source': 'Doppler notes/prd', 'mode': '0600'}


def cli_smoke(operation):
    # Upstream doctor runs a transactional SQLite write-health probe even without
    # --fix. Never aim that probe (or CLI initialization) at receipt-owned state.
    # The launcher mounts selected roots read-only; this copy lives only in tmpfs.
    source = Path(os.environ['HERMES_HOME'])
    destination = Path(tempfile.mkdtemp(prefix='hermes-cli-smoke-', dir='/tmp'))
    from hermes_cli.config import _HERMES_HOME_SUBDIRS
    for relative in _HERMES_HOME_SUBDIRS:
        mkdir(destination / relative)
    for relative in ['config.yaml', '.env', 'auth.json', 'state.db', *STATE_FILES]:
        path = source / relative
        safe(path, missing=True, owner=os.getuid() if path.exists() else None)
        if path.exists():
            atomic(destination / relative, read_private(path))
    environment = dict(os.environ, HERMES_HOME=str(destination))
    argument = {'cli-version': '--version', 'cli-help': '--help', 'cli-doctor': 'doctor'}[operation]
    os.execve(os.environ['HERMES_NATIVE_CLI'], [os.environ['HERMES_NATIVE_CLI'], argument], environment)


def integration_checks():
    # Invoked ONLY by the immutable closed launcher, with explicit env and a
    # private mount/PID namespace. No external config/profile/task code is loaded.
    logging.disable(logging.CRITICAL)
    if os.environ.get('HERMES_NATIVE_STAGE') != 'capabilities-offline':
        raise ValueError('isolated environment required')
    state = Path(os.environ['HERMES_HOME']); home = Path(os.environ['HOME'])
    if os.environ.get('NOTEBOOKLM_HOME') != str(home / '.notebooklm'):
        raise ValueError('NotebookLM HOME layout mismatch')
    results = {}
    from hermes_cli.auth import _load_auth_store, _load_provider_state
    from hermes_cli.auth_codex import _codex_http_client, _codex_usage_probe_url
    from hermes_cli.auth_constants import _decode_jwt_claims
    a = _load_auth_store(); p = _load_provider_state(a, 'openai-codex')
    token = p.get('tokens', {}).get('access_token') if isinstance(p, dict) else None
    claims = _decode_jwt_claims(token or '')
    if not token or not isinstance(claims.get('exp'), (int, float)):
        results['provider'] = 'FAILED_ACCESS_TOKEN_SHAPE_NO_REFRESH'
    elif claims['exp'] <= time.time() + 300:
        results['provider'] = 'EXPIRED_NO_REFRESH_FRESH_EXPORT_REQUIRED'
    else:
        try:
            headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json', 'User-Agent': 'codex-cli'}
            account = (claims.get('https://api.openai.com/auth') or {}).get('chatgpt_account_id')
            if account:
                headers['ChatGPT-Account-Id'] = account
            with _codex_http_client(timeout=15.0) as client:
                response = client.get(_codex_usage_probe_url('https://chatgpt.com/backend-api/codex'), headers=headers)
            results['provider'] = 'PASS_READ_ONLY_USAGE_NO_INFERENCE' if response.status_code == 200 and isinstance(response.json(), dict) else 'FAILED_READ_ONLY_USAGE_HTTP_' + str(response.status_code)
        except Exception:
            results['provider'] = 'FAILED_READ_ONLY_USAGE_NETWORK_OR_SCHEMA'
    results['providerRefresh'] = 'SKIPPED_SINGLE_USE_ROTATION_WOULD_RISK_NAS'
    gog = os.environ['HERMES_NATIVE_GOG']
    gog_env = dict(os.environ)
    password_path = state / 'gogcli/keyring-password'
    safe(password_path, owner=os.getuid())
    if stat.S_IMODE(password_path.stat().st_mode) != 0o600:
        raise ValueError('canonical secret private mode required')
    password = read_private(password_path, owner=os.getuid()).decode().rstrip('\n')
    # gog's file keyring needs a lifecycle lock and may cache a Google access
    # token even for a read-only auth/Calendar command. Permit that ONLY in a
    # disposable tmpfs copy, never in receipt-owned state or the NAS keyring.
    gog_copy = Path(tempfile.mkdtemp(prefix='hermes-gog-read-', dir='/tmp'))
    for relative in ['config/config.json', 'config/credentials.json', 'data/credentials.json', 'data/credentials-personal.json']:
        path = state / 'gogcli' / relative
        safe(path, missing=True)
        if path.exists():
            atomic(gog_copy / relative, read_private(path))
    keyring = state / 'gogcli/data/keyring'
    safe(keyring, directory=True)
    for path in keyring.iterdir():
        relative = 'data/keyring/' + path.name
        if not allowed_member('credentials/gogcli/' + relative):
            raise ValueError('unexpected staged keyring member')
        atomic(gog_copy / relative, read_private(path))
    gog_env.update(GOG_HOME=str(gog_copy), GOG_KEYRING_PASSWORD=password, GOG_KEYRING_BACKEND='file')
    def run(argv, env):
        try:
            r = subprocess.run(argv, env=env, capture_output=True, timeout=180, check=False)
        except (subprocess.TimeoutExpired, OSError):
            return 124, None
        # Never put raw account names, JSON, HTTP messages, cookie or token values
        # in logs/tool output. Return code is NOT enough to claim supported health.
        try:
            value = json.loads(r.stdout)
        except (ValueError, UnicodeError):
            value = None
        return r.returncode, value
    code, auth = run([gog, 'auth', 'list', '--check', '--readonly', '--json', '--no-input'], gog_env)
    accounts = auth.get('accounts', []) if isinstance(auth, dict) else []
    results['calendarAuth'] = 'PASS' if code == 0 and len(accounts) == 2 and all(a.get('valid') is True for a in accounts) else 'FAILED_REFRESH_OR_ACCOUNT_SCHEMA'
    successful = 0
    for account in accounts:
        email = account.get('email')
        if not isinstance(email, str) or not email:
            continue
        e = dict(gog_env, GOG_ACCOUNT=email)
        c, data = run([gog, 'calendar', 'calendars', '--readonly', '--json', '--no-input', '--max=1'], e)
        if c == 0 and isinstance(data, dict) and isinstance(data.get('calendars'), list):
            successful += 1
    results['calendarRead'] = 'PASS_TWO_ACCOUNTS_READ_ONLY' if len(accounts) == successful == 2 else 'FAILED_READ_OR_RESPONSE_SCHEMA'
    c, nlm = run([os.environ['HERMES_NATIVE_NOTEBOOKLM'], 'auth', 'check', '--test', '--passive', '--json'], dict(os.environ))
    checks = nlm.get('checks', {}) if isinstance(nlm, dict) else {}
    results['notebooklm'] = 'PASS_PASSIVE_CSRF_SESSION_FETCH_NO_CONTENT' if c == 0 and nlm.get('status') == 'ok' and all(checks.get(k) is True for k in ['storage_exists', 'json_valid', 'cookies_present', 'token_fetch']) else 'FAILED_PASSIVE_AUTH_OR_SCHEMA'
    results.update(telegram='SKIPPED_TOKEN_NOT_PROVISIONED_NO_POLLING_OR_SENDS', messages='UNSUPPORTED_SCHEMA_DISABLED',
                   notebooklmContent='SKIPPED_NO_NOTEBOOK_LIST_SOURCE_CREATION_OR_UPLOAD',
                   inference='SKIPPED_NO_PAID_OR_FREE_MODEL_CALL', calendarMutations='SKIPPED')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['export', 'import', 'verify', 'state-check', 'provision-gog', 'integrations', 'cli-version', 'cli-help', 'cli-doctor'])
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.operation.startswith('cli-'):
            cli_smoke(args.operation)
            return
        if args.operation == 'export':
            # This script is delivered over stdin, not installed into source state.
            write_tar(export_payload(Path('/opt/data')), sys.stdout.buffer)
            return
        if args.operation == 'integrations':
            result = integration_checks()
        elif args.operation == 'state-check':
            m = {'paths': {'state': os.environ['HERMES_HOME'], 'home': os.environ['HOME']}}
            result = verify_receipt(json.loads(read_private(Path(m['paths']['state']) / 'state-staging.json')), m)
        else:
            m = metadata()
            if args.operation == 'import':
                result = import_payload(sys.stdin.buffer, m)
            elif args.operation == 'provision-gog':
                result = provision_password(m, sys.stdin.buffer)
            else:
                result = verify_receipt(json.loads(read_private(Path(m['paths']['state']) / 'state-staging.json')), m)
        print(json.dumps(result, sort_keys=True))
        if any(str(v).startswith(('FAILED', 'EXPIRED')) for v in result.values()):
            raise SystemExit(2)
    except (Exception, KeyboardInterrupt):
        # No traceback, exception text, private paths/names, provider response or
        # payload values may cross the private channel into tool/system logs.
        print('Restricted Hermes staging refused; private inputs preserved; inspect scoped gates.', file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
