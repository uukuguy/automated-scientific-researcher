import json
import unittest
from integrations.runtimes.pi_system_context import effective_system_context


def row(**values):return dict(role='system',text=json.dumps(dict(role='system',content='',**values)))


class SystemContextTests(unittest.TestCase):
    def test_tool_delta_is_equal_to_snapshot_but_definition_change_is_not(self):
        a=dict(name='read',description='original');b=dict(name='asr',description='current')
        source=[row(sections={'rule':'keep'},toolsAdded=[a,dict(name='asr',description='old')]),row(toolsRemoved=[dict(name='asr')],toolsAdded=[b])]
        snapshot=[row(sections={'rule':'keep'},toolsAdded=[a,b])]
        self.assertEqual(effective_system_context(source),effective_system_context(snapshot))
        snapshot=[row(sections={'rule':'changed'},toolsAdded=[a,b])]
        self.assertNotEqual(effective_system_context(source),effective_system_context(snapshot))
        snapshot=[row(sections={'rule':'keep'},toolsAdded=[a,dict(name='asr',description='widened')])]
        self.assertNotEqual(effective_system_context(source),effective_system_context(snapshot))

    def test_fold_matches_installed_sdk_without_model_calls(self):
        import shutil,subprocess
        from pathlib import Path
        binary=shutil.which('pi')
        if not binary:self.skipTest('pinned SDK unavailable')
        module=Path(binary).resolve().parents[2]/'node_modules/@earendil-works/pi-ai/dist/utils/transcript.js'
        messages=[dict(role='system',content='base',timestamp=1,sections={'a':'A','b':'B'},toolsAdded=[dict(name='read')]),
                  dict(role='system',content='delta',timestamp=2,sections={'b':None,'c':'C'},toolsRemoved=[dict(name='read')],toolsAdded=[dict(name='asr')])]
        code=f'import {{getCurrentSystemMessage}} from {json.dumps(module.as_uri())};let t="";for await(const p of process.stdin)t+=p;console.log(JSON.stringify(getCurrentSystemMessage(JSON.parse(t))));'
        result=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(messages),text=True,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        expected=json.loads(result.stdout);expected.pop('timestamp')
        rows=[dict(role='system',text=json.dumps({k:v for k,v in x.items() if k!='timestamp'})) for x in messages]
        self.assertEqual(effective_system_context(rows),dict(content=expected['content'],sections=expected['sections'],tools=expected['toolsAdded']))
