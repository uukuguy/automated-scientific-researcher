"""Budget cleanup headroom and absolute setup deadline; no model calls."""
from pathlib import Path
import tempfile
import time
import unittest
import json
import os
import subprocess
from unittest.mock import patch

from integrations.runtimes.pi import Limits,PiRuntime,RuntimeFailure
from integrations.runtimes import session


class DeadlineTests(unittest.TestCase):
    def test_prelaunch_cap_is_durable_and_measured_setup_is_not_free(self):
        import test_control_service
        from integrations.aar.bridge import ResearchBridge
        from integrations.runtimes.session import run_session
        fixture=test_control_service.ControlTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.start()
        root=Path(fixture.tmp.name);auth=root/'oauth-fixture.json'
        auth.write_text(json.dumps({'openai-codex':{'type':'oauth','access':'fixture','refresh':'fixture','expires':9999999999999}}))
        class SetupOnly:
            provider='codex';model='gpt-6.1-sol'
            def run(self,**kwargs):
                time.sleep(.02)
                details=dict(kind='model_walltime',limit=10,observed=20,reason='Version fixture exhausted setup cap; no model launched.')
                kwargs['on_event'](dict(type='asr_limit',recoverable=True,**details))
                raise RuntimeFailure('setup_deadline_exhausted',details=details)
        bridge=ResearchBridge(fixture.service,project='p',run='r',researcher_token='agent-secret',supervisor_token='human-secret',workspace=root,snapshots=root/'snapshots')
        with self.assertRaises(RuntimeFailure):
            run_session(SetupOnly(),bridge,config_dir=root/'private',native_session_id='r',prompt='fixture',limits=Limits(3,1,1),oauth_source=auth)
        state=fixture.service.get_run('human-secret','p','r')
        self.assertEqual(state['state'],'paused')
        self.assertGreater(state['budget']['research_walltime_ms']['spent'],0)
        self.assertEqual(state['budget']['research_walltime_ms']['reserved'],0)
        self.assertEqual(state['budget']['turns']['spent'],0)
        self.assertTrue(state['runtime_sessions'][0]['limit_observations'])

    def test_turn_exhaustion_checkpoints_limit_and_aborts_before_next_request(self):
        extension=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code=f'''import extension from {json.dumps(extension)};
const handlers={{}};let aborted=false,checkpoint;
globalThis.fetch=async()=>({{ok:true,json:async()=>({{}})}});
extension({{on:(event,handler)=>handlers[event]=handler,registerTool:()=>{{}},appendEntry:(type,data)=>checkpoint=data}});
const context={{abort:()=>{{aborted=true}}}};
await handlers.before_provider_request({{}},context);
await handlers.before_provider_request({{}},context);
console.log('UNSAFE_NEXT_REQUEST');'''
        env=dict(os.environ,ASR_MAX_TURNS='1',ASR_MAX_TOOLS='1',ASR_DEADLINE_MS=str(int((time.time()+3)*1000)))
        result=subprocess.run(['node','--input-type=module','-e',code],env=env,capture_output=True,timeout=5)
        self.assertNotIn(b'UNSAFE_NEXT_REQUEST',result.stdout)
        records=[json.loads(line) for line in result.stdout.splitlines() if line.startswith(b'{')]
        self.assertTrue(records,'cap exhaustion must emit an explicit recoverable checkpoint')
        self.assertEqual(records[0]['type'],'asr_limit')
        self.assertEqual(records[0]['kind'],'provider_turns')
        self.assertEqual(records[0]['limit'],1)
        self.assertEqual(records[0]['observed'],2)
        self.assertTrue(records[0]['recoverable'])

    def test_engine_deadline_reserves_cleanup_inside_claimed_walltime(self):
        helper=getattr(session,'session_engine_deadline',None)
        self.assertTrue(callable(helper),'runtime needs cleanup headroom inside reserved budget')
        self.assertEqual(helper(Limits(30,2,3),30000,100),125)
        self.assertEqual(helper(Limits(30,2,3),10000,100),107.5)
        self.assertGreater(helper(Limits(.1,1,1),100,100),100)
        self.assertLess(helper(Limits(.1,1,1),100,100),100.1)

    def test_slow_preflight_cannot_start_child_after_absolute_engine_deadline(self):
        self.assertIn('absolute_deadline',PiRuntime.run.__code__.co_varnames)
        with tempfile.TemporaryDirectory() as directory:
            def slow_version(*args,**kwargs):time.sleep(.04);return '1.5.0'
            with patch('integrations.runtimes.pi.subprocess.check_output',side_effect=slow_version),patch('integrations.runtimes.pi.subprocess.Popen') as spawn:
                with self.assertRaisesRegex(RuntimeFailure,'setup_deadline_exhausted') as raised:
                    PiRuntime(model='test').run(workspace=Path(directory),config_dir=Path(directory),session_id='deadline',
                        prompt='fixture',limits=Limits(1,1,1),bridge_url='http://localhost:1',bridge_token='fixture',
                        absolute_deadline=time.monotonic()+.02)
                spawn.assert_not_called()
                self.assertEqual(raised.exception.details['kind'],'model_walltime')
                self.assertGreaterEqual(raised.exception.details['observed'],raised.exception.details['limit'])

    def test_oversize_native_record_stops_with_explicit_recoverable_byte_limit(self):
        from test_runtimes import RuntimeTests
        self.assertIn('max_message_bytes',PiRuntime.__init__.__code__.co_varnames)
        with tempfile.TemporaryDirectory() as directory:
            exe=RuntimeTests().fake(directory,[{'type':'fixture','padding':'x'*2000}])
            result=PiRuntime(executable=exe,model='test',max_message_bytes=1024).run(
                workspace=Path(directory),config_dir=Path(directory),session_id='bytes',prompt='fixture',
                limits=Limits(2,1,1),bridge_url='http://localhost:1',bridge_token='fixture')
            self.assertEqual(result['status'],'limit_reached')
            self.assertEqual(result['limit_observations'][0]['kind'],'protocol_message_bytes')
            self.assertEqual(result['limit_observations'][0]['limit'],1024)
            self.assertGreater(result['limit_observations'][0]['observed'],1024)

    def test_record_count_pending_count_and_buffer_caps_are_explicit(self):
        from test_runtimes import RuntimeTests
        cases=[({'max_records':1},'protocol_records'),
               ({'max_buffer_bytes':1024},'protocol_buffer_bytes')]
        for options,expected in cases:
            with self.subTest(expected=expected),tempfile.TemporaryDirectory() as directory:
                exe=RuntimeTests().fake(directory,[{'type':'fixture','padding':'x'*1500}]*8)
                runtime=PiRuntime(executable=exe,model='test',**options)
                result=runtime.run(workspace=Path(directory),config_dir=Path(directory),session_id='bounded',
                    prompt='fixture',limits=Limits(2,1,1),bridge_url='http://localhost:1',bridge_token='fixture',
                    on_event=lambda event:time.sleep(.02) if event.get('type')=='fixture' else None)
                self.assertEqual(result['status'],'limit_reached')
                self.assertEqual(result['limit_observations'][0]['kind'],expected)

    def test_burst_uses_bounded_backpressure_without_losing_records(self):
        from test_runtimes import RuntimeTests
        with tempfile.TemporaryDirectory() as directory:
            records=[{'type':'fixture','index':i,'padding':'x'*1500} for i in range(20)]
            exe=RuntimeTests().fake(directory,records+[{'type':'agent_settled'}])
            received=[]
            def consume(event):
                if event.get('type')=='fixture':
                    received.append(event['index']);time.sleep(.01)
            result=PiRuntime(executable=exe,model='test',max_pending_records=2,max_buffer_bytes=4096).run(
                workspace=Path(directory),config_dir=Path(directory),session_id='burst',prompt='fixture',
                limits=Limits(3,1,1),bridge_url='http://localhost:1',bridge_token='fixture',on_event=consume)
            self.assertEqual(result['status'],'settled')
            self.assertEqual(received,list(range(20)))
            self.assertLessEqual(result['protocol_flow']['peak_pending_records'],2)
            self.assertLessEqual(result['protocol_flow']['peak_buffer_bytes'],4096)
            self.assertGreater(result['protocol_flow']['backpressure_waits'],0)

    def test_eof_after_full_queue_is_observed_without_waiting_for_deadline(self):
        from test_runtimes import RuntimeTests
        with tempfile.TemporaryDirectory() as directory:
            exe=RuntimeTests().fake(directory,[{'type':'fixture','index':i} for i in range(8)])
            path=Path(exe);path.write_text(path.read_text()+'  sys.exit(0)\n')
            received=[]
            def consume(event):
                if event.get('type')=='fixture':received.append(event['index']);time.sleep(.01)
            result=PiRuntime(executable=exe,model='test',max_pending_records=1).run(
                workspace=Path(directory),config_dir=Path(directory),session_id='eof',prompt='fixture',
                limits=Limits(3,1,1),bridge_url='http://localhost:1',bridge_token='fixture',on_event=consume)
            self.assertEqual(result['status'],'interrupted')
            self.assertEqual(received,list(range(8)))
            self.assertLess(result['duration_seconds'],1)


if __name__=='__main__':unittest.main()
