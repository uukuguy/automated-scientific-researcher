"""Immutable evaluator attestations, separate from execution and author findings.

Authentication identifies the report publisher. It does not prove OS isolation,
mathematical independence, replication or scientific support. Those observations
and their limitations are recorded explicitly; control only verifies references
and frozen raw bytes here.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from .contracts import encoded
from .references import ReferenceStore


class ValidationError(ValueError):
    def __init__(self, code):
        self.code=code
        super().__init__(code)


_TEXT={'type':'string','minLength':1,'maxLength':16384}
_ID={'type':'string','minLength':1,'maxLength':256}
_HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
_INDEPENDENCE={'enum':['observed','not_observed','unknown']}
VALIDATION_SCHEMA={
    '$schema':'https://json-schema.org/draft/2020-12/schema',
    '$id':'asr-validation-document/1',
    'type':'object','additionalProperties':False,
    'required':['target','assessments','provenance','summary'],
    'dependentRequired':{'hypothesis_ref':['analysis_timing'],'analysis_timing':['hypothesis_ref']},
    'properties':{
        'target':{'type':'object','additionalProperties':False,
                  'required':['trial_id','execution_attempt_id','manifest_hash','evaluation_ref'],
                  'properties':{'trial_id':_ID,'execution_attempt_id':_ID,'manifest_hash':_HASH,'evaluation_ref':_HASH}},
        'assessments':{'type':'object','additionalProperties':False,
                       'required':['experiment_validity','equation_validity','operating_checks','replication','generalization','hypothesis_assessment'],
                       'properties':{
                           'experiment_validity':{'enum':['valid','invalid','unassessed']},
                           'equation_validity':{'enum':['valid','invalid','unassessed']},
                           'operating_checks':{'enum':['satisfied','violated','partially_assessed','unassessed']},
                           'replication':{'enum':['consistent','inconsistent','unassessed']},
                           'generalization':{'enum':['supported','unsupported','unassessed']},
                           'hypothesis_assessment':{'enum':['supports','opposes','inconclusive','unassessed']},
                       }},
        'provenance':{'type':'object','additionalProperties':False,
                      'required':['method','independence','limits'],
                      'properties':{
                          'method':_TEXT,
                          'independence':{'type':'object','additionalProperties':False,
                                          'required':['execution','frozen_materials','mathematics'],
                                          'properties':{axis:_INDEPENDENCE for axis in ('execution','frozen_materials','mathematics')}},
                          'limits':{'type':'array','minItems':1,'maxItems':64,'items':_TEXT},
                      }},
        'summary':_TEXT,
        'evaluation_artifact':{'type':'object','additionalProperties':False,
                               'required':['evaluation_id','evaluation_attempt_id','artifact_sha256'],
                               'properties':{'evaluation_id':_ID,'evaluation_attempt_id':_ID,'artifact_sha256':_HASH}},
        'hypothesis_ref':{'type':'object','additionalProperties':False,
                          'required':['project_id','hypothesis_id','revision'],
                          'properties':{'project_id':_ID,'hypothesis_id':_ID,'revision':{'type':'integer','minimum':1,'maximum':2**63-1}}},
        'analysis_timing':{'enum':['prospective','post_hoc']},
    },
}
_VALIDATOR=Draft202012Validator(VALIDATION_SCHEMA)


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS asr_validations(
        project TEXT NOT NULL, run TEXT NOT NULL, validation_id TEXT NOT NULL,
        record TEXT NOT NULL, PRIMARY KEY(project,validation_id))''')


def _document(document):
    if next(_VALIDATOR.iter_errors(document),None) is not None:raise ValidationError('invalid_validation')
    if any(not value.strip() for value in [document['summary'],document['provenance']['method'],*document['provenance']['limits']]):raise ValidationError('invalid_validation')
    axes=document['assessments']
    if axes['experiment_validity']!='valid' and (axes['hypothesis_assessment'] in ('supports','opposes') or axes['generalization']=='supported'):
        raise ValidationError('invalid_experiment_assessment')
    if axes['hypothesis_assessment']!='unassessed' and 'hypothesis_ref' not in document:raise ValidationError('hypothesis_ref_required')
    return copy.deepcopy(document)


def _evidence(db,project,run,target):
    """Bind exact terminal identities and verify the published artifact inventory."""
    row=db.execute('SELECT attempt,state,record FROM asr_dispatch WHERE project=? AND run=? AND trial=?',(project,run,target['trial_id'])).fetchone()
    if row is None:raise ValidationError('trial_not_found')
    if row[0]!=target['execution_attempt_id']:raise ValidationError('validation_target_conflict')
    if row[1] not in ('succeeded','failed','cancelled','timed_out','interrupted'):raise ValidationError('evidence_not_published')
    trial=json.loads(row[2])
    if trial['references']['evaluation']!=target['evaluation_ref']:raise ValidationError('evaluation_ref_conflict')
    ReferenceStore.get_in_transaction(db,project,'evaluation',target['evaluation_ref'])
    from asr_supervisor.store import ExecutionStore
    execution=ExecutionStore._read(db,target['execution_attempt_id'])
    if (execution['project'],execution['run'],execution['trial'],execution['attempt'])!=(project,run,target['trial_id'],target['execution_attempt_id']):raise ValidationError('validation_target_conflict')
    report=execution.get('report')
    if not report or report.get('execution_exited') is not True:raise ValidationError('evidence_not_published')
    if report.get('manifest_hash')!=target['manifest_hash']:raise ValidationError('manifest_hash_conflict')
    try:
        from powerflow_lab.runner import digest,_inventory
        path=Path(report['evidence_path']);manifest=path/'manifest.json'
        if not path.is_dir() or manifest.is_symlink() or digest(manifest)!=target['manifest_hash']:raise ValueError('manifest_mismatch')
        original=json.loads(manifest.read_text())
        if original.get('trial_id')!=target['trial_id'] or original.get('execution_attempt_id')!=target['execution_attempt_id'] or original.get('status')!=report['status'] or original.get('status')!=row[1] or original.get('artifacts')!=_inventory(path):raise ValueError('evidence_mismatch')
    except (OSError,ValueError,KeyError,RuntimeError) as error:
        raise ValidationError('evidence_unavailable') from error
    return trial


def publish_validation(service, token, project, run, validation_id, document, *, idempotency_key, supersedes=None):
    principal=service._auth(token,project,{'evaluator'})
    service._identity(run,validation_id,idempotency_key)
    if supersedes is not None:service._identity(supersedes)
    document=_document(document)
    payload=[principal['subject'],validation_id,document,supersedes]
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        replay=service._replay(db,project,'validation:'+run,idempotency_key,payload)
        if replay:return replay
        service._run(db,project,run)
        if db.execute('SELECT 1 FROM asr_validations WHERE project=? AND validation_id=?',(project,validation_id)).fetchone():raise ValidationError('validation_id_conflict')
        trial=_evidence(db,project,run,document['target'])
        hypothesis=None
        if 'hypothesis_ref' in document:
            hypothesis=service._hypothesis_ref(db,project,document['hypothesis_ref'])
            row=db.execute('SELECT record FROM asr_hypotheses WHERE project=? AND hypothesis_id=? AND revision=?',(project,hypothesis['hypothesis_id'],hypothesis['revision'])).fetchone()
            declaration=json.loads(row[0])
            if document['analysis_timing']=='prospective' and (trial.get('hypothesis_ref')!=hypothesis or declaration['document']['analysis_timing']=='post_hoc'):raise ValidationError('post_hoc_label_required')
        if supersedes is not None:
            prior=db.execute('SELECT record FROM asr_validations WHERE project=? AND run=? AND validation_id=?',(project,run,supersedes)).fetchone()
            if prior is None:raise ValidationError('validation_not_found')
            if json.loads(prior[0])['document']['target']!=document['target']:raise ValidationError('supersedes_target_conflict')
        linked_artifact=_linked_evaluation(service,db,project,run,document['evaluation_artifact'],document['target'],document['assessments']) if 'evaluation_artifact' in document else None
        record=dict(schema_version='asr-validation/1',project_id=project,research_run_id=run,validation_id=validation_id,
                    document=document,sha256=hashlib.sha256(encoded(document).encode()).hexdigest(),hypothesis_ref=hypothesis,
                    author=principal['subject'],author_role=principal['role'],created_at=datetime.now(timezone.utc).isoformat(),supersedes=supersedes,
                    independence_basis='evaluator_attestation',isolation_verified_by_service=False)
        if linked_artifact is not None:record.update(evaluation_artifact=linked_artifact,evaluation_artifact_verified_by_service=True)
        db.execute('INSERT INTO asr_validations VALUES (?,?,?,?)',(project,run,validation_id,encoded(record)))
        service._remember(db,project,'validation:'+run,idempotency_key,payload,record)
        service._event(db,project,run,'validation_recorded',validation_id=validation_id,sha256=record['sha256'],supersedes=supersedes)
        return record


def validations(service, token, project, run):
    service._auth(token,project)
    with service._connect() as db:
        service._run(db,project,run)
        return [json.loads(row[0]) for row in db.execute('SELECT record FROM asr_validations WHERE project=? AND run=? ORDER BY rowid',(project,run))]


def _linked_evaluation(service,db,project,run,reference,target,assessments):
    from .evaluation_jobs import _get,verify_artifact
    job=_get(db,project,run,reference['evaluation_id'])
    if not job['settled'] or not job.get('artifact') or job['evaluation_attempt_id']!=reference['evaluation_attempt_id'] or job['artifact']['sha256']!=reference['artifact_sha256'] or job['target']!=target:raise ValidationError('evaluation_artifact_conflict')
    path=Path(job['artifact']['path'])
    if (path/'manifest.json').is_symlink() or hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()!=reference['artifact_sha256']:raise ValidationError('evaluation_artifact_conflict')
    verified=verify_artifact(path,job['artifact']['authority'])
    if verified['manifest']!=job['report'] or verified['isolation_facts']['container_id']!=job['identity']['container_id']:raise ValidationError('evaluation_artifact_conflict')
    result=job['report'].get('result') or {}
    equation=assessments['equation_validity']
    if equation!='unassessed' and result.get('equation_valid') is not (equation=='valid'):raise ValidationError('validation_result_conflict')
    operating=assessments['operating_checks']
    expected={'satisfied':'satisfied','violated':'violated','partially_assessed':'not_fully_assessed'}
    if operating!='unassessed' and result.get('operational_status')!=expected[operating]:raise ValidationError('validation_result_conflict')
    return dict(reference)
