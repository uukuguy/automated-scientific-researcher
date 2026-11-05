"""Controller-frozen fresh-panel evaluation, with no researcher code execution.

Raw rows stay in restricted execution evidence. Only aggregate results are
eligible for delivery. This is internal isolation, not external certification.
"""
import math
from .ood_worker import sha, verify_rows
from .ood_metrics import evaluate

SPLITS=('private_id','private_ood')
ACCEPTANCE=dict(relative_ood_rmse_reduction=.2,id_rmse_max_ratio=1.1,id_rmse_absolute_allowance_pu=1e-5)


def coordinate_keys(x):
    if type(x) is not list or len(x)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or not .7<=v<=1.6 for v in x):
        raise ValueError('invalid panel coordinate')
    return (sha(['exact',[float(v) for v in x]]),sha(['six-decimal',[round(float(v),6) for v in x]]))


def verify(request,materials):
    if set(request)!={'operation','protocol_sha256'} or request['operation']!='isolated_final':raise ValueError('invalid isolated request')
    if set(materials)!={'protocol','case','models','panels','history'}:raise ValueError('invalid isolated materials')
    p=materials['protocol']
    required={'schema','counts','minimum_valid_fraction','case_sha256','primary_model','baseline_model','models','acceptance','coordinate_policy','history_sha256','panels_sha256'}
    if set(p)!=required or p['schema']!='asr-isolated-confirmation/1' or sha(p)!=request['protocol_sha256']:raise ValueError('frozen protocol mismatch')
    if p['acceptance']!=ACCEPTANCE or type(p['minimum_valid_fraction']) not in (float,int) or not 0<p['minimum_valid_fraction']<=1:raise ValueError('invalid confirmation criteria')
    if p['coordinate_policy'] not in ('independent-uniform-client-regions/1','public-fixture-only'):raise ValueError('unsupported coordinate policy')
    if sha(materials['case'])!=p['case_sha256'] or sha(materials['panels'])!=p['panels_sha256'] or sha(materials['history'])!=p['history_sha256']:raise ValueError('frozen material mismatch')
    if type(materials['history']) is not list or any(type(k) is not str or len(k)!=64 or any(c not in '0123456789abcdef' for c in k) for k in materials['history']):raise ValueError('invalid history fingerprints')
    if p['primary_model']==p['baseline_model'] or set(materials['models'])!={p['primary_model'],p['baseline_model']} or {k:sha(v) for k,v in materials['models'].items()}!=p['models']:raise ValueError('frozen model mismatch')
    if set(p['counts'])!=set(SPLITS) or set(materials['panels'])!=set(SPLITS):raise ValueError('panel membership mismatch')
    seen=set(materials['history'])
    for split in SPLITS:
        count=p['counts'][split];rows=materials['panels'][split]
        if type(count) is not int or count<1 or type(rows) is not list or len(rows)!=count:raise ValueError('panel count mismatch')
        for x in rows:
            keys=coordinate_keys(x)
            if seen.intersection(keys):raise ValueError('panel/history overlap')
            seen.update(keys)
            if p['coordinate_policy']!='public-fixture-only':
                bounds=[(.9,1.1)]*3 if split=='private_id' else [(1.2,1.45),(.85,1.),(1.05,1.25)]
                if any(not low<=v<=high for v,(low,high) in zip(x,bounds)):raise ValueError('panel outside frozen distribution')
    return p


def solve_sample(case,x,sample_id):
    from research_projects.ood_augmentation.project import solve_sample as solve
    return solve(case,x,sample_id)


def execute(request,materials,emit):
    p=verify(request,materials);case=materials['case'];validity={};valid={}
    for split in SPLITS:
        valid[split]=[]
        assessment=dict(proposed=p['counts'][split],equation_valid=0,failed=0,operationally_violating=0,incompletely_assessed=0)
        for index,x in enumerate(materials['panels'][split]):
            row=solve_sample(case,x,f'{split}-{index:04d}')
            emit(dict(type='sample',split=split,index=index,row=row))
            if row.get('x')!=x:raise ValueError('solver changed frozen coordinate')
            if row.get('status')!='labelled':
                if row.get('status') not in ('label_failure','invalid_label') or row.get('y') is not None:raise ValueError('invalid failed-label evidence')
                assessment['failed']+=1
                continue
            checked=verify_rows(case,[row])
            for k in ('equation_valid','operationally_violating','incompletely_assessed'):assessment[k]+=checked[k]
            valid[split].append(row)
        validity[split]=assessment
    result=dict(schema='asr-isolated-confirmation-result/1',protocol_sha256=request['protocol_sha256'],
        primary_model=p['primary_model'],baseline_model=p['baseline_model'],model_sha256=p['models'],
        label_validity=validity,independence='internal_permission_data_execution_isolation',
        engineering_fixture=p['coordinate_policy']=='public-fixture-only',
        scope='Frozen synthetic ID/target panel, conditional on successfully labelled rows. No external-personnel certification, independent training reproduction or operating-feasibility claim.')
    if any(validity[s]['equation_valid']<math.ceil(p['counts'][s]*p['minimum_valid_fraction']) for s in SPLITS):
        return dict(result,assessment='inconclusive_label_coverage')
    metrics={}
    for key,model in materials['models'].items():
        metrics[key]={s:evaluate(model,valid[s],case) for s in SPLITS}
        for value in metrics[key].values():value.pop('sample_voltage_mse')
    baseline=metrics[p['baseline_model']];candidate=metrics[p['primary_model']]
    limits=dict(ood_rmse_max_pu=.8*baseline['private_ood']['pq_voltage_rmse_pu'],id_rmse_max_pu=max(1.1*baseline['private_id']['pq_voltage_rmse_pu'],baseline['private_id']['pq_voltage_rmse_pu']+1e-5))
    passed=candidate['private_ood']['pq_voltage_rmse_pu']<=limits['ood_rmse_max_pu'] and candidate['private_id']['pq_voltage_rmse_pu']<=limits['id_rmse_max_pu']
    return dict(result,metrics=metrics,thresholds=limits,assessment='objective_met_on_frozen_test' if passed else 'objective_not_met_on_frozen_test')
