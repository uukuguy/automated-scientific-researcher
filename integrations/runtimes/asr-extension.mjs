/** Curated pi extension. No discovered skills, extensions, provider switching or Bash. */
import { workspacePath } from './workspace-path.mjs';
export default function(pi) {
  let turns = 0, tools = 0;
  const maxTurns = Number(process.env.ASR_MAX_TURNS);
  const maxTools = Number(process.env.ASR_MAX_TOOLS);
  const deadline = Number(process.env.ASR_DEADLINE_MS);
  const endpoint = process.env.ASR_BRIDGE_URL;
  const token = process.env.ASR_BRIDGE_TOKEN;
  const fatal = () => process.exit(75);
  const watchdog=setTimeout(() => {
    if(process.env.ASR_OWNED_PROCESS_GROUP==='1') process.kill(-process.pid,'SIGKILL');
    else fatal();
  },Math.max(1,deadline-Date.now()));
  watchdog.unref();
  async function bridge(operation, arguments_, key) {
    if (!(Date.now() < deadline)) fatal();
    const response = await fetch(endpoint, {
      method: 'POST', headers: {'Content-Type':'application/json', 'Authorization':`Bearer ${token}`},
      body: JSON.stringify({operation, arguments: arguments_, key}),
      signal: AbortSignal.timeout(Math.max(1,Math.min(10000,deadline-Date.now())))
    });
    const data=await response.json();
    if (!response.ok && operation==='permit') throw new Error('asr_permit_rejected');
    return data;
  }
  pi.on('before_provider_request', async () => {
    try {
      if (++turns > maxTurns) fatal();
      await bridge('permit', {kind:'turn'}, crypto.randomUUID());
    } catch { fatal(); } // pi swallows hook exceptions: process exit is intentional.
  });
  pi.on('tool_call', async event => {
    try {
      if (++tools > maxTools) fatal();
      if (!['asr','read','write','edit','grep','find','ls'].includes(event.toolName)) fatal();
      await bridge('permit', {kind:'tool_execution'}, event.toolCallId);
      if(event.toolName!=='asr') {
        try { const input=event.input.path || '.';
          const safe=(event.toolName==='read' && input===process.env.ASR_SKILL_PATH) ? process.env.ASR_SKILL_PATH : workspacePath(process.env.ASR_WORKSPACE,input,event.toolName); event.input.path=safe; return; }
        catch { return {block:true,reason:'Only ordinary ASCII paths inside the research workspace are allowed; symlinks and metadata paths are forbidden.'}; }
      }
    } catch { fatal(); }
  });
  pi.registerTool({
    name:'asr', label:'ASR research service',
    description:`Read effective contract, guidance, budgets, trials and shared findings with state; submit_trial; publish_finding with completed trial evidence; snapshot workspace with arguments {paths:['research-note.md']}; ack_guidance {command_id,status:'delivered'|'adopted'|'deferred',reason}. publish_finding requires {finding_id,expected_revision,statement,trial_ids,limitations}; submit_trial requires {variables,references,requested_budget}. Returns actual service receipts. Use a stable request key on retry; do not repeat accepted numerical work.`,
    parameters:{type:'object',properties:{operation:{type:'string',enum:['state','submit_trial','publish_finding','snapshot','ack_guidance']},arguments:{type:'object',description:'Operation arguments: state {}; snapshot {paths:[relative file names]}; ack_guidance {command_id,status,reason}; submit_trial {variables,references,requested_budget}; publish_finding {finding_id,expected_revision,statement,trial_ids,limitations}.',additionalProperties:true},key:{type:'string'}},required:['operation','arguments','key'],additionalProperties:false},
    async execute(callId, args) {
      const result = await bridge(args.operation,args.arguments,args.key);
      return {content:[{type:'text',text:JSON.stringify(result)}],details:result,isError:Boolean(result.error)};
    }
  });
}
