import unittest
from integrations.runtimes.capability_inventory import PROFILE_TOOLS

class IntakeTests(unittest.TestCase):
    def test_intake_cannot_claim_experiment_or_validation(self):
        self.assertIn('ood-project-intake/1', PROFILE_TOOLS)
        operations=PROFILE_TOOLS['ood-project-intake/1']
        self.assertTrue({'asr.state','asr.publish_hypothesis','asr.snapshot'} <= operations)
        self.assertFalse({'asr.submit_trial','asr.submit_candidate','asr.publish_finding','asr.request_evaluation'} & operations)


from tests import test_control_service as fixtures

class IntakeContractTests(unittest.TestCase):
    setUp=fixtures.ControlTests.setUp
    start=fixtures.ControlTests.start
    submit=fixtures.ControlTests.submit
    def test_zero_compute_intake_contract_cannot_admit_numerical_work(self):
        self.contract['budget'].update(attempts=0,execution_ms=0)
        self.contract['provenance']['capability_profile']='ood-project-intake/1'
        self.start()
        with self.assertRaises(ValueError):self.submit()
        self.assertEqual(self.service.get_run('human-secret','p','r')['trials'],[])

if __name__=='__main__':unittest.main()
