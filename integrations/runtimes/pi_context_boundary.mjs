/** Synchronous compaction handshake. No fallback summary or installation yet. */
import {captureCursor} from './pi_context_cursor.mjs';

export async function beforeCompact(event,ctx,{request,emit,timeoutMs}) {
  const began=performance.now();
  const cursor={...captureCursor(ctx),boundary:'session_before_compact'};
  const base={type:'asr_context_boundary',boundary_id:cursor.observation_id,
    installation_authorized:false,context_installed:false,reason:'context_installation_not_ready'};
  const record=value=>{try{emit({...base,...value});}catch{/* Cancellation still preserves the native journal. */}};
  let reason='context_installation_not_ready',timer,onAbort;
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
    // Installation needs a separately verified reviewed bundle and post-write
    // receipt. A bridge flag or an arbitrary reply cannot supply that authority.
    if(result.reply?.action==='cancel'&&typeof result.reply.reason==='string'&&/^[a-z0-9_]{1,96}$/.test(result.reply.reason))reason=result.reply.reason;
    return {cancel:true};
  } catch {reason='boundary_request_failed';return {cancel:true};}
  finally {
    clearTimeout(timer);if(onAbort)event?.signal?.removeEventListener('abort',onAbort);
    controller.abort();record({phase:'released',action:'cancel',reason,original_context_preserved:true,
      limit_ms:Number.isSafeInteger(timeoutMs)?timeoutMs:null,elapsed_ms:Math.ceil(performance.now()-began),recoverable:true,
      recovery:'Retain the original journal; prepare and review the context, then retry at a fresh owned boundary. Do not repeat experiments.'});
  }
}
