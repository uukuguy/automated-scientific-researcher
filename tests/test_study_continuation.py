import copy
import json
from pathlib import Path
import unittest

from integrations.runtimes.ood_study import successor_document


class StudyContinuationTests(unittest.TestCase):
    def test_successor_retains_prior_identity_and_never_resets_usage(self):
        policy=json.loads(Path('integrations/runtimes/ood-study-limits.json').read_text())
        previous=dict(contract=dict(sha256='old',document=dict(execution_policy={},runtime_policy={'billing_mode':'subscription'})),
            budget=dict(research_walltime_ms=dict(spent=216397,reserved=0)))
        original=copy.deepcopy(previous)
        result=successor_document(previous,{},policy,{'problem':'new-problem'},'pack')
        self.assertEqual(previous,original)
        self.assertEqual(result['budget']['research_walltime_ms'],1500000)
        self.assertEqual(result['runtime_policy'],{'billing_mode':'subscription'})
        self.assertEqual(result['provenance']['prior_contract_sha256'],'old')
        policy['budget_totals']['research_walltime_ms']=216396
        with self.assertRaisesRegex(ValueError,'committed usage'):
            successor_document(previous,{},policy,{},'pack')

    def test_api_fallback_or_invalid_limits_cannot_be_admitted(self):
        policy=json.loads(Path('integrations/runtimes/ood-study-limits.json').read_text())
        previous=dict(contract=dict(document={},sha256='old'),budget={})
        policy['paid_api_fallback']=True
        with self.assertRaisesRegex(ValueError,'subscription-only'):
            successor_document(previous,{},policy,{},'pack')
        policy['paid_api_fallback']=False;policy['session_limits']['walltime_seconds']=float('inf')
        with self.assertRaises(ValueError):successor_document(previous,{},policy,{},'pack')


if __name__=='__main__':unittest.main()
