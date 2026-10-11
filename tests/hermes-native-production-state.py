#!/usr/bin/env python3
"""#763 durable checkpoint/reverse-CAS fixtures. No live state, auth or restore."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'modules/home-manager/hermes-native/production-state.py'
spec = importlib.util.spec_from_file_location('production_state', MODULE)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class DurableState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hermes763-fixture-')
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir(mode=0o700)
        for n in p.DATABASES:
            f = self.source / n
            f.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            c = sqlite3.connect(f)
            if n == 'state.db':
                c.executescript('''CREATE TABLE schema_version(version INTEGER); INSERT INTO schema_version VALUES(30);
CREATE TABLE sessions(id TEXT PRIMARY KEY); CREATE TABLE messages(id INTEGER PRIMARY KEY,session_id TEXT REFERENCES sessions(id),content TEXT);
CREATE VIRTUAL TABLE messages_fts USING fts5(content);
CREATE VIRTUAL TABLE messages_fts_trigram USING fts5(content,tokenize='trigram');
CREATE TABLE gateway_heartbeats(id TEXT); CREATE TABLE compression_locks(id TEXT);
CREATE TABLE session_turn_leases(id TEXT); CREATE TABLE async_delegations(id TEXT);
CREATE TABLE delivery_obligations(obligation_id TEXT PRIMARY KEY,state TEXT,content TEXT);
INSERT INTO sessions VALUES('public-fixture-session'); INSERT INTO messages VALUES(1,'public-fixture-session','SYNTHETIC CHECKPOINT');
INSERT INTO delivery_obligations VALUES('public-delivery','delivered','SYNTHETIC DELIVERED');''')
            else:
                c.executescript('CREATE TABLE durable(id TEXT PRIMARY KEY,value TEXT); INSERT INTO durable VALUES("public-id","SYNTHETIC HISTORY");')
            c.commit(); c.close(); f.chmod(0o600)
        (self.source / 'auth.json').write_text('{"public_fixture":"original"}\n')
        (self.source / 'auth.json').chmod(0o600)
        self.names = [*p.DATABASES, 'auth.json']

    def tearDown(self):
        self.tmp.cleanup()

    def cold(self, root=None):
        return p.checkpoint(root or self.source, self.names, exclusive_owner=True)

    def test_delivered_history_and_seven_stores_preserved(self):
        data, receipt = self.cold()
        before = {n: p.signature(self.source / n) for n in self.names}
        normalized, checks = p.normalized_databases(data, receipt)
        self.assertEqual(len(checks), 7)
        for n in p.DATABASES:
            self.assertEqual(p.logical_rows(data[n], n), p.logical_rows(normalized[n], n))
        c = sqlite3.connect(':memory:'); c.deserialize(normalized['state.db'])
        self.assertEqual(c.execute('SELECT count(*) FROM delivery_obligations').fetchone()[0], 1)
        c.close()
        self.assertEqual(before, {n: p.signature(self.source / n) for n in self.names})

    def test_actual_wal_included_and_copy_only_normalization(self):
        c = sqlite3.connect(self.source / 'state.db')
        c.execute('PRAGMA journal_mode=WAL')
        c.execute("INSERT INTO messages VALUES(2,'public-fixture-session','SYNTHETIC WAL MESSAGE')")
        c.commit()
        try:
            data, receipt = self.cold()
            self.assertIn('state.db-wal', data)
            before = {n: p.signature(self.source / n) for n in data}
            normalized, _ = p.normalized_databases(data, receipt)
            check = sqlite3.connect(':memory:'); check.deserialize(normalized['state.db'])
            self.assertEqual(check.execute('SELECT count(*) FROM messages').fetchone()[0], 2)
            check.close()
            self.assertEqual(before, {n: p.signature(self.source / n) for n in data})
        finally:
            c.close()

    def test_unknown_pending_delivery_refused_not_purged(self):
        c = sqlite3.connect(self.source / 'state.db')
        c.execute("INSERT INTO delivery_obligations VALUES('pending-id','pending','SYNTHETIC PENDING')")
        c.commit(); c.close()
        data, receipt = self.cold()
        with self.assertRaisesRegex(ValueError, 'delivery'):
            p.normalized_databases(data, receipt)

    def test_leases_delegations_refused_not_erased(self):
        c = sqlite3.connect(self.source / 'state.db')
        c.execute("INSERT INTO session_turn_leases VALUES('stale-fixture')"); c.commit(); c.close()
        with self.assertRaisesRegex(ValueError, 'lifecycle'):
            p.normalized_databases(*self.cold())

    def test_archive_link_checksum_namespace_and_owner_refusals(self):
        data, receipt = self.cold()
        altered = dict(data); altered['auth.json'] = b'altered'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            p.validate_checkpoint(altered, receipt)
        with self.assertRaisesRegex(ValueError, 'stopped'):
            p.checkpoint(self.source, self.names, exclusive_owner=False)
        destination = self.root / 'destination'; destination.mkdir(mode=0o700)
        mapping = {n: n for n in self.names}
        with self.assertRaisesRegex(ValueError, 'namespace'):
            p.mapped_plan(data, receipt, destination=destination, namespace='staging/baseline-0.21.2', mapping=mapping)
        bad = dict(mapping); bad['auth.json'] = '../outside'
        with self.assertRaisesRegex(ValueError, 'relative'):
            p.mapped_plan(data, receipt, destination=destination, namespace='production/baseline-0.21.2', mapping=bad)
        (destination / 'auth.json').symlink_to(self.source / 'auth.json')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            p.mapped_plan(data, receipt, destination=destination, namespace='production/baseline-0.21.2', mapping=mapping)

    def test_synthetic_seven_store_branch_reverse_and_exact_repeat_noop(self):
        import shutil
        checkpoint, receipt = self.cold()
        incident = self.root / 'incident'; shutil.copytree(self.source, incident)
        c = sqlite3.connect(incident / 'state.db')
        c.execute("INSERT INTO sessions VALUES('new-native-session')")
        c.execute("INSERT INTO messages VALUES(2,'new-native-session','SYNTHETIC NEW NATIVE CONVERSATION')")
        c.commit(); c.close()
        (incident / 'auth.json').write_text('{"public_fixture":"latest-native-credential"}\n')
        native, native_receipt = self.cold(incident)
        outputs, _ = p.validate_reverse(checkpoint, receipt, native, native_receipt,
                                       {n: p.signature(self.source / n) for n in checkpoint})
        outputs['auth.json'] = native['auth.json']
        evidence = self.root / 'apply'; evidence.mkdir(mode=0o700)
        expected = {n: p.signature(self.source / n) for n in outputs}
        with self.assertRaisesRegex(ValueError, 'authority'):
            p.apply_cas(self.source, outputs, expected, restore_authorized=False, evidence=evidence)
        result = p.apply_cas(self.source, outputs, expected, restore_authorized=True, evidence=evidence)
        self.assertGreater(result['changedFiles'], 0)
        c = sqlite3.connect(self.source / 'state.db')
        self.assertEqual(c.execute('SELECT count(*) FROM messages').fetchone()[0], 2)
        self.assertEqual(c.execute('SELECT count(*) FROM delivery_obligations').fetchone()[0], 1); c.close()
        self.assertEqual((self.source / 'auth.json').read_bytes(), native['auth.json'])
        before = {n: p.signature(self.source / n) for n in outputs}
        evidence2 = self.root / 'repeat'; evidence2.mkdir(mode=0o700)
        repeat = p.apply_cas(self.source, outputs, before, restore_authorized=True, evidence=evidence2)
        self.assertEqual(repeat['changedFiles'], 0)
        self.assertEqual(before, {n: p.signature(self.source / n) for n in outputs})
        self.assertEqual(json.loads((evidence / 'transaction.json').read_text())['status'], 'COMPLETE')

    def test_reverse_preserves_existing_parent_modes_and_file_owner_mode(self):
        self.source.chmod(0o750)
        (self.source / 'cron').chmod(0o755)
        (self.source / 'auth.json').chmod(0o640)
        data, receipt = self.cold()
        plan = dict(data); plan['auth.json'] = b'{"public_fixture":"changed"}\n'
        evidence = self.root / 'retained'; evidence.mkdir(mode=0o700)
        before = p.signature(self.source / 'auth.json')
        p.apply_cas(self.source, plan, receipt['files'], restore_authorized=True, evidence=evidence)
        self.assertEqual(self.source.stat().st_mode & 0o777, 0o750)
        self.assertEqual((self.source / 'cron').stat().st_mode & 0o777, 0o755)
        after = p.signature(self.source / 'auth.json')
        self.assertEqual({k: before[k] for k in ('mode', 'uid', 'gid')},
                         {k: after[k] for k in ('mode', 'uid', 'gid')})
        self.assertEqual((evidence / 'preimages/auth.json').read_bytes(), data['auth.json'])
        journal = json.loads((evidence / 'transaction.json').read_bytes())
        self.assertEqual(journal['expected']['auth.json'], before)

    def test_checkpoint_receipt_version_and_policy_refused(self):
        data, receipt = self.cold()
        for field, value in [('schemaVersion', 2), ('queuePolicy', 'PURGE')]:
            bad = dict(receipt); bad[field] = value
            with self.assertRaisesRegex(ValueError, 'identity'):
                p.validate_checkpoint(data, bad)

    def test_divergent_nas_and_incomplete_transaction_stop(self):
        data, receipt = self.cold()
        current = {n: p.signature(self.source / n) for n in data}
        (self.source / 'auth.json').write_text('SYNTHETIC CONCURRENT NAS CHANGE')
        with self.assertRaisesRegex(ValueError, 'diverged'):
            p.validate_reverse(data, receipt, data, receipt,
                               {n: p.signature(self.source / n) for n in data})
        evidence = self.root / 'incomplete'; evidence.mkdir(mode=0o700)
        (evidence / 'transaction.json').write_text('{"status":"INCOMPLETE"}')
        with self.assertRaisesRegex(ValueError, 'transaction'):
            p.apply_cas(self.source, data, current, restore_authorized=True, evidence=evidence)


if __name__ == '__main__':
    unittest.main()
