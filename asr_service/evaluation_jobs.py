"""Control-owned evaluator intents, fencing and reservations; no execution loop."""
import copy
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import time
import uuid
from jsonschema import Draft202012Validator
from .contracts import encoded
from .budgets import BudgetStore
from .validations import VALIDATION_SCHEMA,_evidence

TERMINAL={'succeeded','failed','cancelled','timed_out','interrupted'}

class EvaluationError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS asr_evaluation_jobs(project TEXT,run TEXT,evaluation_id TEXT PRIMARY KEY,attempt TEXT UNIQUE,state TEXT,record TEXT)''')


def _get(db,project,run,identifier):
    row=db.execute('SELECT record FROM asr_evaluation_jobs WHERE project=? AND run=? AND evaluation_id=?',(project,run,identifier)).fetchone()
    if row is None:raise EvaluationError('evaluation_not_found')
    return json.loads(row[0])


def _save(db,record):
    db.execute('UPDATE asr_evaluation_jobs SET state=?,record=? WHERE evaluation_id=?',(record['state'],encoded(record),record['evaluation_id']))


def _fence(record,epoch,owner,*,live=True):
    if type(epoch) is not int or record['epoch']!=epoch or record['owner']!=owner:raise EvaluationError('stale_evaluation_epoch')
    if live and record['lease_until']<time.time():raise EvaluationError('evaluation_lease_expired')


def _lease(seconds):
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=3600:raise EvaluationError('invalid_lease')


def list_jobs(service,token,project,run):
    service._auth(token,project)
    with service._connect() as db:
        service._run(db,project,run)
        return [json.loads(row[0]) for row in db.execute('SELECT record FROM asr_evaluation_jobs WHERE project=? AND run=? ORDER BY rowid',(project,run))]


def get_job(service,token,project,run,evaluation_id):
    service._auth(token,project)
    with service._connect() as db:return _get(db,project,run,evaluation_id)


def admit(service,token,project,run,*,request_key,target,requested_budget):
    principal=service._auth(token,project,{'human','researcher'})
    service._identity(run,request_key)
    if next(Draft202012Validator(VALIDATION_SCHEMA['properties']['target']).iter_errors(target),None):raise EvaluationError('invalid_evaluation_target')
    if type(requested_budget) is not dict or set(requested_budget)!={'evaluation_attempts','evaluation_ms'} or type(requested_budget['evaluation_attempts']) is not int or requested_budget['evaluation_attempts']!=1 or type(requested_budget['evaluation_ms']) is not int or not 1<=requested_budget['evaluation_ms']<=60000:raise EvaluationError('invalid_evaluation_budget')
    payload=[principal['subject'],target,requested_budget]
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        replay=service._replay(db,project,'evaluation:'+run,request_key,payload)
        if replay:return replay
        running=service._run(db,project,run)
        if not service.owning_gate(db,dict(project_id=project,research_run_id=run)):raise EvaluationError('admission_closed')
        policy=service._contract(db,project,running['contract_id'],running['contract_revision'])['document']
        if not {'evaluation_attempts','evaluation_ms'}<=set(policy['budget']) or any(policy['budget'][name]<=0 for name in ('evaluation_attempts','evaluation_ms')):raise EvaluationError('capability_unavailable')
        if requested_budget['evaluation_ms']>policy['execution_policy']['timeout_seconds']*1000:raise EvaluationError('invalid_evaluation_budget')
        trial=_evidence(db,project,run,target)
        from asr_supervisor.store import ExecutionStore
        source=ExecutionStore._read(db,target['execution_attempt_id'])['report']['evidence_path']
        identifier='evaluation_'+uuid.uuid4().hex;attempt='eval_attempt_'+uuid.uuid4().hex
        service.budgets.reserve_many_in_transaction(db,project,attempt,requested_budget)
        record=dict(project_id=project,research_run_id=run,evaluation_id=identifier,evaluation_attempt_id=attempt,target=copy.deepcopy(target),source_path=source,requested_budget=copy.deepcopy(requested_budget),timeout_seconds=requested_budget['evaluation_ms']/1000,contract_id=running['contract_id'],contract_revision=running['contract_revision'],state='queued',settled=False,epoch=0,execution_epoch=None,owner=None,lease_until=0,identity=None,created_at=datetime.now(timezone.utc).isoformat())
        db.execute('INSERT INTO asr_evaluation_jobs VALUES (?,?,?,?,?,?)',(project,run,identifier,attempt,'queued',encoded(record)))
        service._remember(db,project,'evaluation:'+run,request_key,payload,record)
        service._event(db,project,run,'evaluation_admitted',evaluation_id=identifier,evaluation_attempt_id=attempt,target=target)
        return record


def claim(service,token,project,run,evaluation_id,owner,*,lease_seconds=30):
    service._auth(token,project,{'supervisor'});service._identity(owner);_lease(lease_seconds)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');record=_get(db,project,run,evaluation_id)
        if record['state']!='queued' or record['settled']:raise EvaluationError('evaluation_reconciliation_required')
        if not service.owning_gate(db,dict(project_id=project,research_run_id=run)):raise EvaluationError('admission_closed')
        for body, in db.execute("SELECT record FROM asr_evaluation_jobs WHERE project=? AND run=? AND state!='queued'",(project,run)):
            other=json.loads(body)
            if not other['settled']:raise EvaluationError('evaluation_execution_active')
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='asr_executions'").fetchone():
            for body, in db.execute('SELECT record FROM asr_executions'):
                other=json.loads(body)
                if other['project']==project and other['run']==run and other.get('report') is None:raise EvaluationError('numerical_execution_active')
        record.update(state='claimed',epoch=1,execution_epoch=1,owner=owner,lease_until=time.time()+lease_seconds,launch_state='prepared',prepared_at=datetime.now(timezone.utc).isoformat(),started_at=time.time())
        record['launch_intent']=dict(name='asr-eval-'+record['evaluation_attempt_id'],labels={'asr.owner':'isolated-material-evaluator','asr.evaluation':evaluation_id,'asr.evaluation_attempt':record['evaluation_attempt_id'],'asr.project':project,'asr.run':run,'asr.epoch':'1'})
        _save(db,record);service._event(db,project,run,'evaluation_claimed',evaluation_id=evaluation_id,epoch=1,launch_intent=record['launch_intent'])
        return record


def heartbeat(service,token,project,run,evaluation_id,epoch,owner,*,lease_seconds=30):
    service._auth(token,project,{'supervisor'});_lease(lease_seconds)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');record=_get(db,project,run,evaluation_id);_fence(record,epoch,owner)
        if record['settled']:raise EvaluationError('evaluation_terminal')
        record['lease_until']=time.time()+lease_seconds;_save(db,record);return record


def attach(service,token,project,run,evaluation_id,epoch,owner,identity):
    service._auth(token,project,{'supervisor'})
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');record=_get(db,project,run,evaluation_id);_fence(record,epoch,owner)
        if record['settled']:raise EvaluationError('evaluation_terminal')
        if record.get('launch_state')!='launching':raise EvaluationError('evaluation_launch_not_authorized')
        intent=record['launch_intent']
        if type(identity) is not dict or identity.get('name')!=intent['name'] or not isinstance(identity.get('container_id'),str) or not identity['container_id'] or any(identity.get('labels',{}).get(k)!=v for k,v in intent['labels'].items()):raise EvaluationError('evaluation_identity_conflict')
        if record['identity'] is not None and record['identity']!=identity:raise EvaluationError('evaluation_identity_immutable')
        record['identity']=copy.deepcopy(identity)
        if record['state']=='claimed':record['state']='running'
        _save(db,record);service._event(db,project,run,'evaluation_identity_attached',evaluation_id=evaluation_id,epoch=epoch,identity=identity);return record


def uncertain(service,token,project,run,evaluation_id,epoch,owner,reason):
    service._auth(token,project,{'supervisor'})
    if type(reason) is not str or not 1<=len(reason)<=256:raise EvaluationError('invalid_uncertainty_reason')
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');record=_get(db,project,run,evaluation_id);_fence(record,epoch,owner)
        if record['settled']:raise EvaluationError('evaluation_terminal')
        record.update(state='uncertain',uncertainty=reason);_save(db,record)
        running=service._run(db,project,run);running.update(health='reconciling',admission_open=False)
        db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(running),project,run))
        service._event(db,project,run,'evaluation_uncertain',evaluation_id=evaluation_id,epoch=epoch)
        return record


def reconcile_claim(service,token,project,run,evaluation_id,owner,*,lease_seconds=30):
    service._auth(token,project,{'supervisor'});service._identity(owner);_lease(lease_seconds)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');record=_get(db,project,run,evaluation_id)
        if record['settled']:return record
        if record['state']=='queued':raise EvaluationError('evaluation_not_launched')
        if record['lease_until']>=time.time():raise EvaluationError('evaluation_lease_active')
        record.update(epoch=record['epoch']+1,owner=owner,lease_until=time.time()+lease_seconds,state='reconciling')
        running=service._run(db,project,run);running.update(health='reconciling',admission_open=False)
        db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(running),project,run))
        _save(db,record);service._event(db,project,run,'evaluation_reconciling',evaluation_id=evaluation_id,epoch=record['epoch']);return record


def should_stop(service,token,project,run,evaluation_id,epoch,owner):
    service._auth(token,project,{'supervisor'})
    with service._connect() as db:
        record=_get(db,project,run,evaluation_id)
        try:_fence(record,epoch,owner)
        except EvaluationError:return True
        running=service._run(db,project,run)
        return record['state']=='cancel_requested' or running['state'] in ('stopping','stopped','failed')


def verify_artifact(path,authority):
    from asr_evaluation.managed import verify_managed_artifact
    return verify_managed_artifact(path,authority)


def complete(service,token,project,run,evaluation_id,epoch,owner,*,artifact_path,artifact_sha256,usage_ms):
    service._auth(token,project,{'supervisor'});BudgetStore._amount(usage_ms)
    with service._connect() as db:
        record=_get(db,project,run,evaluation_id);_fence(record,epoch,owner,live=not record['settled'])
        if record['settled']:
            if record['artifact']['sha256']!=artifact_sha256:raise EvaluationError('evaluation_report_conflict')
            return record
    authority={k:record[k] for k in ('project_id','research_run_id','evaluation_id','evaluation_attempt_id')};authority['epoch']=record['execution_epoch']
    path=Path(artifact_path)
    if path.is_symlink() or (path/'manifest.json').is_symlink() or hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()!=artifact_sha256:raise EvaluationError('evaluation_artifact_conflict')
    verified=verify_artifact(path,authority);manifest=verified['manifest']
    if manifest!=json.loads((path/'manifest.json').read_bytes()) or hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()!=artifact_sha256:raise EvaluationError('evaluation_artifact_conflict')
    target=record['target'];source=manifest.get('source',{})
    identity=record.get('identity');facts=verified['isolation_facts']
    if not identity or facts.get('container_id')!=identity['container_id'] or any(facts.get('labels',{}).get(k)!=v for k,v in record['launch_intent']['labels'].items()):raise EvaluationError('evaluation_artifact_conflict')
    if manifest.get('evaluation_ref')!=target['evaluation_ref']:raise EvaluationError('evaluation_artifact_conflict')
    if manifest.get('authority')!=authority or source.get('identity')!={k:target[k] for k in ('trial_id','execution_attempt_id')}|{'research_run_id':run} or source.get('manifest_sha256')!=target['manifest_hash'] or manifest.get('execution_exited') is not True or manifest.get('execution_status') not in TERMINAL:raise EvaluationError('evaluation_artifact_conflict')
    elapsed=manifest.get('elapsed_seconds')
    if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0:raise EvaluationError('evaluation_artifact_conflict')
    actual=max(usage_ms,math.ceil(elapsed*1000));BudgetStore._amount(actual)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');record=_get(db,project,run,evaluation_id);_fence(record,epoch,owner)
        if record['identity'] is None:raise EvaluationError('evaluation_identity_required')
        if record['settled']:raise EvaluationError('evaluation_terminal')
        db.execute('UPDATE asr_budget_reservations SET actual=CASE dimension WHEN ? THEN 1 ELSE ? END WHERE project=? AND attempt=?',('evaluation_attempts',actual,project,record['evaluation_attempt_id']))
        record.update(state=manifest['execution_status'],settled=True,artifact=dict(path=str(path.resolve()),sha256=artifact_sha256,authority=authority,isolation_facts=verified['isolation_facts']),report=manifest,usage_ms=actual,finished_at=datetime.now(timezone.utc).isoformat())
        _save(db,record)
        _update_run_after_settlement(service,db,project,run)
        service._event(db,project,run,'evaluation_completed',evaluation_id=evaluation_id,artifact_sha256=artifact_sha256,state=record['state'],usage_ms=actual)
        from asr_supervisor.store import ExecutionStore
        ExecutionStore.finalize_controls_in_transaction(db,project,run)
        return record


def _update_run_after_settlement(service,db,project,run):
    service.refresh_run_health(db,project,run)


def begin_launch(service,token,project,run,evaluation_id,epoch,owner):
    service._auth(token,project,{'supervisor'})
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');record=_get(db,project,run,evaluation_id);_fence(record,epoch,owner)
        if record['settled'] or record.get('launch_state')!='prepared' or record['state']=='reconciling':raise EvaluationError('evaluation_launch_already_authorized')
        if not service.owning_gate(db,dict(project_id=project,research_run_id=run)):raise EvaluationError('admission_closed')
        record.update(launch_state='launching',launch_authorized_at=datetime.now(timezone.utc).isoformat());_save(db,record)
        service._event(db,project,run,'evaluation_launch_authorized',evaluation_id=evaluation_id,epoch=epoch,launch_intent=record['launch_intent'])
        return record


def abort_prelaunch(service,token,project,run,evaluation_id,epoch,owner,*,usage_ms,reason):
    service._auth(token,project,{'supervisor'});BudgetStore._amount(usage_ms)
    if type(reason) is not str or not 1<=len(reason)<=256:raise EvaluationError('invalid_preflight_reason')
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');record=_get(db,project,run,evaluation_id);_fence(record,epoch,owner,live=not record['settled'])
        if record['settled'] and record.get('report_type')=='no_launch_grant_issued':return record
        if record['settled'] or record.get('launch_state')!='prepared' or record.get('identity') is not None:raise EvaluationError('evaluation_launch_already_authorized')
        usage_ms=max(usage_ms,1,math.ceil((time.time()-record['started_at'])*1000));BudgetStore._amount(usage_ms)
        db.execute('UPDATE asr_budget_reservations SET actual=CASE dimension WHEN ? THEN 1 ELSE ? END WHERE project=? AND attempt=?',('evaluation_attempts',usage_ms,project,record['evaluation_attempt_id']))
        record.update(state='failed',settled=True,launch_state='aborted',report_type='no_launch_grant_issued',preflight_reason=reason,usage_ms=usage_ms,finished_at=datetime.now(timezone.utc).isoformat());_save(db,record)
        _update_run_after_settlement(service,db,project,run)
        service._event(db,project,run,'evaluation_prelaunch_aborted',evaluation_id=evaluation_id,epoch=epoch,usage_ms=usage_ms,reason=reason)
        from asr_supervisor.store import ExecutionStore
        ExecutionStore.finalize_controls_in_transaction(db,project,run)
        return record
