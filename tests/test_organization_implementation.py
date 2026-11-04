import copy
import json
from pathlib import Path
import tempfile
import unittest

from integrations.runtimes import organization_implementation as implementation


class ImplementationPilotTests(unittest.TestCase):
    def test_explicit_analysis_only_resources_and_role_profiles(self):
        policy=implementation.resources(Path('integrations/runtimes/organization-implementation-limits.json'))
        self.assertEqual(policy['budget']['sample_proposals'],0)
        self.assertEqual(policy['budget']['attempts'],12)
        self.assertEqual(implementation.role_profile('organizer'),'research-organization/1')
        self.assertEqual(implementation.role_profile('worker'),'research-organization-study/1')
        bad=copy.deepcopy(policy);bad['budget']['sample_proposals']=1
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'limits.json';path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'analysis_only'):implementation.resources(path)

    def test_analysis_only_contract_denies_label_and_fit_at_service_boundary(self):
        import test_study_admission as fixtures
        f=fixtures.StudyAdmissionTests('test_shared_ledger_reservation_and_replay')
        f.setUp();self.addCleanup(f.doCleanups);f.configure()
        document=copy.deepcopy(f.contract);document['provenance']['study_operations']=['analysis']
        f.service.publish_contract('human-secret','p','c',document,expected_revision=1,idempotency_key='only-analysis')
        state=f.service.get_run('human-secret','p','r')
        f.service.command('human-secret','p','r','apply_contract',expected_revision=state['control_revision'],idempotency_key='apply',payload=dict(contract_id='c',revision=2))
        for request in (dict(operation='label',purpose='augmentation',coordinates=[[1,1,1]]),dict(operation='fit',augmentation_trials=[])):
            with self.assertRaisesRegex(ValueError,'study_operation_not_authorized'):
                f.service.submit_study('agent-secret','p','r',request_key=request['operation'],request=request,timeout_seconds=5,
                    hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))
        self.assertEqual(f.service.budgets.balance('p','attempts')['reserved'],0)

    def test_materials_bind_previous_team_source_and_public_dataset(self):
        if not Path('artifacts/p5-organization-delivery-001').is_dir():self.skipTest('requires prior team delivery')
        policy=implementation.resources(Path('integrations/runtimes/organization-implementation-limits.json'))
        config,materials=implementation.preflight(policy)
        self.assertIn('PREVIOUS-PROTOCOL.md',materials)
        self.assertIn('PREVIOUS-PROTOTYPE.py',materials)
        self.assertTrue(config['image_id'].startswith('sha256:'))
        self.assertIn('experiment_operations',implementation.BRIEF)
        self.assertIn('analysis',implementation.BRIEF)
        self.assertNotIn('Code cannot be executed',implementation.BRIEF)


if __name__=='__main__':unittest.main()
