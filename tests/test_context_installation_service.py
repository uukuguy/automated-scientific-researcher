import json
from pathlib import Path
import unittest
import shutil
import test_context_sources as sources


@unittest.skipUnless(shutil.which('pi'),'pinned pi SDK unavailable')
class InstallationServiceTests(unittest.TestCase):
    def setUp(self):
        sources.ContextSourcesTests.setUp(self)
        self.path=Path(self.path).resolve()
        with self.path.open('a') as f:f.write(json.dumps(dict(type='message',id='b',parentId='a',message=dict(role='assistant',content=[dict(type='text',text='当前工作')],stopReason='stop')))+'\n')
        self.base_save=sources.ContextSourcesTests.register
        self.s.register_context_source('human-secret','p','r',subject='lead',idempotency_key='source',path=str(self.path),native_session_id='native',leaf_id='b',keep_recent_groups=1,max_journal_bytes=100000)
        self.prepared=sources.ContextSourcesTests.prepared(self)
        self.bundle=sources.ContextSourcesTests.bundle(self,self.prepared)
        sources.ContextSourcesTests.admit(self,self.prepared,self.bundle)

    session=sources.ContextSourcesTests.session

    def test_stage_recomputes_review_and_coverage_before_any_installation_permission(self):
        result=self.s.stage_context_installation('human-secret','p','r',subject='lead',admission_id='admit',first_kept_entry_id='b',idempotency_key='stage')
        self.assertEqual(result['status'],'staged');self.assertFalse(result['installation_authorized'])
        self.assertIn('summary',result['plan']);self.assertEqual(result,self.s.stage_context_installation('human-secret','p','r',subject='lead',admission_id='admit',first_kept_entry_id='b',idempotency_key='stage'))

    def live(self):
        import subprocess,sys,hashlib
        from integrations.runtimes.process import identify
        binding=self.s.organization_runtime_binding('lead','p','r',capability_profile='research-organization/1',capability_pack_sha256='a'*64)
        claim=self.s.claim_runtime('human-secret','p','r','installer',idempotency_key='installer',runtime_identity=self.base.org.fixture.runtime_identity(),requested_walltime_ms=10000,organization_binding=binding)
        ids=dict(session_id=claim['session_id'],epoch=claim['epoch'],owner='installer')
        self.s.bind_runtime_context('human-secret','p','r',**ids,native_session_id='native',journal_directory=str(self.path.parent))
        self.s.begin_runtime_launch('human-secret','p','r',**ids)
        process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
        self.addCleanup(lambda:(process.terminate(),process.wait()))
        self.s.attach_runtime_process('human-secret','p','r',**ids,identity=identify(process.pid))
        cursor=dict(type='asr_context_cursor',schema='asr-pi-cursor/1',observation_id='boundary',status='observed',boundary='session_before_compact',native_session_id='native',journal_file=str(self.path),leaf_id='b',branch_entries=3,branch_ids_sha256=hashlib.sha256(b'["u","a","b"]').hexdigest())
        self.s.observe_context_cursor('human-secret','p','r',**ids,observation=cursor)
        return ids,cursor

    def test_actual_sdk_append_is_verified_once_and_original_prefix_survives(self):
        import subprocess,shutil
        self.s.stage_context_installation('human-secret','p','r',subject='lead',admission_id='admit',first_kept_entry_id='b',idempotency_key='stage')
        ids,cursor=self.live()
        result=self.s.authorize_context_installation('human-secret','p','r',**ids,stage_id='stage',observation=cursor,tokens_before=1000)
        self.assertEqual(result['status'],'authorized');ticket=result['ticket']
        index=Path(shutil.which('pi')).resolve().parents[1]/'index.js'
        code=f'''import {{SessionManager}} from {json.dumps(index.as_uri())};let text='';for await(const part of process.stdin)text+=part;const data=JSON.parse(text);const manager=SessionManager.open(data.path);const c=data.compaction;console.log(JSON.stringify({{entry_id:manager.appendCompaction(c.summary,c.firstKeptEntryId,c.tokensBefore,c.details,true)}}));'''
        native=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(dict(path=str(self.path),compaction=ticket['compaction'])),text=True,capture_output=True,timeout=10)
        self.assertEqual(native.returncode,0,native.stderr);entry=json.loads(native.stdout)['entry_id']
        receipt=self.s.complete_context_installation('human-secret','p','r',**ids,boundary_id='boundary',ticket_id=ticket['ticket_id'],entry_id=entry,idempotency_key='complete')
        self.assertEqual(receipt['status'],'verified',receipt);self.assertTrue(receipt['original_journal_preserved'])
        self.assertTrue(receipt['context_installed'])

    def staged(self):
        return self.s.stage_context_installation('human-secret','p','r',subject='lead',admission_id='admit',first_kept_entry_id='b',idempotency_key='stage')

    def test_rule_change_or_incomplete_coverage_prevents_authorization(self):
        from asr_service.control import ControlError
        self.staged();ids,cursor=self.live()
        state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','pause',expected_revision=state['control_revision'],idempotency_key='changed-rule')
        with self.assertRaises(ControlError):
            self.s.authorize_context_installation('human-secret','p','r',**ids,stage_id='stage',observation=cursor,tokens_before=1000)

    def test_original_rewrite_cannot_be_accepted_as_native_installation(self):
        self.staged();ids,cursor=self.live()
        ticket=self.s.authorize_context_installation('human-secret','p','r',**ids,stage_id='stage',observation=cursor,tokens_before=1000)['ticket']
        self.path.write_text(self.path.read_text().replace('失败结果必须保留','替换记录'))
        receipt=self.s.complete_context_installation('human-secret','p','r',**ids,boundary_id='boundary',ticket_id=ticket['ticket_id'],entry_id='pretend',idempotency_key='complete-false')
        self.assertEqual(receipt['status'],'deferred');self.assertEqual(receipt['reason'],'context_original_journal_changed')
        self.assertFalse(receipt['context_installed'])

    def test_stage_cannot_issue_another_ticket_at_a_new_boundary(self):
        import copy
        from asr_service.control import ControlError
        self.staged();ids,cursor=self.live()
        first=self.s.authorize_context_installation('human-secret','p','r',**ids,stage_id='stage',observation=cursor,tokens_before=1000)
        self.assertEqual(first,self.s.authorize_context_installation('human-secret','p','r',**ids,stage_id='stage',observation=cursor,tokens_before=1000))
        newer=dict(cursor,observation_id='new-boundary')
        self.s.observe_context_cursor('human-secret','p','r',**ids,observation=newer)
        with self.assertRaisesRegex(ControlError,'context_stage_already_used'):
            self.s.authorize_context_installation('human-secret','p','r',**ids,stage_id='stage',observation=newer,tokens_before=1000)

    def test_exited_write_can_be_reconciled_but_cannot_grant_current_admission(self):
        import subprocess,shutil
        from integrations.runtimes.process import verify_process_exit
        from asr_service.control import ControlError
        stage=self.staged();ids,cursor=self.live()
        ticket=self.s.authorize_context_installation('human-secret','p','r',**ids,stage_id=stage['stage_id'],observation=cursor,tokens_before=1000)['ticket']
        index=Path(shutil.which('pi')).resolve().parents[1]/'index.js'
        code=f'import {{SessionManager}} from {json.dumps(index.as_uri())};let s="";for await(const p of process.stdin)s+=p;const d=JSON.parse(s),m=SessionManager.open(d.path),c=d.compaction;console.log(JSON.stringify(m.appendCompaction(c.summary,c.firstKeptEntryId,c.tokensBefore,c.details,true)));'
        output=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(dict(path=str(self.path),compaction=ticket['compaction'])),text=True,capture_output=True,timeout=10)
        self.assertEqual(output.returncode,0,output.stderr);entry=json.loads(output.stdout)
        state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','pause',expected_revision=state['control_revision'],idempotency_key='pause-after-write')
        args=dict(boundary_id='boundary',ticket_id=ticket['ticket_id'],entry_id=entry,idempotency_key='complete-after-change')
        failed=self.s.complete_context_installation('human-secret','p','r',**ids,**args)
        self.assertEqual(failed['status'],'deferred');self.assertTrue(failed['native_write_observed'])
        state=self.s.get_run('human-secret','p','r');session=next(s for s in state['runtime_sessions'] if s['session_id']==ids['session_id'])
        verify_process_exit(session['process_identity'],terminate=True)
        self.s.release_runtime('human-secret','p','r',**ids,execution_exited=True,actual_walltime_ms=100)
        self.s.credentials['supervisor-test']=dict(subject='supervisor',role='supervisor',projects=['p'])
        result=self.s.reconcile_context_installation('supervisor-test','p','r',**ids,**dict(args,idempotency_key='reconcile'))
        self.assertEqual(result['status'],'verified',result);self.assertTrue(result['historical_only']);self.assertTrue(result['requires_fresh_preparation'])
        self.assertFalse(result['current_state_verified'])
        state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','resume',expected_revision=state['control_revision'],idempotency_key='resume-reconciled')
        binding=self.s.organization_runtime_binding('lead','p','r',capability_profile='research-organization/1',capability_pack_sha256='a'*64)
        claim=self.s.claim_runtime('human-secret','p','r','new',idempotency_key='claim-after-reconcile',runtime_identity=self.base.org.fixture.runtime_identity(),requested_walltime_ms=1000,organization_binding=binding)
        with self.assertRaisesRegex(ControlError,'context_fresh_preparation_required'):
            self.s.bind_runtime_context('human-secret','p','r',claim['session_id'],claim['epoch'],'new',native_session_id='native',journal_directory=str(self.path.parent))

    def test_stage_bound_runtime_cannot_request_turn_before_installation(self):
        from asr_service.control import ControlError
        stage=self.staged()
        binding=self.s.organization_runtime_binding('lead','p','r',capability_profile='research-organization/1',capability_pack_sha256='a'*64)
        claim=self.s.claim_runtime('human-secret','p','r','guarded',idempotency_key='guarded-runtime',runtime_identity=self.base.org.fixture.runtime_identity(),requested_walltime_ms=1000,organization_binding=binding)
        ids=dict(session_id=claim['session_id'],epoch=claim['epoch'],owner='guarded')
        self.s.bind_runtime_context('human-secret','p','r',**ids,native_session_id='native',journal_directory=str(self.path.parent),recovery_stage_id=stage['stage_id'])
        before=self.s.get_run('human-secret','p','r')['budget']
        with self.assertRaisesRegex(ControlError,'context_verification_required'):
            self.s.admit_activity('human-secret','p','r',**ids,kind='turn',idempotency_key='forbidden-turn')
        self.assertEqual(before,self.s.get_run('human-secret','p','r')['budget'])
