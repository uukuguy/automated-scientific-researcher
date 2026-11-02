"""Runtime protocol tests: fake subprocesses, no model calls."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from integrations.runtimes.pi import Limits, PiRuntime, RuntimeFailure, prepare_oauth

class RuntimeTests(unittest.TestCase):
    def test_requires_finite_positive_limits(self):
        for value in (0, -1, float('inf'), True):
            with self.assertRaises(ValueError): Limits(value, 2, 3)

    def test_oauth_only_and_no_secret_in_result(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); src=p/'auth.json'; dst=p/'runtime'
            src.write_text(json.dumps({'openai-codex':{'type':'api_key','key':'secret'}}))
            with self.assertRaises(RuntimeFailure): prepare_oauth(src,dst)
            src.write_text(json.dumps({'other':{'type':'api_key','key':'secret'},'openai-codex':{'type':'oauth','access':'private','refresh':'private'}}))
            prepare_oauth(src,dst)
            self.assertEqual(list(json.loads((dst/'auth.json').read_text())),['openai-codex'])
            self.assertEqual((dst/'auth.json').stat().st_mode & 0o777,0o600)

    def fake(self, d, records, wait=False):
        p=Path(d)/'fake-pi'; p.write_text('#!/usr/bin/env python3\nimport sys,json,time\nfor line in sys.stdin:\n c=json.loads(line)\n if c["type"]=="get_state": print(json.dumps({"type":"response","id":c["id"],"success":True,"data":{"sessionId":"native","sessionFile":"native.jsonl","model":{"provider":"openai-codex","id":"test"}}}),flush=True)\n if c["type"]=="prompt":\n  '+ ('time.sleep(10)' if wait else '\n  '.join('print('+repr(json.dumps(r))+',flush=True)' for r in records))+'\n')
        p.chmod(0o700); return str(p)

    def test_completion_requires_settled_not_just_prompt_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            exe=self.fake(d,[{'type':'response','id':'prompt','success':True},{'type':'agent_end','willRetry':True},{'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':'done'}],'stopReason':'stop'}},{'type':'agent_settled'}])
            runtime=PiRuntime(executable=exe,model='test')
            result=runtime.run(workspace=Path(d),config_dir=Path(d),session_id='run1',prompt='test',limits=Limits(2,2,3),bridge_url='http://localhost:1',bridge_token='test')
            self.assertEqual(result['status'],'settled'); self.assertEqual(result['session']['sessionId'],'native')

    def test_deadline_terminates_child(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=PiRuntime(executable=self.fake(d,[],True),model='test')
            result=runtime.run(workspace=Path(d),config_dir=Path(d),session_id='run1',prompt='test',limits=Limits(.1,2,3),bridge_url='http://localhost:1',bridge_token='test')
            self.assertEqual(result['status'],'timed_out')

    def test_external_stop_interrupts_generation(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=PiRuntime(executable=self.fake(d,[],True),model='test')
            result=runtime.run(workspace=Path(d),config_dir=Path(d),session_id='run1',prompt='test',limits=Limits(2,2,3),bridge_url='http://localhost:1',bridge_token='test',should_stop=lambda:True)
            self.assertEqual(result['status'],'cancelled')

    def test_provider_error_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            exe=self.fake(d,[{'type':'message_end','message':{'role':'assistant','stopReason':'error','errorMessage':'rate limit 429'}},{'type':'agent_settled'}])
            result=PiRuntime(executable=exe,model='test').run(workspace=Path(d),config_dir=Path(d),session_id='run1',prompt='test',limits=Limits(2,2,3),bridge_url='http://localhost:1',bridge_token='test')
            self.assertEqual(result['status'],'rate_limited')

class ExtensionGateTests(unittest.TestCase):
    def test_provider_hook_exits_before_denied_request(self):
        import subprocess
        extension=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code=f"import extension from {json.dumps(extension)}; const handlers={{}}; extension({{on:(k,v)=>handlers[k]=v,registerTool:()=>{{}}}}); await handlers.before_provider_request(); console.log('UNSAFE_REQUEST');"
        env=dict(os.environ,ASR_MAX_TURNS='1',ASR_MAX_TOOLS='1',ASR_DEADLINE_MS='1')
        result=subprocess.run(['node','--input-type=module','-e',code],env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,75);self.assertNotIn(b'UNSAFE_REQUEST',result.stdout)

class BridgeTests(unittest.TestCase):
    def test_snapshot_rejects_symlink_and_preserves_content(self):
        from integrations.aar.bridge import ResearchBridge
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);work=root/'work';work.mkdir()
            bridge=ResearchBridge(None,project='p',run='r',researcher_token='r',supervisor_token='s',workspace=work,snapshots=root/'snapshots')
            (work/'note.txt').write_text('hypothesis')
            first=bridge.snapshot(['note.txt'])
            (work/'note.txt').write_text('different')
            second=bridge.snapshot(['note.txt'])
            self.assertNotEqual(first['snapshot_sha256'],second['snapshot_sha256'])
            saved=root/'snapshots'/first['snapshot_sha256']/'files'/'note.txt'
            self.assertEqual(saved.read_text(),'hypothesis')
            (work/'secret').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError): bridge.snapshot(['secret'])
