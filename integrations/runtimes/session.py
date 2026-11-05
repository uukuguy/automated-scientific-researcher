"""Run one fenced runtime session; no scheduler or automatic retry."""
from pathlib import Path
import hashlib
import json
import math
import time
import uuid
import sqlite3
from asr_service.control import ControlError
from .pi import Limits, RuntimeFailure, prepare_oauth, synchronize_oauth


def session_engine_deadline(limits,reserved_walltime_ms,started):
    cap=min(limits.walltime_seconds,reserved_walltime_ms/1000)
    return started+cap-min(5,cap/4)


def run_session(runtime, bridge, *, config_dir, native_session_id, prompt, limits, oauth_source=None, on_event=None):
    service=bridge.service
    from .capacity_policy import load_policy
    from .context_capacity import assess
    capacity_policy=getattr(runtime,'capacity_policy',None) or load_policy()
    organization_arguments={}
    if bridge.capability_profile in ('research-organization/1','research-organization-study/1'):
        pack=runtime.preflight_capabilities()
        if pack['pack']['id']!=bridge.capability_profile:
            raise RuntimeFailure('organization_capability_mismatch')
        binding=service.organization_runtime_binding(bridge.researcher_token,bridge.project,bridge.run,
            capability_profile=bridge.capability_profile,capability_pack_sha256=pack['sha256'])
        organization_arguments['organization_binding']=binding
        identity=[bridge.project,bridge.run,binding['subject'],binding['role']]
        context=hashlib.sha256(json.dumps(identity,separators=(',',':')).encode()).hexdigest()
        config_dir=Path(config_dir)/'organization'/context
    owner='pi_'+uuid.uuid4().hex
    claim=service.claim_runtime(bridge.supervisor_token,bridge.project,bridge.run,owner,
        idempotency_key=owner,runtime_identity=dict(provider=runtime.provider,model=runtime.model,auth_mode='subscription_oauth',billing_mode='subscription'),requested_walltime_ms=int(limits.walltime_seconds*1000),**organization_arguments)
    if claim.get('replayed'): raise RuntimeFailure('runtime_reconciliation_required')
    bridge.runtime_identity=dict(session_id=claim['session_id'],epoch=claim['epoch'],owner=owner)
    started=time.monotonic()
    exited=False
    cursor_receipts=[];capacity_observations=[]
    from .async_observations import OrderedObservations
    runtime_identity=dict(bridge.runtime_identity)
    def record_cursor(record):
        if record.get('type')=='asr_context_capacity':
            assessment=assess(record,policy=capacity_policy)
            assessment.update(runtime_session_id=runtime_identity['session_id'],observation_id=record.get('observation_id'))
            capacity_observations.append(assessment)
            return
        try:
            receipt=service.observe_context_cursor(bridge.supervisor_token,bridge.project,bridge.run,
                **runtime_identity,observation=record)
        except (ControlError,OSError,sqlite3.Error,ValueError) as error:
            receipt=dict(status='deferred',reason=getattr(error,'code','context_cursor_record_failed'),
                         installation_authorized=False,active_cursor_verified=False,
                         recovery='Keep native originals; delayed observations do not prove a live cursor.')
        cursor_receipts.append(receipt)
    cursor_writer=None
    def recording_pressure():
        observer=cursor_writer.capacity_state() if cursor_writer is not None else None
        if observer:return observer
        probe=getattr(on_event,'capacity_state',None)
        return probe() if probe is not None else None
    def record_event(record,forward=True):
        if record.get('type')=='asr_limit':
            observation={key:record[key] for key in ('kind','limit','observed','reason')}
            if 'native_checkpointed' in record:
                observation['reason']+=' Native checkpoint: '+('stored' if record['native_checkpointed'] else str(record.get('checkpoint_failure') or 'unconfirmed'))+'; abort: '+('requested' if record.get('graceful_abort_requested') else str(record.get('abort_failure') or 'unconfirmed'))+'.'
            identity=hashlib.sha256(json.dumps(observation,sort_keys=True).encode()).hexdigest()
            service.observe_runtime_limit(bridge.supervisor_token,bridge.project,bridge.run,
                **bridge.runtime_identity,**observation,idempotency_key='runtime_limit_'+owner+'_'+identity)
        if record.get('type')=='asr_context_capacity' or record.get('type')=='asr_context_cursor' and organization_arguments:
            cursor_writer.submit(record)
        if forward and on_event:on_event(record)
    try:
        cursor_writer=OrderedObservations(record_cursor,policy=capacity_policy)
        bridge.context_observation_barrier=cursor_writer.barrier
        bridge.recording_pressure=recording_pressure
        source=Path(oauth_source or Path.home()/'.pi/agent/auth.json')
        oauth_baseline=prepare_oauth(source,Path(config_dir))
        effective=Limits(min(limits.walltime_seconds,claim['reserved_walltime_ms']/1000),limits.turns,limits.tool_executions)
        if organization_arguments:
            generation=getattr(runtime,'context_generation',0)
            directory=Path(config_dir).resolve()/('sessions' if generation==0 else f'sessions-generation-{generation}')
            service.bind_runtime_context(bridge.supervisor_token,bridge.project,bridge.run,**bridge.runtime_identity,
                native_session_id=native_session_id,journal_directory=str(directory))
        with bridge:
            result=runtime.run(workspace=bridge.workspace,config_dir=config_dir,session_id=native_session_id,
                prompt=prompt,limits=effective,bridge_url=bridge.url,bridge_token=bridge.token,on_event=record_event,
                absolute_deadline=session_engine_deadline(limits,claim['reserved_walltime_ms'],started),
                on_launch=lambda: service.begin_runtime_launch(bridge.supervisor_token,bridge.project,bridge.run,claim['session_id'],claim['epoch'],owner),
                on_process=lambda identity: service.attach_runtime_process(bridge.supervisor_token,bridge.project,bridge.run,claim['session_id'],claim['epoch'],owner,identity),
                should_stop=lambda: service.runtime_stop_requested(bridge.supervisor_token,bridge.project,bridge.run))
        exited=True
        result['runtime_claim']=claim
        result['context_observation_drain']=cursor_writer.close(timeout=0)
        result['context_cursor_receipts']=list(cursor_receipts)
        result['context_capacity_observations']=list(capacity_observations)
        if on_event:
            for receipt in result['context_cursor_receipts']:
                on_event(dict(type='asr_context_cursor_binding',**receipt))
            for assessment in result['context_capacity_observations']:
                on_event(dict(type='asr_context_capacity_assessment',**assessment))
            on_event(dict(type='asr_context_observation_drain',**result['context_observation_drain']))
        try:
            result['oauth_sync']=synchronize_oauth(source,Path(config_dir),oauth_baseline)
        except (RuntimeFailure,OSError,ValueError) as error:
            # Preserve the actual model result and release its reservation below.
            # A conflicting login/locked store is not permission to log in again.
            reason=error.code if isinstance(error,RuntimeFailure) else 'oauth_store_io_failed'
            result['oauth_sync']=dict(status='deferred',reason=reason,credentials_emitted=False)
            with service._connect() as db:
                service._event(db,bridge.project,bridge.run,'runtime_auth_sync_deferred',session_id=claim['session_id'],reason=reason)
            state=service.get_run(bridge.supervisor_token,bridge.project,bridge.run)
            if state['state']=='running':
                service.command(bridge.supervisor_token,bridge.project,bridge.run,'pause',expected_revision=state['control_revision'],idempotency_key='auth_sync_'+owner)
        for observation in result.get('limit_observations',[]):record_event(observation,False)
        if result['status']=='rate_limited':
            run=service.get_run(bridge.supervisor_token,bridge.project,bridge.run)
            service.command(bridge.supervisor_token,bridge.project,bridge.run,'quota',expected_revision=run['control_revision'],
                idempotency_key='quota_'+owner,payload={'state':'rate_limited'})
        return result
    except RuntimeFailure as error:
        if {'kind','limit','observed','reason'}<=set(error.details):
            record_event(dict(type='asr_limit',recoverable=True,**error.details))
        raise
    finally:
        if cursor_writer is not None and not cursor_writer.closed:cursor_writer.close(timeout=0)
        bridge.context_observation_barrier=None
        bridge.recording_pressure=None
        # If setup failed before spawn, there is no child to reconcile. A runtime
        # exception after launch is conservatively unresolved unless run returned.
        if not exited:
            current=service.get_run(bridge.supervisor_token,bridge.project,bridge.run)
            session=next(x for x in current['runtime_sessions'] if x['session_id']==claim['session_id'])
            if session.get('launch_state')=='prepared':
                service.abort_runtime_prelaunch(bridge.supervisor_token,bridge.project,bridge.run,claim['session_id'],claim['epoch'],owner,
                    reason='runtime_preflight_failed',actual_walltime_ms=max(1,math.ceil((time.monotonic()-started)*1000)))
                # No launch intent existed, so there is no process to release.
                exited=False
        if exited: service.release_runtime(bridge.supervisor_token,bridge.project,bridge.run,
            claim['session_id'],claim['epoch'],owner,execution_exited=exited,
            actual_walltime_ms=max(1,int((time.monotonic()-started)*1000)))
