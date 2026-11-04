"""Research-specific correspondence between team ledger and frozen native fit.

The caller supplies authenticated build/material pins, persists preparation
before dispatch and pins each subsequent artifact in its authoritative store.
This module neither grants execution authority nor schedules/retries work.
"""
import copy
import hashlib
import math

from . import prototype as p, native_adapter as native

PROJECT = 'research_projects/ood_augmentation/project.py'
WORKER = 'research_projects/ood_augmentation/worker.py'
SOLVER = 'environments/scientific/calibrate.py'
VALIDATOR = 'powerflow_lab/validation.py'
FIT_POLICY = dict(features='regional-load-quadratic/1', feature_count=10, ridge=1e-10,
                  intercept_penalized=False, row_weight='equal', target='bus-order-vm-then-va')


def pinned(value, expected, name):
    p.require(p.sha(expected) and p.digest(value) == expected, name + ' pin mismatch')


def prepare(materials, policy, group_id, arm, seed, image, *, expected_image_hash):
    pinned(image, expected_image_hash, 'image manifest')
    p.require(image['schema'] == 'asr-scientific-image/1', 'image schema')
    for relative in (PROJECT, WORKER, SOLVER, VALIDATOR):
        p.require(hashlib.sha256((native.ROOT / relative).read_bytes()).hexdigest() == image['sources'][relative],
                  'fixed image source mismatch: ' + relative)
    p.require(hashlib.sha256((native.ROOT / 'environments/scientific/uv.lock').read_bytes()).hexdigest() == image['uv_lock_sha256'], 'environment lock mismatch')
    p.require(type(seed) is int and 1101 <= seed <= 1108, 'proposal seed set')
    from asr_service.paired_sampling import validate, fingerprint
    # Validation only; these values are NOT execution authorization or reservations.
    validate(policy, dict(attempts=sum(len(g['arms']) for g in policy['groups'].values()),
                          sample_proposals=sum(sum(len(g['blocks'][b]) for b in names) for g in policy['groups'].values() for names in g['arms'].values())))
    group = policy['groups'][group_id]
    rows = [dict(proposal_id=f'{group_id}/{arm}/{block}/{i}',seed=seed,arm=arm,stream=block,x=list(p.point(x)))
            for block in group['arms'][arm] for i,x in enumerate(group['blocks'][block])]
    p.require(len(rows) == 64, 'team proposal requires complete 64-slot arm')
    excluded = {p.point(r['x']) for name in ('train','id_dev','diagnostic') for r in materials[name]}
    p.require(not any(p.point(row['x']) in excluded for row in rows), 'public coordinate collision')
    original = materials['train']; case = materials['case']
    p.require(len(original) == 128 and all(r['status'] == 'labelled' for r in original), 'unaltered labelled original128 required')
    p.require(len(case['bus']) == 118, 'IEEE118 target required')
    mask = dict(pq_voltage=[i for i,b in enumerate(case['bus']) if b[1] == 1],
                nonreference_angle=[118+i for i,b in enumerate(case['bus']) if b[1] != 3])
    contract = dict(case_sha256=p.digest(case), original_sha256=p.digest(original),
        scenario_source_sha256=image['sources'][PROJECT], feature_source_sha256=image['sources'][PROJECT],
        fit_source_sha256=image['sources'][PROJECT], fit_policy_sha256=p.digest(FIT_POLICY),
        validator_source_sha256=image['sources'][VALIDATOR], solver_source_sha256=image['sources'][SOLVER],
        mask_sha256=p.digest(mask), protocol_sha256=fingerprint(policy), environment_sha256=p.digest(image))
    plan = dict(kind='static-plan/1',rows=rows)
    expected = native.prepare_inputs(case,plan,contract)
    return dict(schema='asr-paired-arm-preparation/1',group_id=group_id,arm=arm,seed=seed,
        image=copy.deepcopy(image), contract=contract, plan=plan, original=copy.deepcopy(original),
        expected_inputs=expected, expected_hashes={pid:p.digest(v) for pid,v in expected.items()})


def ingest(prepared, rows, *, expected_preparation_hash):
    pinned(prepared, expected_preparation_hash, 'preparation')
    proposals = prepared['plan']['rows']
    p.require(len(rows) == len(proposals), 'complete native slot coverage required')
    receipts = [native.convert(proposal,row,prepared['contract'],prepared['expected_inputs'][proposal['proposal_id']])
                for proposal,row in zip(proposals,rows)]
    return p.ingest(prepared['plan'],receipts,prepared['contract'],prepared['expected_hashes'])


def read_trial(service, token, project, run, trial_id):
    """Read an authenticated completed attempt; never accept caller-supplied scores."""
    import json
    from pathlib import Path
    from asr_service.study import completed_material
    from powerflow_lab.runner import canonical, digest
    service._auth(token, project, {'human','researcher','viewer','evaluator'})
    with service._connect() as db:
        db.execute('BEGIN')
        material, reference = completed_material(db,project,run,trial_id)
        trial = json.loads(db.execute('SELECT record FROM asr_dispatch WHERE project=? AND run=? AND trial=?',
                                     (project,run,trial_id)).fetchone()[0])
        execution = json.loads(db.execute('SELECT record FROM asr_executions WHERE attempt=?',
                                         (reference['execution_attempt_id'],)).fetchone()[0])
        root = Path(execution['report']['evidence_path'])
        manifest = json.loads((root/'manifest.json').read_text())
        request = trial['execution_request']
        p.require(manifest['trial_id']==trial_id and manifest['execution_attempt_id']==reference['execution_attempt_id'], 'evidence identity mismatch')
        p.require(manifest['request_sha256']==hashlib.sha256(canonical(request)).hexdigest(), 'evidence request mismatch')
        for field in ('paired_sampling','organization_task','paired_adapter'):
            p.require(manifest.get(field)==trial.get(field), 'evidence binding mismatch')
        p.require(digest(root/'study-input.json')==request['payload_sha256'], 'native payload mismatch')
        payload = json.loads((root/'study-input.json').read_text())
        result = json.loads((root/'study-result.json').read_text())
    return dict(trial=trial, reference=reference, payload=payload, events=material['events'], result=result)


def check_trial(prepared, record, operation):
    trial = record['trial']
    p.require(trial['variables']['operation']==operation, 'native operation mismatch')
    p.require(trial['execution_request']['image_id']==prepared['image']['image_id'], 'native image mismatch')
    binding = trial.get('paired_sampling')
    p.require(binding is not None and binding['protocol_sha256']==prepared['contract']['protocol_sha256']
              and binding['group_id']==prepared['group_id'] and binding['arm_id']==prepared['arm'], 'paired arm mismatch')
    p.require(p.digest(record['payload']['materials']['case'])==prepared['contract']['case_sha256'], 'native case mismatch')


def ingest_trial(service, token, project, run, trial_id, prepared, *, expected_preparation_hash):
    pinned(prepared,expected_preparation_hash,'preparation')
    record = read_trial(service,token,project,run,trial_id)
    check_trial(prepared,record,'label')
    request = record['payload']['request']
    p.require(request==dict(operation='label',purpose='augmentation',coordinates=[r['x'] for r in prepared['plan']['rows']]), 'native label request mismatch')
    events = [e for e in record['events'] if e['type']=='sample']
    p.require([e['index'] for e in events]==list(range(len(prepared['plan']['rows']))), 'native slot order/coverage mismatch')
    ledger = ingest(prepared,[e['row'] for e in events],expected_preparation_hash=expected_preparation_hash)
    return dict(schema='asr-paired-label-bundle/1',preparation_sha256=expected_preparation_hash,
                label_reference=record['reference'],ledger=ledger)


def training_manifest(prepared, bundle, *, expected_preparation_hash, expected_bundle_hash):
    pinned(prepared,expected_preparation_hash,'preparation')
    pinned(bundle,expected_bundle_hash,'label bundle')
    p.require(bundle['preparation_sha256']==expected_preparation_hash, 'label preparation correspondence')
    ledger = bundle['ledger']
    p.require(ledger['plan']==prepared['plan'] and ledger['expected_inputs']==prepared['expected_hashes'], 'ledger preparation correspondence')
    manifest = p.training_manifest(ledger,prepared['arm'],prepared['seed'],prepared['original'],
                                   prepared['contract'],p.digest(ledger))
    manifest.update(label_reference=bundle['label_reference'],preparation_sha256=expected_preparation_hash,
                    label_bundle_sha256=expected_bundle_hash)
    return manifest


def bind_fit(service, token, project, run, trial_id, prepared, bundle, manifest, *,
             expected_preparation_hash, expected_bundle_hash, expected_manifest_hash):
    pinned(manifest,expected_manifest_hash,'manifest')
    rebuilt = training_manifest(prepared,bundle,expected_preparation_hash=expected_preparation_hash,
                                expected_bundle_hash=expected_bundle_hash)
    p.require(rebuilt==manifest, 'training manifest correspondence')
    record = read_trial(service,token,project,run,trial_id)
    check_trial(prepared,record,'fit')
    p.require(record['trial']['dependencies']==[bundle['label_reference']], 'native label dependency mismatch')
    p.require(record['payload']['request']==dict(operation='fit'), 'fixed fit request required')
    materials = record['payload']['materials']
    p.require(materials['train']==prepared['original'], 'original128 payload mismatch')
    batches = materials['augmentation']
    p.require(len(batches)==1 and batches[0]['purpose']=='augmentation', 'one native augmentation arm required')
    rows = batches[0]['rows']; records = bundle['ledger']['records']
    p.require(len(rows)==len(records) and all(p.digest(row)==v['receipt']['native_sha256'] for row,v in zip(rows,records)),
              'native training rows differ from checked ledger')
    # Different sample identifiers are retained in their source artifacts;
    # numeric training inputs must agree in exact order.
    native_training = [r for r in materials['train']+rows if r['status']=='labelled']
    pairs = lambda values: [dict(x=r['x'],y=r['y']) for r in values]
    p.require(pairs(native_training)==pairs(manifest['rows']), 'ordered training payload mismatch')
    result = record['result']; model = result['model']
    p.require(result['operation']=='fit' and result['augmentation_proposed']==64
              and result['augmentation_labelled']==manifest['labelled'], 'fit label counts mismatch')
    p.require(model['training_count']==len(manifest['rows']) and model['schema']=='regional-load-quadratic/1'
              and model['ridge']==1e-10, 'fixed model policy mismatch')
    weights = model['weights']
    p.require(len(weights)==10 and all(len(row)==236 and all(type(v) in (int,float) and math.isfinite(v) for v in row) for row in weights), 'model weights shape/value mismatch')
    receipt = dict(training_sha256=manifest['training_sha256'],contract_sha256=manifest['contract_sha256'],
        model=copy.deepcopy(model),model_sha256=p.digest(model),fit_reference=record['reference'],
        label_reference=bundle['label_reference'],ordered_numeric_training_sha256=p.digest(pairs(native_training)),
        native_payload_sha256=record['trial']['execution_request']['payload_sha256'],
        image_id=prepared['image']['image_id'],worker_source_sha256=prepared['image']['sources'][WORKER])
    return dict(schema='asr-paired-model-binding/1',receipt=receipt,
                binding=p.bind_model(manifest,receipt,expected_manifest_hash))
