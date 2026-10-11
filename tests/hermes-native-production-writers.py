#!/usr/bin/env python3
"""Synthetic reservation tests only; no actual manual freeze or writer authority."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'modules/home-manager/hermes-native/production-writers.py'
spec = importlib.util.spec_from_file_location('production_writers', MODULE)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


class Writers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hermes763-reservation-fixture-')
        self.root = Path(self.tmp.name).resolve()
        self.coordinator = self.root / 'hermes-native/production/baseline-0.21.2'
        self.coordinator.mkdir(mode=0o700, parents=True)
        self.vault = self.root / 'vault'; self.vault.mkdir(mode=0o700)
        (self.vault / 'canary.md').write_bytes(b'SYNTHETIC CHECKPOINT\n')
        (self.vault / 'canary.md').chmod(0o600)
        self.files = ('canary.md',)
        self.now = 100.0
        self.scope = {'schemaVersion': 1, 'namespace': w.NAMESPACE, 'coordinator': 'omarchy',
            'nonce': 'SYNTHETIC-nonce-00000000000001', 'confirmedAt': 99, 'expiresAt': 200,
            'manualConfirmationSource': 'JOHN_EXECUTION_WINDOW',
            'excludedWriters': sorted(w.WRITERS), 'files': list(self.files)}
        self.change_observation = lambda x: x

    def tearDown(self):
        self.tmp.cleanup()

    def observation(self, files):
        result = {}
        for i, p in enumerate(w.PEERS):
            result[p] = {'folderID': 'notes', 'type': 'sendreceive', 'paused': False, 'state': 'idle',
                'connectedPeers': sorted(w.PEERS[j] for j in range(3) if abs(i-j)==1),
                'completion': 100, 'needItems': 0, 'needBytes': 0, 'errors': 0, 'pullErrors': 0,
                'conflicts': [], 'observedAt': self.now}
        return self.change_observation(result)

    def reserve(self, **kw):
        return w.reserve(self.coordinator, self.vault, self.files, scope=kw.get('scope', self.scope),
                         observer=self.observation, clock=lambda: self.now)

    def test_shared_inode_survives_normal_release_and_readback(self):
        with self.reserve() as r:
            r.check()
            original = w.state.signature(self.vault / 'canary.md')
            w.state.atomic_durable(self.vault / 'canary.md', b'SYNTHETIC NEW POSTIMAGE\n', original)
            r.complete(w.manifest(self.vault, self.files))
        lock = self.coordinator / 'writer.lock'
        inode = (lock.stat().st_dev, lock.stat().st_ino)
        self.scope['nonce'] = 'SYNTHETIC-nonce-00000000000002'
        with self.reserve() as r:
            r.complete(w.manifest(self.vault, self.files))
        self.assertEqual((lock.stat().st_dev, lock.stat().st_ino), inode)
        self.assertEqual(json.loads((self.coordinator / 'writer-reservation.json').read_bytes())['status'], 'COMPLETE')
        self.assertEqual(len(list((self.coordinator / 'reservation-evidence').glob('*.json'))), 2)

    def test_another_process_cannot_take_shared_lock(self):
        code = '''import importlib.util,sys,pathlib
spec=importlib.util.spec_from_file_location('writers',sys.argv[1]); w=importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
try:
    with w.held_lock(pathlib.Path(sys.argv[2])): pass
except ValueError:
    raise SystemExit(23)
raise SystemExit(0)
'''
        with self.reserve() as r:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(MODULE),
                                     str(self.coordinator / 'writer.lock')], cwd='/', capture_output=True)
            self.assertEqual(result.returncode, 23)
            r.complete(w.manifest(self.vault, self.files))

    @unittest.skipUnless(sys.platform == 'linux', 'Linux mount-namespace fixture')
    def test_private_tmp_namespace_uses_same_bound_lock_inode(self):
        code = '''import importlib.util,sys,pathlib
spec=importlib.util.spec_from_file_location('writers','/fixture-code/modules/home-manager/hermes-native/production-writers.py')
w=importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
p=pathlib.Path('/coord/writer.lock'); s=p.stat()
assert (s.st_dev,s.st_ino)==(int(sys.argv[1]),int(sys.argv[2]))
try:
    with w.held_lock(p): pass
except ValueError:
    raise SystemExit(23)
raise SystemExit(0)
'''
        with self.reserve() as r:
            s = (self.coordinator / 'writer.lock').stat()
            result = subprocess.run(['/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--new-session',
                '--ro-bind', '/nix/store', '/nix/store', '--proc', '/proc', '--dev', '/dev',
                '--tmpfs', '/tmp', '--tmpfs', '/home', '--dir', '/etc',
                '--ro-bind', str(MODULE.parents[3]), '/fixture-code',
                '--bind', str(self.coordinator), '/coord', '--chdir', '/tmp',
                sys.executable, '-I', '-B', '-c', code, str(s.st_dev), str(s.st_ino)],
                env={'PATH': '/usr/bin:/bin'}, cwd='/', capture_output=True)
            self.assertEqual(result.returncode, 23, 'same-inode namespace reservation must refuse')
            r.complete(w.manifest(self.vault, self.files))

    def test_file_lock_cannot_be_bypassed_by_global_lock_release(self):
        import hashlib
        locks = self.coordinator / 'file-locks'; locks.mkdir(mode=0o700)
        key = hashlib.sha256(self.files[0].encode()).hexdigest()+'.lock'
        with w.held_lock(locks / key):
            with self.assertRaisesRegex(ValueError, 'already held'):
                with self.reserve(): pass

    def test_expiry_stop_retains_sticky_evidence(self):
        with self.assertRaisesRegex(ValueError, 'expired'):
            with self.reserve() as r:
                self.now = 201
                r.check()
        record = json.loads((self.coordinator / 'writer-reservation.json').read_bytes())
        self.assertEqual(record['status'], 'STOPPED_REVIEW_REQUIRED')
        self.now = 100; self.scope['nonce'] = 'SYNTHETIC-nonce-00000000000002'
        with self.assertRaisesRegex(ValueError, 'requires review'):
            with self.reserve(): pass

    def test_preimage_cas_and_postimage_mismatch_stop(self):
        with self.assertRaisesRegex(ValueError, 'CAS drift'):
            with self.reserve() as r:
                (self.vault / 'canary.md').write_bytes(b'SYNTHETIC OUTSIDE WRITER\n')
                r.check()

    def test_unknown_writer_missing_peer_stale_status_and_conflict_refused(self):
        bad = copy.deepcopy(self.scope); bad['excludedWriters'].remove('mobile-icloud')
        with self.assertRaisesRegex(ValueError, 'manual writer'):
            with self.reserve(scope=bad): pass
        for kind in ('missing', 'stale', 'conflict', 'extra-direct-peer', 'incomplete', 'pull-error'):
            def mutate(rows, kind=kind):
                if kind == 'missing': rows.pop('nas')
                elif kind == 'stale': rows['nas']['observedAt'] = 94
                elif kind == 'conflict': rows['mac']['conflicts'] = ['SYNTHETIC-CONFLICT']
                elif kind == 'extra-direct-peer': rows['omarchy']['connectedPeers'] = ['mac', 'nas']
                elif kind == 'incomplete': rows['nas']['completion'] = 99
                elif kind == 'pull-error': rows['nas']['pullErrors'] = 1
                return rows
            self.change_observation = mutate
            with self.assertRaises(ValueError):
                with self.reserve(): pass
        self.assertFalse((self.coordinator / 'writer-reservation.json').exists())

    def test_scope_path_namespace_manual_receipt_and_duration_refused(self):
        for key, value in [('namespace', 'staging/baseline-0.21.2'),
                           ('manualConfirmationSource', 'EARLIER_GENERAL_PERMISSION'),
                           ('expiresAt', 99999), ('files', ['../outside'])]:
            bad = copy.deepcopy(self.scope); bad[key] = value
            with self.assertRaises(ValueError):
                with self.reserve(scope=bad): pass
        linked = self.root / 'linked.md'; linked.write_bytes(b'SYNTHETIC LINK\n')
        (self.vault / 'canary.md').unlink(); (self.vault / 'canary.md').symlink_to(linked)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            with self.reserve(): pass

    def test_nonce_replay_refused_even_after_another_reservation(self):
        first = self.scope['nonce']
        with self.reserve() as r: r.complete(w.manifest(self.vault, self.files))
        self.scope['nonce'] = 'SYNTHETIC-nonce-00000000000002'
        with self.reserve() as r: r.complete(w.manifest(self.vault, self.files))
        self.scope['nonce'] = first
        with self.assertRaisesRegex(ValueError, 'nonce replay'):
            with self.reserve(): pass

    def test_lock_replacement_after_acknowledgment_cannot_mark_complete(self):
        with self.assertRaisesRegex(ValueError, 'shared lock replaced'):
            with self.reserve() as r:
                r.complete(w.manifest(self.vault, self.files))
                lock = self.coordinator / 'writer.lock'
                lock.rename(self.coordinator / 'SYNTHETIC-retained-old-inode.lock')
                lock.write_bytes(b''); lock.chmod(0o600)
        self.assertEqual(json.loads((self.coordinator / 'writer-reservation.json').read_bytes())['status'],
                         'STOPPED_REVIEW_REQUIRED')
        self.scope['nonce'] = 'SYNTHETIC-nonce-00000000000002'
        with self.assertRaisesRegex(ValueError, 'requires review'):
            with self.reserve(): pass

    def normal_owner(self):
        path=self.coordinator/'controller/ownership.json'; path.parent.mkdir(mode=0o700)
        path.write_text(json.dumps({'namespace':w.NAMESPACE,'owner':'native','phase':'NATIVE_LIVE',
            'vaultWrites':'ENABLED','normalWriterPolicy':'NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION'}))
        path.chmod(0o600)
        return path

    def local_observation(self,files):
        return {'folder':'notes','type':'sendreceive','state':'idle','observedAt':self.now,
                'localConvergence':True,'directPeerConvergence':True,'directPeerCount':1,
                'conflicts':0,'temporary':0,'special':0}

    def test_scheduled_brief_normal_policy_requires_no_fresh_human_lease(self):
        self.normal_owner()
        # Synthetic successive 05:00 runs a day apart. There is no forged manual
        # confirmation and no permanent ten-minute lease in the normal record.
        for at in [100.0,86500.0]:
            self.now=at
            with w.normal_reserve(self.coordinator,self.vault,self.files,
                                  observer=self.local_observation,clock=lambda:self.now) as reservation:
                reservation.complete(w.manifest(self.vault,self.files))
            record=json.loads((self.coordinator/'writer-reservation.json').read_bytes())
            self.assertEqual(record['policy'],'NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION')
            self.assertEqual(record['convergenceEvidence'],'LOCAL_AND_DIRECT_METADATA')
            self.assertNotIn('expiresAt',record); self.assertNotIn('confirmedAt',record)
            self.assertEqual((Path(record['preimages'])/'canary.md').read_bytes(),b'SYNTHETIC CHECKPOINT\n')
        # The actual maintenance gate still refuses this expired human window.
        with self.assertRaisesRegex(ValueError,'expired'):
            with self.reserve(): pass

    def test_normal_conflicts_and_revoked_ownership_still_fail_closed(self):
        owner=self.normal_owner()
        def conflict(files): return dict(self.local_observation(files),conflicts=1)
        with self.assertRaisesRegex(ValueError,'conflict stop'):
            with w.normal_reserve(self.coordinator,self.vault,self.files,observer=conflict,clock=lambda:self.now): pass
        data=json.loads(owner.read_bytes()); data['phase']='STOPPED_REVIEW_REQUIRED'; owner.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'live normal-writer ownership'):
            with w.normal_reserve(self.coordinator,self.vault,self.files,observer=self.local_observation,clock=lambda:self.now): pass
        self.assertFalse((self.coordinator/'writer-reservation.json').exists())

    def test_only_exact_archived_noeffect_reservation_can_continue_with_fresh_timed_scope(self):
        with self.assertRaisesRegex(ValueError,'acknowledgment'):
            with self.reserve(): pass
        journal=self.coordinator/'writer-reservation.json'; before=journal.read_bytes()
        history=self.coordinator/'reservation-evidence'
        old_record=json.loads(before)
        old_evidence=history/(w.state.stage.digest(old_record['nonce'].encode())+'.json')
        archive=self.coordinator/'controller/fixture-noeffect-archive'; archive.mkdir(parents=True,mode=0o700)
        w.state.stage.atomic(archive/'writer-reservation.json',before)
        review=self.coordinator/'controller/acceptance-noeffect-continuation.json'
        proof={'kind':'HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION','namespace':w.NAMESPACE,
               'reservationSha256':'0'*64,'archive':str(archive)}
        w.state.stage.atomic(review,w.state.stage.encoded(proof))
        self.scope['nonce']='SYNTHETIC-new-noeffect-0000000002'
        with self.assertRaisesRegex(ValueError,'only exact reviewed'):
            with self.reserve(): pass
        self.assertEqual(journal.read_bytes(),before)
        proof['reservationSha256']=w.state.stage.digest(before)
        w.state.stage.atomic(review,w.state.stage.encoded(proof))
        expired=copy.deepcopy(self.scope); expired['expiresAt']=99
        with self.assertRaisesRegex(ValueError,'expired'):
            with self.reserve(scope=expired): pass
        with self.reserve() as reservation: reservation.complete(w.manifest(self.vault,self.files))
        self.assertEqual(old_evidence.read_bytes(),before)
        self.assertEqual((archive/'writer-reservation.json').read_bytes(),before)
        self.assertEqual(json.loads(journal.read_bytes())['status'],'COMPLETE')

    def test_missing_all_peer_postimage_acknowledgment_stops(self):
        with self.assertRaisesRegex(ValueError, 'acknowledgment'):
            with self.reserve(): pass
        self.assertEqual(json.loads((self.coordinator / 'writer-reservation.json').read_bytes())['status'],
                         'STOPPED_REVIEW_REQUIRED')


if __name__ == '__main__':
    unittest.main()
