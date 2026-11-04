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


def register(service,token,project,run,*,subject,idempotency_key,path,native_session_id,leaf_id,keep_recent_groups,max_journal_bytes):
    from .context_admission import _scope
    service._auth(token,project,{'human','supervisor'})
    service._identity(run,subject,idempotency_key,native_session_id,leaf_id)
    if type(path) is not str or not Path(path).is_absolute():raise ControlError('context_source_absolute_path_required')
    arguments=dict(path=path,native_session_id=native_session_id,leaf_id=leaf_id,scope=encoded([project,run,subject]),
                   keep_recent_groups=keep_recent_groups,max_journal_bytes=max_journal_bytes)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        member(db,project,run,subject);service._run(db,project,run)
        scope=_scope('source',run,subject)
        replay=service._replay(db,project,scope,idempotency_key,arguments)
        if replay:return replay  # Historical registration, not a fresh cursor check.
        observed=_observe(arguments)
        result=dict(status='registered' if observed['status']=='observed' else 'deferred',registration_id=idempotency_key,
                    subject=subject,reader=arguments,observation=observed,active_cursor_verified=False,installation_authorized=False)
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
    return materials(observed['conversation'])
