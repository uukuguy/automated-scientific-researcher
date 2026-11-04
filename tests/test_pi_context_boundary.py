import json
import os
from pathlib import Path
import subprocess
import time
import unittest


class PiContextBoundaryTests(unittest.TestCase):
    def node(self,body,timeout=5):
        module=Path('integrations/runtimes/pi_context_boundary.mjs').resolve().as_uri()
        code=f'import {{beforeCompact}} from {json.dumps(module)};'+'''const events=[];let leaf='a';const ctx={sessionManager:{getSessionId:()=> 'native',getSessionFile:()=> '/private/session.jsonl',getLeafId:()=>leaf,getBranch:()=>[{id:leaf}]}};const event={signal:new AbortController().signal,reason:'manual'};'''+body
        result=subprocess.run(['node','--input-type=module','-e',code],capture_output=True,text=True,timeout=timeout)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_compaction_waits_for_host_response_then_explicitly_cancels_without_fallback(self):
        result=self.node('''let release;let completed=false;const pending=beforeCompact(event,ctx,{timeoutMs:1000,emit:e=>events.push(e),request:()=>new Promise(resolve=>release=resolve)}).then(r=>{completed=true;return r});await new Promise(r=>setTimeout(r,10));const held=!completed;release({action:'cancel',reason:'context_installation_not_ready'});const result=await pending;console.log(JSON.stringify({held,result,events}));''')
        self.assertTrue(result['held']);self.assertEqual(result['result'],dict(cancel=True))
        self.assertEqual(result['events'][0]['phase'],'entered');self.assertEqual(result['events'][-1]['phase'],'released')
        self.assertEqual(result['events'][-1]['reason'],'context_installation_not_ready')

    def test_timeout_rejection_and_abort_preserve_original_context_and_report_reason(self):
        for request,reason in [('()=>new Promise(()=>{})','boundary_timeout'),("()=>Promise.reject(new Error('secret-token'))",'boundary_request_failed')]:
            result=self.node(f'const result=await beforeCompact(event,ctx,{{timeoutMs:15,emit:e=>events.push(e),request:{request}}});console.log(JSON.stringify({{result,events}}));')
            self.assertEqual(result['result'],dict(cancel=True));self.assertEqual(result['events'][-1]['reason'],reason)
            self.assertNotIn('secret-token',json.dumps(result))
            self.assertEqual(result['events'][-1]['limit_ms'],15);self.assertIn('elapsed_ms',result['events'][-1]);self.assertTrue(result['events'][-1]['recoverable'])
        result=self.node('const controller=new AbortController();controller.abort();const result=await beforeCompact({...event,signal:controller.signal},ctx,{timeoutMs:1000,emit:e=>events.push(e),request:()=>{throw new Error("must not request")}});console.log(JSON.stringify({result,events}));')
        self.assertEqual(result['events'][-1]['reason'],'boundary_aborted')

    def test_cursor_drift_or_unimplemented_installation_cannot_authorize_default_compaction(self):
        for request,reason in [("()=>{leaf='b';return {action:'cancel'}}",'boundary_cursor_changed'),("()=>({action:'install',installation_authorized:true,summary:'unreviewed'})",'context_installation_not_ready')]:
            result=self.node(f'const result=await beforeCompact(event,ctx,{{timeoutMs:1000,emit:e=>events.push(e),request:{request}}});console.log(JSON.stringify({{result,events}}));')
            self.assertEqual(result['result'],dict(cancel=True));self.assertEqual(result['events'][-1]['reason'],reason)

    def test_extension_hook_is_registered_and_does_not_expose_internal_operation_as_model_tool(self):
        module=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code=f'''import extension from {json.dumps(module)};const handlers={{}};let tool;
globalThis.fetch=async()=>({{ok:true,json:async()=>({{action:'cancel',reason:'context_installation_not_ready'}})}});
extension({{on:(k,v)=>handlers[k]=v,registerTool:t=>tool=t}});
const result=await handlers.session_before_compact({{reason:'manual',signal:new AbortController().signal}},{{sessionManager:{{getSessionId:()=> 'native',getSessionFile:()=> '/private/session.jsonl',getLeafId:()=> 'a',getBranch:()=>[{{id:'a'}}]}}}});
console.log(JSON.stringify({{result,operations:tool.parameters.properties.operation.enum}}));'''
        env=dict(os.environ,ASR_MAX_TURNS='10',ASR_MAX_TOOLS='10',ASR_CONTEXT_BOUNDARY_TIMEOUT_MS='1000',ASR_DEADLINE_MS=str(int((time.time()+10)*1000)))
        result=subprocess.run(['node','--input-type=module','-e',code],capture_output=True,text=True,timeout=5,env=env)
        self.assertEqual(result.returncode,0,result.stderr)
        records=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(records[-1]['result'],dict(cancel=True));self.assertNotIn('context_boundary',records[-1]['operations'])

    def test_abort_while_waiting_and_broken_event_sink_still_cancel(self):
        result=self.node('const controller=new AbortController();setTimeout(()=>controller.abort(),10);const result=await beforeCompact({...event,signal:controller.signal},ctx,{timeoutMs:1000,emit:e=>events.push(e),request:()=>new Promise(()=>{})});console.log(JSON.stringify({result,events}));')
        self.assertEqual(result['result'],dict(cancel=True));self.assertEqual(result['events'][-1]['reason'],'boundary_aborted')
        result=self.node('const result=await beforeCompact(event,ctx,{timeoutMs:1000,emit:()=>{throw new Error("sink failed")},request:()=>({action:"cancel"})});console.log(JSON.stringify(result));')
        self.assertEqual(result,dict(cancel=True))

    def test_verified_host_ticket_returns_custom_compaction(self):
        module=Path('integrations/runtimes/pi_context_boundary.mjs').resolve().as_uri()
        code=f'import {{beforeCompact,sealTicket}} from {json.dumps(module)};'+'''const events=[];const ctx={sessionManager:{getSessionId:()=> 'native',getSessionFile:()=> '/private/session.jsonl',getLeafId:()=> 'a',getBranch:()=>[{id:'a'}]}};const result=await beforeCompact({signal:new AbortController().signal},ctx,{timeoutMs:1000,emit:e=>events.push(e),request:cursor=>{const ticket=sealTicket({schema:'asr-installation-ticket/1',ticket_id:'ticket',boundary_id:cursor.observation_id,native_session_id:'native',source_cursor:cursor,compaction:{summary:'reviewed',firstKeptEntryId:'a',tokensBefore:10,details:{asr_installation_ticket:'ticket'}}});return {action:'install',status:'authorized',installation_authorized:true,ticket};}});console.log(JSON.stringify({result,events}));'''
        result=subprocess.run(['node','--input-type=module','-e',code],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        record=json.loads(result.stdout);self.assertEqual(record['result']['compaction']['summary'],'reviewed')
        self.assertEqual(record['events'][-1]['action'],'install')
