#!/usr/bin/env python3
"""Synthetic exact #786 approval-chain regressions; no runtime or network actions."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_fixtures', ROOT/'tests/hermes-source-path-transition.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
l = f.lifecycle


class FoodBinding(f.SourceBinding):
    def food_review(self):
        source_path, source_review = self.source_reviews()
        previous = copy.deepcopy(self.m)
        previous_generation = self.store/'pre-food-generation'
        shutil.copytree(self.generation, previous_generation, symlinks=False)
        source_review['generation'] = str(previous_generation)
        self.rewrite_source_review(source_path, source_review)
        previous_code = l.identity(previous)
        assets = self.store/'food-validation-assets'; assets.mkdir()
        for p in Path(previous['managedAssets']).iterdir():
            (assets/p.name).write_bytes(p.read_bytes())
        (assets/'production-runtime.py').write_text('SYNTHETIC approved food validation runtime\n')
        mock.patch.object(l, 'FOOD_RUNTIME_SHA', hashlib.sha256((assets/'production-runtime.py').read_bytes()).hexdigest()).start()
        self.m = dict(previous, managedAssets=str(assets))
        (self.store/'installed.json').write_text(json.dumps(self.m)); self.write_candidate(self.m)
        path = self.control/'food-validation-deployments/review-786-SYNTHETIC/qualification.json'
        path.parent.mkdir(parents=True)
        approval = {'authorization':l.FOOD_AUTHORIZATION,
                    'userRequest':'i retried and it crashed again. open a card; fix the bug and deploy it',
                    'approvedAction':'NATIVE_ONLY_FIX_DEPLOY_SAME_OWNER_RESUME'}
        raw = json.dumps(approval).encode(); path.with_name('authorization.json').write_bytes(raw)
        review = {'schemaVersion':1,'kind':'HERMES786_AUTHORIZED_SAME_NATIVE_OWNER_FOOD_VALIDATION_DEPLOYMENT',
                  'namespace':l.NAMESPACE,'card':786,'authorization':l.FOOD_AUTHORIZATION,
                  'scope':'FOOD_VALIDATION_BEFORE_WRITER_RESERVATION','futureAutomaticResume':False,
                  'historicalArmingAndAcceptance':'UNCHANGED',
                  'canonicalStateAndCredentials':'COLD_PRESERVED_NO_REIMPORT_OR_REPLAY',
                  'sourceBundleSha256':self.owner['sourceBundleSha256'],
                  'approvalSha256':hashlib.sha256(raw).hexdigest(),
                  'previousGeneration':str(previous_generation),'generation':str(self.generation),
                  'previousCode':previous_code,'code':l.identity(self.m),
                  'protectedRecords':source_review['protectedRecords']}
        self.rewrite_food_review(path, review)
        return path, review

    def rewrite_food_review(self, path, review):
        path.write_text(json.dumps(review))
        self.owner.update(currentFoodValidationReview=str(path),
                          currentFoodValidationReviewSha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.write_owner()

    def test_food_review_preserves_prior_chain_and_is_read_only(self):
        self.food_review()
        self.assertEqual(self.preflight(),'UNCHANGED_LIVE_IDENTITY')
        self.assertTrue(l.status(self.home)['schedulerAuthorized'])

    def test_food_review_corruption_never_falls_back_to_old_source_approval(self):
        path, review = self.food_review()
        path.write_text(json.dumps(dict(review,futureAutomaticResume=True)))
        with self.assertRaisesRegex(ValueError,'food-validation review digest'):
            self.preflight()

    def test_food_review_cannot_approve_other_code_or_metadata(self):
        path, review = self.food_review()
        (Path(self.m['managedAssets'])/'production-runtime.py').write_text('SYNTHETIC unreviewed runtime\n')
        changed = dict(review,code=l.identity(self.m)); self.rewrite_food_review(path,changed)
        with self.assertRaisesRegex(ValueError,'exact reviewed #786'):
            self.preflight()

    def test_food_review_revalidates_historical_receipts_and_authorization(self):
        path, review = self.food_review()
        path.with_name('authorization.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'explicit food-validation authorization'):
            self.preflight()


if __name__ == '__main__':
    unittest.main()
