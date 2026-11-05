import json
import os
from pathlib import Path
import subprocess
import time
import unittest
import test_context_cursor_binding as fixture


class RecordingBackpressureTests(unittest.TestCase):
    setUp=fixture.ContextCursorBindingTests.setUp
    bind=fixture.ContextCursorBindingTests.bind
    launch=fixture.ContextCursorBindingTests.launch

    def bridge(self):
        from integrations.aar.bridge import ResearchBridge
        bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='lead',supervisor_token='human-secret',workspace=self.root.parent/'workspace',snapshots=self.root.parent/'snapshots',capability_profile='research-organization/1')
        bridge.runtime_identity=self.ids
        return bridge

    def test_next_turn_is_deferred_with_durable_receipt_without_consuming_turn(self):
        self.bind();self.launch();bridge=self.bridge()
        before=self.s.get_run('human-secret','p','r')['budget']
        bridge.recording_pressure=lambda:dict(kind='async_log_warning_bytes',limit=100,observed=101,
            source='communication_events',capacity_policy_sha256='a'*64)
        result=bridge.call('permit',dict(kind='turn'),'blocked-turn')
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result['reason'],'recording_backpressure')
        state=self.s.get_run('human-secret','p','r')
        self.assertEqual(state['state'],'paused')
        self.assertEqual(before,state['budget'])
        self.assertFalse(result['scientific_executions_cancelled'])
        self.assertEqual(state['runtime_sessions'][0]['limit_observations'][-1]['kind'],'async_log_warning_bytes')

    def test_tool_permit_can_finish_current_interaction_before_next_turn_gate(self):
        self.bind();self.launch();bridge=self.bridge()
        bridge.recording_pressure=lambda:dict(kind='async_log_warning_bytes',limit=100,observed=101,
            source='communication_events',capacity_policy_sha256='a'*64)
        self.assertIn('activity_id',bridge.call('permit',dict(kind='tool_execution'),'finish-tool'))
        self.assertEqual(self.s.get_run('human-secret','p','r')['state'],'running')

    def test_native_hook_records_checkpoint_and_holds_without_sending_request(self):
        module=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code=f'''import extension from {json.dumps(module)};
const handlers={{}},events=[],entries=[];let aborted=false,completed=false;
globalThis.fetch=async()=>({{ok:true,json:async()=>({{status:'deferred',reason:'recording_backpressure',recoverable:true}})}});
extension({{on:(k,v)=>handlers[k]=v,registerTool:()=>{{}},appendEntry:(k,v)=>entries.push([k,v])}});
handlers.before_provider_request({{}},{{abort:()=>{{aborted=true}},ui:{{notify:text=>events.push(text)}}}}).then(()=>completed=true);
await new Promise(resolve=>setTimeout(resolve,20));
console.log(JSON.stringify({{aborted,completed,events,entries}}));process.exit(0);'''
        env=dict(os.environ,ASR_MAX_TURNS='10',ASR_MAX_TOOLS='10',ASR_DEADLINE_MS=str(int((time.time()+30)*1000)))
        result=subprocess.run(['node','--input-type=module','-e',code],env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        observed=json.loads(result.stdout)
        self.assertTrue(observed['aborted']);self.assertFalse(observed['completed'])
        self.assertTrue(observed['entries'])
        self.assertTrue(any('asr_recording_backpressure' in event for event in observed['events']))

    def test_accepted_permit_replay_is_preserved_after_pressure_changes(self):
        self.bind();self.launch();bridge=self.bridge()
        first=bridge.call('permit',dict(kind='turn'),'accepted-turn')
        bridge.recording_pressure=lambda:dict(kind='async_log_warning_bytes',limit=100,observed=101,
            source='communication_events',capacity_policy_sha256='a'*64)
        self.assertEqual(first,bridge.call('permit',dict(kind='turn'),'accepted-turn'))
        self.assertEqual(self.s.get_run('human-secret','p','r')['state'],'running')
        result=bridge.call('permit',dict(kind='turn'),'next-turn')
        self.assertEqual(result['reason'],'recording_backpressure')
        self.assertEqual(result,bridge.call('permit',dict(kind='turn'),'next-turn'))

    def test_runtime_preserves_explicit_pressure_status_and_exit_proof(self):
        import tempfile
        import test_runtimes
        from integrations.runtimes.pi import PiRuntime,Limits
        pressure=dict(type='asr_recording_backpressure',schema='asr-recording-backpressure/1',status='deferred',reason='recording_backpressure',scope='next_model_request',recoverable=True,scientific_executions_cancelled=False)
        raw=dict(type='extension_ui_request',method='notify',message='ASR_CONTEXT_EVENT '+json.dumps(pressure))
        with tempfile.TemporaryDirectory() as root:
            executable=test_runtimes.RuntimeTests().fake(root,[raw])
            result=PiRuntime(executable=executable,model='test').run(workspace=Path(root),config_dir=Path(root),session_id='pressure-test',prompt='No model',limits=Limits(3,2,2),bridge_url='http://localhost:1',bridge_token='fixture')
        self.assertEqual(result['status'],'recording_backpressure')
        self.assertEqual(result['recording_pressure_receipt'],pressure)
        self.assertFalse(result['settled'])
        self.assertIsNotNone(result['exit_code'])
        self.assertTrue(result['cleanup']['native_abort_requested'])

    def test_session_connects_actual_slow_recorder_to_control_gate(self):
        import threading
        from integrations.runtimes.async_events import AsyncEventRecorder
        from integrations.runtimes.capacity_policy import load_policy
        from integrations.runtimes.pi import Limits,PiRuntime
        from integrations.runtimes.process import identify
        from integrations.runtimes.session import run_session
        self.s.abort_runtime_prelaunch('human-secret','p','r',**self.ids,reason='fixture replacement',actual_walltime_ms=1)
        root=self.root.parent;auth=root/'auth.json'
        auth.write_text(json.dumps({'openai-codex':{'type':'oauth','access':'fixture','refresh':'fixture'}}))
        policy=load_policy();del policy['sha256'];policy['limits']['async_log_warning_bytes']['value']=100
        config=root/'recording-policy.json';config.write_text(json.dumps(policy))
        entered=threading.Event();release=threading.Event();bridge=self.bridge()
        pack=PiRuntime(model='gpt-6.1-sol',capabilities_path=Path('integrations/runtimes/organization-capabilities.json')).preflight_capabilities()
        def slow_write(line):entered.set();release.wait(3);return recorder.stream.write(line)
        class Runtime:
            provider='codex';model='gpt-6.1-sol';context_generation=0
            def preflight_capabilities(self):return pack
            def run(self,**arguments):
                import sys
                arguments['on_launch']()
                process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
                try:
                    arguments['on_process'](identify(process.pid))
                    arguments['on_event'](dict(type='fixture_event',body='pending data'))
                    if not entered.wait(1):raise AssertionError('writer did not receive event')
                    permit=bridge.call('permit',dict(kind='turn'),'actual-recorder-turn')
                    if permit.get('reason')!='recording_backpressure':raise AssertionError('pressure gate missing')
                finally:release.set();process.terminate();process.wait()
                return dict(status='recording_backpressure',recording_pressure_receipt=permit)
        before=self.s.get_run('human-secret','p','r')['budget']['turns']
        try:
            with AsyncEventRecorder(root/'events.jsonl',capacity_policy_path=config,write=slow_write) as recorder:
                result=run_session(Runtime(),bridge,config_dir=root/'private',native_session_id='native',prompt='No model',limits=Limits(3,2,2),oauth_source=auth,on_event=recorder)
        finally:release.set()
        state=self.s.get_run('human-secret','p','r')
        self.assertEqual(result['status'],'recording_backpressure')
        self.assertEqual(state['state'],'paused')
        self.assertEqual(before,state['budget']['turns'])
        self.assertEqual(state['budget']['research_walltime_ms']['reserved'],0)
        self.assertEqual(recorder.receipt['status'],'complete')
        self.assertIsNone(bridge.recording_pressure)
