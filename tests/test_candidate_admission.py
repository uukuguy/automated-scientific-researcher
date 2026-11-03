"""Frozen candidate byte admission and same-method replication, no model calls."""
import copy
from pathlib import Path
import unittest
import test_control_service as fixtures
from asr_service.control import ControlService


class CandidateAdmissionTests(unittest.TestCase):
    setUp=fixtures.ControlTests.setUp
    start=fixtures.ControlTests.start

    def opt_in(self):
        self.contract['execution_policy']['candidate_profiles']=['octave-candidate/1']
        self.contract['budget'].update(evaluation_attempts=3,evaluation_ms=60000)
        self.start()

    def register(self,key='code',source=None):
        return self.service.register_candidate('agent-secret','p',request_key=key,source=source or 'function s = candidate(mpc)\ns = mpc;\nend\n',entrypoint='candidate.m',profile='octave-candidate/1')

    def submit(self,reference,key='candidate'):
        references={k:v for k,v in self.refs.items() if k!='reference'};references['candidate']=reference
        return self.service.submit_trial('agent-secret','p','r',request_key=key,variables={'solver':'octave-candidate/1'},references=references,requested_budget={'attempts':1,'execution_ms':5000})

    def test_opt_in_frozen_candidate_and_reopen_replay(self):
        self.opt_in();registered=self.register()
        self.assertEqual(self.register(),registered)
        trial=self.submit(registered['digest'])
        self.assertEqual(trial['execution_request']['profile'],'octave-candidate/1')
        self.assertEqual(trial['execution_request']['candidate']['sha256'],registered['source_sha256'])
        self.assertEqual(Path(trial['execution_request']['candidate']['path']).stat().st_mode&0o777,0o444)
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        self.assertEqual(self.submit(registered['digest']),trial)
        with self.assertRaisesRegex(ValueError,'idempotency_conflict'):self.register(source='function s=candidate(mpc);s=mpc;end')
        Path(trial['execution_request']['candidate']['path']).chmod(0o644)
        Path(trial['execution_request']['candidate']['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'candidate_artifact_corrupt'):self.submit(registered['digest'],'new')

    def test_applied_method_revision_cap_and_frozen_replication(self):
        self.contract['execution_policy']['max_candidate_revisions']=1
        self.opt_in();candidate=self.register()
        second=self.register('second','function s = candidate(mpc); s=mpc; end')
        self.assertEqual(self.register('same-code')['digest'],candidate['digest'])
        self.trial=self.submit(candidate['digest'])
        with self.assertRaisesRegex(ValueError,'candidate_revision_limit'):self.submit(second['digest'],'second-trial')
        import test_validations as validation_fixtures
        validation_fixtures.ValidationTests.complete(self)
        replica=self.service.submit_replication('agent-secret','p','r',request_key='replicate',trial_id=self.trial['trial_id'],requested_budget={'attempts':1,'execution_ms':5000})
        self.assertNotEqual(replica['trial_id'],self.trial['trial_id'])
        self.assertEqual(replica['execution_request'],self.trial['execution_request'])
        self.assertEqual(replica['replicates']['trial_id'],self.trial['trial_id'])
        self.assertEqual(self.service.submit_replication('agent-secret','p','r',request_key='replicate',trial_id=self.trial['trial_id'],requested_budget={'attempts':1,'execution_ms':5000}),replica)

    def test_run_cap_cannot_be_bypassed_by_other_run_registration(self):
        self.contract['execution_policy']['max_candidate_revisions']=1
        self.opt_in()
        first=self.register()
        self.submit(first['digest'])
        uncapped=copy.deepcopy(self.contract);del uncapped['execution_policy']['max_candidate_revisions']
        self.service.publish_contract('human-secret','p','uncapped',uncapped,expected_revision=0,idempotency_key='uncapped')
        self.service.create_run('human-secret','p','other-run','experiment-2','uncapped',1,idempotency_key='other-run')
        second=self.service.register_candidate('agent-secret','p',request_key='other-source',source='function s = candidate(mpc); s=mpc; end',run='other-run')
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        with self.assertRaisesRegex(ValueError,'candidate_revision_limit'):self.submit(second['digest'],'bypass')
        self.assertEqual(len(self.service.get_run('agent-secret','p','r')['trials']),1)
        self.assertEqual(self.service.budgets.balance('p','attempts')['reserved'],1)

    def test_replication_rejects_new_contract_timeout_without_rewriting_original(self):
        self.opt_in();candidate=self.register();self.trial=self.submit(candidate['digest'])
        import test_validations as validation_fixtures
        validation_fixtures.ValidationTests.complete(self)
        changed=copy.deepcopy(self.contract);changed['execution_policy']['timeout_seconds']=1
        self.service.publish_contract('human-secret','p','c',changed,expected_revision=1,idempotency_key='shorter')
        self.service.command('human-secret','p','r','apply_contract',expected_revision=1,idempotency_key='apply-shorter',payload={'contract_id':'c','revision':2})
        with self.assertRaisesRegex(ValueError,'replication_contract_conflict'):
            self.service.submit_replication('agent-secret','p','r',request_key='too-long',trial_id=self.trial['trial_id'],requested_budget={'attempts':1,'execution_ms':5000})
        run=self.service.get_run('agent-secret','p','r')
        self.assertEqual(len(run['trials']),1)
        self.assertEqual(run['trials'][0]['execution_request']['timeout_seconds'],5)
        self.assertEqual(self.service.budgets.balance('p','attempts')['reserved'],0)

    def test_no_implicit_candidate_permission_and_no_forged_registry(self):
        self.start();candidate=self.register()
        with self.assertRaisesRegex(ValueError,'capability_unavailable'):self.submit(candidate['digest'])
        fake=self.service.references.register('p','candidate',dict(profile='octave-candidate/1',image_id='sha256:fake',source_sha256='0'*64,size=1,entrypoint='candidate.m'))
        with self.assertRaises(ValueError):self.submit(fake,'forged')
        for source in ('x'*65537,'bad\x00source'):
            with self.assertRaises(ValueError):self.register('oversize',source)

if __name__=='__main__':unittest.main()
