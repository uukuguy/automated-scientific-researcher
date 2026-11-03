"""Explicit frozen sharing across acquisition arms, never blanket dedup bypass."""
import hashlib
import json
import re

from .organization import require
from powerflow_lab.runner import canonical


def fingerprint(policy):
    return hashlib.sha256(canonical(policy)).hexdigest() if policy is not None else None


def identifier(value):
    return type(value) is str and bool(value.strip())


def validate(policy, budget):
    from .study import coordinate, check_limit
    require(type(policy) is dict and set(policy)=={'schema','proposal_sha256','purpose','charging','groups'},'invalid_paired_protocol')
    require(policy['schema']=='asr-paired-sampling/1' and policy['purpose']=='augmentation'
            and policy['charging']=='each_slot_no_retries','invalid_paired_protocol')
    require(type(policy['proposal_sha256']) is str and re.fullmatch('[a-f0-9]{64}',policy['proposal_sha256']) is not None,'invalid_paired_protocol')
    groups=policy['groups'];require(type(groups) is dict and bool(groups),'invalid_paired_protocol')
    seen=set();slots=attempts=0
    for group_id,group in groups.items():
        require(identifier(group_id) and type(group) is dict and set(group)=={'blocks','arms'},'invalid_paired_protocol')
        blocks,arms=group['blocks'],group['arms']
        require(type(blocks) is dict and bool(blocks) and type(arms) is dict and bool(arms),'invalid_paired_protocol')
        used=set()
        for block_id,points in blocks.items():
            require(identifier(block_id) and type(points) is list and bool(points),'invalid_paired_protocol')
            for point in points:
                value=coordinate(point)
                require(value not in seen,'paired_coordinate_collision');seen.add(value)
        for arm_id,names in arms.items():
            require(identifier(arm_id) and type(names) is list and bool(names)
                    and all(type(x) is str and x in blocks for x in names) and len(names)==len(set(names)),'invalid_paired_protocol')
            size=sum(len(blocks[x]) for x in names)
            check_limit('study_batch_limit','study_batch_samples',64,size)
            used.update(names);slots+=size;attempts+=1
        require(used==set(blocks),'paired_unused_block')
    for dimension, requested in (('sample_proposals', slots), ('attempts', attempts)):
        limit = budget.get(dimension, 0)
        if requested > limit:
            from .control import ControlError
            error = ControlError('paired_budget_insufficient')
            error.details = dict(dimension=dimension, limit=limit, requested=requested,
                scope='contract_proposal', recoverable=True, task_retained=True,
                recovery='Revise the frozen proposal or explicitly authorize sufficient budget; no execution was started.')
            raise error


def check_run(db,project,run,policy):
    for raw, in db.execute('SELECT record FROM asr_dispatch WHERE project=? AND run=?',(project,run)):
        previous=json.loads(raw).get('paired_sampling')
        if previous:require(previous['protocol_sha256']==fingerprint(policy),'paired_protocol_changed')


def label_binding(db,project,run,policy,request):
    if policy is None:
        require('paired_batch' not in request,'paired_protocol_required')
        return None
    reference=request.get('paired_batch')
    require(type(reference) is dict and set(reference)=={'group_id','arm_id'},'paired_batch_required')
    require(all(identifier(x) for x in reference.values()),'paired_batch_required')
    group=policy['groups'].get(reference['group_id'])
    require(group is not None and reference['arm_id'] in group['arms'],'paired_batch_unknown')
    names=group['arms'][reference['arm_id']]
    expected=[point for name in names for point in group['blocks'][name]]
    require(request.get('purpose')=='augmentation' and request.get('coordinates')==expected,'paired_coordinates_changed')
    result=dict(protocol_sha256=fingerprint(policy),group_id=reference['group_id'],arm_id=reference['arm_id'],
        slot_ids=[f'{name}/{i}' for name in names for i in range(len(group['blocks'][name]))],charging='each_slot_no_retries')
    for raw, in db.execute('SELECT record FROM asr_dispatch WHERE project=? AND run=?',(project,run)):
        old=json.loads(raw);binding=old.get('paired_sampling')
        if binding and old['variables'].get('operation')=='label':
            require((binding['group_id'],binding['arm_id'])!=(result['group_id'],result['arm_id']),'paired_batch_already_submitted')
    return result


def shared_pair(current, previous):
    return bool(current and previous and current['protocol_sha256']==previous['protocol_sha256']
                and current['group_id']==previous['group_id'] and current['arm_id']!=previous['arm_id'])


def fit_binding(db,project,run,policy,ids):
    if policy is None:return None
    if not ids:return dict(protocol_sha256=fingerprint(policy),group_id=None,arm_id=None,slot_ids=[],charging='baseline_no_augmentation')
    require(len(ids)==1,'paired_fit_one_arm_required')
    row=db.execute('SELECT record FROM asr_dispatch WHERE project=? AND run=? AND trial=?',(project,run,ids[0])).fetchone()
    binding=json.loads(row[0]).get('paired_sampling') if row else None
    require(binding is not None and binding['protocol_sha256']==fingerprint(policy) and binding['arm_id'] is not None,'paired_fit_one_arm_required')
    return binding
