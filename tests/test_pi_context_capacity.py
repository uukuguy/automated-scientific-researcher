import json
from pathlib import Path
import subprocess
import unittest


class PiContextCapacityTests(unittest.TestCase):
    def capture(self,usage,*,getter=None):
        module=Path('integrations/runtimes/pi_context_capacity.mjs').resolve().as_uri()
        function=getter or '()=>('+json.dumps(usage)+')'
        script=f'''import {{captureCapacity}} from {json.dumps(module)};
const cursor={{status:'observed',native_session_id:'native',leaf_id:'leaf',journal_file:'/private/session.jsonl'}};
const ctx={{getContextUsage:{function},sessionManager:{{getSessionId:()=> 'native',getLeafId:()=> 'leaf',getSessionFile:()=> '/private/session.jsonl'}}}};
console.log(JSON.stringify(captureCapacity(ctx,cursor)));'''
        result=subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_native_estimate_is_observation_only_and_never_certifies_request(self):
        result=self.capture(dict(tokens=650,contextWindow=1000,percent=65))
        self.assertEqual(result['used_tokens'],650)
        self.assertEqual(result['window_tokens'],1000)
        self.assertEqual(result['measurement'],'estimate')
        self.assertFalse(result['full_next_request_verified'])
        self.assertFalse(result['provider_payload_verified'])
        self.assertEqual(result['window_source'],'pinned_sdk_getContextUsage')

    def test_unknown_after_compaction_is_not_replaced_by_previous_usage(self):
        result=self.capture(dict(tokens=None,contextWindow=1000,percent=None))
        self.assertIsNone(result['used_tokens'])
        self.assertEqual(result['reason'],'native_usage_unknown')

    def test_missing_or_failed_getter_has_explicit_reason_without_private_text(self):
        result=self.capture(None,getter="()=>{throw new Error('private prompt and credentials')}")
        self.assertEqual(result['reason'],'native_usage_read_failed')
        self.assertNotIn('private prompt',json.dumps(result))
        self.assertIsNone(result['used_tokens'])

    def test_invalid_fractional_counts_are_not_rounded_into_proof(self):
        result=self.capture(dict(tokens=1.5,contextWindow=1000))
        self.assertEqual(result['reason'],'invalid_native_usage')
        self.assertIsNone(result['used_tokens'])

    def test_installed_pinned_sdk_marks_usage_unknown_after_compaction(self):
        import shutil
        binary=shutil.which('pi')
        if not binary:self.skipTest('pinned pi SDK unavailable')
        index=Path(binary).resolve().parents[1]/'index.js'
        package=json.loads((index.parent.parent/'package.json').read_text())
        if package['version']!='1.5.0':self.skipTest('pi SDK version mismatch')
        module=Path('integrations/runtimes/pi_context_capacity.mjs').resolve().as_uri()
        script=f'''import {{AgentSession}} from {json.dumps(index.as_uri())};
import {{captureCapacity}} from {json.dumps(module)};
const manager={{getSessionId:()=> 'native',getLeafId:()=> 'c',getSessionFile:()=> '/private/session.jsonl',
 buildSessionProjection:()=>({{entries:[]}}),getBranch:()=>[{{type:'compaction',id:'c'}}]}};
const owner={{_limitsModel:()=>({{contextWindow:1000}}),sessionManager:manager}};
const ctx={{sessionManager:manager,getContextUsage:()=>AgentSession.prototype.getContextUsage.call(owner)}};
console.log(JSON.stringify(captureCapacity(ctx,{{status:'observed',native_session_id:'native',leaf_id:'c',journal_file:'/private/session.jsonl'}})));'''
        result=subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        observation=json.loads(result.stdout)
        self.assertIsNone(observation['used_tokens'])
        self.assertEqual(observation['window_tokens'],1000)
        self.assertEqual(observation['reason'],'native_usage_unknown')

    def test_cursor_change_during_measurement_defers_without_using_stale_count(self):
        result=self.capture(None,getter="()=>{ctx.sessionManager.getLeafId=()=> 'changed';return {tokens:500,contextWindow:1000};}")
        self.assertEqual(result['reason'],'native_usage_view_changed')
        self.assertIsNone(result['used_tokens'])

    def test_request_hook_emits_estimate_without_copying_provider_payload(self):
        import os,time
        module=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        script=f'''import extension from {json.dumps(module)};
const handlers={{}},events=[];let measurements=0;
globalThis.fetch=async()=>({{ok:true,json:async()=>({{activity_id:'fixture-permit'}})}});
extension({{on:(k,v)=>handlers[k]=v,registerTool:()=>{{}}}});
const ctx={{getContextUsage:()=>{{measurements++;return {{tokens:700,contextWindow:1000}}}},
 sessionManager:{{getSessionId:()=> 'native',getSessionFile:()=> '/private/session.jsonl',getLeafId:()=> 'leaf',getBranch:()=>[{{id:'leaf'}}]}},
 ui:{{notify:value=>events.push(value)}}}};
await handlers.before_provider_request({{payload:{{private_reasoning:'never-log-this'}}}},ctx);
console.log(JSON.stringify({{measurements,events}}));process.exit(0);'''
        env=dict(os.environ,ASR_CONTEXT_OBSERVATION='1',ASR_MAX_TURNS='10',ASR_MAX_TOOLS='10',ASR_DEADLINE_MS=str(int((time.time()+30)*1000)))
        result=subprocess.run(['node','--input-type=module','-e',script],env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        observed=json.loads(result.stdout)
        self.assertEqual(observed['measurements'],1)
        self.assertNotIn('never-log-this',result.stdout)
        self.assertTrue(any('asr_context_capacity' in event for event in observed['events']))
