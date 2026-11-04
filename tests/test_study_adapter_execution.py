"""Opt-in true bridge recovery, with no manual adapter calls in the workflow."""
import copy
import json
import os
from pathlib import Path
import unittest

import test_acquisition_training_execution as fixtures
from integrations.aar.bridge import ResearchBridge
from research_projects.paired_acquisition import prototype as p


@unittest.skipUnless(os.environ.get('ASR_SCIENTIFIC_IMAGE'), 'requires explicitly selected scientific image')
class AdapterExecutionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.TrainingExecutionTests('test_full_arm_uses_own_labels_and_binds_actual_model')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.root=Path(self.f.f.tmp.name)
        current=self.s.get_run('human-secret','p','r')
        document=copy.deepcopy(current['contract']['document'])
        image=self.f.config.image
        document['provenance']['paired_adapter']=dict(profile='paired-acquisition/1',image_manifest=image,
            image_manifest_sha256=p.digest(image),group_seeds={'g':1101})
        self.s.publish_contract('human-secret','p','c',document,expected_revision=2,idempotency_key='adapter')
        self.s.command('human-secret','p','r','apply_contract',expected_revision=current['control_revision'],
            idempotency_key='adapter-apply',payload=dict(contract_id='c',revision=3))
        self.label_args=dict(request=dict(operation='label',purpose='augmentation',
            coordinates=self.f.config.policy['groups']['g']['blocks']['T0'],paired_batch=dict(group_id='g',arm_id='TT')),
            timeout_seconds=60,hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1),organization_task=dict(task_id='t',revision=2))

    def bridge(self,dispatch=None):
        return ResearchBridge(self.s,project='p',run='r',researcher_token='worker',supervisor_token='human-secret',
            workspace=self.root/'worker',snapshots=self.root/'snapshots',capability_profile='research-organization-study/1',dispatch=dispatch)

    def test_interrupted_return_recovers_checks_and_replay_never_reruns(self):
        from asr_service.study_adapters import load,summary
        def interrupted(trial):
            with self.s._connect() as db:
                prepared=load(db,'p','r',trial['paired_adapter']['preparation'])
                self.assertEqual(len(prepared['expected_inputs']),64)
            self.f.f.supervisor.execute(trial['execution_attempt_id'],'adapter-test')
            raise RuntimeError('simulated bridge loss after execution')
        with self.assertRaisesRegex(RuntimeError,'simulated bridge loss'):
            self.bridge(interrupted).call('submit_study',self.label_args,'labels')
        label=self.s.get_run('worker','p','r')['trials'][0]['trial_id']
        self.assertEqual(summary(self.s,'worker','p','r'),{})
        self.f.org.change('task','t',dict(self.f.org.task,status='completed',result='Label process exited; verification pending',evidence_trial_ids=[label]),'worker',2)
        task=dict(self.f.org.task,experiment_operations=['study:fit'],status='assigned')
        self.f.org.change('task','fit',task,'lead')
        self.f.org.change('task','fit',dict(task,status='in_progress'),'worker',1)
        fit_args=dict(request=dict(operation='fit',augmentation_trials=[label]),timeout_seconds=60,
            hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1),organization_task=dict(task_id='fit',revision=2))
        with self.assertRaisesRegex(ValueError,'study_adapter_verification_required'):
            self.s.submit_study('worker','p','r',request_key='fit',**fit_args)
        recovered=self.bridge(lambda trial:self.f.f.supervisor.execute(trial['execution_attempt_id'],'adapter-test'))
        state=recovered.call('state',{},'state')
        check=state['trials'][0]['study_adapter_check']
        self.assertEqual(check['status'],'verified');self.assertEqual(check['details']['training_rows'],192)
        fit=recovered.call('submit_study',fit_args,'fit')
        fitted=fit['receipt']['trial_id']
        checked=next(t['study_adapter_check'] for t in fit['state']['trials'] if t['trial_id']==fitted)
        self.assertEqual(checked['status'],'verified')
        self.assertEqual(checked['details']['training_rows'],192)
        self.assertNotIn('weights',json.dumps(fit['state']))
        def forbidden_dispatch(trial):raise AssertionError('completed experiment rerun')
        replay=self.bridge(forbidden_dispatch)
        self.assertEqual(replay.call('submit_study',fit_args,'fit')['receipt'],fit['receipt'])
        # Raw corruption is reported in state without publishing altered results.
        fit_record=next(t for t in self.s.get_run('worker','p','r')['trials'] if t['trial_id']==fitted)
        result_path=Path(fit_record['execution']['report']['evidence_path'])/'study-result.json'
        original_result=result_path.read_bytes()
        try:
            result_path.write_text('{}')
            damaged=replay.call('state',{},'bad-result')
            damaged_fit=next(t for t in damaged['trials'] if t['trial_id']==fitted)
            self.assertEqual(damaged_fit['study_adapter_check']['status'],'blocked')
            self.assertIn('evidence_error',damaged_fit)
            self.assertNotIn('result',damaged_fit)
        finally:result_path.write_bytes(original_result)
        replay.call('submit_study',fit_args,'fit')
        # Detect corrupted preparation in state, durably record it and forbid fit.
        reference=check['artifacts']['preparation']
        with self.s._connect() as db:
            query='SELECT body FROM asr_study_artifacts WHERE project=? AND run=? AND trial=? AND kind=?'
            keys=('p','r',reference['trial_id'],reference['kind'])
            original=db.execute(query,keys).fetchone()[0]
            db.execute('UPDATE asr_study_artifacts SET body=? WHERE project=? AND run=? AND trial=? AND kind=?',('{}',*keys))
        try:
            blocked=replay.call('state',{},'corrupt')
            self.assertTrue(all(t['study_adapter_check']['status']=='blocked' for t in blocked['trials']))
            with self.assertRaisesRegex(ValueError,'study_adapter_verification_required'):
                self.s.submit_study('worker','p','r',request_key='fit-after-corruption',**fit_args)
        finally:
            with self.s._connect() as db:
                db.execute('UPDATE asr_study_artifacts SET body=? WHERE project=? AND run=? AND trial=? AND kind=?',(original,*keys))
        # State does not silently retry a blocked check. Original-key replay is explicit.
        self.assertEqual(replay.call('state',{},'still-blocked')['trials'][0]['study_adapter_check']['status'],'blocked')
        replay.call('submit_study',self.label_args,'labels')
        result=replay.call('submit_study',fit_args,'fit')
        self.assertTrue(all(t['study_adapter_check']['status']=='verified' for t in result['state']['trials']))
        self.assertEqual(self.s.budgets.balance('p','attempts')['spent'],2)
        self.assertEqual(self.s.budgets.balance('p','sample_proposals')['spent'],64)
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],0)
        with self.s._connect() as db:
            events=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_events')]
        statuses=[e['status'] for e in events if e['type']=='study_adapter_checked']
        self.assertIn('blocked',statuses)
        (self.root/'bridge-state.json').write_text(json.dumps(result['state'],indent=2))
        (self.root/'check-history.json').write_text(json.dumps([e for e in events if e['type']=='study_adapter_checked'],indent=2))


if __name__=='__main__':unittest.main()
