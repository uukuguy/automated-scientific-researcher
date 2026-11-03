"""Trusted simulated-client materials, not an autonomous research solution.

Run with the locked environments/scientific Python. No model calls or candidate
code execution. Hidden-test material is never copied to the public project pack.
Directory separation is preparation, not a claim of researcher OS isolation.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_SPLITS = {'train': 128, 'id_dev': 32, 'diagnostic': 32}
PRIVATE_SPLITS = {'private_id': 64, 'private_ood': 64}
FEATURE_SCHEMA = 'regional-load-quadratic/1'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def save(path, value):
    path=Path(path)
    body=canonical(value)+b'\n'
    if path.exists():
        if path.read_bytes()!=body: raise ValueError('immutable artifact conflict: '+path.name)
        return
    temporary=path.with_suffix(path.suffix+'.pending')
    with temporary.open('xb') as f:
        f.write(body);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


def load_case():
    from environments.scientific.calibrate import load_fixture
    return load_fixture(ROOT/'environments/scientific/fixtures/matpower-case118')[0]


def group(index,count):
    return min(2,index*3//count)


def make_scenario(original, scales):
    a=np.asarray(scales,dtype=float)
    if a.shape!=(3,) or not np.isfinite(a).all() or np.any((a<.7)|(a>1.6)):
        raise ValueError('three finite regional multipliers in [0.7,1.6] required')
    result=copy.deepcopy(original)
    for i,bus in enumerate(result['bus']):
        bus[2]*=float(a[group(i,len(result['bus']))]);bus[3]*=float(a[group(i,len(result['bus']))])
    # Fixed synthetic dispatch rule, not a physical-feasibility guarantee.
    # Non-reference Pg scales with total demand; reference Pg absorbs losses.
    scale=sum(b[2] for b in result['bus'])/sum(b[2] for b in original['bus'])
    types={b[0]:b[1] for b in result['bus']}
    for gen in result['gen']:
        if gen[7] and types[gen[0]]!=3:gen[1]*=scale
    return result


def coordinates(split,seed,count):
    if split not in PUBLIC_SPLITS and split not in PRIVATE_SPLITS:raise ValueError('unknown split')
    if type(count) is not int or not 1<=count<=512:raise ValueError('count in [1,512] required')
    rng=np.random.default_rng(seed)
    if split in ('diagnostic','private_ood'):
        a=rng.uniform([1.2,.85,1.05],[1.45,1.,1.25],(count,3))
    else:a=rng.uniform(.9,1.1,(count,3))
    return a.tolist()


def features(x):
    a=np.asarray(x,dtype=float)
    if a.ndim!=2 or a.shape[1]!=3 or len(a)==0 or not np.isfinite(a).all():raise ValueError('finite Nx3 inputs required')
    z=a-1
    return np.column_stack([np.ones(len(a)),z,z*z,z[:,0]*z[:,1],z[:,0]*z[:,2],z[:,1]*z[:,2]])


def fit(x,y):
    f=features(x);y=np.asarray(y,dtype=float)
    if y.ndim!=2 or y.shape[0]!=len(f) or not np.isfinite(y).all() or len(f)<10:raise ValueError('at least ten valid paired training rows required')
    penalty=np.eye(f.shape[1])*1e-10;penalty[0,0]=0
    weights=np.linalg.solve(f.T@f+penalty,f.T@y)
    return dict(schema=FEATURE_SCHEMA,weights=weights.tolist(),training_count=len(f),ridge=1e-10)


def predict(model,x):
    if model['schema']!=FEATURE_SCHEMA:raise ValueError('unsupported model')
    weights=np.asarray(model['weights'],dtype=float)
    if weights.ndim!=2 or weights.shape[0]!=10 or not np.isfinite(weights).all():raise ValueError('invalid model weights')
    return features(x)@weights


def solve_sample(original, x, sample_id):
    from environments.scientific.calibrate import solve_reference
    from powerflow_lab.validation import validate
    case=make_scenario(original,x);began=time.monotonic()
    base=dict(sample_id=sample_id,x=x,input_sha256=digest(case))
    try:
        solution,solver=solve_reference(case)
        check=validate(case,solution,1e-7)
        target=[b[7] for b in solution['bus']]+[b[8] for b in solution['bus']]
        base.update(status='labelled' if check['equation_valid'] else 'invalid_label',
                    y=target if check['equation_valid'] else None,validation=check,
                    solution_sha256=digest(solution),input=case,solution=solution,
                    solver=dict(converged=solver['converged'],iterations=solver['iterations'],
                                max_admittance_difference_pu=solver['max_admittance_difference_pu']))
    except Exception as exc:
        # Retain each failed proposal; no rejection sampling or silent retry.
        base.update(status='label_failure',y=None,input=case,error_type=type(exc).__name__,error=str(exc))
    base['elapsed_ms']=int((time.monotonic()-began)*1000)
    return base


def metrics(model, rows, original):
    valid=[r for r in rows if r['status']=='labelled']
    if not valid:return dict(proposed=len(rows),labelled=0)
    error=predict(model,[r['x'] for r in valid])-np.asarray([r['y'] for r in valid])
    n=len(original['bus']);pq=[i for i,b in enumerate(original['bus']) if b[1]==1]
    nonref=[n+i for i,b in enumerate(original['bus']) if b[1]!=3]
    return dict(proposed=len(rows),labelled=len(valid),
                pq_voltage_rmse_pu=float(np.sqrt(np.mean(error[:,pq]**2))),
                nonreference_angle_rmse_degree=float(np.sqrt(np.mean(error[:,nonref]**2))),
                operationally_violating=sum(r['validation']['operational_status']=='violated' for r in valid),
                incompletely_assessed=sum(r['validation']['thermal_limits_unassessed']>0 for r in valid))


def build(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    public=root/'public';private=root/'private';raw=root/'raw'
    for p in (public,private,raw):p.mkdir(exist_ok=True,mode=0o700)
    original=load_case()
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    config_path=private/'preparation.json'
    if config_path.exists():config=json.loads(config_path.read_text())
    else:
        config=dict(schema='asr-simulated-client/1',case_sha256=digest(original),source_sha256=source_hash,
                    seeds={name:secrets.randbits(63) for name in PRIVATE_SPLITS},
                    public_seeds={'train':202611031,'id_dev':202611032,'diagnostic':202611033},
                    counts={**PUBLIC_SPLITS,**PRIVATE_SPLITS},
                    intent='Fixed specification before measuring ID/OOD error; no gap-dependent tuning.',
                    max_preparation_seconds=600)
        save(config_path,config)
    if config['source_sha256']!=source_hash or config['case_sha256']!=digest(original):raise ValueError('preparation source or case drift; use new root')
    all_seeds={**config['public_seeds'],**config['seeds']};samples={};start=time.monotonic()
    for split,count in config['counts'].items():
        directory=raw/split;directory.mkdir(exist_ok=True,mode=0o700)
        rows=[]
        for i,x in enumerate(coordinates(split,all_seeds[split],count)):
            path=directory/f'{i:04d}.json'
            if path.exists():row=json.loads(path.read_text())
            else:
                if time.monotonic()-start>=config['max_preparation_seconds']:
                    save(root/f'paused-{time.time_ns()}.json',dict(status='paused',limit='preparation_seconds',configured=600,observed=time.monotonic()-start,next_sample=f'{split}/{i}',recovery='Resume the same root; do not discard completed samples.'))
                    return False
                row=solve_sample(original,x,f'{split}-{i:04d}')
                save(path,row)
            if row['x']!=x or row['input_sha256']!=digest(make_scenario(original,x)):raise ValueError('sample identity drift')
            rows.append(row)
        samples[split]=rows
        exported=[{k:v for k,v in r.items() if k not in ('input','solution')} for r in rows]
        save((public if split in PUBLIC_SPLITS else private)/(split+'.json'),exported)
        print(json.dumps(dict(split=split,proposed=count,labelled=sum(r['status']=='labelled' for r in rows))),flush=True)
    train=[r for r in samples['train'] if r['status']=='labelled']
    model=fit([r['x'] for r in train],[r['y'] for r in train]);save(public/'baseline.json',model)
    baseline={k:metrics(model,samples[k],original) for k in PUBLIC_SPLITS}
    save(public/'baseline-report.json',dict(metrics=baseline,
        observed_ood_voltage_ratio=baseline['diagnostic']['pq_voltage_rmse_pu']/max(baseline['id_dev']['pq_voltage_rmse_pu'],1e-15),
        interpretation='Measured simulated-client deficiency only; not an ASR result or evidence that augmentation helps.'))
    save(public/'case.json',original)
    save(public/'task.json',dict(project_id='simulated-ood-voltage-001',
        objective='Generate useful training data to improve the supplied voltage surrogate on the diagnostic regime without unacceptable ID regression.',
        target='Fixed quadratic regional-load surrogate. Retrain weights with unchanged fit policy; research data selection/generation.',
        labels='PQ/all-bus voltage magnitudes and bus angles; independently equation-checked reference solves. Operational violations are labelled, not erased.',
        coordinates='Three contiguous bus-index groups, synthetic rather than geographical; scale each group Pd/Qd together. Non-reference Pg scales with total Pd.',
        proposal_domain=[.7,1.6],primary_metric='PQ voltage RMSE in pu',secondary_metric='nonreference angle RMSE in degrees',
        acceptance=dict(relative_ood_rmse_reduction=.2,id_rmse_max_ratio=1.1,id_rmse_absolute_allowance_pu=1e-5),
        constraints='Keep original data, fixed model/trainer, equations and evaluation rules. Select/generate augmentation independently. Retain unsuccessful proposals and all cost.',
        success='A supported negative finding is acceptable research; report whether the improvement objective was met.',
        limitations='Synthetic benchmark; fixed topology/PV-PQ, missing thermal ratings, not proof of operational feasibility or real-client benefit.'))
    inventory={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in public.iterdir() if p.name!='manifest.json'}
    save(public/'manifest.json',dict(schema='asr-client-package/1',files=inventory))
    save(private/'baseline-report.json',{k:metrics(model,samples[k],original) for k in PRIVATE_SPLITS})
    save(root/'preparation-report.json',dict(status='prepared',public_manifest_sha256=hashlib.sha256((public/'manifest.json').read_bytes()).hexdigest(),
        source_sha256=source_hash,total_proposed=sum(config['counts'].values()),total_labelled=sum(r['status']=='labelled' for rows in samples.values() for r in rows),
        raw_inventory={str(p.relative_to(raw)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw.rglob('*.json'))},
        boundary='Client-side trusted preparation only; ASR has not run. Private materials require verified access isolation before research.',
        public_metrics=baseline))
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    args=parser.parse_args();raise SystemExit(0 if build(args.root) else 2)

if __name__=='__main__':main()
