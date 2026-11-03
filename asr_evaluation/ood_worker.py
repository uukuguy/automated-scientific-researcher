"""Independent final scoring from frozen raw labels and trusted fitted models."""
import copy
import hashlib
import json
import math

from powerflow_lab.validation import validate
from .ood_metrics import evaluate, paired_interval


def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def verify_rows(original, rows):
    assessment=dict(proposed=len(rows),equation_valid=0,operationally_violating=0,incompletely_assessed=0)
    seen=set()
    for row in rows:
        if row.get('status')!='labelled':raise ValueError('unresolved frozen test label')
        case=copy.deepcopy(original); x=row['x']; n=len(case['bus'])
        if len(x)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or not .7<=v<=1.6 for v in x):
            raise ValueError('invalid frozen test coordinates')
        if tuple(x) in seen:raise ValueError('duplicate frozen test coordinate')
        seen.add(tuple(x))
        for i,bus in enumerate(case['bus']):
            multiplier=x[min(2,(i*3)//n)];bus[2]*=multiplier;bus[3]*=multiplier
        demand_ratio=sum(b[2] for b in case['bus'])/sum(b[2] for b in original['bus'])
        kinds={b[0]:b[1] for b in original['bus']}
        for generator in case['gen']:
            if generator[7] and kinds[generator[0]]!=3:generator[1]*=demand_ratio
        if case!=row['input'] or sha(case)!=row['input_sha256'] or sha(row['solution'])!=row['solution_sha256']:
            raise ValueError('frozen original test material mismatch')
        check=validate(case,row['solution'],1e-7)
        if not check['equation_valid']:raise ValueError('independent test-label equations invalid')
        target=[b[7] for b in row['solution']['bus']]+[b[8] for b in row['solution']['bus']]
        if row['y']!=target:raise ValueError('test target differs from verified state')
        assessment['equation_valid']+=1
        assessment['operationally_violating']+=check['operational_status']=='violated'
        assessment['incompletely_assessed']+=check['thermal_limits_unassessed']>0
    return assessment


def execute(request, materials):
    if set(request)!={'operation','primary_model','model_trials','protocol_sha256'} or request['operation']!='final':
        raise ValueError('unsupported final protocol')
    if set(request['model_trials'])!=set(materials['models']) or request['primary_model'] not in materials['models']:
        raise ValueError('frozen final model selection mismatch')
    if materials['criteria']!={'relative_ood_rmse_reduction':.2,'id_rmse_max_ratio':1.1,'id_rmse_absolute_allowance_pu':1e-5}:
        raise ValueError('client acceptance policy changed')
    case=materials['case']
    validity={name:verify_rows(case,materials[name]) for name in ('private_id','private_ood')}
    baseline={name:evaluate(materials['baseline'],materials[name],case) for name in validity}
    limits=dict(ood_rmse_max_pu=.8*baseline['private_ood']['pq_voltage_rmse_pu'],
                id_rmse_max_pu=max(1.1*baseline['private_id']['pq_voltage_rmse_pu'],baseline['private_id']['pq_voltage_rmse_pu']+1e-5))
    models={}
    for trial,model in materials['models'].items():
        metrics={name:evaluate(model,materials[name],case) for name in validity}
        intervals={name:paired_interval(metrics[name]['sample_voltage_mse'],baseline[name]['sample_voltage_mse']) for name in validity}
        for value in metrics.values():value.pop('sample_voltage_mse')
        ood=metrics['private_ood']['pq_voltage_rmse_pu'];id_error=metrics['private_id']['pq_voltage_rmse_pu']
        models[trial]=dict(model_sha256=sha(model),metrics=metrics,paired_mse_intervals=intervals,
            ood_improvement_satisfied=ood<=limits['ood_rmse_max_pu'],id_retention_satisfied=id_error<=limits['id_rmse_max_pu'],
            utility_satisfied=ood<=limits['ood_rmse_max_pu'] and id_error<=limits['id_rmse_max_pu'])
    for value in baseline.values():value.pop('sample_voltage_mse')
    return dict(schema='asr-ood-independent-validation/1',protocol_sha256=request['protocol_sha256'],
        primary_model=request['primary_model'],models=models,baseline=baseline,thresholds=limits,label_validity=validity,
        assessment='objective_met_on_frozen_test' if models[request['primary_model']]['utility_satisfied'] else 'objective_not_met_on_frozen_test',
        scope='One frozen synthetic ID/target-regime test. Independent scalar metrics and original-equation checks. No unseen-family transfer, operating feasibility, scientific novelty or independent training reproduction claim.')
