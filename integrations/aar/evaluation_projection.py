"""Trusted report projection; freeform scientific judgments remain unassessed."""
import copy
import hashlib
import json
from pathlib import Path


def validation_document(job, *, replication='unassessed', comparison=None):
    if not job.get('settled') or not job.get('artifact'):
        raise ValueError('settled_evaluation_required')
    result=job['report'].get('result') or {}
    preserved=result.get('input_preserved')
    equation=result.get('equation_valid')
    operating=result.get('operational_status')
    if operating not in ('satisfied','violated','partially_assessed'):
        operating='unassessed'
    limits=[
        'Automatic mapping leaves experimental design, freeform hypotheses and generalization unassessed.',
        'Equation validity is separate from operating limits; missing thermal ratings remain unassessed.',
        'A material recheck alone is not candidate-method replication.',
    ]
    if comparison:
        limits.append('Replication compares bytewise solution reproducibility under identical frozen source/input in distinct admitted containers; it does not assess generalization.')
    return dict(target=copy.deepcopy(job['target']),
        evaluation_artifact=dict(evaluation_id=job['evaluation_id'],
            evaluation_attempt_id=job['evaluation_attempt_id'],artifact_sha256=job['artifact']['sha256']),
        assessments=dict(experiment_validity='invalid' if preserved is False else 'unassessed',
            equation_validity='valid' if equation is True else 'invalid' if equation is False else 'unassessed',
            operating_checks=operating,replication=replication,generalization='unassessed',hypothesis_assessment='unassessed'),
        provenance=dict(method='Isolated frozen-material evaluator; separate admitted method comparison when explicitly recorded',
            independence=dict(execution='observed',frozen_materials='observed',mathematics='observed'),limits=limits),
        summary=json.dumps(dict(input_preserved=preserved,max_mismatch_pu=result.get('max_mismatch_pu'),
            thermal_limits_unassessed=result.get('thermal_limits_unassessed'),replication_comparison=comparison),sort_keys=True))


def compare_replication(source, replica, source_evaluation, replica_evaluation):
    """Compare exact admitted method runs after both isolated checks completed."""
    from asr_evaluation.replay import freeze_source
    if replica.get('replicates',{}).get('trial_id')!=source['trial_id']:
        raise ValueError('replication_parent_mismatch')
    if any(not job.get('settled') or not job.get('artifact') or job.get('report',{}).get('execution_status')!='succeeded' or not isinstance(job['report'].get('result'),dict)
           for job in (source_evaluation,replica_evaluation)):
        raise ValueError('successful_independent_evaluations_required')
    records=[]
    for trial,job in ((source,source_evaluation),(replica,replica_evaluation)):
        report=(trial.get('execution') or {}).get('report') or {}
        expected=dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],
            manifest_hash=report.get('manifest_hash'),evaluation_ref=trial['references']['evaluation'])
        if job.get('target')!=expected:
            raise ValueError('successful_independent_evaluations_required')
        if trial['dispatch_state']!='succeeded' or report.get('execution_exited') is not True:
            raise ValueError('successful_method_replay_required')
        frozen=freeze_source(Path(report['evidence_path']),report['manifest_hash'],trial_id=trial['trial_id'],
            execution_attempt_id=trial['execution_attempt_id'],research_run_id=trial['research_run_id'])
        request=json.loads(frozen['files']['request.json'])
        if request.get('profile')!='octave-candidate/1':raise ValueError('candidate_method_required')
        records.append(dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],
            evaluation_id=job['evaluation_id'],candidate_sha256=request['candidate']['sha256'],
            request_sha256=hashlib.sha256(frozen['files']['request.json']).hexdigest(),
            input_sha256=frozen['input_sha256'],solution_sha256=frozen['solution_sha256'],
            container_id=trial['execution']['identity']['container_id']))
    first,second=records
    if any(first[key]!=second[key] for key in ('candidate_sha256','request_sha256','input_sha256')) or any(first[key]==second[key] for key in ('trial_id','execution_attempt_id','container_id','evaluation_id')):
        raise ValueError('replication_identity_mismatch')
    return dict(status='consistent' if first['solution_sha256']==second['solution_sha256'] else 'inconsistent',
                protocol='exact-frozen-solution/1',source=first,replica=second)
