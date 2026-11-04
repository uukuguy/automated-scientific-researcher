"""Opt-in trusted study adapter artifacts in the owning Control database.

These derived artifacts are not another execution/budget ledger or independent
scientific findings. Candidate code cannot choose/import adapter modules.
"""
import json

from .organization import require
from research_projects.paired_acquisition import prototype as p

PROFILE = 'paired-acquisition/1'


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS asr_study_artifacts (
      project TEXT, run TEXT, trial TEXT, kind TEXT, sha256 TEXT, body TEXT,
      PRIMARY KEY(project,run,trial,kind));
    CREATE TABLE IF NOT EXISTS asr_study_adapter_checks (
      project TEXT, run TEXT, trial TEXT, record TEXT,
      PRIMARY KEY(project,run,trial));
    ''')


def validate(provenance):
    config = provenance.get('paired_adapter')
    require(type(config) is dict and set(config)=={'profile','image_manifest','image_manifest_sha256','group_seeds'}, 'invalid_study_adapter')
    require(config['profile']==PROFILE and 'paired_sampling' in provenance, 'unsupported_study_adapter')
    image=config['image_manifest'];seeds=config['group_seeds']
    require(type(image) is dict and image.get('schema')=='asr-scientific-image/1'
            and p.digest(image)==config['image_manifest_sha256'], 'study_adapter_image_mismatch')
    require(image.get('image_id')==provenance['study']['image_id'], 'study_adapter_image_mismatch')
    require(type(seeds) is dict and set(seeds)==set(provenance['paired_sampling']['groups'])
            and all(type(v) is int and 1101<=v<=1108 for v in seeds.values())
            and len(set(seeds.values()))==len(seeds), 'study_adapter_seeds_required')


def check_run(db, project, run, provenance):
    config=provenance.get('paired_adapter')
    for body, in db.execute('SELECT record FROM asr_dispatch WHERE project=? AND run=?',(project,run)):
        old=json.loads(body)
        if 'paired_sampling' in old:
            previous=old['contract']['document']['provenance'].get('paired_adapter')
            require(previous==config, 'study_adapter_config_changed')


def save(db, project, run, trial, kind, value):
    body=p.canonical(value).decode();sha=p.digest(value)
    existing=db.execute('SELECT sha256,body FROM asr_study_artifacts WHERE project=? AND run=? AND trial=? AND kind=?',
                        (project,run,trial,kind)).fetchone()
    if existing:
        require(existing==(sha,body), 'study_adapter_artifact_conflict')
    else:
        db.execute('INSERT INTO asr_study_artifacts VALUES (?,?,?,?,?,?)',(project,run,trial,kind,sha,body))
    return dict(trial_id=trial,kind=kind,sha256=sha)


def load(db, project, run, reference):
    row=db.execute('SELECT sha256,body FROM asr_study_artifacts WHERE project=? AND run=? AND trial=? AND kind=?',
                   (project,run,reference['trial_id'],reference['kind'])).fetchone()
    require(row is not None, 'study adapter artifact missing')
    value=json.loads(row[1])
    require(row[0]==reference['sha256']==p.digest(value), 'study adapter artifact corrupt')
    return value


def prepare_label(db, project, run, trial, provenance, pairing, materials):
    config=provenance.get('paired_adapter')
    if config is None:return None
    from research_projects.paired_acquisition import training_adapter as adapter
    group,arm=pairing['group_id'],pairing['arm_id']
    prepared=adapter.prepare(materials,provenance['paired_sampling'],group,arm,config['group_seeds'][group],
        config['image_manifest'],expected_image_hash=config['image_manifest_sha256'])
    return dict(profile=PROFILE,preparation=save(db,project,run,trial,'preparation',prepared))


def prepare_fit(db, project, run, provenance, ids):
    if provenance.get('paired_adapter') is None or not ids:return None
    require(len(ids)==1,'paired_fit_one_arm_required')
    row=db.execute('SELECT record FROM asr_study_adapter_checks WHERE project=? AND run=? AND trial=?',(project,run,ids[0])).fetchone()
    check=json.loads(row[0]) if row else None
    require(check is not None and check['status']=='verified', 'study_adapter_verification_required')
    refs=check['artifacts']
    require(set(refs)=={'preparation','label_bundle','training_manifest'},'study_adapter_label_check_required')
    for ref in refs.values():load(db,project,run,ref)
    return dict(profile=PROFILE,**refs)


def summary(service, token, project, run):
    service._auth(token,project)
    with service._connect() as db:
        return {trial:json.loads(record) for trial,record in db.execute(
            'SELECT trial,record FROM asr_study_adapter_checks WHERE project=? AND run=?',(project,run))}


def reconcile(service, token, project, run, trial_id, *, retry=False):
    """Reconcile already completed evidence. This never submits or executes jobs."""
    service._auth(token,project)
    with service._connect() as db:
        row=db.execute('SELECT state,record FROM asr_dispatch WHERE project=? AND run=? AND trial=?',(project,run,trial_id)).fetchone()
        require(row is not None,'trial_not_found')
        state,raw=row;trial=json.loads(raw);binding=trial.get('paired_adapter')
        if not binding:return None
        previous=db.execute('SELECT record FROM asr_study_adapter_checks WHERE project=? AND run=? AND trial=?',(project,run,trial_id)).fetchone()
        previous=json.loads(previous[0]) if previous else None
        if previous and not retry:
            if previous['status']!='verified':return previous
            try:
                for ref in previous['artifacts'].values():load(db,project,run,ref)
                from research_projects.paired_acquisition.training_adapter import read_trial
                read_trial(service,token,project,run,trial_id)
                return previous
            except Exception:
                pass  # Recompute below to record the concrete corruption, never hide it.
        if state not in ('succeeded','failed','cancelled','timed_out'):return dict(status='awaiting_execution',trial_id=trial_id)
    artifacts={}
    if state!='succeeded':
        result=dict(status='execution_incomplete',trial_id=trial_id,execution_state=state,
            recovery='Preserve this attempt and raw evidence. No automatic replacement or retry; failed arm remains unavailable for training.')
    else:
        try:
            from research_projects.paired_acquisition import training_adapter as adapter
            with service._connect() as db:
                prepared=load(db,project,run,binding['preparation'])
                if trial['variables']['operation']=='fit':
                    bundle=load(db,project,run,binding['label_bundle'])
                    manifest=load(db,project,run,binding['training_manifest'])
            prep_hash=binding['preparation']['sha256']
            if trial['variables']['operation']=='label':
                bundle=adapter.ingest_trial(service,token,project,run,trial_id,prepared,expected_preparation_hash=prep_hash)
                manifest=adapter.training_manifest(prepared,bundle,expected_preparation_hash=prep_hash,expected_bundle_hash=p.digest(bundle))
                artifacts=dict(label_bundle=bundle,training_manifest=manifest)
                details=dict(proposed=manifest['proposed'],labelled=manifest['labelled'],training_rows=len(manifest['rows']))
            else:
                model=adapter.bind_fit(service,token,project,run,trial_id,prepared,bundle,manifest,
                    expected_preparation_hash=prep_hash,expected_bundle_hash=binding['label_bundle']['sha256'],
                    expected_manifest_hash=binding['training_manifest']['sha256'])
                artifacts=dict(model_binding=model)
                details=dict(training_rows=model['receipt']['model']['training_count'],model_sha256=model['receipt']['model_sha256'])
            result=dict(status='verified',trial_id=trial_id,details=details)
        except Exception as error:
            result=dict(status='blocked',trial_id=trial_id,error_type=type(error).__name__,code=getattr(error,'code',str(error)),
                message=str(error),recovery='Keep the original attempt, task and evidence. Inspect the recorded mismatch; after repair replay the SAME study request to retry verification only.')
            if getattr(error,'details',None) is not None:result['details']=error.details
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            if result['status']=='verified':
                result['artifacts']={key:value for key,value in binding.items() if key!='profile'}
                for kind,value in artifacts.items():result['artifacts'][kind]=save(db,project,run,trial_id,kind,value)
        except Exception as error:
            # Preserve existing immutable artifacts; never overwrite a mismatch.
            result=dict(status='blocked',trial_id=trial_id,error_type=type(error).__name__,code=getattr(error,'code',str(error)),
                message=str(error),recovery='Retain immutable artifacts and execution. Resolve the conflict; replay the same request for verification only.')
        body=json.dumps(result,sort_keys=True,allow_nan=False)
        old=db.execute('SELECT record FROM asr_study_adapter_checks WHERE project=? AND run=? AND trial=?',(project,run,trial_id)).fetchone()
        if old is None or old[0]!=body:
            db.execute('INSERT INTO asr_study_adapter_checks VALUES (?,?,?,?) ON CONFLICT(project,run,trial) DO UPDATE SET record=excluded.record',
                       (project,run,trial_id,body))
            service._event(db,project,run,'study_adapter_checked',**result)
    return result
