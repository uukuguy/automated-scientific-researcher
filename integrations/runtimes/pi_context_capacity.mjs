/** Pinned SDK estimate only. Never logs request content or certifies admission. */
import {randomUUID} from 'node:crypto';

export function captureCapacity(ctx,cursor) {
  const began=performance.now();
  const base={type:'asr_context_capacity',schema:'asr-pi-context-capacity/1',
    observation_id:randomUUID(),observed_at:new Date().toISOString(),boundary:'before_provider_request',
    measurement:'estimate',unit:'tokens',window_source:'pinned_sdk_getContextUsage',
    full_next_request_verified:false,provider_payload_verified:false,
    used_tokens:null,window_tokens:null};
  const finish=value=>({...base,...value,measurement_elapsed_ms:Math.ceil(performance.now()-began)});
  if(cursor?.status!=='observed')return finish({status:'deferred',reason:'native_cursor_unavailable'});
  try {
    if(typeof ctx?.getContextUsage!=='function')return finish({status:'deferred',reason:'native_usage_unavailable'});
    const usage=ctx.getContextUsage();
    if(usage===undefined||usage===null)return finish({status:'deferred',reason:'native_usage_unavailable'});
    if(!Number.isSafeInteger(usage.contextWindow)||usage.contextWindow<=0||
      (usage.tokens!==null&&(!Number.isSafeInteger(usage.tokens)||usage.tokens<0)))
      return finish({status:'deferred',reason:'invalid_native_usage'});
    const manager=ctx.sessionManager;
    if(manager?.getSessionId()!==cursor.native_session_id||manager?.getLeafId()!==cursor.leaf_id||manager?.getSessionFile()!==cursor.journal_file)
      return finish({status:'deferred',reason:'native_usage_view_changed'});
    return finish({status:'observed',native_session_id:cursor.native_session_id,leaf_id:cursor.leaf_id,
      used_tokens:usage.tokens,window_tokens:usage.contextWindow,
      ...(usage.tokens===null?{reason:'native_usage_unknown'}:{})});
  } catch {return finish({status:'deferred',reason:'native_usage_read_failed'});}
}
