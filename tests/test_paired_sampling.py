import copy
import json
import unittest
from unittest.mock import patch

import test_study_admission as fixtures
from asr_service.control import ControlError


def protocol():
    return dict(schema='asr-paired-sampling/1',proposal_sha256='a'*64,purpose='augmentation',
        charging='each_slot_no_retries',groups={'g':dict(blocks={'shared':[[1.,1.,1.]]},arms={'A':['shared'],'B':['shared']})})


class PairedSamplingTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.StudyAdmissionTests('test_shared_ledger_reservation_and_replay')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.configure();self.s=self.f.service
        self.doc=copy.deepcopy(self.f.contract);self.doc['budget'].update(attempts=5,sample_proposals=6,execution_ms=30000)
        self.doc['provenance']['paired_sampling']=protocol();self.revision=1

    def apply(self):
        self.revision+=1
        self.s.publish_contract('human-secret','p','c',self.doc,expected_revision=self.revision-1,idempotency_key=f'pub-{self.revision}')
        state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','apply_contract',expected_revision=state['control_revision'],
            idempotency_key=f'apply-{self.revision}',payload=dict(contract_id='c',revision=self.revision))

    def submit(self,arm='A',key=None,coordinates=None,purpose='augmentation'):
        return self.s.submit_study('agent-secret','p','r',request_key=key or arm,
            request=dict(operation='label',purpose=purpose,coordinates=coordinates or [[1.,1.,1.]],paired_batch=dict(group_id='g',arm_id=arm)),
            timeout_seconds=5,hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))

    def test_declared_pair_reuses_coordinate_but_reserves_each_solve(self):
        self.apply();a=self.submit();b=self.submit('B')
        self.assertEqual(self.s.budgets.balance('p','sample_proposals')['reserved'],2)
        self.assertNotEqual(a['execution_attempt_id'],b['execution_attempt_id'])
        self.assertEqual(a['paired_sampling']['protocol_sha256'],b['paired_sampling']['protocol_sha256'])
        self.assertEqual(a['paired_sampling']['slot_ids'],['shared/0'])
        self.assertEqual(self.submit(),a)

    def test_slot_cannot_be_replenished_after_cancel_and_protocol_cannot_drift(self):
        self.apply();a=self.submit();state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','cancel_trial',expected_revision=state['control_revision'],idempotency_key='cancel',payload=dict(trial_id=a['trial_id']))
        with self.assertRaisesRegex(ControlError,'paired_batch_already_submitted'):self.submit(key='replacement')
        self.assertEqual(self.submit(),a)
        self.doc['provenance']['paired_sampling']['proposal_sha256']='b'*64;self.apply()
        with self.assertRaisesRegex(ControlError,'paired_protocol_changed'):self.submit('B')

    def test_wrong_coordinates_unknown_arm_and_probe_conversion_rejected(self):
        self.apply()
        for kwargs in (dict(coordinates=[[1.01,1,1]]),dict(arm='unknown'),dict(purpose='probe')):
            with self.assertRaises(ControlError):self.submit(**kwargs)
        with self.assertRaisesRegex(ControlError,'paired_batch_required'):self.f.admit()
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],0)

    def test_protocol_requires_budget_and_unique_blocks_groups(self):
        from asr_service.paired_sampling import validate
        p=protocol()
        with self.assertRaisesRegex(ControlError,'paired_budget_insufficient') as caught:validate(p,dict(attempts=1,sample_proposals=1))
        self.assertEqual(caught.exception.details['requested'],2)
        self.assertEqual(caught.exception.details['limit'],1)
        self.assertTrue(caught.exception.details['task_retained'])
        p['groups']['other']=copy.deepcopy(p['groups']['g'])
        with self.assertRaisesRegex(ControlError,'paired_coordinate_collision'):validate(p,dict(attempts=5,sample_proposals=6))
        p=protocol();p['groups']['g']['blocks']['other']=[[1,1,1]];p['groups']['g']['arms']['B']=['other']
        with self.assertRaisesRegex(ControlError,'paired_coordinate_collision'):validate(p,dict(attempts=5,sample_proposals=6))

    def test_rejected_contract_budget_has_durable_details_without_pausing_run(self):
        self.doc['budget']['sample_proposals']=1
        with self.assertRaisesRegex(ControlError,'paired_budget_insufficient'):self.apply()
        with self.s._connect() as db:
            events=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_events')]
        blocked=[e for e in events if e['type']=='contract_budget_rejected']
        self.assertEqual(blocked[-1]['details']['requested'],2)
        self.assertEqual(blocked[-1]['details']['limit'],1)
        self.assertEqual(self.s.get_run('human-secret','p','r')['state'],'running')

    def test_unpaired_prior_data_still_blocks_declared_pair(self):
        self.f.admit();self.apply()
        with self.assertRaisesRegex(ControlError,'prior label/probe'):self.submit()

    def test_fit_cannot_pool_paired_arms(self):
        self.apply();a=self.submit();b=self.submit('B')
        def material(db,project,run,trial):
            return dict(variables=dict(operation='label',purpose='augmentation'),events=[]),dict(trial_id=trial)
        with patch('asr_service.study.completed_material',side_effect=material):
            with self.assertRaisesRegex(ControlError,'paired_fit_one_arm_required'):
                self.s.submit_study('agent-secret','p','r',request_key='pooled',request=dict(operation='fit',augmentation_trials=[a['trial_id'],b['trial_id']]),
                    timeout_seconds=5,hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],2)


if __name__=='__main__':unittest.main()
