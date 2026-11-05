"""Host-only context preparation/admission using Control's existing ledger.

Admission records permission to proceed to an installer, not actual installation.
The model cannot supply its own current state or mark itself accepted.
"""
from dataclasses import asdict
import json

from asr_context import Material, material_digest
from asr_context.application import plan
from asr_context.notes import restore
from .contracts import encoded
from .control import ControlError
from .organization import member,current
from .research_notes import _materials
from .note_artifacts import resolve
from . import note_io


def _scope(phase,run,subject):
    return 'context-'+phase+':'+encoded([run,subject])


def snapshot(service,db,project,run,subject,source_registration=None,*,verified_source=None,verified_note=None):
    role=member(db,project,run,subject);state=service._run(db,project,run)
    if state['health']!='ok' or state['state'] not in ('running','paused'):raise ControlError('context_run_unavailable')
    row=db.execute('SELECT revision FROM asr_note_heads WHERE project=? AND run=? AND owner=?',(project,run,subject)).fetchone()
    if not row:raise ControlError('context_note_required')
    note_io.check(verified_note,db)
    if row[0]!=verified_note['head']:raise ControlError('context_note_sources_changed')
    store=verified_note['store']
    note=store.read(row[0])
    sequences=[int(ref['id'].split(':',1)[1]) for ref in note['sources'] if ref['id'].startswith('organization:')]
    refs=[json.loads(ref['id'][len('artifact:'):]) for ref in note['sources'] if ref['id'].startswith('artifact:')]
    materials=_materials(db,service,project,run,sequences)+resolve(db,service,project,run,refs,prepared=verified_note['artifacts'])
    restored=restore(store,accepted_revision=row[0],materials=materials,role=subject)
    if restored['status']!='ready':raise ControlError('context_note_sources_changed')
    if source_registration is not None:
        from .context_sources import read
        materials.extend(read(service,db,project,run,subject,source_registration,verified=verified_source))
    materials.append(restored['material'])
    owned={d['entity_id'] for d in current(db,project,run,'direction') if d['document']['owner']==subject}
    tasks={t['entity_id']:t['revision'] for t in current(db,project,run,'task') if role=='organizer' or t['document']['assignee']==subject or t['document']['direction_id'] in owned}
    executions=sorted(r[0] for r in db.execute("SELECT attempt FROM asr_dispatch WHERE project=? AND run=? AND state NOT IN ('succeeded','failed','cancelled','timed_out','interrupted')",(project,run)))
    stamp=dict(project_id=project,run_id=run,contract_revision=state['contract_revision'],control_revision=state['control_revision'],task_revisions=tasks,
               unsettled_executions=executions,source_fingerprints={m.id:material_digest(m) for m in materials})
    return materials,stamp


def source_rows(materials):
    return [dict(id=m.id,revision=m.revision,sha256=material_digest(m),text=m.text) for m in materials]


def _prepare(service,token,project,run,*,subject,reviewer_subject,idempotency_key,source_registration=None,verified_source=None,verified_note=None):
    service._auth(token,project,{'human','supervisor'});service._identity(run,subject,reviewer_subject,idempotency_key)
    if source_registration is not None:service._identity(source_registration)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        member(db,project,run,subject);member(db,project,run,reviewer_subject)
        if subject==reviewer_subject:raise ControlError('context_separate_reviewer_required')
        scope=_scope('prepare',run,subject);payload=[subject,reviewer_subject]
        if source_registration is not None:payload.append(source_registration)
        replay=service._replay(db,project,scope,idempotency_key,payload)
        if replay:return replay
        materials,stamp=snapshot(service,db,project,run,subject,source_registration,verified_source=verified_source,verified_note=verified_note)
        record=dict(preparation_id=idempotency_key,subject=subject,reviewer_subject=reviewer_subject,
                    materials=[asdict(m) for m in materials],state_stamp=stamp,note_revision=materials[-1].revision,source_registration=source_registration)
        record=json.loads(encoded(record))
        note_io.check(verified_note,db)
        if verified_source is not None:verified_source.check()
        service._remember(db,project,scope,idempotency_key,payload,record)
        service._event(db,project,run,'context_prepared',subject=subject,reviewer_subject=reviewer_subject,preparation_id=idempotency_key)
        return record


def prepare(service,token,project,run,**arguments):
    service._auth(token,project,{'human','supervisor'})
    from .context_sources import verify_registered
    source=arguments.get('source_registration')
    # Replay first: historical receipts never require the original file to exist.
    subject=arguments['subject'];payload=[subject,arguments['reviewer_subject']]
    if source is not None:payload.append(source)
    with service._connect() as db:
        member(db,project,run,subject);member(db,project,run,arguments['reviewer_subject'])
        replay=service._replay(db,project,_scope('prepare',run,subject),arguments['idempotency_key'],payload)
        if replay:return replay
    verified=verify_registered(service,project,run,subject,source) if source is not None else None
    return _prepare(service,token,project,run,**arguments,verified_source=verified,verified_note=note_io.capture(service,project,run,subject))


def _session(db,project,run,session_id,subject):
    raw=db.execute('SELECT record FROM asr_runtime_sessions WHERE project=? AND run=? AND session_id=?',(project,run,session_id)).fetchone()
    session=json.loads(raw[0]) if raw else {}
    binding=session.get('organization_binding') or {}
    if session.get('state')!='exited' or session.get('execution_exited') is not True or not session.get('process_identity') or binding.get('subject')!=subject:
        raise ControlError('context_review_session_unavailable')
    from .organization_runtime import validate
    validate(db,project,run,binding)


def _admit(service,token,project,run,*,subject,preparation_id,idempotency_key,request,candidate,review_request,review,author_session,reviewer_session,verified_source=None,verified_note=None,evaluation=None):
    service._auth(token,project,{'human','supervisor'});service._identity(run,subject,preparation_id,idempotency_key,author_session,reviewer_session)
    if any(type(v) is not dict for v in (request,candidate,review_request,review)) or type(request.get('payload')) is not dict:raise ControlError('invalid_context_bundle')
    payload=[subject,preparation_id,request,candidate,review_request,review,author_session,reviewer_session]
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        member(db,project,run,subject)
        scope=_scope('admission',run,subject)
        replay=service._replay(db,project,scope,idempotency_key,payload)
        if replay:return replay  # Historical receipt only; not an installation bearer token.
        raw=db.execute('SELECT record FROM asr_requests WHERE project=? AND scope=? AND request_key=?',(project,_scope('prepare',run,subject),preparation_id)).fetchone()
        if not raw:raise ControlError('context_preparation_unavailable')
        prepared=json.loads(raw[0]);member(db,project,run,prepared['reviewer_subject'])
        _session(db,project,run,author_session,subject);_session(db,project,run,reviewer_session,prepared['reviewer_subject'])
        if db.execute("SELECT 1 FROM asr_runtime_sessions WHERE project=? AND run=? AND state!='exited'",(project,run)).fetchone():raise ControlError('context_runtime_active')
        try:
            materials,stamp=snapshot(service,db,project,run,subject,prepared.get('source_registration'),verified_source=verified_source,verified_note=verified_note)
            if evaluation is None or evaluation['prepared']!=encoded(prepared) or evaluation['payload']!=encoded(payload):
                raise ControlError('context_admission_inputs_changed')
            if evaluation.get('error') is not None:raise evaluation['error']
            if stamp!=evaluation['state']:raise ControlError('research_state_changed')
            checked=evaluation['check']
            note_io.check(verified_note,db)
            if verified_source is not None:verified_source.check()
            if checked['status']!='admission_required':
                result=dict(status='deferred',context_installed=False,check=checked)
            else:
                result=dict(status='admitted',context_installed=False,requires_runtime_receipt=True,installation_authorized=False,runtime_coverage_verified=False,requires_fresh_installation_check=True,subject=subject,
                            preparation_id=preparation_id,plan=checked,admission_id=idempotency_key)
        except (ControlError,ValueError) as error:
            result=dict(status='deferred',context_installed=False,check=dict(reason=getattr(error,'code',str(error)),details=getattr(error,'details',None)))
        service._remember(db,project,scope,idempotency_key,payload,result)
        service._event(db,project,run,'context_'+result['status'],subject=subject,preparation_id=preparation_id,admission_id=idempotency_key)
        return result


def _evaluate(service,project,run,prepared,payload,verified_source,verified_note):
    """Pure review work outside the writer; commit still owns current authority."""
    subject,preparation_id,request,candidate,review_request,review,author_session,reviewer_session=payload
    evaluation=dict(prepared=encoded(prepared),payload=encoded(payload))
    try:
        with service._connect() as db:
            _,stamp=snapshot(service,db,project,run,subject,prepared.get('source_registration'),verified_source=verified_source,verified_note=verified_note)
        frozen=[Material(**{k:tuple(v) if k in ('references','citations','roles') else v for k,v in row.items()}) for row in prepared['materials']]
        if request.get('payload',{}).get('role')!=subject or request['payload'].get('sources')!=source_rows(frozen):raise ControlError('context_request_sources_mismatch')
        checked=plan(request,candidate,review_request,review,author_session=author_session,reviewer_session=reviewer_session,
                     expected_state=prepared['state_stamp'],current_state=stamp)
        evaluation.update(state=stamp,check=checked)
    except (ControlError,ValueError) as error:evaluation['error']=error
    return evaluation


def admit(service,token,project,run,**arguments):
    try:
        service._auth(token,project,{'human','supervisor'})
        subject=arguments['subject']
        payload=[subject,arguments['preparation_id'],arguments['request'],arguments['candidate'],arguments['review_request'],arguments['review'],arguments['author_session'],arguments['reviewer_session']]
        with service._connect() as db:
            member(db,project,run,subject)
            replay=service._replay(db,project,_scope('admission',run,subject),arguments['idempotency_key'],payload)
            if replay:return replay
            raw=db.execute('SELECT record FROM asr_requests WHERE project=? AND scope=? AND request_key=?',(project,_scope('prepare',run,subject),arguments['preparation_id'])).fetchone()
            if not raw:raise ControlError('context_preparation_unavailable')
            prepared=json.loads(raw[0])
            member(db,project,run,prepared['reviewer_subject'])
            _session(db,project,run,arguments['author_session'],subject)
            _session(db,project,run,arguments['reviewer_session'],prepared['reviewer_subject'])
            if db.execute("SELECT 1 FROM asr_runtime_sessions WHERE project=? AND run=? AND state!='exited'",(project,run)).fetchone():raise ControlError('context_runtime_active')
        from .context_sources import verify_registered
        source=prepared.get('source_registration')
        verified=verify_registered(service,project,run,subject,source) if source is not None else None
        if any(type(arguments[v]) is not dict for v in ('request','candidate','review_request','review')) or type(arguments['request'].get('payload')) is not dict:
            raise ControlError('invalid_context_bundle')
        verified_note=note_io.capture(service,project,run,subject)
        evaluation=_evaluate(service,project,run,prepared,payload,verified,verified_note)
        return _admit(service,token,project,run,**arguments,verified_source=verified,verified_note=verified_note,evaluation=evaluation)
    except ControlError as error:
        if error.code not in ('unauthorized','forbidden'):
            service._auth(token,project,{'human','supervisor'})
            with service._connect() as db:
                service._event(db,project,run,'context_admission_rejected',reason=error.code,subject=arguments.get('subject'),
                               preparation_id=arguments.get('preparation_id'),request_key=arguments.get('idempotency_key'))
        raise
