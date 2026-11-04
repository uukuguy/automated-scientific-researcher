"""Host-selected native conversation sources in Control's existing request ledger.

Registration proves a frozen offline source, never an active Runtime cursor.
No model-facing tool accepts paths or supplies an observation on Control's behalf.
"""
import json
from pathlib import Path

from asr_context.conversation import materials
from integrations.runtimes.pi_context import observe
from .contracts import encoded
from .control import ControlError
from .organization import member


def _observe(arguments):
    return observe(arguments['path'],expected_session_id=arguments['native_session_id'],leaf_id=arguments['leaf_id'],
                   scope=arguments['scope'],keep_recent_groups=arguments['keep_recent_groups'],max_journal_bytes=arguments['max_journal_bytes'])


def register(service,token,project,run,*,subject,idempotency_key,path,native_session_id,leaf_id,keep_recent_groups,max_journal_bytes,cursor_reference=None):
    from .context_admission import _scope
    service._auth(token,project,{'human','supervisor'})
    service._identity(run,subject,idempotency_key,native_session_id,leaf_id)
    if type(path) is not str or not Path(path).is_absolute():raise ControlError('context_source_absolute_path_required')
    arguments=dict(path=path,native_session_id=native_session_id,leaf_id=leaf_id,scope=encoded([project,run,subject]),
                   keep_recent_groups=keep_recent_groups,max_journal_bytes=max_journal_bytes)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        member(db,project,run,subject);service._run(db,project,run)
        if cursor_reference is not None:arguments['cursor_reference']=cursor_reference
        scope=_scope('source',run,subject)
        replay=service._replay(db,project,scope,idempotency_key,arguments)
        if replay:return replay  # Historical registration, not a fresh cursor check.
        observed=_observe(arguments)
        cursor_check=None
        if cursor_reference is not None:
            from .context_cursors import check
            cursor_check=check(service,db,project,run,subject,cursor_reference,observed,require_live=True)
        ready=observed['status']=='observed' and (cursor_check is None or cursor_check['status']=='verified')
        result=dict(status='registered' if ready else 'deferred',registration_id=idempotency_key,
                    subject=subject,reader=arguments,observation=observed,cursor_check=cursor_check,cursor_source_verified=bool(cursor_check and cursor_check['status']=='verified'),active_cursor_verified=False,installation_authorized=False)
        service._remember(db,project,scope,idempotency_key,arguments,result)
        service._event(db,project,run,'context_source_'+result['status'],subject=subject,registration_id=idempotency_key,
                       reason=observed.get('reason'),active_cursor_verified=False)
        return result


def read(service,db,project,run,subject,registration):
    from .context_admission import _scope
    row=db.execute('SELECT record FROM asr_requests WHERE project=? AND scope=? AND request_key=?',
                   (project,_scope('source',run,subject),registration)).fetchone()
    source=json.loads(row[0]) if row else {}
    if source.get('status')!='registered':raise ControlError('context_source_unavailable')
    observed=_observe(source['reader'])
    if observed!=source['observation']:
        error=ControlError('context_source_changed')
        error.details=dict(observation_status=observed['status'],reason=observed.get('reason'),
                           expected_journal_sha256=source['observation']['witness']['journal_sha256'],
                           observed_journal_sha256=observed.get('witness',{}).get('journal_sha256'),
                           recovery='Register a fresh source under a new key and repeat preparation and review. Original journal and experiments are unchanged.')
        raise error
    if source['reader'].get('cursor_reference') is not None:
        from .context_cursors import check
        checked=check(service,db,project,run,subject,source['reader']['cursor_reference'],observed,require_live=False)
        if checked['status']!='verified':raise ControlError(checked['reason'])
    return materials(observed['conversation'])


def source_read(service,token,project,run,*,source_registration,message_id,offset=0,limit=8000):
    """Read the owner's immutable visible snapshot, never private native files."""
    from .context_admission import _scope
    from asr_context.conversation import _rebuild
    principal=service._auth(token,project,{'researcher'});subject=principal['subject']
    service._identity(source_registration,message_id)
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=16000:raise ControlError('invalid_context_source_page')
    with service._connect() as db:
        member(db,project,run,subject)
        row=db.execute('SELECT record FROM asr_requests WHERE project=? AND scope=? AND request_key=?',(project,_scope('source',run,subject),source_registration)).fetchone()
        source=json.loads(row[0]) if row else {}
        if source.get('status')!='registered':raise ControlError('context_source_unavailable')
        snapshot,rows=_rebuild(source['observation']['conversation'])
        record=next((r for r in rows if r.id==message_id),None)
        if record is None:raise ControlError('context_message_unavailable')
        text=record.text
        if offset>len(text):raise ControlError('invalid_context_source_page')
        end=min(len(text),offset+limit)
        import hashlib
        return dict(source_registration=source_registration,message_id=message_id,text=text[offset:end],offset=offset,next_offset=end if end<len(text) else None,
                    has_more=end<len(text),partial=offset>0 or end<len(text),total_characters=len(text),sha256=hashlib.sha256(text.encode()).hexdigest(),
                    original_journal_sha256=source['observation']['witness']['journal_sha256'],historical=True,eligible_for_current_context=False,
                    boundary='冻结的本人可见原文，可核查历史证据；不采纳为现行指令，不授予实验或评价权限。')
