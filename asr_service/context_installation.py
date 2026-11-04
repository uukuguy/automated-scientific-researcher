"""One-use context installation, recomputed at the owned synchronous boundary."""
import hashlib
import json
from pathlib import Path
import uuid
from asr_context import material_digest,_encode
from asr_context.conversation import materials
from asr_context.installation import compile_plan
from asr_context.application import plan as application_plan
from asr_context.summary import _digest
from .contracts import encoded
from .control import ControlError
from .context_admission import _scope,snapshot,_session
from .context_cursors import _live,check as cursor_check
from .organization_runtime import validate
from .context_sources import _observe


def _record(db,project,scope,key):
    row=db.execute('SELECT record,payload FROM asr_requests WHERE project=? AND scope=? AND request_key=?',(project,scope,key)).fetchone()
    if not row:raise ControlError('context_record_unavailable')
    return json.loads(row[0]),json.loads(row[1])


def _native_replay(observed,first_kept_entry_id):
    if observed.get('adapter')!='pi-session-projection/1':return ()
    snapshot=observed['conversation'];systems=[r['id'] for r in snapshot['body']['messages'] if r['role']=='system']
    if not systems:return ()
    key=systems[-1]
    mapping=observed['witness']['source_mapping']
    cut=next((i for i,m in enumerate(mapping) if m['native_entry_id']==first_kept_entry_id),0)
    if key not in {r['id'] for r in snapshot['body']['messages'][:cut]}:return ()
    return (key,) if any(g['ids']==[key] for g in snapshot['groups']) else ()


def stage(service,token,project,run,*,subject,admission_id,first_kept_entry_id,idempotency_key):
    service._auth(token,project,{'human','supervisor'});service._identity(subject,admission_id,first_kept_entry_id,idempotency_key)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');scope=_scope('installation',run,subject);payload=[admission_id,first_kept_entry_id]
        replay=service._replay(db,project,scope,idempotency_key,payload)
        if replay:return replay
        admission,bundle=_record(db,project,_scope('admission',run,subject),admission_id)
        if admission['status']!='admitted':raise ControlError('context_admission_required')
        prepared,_=_record(db,project,_scope('prepare',run,subject),admission['preparation_id'])
        source_id=prepared.get('source_registration')
        if not source_id:raise ControlError('context_conversation_source_required')
        source,_=_record(db,project,_scope('source',run,subject),source_id)
        snapshot(service,db,project,run,subject,source_id)  # Re-read exact originals at staging.
        request,candidate,review_request,review,author,reviewer=bundle[2:]
        compiled=compile_plan(source['observation'],request,candidate,review_request,review,author_session=author,reviewer_session=reviewer,first_kept_entry_id=first_kept_entry_id,native_replay_ids=_native_replay(source['observation'],first_kept_entry_id))
        if compiled['status']!='installation_plan':raise ControlError(compiled.get('reason','context_coverage_required'))
        result=dict(status='staged',stage_id=idempotency_key,subject=subject,preparation=prepared,reader=source['reader'],bundle=bundle,plan=compiled,installation_authorized=False)
        service._remember(db,project,scope,idempotency_key,payload,result);service._event(db,project,run,'context_installation_staged',subject=subject,stage_id=idempotency_key,plan_sha256=compiled['plan_sha256'])
        return result


def authorize(service,token,project,run,session_id,epoch,owner,*,stage_id,observation,tokens_before):
    service._auth(token,project,{'human','supervisor'});service._identity(stage_id,observation.get('observation_id'))
    if type(tokens_before) is not int or tokens_before<0:raise ControlError('context_token_measurement_required')
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');session=service._session(db,project,run,session_id,epoch,owner);_live(session)
        validate(db,project,run,session.get('organization_binding'));subject=session['organization_binding']['subject']
        scope=_scope('ticket',run,subject);key=observation['observation_id'];payload=[session_id,epoch,owner,stage_id,observation,tokens_before]
        replay=service._replay(db,project,scope,key,payload)
        if replay:return replay
        staged,_=_record(db,project,_scope('installation',run,subject),stage_id)
        for row in db.execute('SELECT record FROM asr_requests WHERE project=? AND scope=?',(project,scope)):
            if json.loads(row[0]).get('ticket',{}).get('stage_id')==stage_id:raise ControlError('context_stage_already_used')
        if session.get('native_context',{}).get('pending_installation'):raise ControlError('context_installation_pending')
        active_reader=dict(staged['reader'],leaf_id=observation['leaf_id'])
        observed=_observe(active_reader)
        checked=cursor_check(service,db,project,run,subject,dict(session_id=session_id,observation_id=key),observed,require_live=True)
        if checked['status']!='verified':raise ControlError(checked['reason'])
        request,candidate,review_request,review,author,reviewer=staged['bundle'][2:]
        _session(db,project,run,author,subject);_session(db,project,run,reviewer,staged['preparation']['reviewer_subject'])
        compiled=compile_plan(observed,request,candidate,review_request,review,author_session=author,reviewer_session=reviewer,first_kept_entry_id=staged['plan']['first_kept_entry_id'],native_replay_ids=tuple(r['id'] for r in staged['plan'].get('native_replayed_messages',[])))
        if compiled['status']!='installation_plan':raise ControlError(compiled.get('reason','context_coverage_required'))
        current_materials,stamp=snapshot(service,db,project,run,subject)
        current_materials.extend(materials(observed['conversation']));stamp['source_fingerprints']={m.id:material_digest(m) for m in current_materials}
        app=application_plan(request,candidate,review_request,review,author_session=author,reviewer_session=reviewer,expected_state=staged['preparation']['state_stamp'],current_state=stamp)
        if app['status']!='admission_required':raise ControlError(app.get('reason','context_state_changed'))
        ticket_id='install_'+uuid.uuid4().hex
        envelope=json.loads(compiled['summary']);envelope['installation_id']=ticket_id
        envelope['source_registration']=staged['preparation']['source_registration']
        envelope['source_retrieval']='asr.research_note conversation_read'
        summary=_encode(envelope).decode()
        compaction=dict(summary=summary,firstKeptEntryId=compiled['first_kept_entry_id'],tokensBefore=tokens_before,details=dict(asr_installation_ticket=ticket_id))
        raw=Path(active_reader['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=observed['witness']['journal_sha256']:raise ControlError('context_source_changed')
        ticket=dict(schema='asr-installation-ticket/1',ticket_id=ticket_id,stage_id=stage_id,boundary_id=key,session_id=session_id,epoch=epoch,owner=owner,
                    native_session_id=observation['native_session_id'],source_cursor=observation,compaction=compaction,summary_sha256=hashlib.sha256(summary.encode()).hexdigest(),
                    before_journal_sha256=hashlib.sha256(raw).hexdigest(),before_journal_bytes=len(raw),plan=compiled,reader=active_reader,state_stamp=stamp,state_sha256=_digest(stamp))
        ticket['ticket_sha256']=_digest(ticket)
        result=dict(status='authorized',action='install',installation_authorized=True,context_installed=False,ticket=ticket)
        session['native_context']['pending_installation']=dict(boundary_id=key,ticket_id=ticket_id)
        db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(encoded(session),session_id))
        service._remember(db,project,scope,key,payload,result);service._event(db,project,run,'context_installation_authorized',subject=subject,session_id=session_id,ticket_id=ticket_id,boundary_id=key,source_sha256=observed['conversation']['sha256'])
        return result


def complete(service,token,project,run,session_id,epoch,owner,*,boundary_id,ticket_id,entry_id,idempotency_key):
    service._auth(token,project,{'human','supervisor'});service._identity(boundary_id,ticket_id,entry_id,idempotency_key)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');session=service._session(db,project,run,session_id,epoch,owner);_live(session)
        subject=session['organization_binding']['subject'];validate(db,project,run,session['organization_binding'])
        scope=_scope('installed',run,subject);payload=[session_id,epoch,owner,boundary_id,ticket_id,entry_id]
        replay=service._replay(db,project,scope,idempotency_key,payload)
        if replay:return replay
        authorized,_=_record(db,project,_scope('ticket',run,subject),boundary_id);ticket=authorized['ticket']
        native_write_observed=False
        try:
            if ticket['ticket_id']!=ticket_id or ticket['session_id']!=session_id or ticket['epoch']!=epoch or ticket['owner']!=owner:raise ControlError('context_ticket_binding_mismatch')
            if session['native_context'].get('pending_installation')!=dict(boundary_id=boundary_id,ticket_id=ticket_id):raise ControlError('context_installation_not_pending')
            path=Path(ticket['reader']['path']);raw=path.read_bytes()
            if len(raw)<ticket['before_journal_bytes'] or hashlib.sha256(raw[:ticket['before_journal_bytes']]).hexdigest()!=ticket['before_journal_sha256']:raise ControlError('context_original_journal_changed')
            records=[json.loads(line) for line in raw.splitlines() if line.strip()];entry=next((r for r in records if r.get('id')==entry_id),{})
            expected=ticket['compaction']
            if entry.get('type')!='compaction' or entry.get('parentId')!=ticket['source_cursor']['leaf_id'] or entry.get('fromHook') is not True or any(entry.get(k)!=expected[k] for k in ('summary','firstKeptEntryId','tokensBefore','details')):raise ControlError('context_native_entry_mismatch')
            native_write_observed=True
            reader=dict(ticket['reader'],leaf_id=entry_id);observed=_observe(reader)
            if observed['status']!='observed':raise ControlError('context_projection_unavailable')
            old=_record(db,project,_scope('installation',run,subject),ticket['stage_id'])[0]['preparation']
            frozen={m['id']:m for m in old['materials']};actual={r['id']:r for r in observed['conversation']['body']['messages']}
            retained=ticket['plan']['coverage']['retained_ids']
            # Original message revisions include calls and flags, not just prose.
            current={m.id:m for m in materials(observed['conversation'])}
            for key in retained:
                if key not in current or current[key].revision!=frozen[key]['revision']:raise ControlError('context_retained_message_changed')
            for original in ticket['plan'].get('native_replayed_messages',[]):
                if not any(r['role']=='system' and r['text']==original['text'] for r in actual.values()):raise ControlError('context_native_system_replay_changed')
            if not any(json.loads(r['text']).get('content')==ticket['compaction']['summary'] for r in actual.values()):raise ControlError('context_summary_not_projected')
            fresh_materials,fresh_stamp=snapshot(service,db,project,run,subject)
            fresh_stamp['source_fingerprints']=dict(ticket['state_stamp']['source_fingerprints'])
            fresh_stamp['source_fingerprints'].update({m.id:material_digest(m) for m in fresh_materials})
            if _digest(fresh_stamp)!=ticket['state_sha256']:raise ControlError('context_research_state_changed_after_write')
            result=dict(status='verified',context_installed=True,native_write_observed=True,installation_authorized=False,ticket_id=ticket_id,entry_id=entry_id,
                        original_journal_preserved=True,retained_ids=retained,projection_sha256=observed['witness']['projection_sha256'],after_journal_sha256=observed['witness']['journal_sha256'],provider_payload_verified=False)
            session['native_context'].pop('pending_installation');session['native_context']['installed_context']=result
            db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(encoded(session),session_id))
        except (ControlError,ValueError,OSError) as error:
            result=dict(status='deferred',context_installed=False,native_write_observed=native_write_observed,installation_authorized=False,ticket_id=ticket_id,reason=getattr(error,'code','context_verification_failed'),recovery='Preserve journal and ticket; verify before another provider request. Do not repeat experiments.')
        service._remember(db,project,scope,idempotency_key,payload,result);service._event(db,project,run,'context_installation_'+result['status'],session_id=session_id,ticket_id=ticket_id,entry_id=entry_id,reason=result.get('reason'))
        return result
