"""Task-scoped admission tests; no model or numerical claims."""
import json
import unittest
from pathlib import Path
import sys

import test_study_admission as study_fixtures
import test_organization as organization_fixtures
from asr_service.control import ControlError
from asr_supervisor.store import ExecutionStore


class OrganizationExperimentTests(unittest.TestCase):
    def setUp(self):
        self.f=study_fixtures.StudyAdmissionTests('test_shared_ledger_reservation_and_replay')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.configure()
        self.s=self.f.service;self.counter=0
        for name in ('organizer','lead','worker','other'):
            self.s.credentials[name]=dict(subject=name,role='researcher',projects=['p'])
        self.change('policy','capacity',dict(max_active_leads=2,max_active_workers=2))
        for name,role in [('organizer','organizer'),('lead','lead'),('worker','worker'),('other','worker')]:
            self.change('member',name,dict(role=role,enabled=True))
        self.change('direction','d',organization_fixtures.OrganizationTests.direction(),'organizer')

    def change(self,kind,entity,document,token='human-secret',revision=0):
        self.counter+=1
        return self.s.change_organization(token,'p','r',kind=kind,entity_id=entity,
            document=document,expected_revision=revision,idempotency_key=f'org-{self.counter}')

    def task(self,operations=None):
        self.document=organization_fixtures.OrganizationTests.task()
        if operations is not None:self.document['experiment_operations']=operations
        self.change('task','t',self.document,'lead')
        self.document=dict(self.document,status='in_progress')
        self.change('task','t',self.document,'worker',1)

    def submit(self,actor='worker',revision=2,key='label',binding=True):
        extra={'organization_task':dict(task_id='t',revision=revision)} if binding else {}
        return self.s.submit_study(actor,'p','r',request_key=key,
            request=dict(operation='label',purpose='augmentation',coordinates=[[1,1,1]]),
            timeout_seconds=5,hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1),**extra)

    def test_coordination_task_is_not_experiment_permission(self):
        self.task()
        with self.assertRaisesRegex(ControlError,'organization_task_required'):self.submit(binding=False)
        with self.assertRaisesRegex(ControlError,'organization_operation_forbidden'):self.submit()
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],0)

    def test_owner_revision_and_operation_are_frozen_without_double_charge(self):
        self.task(['study:label'])
        for actor in ('organizer','lead','other','human-secret'):
            with self.assertRaisesRegex(ControlError,'organization_task_owner_required'):self.submit(actor)
        with self.assertRaisesRegex(ControlError,'organization_task_stale'):self.submit(revision=1)
        trial=self.submit();binding=trial['organization_task']
        self.assertEqual(binding['subject'],'worker')
        self.assertEqual(binding['operation'],'study:label')
        self.assertEqual(binding['task']['revision'],2)
        self.assertEqual(binding['direction']['entity_id'],'d')
        self.assertEqual(self.submit(),trial)
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],1)

    def test_task_cannot_close_or_change_permissions_with_queued_or_active_trial(self):
        self.task(['study:label']);trial=self.submit()
        with self.assertRaisesRegex(ControlError,'task_in_progress'):
            self.change('task','t',dict(self.document,status='completed',result='done',experiment_operations=['study:fit']),'worker',2)
        for active in (False,True):
            if active:ExecutionStore(self.s.path).claim(trial['execution_attempt_id'],'fixture')
            with self.assertRaisesRegex(ControlError,'task_experiments_unsettled'):
                self.change('task','t',dict(self.document,status='completed',result='done'),'worker',2)

    def test_cancelled_queue_allows_task_close_but_historical_replay_survives(self):
        self.task(['study:label']);trial=self.submit()
        self.s.command('human-secret','p','r','cancel_trial',expected_revision=1,idempotency_key='cancel',payload=dict(trial_id=trial['trial_id']))
        self.change('task','t',dict(self.document,status='completed',result='Cancelled queued attempt; no result claimed'),'worker',2)
        self.assertEqual(self.submit(),trial)
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],0)

    def test_legacy_routes_and_enabling_over_pending_experiments_are_blocked(self):
        with self.assertRaisesRegex(ControlError,'organization_operation_unavailable'):
            self.s.submit_trial('worker','p','r',request_key='legacy',variables={},references={},requested_budget={})
        with self.assertRaisesRegex(ControlError,'organization_operation_unavailable'):
            self.s.submit_replication('worker','p','r',request_key='replicate',trial_id='missing',requested_budget={})
        other=study_fixtures.StudyAdmissionTests('test_shared_ledger_reservation_and_replay')
        other.setUp();self.addCleanup(other.doCleanups);other.configure();other.admit()
        with self.assertRaisesRegex(ControlError,'organization_experiment_reconciliation_required'):
            other.service.change_organization('human-secret','p','r',kind='policy',entity_id='capacity',
                document=dict(max_active_leads=2,max_active_workers=2),expected_revision=0,idempotency_key='capacity')

    def test_failed_process_evidence_retains_task_binding_and_allows_honest_close(self):
        from asr_supervisor.process import ProcessBackend
        from asr_supervisor.supervisor import Supervisor
        self.task(['study:label']);trial=self.submit()
        manager=Supervisor(ExecutionStore(self.s.path),Path(self.f.tmp.name)/'evidence',
            backend=ProcessBackend([sys.executable,'-c','raise SystemExit(7)']),poll_seconds=.01)
        result=manager.execute(trial['execution_attempt_id'],'fixture-worker')
        self.assertEqual(result['state'],'failed')
        path=Path(result['report']['evidence_path'])
        manifest=json.loads((path/'manifest.json').read_text())
        self.assertEqual(manifest['organization_task'],trial['organization_task'])
        self.change('task','t',dict(self.document,status='completed',result='Execution failed; negative outcome retained'),'worker',2)
        self.assertEqual(self.submit(),trial)
        self.assertEqual(self.s.budgets.balance('p','attempts')['spent'],1)
        # A manifest must not substitute responsibility while retaining the same
        # numerical request hash. This is integrity checking, not science scoring.
        manifest['organization_task']['subject']='other'
        (path/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'manifest organization binding mismatch'):
            manager._report(result,path)

    def test_scientific_role_profile_binds_worker_and_preserves_bridge_task_gate(self):
        from integrations.runtimes.pi import PiRuntime, Limits, RuntimeFailure
        from integrations.runtimes.session import run_session
        from integrations.aar.bridge import ResearchBridge
        self.task(['study:label']);root=Path(self.f.tmp.name)
        pack=PiRuntime(model='gpt-6.1-sol',capabilities_path=Path('integrations/runtimes/organization-study-capabilities.json')).preflight_capabilities()
        kwargs=dict(capability_profile=pack['pack']['id'],capability_pack_sha256=pack['sha256'])
        with self.assertRaisesRegex(ControlError,'organization_scientific_role_required'):
            self.s.organization_runtime_binding('organizer','p','r',**kwargs)
        binding=self.s.organization_runtime_binding('worker','p','r',**kwargs)
        self.assertEqual(binding['role'],'worker')
        bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='worker',supervisor_token='human-secret',
            workspace=root/'worker',snapshots=root/'snapshots',capability_profile=pack['pack']['id'])
        args=dict(request=dict(operation='label',purpose='augmentation',coordinates=[[1,1,1]]),
            timeout_seconds=5,hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))
        with self.assertRaisesRegex(ControlError,'organization_task_required'):bridge.call('submit_study',args,'missing-task')
        result=bridge.call('submit_study',dict(args,organization_task=dict(task_id='t',revision=2)),'owned')
        self.assertEqual(result['receipt']['organization_task']['subject'],'worker')
        self.assertNotIn('execution_request',result['state']['trials'][0])
        self.assertEqual(result['state']['trials'][0]['organization_task']['task_id'],'t')
        self.assertEqual(result['state']['trials'][0]['organization_task']['task_revision'],2)
        auth=root/'auth.json';auth.write_text(json.dumps({'openai-codex':{'type':'oauth','access':'fixture','refresh':'fixture'}}))
        contexts=[]
        class SetupOnly:
            provider='codex';model='gpt-6.1-sol'
            def preflight_capabilities(self):return pack
            def run(self,**arguments):
                contexts.append(Path(arguments['config_dir']))
                raise RuntimeFailure('fixture_no_model')
        with self.assertRaisesRegex(RuntimeFailure,'fixture_no_model'):
            run_session(SetupOnly(),bridge,config_dir=root/'private',native_session_id='r',prompt='fixture',limits=Limits(3,1,1),oauth_source=auth)
        self.assertEqual(contexts[0].parent,root/'private/organization')
        state=self.s.get_run('human-secret','p','r')
        self.assertEqual(state['runtime_sessions'][0]['organization_binding'],binding)


if __name__=='__main__':unittest.main()
