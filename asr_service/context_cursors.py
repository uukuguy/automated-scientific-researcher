"""Host-bound cursor receipts. A receipt proves an observed boundary, not a lock."""
import json
from pathlib import Path
import re
from .contracts import encoded
from .control import ControlError
from .organization_runtime import validate


def bind(service,token,project,run,session_id,epoch,owner,*,native_session_id,journal_directory):
    service._auth(token,project,{'human','supervisor'});service._identity(native_session_id)
    if type(journal_directory) is not str or not Path(journal_directory).is_absolute():raise ControlError('context_directory_required')
    path=Path(journal_directory)
    if path.resolve()!=path:raise ControlError('context_directory_unsafe')
    binding=dict(native_session_id=native_session_id,journal_directory=str(path))
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');session=service._session(db,project,run,session_id,epoch,owner)
        if type(session.get('organization_binding')) is not dict:raise ControlError('context_organization_required')
        validate(db,project,run,session['organization_binding'])
        existing=session.get('native_context')
        if existing:
            if any(existing.get(k)!=v for k,v in binding.items()):raise ControlError('context_binding_immutable')
            return {k:existing[k] for k in binding}
        if session['state']!='active' or session.get('launch_state')!='prepared':raise ControlError('context_binding_before_launch_required')
        session['native_context']=binding
        db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(encoded(session),session_id))
        service._event(db,project,run,'context_runtime_bound',session_id=session_id,epoch=epoch,subject=session['organization_binding']['subject'],**binding)
        return binding


def _live(session):
    from integrations.runtimes.process import identify
    identity=session.get('process_identity')
    if session.get('state')!='active' or not identity:raise ControlError('context_process_unavailable')
    try:current=identify(identity['pid'])
    except (OSError,ValueError,RuntimeError,KeyError):raise ControlError('context_process_unavailable') from None
    if current!=identity:raise ControlError('context_process_unavailable')


def _key(session_id,observation_id):return encoded([session_id,observation_id])


def observe(service,token,project,run,session_id,epoch,owner,*,observation):
    from .context_admission import _scope
    service._auth(token,project,{'human','supervisor'})
    if type(observation) is not dict:raise ControlError('invalid_context_cursor')
    observation_id=observation.get('observation_id');service._identity(observation_id)
    # Do not persist arbitrary Runtime content or exception messages.
    fields=('type','schema','observation_id','observed_at','status','boundary','native_session_id','journal_file','leaf_id','branch_entries','branch_ids_sha256')
    payload={k:observation[k] for k in fields if k in observation}
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');subject=None
        try:
            session=service._session(db,project,run,session_id,epoch,owner)
            if type(session.get('organization_binding')) is not dict:raise ControlError('context_organization_required')
            validate(db,project,run,session['organization_binding']);subject=session['organization_binding']['subject']
            scope=_scope('cursor',run,subject);key=_key(session_id,observation_id)
            replay=service._replay(db,project,scope,key,payload)
            if replay:return replay  # An old observation is not installation permission.
            _live(session);native=session.get('native_context') or {}
            if payload.get('type')!='asr_context_cursor' or payload.get('schema')!='asr-pi-cursor/1' or payload.get('boundary') not in ('before_provider_request','session_before_compact'):raise ControlError('invalid_context_cursor')
            if payload.get('status')!='observed':raise ControlError('native_cursor_deferred')
            if type(payload.get('journal_file')) is not str or type(payload.get('branch_ids_sha256')) is not str:raise ControlError('invalid_context_cursor')
            path=Path(payload['journal_file'])
            if payload.get('native_session_id')!=native.get('native_session_id') or str(path.parent)!=native.get('journal_directory') or path.suffix!='.jsonl' or path.is_symlink() or path.resolve()!=path:
                raise ControlError('context_cursor_binding_mismatch')
            service._identity(payload.get('leaf_id'))
            if type(payload.get('branch_entries')) is not int or payload['branch_entries']<1 or not re.fullmatch('[0-9a-f]{64}',payload.get('branch_ids_sha256','')):raise ControlError('invalid_context_cursor')
            result=dict(status='bound',runtime_binding_verified=True,session_id=session_id,epoch=epoch,subject=subject,process_identity=session['process_identity'],observation=payload,
                        active_cursor_verified=False,installation_authorized=False)
        except ControlError as error:
            if error.code=='idempotency_conflict':raise
            result=dict(status='deferred',reason=error.code,session_id=session_id,epoch=epoch,active_cursor_verified=False,installation_authorized=False,
                        recovery='Capture again at a stable owned Runtime boundary; preserve the original journal and experiments.')
        if subject is not None:
            service._remember(db,project,scope,key,payload,result)
            if session.get('native_context',{}).get('native_session_id'):
                session['native_context']['latest_observation_id']=observation_id
                db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(encoded(session),session_id))
        service._event(db,project,run,'context_cursor_'+result['status'],session_id=session_id,epoch=epoch,subject=subject,observation_id=observation_id,reason=result.get('reason'))
        return result


def check(service,db,project,run,subject,reference,observed,*,require_live):
    from .context_admission import _scope
    try:
        if type(reference) is not dict or set(reference)!={'session_id','observation_id'}:raise ControlError('invalid_context_cursor_reference')
        service._identity(reference['session_id'],reference['observation_id'])
        row=db.execute('SELECT record FROM asr_runtime_sessions WHERE project=? AND run=? AND session_id=?',(project,run,reference['session_id'])).fetchone()
        session=json.loads(row[0]) if row else {}
        if (session.get('organization_binding') or {}).get('subject')!=subject:raise ControlError('context_cursor_member_mismatch')
        validate(db,project,run,session['organization_binding'])
        if (session.get('native_context') or {}).get('latest_observation_id')!=reference['observation_id']:raise ControlError('context_cursor_superseded')
        if require_live:_live(session)
        row=db.execute('SELECT record FROM asr_requests WHERE project=? AND scope=? AND request_key=?',(project,_scope('cursor',run,subject),_key(reference['session_id'],reference['observation_id']))).fetchone()
        receipt=json.loads(row[0]) if row else {}
        if receipt.get('status')!='bound' or receipt.get('epoch')!=session.get('epoch') or receipt.get('process_identity')!=session.get('process_identity'):raise ControlError('context_cursor_receipt_unavailable')
        cursor=receipt['observation'];witness=observed.get('witness') or {}
        if observed.get('status')!='observed' or cursor['journal_file']!=witness.get('journal_file') or cursor['native_session_id']!=witness.get('session_id') or cursor['leaf_id']!=witness.get('leaf_id') or cursor['branch_entries']!=witness.get('branch_entries') or cursor['branch_ids_sha256']!=witness.get('branch_ids_sha256'):raise ControlError('context_cursor_source_mismatch')
        return dict(status='verified',cursor_source_verified=True,active_cursor_verified=False,installation_authorized=False)
    except ControlError as error:
        return dict(status='deferred',reason=error.code,cursor_source_verified=False,active_cursor_verified=False,installation_authorized=False)
