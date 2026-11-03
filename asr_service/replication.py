"""A new controlled numerical attempt of the same immutable method, no scheduler."""
import copy
import json
import math
import uuid
from datetime import datetime,timezone
from .contracts import encoded,check_change
from .validations import _evidence


def submit(service,token,project,run,*,request_key,trial_id,requested_budget):
    principal=service._auth(token,project,{'human','researcher'});service._identity(request_key,trial_id,run)
    payload=[principal['subject'],trial_id,requested_budget]
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        replay=service._replay(db,project,'replication:'+run,request_key,payload)
        if replay:return replay
        running=service._run(db,project,run)
        from .organization_experiments import reject_legacy
        reject_legacy(db,project,run)
        if not service.owning_gate(db,dict(project_id=project,research_run_id=run)):raise ValueError('admission_closed')
        row=db.execute('SELECT attempt,record FROM asr_dispatch WHERE project=? AND run=? AND trial=?',(project,run,trial_id)).fetchone()
        if not row:raise ValueError('trial_not_found')
        original=json.loads(row[1])
        from asr_supervisor.store import ExecutionStore
        execution=ExecutionStore._read(db,row[0])
        if not execution.get('report'):raise ValueError('evidence_not_published')
        target=dict(trial_id=trial_id,execution_attempt_id=row[0],manifest_hash=execution['report']['manifest_hash'],evaluation_ref=original['references']['evaluation'])
        _evidence(db,project,run,target)
        doc=service._contract(db,project,running['contract_id'],running['contract_revision'])['document']
        service._validate_contract(db,project,doc)
        if doc['problem_ref']!=original['references']['problem'] or doc['evaluation_ref']!=target['evaluation_ref'] or original['execution_request']['timeout_seconds']>doc['execution_policy']['timeout_seconds']:raise ValueError('replication_contract_conflict')
        for name,value in original['variables'].items():
            variable=doc['variable_policy']['variables'].get(name)
            if variable is None:raise ValueError('replication_contract_conflict')
            if variable['value']!=value:check_change(doc['variable_policy'],name,value,principal['role'])
        if original['execution_request'].get('profile')=='octave-candidate/1':
            if 'octave-candidate/1' not in doc['execution_policy'].get('candidate_profiles',[]):raise ValueError('capability_unavailable')
            from .candidates import resolve,check_admission
            resolve(db,project,original['references']['candidate'])
            check_admission(db,project,run,original['references']['candidate'],doc['execution_policy'])
        expected={'attempts':1,'execution_ms':math.ceil(original['execution_request']['timeout_seconds']*1000)}
        if requested_budget!=expected or any(type(v) is not int for v in requested_budget.values()):raise ValueError('replication_budget_conflict')
        trial='trial_'+uuid.uuid4().hex;attempt='attempt_'+uuid.uuid4().hex
        service.budgets.reserve_many_in_transaction(db,project,attempt,requested_budget)
        record=copy.deepcopy(original)
        record.update(trial_id=trial,execution_attempt_id=attempt,requested_budget=requested_budget,state='queued',created_at=datetime.now(timezone.utc).isoformat(),replicates=target,contract_id=running['contract_id'],contract_revision=running['contract_revision'],contract=service._contract(db,project,running['contract_id'],running['contract_revision']))
        db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)',(attempt,project,run,trial,attempt,'queued',encoded(record)))
        service._remember(db,project,'replication:'+run,request_key,payload,record)
        service._event(db,project,run,'replication_admitted',trial_id=trial,execution_attempt_id=attempt,replicates=target)
        return record
