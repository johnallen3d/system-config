#!/usr/bin/env python3
"""#760 synthetic staging regressions. Never reads NAS, private accounts or notes."""
import importlib.util
import io
import json
import os
import sqlite3
import stat
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('state_stage', ROOT / 'modules/home-manager/hermes-native/state-stage.py')
stage = importlib.util.module_from_spec(spec); spec.loader.exec_module(stage)


def refused(function):
    try:
        function()
    except (ValueError, OSError, sqlite3.Error, KeyError):
        return
    raise AssertionError('unsafe operation accepted')


def archive(files):
    out = io.BytesIO(); stage.write_tar(files, out); out.seek(0); return out


def fixtures(base):
    source, state, home = [base / n for n in ['source', 'state', 'home']]
    for p in [source, state, home]:stage.mkdir(p)
    model = {'provider': 'openai-codex', 'default': 'synthetic-model', 'base_url': 'https://chatgpt.com/backend-api/codex'}
    stage.atomic(source / 'config.yaml', stage.encoded({'_config_version': 44, 'model': model, 'terminal': {'cwd': '/opt/data/workspaces/notes'}}))
    stage.atomic(state / 'config.yaml', stage.encoded({'_config_version': 44, 'terminal': {'cwd': str(state / 'workspace'), 'backend': 'local'},
                    'platforms': {'telegram': {'enabled': False}}, 'platform_toolsets': {'cli': [], 'telegram': []}, 'mcp_servers': {}}))
    stage.atomic(state / '.env', b'')
    stage.atomic(state / 'cron/jobs.json', stage.encoded({'jobs': [{'name': 'pi-cielo-morning-brief', 'enabled': False,
                 'deliver': None, 'failure_deliver': None, 'next_run_at': None}]}))
    stage.atomic(source / 'auth.json', stage.encoded({'version': 1, 'providers': {'openai-codex': {'tokens': {'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh'}},
                 'unrelated': {'key': 'synthetic-not-authorized'}}, 'credential_pool': {'openai-api': [{'api_key': 'synthetic-unrelated'}], 'openai-codex': []}}))
    for n in stage.STATE_FILES:stage.atomic(source / n, b'SYNTHETIC PRIVATE FIXTURE\n')
    for n in stage.NOTEBOOK_FILES:stage.atomic(source / '.notebooklm' / n, stage.encoded({'synthetic': True}))
    stage.atomic(source / 'gogcli/config/config.json', stage.encoded({'keyring_backend': 'file'}))
    stage.atomic(source / 'gogcli/data/keyring/_synthetic', b'SYNTHETIC ENCRYPTED KEYRING')
    stage.atomic(source / 'gogcli/data/keyring/.lock', b'SYNTHETIC LOCK NOT IMPORTED')
    stage.atomic(source / 'gogcli/data/credentials.json', stage.encoded({'synthetic': True}))
    stage.atomic(source / 'pending/synthetic.json', stage.encoded({'delivery': 'DO NOT REPLAY'}))
    for name in stage.DATABASES:
        p = source / name; stage.mkdir(p.parent)
        with sqlite3.connect(p) as db:
            if name == 'state.db':
                db.executescript('''CREATE TABLE schema_version(version INTEGER); INSERT INTO schema_version VALUES(30);
                    CREATE TABLE sessions(id TEXT PRIMARY KEY); CREATE TABLE messages(id INTEGER PRIMARY KEY,session_id TEXT REFERENCES sessions(id),body TEXT);
                    INSERT INTO sessions VALUES('synthetic'); INSERT INTO messages VALUES(1,'synthetic','synthetic message');
                    CREATE VIRTUAL TABLE messages_fts USING fts5(body); CREATE VIRTUAL TABLE messages_fts_trigram USING fts5(body,tokenize='trigram');
                    INSERT INTO messages_fts VALUES('synthetic'); INSERT INTO messages_fts_trigram VALUES('synthetic');''')
                for table in stage.TRANSIENT_TABLES:
                    db.execute('CREATE TABLE ' + table + '(intent TEXT)');db.execute('INSERT INTO ' + table + " VALUES('synthetic no replay')")
            else:db.executescript("CREATE TABLE history(id INTEGER PRIMARY KEY,data TEXT);INSERT INTO history VALUES(1,'synthetic history');")
        p.chmod(0o600)
    m = {'paths': {'state': str(state), 'home': str(home)}, 'stateStaging': {'archives': str(base / 'archives')},
         'environment': {'GOG_HOME': str(state / 'gogcli')}}
    return source, state, home, m


def main():
    os.umask(0o077)
    assert 'refresh_codex_oauth' not in (ROOT / 'modules/home-manager/hermes-native/state-stage.py').read_text()
    # Regression for the inherited disposable Syncthing fixture: temporary file
    # absence must retry, while persistent absence must still time out/fail.
    fixture_spec = importlib.util.spec_from_file_location('vault_fixture', ROOT / 'modules/home-manager/hermes-native/vault-fixture.py')
    fixture = importlib.util.module_from_spec(fixture_spec); fixture_spec.loader.exec_module(fixture)
    attempts = [0]
    def converging():
        attempts[0] += 1
        if attempts[0] == 1:
            raise FileNotFoundError('SYNTHETIC ASYNC ABSENCE')
        return True
    fixture.wait(converging, timeout=1)
    assert attempts[0] == 2
    try:
        fixture.wait(lambda: (_ for _ in ()).throw(FileNotFoundError('SYNTHETIC PERSISTENT ABSENCE')), timeout=.01)
    except RuntimeError:
        pass
    else:
        raise AssertionError('missing disposable peer accepted as converged')
    print('PASS disposable convergence missing-file retry and bounded failure; no network')
    if sqlite3.sqlite_version_info < (3, 51, 3):
        print('SKIP local SQLite online-backup acceptance: interpreter below WAL safety floor; mandatory on installed runtime')
        return
    with tempfile.TemporaryDirectory(prefix='hermes-state-synthetic-') as d:
        source, state, home, m = fixtures(Path(d).resolve())
        # Keep WAL open/nonempty; copying the main file alone would lose this row.
        live = sqlite3.connect(source / 'state.db')
        live.execute('PRAGMA journal_mode=WAL'); live.execute('INSERT INTO messages VALUES(2,?,?)', ('synthetic', 'synthetic WAL row'));live.commit()
        files = stage.export_payload(source)
        assert stage.DATABASES and len(stage.DATABASES) == 7
        assert b'synthetic-not-authorized' not in files['credentials/auth.json']
        assert b'synthetic-unrelated' not in files['credentials/auth.json']
        assert 'credentials/gogcli/data/keyring/.lock' not in files
        assert 'quarantine/pending/synthetic.json' in files
        snapshot, manifest = stage.read_tar(archive(files))
        assert manifest['databases']['state.db']['counts']['messages'] == 2
        assert manifest['databases']['state.db']['walObservedBytes'] > 0
        source_hashes = {n: stage.digest(stage.read_private(source / n)) for n in stage.STATE_FILES}
        # The old smoke launcher generated an empty DB/default SOUL. Only those
        # exact foundation preimages are eligible, never customized/nonempty state.
        seed_db = state / 'state.db'
        with sqlite3.connect(seed_db) as seed:
            seed.execute('CREATE TABLE schema_version(version INTEGER)')
        seed_db.chmod(0o600)
        assert stage.foundation_seed(seed_db, state)
        with sqlite3.connect(seed_db) as seed:
            seed.execute('INSERT INTO schema_version VALUES(30)')
        assert not stage.foundation_seed(seed_db, state)
        refused(lambda: stage.import_payload(archive(files), m))
        with sqlite3.connect(seed_db) as seed:
            seed.execute('DELETE FROM schema_version')
        Path(str(seed_db) + '-wal').touch(mode=0o600)
        assert not stage.foundation_seed(seed_db, state)
        Path(str(seed_db) + '-wal').unlink()
        try:
            from hermes_cli.default_soul import DEFAULT_SOUL_MD
        except ModuleNotFoundError:
            print('SKIP local exact upstream SOUL seed: mandatory on installed interpreter')
        else:
            stage.atomic(state / 'SOUL.md', DEFAULT_SOUL_MD.encode(), mode=0o660)
            assert stage.foundation_seed(state / 'SOUL.md', state)
            stage.atomic(state / 'SOUL.md', b'SYNTHETIC CUSTOM SOUL')
            assert not stage.foundation_seed(state / 'SOUL.md', state)
            refused(lambda: stage.import_payload(archive(files), m))
            stage.atomic(state / 'SOUL.md', DEFAULT_SOUL_MD.encode(), mode=0o660)
        seed_before = stage.read_private(seed_db)
        first = stage.import_payload(archive(files), m)
        journal = json.loads((Path(m['stateStaging']['archives']) / 'transaction.json').read_bytes())
        assert journal['beforeAttributes'][str(seed_db)]['mode'] == 0o600
        assert (Path(journal['bundle']) / 'target-before/state/state.db').read_bytes() == seed_before
        assert first['databases'] == 7 and first['authoritative'] is False
        assert not (state / 'pending/synthetic.json').exists()
        assert (home / '.notebooklm/profiles/default/storage_state.json').is_file()
        assert not (state / '.notebooklm').exists()
        receipt = json.loads((state / 'state-staging.json').read_bytes())
        assert stage.verify_receipt(receipt, m)['stateCheck'] == 'PASS'
        c = sqlite3.connect(state / 'state.db')
        assert c.execute('SELECT count(*) FROM messages').fetchone()[0] == 2
        for table in stage.TRANSIENT_TABLES:assert c.execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0
        c.close()
        before = {name: Path(name).stat().st_mtime_ns for name in receipt['files']}
        second = stage.import_payload(archive(files), m)
        assert second['changedFiles'] == 0
        assert before == {name: Path(name).stat().st_mtime_ns for name in receipt['files']}
        assert source_hashes == {n: stage.digest(stage.read_private(source / n)) for n in stage.STATE_FILES}
        assert live.execute('SELECT count(*) FROM delivery_obligations').fetchone()[0] == 1
        assert (Path(receipt['sourceBundle']) / 'source/databases/state.db').read_bytes() == files['databases/state.db']
        print('PASS seven-DB online WAL backup, integrity/FTS/relationships, immutable original retention, private path mapping, source untouched, queue quarantine and exact re-import bytes/mtime')
        # Source movement, permissions, unowned paths, hardlinks and symlinks stop.
        sidecar = Path(str(state / 'state.db') + '-wal')
        sidecar.touch(mode=0o600)
        refused(lambda: stage.verify_receipt(receipt, m))
        sidecar.unlink()
        stage.atomic(state / 'SOUL.md', b'SYNTHETIC DRIFT')
        refused(lambda: stage.import_payload(archive(files), m))
        stage.atomic(state / 'SOUL.md', snapshot['state/SOUL.md'])
        (state / 'SOUL.md').chmod(0o644)
        refused(lambda: stage.verify_receipt(json.loads((state / 'state-staging.json').read_bytes()), m))
        (state / 'SOUL.md').chmod(0o600)
        (source / 'SOUL.md').unlink();(source / 'SOUL.md').symlink_to('auth.json')
        refused(lambda: stage.export_payload(source))
        (source / 'SOUL.md').unlink();stage.atomic(source / 'SOUL.md', snapshot['state/SOUL.md'])
        os.link(source / 'SOUL.md', source / 'hardlink')
        refused(lambda: stage.export_payload(source))
        (source / 'hardlink').unlink()
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE), ('state/../escape', tarfile.REGTYPE),
                           ('credentials/gogcli/config/unreviewed.py', tarfile.REGTYPE), ('state/SOUL.md', tarfile.SYMTYPE),
                           ('state/SOUL.md', tarfile.LNKTYPE), ('state/SOUL.md', tarfile.FIFOTYPE)]:
            out=io.BytesIO()
            with tarfile.open(fileobj=out,mode='w') as t:
                member=tarfile.TarInfo(name);member.type=kind;member.uid=member.gid=1000
                t.addfile(member)
            out.seek(0);refused(lambda: stage.read_tar(out))
        corrupt = dict(files);corrupt['state/SOUL.md'] = b'SYNTHETIC CORRUPTION'
        refused(lambda: stage.read_tar(archive(corrupt)))
        print('PASS private drift/mode, source links, archive traversal/absolute/code/link/special-file and checksum refusals')
        stage.provision_password(m, io.BytesIO(b'SYNTHETIC CANONICAL PASSWORD'))
        assert stat.S_IMODE((state / 'gogcli/keyring-password').stat().st_mode) == 0o600
        refused(lambda: stage.provision_password(m, io.BytesIO(b'')))
        stage.atomic(Path(m['stateStaging']['archives']) / 'transaction.json', stage.encoded({'status': 'INCOMPLETE'}))
        refused(lambda: stage.import_payload(archive(files), m))
        print('PASS canonical stdin-only private secret and incomplete-import fail-closed recovery journal')
        live.close()
    print('Synthetic #760 staging suite passed; no network, inference, profiles, real notes or credentials')


if __name__ == '__main__':main()
