"""One frozen final-test release, admitted only by the human/controller role."""
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .control import ControlError, now
from .contracts import encoded
from .study import completed_material, public_materials
from powerflow_lab.runner import canonical, digest
from asr_supervisor.study import MAX_PAYLOAD_BYTES

CAPABILITY='ood-study-confirmation/1'


def evaluation_reference(config):
    required={'client_root','preparation_report_sha256','image_id','metric_source_sha256','worker_source_sha256'}
    if type(config) is not dict or set(config) not in (required,required|{'isolated_panel'}) or type(config['client_root']) is not str or not Path(config['client_root']).is_absolute():
        raise ControlError('invalid_final_configuration')
    if any(type(config[k]) is not str or re.fullmatch('[a-f0-9]{64}',config[k]) is None for k in required-{'client_root','image_id'}):
        raise ControlError('invalid_final_configuration')
    if type(config['image_id']) is not str or re.fullmatch('sha256:[a-f0-9]{64}',config['image_id']) is None:
        raise ControlError('invalid_final_configuration')
    extra={}
    if 'isolated_panel' in config:
        panel=config['isolated_panel']
        if type(panel) is not dict or set(panel)!={'path','sha256'} or type(panel['path']) is not str or not Path(panel['path']).is_absolute() or type(panel['sha256']) is not str or re.fullmatch('[a-f0-9]{64}',panel['sha256']) is None:
            raise ControlError('invalid_isolated_panel_configuration')
        extra=dict(panel_sha256=panel['sha256'])
    return dict(profile='ood-isolated-confirmation/1' if extra else 'ood-independent-final/1',image_id=config['image_id'],
        metric_source_sha256=config['metric_source_sha256'],worker_source_sha256=config['worker_source_sha256'],
        preparation_report_sha256=config['preparation_report_sha256'],release='one_frozen_protocol',**extra)


def materials(config, study_config):
    root=Path(config['client_root'])
    if root.is_symlink() or root/'public'!=Path(study_config['public_directory']):raise ControlError('final_client_identity_mismatch')
    preparation=root/'preparation-report.json'
    if preparation.is_symlink() or digest(preparation)!=config['preparation_report_sha256']:
        raise ControlError('final_preparation_changed')
    prepared=json.loads(preparation.read_text());result={'case':public_materials(study_config)['case']}
    manifest=json.loads((root/'public/manifest.json').read_text())
    for name,key in (('baseline.json','baseline'),('task.json','task')):
        path=root/'public'/name
        if path.is_symlink() or digest(path)!=manifest['files'][name]:raise ControlError('final_client_material_changed')
        result[key]=json.loads(path.read_text())
    result['criteria']=result.pop('task')['acceptance']
    for split in ('private_id','private_ood'):
        rows=[]
        expected={f'{split}/{i:04d}.json' for i in range(64)}
        actual={name for name in prepared['raw_inventory'] if name.startswith(split+'/')}
        if actual!=expected:raise ControlError('final_split_membership_changed')
        for name in sorted(expected):
            path=root/'raw'/name
            if path.is_symlink() or digest(path)!=prepared['raw_inventory'][name]:raise ControlError('final_raw_material_changed')
            rows.append(json.loads(path.read_text()))
        result[split]=rows
    return result


def submit(service,token,project,run,*,request_key,protocol,hypothesis_ref):
    principal=service._auth(token,project,{'human'})
    service._identity(run,request_key)
    if (type(protocol) is not dict or set(protocol)!={'primary_model','model_trials','proposal_sha256'} or
        type(protocol['model_trials']) is not list or not 1<=len(protocol['model_trials'])<=10 or
        any(type(v) is not str for v in protocol['model_trials']) or len(set(protocol['model_trials']))!=len(protocol['model_trials']) or
        protocol['primary_model'] not in protocol['model_trials'] or type(protocol['proposal_sha256']) is not str or
        re.fullmatch('[a-f0-9]{64}',protocol['proposal_sha256']) is None):
        raise ControlError('invalid_final_protocol')
    payload=[principal['subject'],protocol,hypothesis_ref]
    protocol_hash=hashlib.sha256(canonical(dict(protocol=protocol,hypothesis_ref=hypothesis_ref))).hexdigest()
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        replay=service._replay(db,project,'ood-final:'+run,request_key,payload)
        if replay:return replay
        running=service._run(db,project,run)
        if not service.owning_gate(db,{'project_id':project,'research_run_id':run}):raise ControlError('admission_closed')
        if db.execute("SELECT 1 FROM asr_runtime_sessions WHERE project=? AND run=? AND state!='exited'",(project,run)).fetchone():
            raise ControlError('final_requires_researcher_exit')
        contract=service._contract(db,project,running['contract_id'],running['contract_revision'])
        doc=service._validate_contract(db,project,contract['document'])
        if doc['provenance'].get('capability_profile')!=CAPABILITY:raise ControlError('final_not_authorized')
        lock=running.get('study_final_lock')
        if lock:
            if lock['protocol_sha256']!=protocol_hash:raise ControlError('final_protocol_frozen')
            state=db.execute('SELECT state FROM asr_dispatch WHERE attempt=?',(lock['attempt_id'],)).fetchone()[0]
            if state not in ('failed','cancelled','timed_out','interrupted'):raise ControlError('final_already_admitted_or_released')
        if db.execute("SELECT 1 FROM asr_dispatch WHERE project=? AND run=? AND state NOT IN ('succeeded','failed','cancelled','timed_out','interrupted')",(project,run)).fetchone():
            raise ControlError('final_requires_settled_experiments')
        hypothesis=service._hypothesis_ref(db,project,hypothesis_ref)
        config=doc['provenance']['final']
        isolated='isolated_panel' in config
        if isolated:
            from .isolated_confirmation import load_panel
            data=load_panel(config,doc['provenance']['study'])
        else:
            data=materials(config,doc['provenance']['study'])
        data['models']={};dependencies=[]
        for trial_id in protocol['model_trials']:
            material,reference=completed_material(db,project,run,trial_id)
            if material['variables']!={'operation':'fit'}:raise ControlError('final_requires_trusted_fit')
            data['models'][trial_id]=material['events'][-1]['result']['model'];dependencies.append(reference)
        if isolated:
            from asr_evaluation.isolated_confirmation import verify, sha
            if data['protocol']['primary_model']!=protocol['primary_model'] or set(data['protocol']['models'])!=set(protocol['model_trials']):raise ControlError('isolated_model_selection_changed')
            request=dict(operation='isolated_final',protocol_sha256=sha(data['protocol']))
            verify(request,data)
        else:
            request=dict(operation='final',primary_model=protocol['primary_model'],model_trials=protocol['model_trials'],protocol_sha256=protocol_hash)
        body=canonical(dict(request=request,materials=data))
        from .study import check_limit
        check_limit('study_payload_limit','final_payload_bytes',MAX_PAYLOAD_BYTES,len(body))
        sha=hashlib.sha256(body).hexdigest()
        directory=service.path.parent/'asr-artifacts'/'ood-final'/hashlib.sha256(project.encode()).hexdigest()
        for p in (directory.parent.parent,directory.parent,directory):
            if p.is_symlink():raise ControlError('unsafe_final_artifact_directory')
        directory.mkdir(parents=True,exist_ok=True,mode=0o700);path=directory/(sha+'.json')
        if path.exists() or path.is_symlink():
            if path.is_symlink() or path.stat().st_nlink!=1 or path.read_bytes()!=body:raise ControlError('final_artifact_conflict')
        else:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
            with os.fdopen(fd,'wb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
        timeout=min(300 if isolated else 60,doc['execution_policy']['timeout_seconds'])
        attempt='attempt_'+uuid.uuid4().hex;trial='trial_'+uuid.uuid4().hex
        budget=dict(attempts=1,execution_ms=timeout*1000,sample_proposals=sum(data['protocol']['counts'].values()) if isolated else 0)
        service.budgets.reserve_many_in_transaction(db,project,attempt,budget)
        record=dict(project_id=project,research_run_id=run,trial_id=trial,execution_attempt_id=attempt,
            contract_id=running['contract_id'],contract_revision=running['contract_revision'],contract=contract,
            variables=dict(operation='final'),references=dict(problem=doc['problem_ref'],evaluation=doc['evaluation_ref']),
            execution_request=dict(profile='ood-isolated-confirmation/1' if isolated else 'ood-independent-final/1',image_id=config['image_id'],payload_path=str(path.resolve()),payload_sha256=sha,timeout_seconds=timeout),
            requested_budget=budget,state='queued',created_at=now(),hypothesis_ref=hypothesis,hypothesis_linkage='linked',
            dependencies=dependencies,protocol=protocol,protocol_sha256=protocol_hash)
        db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)',(attempt,project,run,trial,attempt,'queued',encoded(record)))
        running['study_final_lock']=dict(protocol_sha256=protocol_hash,attempt_id=attempt)
        if isolated:running['study_final_lock']['isolated']=True
        db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(running),project,run))
        service._remember(db,project,'ood-final:'+run,request_key,payload,record)
        service._event(db,project,run,'final_protocol_frozen',protocol_sha256=protocol_hash,trial_id=trial,execution_attempt_id=attempt)
        return record
