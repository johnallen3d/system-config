#!/usr/bin/env python3
"""Synthetic read-only lifecycle checks; NOT Telegram or HM acceptance evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lifecycle', ROOT / 'modules/home-manager/hermes-activation-check.py')
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hermes771-synthetic-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.store = self.root / 'store'
        self.home = self.root / 'home'
        self.generation = self.store / 'generation'
        self.assets = self.store / 'assets'
        self.assets.mkdir(parents=True)
        (self.assets / 'runtime.py').write_text('SYNTHETIC immutable runtime\n')
        self.state = self.home / '.local/state/hermes-native/production/baseline-0.21.2'
        self.control = self.state / 'controller'
        self.control.mkdir(parents=True)
        self.m = {'namespace': lifecycle.NAMESPACE, 'service': lifecycle.SERVICE,
                  'managedAssets': str(self.assets), 'paths': {'state': str(self.state)},
                  'launcher': str(self.store / 'launcher/bin/hermes-production')}
        self.owner = {'schemaVersion': 1, 'namespace': lifecycle.NAMESPACE, 'owner': 'native',
                      'phase': 'NATIVE_LIVE', 'sourceBundleSha256': 'SYNTHETIC',
                      **{k: 'ENABLED' for k in lifecycle.CAPABILITIES}}
        self.write_owner()
        for where in (self.home, self.generation / 'home-files'):
            p = where / '.config/hermes-native/production.json'
            p.parent.mkdir(parents=True)
            p.symlink_to(self.store / ('installed.json' if where == self.home else 'candidate.json'))
            unit = where / '.config/systemd/user' / lifecycle.SERVICE
            unit.parent.mkdir(parents=True)
            unit.symlink_to(self.store / ('installed.service' if where == self.home else 'candidate.service'))
        self.write_candidate(self.m)
        (self.store / 'installed.json').write_text(json.dumps(self.m))
        for name in ('installed.service', 'candidate.service'):
            (self.store / name).write_text('[Service]\nRestart=no\nExecStart=SYNTHETIC\n')
        runtime = self.root / 'run'
        self.dropin = runtime / 'systemd/user/hermes-production.service.d/763-cutover.conf'
        self.dropin.parent.mkdir(parents=True)
        self.dropin.write_text('[Unit]\nRefuseManualStart=false\n')
        self.unit = {'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'running',
                     'MainPID': '123', 'Restart': 'no',
                     'FragmentPath': str(self.home / '.config/systemd/user' / lifecycle.SERVICE),
                     'ExecStart': '{ path=' + self.m['launcher'] + ' ; argv[]=SYNTHETIC ; }',
                     'DropInPaths': str(self.dropin)}
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(lifecycle, 'STORE', self.store).start()
        mock.patch.dict(lifecycle.SYSTEMD_ENV, XDG_RUNTIME_DIR=str(runtime)).start()
        mock.patch.object(lifecycle, 'unit_state', side_effect=lambda: self.unit.copy()).start()
        self.arming = {'namespace': lifecycle.NAMESPACE, 'status': 'ARMED',
                       'sourceBundleSha256': 'SYNTHETIC', 'code': lifecycle.identity(self.m)}
        self.write_arming()
        (self.state / 'cron').mkdir()
        (self.state / 'cron/jobs.json').write_text(json.dumps({'jobs': [{'id': 'SYNTHETIC', 'enabled': True}]}))

    def write_owner(self):
        (self.control / 'ownership.json').write_text(json.dumps(self.owner))

    def write_arming(self):
        (self.control / 'arming.json').write_text(json.dumps(self.arming))

    def write_candidate(self, value):
        (self.store / 'candidate.json').write_text(json.dumps(value))

    def preflight(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        try:
            return lifecycle.preflight(self.home, self.generation)
        finally:
            self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_unchanged_live_generation_passes_without_writes(self):
        self.assertEqual(self.preflight(), 'UNCHANGED_LIVE_IDENTITY')

    def test_byte_equivalent_path_change_does_not_auto_rebind(self):
        candidate = copy.deepcopy(self.m)
        candidate['managedAssets'] = str(self.store / 'different-assets')
        self.write_candidate(candidate)
        with self.assertRaisesRegex(ValueError, 'controlled stop'):
            self.preflight()

    def test_semantic_metadata_change_refuses_before_writes(self):
        candidate = copy.deepcopy(self.m)
        candidate['newSemanticField'] = True
        self.write_candidate(candidate)
        with self.assertRaisesRegex(ValueError, 'controlled stop'):
            self.preflight()

    def test_unit_only_change_refuses(self):
        (self.store / 'candidate.service').write_text('SYNTHETIC altered unit')
        with self.assertRaisesRegex(ValueError, 'installed unit'):
            self.preflight()

    def test_effective_override_refuses(self):
        self.unit['DropInPaths'] += ' /SYNTHETIC/unapproved.conf'
        with self.assertRaisesRegex(ValueError, 'override'):
            self.preflight()

    def test_effective_launcher_refuses(self):
        self.unit['ExecStart'] = '{ path=/SYNTHETIC/unapproved ; }'
        with self.assertRaisesRegex(ValueError, 'effective unit'):
            self.preflight()

    def test_unknown_arming_or_changed_asset_refuses(self):
        (self.assets / 'runtime.py').write_text('SYNTHETIC semantic change')
        with self.assertRaisesRegex(ValueError, 'arming binding'):
            self.preflight()

    def test_explicitly_revoked_and_stopped_install_is_not_start_permission(self):
        self.owner.update(phase='STOPPED_REVIEW_REQUIRED', **{k: 'DISABLED' for k in lifecycle.CAPABILITIES})
        self.write_owner()
        self.unit.update(ActiveState='inactive', SubState='dead', MainPID='0')
        self.write_candidate(dict(self.m, changed=True))
        self.assertEqual(self.preflight(), 'STOPPED_INSTALL_ONLY')
        report = lifecycle.status(self.home)
        self.assertFalse(report['schedulerAuthorized'])
        self.assertTrue(report['jobs'][0]['configuredEnabled'])
        self.assertFalse(report['jobs'][0]['executionAuthorized'])

    def test_revoked_but_process_still_active_refuses(self):
        self.owner.update(phase='STOPPED_REVIEW_REQUIRED', **{k: 'DISABLED' for k in lifecycle.CAPABILITIES})
        self.write_owner()
        with self.assertRaisesRegex(ValueError, 'fully stopped'):
            self.preflight()

    def test_inactive_native_live_and_transitioning_service_refuse(self):
        for state, pid in [('inactive', '0'), ('activating', '123'), ('deactivating', '123')]:
            with self.subTest(state=state):
                self.unit.update(ActiveState=state, MainPID=pid)
                with self.assertRaisesRegex(ValueError, 'disagreement'):
                    self.preflight()

    def test_missing_owner_while_active_refuses(self):
        (self.control / 'ownership.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing owner'):
            self.preflight()

    def test_controller_symlink_refuses(self):
        original = self.control / 'ownership.json'
        renamed = self.control / 'SYNTHETIC-renamed.json'
        original.rename(renamed)
        original.symlink_to(renamed)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.preflight()

    def test_scheduler_status_does_not_claim_readiness_or_delivery(self):
        report = lifecycle.status(self.home)
        self.assertTrue(report['schedulerAuthorized'])
        self.assertTrue(report['jobs'][0]['executionAuthorized'])
        self.assertEqual(report['telegramReadiness'], 'NOT_PROBED')
        self.assertEqual(report['scheduledDelivery'], 'NOT_VERIFIED')
        self.owner['scheduler'] = 'DISABLED'
        self.write_owner()
        self.assertFalse(lifecycle.status(self.home)['jobs'][0]['executionAuthorized'])

    def retained_resumption(self):
        self.arming['code']['@metadata'] = 'SYNTHETIC-original-accepted-metadata'
        self.write_arming()
        accepted = self.store / 'historical-approved-generation'
        archived_metadata = accepted / 'home-files/.config/hermes-native/production.json'
        archived_metadata.parent.mkdir(parents=True)
        archived_metadata.symlink_to(self.store / 'installed.json')
        evidence_path = self.control / 'engineering-runs/authorized-same-owner-resumption-SYNTHETIC/qualification.json'
        evidence_path.parent.mkdir(parents=True)
        evidence = {'kind': 'HERMES763_AUTHORIZED_SAME_ACCEPTED_OWNER_METADATA_ONLY_RESUMPTION',
                    'namespace': lifecycle.NAMESPACE, 'authorization': 'JOHN_NATIVE_REPAIR_AND_RESTART_ONLY',
                    'futureAutomaticResume': False, 'originalArmingAndAcceptance': 'UNCHANGED',
                    'allAssetAndFixtureBytes': 'IDENTICAL', 'acceptedCode': self.arming['code'],
                    'currentCode': lifecycle.identity(self.m), 'currentGeneration': str(accepted)}
        evidence_path.write_text(json.dumps(evidence))
        self.owner.update(resumptionEvidence=str(evidence_path),
                          resumptionEvidenceSha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest())
        self.write_owner()
        return evidence_path, evidence

    def test_exact_retained_resumption_is_read_only_not_future_resume_permission(self):
        self.retained_resumption()
        self.assertEqual(self.preflight(), 'UNCHANGED_LIVE_IDENTITY')
        self.write_candidate(dict(self.m, changed=True))
        with self.assertRaisesRegex(ValueError, 'controlled stop'):
            self.preflight()

    def test_tampered_retained_evidence_refuses(self):
        path, evidence = self.retained_resumption()
        path.write_text(json.dumps(dict(evidence, futureAutomaticResume=True)))
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            self.preflight()

    def test_retained_evidence_for_another_generation_refuses(self):
        path, evidence = self.retained_resumption()
        evidence['currentGeneration'] = '/SYNTHETIC/other-generation'
        path.write_text(json.dumps(evidence))
        self.owner['resumptionEvidenceSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_owner()
        with self.assertRaisesRegex(ValueError, 'does not approve'):
            self.preflight()

    def test_retained_evidence_cannot_bypass_actual_asset_change(self):
        self.retained_resumption()
        (self.assets / 'runtime.py').write_text('SYNTHETIC changed after qualification')
        with self.assertRaisesRegex(ValueError, 'does not approve'):
            self.preflight()

    def packaging_receipt(self):
        # This receipt approves the historical #771 postimage, not later deployments.
        source = ROOT / 'tests/fixtures/hermes771/production-module.nix'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), lifecycle.NEW_MODULE_SHA)
        (self.assets / 'production-module.nix').write_bytes(source.read_bytes())
        self.arming['code']['@metadata'] = 'SYNTHETIC-original-accepted-metadata'
        self.arming['code']['production-module.nix'] = lifecycle.OLD_MODULE_SHA
        self.write_arming()
        approved = self.store / 'reviewed-packaging-generation'
        m = approved / 'home-files/.config/hermes-native/production.json'
        m.parent.mkdir(parents=True)
        m.symlink_to(self.store / 'installed.json')
        path = self.control / 'engineering-runs/packaging-adoption-SYNTHETIC/qualification.json'
        path.parent.mkdir(parents=True)
        evidence = {'kind': 'HERMES771_REVIEWED_ONE_TIME_PACKAGING_ADOPTION',
                    'authorization': 'JOHN_APPROVED_771_CONTROLLED_PACKAGING_ADOPTION',
                    'namespace': lifecycle.NAMESPACE, 'sourceBundleSha256': 'SYNTHETIC',
                    'futureAutomaticResume': False, 'originalAcceptedCode': self.arming['code'],
                    'currentCode': lifecycle.identity(self.m), 'currentGeneration': str(approved)}
        path.write_text(json.dumps(evidence))
        self.owner.update(packagingAdoptionEvidence=str(path),
                          packagingAdoptionEvidenceSha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.write_owner()
        return path, evidence

    def test_exact_reviewed_packaging_receipt_preserves_original_arming(self):
        self.packaging_receipt()
        self.assertEqual(self.preflight(), 'UNCHANGED_LIVE_IDENTITY')
        self.assertEqual(self.arming['code']['production-module.nix'], lifecycle.OLD_MODULE_SHA)
        self.write_candidate(dict(self.m, changed=True))
        with self.assertRaisesRegex(ValueError, 'controlled stop'):
            self.preflight()

    def test_packaging_receipt_tampering_refuses(self):
        path, evidence = self.packaging_receipt()
        path.write_text(json.dumps(dict(evidence, futureAutomaticResume=True)))
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            self.preflight()

    def test_packaging_receipt_is_not_general_code_change_approval(self):
        path, evidence = self.packaging_receipt()
        (self.assets / 'runtime.py').write_text('SYNTHETIC other changed code')
        evidence['currentCode'] = lifecycle.identity(self.m)
        path.write_text(json.dumps(evidence))
        self.owner['packagingAdoptionEvidenceSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_owner()
        with self.assertRaisesRegex(ValueError, 'does not approve'):
            self.preflight()

    def test_packaging_receipt_does_not_authorize_automatic_resume(self):
        path, evidence = self.packaging_receipt()
        evidence['futureAutomaticResume'] = True
        path.write_text(json.dumps(evidence))
        self.owner['packagingAdoptionEvidenceSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_owner()
        with self.assertRaisesRegex(ValueError, 'does not approve'):
            self.preflight()

    def current_reviews(self):
        old_assets = self.store / 'calendar-assets'
        old_assets.mkdir()
        (old_assets / 'runtime.py').write_text('SYNTHETIC earlier reviewed code\n')
        old_metadata = dict(self.m, managedAssets=str(old_assets))
        self.arming['code'] = lifecycle.identity(old_metadata)
        calendar_generation = self.store / 'calendar-generation'
        target = calendar_generation / 'home-files/.config/hermes-native/production.json'
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(old_metadata))
        calendar_path = self.control / 'calendar-deployments/review-SYNTHETIC/review.json'
        calendar_path.parent.mkdir(parents=True)
        preserved = {}
        for name in lifecycle.ACCEPTANCE_RECEIPTS:
            path = self.control / name
            path.write_text(json.dumps({'kind': 'SYNTHETIC ORIGINAL ACCEPTANCE', 'name': name}))
            preserved[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        calendar = {'kind': 'HERMES763_REVIEWED_CURRENT_NATIVE_CALENDAR_CODE_CONTINUATION',
                    'namespace': lifecycle.NAMESPACE,
                    'authorization': 'JOHN_CALENDAR_ONLY_CONTROLLED_DEPLOYMENT_2026_10_11',
                    'sourceBundleSha256': self.owner['sourceBundleSha256'],
                    'code': self.arming['code'], 'initialAcceptance': 'PRESERVED_NOT_RERUN',
                    'preservedAcceptance': preserved, 'generation': str(calendar_generation)}
        calendar_path.write_text(json.dumps(calendar))
        self.arming.update(currentNativeCalendarReview=str(calendar_path),
                           currentNativeCalendarReviewSha256=hashlib.sha256(calendar_path.read_bytes()).hexdigest())
        self.write_arming()
        generation = self.store / 'task-access-generation'
        target = generation / 'home-files/.config/hermes-native/production.json'
        target.parent.mkdir(parents=True)
        target.symlink_to(self.store / 'installed.json')
        path = self.control / 'task-access-deployments/review-774-SYNTHETIC/qualification.json'
        path.parent.mkdir(parents=True)
        review = {'schemaVersion': 1,
                  'kind': 'HERMES774_AUTHORIZED_SAME_NATIVE_OWNER_TASK_ACCESS_DEPLOYMENT',
                  'namespace': lifecycle.NAMESPACE, 'card': 774,
                  'authorization': 'JOHN_GO_AHEAD_AND_DEPLOY', 'futureAutomaticResume': False,
                  'historicalArmingAndAcceptance': 'UNCHANGED',
                  'canonicalStateAndCredentials': 'COLD_PRESERVED_NO_REIMPORT_OR_REPLAY',
                  'code': lifecycle.identity(self.m), 'generation': str(generation)}
        path.write_text(json.dumps(review))
        self.owner.update(currentNativeCalendarReview=str(calendar_path),
                          currentNativeTaskAccessReview=str(path),
                          currentNativeTaskAccessReviewSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                          packagingAdoptionEvidence='/SYNTHETIC/historical-packaging-not-current',
                          resumptionEvidence='/SYNTHETIC/historical-resumption-not-current')
        self.write_owner()
        return path, review, calendar_path, calendar

    def rewrite_task_review(self, path, review):
        path.write_text(json.dumps(review))
        self.owner['currentNativeTaskAccessReviewSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_owner()

    def rewrite_calendar_review(self, path, review):
        path.write_text(json.dumps(review))
        self.arming['currentNativeCalendarReviewSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_arming()

    def test_current_task_review_precedes_historical_receipts_without_writes(self):
        self.current_reviews()
        self.assertEqual(self.preflight(), 'UNCHANGED_LIVE_IDENTITY')
        self.assertTrue(lifecycle.status(self.home)['schedulerAuthorized'])

    def test_current_review_does_not_approve_new_candidate(self):
        self.current_reviews()
        self.write_candidate(dict(self.m, changed=True))
        with self.assertRaisesRegex(ValueError, 'controlled stop'):
            self.preflight()

    def test_corrupt_current_review_does_not_fall_back_to_history(self):
        path, review, _, _ = self.current_reviews()
        path.write_text(json.dumps(dict(review, futureAutomaticResume=True)))
        with self.assertRaisesRegex(ValueError, 'task-access review digest'):
            self.preflight()

    def test_current_review_missing_owner_digest_refuses(self):
        self.current_reviews()
        self.owner.pop('currentNativeTaskAccessReviewSha256')
        self.write_owner()
        with self.assertRaisesRegex(ValueError, 'task-access review digest'):
            self.preflight()

    def test_current_review_requires_exact_authorization_and_identity(self):
        path, review, _, _ = self.current_reviews()
        for key, value in [('schemaVersion', 2), ('kind', 'OTHER'), ('namespace', 'OTHER'),
                           ('card', 780), ('authorization', 'OTHER'), ('futureAutomaticResume', True),
                           ('historicalArmingAndAcceptance', 'CHANGED'),
                           ('canonicalStateAndCredentials', 'RESTORED'), ('code', {})]:
            with self.subTest(key=key):
                self.rewrite_task_review(path, dict(review, **{key: value}))
                with self.assertRaisesRegex(ValueError, 'does not approve'):
                    self.preflight()
        self.rewrite_task_review(path, review)

    def test_current_review_requires_exact_immutable_generation(self):
        path, review, _, _ = self.current_reviews()
        other = self.store / 'different-task-generation'
        target = other / 'home-files/.config/hermes-native/production.json'
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(dict(self.m, changed=True)))
        self.rewrite_task_review(path, dict(review, generation=str(other)))
        with self.assertRaisesRegex(ValueError, 'does not approve'):
            self.preflight()

    def test_current_review_never_exempts_changed_asset_bytes(self):
        self.current_reviews()
        (self.assets / 'runtime.py').write_text('SYNTHETIC unreviewed replacement')
        with self.assertRaisesRegex(ValueError, 'does not approve'):
            self.preflight()

    def test_current_review_requires_calendar_digest(self):
        _, _, path, calendar = self.current_reviews()
        path.write_text(json.dumps(dict(calendar, sourceBundleSha256='OTHER')))
        with self.assertRaisesRegex(ValueError, 'calendar review digest'):
            self.preflight()

    def test_current_review_requires_exact_calendar_arming_binding(self):
        _, _, path, calendar = self.current_reviews()
        for key, value in [('kind', 'OTHER'), ('namespace', 'OTHER'), ('authorization', 'OTHER'),
                           ('sourceBundleSha256', 'OTHER'), ('code', {}),
                           ('initialAcceptance', 'RERUN')]:
            with self.subTest(key=key):
                self.rewrite_calendar_review(path, dict(calendar, **{key: value}))
                with self.assertRaisesRegex(ValueError, 'does not bind'):
                    self.preflight()
        self.rewrite_calendar_review(path, calendar)

    def test_current_review_requires_same_calendar_reference_on_owner(self):
        self.current_reviews()
        self.owner['currentNativeCalendarReview'] = '/SYNTHETIC/unrelated'
        self.write_owner()
        with self.assertRaisesRegex(ValueError, 'fixed retained calendar'):
            self.preflight()

    def test_current_review_requires_fixed_task_review_path(self):
        path, _, _, _ = self.current_reviews()
        self.owner['currentNativeTaskAccessReview'] = str(path.parent / 'unapproved.json')
        self.write_owner()
        with self.assertRaisesRegex(ValueError, 'fixed retained task-access'):
            self.preflight()

    def test_current_review_rejects_changed_archived_calendar_metadata(self):
        _, _, _, calendar = self.current_reviews()
        target = Path(calendar['generation']) / 'home-files/.config/hermes-native/production.json'
        target.write_text(json.dumps(dict(json.loads(target.read_text()), changed=True)))
        with self.assertRaisesRegex(ValueError, 'does not bind'):
            self.preflight()

    def test_current_review_requires_preserved_original_acceptance(self):
        self.current_reviews()
        (self.control / 'acceptance-probe.json').write_text('SYNTHETIC replaced acceptance')
        with self.assertRaisesRegex(ValueError, 'original acceptance receipt changed'):
            self.preflight()

    def test_current_review_symlink_refuses(self):
        path, _, _, _ = self.current_reviews()
        renamed = path.with_name('actual.json')
        path.rename(renamed)
        path.symlink_to(renamed)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.preflight()

    def test_current_reviews_require_objects(self):
        path, review, calendar_path, calendar = self.current_reviews()
        self.rewrite_calendar_review(calendar_path, [])
        with self.assertRaisesRegex(ValueError, 'calendar review object'):
            self.preflight()
        self.rewrite_calendar_review(calendar_path, calendar)
        self.rewrite_task_review(path, [])
        with self.assertRaisesRegex(ValueError, 'task-access review object'):
            self.preflight()
        self.rewrite_task_review(path, review)

    def test_current_review_is_not_initial_arming_permission(self):
        self.current_reviews()
        self.owner['phase'] = 'NATIVE_ARMED'
        self.write_owner()
        with self.assertRaisesRegex(ValueError, 'fixed retained calendar'):
            self.preflight()

    def test_identity_preserves_exact_approval_encoding(self):
        encoded = (json.dumps(self.m, sort_keys=True, indent=2) + '\n').encode()
        self.assertEqual(lifecycle.identity(self.m)['@metadata'], hashlib.sha256(encoded).hexdigest())

    def test_nix_wiring_keeps_fixture_layout_and_pre_write_gate(self):
        module = (ROOT / 'modules/home-manager/omarchy-hermes.nix').read_text()
        production = (ROOT / 'modules/home-manager/hermes-native/production-module.nix').read_text()
        self.assertIn('lib.fileset.toSource', module)
        self.assertIn('assets = "${hermesSource}/modules/home-manager/hermes-native"', module)
        self.assertIn('entryBefore ["writeBoundary"]', module)
        for fixture in ('state', 'transfer', 'writers'):
            self.assertIn(f'../../tests/hermes-native-production-{fixture}.py', module)
        self.assertIn('${hermesSource}/tests/hermes-native-production-transfer.py', production)
        self.assertIn('${hermesSource}/tests/hermes-native-production-writers.py', production)


if __name__ == '__main__':
    unittest.main()
