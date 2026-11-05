/** Read-only runtime cursor observation; never an installation permission. */
import {createHash,randomUUID} from 'node:crypto';
import {isAbsolute} from 'node:path';

let observationSequence=0;
export function captureCursor(ctx) {
  const base={type:'asr_context_cursor',schema:'asr-pi-cursor/1',observation_id:randomUUID(),
    observed_at:new Date().toISOString(),observation_sequence:++observationSequence,installation_authorized:false,provider_payload_verified:false};
  try {
    const manager=ctx?.sessionManager;
    if(!manager)throw new Error('native_session_manager_unavailable');
    const session=manager.getSessionId(),file=manager.getSessionFile(),leaf=manager.getLeafId();
    if(typeof session!=='string'||!session||typeof file!=='string'||!isAbsolute(file)||typeof leaf!=='string'||!leaf)
      throw new Error('native_cursor_unavailable');
    const branch=manager.getBranch(leaf),ids=branch.map(entry=>entry.id);
    if(!ids.length||ids.at(-1)!==leaf||ids.some(id=>typeof id!=='string'||!id)||new Set(ids).size!==ids.length)
      throw new Error('native_branch_invalid');
    if(manager.getSessionId()!==session||manager.getSessionFile()!==file||manager.getLeafId()!==leaf)
      throw new Error('native_cursor_changed');
    return {...base,status:'observed',native_session_id:session,journal_file:file,leaf_id:leaf,
      branch_entries:ids.length,branch_ids_sha256:createHash('sha256').update(JSON.stringify(ids)).digest('hex')};
  } catch(error) {
    const reasons=new Set(['native_session_manager_unavailable','native_cursor_unavailable','native_branch_invalid','native_cursor_changed']);
    return {...base,status:'deferred',reason:reasons.has(error?.message)?error.message:'native_cursor_read_failed',
      recovery:'Retain the native journal; retry capture at a stable runtime boundary. This observation cannot authorize installation.'};
  }
}
