import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
import unittest
from asr_service.control import ControlError
from integrations.runtimes.process import identify
import test_control_research_notes as fixtures


class ContextCursorBindingTests(unittest.TestCase):
    def setUp(self):
        self.base=fixtures.ControlResearchNotesTests();self.base.setUp();self.addCleanup(self.base.doCleanups);self.s=self.base.s
        self.root=self.s.path.parent.resolve()/'sessions';self.root.mkdir()
        self.path=self.root/'native.jsonl'
        self.path.write_text('\n'.join(json.dumps(r) for r in [dict(type='session',version=3,id='native'),dict(type='message',id='u',parentId=None,message=dict(role='user',content='question')),dict(type='message',id='a',parentId='u',message=dict(role='assistant',content=[dict(type='text',text='negative evidence')],stopReason='stop'))])+'\n')
        binding=self.s.organization_runtime_binding('lead','p','r',capability_profile='research-organization/1',capability_pack_sha256='a'*64)
        self.claim=self.s.claim_runtime('human-secret','p','r','worker',idempotency_key='claim',runtime_identity=self.base.org.fixture.runtime_identity(),requested_walltime_ms=10000,organization_binding=binding)
        self.ids=dict(session_id=self.claim['session_id'],epoch=self.claim['epoch'],owner='worker')

    def bind(self,**kw):
        return self.s.bind_runtime_context('human-secret','p','r',**self.ids,native_session_id='native',journal_directory=str(self.root),**kw)

    def launch(self):
        self.s.begin_runtime_launch('human-secret','p','r',**self.ids)
        self.process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
        def cleanup():self.process.terminate();self.process.wait()
        self.addCleanup(cleanup)
        self.s.attach_runtime_process('human-secret','p','r',**self.ids,identity=identify(self.process.pid))

    def event(self,key='cursor',**kw):
        value=dict(type='asr_context_cursor',schema='asr-pi-cursor/1',observation_id=key,observed_at='2026-11-04T00:00:00Z',status='observed',boundary='before_provider_request',native_session_id='native',journal_file=str(self.path),leaf_id='a',branch_entries=2,branch_ids_sha256=hashlib.sha256(b'["u","a"]').hexdigest(),installation_authorized=False,provider_payload_verified=False)
        return dict(value,**kw)

    def record(self,event=None,**kw):
        return self.s.observe_context_cursor('human-secret','p','r',**dict(self.ids,**kw),observation=event or self.event())

    @unittest.skipUnless(shutil.which('pi'),'pinned pi SDK unavailable')
    def test_bound_event_and_source_share_process_member_session_and_branch(self):
        self.bind();self.launch();receipt=self.record()
        self.assertEqual(receipt['status'],'bound');self.assertTrue(receipt['runtime_binding_verified'])
        self.assertFalse(receipt['installation_authorized']);self.assertEqual(receipt,self.record())
        source=self.s.register_context_source('human-secret','p','r',subject='lead',idempotency_key='live-source',path=str(self.path),native_session_id='native',leaf_id='a',keep_recent_groups=1,max_journal_bytes=100000,cursor_reference=dict(session_id=self.claim['session_id'],observation_id='cursor'))
        self.assertEqual(source['status'],'registered');self.assertTrue(source['cursor_source_verified'])
        self.assertFalse(source['active_cursor_verified']);self.assertFalse(source['installation_authorized'])

    def test_unlaunched_stale_and_foreign_observations_are_recorded_as_deferred(self):
        self.bind();self.assertEqual(self.record()['status'],'deferred')
        self.launch()
        for event in (self.event('foreign',native_session_id='other'),self.event('outside',journal_file=str(self.root.parent/'other.jsonl'))):
            self.assertEqual(self.record(event)['status'],'deferred')
        self.assertEqual(self.record(self.event('stale'),epoch=2)['status'],'deferred')

    def test_binding_cannot_change_or_be_self_declared(self):
        self.bind();self.assertEqual(self.bind()['native_session_id'],'native')
        with self.assertRaisesRegex(ControlError,'context_binding_immutable'):
            self.s.bind_runtime_context('human-secret','p','r',**self.ids,native_session_id='other',journal_directory=str(self.root))
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.s.observe_context_cursor('lead','p','r',**self.ids,observation=self.event())

    @unittest.skipUnless(shutil.which('pi'),'pinned pi SDK unavailable')
    def test_source_rejects_wrong_branch_and_superseded_cursor(self):
        self.bind();self.launch();self.record();self.record(self.event('newer'))
        result=self.s.register_context_source('human-secret','p','r',subject='lead',idempotency_key='old-source',path=str(self.path),native_session_id='native',leaf_id='a',keep_recent_groups=1,max_journal_bytes=100000,cursor_reference=dict(session_id=self.claim['session_id'],observation_id='cursor'))
        self.assertEqual(result['status'],'deferred');self.assertEqual(result['cursor_check']['reason'],'context_cursor_superseded')
        self.record(self.event('wrong',branch_ids_sha256='0'*64))
        result=self.s.register_context_source('human-secret','p','r',subject='lead',idempotency_key='wrong-source',path=str(self.path),native_session_id='native',leaf_id='a',keep_recent_groups=1,max_journal_bytes=100000,cursor_reference=dict(session_id=self.claim['session_id'],observation_id='wrong'))
        self.assertEqual(result['status'],'deferred');self.assertEqual(result['cursor_check']['reason'],'context_cursor_source_mismatch')

    def test_exited_process_does_not_support_new_cursor(self):
        self.bind();self.launch();self.process.terminate();self.process.wait()
        result=self.record();self.assertEqual(result['status'],'deferred');self.assertEqual(result['reason'],'context_process_unavailable')

    @unittest.skipUnless(shutil.which('pi'),'pinned pi SDK unavailable')
    def test_conflicting_replay_and_same_ids_in_another_file_cannot_replace_receipt(self):
        self.bind();self.launch();self.record()
        with self.assertRaisesRegex(ControlError,'idempotency_conflict'):
            self.record(self.event(leaf_id='different'))
        copy=self.root/'copy.jsonl';copy.write_bytes(self.path.read_bytes())
        result=self.s.register_context_source('human-secret','p','r',subject='lead',idempotency_key='copied',path=str(copy),native_session_id='native',leaf_id='a',keep_recent_groups=1,max_journal_bytes=100000,cursor_reference=dict(session_id=self.claim['session_id'],observation_id='cursor'))
        self.assertEqual(result['status'],'deferred');self.assertEqual(result['cursor_check']['reason'],'context_cursor_source_mismatch')

    def test_malformed_cursor_is_deferred_and_retained(self):
        self.bind();self.launch()
        for index,value in enumerate((self.event('bad-file',journal_file=3),self.event('bad-hash',branch_ids_sha256=7))):
            result=self.record(value);self.assertEqual(result['status'],'deferred')

    def test_session_adapter_binds_generation_and_records_cursor_without_model_calls(self):
        from integrations.aar.bridge import ResearchBridge
        from integrations.runtimes.session import run_session
        from integrations.runtimes.pi import Limits,PiRuntime
        self.s.abort_runtime_prelaunch('human-secret','p','r',**self.ids,reason='fixture replacement',actual_walltime_ms=1)
        root=self.s.path.parent.resolve();auth=root/'fixture-auth.json'
        auth.write_text(json.dumps({'openai-codex':{'type':'oauth','access':'fixture','refresh':'fixture'}}))
        pack=PiRuntime(model='gpt-6.1-sol',capabilities_path=Path('integrations/runtimes/organization-capabilities.json')).preflight_capabilities()
        make_event=self.event
        class Runtime:
            provider='codex';model='gpt-6.1-sol';context_generation=1
            def preflight_capabilities(self):return pack
            def run(self,**arguments):
                directory=Path(arguments['config_dir']).resolve()/'sessions-generation-1';directory.mkdir()
                arguments['on_launch']()
                process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
                try:
                    arguments['on_process'](identify(process.pid))
                    arguments['on_event'](make_event('adapter',journal_file=str(directory/'native.jsonl')))
                    arguments['on_event'](dict(type='asr_context_capacity',schema='asr-pi-context-capacity/1',observation_id='capacity-adapter',
                        status='observed',measurement='estimate',used_tokens=651,window_tokens=1000,
                        full_next_request_verified=False,provider_payload_verified=False))
                    assert bridge.context_observation_barrier()['drained']
                finally:process.terminate();process.wait()
                return dict(status='settled')
        bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='lead',supervisor_token='human-secret',workspace=root/'workspace',snapshots=root/'snapshots',capability_profile='research-organization/1')
        events=[]
        result=run_session(Runtime(),bridge,config_dir=root/'private',native_session_id='native',prompt='No model',limits=Limits(3,1,1),oauth_source=auth,on_event=events.append)
        self.assertEqual(result['context_cursor_receipts'][0]['status'],'bound')
        self.assertTrue(any(e['type']=='asr_context_cursor_binding' for e in events))
        self.assertTrue(result['context_capacity_observations'][0]['warning'])
        self.assertFalse(result['context_capacity_observations'][0]['hold_new_model_requests'])
        self.assertTrue(any(e['type']=='asr_context_capacity_assessment' for e in events))
        state=self.s.get_run('human-secret','p','r')
        session=next(s for s in state['runtime_sessions'] if s['session_id']==result['runtime_claim']['session_id'])
        self.assertTrue(session['native_context']['journal_directory'].endswith('sessions-generation-1'))
        self.assertEqual(session['state'],'exited');self.assertEqual(state['budget']['research_walltime_ms']['reserved'],0)
        self.assertEqual(state['state'],'running')
        self.assertEqual(state['budget']['turns']['spent'],0)

    def test_prelaunch_observation_does_not_create_a_false_native_binding(self):
        self.assertEqual(self.record()['status'],'deferred')
        self.assertEqual(self.bind()['native_session_id'],'native')

    def test_compaction_handshake_uses_owned_http_bridge_and_never_installs_unreviewed_content(self):
        from integrations.aar.bridge import ResearchBridge
        from urllib.request import Request,urlopen
        self.bind();self.launch()
        bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='lead',supervisor_token='human-secret',workspace=self.root.parent/'workspace',snapshots=self.root.parent/'snapshots',capability_profile='research-organization/1')
        bridge.runtime_identity=self.ids
        with bridge:
            body=dict(operation='context_boundary',arguments=dict(observation=self.event('boundary',boundary='session_before_compact')),key='boundary')
            request=Request(bridge.url,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+bridge.token,'Content-Type':'application/json'})
            with urlopen(request,timeout=5) as response:result=json.load(response)
        self.assertEqual(result['action'],'cancel');self.assertEqual(result['reason'],'context_installation_not_ready')
        self.assertEqual(result['cursor_receipt']['status'],'bound');self.assertFalse(result['installation_authorized'])
        with self.s._connect() as db:
            events=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_events')]
        self.assertTrue(any(e['type']=='context_boundary_deferred' and e['observation_id']=='boundary' for e in events))

    def test_native_hook_waits_on_real_http_control_handshake_without_model(self):
        import os,time
        from integrations.aar.bridge import ResearchBridge
        from integrations.runtimes.environment import COMMON_ENVIRONMENT,build_environment
        self.bind();self.s.begin_runtime_launch('human-secret','p','r',**self.ids)
        bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='lead',supervisor_token='human-secret',workspace=self.root.parent/'workspace',snapshots=self.root.parent/'snapshots',capability_profile='research-organization/1')
        bridge.runtime_identity=self.ids
        module=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code=f'''import extension from {json.dumps(module)};const handlers={{}};
extension({{on:(k,v)=>handlers[k]=v,registerTool:()=>{{}}}});
await new Promise(resolve=>process.stdin.once('data',resolve));
const result=await handlers.session_before_compact({{reason:'manual',signal:new AbortController().signal}},{{sessionManager:{{getSessionId:()=> 'native',getSessionFile:()=> {json.dumps(str(self.path))},getLeafId:()=> 'a',getBranch:()=>[{{id:'u'}},{{id:'a'}}]}}}});
console.log(JSON.stringify({{type:'fixture_result',result}}));'''
        with bridge:
            env=build_environment(COMMON_ENVIRONMENT,runtime='pi',provider='openai-codex')
            env.update(ASR_BRIDGE_URL=bridge.url,ASR_BRIDGE_TOKEN=bridge.token,ASR_CONTEXT_BOUNDARY_TIMEOUT_MS='2000',ASR_MAX_TURNS='10',ASR_MAX_TOOLS='10',ASR_DEADLINE_MS=str(int((time.time()+20)*1000)))
            process=subprocess.Popen(['node','--input-type=module','-e',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env=env)
            try:
                self.s.attach_runtime_process('human-secret','p','r',**self.ids,identity=identify(process.pid))
                stdout,stderr=process.communicate(b'start\n',timeout=5)
            finally:
                if process.poll() is None:process.kill();process.wait()
        self.assertEqual(process.returncode,0,stderr.decode())
        records=[json.loads(line) for line in stdout.splitlines()]
        self.assertEqual(records[-1]['result'],dict(cancel=True))
        self.assertEqual(records[-2]['reason'],'context_installation_not_ready')
        self.s.release_runtime('human-secret','p','r',**self.ids,execution_exited=True,actual_walltime_ms=100)
        with self.s._connect() as db:
            events=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_events')]
        self.assertTrue(any(e['type']=='context_cursor_bound' and e['session_id']==self.claim['session_id'] for e in events))

    def test_pending_async_observations_cancel_installation_before_cursor_mutation(self):
        from integrations.aar.bridge import ResearchBridge
        from unittest.mock import patch
        bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='lead',supervisor_token='human-secret',workspace=self.root.parent/'workspace',snapshots=self.root.parent/'snapshots',capability_profile='research-organization/1')
        bridge.runtime_identity=self.ids
        bridge.context_observation_barrier=lambda:dict(drained=False,pending=1)
        with patch.object(self.s,'observe_context_cursor',side_effect=AssertionError('must not mutate cursor')):
            result=bridge.call('context_boundary',dict(observation=self.event('pending',boundary='session_before_compact')),'pending')
        self.assertEqual(result['reason'],'context_observations_pending')
        self.assertFalse(result['installation_authorized'])
        self.assertEqual(result['observation_drain']['pending'],1)

    def test_late_ordinary_observation_cannot_overwrite_newer_installation_boundary(self):
        self.bind();self.launch()
        boundary=self.record(self.event('new-boundary',boundary='session_before_compact',observation_sequence=20))
        self.assertEqual(boundary['status'],'bound')
        late=self.record(self.event('late-old-event',observation_sequence=19))
        self.assertEqual(late['status'],'deferred')
        self.assertEqual(late['reason'],'context_cursor_superseded')
        with self.s._connect() as db:
            session=self.s._session(db,'p','r',**self.ids)
        self.assertEqual(session['native_context']['latest_observation_id'],'new-boundary')
