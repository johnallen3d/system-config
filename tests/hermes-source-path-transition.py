#!/usr/bin/env python3
"""Synthetic #781 transition/binding regressions. No services, network or live state."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

legacy = load('source_binding_fixtures', ROOT / 'tests/hermes-activation-lifecycle.py')
lifecycle = legacy.lifecycle
transition = load('source_transition', ROOT / 'modules/home-manager/hermes-source-path-transition.py')


class SourceBinding(legacy.Lifecycle):
    def source_reviews(self):
        (self.assets / 'production-runtime.py').write_text('SYNTHETIC reviewed old source runtime\n')
        _, task_review, _, _ = self.current_reviews()
        old_metadata = copy.deepcopy(self.m)
        old_code = lifecycle.identity(old_metadata)
        target = Path(task_review['generation']) / 'home-files/.config/hermes-native/production.json'
        target.unlink()
        target.write_text(json.dumps(old_metadata))
        assets = self.store / 'source-path-assets'
        assets.mkdir()
        for p in self.assets.iterdir():
            (assets / p.name).write_bytes(p.read_bytes())
        (assets / 'production-runtime.py').write_text('SYNTHETIC reviewed new source runtime\n')
        mock.patch.object(lifecycle, 'OLD_SOURCE_RUNTIME_SHA', old_code['production-runtime.py']).start()
        mock.patch.object(lifecycle, 'NEW_SOURCE_RUNTIME_SHA',
                          hashlib.sha256((assets / 'production-runtime.py').read_bytes()).hexdigest()).start()
        self.m = dict(self.m, managedAssets=str(assets))
        (self.store / 'installed.json').write_text(json.dumps(self.m))
        self.write_candidate(self.m)
        path = self.control / 'source-path-deployments/review-781-SYNTHETIC/qualification.json'
        path.parent.mkdir(parents=True)
        approval = {'authorization': lifecycle.SOURCE_AUTHORIZATION,
                    'userApproval': lifecycle.SOURCE_USER_APPROVAL,
                    'approvedAction': 'NATIVE_ONLY_STOP_UPDATE_SAME_OWNER_RESUME',
                    'authorizationBasis': 'DIRECT_USER_INSTRUCTION_IN_RESPONSE_TO_PROPOSAL',
                    'userRequest': 'SYNTHETIC consent, never live authorization'}
        raw = json.dumps(approval).encode()
        path.with_name('authorization.json').write_bytes(raw)
        review = {'schemaVersion': 1,
                  'kind': 'HERMES781_AUTHORIZED_SAME_NATIVE_OWNER_SOURCE_PATH_DEPLOYMENT',
                  'namespace': lifecycle.NAMESPACE, 'card': 781,
                  'authorization': lifecycle.SOURCE_AUTHORIZATION, 'userApproval': lifecycle.SOURCE_USER_APPROVAL,
                  'scope': 'SOURCE_PATHS_ONLY_NO_VAULT_WRITES', 'approvalSha256': hashlib.sha256(raw).hexdigest(),
                  'futureAutomaticResume': False, 'historicalArmingAndAcceptance': 'UNCHANGED',
                  'canonicalStateAndCredentials': 'COLD_PRESERVED_NO_REIMPORT_OR_REPLAY',
                  'sourceBundleSha256': self.owner['sourceBundleSha256'],
                  'previousGeneration': task_review['generation'], 'generation': str(self.generation),
                  'previousCode': old_code, 'code': lifecycle.identity(self.m),
                  'protectedRecords': {'controller/' + n: hashlib.sha256((self.control / n).read_bytes()).hexdigest()
                                       for n in ('arming.json', *lifecycle.ACCEPTANCE_RECEIPTS)}}
        self.rewrite_source_review(path, review)
        return path, review

    def rewrite_source_review(self, path, review):
        path.write_text(json.dumps(review))
        self.owner.update(currentSourcePathReview=str(path),
                          currentSourcePathReviewSha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.write_owner()

    def test_source_binding_is_read_only_and_retains_original_chain(self):
        self.source_reviews()
        self.assertEqual(self.preflight(), 'UNCHANGED_LIVE_IDENTITY')
        self.assertTrue(lifecycle.status(self.home)['schedulerAuthorized'])

    def test_source_binding_never_approves_another_candidate(self):
        self.source_reviews()
        self.write_candidate(dict(self.m, changed=True))
        with self.assertRaisesRegex(ValueError, 'controlled stop|immutable generation binding'):
            self.preflight()

    def test_corrupt_new_review_never_falls_back(self):
        path, review = self.source_reviews()
        path.write_text(json.dumps(dict(review, futureAutomaticResume=True)))
        with self.assertRaisesRegex(ValueError, 'source-path review digest'):
            self.preflight()

    def test_exact_authorization_scope_and_code_required(self):
        path, review = self.source_reviews()
        for key, value in [('card', 780), ('scope', 'ARBITRARY_CODE'), ('userApproval', 'OTHER'),
                           ('futureAutomaticResume', True), ('code', {}),
                           ('historicalArmingAndAcceptance', 'REWRITTEN')]:
            with self.subTest(key=key):
                self.rewrite_source_review(path, dict(review, **{key: value}))
                with self.assertRaisesRegex(ValueError, 'does not approve'):
                    self.preflight()
        self.rewrite_source_review(path, review)

    def test_retained_actual_request_required(self):
        path, _ = self.source_reviews()
        path.with_name('authorization.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'authorization mismatch'):
            self.preflight()

    def test_historical_arming_unchanged(self):
        path, review = self.source_reviews()
        changed = copy.deepcopy(review)
        changed['protectedRecords']['controller/arming.json'] = 'OTHER'
        self.rewrite_source_review(path, changed)
        with self.assertRaisesRegex(ValueError, 'historical receipt changed'):
            self.preflight()

    def test_previous_task_approval_is_revalidated(self):
        self.source_reviews()
        path = Path(self.owner['currentNativeTaskAccessReview'])
        self.rewrite_task_review(path, dict(json.loads(path.read_text()), authorization='OTHER'))
        with self.assertRaisesRegex(ValueError, 'task-access review does not approve'):
            self.preflight()

    def test_runtime_drift_is_refused(self):
        self.source_reviews()
        (Path(self.m['managedAssets']) / 'production-runtime.py').write_text('SYNTHETIC unauthorized drift\n')
        with self.assertRaisesRegex(ValueError, 'does not approve'):
            self.preflight()


class TransitionGates(unittest.TestCase):
    def request(self):
        now = time.time()
        return {'authorization': transition.l.SOURCE_AUTHORIZATION,
                'userApproval': transition.l.SOURCE_USER_APPROVAL,
                'approvedAction': 'NATIVE_ONLY_STOP_UPDATE_SAME_OWNER_RESUME',
                'authorizationBasis': 'DIRECT_USER_INSTRUCTION_IN_RESPONSE_TO_PROPOSAL',
                'userRequest': 'SYNTHETIC consent, never live authorization',
                'requestedAt': now - 1, 'expiresAt': now + 300}

    def test_explicit_fresh_scoped_request_required(self):
        request = self.request()
        transition.authorization(request)
        for key, value in [('authorization', 'OTHER'), ('userApproval', 'OTHER'),
                           ('approvedAction', 'NAS_RESTART'), ('userRequest', ''),
                           ('authorizationBasis', 'ASSUMPTION'), ('expiresAt', time.time() - 1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                transition.authorization(dict(request, **{key: value}))

    def test_only_exact_reviewed_runtime_delta_is_accepted(self):
        old = {'production-runtime.py': transition.l.OLD_SOURCE_RUNTIME_SHA,
               '@metadata': 'OLD', 'unchanged.py': 'UNCHANGED'}
        new = dict(old, **{'production-runtime.py': transition.l.NEW_SOURCE_RUNTIME_SHA, '@metadata': 'NEW'})
        transition.l.source_path_diff(old, new)
        for changed in (dict(new, **{'unchanged.py': 'OTHER'}), dict(new, injected='OTHER'),
                        dict(new, **{'production-runtime.py': 'OTHER'})):
            with self.assertRaises(ValueError):
                transition.l.source_path_diff(old, changed)

    def test_source_observation_must_be_actual_fresh_and_exact(self):
        proof = {'running': False, 'pid': 0, 'restartPolicy': 'no', 'managedRetirement': True,
                 'observedAt': time.time(), 'containerID': 'SYNTHETIC', 'imageID': 'SYNTHETIC',
                 'revision': 'SYNTHETIC', 'retirementSha256': 'SYNTHETIC'}
        arming = {'sourceProof': proof.copy()}
        transition.observation(proof, arming)
        for key, value in [('running', True), ('managedRetirement', False), ('pid', 1),
                           ('restartPolicy', 'always'), ('observedAt', time.time() - 31),
                           ('revision', 'OTHER')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                transition.observation(dict(proof, **{key: value}), arming)

    def test_metadata_launcher_and_unit_semantics_stay_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, new = {}, {}
            for name, metadata in [('old', old), ('new', new)]:
                d = root / name
                d.mkdir()
                for key in transition.a.POINTERS:
                    metadata[key] = str(d / key)
                metadata['environment'] = {'HERMES_NATIVE_ASSETS': metadata['managedAssets'],
                                           'HERMES_PRODUCTION_OPERATOR': metadata['operator'], 'OTHER': 'UNCHANGED'}
                metadata['paths'] = {'state': 'SYNTHETIC_UNCHANGED'}
                for key in ('transferOperator', 'productionFixture', 'writerFixture'):
                    Path(metadata[key]).write_bytes(b'SYNTHETIC identical bytes')
                Path(metadata['productionFixture']).with_name('hermes-native-production-state.py').write_bytes(b'SYNTHETIC identical state')
                Path(metadata['launcher']).write_text('exec ' + metadata['operator'])
            old_unit = ('ExecStart=' + old['launcher']).encode()
            new_unit = ('ExecStart=' + new['launcher']).encode()
            transition.equivalent(old, new, old_unit, new_unit)
            changed = copy.deepcopy(new)
            changed['environment']['OTHER'] = 'OTHER'
            with self.assertRaises(ValueError):
                transition.equivalent(old, changed, old_unit, new_unit)
            with self.assertRaises(ValueError):
                transition.equivalent(old, new, old_unit, new_unit + b'\nRestart=always')
            Path(new['launcher']).write_text('exec arbitrary command')
            with self.assertRaises(ValueError):
                transition.equivalent(old, new, old_unit, new_unit)


if __name__ == '__main__':
    unittest.main()
