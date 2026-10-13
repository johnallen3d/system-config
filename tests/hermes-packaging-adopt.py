#!/usr/bin/env python3
"""Focused synthetic reviewed-adoption gates. No service, network or credentials."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('adoption', ROOT / 'modules/home-manager/hermes-packaging-adopt.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class ReviewedAdoption(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hermes771-synthetic-adoption-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.old, self.new = {}, {}
        for m, side in ((self.old, 'old'), (self.new, 'new')):
            root = self.root / side
            root.mkdir()
            m.update(package='/SYNTHETIC/same-package', python='/SYNTHETIC/same-python',
                     managedAssets=str(root / 'modules/home-manager/hermes-native'),
                     launcher=str(root / 'launcher'), operator=str(root / 'operator'),
                     transferOperator=str(root / 'transfer'), productionFixture=str(root / 'tests/transfer.py'),
                     writerFixture=str(root / 'tests/writers.py'))
            m['environment'] = {'HERMES_NATIVE_ASSETS': m['managedAssets'],
                                'HERMES_PRODUCTION_OPERATOR': m['operator'], 'TZ': 'America/New_York'}
            for key in ('operator', 'transferOperator', 'productionFixture', 'writerFixture'):
                p = Path(m[key]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('SYNTHETIC identical code')
            Path(m['productionFixture']).with_name('hermes-native-production-state.py').write_text('SYNTHETIC sibling')
            Path(m['launcher']).write_text(m['managedAssets'] + '\n' + m['operator'] + '\n')
        self.old_unit = ('Restart=no\nExecStart=' + self.old['launcher']).encode()
        self.new_unit = ('Restart=no\nExecStart=' + self.new['launcher']).encode()

    def test_exact_pointer_migration_passes_actual_file_comparison(self):
        a.equivalent(self.old, self.new, self.old_unit, self.new_unit)

    def test_environment_semantic_change_refuses(self):
        self.new['environment']['TZ'] = 'UTC'
        with self.assertRaisesRegex(ValueError, 'semantic metadata'):
            a.equivalent(self.old, self.new, self.old_unit, self.new_unit)

    def test_unit_semantic_change_refuses(self):
        with self.assertRaisesRegex(ValueError, 'semantic unit'):
            a.equivalent(self.old, self.new, self.old_unit, self.new_unit.replace(b'Restart=no', b'Restart=always'))

    def test_launcher_code_change_refuses(self):
        p = Path(self.new['launcher']); p.write_text(p.read_text() + 'SYNTHETIC changed command')
        with self.assertRaisesRegex(ValueError, 'semantic launcher'):
            a.equivalent(self.old, self.new, self.old_unit, self.new_unit)

    def test_controller_code_change_refuses(self):
        Path(self.new['operator']).write_text('SYNTHETIC changed controller')
        with self.assertRaisesRegex(ValueError, 'changed executable'):
            a.equivalent(self.old, self.new, self.old_unit, self.new_unit)

    def test_fixed_reviewed_module_preimages_only(self):
        old = {'@metadata': 'OLD', 'production-module.nix': a.l.OLD_MODULE_SHA, 'runtime.py': 'UNCHANGED'}
        new = dict(old, **{'@metadata': 'NEW', 'production-module.nix': a.l.NEW_MODULE_SHA})
        a.module_diff(old, new)
        for mutation in ({'runtime.py': 'CHANGED'}, {'production-module.nix': 'UNREVIEWED'}):
            with self.assertRaisesRegex(ValueError, 'exact reviewed'):
                a.module_diff(old, dict(new, **mutation))

    def test_expired_or_missing_approval_cannot_reach_controller(self):
        with mock.patch.object(a, 'qualify', return_value=(self.root, self.old, self.new, {}, {})), \
                mock.patch.object(a, 'controller') as controller:
            with self.assertRaises((KeyError, ValueError)):
                a.adopt(self.root, self.root, {'authorization': 'SYNTHETIC-NOT-APPROVED'})
            controller.assert_not_called()

    def test_historical_postimage_keeps_one_time_approval_hash(self):
        # Later deployments may change the live module; never widen #771 approval.
        target = ROOT / 'tests/fixtures/hermes771/production-module.nix'
        self.assertEqual(a.digest(target.read_bytes()), a.l.NEW_MODULE_SHA)


if __name__ == '__main__':
    unittest.main()
