/** Synchronous compaction handshake. No fallback summary or installation yet. */
import {createHash} from 'node:crypto';
import {captureCursor} from './pi_context_cursor.mjs';

function canonical(v){return v===null||typeof v!=='object'?JSON.stringify(v):Array.isArray(v)?'['+v.map(canonical).join(',')+']':'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';}
const sha=value=>createHash('sha256').update(value).digest('hex');
export function sealTicket(value){const ticket=structuredClone(value);delete ticket.ticket_sha256;ticket.summary_sha256=sha(ticket.compaction.summary);return {...ticket,ticket_sha256:sha(canonical(ticket))};}

export async function beforeCompact(event,ctx,{request,emit,timeoutMs,onAuthorized=()=>{}}) {
  const began=performance.now();
  const cursor={...captureCursor(ctx),boundary:'session_before_compact'};
  const base={type:'asr_context_boundary',boundary_id:cursor.observation_id,
    installation_authorized:false,context_installed:false,reason:'context_installation_not_ready'};
  const record=value=>{try{emit({...base,...value});}catch{/* Cancellation still preserves the native journal. */}};
  let reason='context_installation_not_ready',action='cancel',timer,onAbort;
  const controller=new AbortController();
  record({phase:'entered',action:'hold',cursor_status:cursor.status});
  try {
    if(!Number.isSafeInteger(timeoutMs)||timeoutMs<=0){reason='invalid_boundary_timeout';return {cancel:true};}
    if(event?.signal?.aborted){reason='boundary_aborted';return {cancel:true};}
    if(cursor.status!=='observed'){reason='boundary_cursor_unavailable';return {cancel:true};}
    const timeout=new Promise(resolve=>{timer=setTimeout(()=>{resolve({kind:'boundary_timeout'});controller.abort();},timeoutMs);});
    const abort=new Promise(resolve=>{onAbort=()=>{resolve({kind:'boundary_aborted'});controller.abort();};event?.signal?.addEventListener('abort',onAbort,{once:true});});
    const host=Promise.resolve().then(()=>request(cursor,controller.signal)).then(reply=>({kind:'reply',reply}),()=>({kind:'boundary_request_failed'}));
    const result=await Promise.race([timeout,abort,host]);
    if(result.kind!=='reply'){reason=result.kind;return {cancel:true};}
    const after=captureCursor(ctx);
    if(after.status!=='observed'||['native_session_id','journal_file','leaf_id','branch_entries','branch_ids_sha256'].some(k=>cursor[k]!==after[k])) {
      reason='boundary_cursor_changed';return {cancel:true};
    }
    const reply=result.reply,ticket=reply?.ticket;
    if(reply?.action==='install'&&reply.status==='authorized'&&reply.installation_authorized===true&&ticket?.schema==='asr-installation-ticket/1') {
      const sealed=sealTicket(ticket),c=ticket.compaction;
      if(sealed.ticket_sha256!==ticket.ticket_sha256||sealed.summary_sha256!==ticket.summary_sha256||ticket.boundary_id!==cursor.observation_id||ticket.native_session_id!==cursor.native_session_id||
        ['native_session_id','journal_file','leaf_id','branch_entries','branch_ids_sha256'].some(k=>ticket.source_cursor?.[k]!==cursor[k])||
        typeof c.summary!=='string'||!c.summary||!Number.isSafeInteger(c.tokensBefore)||c.tokensBefore<0||c.details?.asr_installation_ticket!==ticket.ticket_id||
        !ctx.sessionManager.getBranch(cursor.leaf_id).some(e=>e.id===c.firstKeptEntryId)) {
        reason='invalid_installation_ticket';return {cancel:true};
      }
      onAuthorized(ticket);action='install';reason='reviewed_context_installation';
      return {compaction:c};
    }
    if(result.reply?.action==='cancel'&&typeof result.reply.reason==='string'&&/^[a-z0-9_]{1,96}$/.test(result.reply.reason))reason=result.reply.reason;
    return {cancel:true};
  } catch {reason='boundary_request_failed';return {cancel:true};}
  finally {
    clearTimeout(timer);if(onAbort)event?.signal?.removeEventListener('abort',onAbort);
    controller.abort();record({phase:'released',action,reason,installation_authorized:action==='install',original_context_preserved:action==='cancel',
      limit_ms:Number.isSafeInteger(timeoutMs)?timeoutMs:null,elapsed_ms:Math.ceil(performance.now()-began),recoverable:true,
      recovery:'Retain the original journal; prepare and review the context, then retry at a fresh owned boundary. Do not repeat experiments.'});
  }
}
