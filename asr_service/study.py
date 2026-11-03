"""OOD development admission using the existing Control ledger and dispatch table.

Final-test release is deliberately not supported by this development profile.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

from .contracts import encoded
from .control import ControlError, now
from .budgets import BudgetError
from powerflow_lab.runner import canonical, digest
from asr_supervisor.study import PROFILE, MAX_PAYLOAD_BYTES

CAPABILITY = 'ood-study-development/1'


class StudyRequestError(ControlError):
    """Safe fixed validation explanations, without echoing author code or data."""
    def __init__(self,reason):
        super().__init__('invalid_study_request')
        self.args=(reason,)
        self.details=dict(reason=reason,recoverable=True,scope='request',task_retained=True)


def check_limit(code, dimension, limit, requested):
    if requested > limit:
        raise BudgetError(code, details=dict(dimension=dimension, limit=limit, spent=0, reserved=0,
            available=limit, requested=requested, scope=CAPABILITY,
            recovery='Keep the task and accepted trials. Split this request or obtain an explicit profile revision; no automatic retry.'))


def expected_references(config):
    if type(config) is not dict or set(config) != {'public_directory', 'public_manifest_sha256', 'image_id', 'validator_sha256'}:
        raise ControlError('invalid_study_configuration')
    if (type(config['public_directory']) is not str or not Path(config['public_directory']).is_absolute() or
        any(type(config[k]) is not str or re.fullmatch('[a-f0-9]{64}', config[k]) is None
            for k in ('public_manifest_sha256', 'validator_sha256')) or
        type(config['image_id']) is not str or re.fullmatch('sha256:[a-f0-9]{64}', config['image_id']) is None):
        raise ControlError('invalid_study_configuration')
    return dict(problem=dict(profile='ood-client-training/1', manifest_sha256=config['public_manifest_sha256']),
                reference=dict(profile='ood-label-worker/1', image_id=config['image_id']),
                evaluation=dict(profile='ood-development-equations/1', validator_sha256=config['validator_sha256'],
                                tolerance_pu=1e-7, final_test_authorized=False))


def public_materials(config):
    root = Path(config['public_directory'])
    manifest_path = root / 'manifest.json'
    if root.is_symlink() or manifest_path.is_symlink() or digest(manifest_path) != config['public_manifest_sha256']:
        raise StudyRequestError('client material manifest changed')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema') != 'asr-client-package/1':
        raise StudyRequestError('unsupported client material manifest')
    result = {}
    for name in ('case', 'train', 'id_dev', 'diagnostic'):
        path = root / (name + '.json')
        if path.is_symlink() or digest(path) != manifest['files'].get(path.name):
            raise StudyRequestError('client material changed: ' + name)
        result[name] = json.loads(path.read_text())
    return result


def coordinate(x):
    if (type(x) is not list or len(x) != 3 or
        any(type(v) not in (int, float) or not math.isfinite(v) or not .7 <= v <= 1.6 for v in x)):
        raise StudyRequestError('three finite coordinates in [0.7,1.6] required')
    return tuple(float(v) for v in x)


def completed_material(db, project, run, trial_id):
    row = db.execute('SELECT attempt,state,record FROM asr_dispatch WHERE project=? AND run=? AND trial=?',
                     (project, run, trial_id)).fetchone()
    if not row or row[1] != 'succeeded':
        raise ControlError('completed_label_trial_required')
    trial = json.loads(row[2])
    if trial['execution_request'].get('profile') != PROFILE:
        raise ControlError('study_trial_required')
    execution = db.execute('SELECT record FROM asr_executions WHERE attempt=?', (row[0],)).fetchone()
    report = json.loads(execution[0])['report'] if execution else None
    if not report or report['status'] != 'succeeded':
        raise ControlError('label_execution_report_required')
    root = Path(report['evidence_path'])
    if root.is_symlink() or digest(root / 'manifest.json') != report['manifest_hash']:
        raise ControlError('label_evidence_corrupt')
    manifest = json.loads((root / 'manifest.json').read_text())
    from asr_supervisor.supervisor import publication_inventory
    if manifest['artifacts'] != publication_inventory(root):
        raise ControlError('label_evidence_corrupt')
    events = json.loads((root / 'study-events.json').read_text())
    return dict(variables=trial['variables'], events=events), dict(
        trial_id=trial_id, execution_attempt_id=row[0], manifest_hash=report['manifest_hash'])


def submit(service, token, project, run, *, request_key, request, timeout_seconds, hypothesis_ref):
    principal = service._auth(token, project, {'researcher', 'human'})
    service._identity(run, request_key)
    payload = [principal['subject'], request, timeout_seconds, hypothesis_ref]
    encoded(payload)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        replay = service._replay(db, project, 'study:' + run, request_key, payload)
        if replay:
            return replay
        running = service._run(db, project, run)
        if running.get('study_final_lock'):raise ControlError('final_protocol_frozen')
        if not service.owning_gate(db, {'project_id': project, 'research_run_id': run}):
            raise ControlError('admission_closed')
        hypothesis = service._hypothesis_ref(db, project, hypothesis_ref)
        contract = service._contract(db, project, running['contract_id'], running['contract_revision'])
        doc = service._validate_contract(db, project, contract['document'])
        if doc['provenance'].get('capability_profile') != CAPABILITY:
            raise ControlError('capability_unavailable')
        config = doc['provenance']['study']
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise StudyRequestError('study timeout exceeds admitted execution policy')
        check_limit('study_timeout_limit','study_timeout_seconds',min(300,doc['execution_policy']['timeout_seconds']),timeout_seconds)
        materials = public_materials(config)
        dependencies = []
        proposed = 0
        if type(request) is not dict:
            raise StudyRequestError('study request must be an object')
        operation = request.get('operation')
        if operation == 'label':
            if set(request) != {'operation', 'purpose', 'coordinates'} or request['purpose'] not in ('augmentation', 'probe'):
                raise StudyRequestError('invalid label request')
            if type(request['coordinates']) is not list or not request['coordinates']:
                raise StudyRequestError('label batch requires 1..64 proposals; split larger batches')
            check_limit('study_batch_limit','study_batch_samples',64,len(request['coordinates']))
            points = [coordinate(x) for x in request['coordinates']]
            if len(set(points)) != len(points):
                raise StudyRequestError('duplicate proposed coordinates')
            exposed = {coordinate(r['x']) for name in ('train', 'id_dev', 'diagnostic') for r in materials[name]}
            if any(point in exposed for point in points):
                raise StudyRequestError('proposal duplicates original training/development data')
            # A fresh probe must remain separate from training acquisition.
            # Reuse an existing label trial as a dependency rather than silently
            # relabelling its coordinates under a different role.
            for body, in db.execute('SELECT record FROM asr_dispatch WHERE project=? AND run=?', (project, run)):
                prior = json.loads(body)
                frozen = prior.get('execution_request', {})
                if frozen.get('profile') == PROFILE and prior['variables'].get('operation') == 'label':
                    from asr_supervisor.study import frozen_payload
                    previous = json.loads(frozen_payload(frozen['payload_path'], frozen['payload_sha256']))
                    exposed.update(coordinate(x) for x in previous['request']['coordinates'])
            if any(point in exposed for point in points):
                raise StudyRequestError('proposal duplicates a prior label/probe trial; preserve original purpose and evidence')
            proposed = len(points)
            materials = {'case': materials['case']}
            worker_request = request
            variables = dict(operation=operation, purpose=request['purpose'])
        elif operation == 'analysis':
            if set(request) != {'operation', 'source', 'input_trials'} or type(request['source']) is not str or not request['source']:
                raise StudyRequestError('analysis requires main(data) source, at most 65536 UTF-8 bytes')
            check_limit('study_source_limit','study_source_bytes',65536,len(request['source'].encode()))
            ids = request['input_trials']
            if type(ids) is not list or any(type(x) is not str for x in ids) or len(set(ids)) != len(ids):
                raise StudyRequestError('analysis accepts at most 12 distinct completed input trials')
            check_limit('study_dependency_limit','study_input_trials',12,len(ids))
            materials['trials'] = {}
            for trial_id in ids:
                material, reference = completed_material(db, project, run, trial_id)
                materials['trials'][trial_id] = material
                dependencies.append(reference)
            worker_request = {key: request[key] for key in ('operation', 'source')}
            variables = dict(operation=operation)
        elif operation == 'fit':
            if set(request) != {'operation', 'augmentation_trials'} or type(request['augmentation_trials']) is not list:
                raise StudyRequestError('fit requires augmentation trial references only')
            ids = request['augmentation_trials']
            if any(type(x) is not str for x in ids) or len(set(ids)) != len(ids):
                raise StudyRequestError('fit accepts at most 12 distinct label batches (768 proposals)')
            check_limit('study_dependency_limit','study_input_trials',12,len(ids))
            materials['augmentation'] = []
            for trial_id in ids:
                material, reference = completed_material(db, project, run, trial_id)
                if material['variables'] != {'operation': 'label', 'purpose': 'augmentation'}:
                    raise ControlError('augmentation_label_trial_required')
                batch = dict(purpose='augmentation', rows=[e['row'] for e in material['events'] if e['type'] == 'sample'])
                materials['augmentation'].append(batch); dependencies.append(reference)
            worker_request = dict(operation='fit')
            variables = dict(operation=operation)
        else:
            raise ControlError('capability_unavailable')
        body = canonical(dict(request=worker_request, materials=materials))
        check_limit('study_payload_limit','study_payload_bytes',MAX_PAYLOAD_BYTES,len(body))
        sha = hashlib.sha256(body).hexdigest()
        root = service.path.parent / 'asr-artifacts' / 'study' / hashlib.sha256(project.encode()).hexdigest()
        for parent in (root.parent.parent, root.parent, root):
            if parent.is_symlink():
                raise StudyRequestError('unsafe study artifact directory')
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = root / (sha + '.json')
        if path.exists() or path.is_symlink():
            if path.is_symlink() or path.stat().st_nlink != 1 or path.read_bytes() != body:
                raise StudyRequestError('study artifact conflict')
        else:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body); stream.flush(); os.fsync(stream.fileno())
        attempt = 'attempt_' + uuid.uuid4().hex
        trial = 'trial_' + uuid.uuid4().hex
        budget = dict(attempts=1, execution_ms=timeout_seconds * 1000, sample_proposals=proposed)
        service.budgets.reserve_many_in_transaction(db, project, attempt, budget)
        execution_request = dict(profile=PROFILE, image_id=config['image_id'], payload_path=str(path.resolve()),
                                 payload_sha256=sha, timeout_seconds=timeout_seconds)
        record = dict(project_id=project, research_run_id=run, trial_id=trial, execution_attempt_id=attempt,
                      contract_id=running['contract_id'], contract_revision=running['contract_revision'], contract=contract,
                      variables=variables, references=dict(problem=doc['problem_ref'], evaluation=doc['evaluation_ref']),
                      requested_budget=budget, execution_request=execution_request, state='queued', created_at=now(),
                      hypothesis_ref=hypothesis, hypothesis_linkage='linked', dependencies=dependencies,
                      proposal_accounting='Conservative permits: all admitted proposals charged once execution starts; partial results retained.')
        db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)', (attempt, project, run, trial, attempt, 'queued', encoded(record)))
        service._remember(db, project, 'study:' + run, request_key, payload, record)
        service._event(db, project, run, 'trial_admitted', trial_id=trial, execution_attempt_id=attempt, profile=PROFILE)
        return record
