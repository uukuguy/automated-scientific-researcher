/** Curated pi extension. No discovered skills, extensions, provider switching or Bash. */
export default function(pi) {
  let turns = 0, tools = 0;
  const maxTurns = Number(process.env.ASR_MAX_TURNS);
  const maxTools = Number(process.env.ASR_MAX_TOOLS);
  const deadline = Number(process.env.ASR_DEADLINE_MS);
  const endpoint = process.env.ASR_BRIDGE_URL;
  const token = process.env.ASR_BRIDGE_TOKEN;
  const fatal = () => process.exit(75);
  async function bridge(operation, arguments_, key) {
    if (!(Date.now() < deadline)) fatal();
    const response = await fetch(endpoint, {
      method: 'POST', headers: {'Content-Type':'application/json', 'Authorization':`Bearer ${token}`},
      body: JSON.stringify({operation, arguments: arguments_, key}),
      signal: AbortSignal.timeout(Math.max(1,Math.min(10000,deadline-Date.now())))
    });
    if (!response.ok) throw new Error('asr_bridge_rejected');
    return await response.json();
  }
  pi.on('before_provider_request', async () => {
    try {
      if (++turns > maxTurns) fatal();
      await bridge('permit', {kind:'turn'}, crypto.randomUUID());
    } catch { fatal(); } // pi swallows hook exceptions: process exit is intentional.
  });
  pi.on('tool_call', async event => {
    try {
      if (++tools > maxTools || event.toolName !== 'asr') fatal();
      await bridge('permit', {kind:'tool_execution'}, event.toolCallId);
    } catch { fatal(); }
  });
  pi.registerTool({
    name:'asr', label:'ASR research service',
    description:'Read effective contract, guidance, budgets, trials and shared findings with state; submit_trial; publish_finding with completed trial evidence; snapshot workspace. Returns actual service receipts. Use a stable request key on retry; do not repeat accepted numerical work.',
    parameters:{type:'object',properties:{operation:{type:'string',enum:['state','submit_trial','publish_finding','snapshot']},arguments:{type:'object',additionalProperties:true},key:{type:'string'}},required:['operation','arguments','key'],additionalProperties:false},
    async execute(callId, args) {
      const result = await bridge(args.operation,args.arguments,args.key);
      return {content:[{type:'text',text:JSON.stringify(result)}],details:result};
    }
  });
}
