"""Subscription launch environment checks using real harmless child processes."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


KEYS={name:'fixture-not-a-secret' for name in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY','CUSTOM_API_KEY','grok_api_key','API_KEY')}


class SubscriptionEnvironmentTests(unittest.TestCase):
    def guard(self):
        name='integrations.runtimes.environment'
        self.assertIsNotNone(importlib.util.find_spec(name),'shared subscription environment guard required')
        return importlib.import_module(name)

    def test_actual_child_receives_no_inherited_api_keys(self):
        guard=self.guard()
        inherited=dict(os.environ,**KEYS)
        env=guard.build_environment(tuple(inherited),runtime='pi',provider='openai-codex',inherited=inherited)
        child=subprocess.check_output([sys.executable,'-c',
            "import os,json;print(json.dumps([k for k in os.environ if k.upper()=='API_KEY' or k.upper().endswith('_API_KEY')]))"],env=env,text=True)
        self.assertEqual(json.loads(child),[])

    def test_explicit_environment_and_nested_settings_are_rejected_without_values(self):
        guard=self.guard()
        for runtime,provider in (('pi','openai-codex'),('codex','openai'),('grok','grok')):
            with self.subTest(runtime=runtime):
                with self.assertRaises(ValueError) as error:
                    guard.build_environment(('PATH',),runtime=runtime,provider=provider,overrides={'CUSTOM_API_KEY':'private-fixture'})
                self.assertNotIn('private-fixture',str(error.exception))
                with self.assertRaises(ValueError):
                    guard.reject_api_key_settings({'nested':[{'anthropic_api_key':''}]},runtime=runtime,provider=provider)

    def test_exception_requires_explicit_noncodex_pi_provider(self):
        guard=self.guard()
        for runtime,provider in (('pi','openai_codex'),('pi','OPENAI-CODEX'),('pi','codex'),('codex','anthropic'),('grok','grok'),('pi','')):
            with self.subTest(runtime=runtime,provider=provider), self.assertRaises(ValueError):
                guard.build_environment((),runtime=runtime,provider=provider,allow_api_keys=True)
        allowed=guard.build_environment((),runtime='pi',provider='anthropic',allow_api_keys=True,overrides={'ANTHROPIC_API_KEY':'fixture'})
        self.assertIn('ANTHROPIC_API_KEY',allowed)

    def test_pi_and_codex_reject_explicit_keys_before_spawn(self):
        from integrations.runtimes.pi import PiRuntime
        from integrations.runtimes.codex_app_server import CodexAppServerClient
        self.assertIn('environment',PiRuntime.__init__.__code__.co_varnames)
        self.assertIn('environment',CodexAppServerClient.__init__.__code__.co_varnames)
        with patch('subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):PiRuntime(model='test',environment=KEYS)
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):CodexAppServerClient(cwd=directory,environment=KEYS)
            spawn.assert_not_called()

    def test_grok_builder_drops_all_unrelated_provider_keys(self):
        from integrations.runtimes import grok_smoke
        self.assertTrue(callable(getattr(grok_smoke,'grok_environment',None)))
        env=grok_smoke.grok_environment(Path('/private/home'),Path('/private/home/.grok'),'http://127.0.0.1:7897',inherited=dict(os.environ,**KEYS))
        self.assertFalse(set(KEYS)&set(env))
        self.assertEqual(env['GROK_HOME'],'/private/home/.grok')

    def test_actual_pi_protocol_child_reports_no_api_keys(self):
        from integrations.runtimes.pi import Limits,PiRuntime
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,KEYS):
            root=Path(directory);script=root/'fake-pi'
            script.write_text('''#!/usr/bin/env python3
import json,os,sys
if '--version' in sys.argv:print('1.5.0');sys.exit()
for line in sys.stdin:
 command=json.loads(line)
 if command['type']=='get_state':
  keys=[k for k in os.environ if k.upper()=='API_KEY' or k.upper().endswith('_API_KEY')]
  print(json.dumps({'type':'response','id':command['id'],'success':True,'data':{'sessionId':'native','api_keys':keys,'model':{'provider':'openai-codex','id':'test'}}}),flush=True)
 if command['type']=='prompt':print(json.dumps({'type':'agent_settled'}),flush=True)
''')
            script.chmod(0o700)
            result=PiRuntime(executable=str(script),model='test').run(workspace=root,config_dir=root,
                session_id='guard-test',prompt='fixture only',limits=Limits(2,1,1),bridge_url='http://localhost:1',bridge_token='fixture')
            self.assertEqual(result['session']['api_keys'],[])

    def test_actual_codex_protocol_child_reports_no_api_keys(self):
        from integrations.runtimes.codex_app_server import CodexAppServerClient
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,KEYS):
            root=Path(directory);script=root/'fake-codex.py'
            script.write_text('''import json,os,sys
for line in sys.stdin:
 command=json.loads(line)
 if 'id' not in command:continue
 result={} if command['method']=='initialize' else [k for k in os.environ if k.upper()=='API_KEY' or k.upper().endswith('_API_KEY')]
 print(json.dumps({'id':command['id'],'result':result}),flush=True)
''')
            with CodexAppServerClient(cwd=root,command=[sys.executable,'-u',str(script)],walltime_seconds=2) as client:
                client.initialize()
                self.assertEqual(client.request('inspect_environment',{}),[])


if __name__=='__main__':unittest.main()
