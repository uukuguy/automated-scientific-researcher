from pathlib import Path
import unittest

import test_study_admission as fixtures
from integrations.aar.bridge import ResearchBridge
from integrations.runtimes.pi import PiRuntime


class StudyBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.StudyAdmissionTests('test_shared_ledger_reservation_and_replay')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.configure()
        root=Path(self.fixture.tmp.name)
        self.bridge=ResearchBridge(self.fixture.service,project='p',run='r',researcher_token='agent-secret',
            supervisor_token='human-secret',workspace=root/'workspace',snapshots=root/'snapshots',
            capability_profile='ood-study-development/1')

    def test_profile_inventory_and_admitted_receipt(self):
        pack=PiRuntime(model='gpt-6.1-sol',capabilities_path=Path('integrations/runtimes/ood-study-capabilities.json')).preflight_capabilities()
        self.assertEqual(pack['pack']['id'],'ood-study-development/1')
        result=self.bridge.call('submit_study',dict(request=dict(operation='label',purpose='augmentation',coordinates=[[1,1,1]]),
            timeout_seconds=5,hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1)),'one')
        self.assertEqual(result['receipt']['requested_budget']['sample_proposals'],1)
        self.assertEqual(result['state']['trials'][0]['dispatch_state'],'queued')
        self.assertNotIn('execution_request',result['state']['trials'][0])
        for operation in ('submit_trial','request_evaluation','request_replication'):
            with self.assertRaisesRegex(ValueError,'unsupported_bridge_operation'):
                self.bridge.call(operation,{},'unsupported')


if __name__=='__main__':unittest.main()
