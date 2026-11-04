import json
import os
from pathlib import Path
import subprocess
import time
import unittest


class PiContextCursorTests(unittest.TestCase):
    def run_node(self,body):
        module=Path('integrations/runtimes/pi_context_cursor.mjs').resolve().as_uri()
        result=subprocess.run(['node','--input-type=module','-e',f'import {{captureCursor}} from {json.dumps(module)};'+body],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_cursor_reads_selected_branch_without_exporting_contents(self):
        result=self.run_node("const manager={getSessionId:()=> 'native',getSessionFile:()=> '/private/session.jsonl',getLeafId:()=> 'selected',getBranch:()=>[{id:'u',message:{content:'private thought'}},{id:'selected'}]};console.log(JSON.stringify(captureCursor({sessionManager:manager})));" )
        self.assertEqual(result['status'],'observed');self.assertEqual(result['leaf_id'],'selected')
        self.assertNotIn('private thought',json.dumps(result));self.assertEqual(result['branch_entries'],2)
        self.assertFalse(result['installation_authorized'])

    def test_changing_cursor_and_missing_manager_defer_without_throwing(self):
        for code in ("let n=0;const ctx={sessionManager:{getSessionId:()=> 'native',getSessionFile:()=> '/private/session.jsonl',getLeafId:()=>++n===1?'old':'new',getBranch:()=>[{id:'old'}]}};",'const ctx={};'):
            result=self.run_node(code+'console.log(JSON.stringify(captureCursor(ctx)));')
            self.assertEqual(result['status'],'deferred');self.assertFalse(result['installation_authorized'])

    def test_enabled_provider_hook_emits_cursor_without_new_tools_or_model_call(self):
        module=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code=f'''import extension from {json.dumps(module)};const handlers={{}};
globalThis.fetch=async()=>({{ok:true,json:async()=>({{}})}});
extension({{on:(event,handler)=>handlers[event]=handler,registerTool:()=>{{}}}});
await handlers.before_provider_request({{}},{{sessionManager:{{getSessionId:()=> 'native',getSessionFile:()=> '/private/session.jsonl',getLeafId:()=> 'leaf',getBranch:()=>[{{id:'leaf'}}]}}}});'''
        env=dict(os.environ,ASR_CONTEXT_OBSERVATION='1',ASR_MAX_TURNS='10',ASR_MAX_TOOLS='10',ASR_DEADLINE_MS=str(int((time.time()+20)*1000)))
        result=subprocess.run(['node','--input-type=module','-e',code],capture_output=True,text=True,timeout=5,env=env)
        self.assertEqual(result.returncode,0,result.stderr)
        records=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(records),1);self.assertEqual(records[0]['type'],'asr_context_cursor')
        self.assertEqual(records[0]['boundary'],'before_provider_request');self.assertEqual(records[0]['leaf_id'],'leaf')
