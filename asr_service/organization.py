"""Versioned organization declarations in Control's existing transaction ledger.

No model launcher, experiment scheduler or process-exit authority lives here.
Task completion is an attributed claim; trial evidence remains independently owned.
"""
import copy
import hashlib
import json

from .contracts import encoded
from .control import ControlError, now

TERMINAL_TASKS = {'completed', 'cancelled'}
KINDS = {'policy', 'member', 'direction', 'task', 'message'}


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS asr_organization(
        seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL,
        run TEXT NOT NULL, kind TEXT NOT NULL, entity TEXT NOT NULL,
        revision INTEGER NOT NULL, record TEXT NOT NULL,
        UNIQUE(project,run,kind,entity,revision))''')


def latest(db, project, run, kind, entity):
    row = db.execute('SELECT record FROM asr_organization WHERE project=? AND run=? AND kind=? AND entity=? ORDER BY revision DESC LIMIT 1',
                     (project, run, kind, entity)).fetchone()
    return json.loads(row[0]) if row else None


def current(db, project, run, kind):
    rows = db.execute('''SELECT a.record FROM asr_organization a JOIN
        (SELECT entity,MAX(revision) revision FROM asr_organization
         WHERE project=? AND run=? AND kind=? GROUP BY entity) b
        ON a.entity=b.entity AND a.revision=b.revision
        WHERE a.project=? AND a.run=? AND a.kind=?''', (project, run, kind, project, run, kind))
    return [json.loads(row[0]) for row in rows]


def member(db, project, run, subject):
    item = latest(db, project, run, 'member', subject)
    if not item or not item['document']['enabled']:
        raise ControlError('forbidden')
    return item['document']['role']


def principal_role(db, project, run, principal):
    if principal['role'] == 'human':
        return 'human'
    if principal['role'] != 'researcher':
        raise ControlError('forbidden')
    return member(db, project, run, principal['subject'])


def require(condition, code='invalid_organization_document'):
    if not condition:
        raise ControlError(code)


def text(value):
    return type(value) is str and bool(value.strip())


def capacity(dimension, limit, requested):
    if requested <= limit:
        return
    error = ControlError('organization_capacity')
    error.details = dict(dimension=dimension, limit=limit, requested=requested,
        unit='active_members', scope='research_run', action='request_deferred',
        recovery='Preserve accepted work. Wait for completion or explicitly revise capacity; do not duplicate tasks.')
    raise error


def evidence(db, project, run, document):
    refs = document.get('evidence_trial_ids')
    require(type(refs) is list and all(text(x) for x in refs) and len(refs) == len(set(refs)))
    result = []
    for trial in refs:
        row = db.execute('SELECT attempt,state FROM asr_dispatch WHERE project=? AND run=? AND trial=?',
                         (project, run, trial)).fetchone()
        require(row is not None and row[1] in ('succeeded','failed','timed_out','interrupted'), 'organization_evidence_unavailable')
        row2 = db.execute('SELECT record FROM asr_executions WHERE attempt=?', (row[0],)).fetchone()
        execution = json.loads(row2[0]) if row2 else {}
        report = execution.get('report') or {}
        require(bool(report.get('manifest_hash')), 'organization_evidence_unavailable')
        # Resolve the identity, not an agent's score. Full integrity/validation
        # remains with the evidence publisher and independent evaluator.
        result.append(dict(trial_id=trial, execution_attempt_id=row[0], manifest_hash=report['manifest_hash']))
    return result


def check_capacity(db, project, run, policy, *, replacement=None):
    directions = {x['entity_id']: x['document'] for x in current(db, project, run, 'direction')}
    tasks = {x['entity_id']: x['document'] for x in current(db, project, run, 'task')}
    if replacement:
        kind, entity, doc = replacement
        if kind == 'direction': directions[entity] = doc
        if kind == 'task': tasks[entity] = doc
    leads = {x['owner'] for x in directions.values() if x['status'] == 'active'}
    workers = {x['assignee'] for x in tasks.values() if x['status'] == 'in_progress'
               and member(db, project, run, x['assignee']) == 'worker'}
    capacity('active_leads', policy['max_active_leads'], len(leads))
    capacity('active_workers', policy['max_active_workers'], len(workers))


def validate(db, project, run, kind, entity, doc, previous, role, subject, run_state):
    old = previous['document'] if previous else None
    if kind == 'policy':
        require(role == 'human', 'forbidden')
        require(entity == 'capacity' and set(doc) == {'max_active_leads','max_active_workers'})
        require(all(type(v) is int and v > 0 for v in doc.values()))
        if not old:
            require(db.execute("SELECT 1 FROM asr_runtime_sessions WHERE project=? AND run=? AND state!='exited'", (project,run)).fetchone() is None,
                    'organization_runtime_reconciliation_required')
            require(not any(state not in ('succeeded','failed','cancelled','timed_out','interrupted')
                            for state, in db.execute('SELECT state FROM asr_dispatch WHERE project=? AND run=?', (project,run))),
                    'organization_experiment_reconciliation_required')
        check_capacity(db, project, run, doc)
        return []
    policy = latest(db, project, run, 'policy', 'capacity')
    require(policy is not None, 'organization_policy_required')
    if kind == 'member':
        require(role == 'human', 'forbidden')
        require(set(doc) == {'role','enabled'} and doc['role'] in ('organizer','lead','worker') and type(doc['enabled']) is bool)
        if old:
            active = [json.loads(row[0]) for row in db.execute(
                "SELECT record FROM asr_runtime_sessions WHERE project=? AND run=? AND state!='exited'", (project,run))]
            require(not any(x.get('organization_binding',{}).get('subject') == entity for x in active), 'member_runtime_active')
            busy = any(x['document']['owner'] == entity and x['document']['status'] != 'closed'
                       for x in current(db, project, run, 'direction'))
            busy |= any(x['document']['assignee'] == entity and x['document']['status'] not in TERMINAL_TASKS
                        for x in current(db, project, run, 'task'))
            require(not busy, 'member_has_open_work')
        if doc == dict(role='organizer', enabled=True):
            require(not any(x['entity_id'] != entity and x['document'] == doc for x in current(db, project, run, 'member')),
                    'organizer_already_bound')
        return []
    resolved = evidence(db, project, run, doc)
    if kind == 'direction':
        require(set(doc) == {'title','question','owner','status','rationale','evidence_trial_ids'})
        require(all(text(doc[k]) for k in ('title','question','owner','rationale')))
        require(doc['status'] in ('proposed','active','paused','closed'))
        require(member(db, project, run, doc['owner']) == 'lead', 'direction_lead_required')
        require(role in ('human','organizer') or (role == 'lead' and doc['owner'] == subject
                and doc['status'] == 'proposed' and (old is None or old['status'] == 'proposed' and old['owner'] == subject)), 'forbidden')
        require(not old or old['status'] != 'closed', 'direction_terminal')
        if old and (any(old[k] != doc[k] for k in ('owner','title','question')) or
                    doc['status'] != old['status'] and doc['status'] in ('paused','closed','proposed')):
            require(not any(x['document']['direction_id'] == entity and x['document']['status'] not in TERMINAL_TASKS
                            for x in current(db, project, run, 'task')), 'direction_has_open_tasks')
        if doc['status'] == 'active': require(run_state == 'running', 'organization_work_paused')
        check_capacity(db, project, run, policy['document'], replacement=(kind,entity,doc))
    elif kind == 'task':
        require(set(doc)-{'experiment_operations'} == {'direction_id','assignee','title','instructions','status','result','evidence_trial_ids'})
        from .organization_experiments import OPERATIONS, require_idle
        operations=doc.get('experiment_operations', [])
        require(type(operations) is list and all(type(x) is str and x in OPERATIONS for x in operations)
                and len(operations)==len(set(operations)))
        require(all(text(doc[k]) for k in ('direction_id','assignee','title','instructions')) and type(doc['result']) is str)
        require(doc['status'] in ('assigned','in_progress','completed','cancelled'))
        direction = latest(db, project, run, 'direction', doc['direction_id'])
        require(direction is not None, 'direction_not_found')
        require(member(db, project, run, doc['assignee']) in ('lead','worker'), 'task_executor_required')
        manager = role in ('human','organizer') or role == 'lead' and direction['document']['owner'] == subject
        if old:
            require(old['status'] not in TERMINAL_TASKS, 'task_terminal')
            require(doc['direction_id'] == old['direction_id'], 'task_direction_immutable')
            if old['status'] == 'in_progress':
                require(doc.get('experiment_operations',[]) == old.get('experiment_operations',[]), 'task_in_progress')
                require(all(doc[k] == old[k] for k in ('direction_id','assignee','title','instructions')), 'task_in_progress')
                require(subject == old['assignee'], 'forbidden')
                require(doc['status'] in TERMINAL_TASKS, 'invalid_task_transition')
            elif doc['status'] == 'in_progress':
                require(doc.get('experiment_operations',[]) == old.get('experiment_operations',[]), 'forbidden')
                require(subject == old['assignee'] and all(doc[k] == old[k] for k in ('assignee','title','instructions')), 'forbidden')
            else:
                require(manager, 'forbidden')
                require(doc['status'] in ('assigned','cancelled'), 'invalid_task_transition')
        else:
            require(manager, 'forbidden')
            require(doc['status'] == 'assigned' and not doc['result'], 'invalid_task_transition')
        if doc['status'] not in TERMINAL_TASKS:
            require(direction['document']['status'] == 'active' and run_state == 'running', 'organization_work_paused')
            require(not doc['result'])
        else:
            require(text(doc['result']), 'task_result_required')
            require_idle(db, project, run, entity)
        if doc['status'] == 'in_progress':
            require(not any(x['entity_id'] != entity and x['document']['status'] == 'in_progress'
                            and x['document']['assignee'] == doc['assignee'] for x in current(db, project, run, 'task')), 'member_already_working')
        check_capacity(db, project, run, policy['document'], replacement=(kind,entity,doc))
    elif kind == 'message':
        require(not previous, 'message_immutable')
        require(set(doc) == {'recipients','text','evidence_trial_ids'} and text(doc['text']))
        require(type(doc['recipients']) is list and len(doc['recipients']) > 0 and
                all(text(x) for x in doc['recipients']) and len(set(doc['recipients'])) == len(doc['recipients']))
        for recipient in doc['recipients']: member(db, project, run, recipient)
    return resolved


def change(service, token, project, run, *, kind, entity_id, expected_revision, idempotency_key, document):
    principal = service._auth(token, project, {'human','researcher'})
    service._identity(run, entity_id, idempotency_key)
    service._revision(expected_revision)
    require(kind in KINDS and type(document) is dict)
    document = copy.deepcopy(document)
    body = encoded(document).encode()
    payload = [principal['subject'],kind,entity_id,expected_revision,document]
    try:
        with service._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = service._run(db, project, run)
            role = principal_role(db, project, run, principal)
            replay = service._replay(db, project, 'organization:'+run, idempotency_key, payload)
            if replay: return replay
            require(state['state'] in ('running','paused'), 'organization_run_closed')
            document_limit=service.artifact_io_policy['limits']['organization_document_bytes']['value']
            if len(body) > document_limit:
                error = ControlError('organization_document_limit')
                error.details = dict(dimension='organization_document_bytes', limit=document_limit, capacity_policy_sha256=service.artifact_io_policy['sha256'],
                    requested=len(body), unit='bytes', scope='organization_record', action='request_deferred',
                    recovery='Preserve the task. Store large code/data as governed artifacts and submit a concise description with evidence references.')
                raise error
            previous = latest(db, project, run, kind, entity_id)
            require(expected_revision == (previous['revision'] if previous else 0), 'revision_conflict')
            resolved = validate(db, project, run, kind, entity_id, document, previous, role, principal['subject'], state['state'])
            record = dict(schema='asr-organization-record/1', project_id=project, research_run_id=run,
                kind=kind, entity_id=entity_id, revision=expected_revision+1, document=document,
                author=principal['subject'], author_role=role, evidence=resolved, created_at=now())
            cursor = db.execute('INSERT INTO asr_organization(project,run,kind,entity,revision,record) VALUES (?,?,?,?,?,?)',
                               (project,run,kind,entity_id,record['revision'],encoded(record)))
            record['seq'] = cursor.lastrowid
            db.execute('UPDATE asr_organization SET record=? WHERE seq=?', (encoded(record),record['seq']))
            service._remember(db, project, 'organization:'+run, idempotency_key, payload, record)
            service._event(db, project, run, 'organization_recorded', kind=kind, entity_id=entity_id,
                           revision=record['revision'], record_seq=record['seq'], author=principal['subject'])
            return record
    except ControlError as error:
        if hasattr(error, 'details'):
            # The failed mutation rolls back; its rejection survives separately.
            with service._connect() as db:
                service._event(db, project, run, 'organization_request_deferred',
                    author=principal['subject'], kind=kind, entity_id=entity_id, expected_revision=expected_revision,
                    request_key=idempotency_key, document_sha256=hashlib.sha256(body).hexdigest(),
                    reason=error.code, details=error.details)
        raise


def records(service, token, project, run, *, after=0, limit=None):
    principal = service._auth(token, project, {'human','researcher'})
    caps=service.artifact_io_policy['limits']
    limit=caps['organization_page_default_records']['value'] if limit is None else limit
    maximum=caps['organization_page_max_records']['value']
    require(type(after) is int and after >= 0 and type(limit) is int and limit >= 1, 'invalid_organization_page')
    if limit > maximum:
        error = ControlError('invalid_organization_page')
        error.details = dict(dimension='organization_page_records', limit=maximum, requested=limit, capacity_policy_sha256=service.artifact_io_policy['sha256'],
            unit='records', scope='organization_read', action='request_deferred',
            recovery=f'Read at most {maximum} records per page and follow next_after while has_more is true; no history was discarded.')
        with service._connect() as db:
            service._run(db, project, run)
            principal_role(db, project, run, principal)
            service._event(db, project, run, 'organization_request_deferred', author=principal['subject'],
                after=after, reason=error.code, details=error.details)
        raise error
    with service._connect() as db:
        service._run(db, project, run)
        principal_role(db, project, run, principal)
        rows = db.execute('SELECT record FROM asr_organization WHERE project=? AND run=? AND seq>? ORDER BY seq LIMIT ?',
                          (project,run,after,limit+1)).fetchall()
    items = [json.loads(x[0]) for x in rows[:limit]]
    return dict(records=items, next_after=items[-1]['seq'] if items else after, has_more=len(rows)>limit,
                boundary='Shared organization history; task results are claims, not execution exit proof or scientific validation.')
