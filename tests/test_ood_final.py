import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_study_admission as fixtures
from asr_service.ood_final import evaluation_reference


class FinalAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.StudyAdmissionTests('test_shared_ledger_reservation_and_replay')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.fixture.configure()
        self.service=self.fixture.service
        self.protocol=dict(primary_model='fitted',model_trials=['fitted'],proposal_sha256='c'*64)
        self.arguments=dict(request_key='final',protocol=self.protocol,hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))

    def authorize(self):
        doc=copy.deepcopy(self.fixture.contract)
        config=dict(client_root='/fixture-only',preparation_report_sha256='d'*64,image_id='sha256:'+'e'*64,
                    metric_source_sha256='f'*64,worker_source_sha256='a'*64)
        doc['provenance'].update(capability_profile='ood-study-confirmation/1',final=config)
        doc['evaluation_ref']=self.service.references.register('p','evaluation',evaluation_reference(config))
        self.service.publish_contract('human-secret','p','c',doc,expected_revision=1,idempotency_key='final-policy')
        self.service.command('human-secret','p','r','apply_contract',expected_revision=1,idempotency_key='apply-final',payload=dict(contract_id='c',revision=2))

    def test_researcher_or_development_contract_cannot_release_test(self):
        with self.assertRaisesRegex(ValueError,'forbidden'):
            self.service.submit_ood_final('agent-secret','p','r',**self.arguments)
        with self.assertRaisesRegex(ValueError,'final_not_authorized'):
            self.service.submit_ood_final('human-secret','p','r',**self.arguments)

    def test_first_admission_freezes_protocol_and_prevents_duplicate_release(self):
        self.authorize()
        # Interface test only; real frozen raw-label scoring is tested separately.
        source=dict(variables={'operation':'fit'},events=[{'type':'result','result':{'model':{'schema':'fixture'}}}])
        with patch('asr_service.ood_final.materials',return_value={'case':{},'private_id':[],'private_ood':[]}),patch(
            'asr_service.ood_final.completed_material',return_value=(source,{'trial_id':'fitted'})):
            first=self.service.submit_ood_final('human-secret','p','r',**self.arguments)
            self.assertEqual(first,self.service.submit_ood_final('human-secret','p','r',**self.arguments))
            with self.assertRaisesRegex(ValueError,'final_already_admitted_or_released'):
                self.service.submit_ood_final('human-secret','p','r',**dict(self.arguments,request_key='duplicate'))
            changed=dict(self.protocol,proposal_sha256='b'*64)
            with self.assertRaisesRegex(ValueError,'final_protocol_frozen'):
                self.service.submit_ood_final('human-secret','p','r',**dict(self.arguments,request_key='changed',protocol=changed))
        # Even reapplying the old development contract cannot reopen this run.
        self.service.command('human-secret','p','r','apply_contract',expected_revision=2,idempotency_key='old-contract',payload=dict(contract_id='c',revision=1))
        with self.assertRaisesRegex(ValueError,'final_protocol_frozen'):self.fixture.admit()
        self.assertEqual(self.service.budgets.balance('p','attempts')['reserved'],1)


@unittest.skipUnless(Path('artifacts/p4-simulated-client-001/raw/train/0000.json').exists(),'requires prepared public calibration labels')
class IndependentFinalMathTests(unittest.TestCase):
    def test_public_calibration_only_and_forged_test_target_rejected(self):
        from asr_evaluation.ood_worker import execute
        root=Path('artifacts/p4-simulated-client-001')
        rows=[json.loads((root/'raw/train'/f'{i:04d}.json').read_text()) for i in range(2)]
        model=json.loads((root/'public/baseline.json').read_text())
        data=dict(case=json.loads((root/'public/case.json').read_text()),baseline=model,models={'same':model},
                  private_id=rows,private_ood=copy.deepcopy(rows),criteria=json.loads((root/'public/task.json').read_text())['acceptance'])
        request=dict(operation='final',primary_model='same',model_trials=['same'],protocol_sha256='a'*64)
        result=execute(request,data)
        self.assertEqual(result['assessment'],'objective_not_met_on_frozen_test')
        self.assertEqual(result['label_validity']['private_id']['equation_valid'],2)
        self.assertEqual(result['models']['same']['paired_mse_intervals']['private_ood']['mean'],0)
        self.assertNotIn('sample_voltage_mse',result['baseline']['private_id'])
        data['private_ood'][0]['y'][0]+=.01
        with self.assertRaisesRegex(ValueError,'test target'):execute(request,data)


if __name__=='__main__':unittest.main()
