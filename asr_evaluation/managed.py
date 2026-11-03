"""Bind isolated rechecks to Control's sole evaluator-job and budget ledger."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
from datetime import datetime,timezone

from .replay import Replay,ReplayError,_read,_json,_write,verify_container
from powerflow_lab.runner import canonical
from asr_supervisor.resources import bounded_command


def _intent(authority):
    return dict(name='asr-eval-'+authority['evaluation_attempt_id'],labels={
        'asr.owner':'isolated-material-evaluator','asr.evaluation':authority['evaluation_id'],
        'asr.evaluation_attempt':authority['evaluation_attempt_id'],'asr.project':authority['project_id'],
        'asr.run':authority['research_run_id'],'asr.epoch':str(authority['epoch'])})


def _absence(intent):
    """Distinguish a responsive daemon's exact 404 from connection failure."""
    name=intent['name']
    result=bounded_command(['docker','container','inspect',name],component='evaluator',operation='prelaunch_inspect')
    message=result.stderr.decode(errors='replace').strip()
    allowed={'Error: No such container: '+name,'Error: No such object: '+name,
             'Error response from daemon: No such container: '+name}
    if result.returncode!=1 or message not in allowed:
        raise ReplayError('prelaunch container absence is not confirmed')
    daemon=bounded_command(['docker','info','--format','{{.ID}}'],component='evaluator',operation='prelaunch_daemon_probe',max_bytes=256)
    if daemon.returncode or not daemon.stdout.strip() or len(daemon.stdout)>256:
        raise ReplayError('prelaunch Docker daemon responsiveness is unconfirmed')
    return dict(name=name,absence_confirmed=True,daemon_id=daemon.stdout.decode().strip(),
                method='exact container-inspect not-found plus responsive Docker info')


def verify_managed_artifact(path,authority):
    """Verify bytes/derived fields and actual recorded configuration facts.

    This does not accept an author's label as machine evidence. Control must
    additionally match the exact manifest digest, admitted target, attached
    container ID and its current fencing owner before settling any reservation.
    """
    if not isinstance(authority,dict) or set(authority)!={'project_id','research_run_id','evaluation_id','evaluation_attempt_id','epoch'} or type(authority['epoch']) is not int or authority['epoch']<1:
        raise ValueError('invalid managed evaluation authority')
    original=Path(path)
    if original.is_symlink():raise ValueError('symlinked evaluation artifact')
    path=original.resolve()
    try:
        manifest=Replay(path.parent)._verified_final(path)
        if manifest.get('authority')!=authority:raise ValueError('managed evaluation authority mismatch')
        identity=_json(_read(path/'identity.json',65536))
        expected=_intent(authority)
        if identity.get('name')!=expected['name'] or identity.get('labels')!=expected['labels']:
            raise ValueError('managed launch intent mismatch')
        pending=path if path.name.endswith('.pending') else path.with_name(path.name+'.pending')
        exit_value=_json(_read(path/'exit-inspection.json'))
        verify_container(exit_value,identity,pending)
        launch_path=path/'launch-inspection.json'
        if launch_path.exists():verify_container(_json(_read(launch_path)),identity,pending)
        elif manifest['execution_status']=='succeeded':raise ValueError('managed launch inspection missing')
        if exit_value['State']['Running']:raise ValueError('managed execution exit unconfirmed')
        facts=dict(container_id=exit_value['Id'],image_id=exit_value['Image'],labels=expected['labels'],
            mounts=[dict(destination=m['Destination'],read_only=not m['RW']) for m in exit_value['Mounts']],
            user=exit_value['Config']['User'],environment_names=sorted(item.split('=',1)[0] for item in exit_value['Config']['Env']),
            security={name:exit_value['HostConfig'][name] for name in (
                'NetworkMode','ReadonlyRootfs','Privileged','Memory','MemorySwap','NanoCpus','PidsLimit','CapDrop','SecurityOpt')},
            execution_exited=True,launch_inspection_present=launch_path.exists())
        return dict(manifest=manifest,isolation_facts=facts)
    except (ReplayError,KeyError,TypeError,AttributeError) as error:
        raise ValueError('invalid managed evaluation artifact') from error


def run_evaluation(service,token,project,run,evaluation_id,owner,evidence_root,*,reconcile=False):
    """Advance one explicitly admitted job, never create a second queue or retry.

    Recovery requires ``reconcile=True`` and an expired Control lease. Immutable
    execution_epoch stays in the artifact; current epoch fences service writes.
    Credentials stay in this trusted host process, never in container mounts/env.
    """
    existing=service.get_evaluation(token,project,run,evaluation_id)
    if existing['settled']:
        if existing.get('artifact'):
            verify_managed_artifact(existing['artifact']['path'],existing['artifact']['authority'])
            if hashlib.sha256(_read(Path(existing['artifact']['path'])/'manifest.json',65536)).hexdigest()!=existing['artifact']['sha256']:
                raise ValueError('settled evaluation artifact changed')
        return existing
    claim=service.reconcile_evaluation_claim if reconcile else service.claim_evaluation
    record=claim(token,project,run,evaluation_id,owner)
    authority={k:record[k] for k in ('project_id','research_run_id','evaluation_id','evaluation_attempt_id')}
    authority['epoch']=record['execution_epoch']
    if record['launch_intent']!=_intent(authority):raise ValueError('Control launch intent mismatch')
    runner=Replay(evidence_root)
    key=record['evaluation_attempt_id']

    def poll():
        service.heartbeat_evaluation(token,project,run,evaluation_id,record['epoch'],owner)
        return service.evaluation_should_stop(token,project,run,evaluation_id,record['epoch'],owner)

    def attach(identity):
        service.attach_evaluation(token,project,run,evaluation_id,record['epoch'],owner,identity)

    def begin():
        service.begin_evaluation_launch(token,project,run,evaluation_id,record['epoch'],owner)

    def abort_prepared(current,reason,diagnostic=None):
        proof=_absence(current['launch_intent'])
        prepared=datetime.fromisoformat(current['prepared_at'])
        usage=max(1,math.ceil((datetime.now(timezone.utc)-prepared).total_seconds()*1000))
        receipt=dict(authority=authority,current_fencing_epoch=current['epoch'],absence=proof,
            report_type='no_launch_grant_issued',usage_ms=usage,
            usage_basis='Allocated setup walltime since prepared claim; includes interruption downtime.',reason=reason,diagnostic=diagnostic)
        body=canonical(receipt);digest=hashlib.sha256(body).hexdigest()
        receipt_path=runner.root/('prelaunch-'+digest+'.json')
        if not receipt_path.exists():_write(receipt_path,body)
        ended=service.abort_evaluation_prelaunch(token,project,run,evaluation_id,current['epoch'],owner,
            usage_ms=usage,reason=('no_launch_grant;'+_reason(reason,diagnostic)+';receipt_sha256='+digest)[:256])
        pending,_,_=runner._paths(key)
        if pending.exists():
            aborted=pending.with_name(pending.name.removesuffix('.pending')+'.preflight-aborted')
            if not aborted.exists():pending.rename(aborted)
        return ended

    try:
        if reconcile and record.get('launch_state')=='prepared':
            return abort_prepared(record,'prepared_claim_recovery')
        if reconcile:
            manifest=runner.reconcile(key,on_attach=attach,on_poll=poll)
        else:
            target=record['target']
            manifest=runner.run(key,record['source_path'],target['manifest_hash'],trial_id=target['trial_id'],
                execution_attempt_id=target['execution_attempt_id'],research_run_id=run,
                timeout_seconds=record['timeout_seconds'],authority=authority,evaluation_ref=target['evaluation_ref'],
                launch_intent=record['launch_intent'],on_create=begin,on_attach=attach,on_poll=poll)
        _,path,_=runner._paths(key)
        verified=verify_managed_artifact(path,authority)
        if verified['manifest']!=manifest:raise ValueError('managed result changed before completion')
        return service.complete_evaluation(token,project,run,evaluation_id,record['epoch'],owner,
            artifact_path=str(path),artifact_sha256=hashlib.sha256(_read(path/'manifest.json',65536)).hexdigest(),
            usage_ms=math.ceil(manifest['elapsed_seconds']*1000))
    except BaseException as error:
        current=service.get_evaluation(token,project,run,evaluation_id)
        diagnostic=getattr(error,'diagnostic',None)
        if not current['settled'] and current['epoch']==record['epoch'] and current.get('launch_state')=='prepared':
            try:return abort_prepared(current,type(error).__name__,diagnostic)
            except Exception:pass
        try:
            service.mark_evaluation_uncertain(token,project,run,evaluation_id,record['epoch'],owner,_reason(type(error).__name__,diagnostic))
        except Exception:
            pass  # A stale owner cannot overwrite a newer fence; budget stays reserved.
        raise


def _reason(fallback,diagnostic):
    if not diagnostic:return fallback
    if 'limit' not in diagnostic:return str(diagnostic.get('code',fallback))[:160]
    limit=diagnostic.get('limit',{});observed=diagnostic.get('observed',{})
    return (str(diagnostic.get('code',fallback))+';'+str(limit.get('name','limit'))+'='+str(limit.get('configured'))+
            ' '+str(limit.get('unit',''))+';observed='+str(observed.get('value')))[:160]
