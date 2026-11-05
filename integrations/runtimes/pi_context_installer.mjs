/** Host-owned recovery installer: no agent, authentication or provider request. */
import {pathToFileURL} from 'node:url';
import {readFileSync} from 'node:fs';
import {createHash,randomUUID} from 'node:crypto';
import {createInterface} from 'node:readline';
const {SessionManager,buildSessionProjection,estimateTokens}=await import(pathToFileURL(process.argv[2]).href);
const manager=SessionManager.open(process.argv[3]);
const branch=manager.getBranch();
const cursor={type:'asr_context_cursor',schema:'asr-pi-cursor/1',status:'observed',
  observation_id:randomUUID(),observation_sequence:1,observed_at:new Date().toISOString(),
  boundary:'session_before_compact',native_session_id:manager.getSessionId(),
  journal_file:manager.getSessionFile(),leaf_id:manager.getLeafId(),branch_entries:branch.length,
  branch_ids_sha256:createHash('sha256').update(JSON.stringify(branch.map(x=>x.id))).digest('hex'),
  installation_authorized:false,provider_payload_verified:false};
const tokens_before_estimate=buildSessionProjection(branch).entries.flatMap(x=>x.messages).reduce((sum,message)=>sum+estimateTokens(message),0);
process.stdout.write(JSON.stringify({cursor,tokens_before_estimate,measurement:'estimate'})+'\n');
let installed=false;
for await(const line of createInterface({input:process.stdin})) {
  const command=JSON.parse(line);
  if(command.operation==='exit')break;
  if(command.operation!=='install'||installed)throw new Error('one_installation_required');
  const ticket=JSON.parse(readFileSync(command.authorization_path,'utf8')).receipt.ticket;
  if(ticket.source_cursor.leaf_id!==manager.getLeafId()||ticket.native_session_id!==manager.getSessionId())throw new Error('native_cursor_changed');
  const c=ticket.compaction;
  const entry=manager.appendCompaction(c.summary,c.firstKeptEntryId,c.tokensBefore,c.details,true);
  installed=true;process.stdout.write(JSON.stringify({entry_id:entry})+'\n');
}
