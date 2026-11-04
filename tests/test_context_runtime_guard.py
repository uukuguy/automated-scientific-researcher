import json
from pathlib import Path
import tempfile
import unittest
from integrations.runtimes.pi import PiRuntime,Limits


class RuntimeInstallationGuardTests(unittest.TestCase):
    def run_case(self,verified,notification=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);trace=root/'commands.jsonl';exe=root/'fake-pi';(root/'settings.json').write_text('{}')
            record=dict(type='asr_context_installation',status='verified',ticket_id='ticket',context_installed=True,original_journal_preserved=True)
            if notification:record=dict(type='extension_ui_request',method='notify',message='ASR_CONTEXT_EVENT '+json.dumps(record))
            script='''#!/usr/bin/env python3
import sys,json
if '--version' in sys.argv:print('1.5.0');sys.exit()
for line in sys.stdin:
 c=json.loads(line)
 with open(TRACE,'a') as f:f.write(line)
 if c['type']=='get_state':print(json.dumps(dict(type='response',id=c['id'],success=True,data=dict(model=dict(provider='openai-codex',id='test')))),flush=True)
 if c['type']=='compact':
  if VERIFIED:print(json.dumps(RECORD),flush=True)
  print(json.dumps(dict(type='response',id=c['id'],success=True)),flush=True)
 if c['type']=='prompt':print(json.dumps(dict(type='agent_settled')),flush=True)
'''.replace('TRACE',repr(str(trace))).replace('VERIFIED',repr(verified)).replace('RECORD',repr(record))
            exe.write_text(script);exe.chmod(0o700)
            result=PiRuntime(executable=str(exe),model='test',compact_before_prompt=True).run(workspace=root,config_dir=root,session_id='native',prompt='continue',limits=Limits(3,2,2),bridge_url='http://localhost:1',bridge_token='test')
            commands=[json.loads(row)['type'] for row in trace.read_text().splitlines()]
            return result,commands

    def test_native_success_without_control_receipt_cannot_start_another_provider_request(self):
        result,commands=self.run_case(False)
        self.assertEqual(result['status'],'context_recovery_required');self.assertNotIn('prompt',commands)

    def test_verified_installation_allows_the_continuation_prompt(self):
        result,commands=self.run_case(True)
        self.assertEqual(result['status'],'settled');self.assertIn('prompt',commands)

    def test_official_rpc_notification_can_supply_the_verified_receipt(self):
        result,commands=self.run_case(True,notification=True)
        self.assertEqual(result['status'],'settled');self.assertTrue(result['context_installation_verified'])
