"""Task authority for existing experimental admission; no new execution ledger."""
import json

from .organization import latest, member, require

OPERATIONS = {'study:label', 'study:analysis', 'study:fit'}
TERMINAL = {'succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'}


def enabled(db, project, run):
    return latest(db, project, run, 'policy', 'capacity') is not None


def reject_legacy(db, project, run):
    require(not enabled(db, project, run), 'organization_operation_unavailable')


def admit(db, project, run, principal, reference, operation):
    if not enabled(db, project, run):
        require(reference is None, 'organization_policy_required')
        return None
    require(type(reference) is dict and set(reference) == {'task_id','revision'}, 'organization_task_required')
    require(type(reference['task_id']) is str and type(reference['revision']) is int, 'organization_task_required')
    task = latest(db, project, run, 'task', reference['task_id'])
    require(task is not None and task['revision'] == reference['revision'], 'organization_task_stale')
    doc = task['document']
    require(principal['role'] == 'researcher' and principal['subject'] == doc['assignee'], 'organization_task_owner_required')
    role = member(db, project, run, principal['subject'])
    require(role in ('lead','worker'), 'organization_task_owner_required')
    require(doc['status'] == 'in_progress', 'organization_task_not_active')
    require(operation in OPERATIONS and operation in doc.get('experiment_operations', []), 'organization_operation_forbidden')
    direction = latest(db, project, run, 'direction', doc['direction_id'])
    require(direction is not None and direction['document']['status'] == 'active', 'organization_work_paused')
    return dict(schema='asr-task-experiment-binding/1', subject=principal['subject'], operation=operation,
                member=latest(db, project, run, 'member', principal['subject']), direction=direction, task=task)


def require_idle(db, project, run, task_id):
    for state, raw in db.execute('SELECT state,record FROM asr_dispatch WHERE project=? AND run=?', (project,run)):
        binding = json.loads(raw).get('organization_task')
        if binding and binding['task']['entity_id'] == task_id:
            require(state in TERMINAL, 'task_experiments_unsettled')
