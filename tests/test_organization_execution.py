"""Opt-in real task-bound containers; engineering checks, not team research."""
import json
import os
from pathlib import Path
import unittest

import test_study_execution as fixtures
import test_organization as organization


@unittest.skipUnless(os.environ.get('ASR_SCIENTIFIC_IMAGE'), 'requires explicitly selected scientific image')
class OrganizationExecutionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.StudyExecutionTests('test_real_batch_and_unchanged_training_through_owning_ledger')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.service;self.counter=0
        for actor,role in [('organizer','organizer'),('lead','lead'),('worker','worker')]:
            self.s.credentials[actor]=dict(subject=actor,role='researcher',projects=['p'])
        self.change('policy','capacity',dict(max_active_leads=1,max_active_workers=1))
        for actor,role in [('organizer','organizer'),('lead','lead'),('worker','worker')]:
            self.change('member',actor,dict(role=role,enabled=True))
        self.change('direction','d',organization.OrganizationTests.direction(),'organizer')
        self.task=dict(organization.OrganizationTests.task(),experiment_operations=['study:label','study:analysis'])
        self.change('task','t',self.task,'lead')
        self.task=dict(self.task,status='in_progress')
        self.change('task','t',self.task,'worker',1)

    def change(self,kind,entity,document,token='human-secret',revision=0):
        self.counter+=1
        return self.s.change_organization(token,'p','r',kind=kind,entity_id=entity,document=document,
            expected_revision=revision,idempotency_key=f'org-{self.counter}')

    def execute(self,request):
        from integrations.aar.bridge import ResearchBridge
        workspace=Path(self.f.tmp.name)/'worker';workspace.mkdir()
        bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='worker',supervisor_token='human-secret',
            workspace=workspace,snapshots=Path(self.f.tmp.name)/'snapshots',capability_profile='research-organization-study/1',
            dispatch=lambda trial:self.f.supervisor.execute(trial['execution_attempt_id'],'engineering-supervisor'))
        delivery=bridge.call('submit_study',dict(request=request,timeout_seconds=60,
            hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1),organization_task=dict(task_id='t',revision=2)),'engineering')
        trial=delivery['receipt'];result=self.f.supervisor.store.get(trial['execution_attempt_id'])
        self.assertEqual(delivery['state']['trials'][0]['organization_task']['task_revision'],2)
        self.assertNotIn('execution_request',delivery['state']['trials'][0])
        path=Path(result['report']['evidence_path'])
        self.assertEqual(json.loads((path/'manifest.json').read_text())['organization_task'],trial['organization_task'])
        self.assertTrue(result['report']['execution_exited'])
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],0)
        self.assertEqual(self.s.budgets.balance('p','attempts')['spent'],1)
        self.change('task','t',dict(self.task,status='completed',result='Engineering execution '+result['state'],
            evidence_trial_ids=[trial['trial_id']]),'worker',2)
        return result,path

    def test_real_task_bound_numerical_label(self):
        result,path=self.execute(dict(operation='label',purpose='augmentation',coordinates=[[1.012345,.998765,1.023456]]))
        self.assertEqual(result['state'],'succeeded')
        events=json.loads((path/'study-events.json').read_text())
        samples=[e['row'] for e in events if e['type']=='sample']
        self.assertEqual(len(samples),1)
        self.assertEqual(samples[0]['status'],'labelled')

    def test_real_failed_analysis_preserves_bound_failure(self):
        result,path=self.execute(dict(operation='analysis',source="def main(data):\n    raise RuntimeError('deliberate task failure')\n",input_trials=[]))
        self.assertEqual(result['state'],'failed')
        self.assertIn('deliberate task failure',(path/'candidate-stream.log').read_text())


if __name__=='__main__':unittest.main()
