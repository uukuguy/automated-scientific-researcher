"""Independent scalar scoring for the frozen client surrogate.

No imports from the researcher, training implementation or NumPy. This module
does not grant test access or declare scientific findings; admission and frozen
material verification belong to the independent evaluation service.
"""
import math
import random


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def predict(model, x):
    if model.get('schema')!='regional-load-quadratic/1':
        raise ValueError('unsupported frozen target model')
    weights=model.get('weights')
    if (type(weights) is not list or len(weights)!=10 or not weights[0] or
        any(type(row) is not list or len(row)!=len(weights[0]) or not all(finite(v) for v in row) for row in weights)):
        raise ValueError('finite rectangular ten-feature model required')
    if type(x) is not list or len(x)!=3 or not all(finite(v) and .7<=v<=1.6 for v in x):
        raise ValueError('invalid regional coordinates')
    a,b,c=(v-1 for v in x)
    basis=(1.,a,b,c,a*a,b*b,c*c,a*b,a*c,b*c)
    result=[math.fsum(basis[j]*weights[j][k] for j in range(10)) for k in range(len(weights[0]))]
    if not all(finite(v) for v in result):raise ValueError('nonfinite model prediction')
    return result


def evaluate(model, rows, case):
    n=len(case['bus'])
    voltage=[i for i,bus in enumerate(case['bus']) if bus[1]==1]
    angles=[n+i for i,bus in enumerate(case['bus']) if bus[1]!=3]
    if not rows or not voltage or not angles:raise ValueError('nonempty frozen test and output masks required')
    errors=[];angle_errors=[]
    for row in rows:
        # Excluding unsuccessful cases could change a held-out denominator.
        # Final admission must resolve label validity, not filter failures here.
        if row.get('status')!='labelled':raise ValueError('unresolved final-test label')
        target=row['y'];prediction=predict(model,row['x'])
        if len(target)!=2*n or len(prediction)!=2*n or not all(finite(v) for v in target):
            raise ValueError('final target/output dimension mismatch')
        errors.append(math.fsum((prediction[i]-target[i])**2 for i in voltage)/len(voltage))
        angle_errors.append(math.fsum((prediction[i]-target[i])**2 for i in angles)/len(angles))
    return dict(proposed=len(rows),labelled=len(rows),
                pq_voltage_rmse_pu=math.sqrt(math.fsum(errors)/len(errors)),
                nonreference_angle_rmse_degree=math.sqrt(math.fsum(angle_errors)/len(angle_errors)),
                sample_voltage_mse=errors)


def paired_interval(candidate, baseline):
    """Fixed-seed paired case bootstrap, conditional on the supplied trained model.

    This quantifies test-instance variation, not training-seed uncertainty or
    transfer to unseen families. It does not change the fixed utility predicate.
    """
    if not candidate or len(candidate)!=len(baseline) or not all(finite(v) for v in candidate+baseline):
        raise ValueError('finite paired per-case errors required')
    delta=[a-b for a,b in zip(candidate,baseline)]
    rng=random.Random(20261103);n=len(delta);draws=2000
    samples=sorted(math.fsum(delta[rng.randrange(n)] for _ in range(n))/n for _ in range(draws))
    def quantile(q):
        position=(draws-1)*q;lo=math.floor(position);hi=math.ceil(position)
        return samples[lo]+(position-lo)*(samples[hi]-samples[lo])
    return dict(estimand='candidate_minus_baseline_sample_mse',mean=math.fsum(delta)/n,
                lower=quantile(.025),upper=quantile(.975),level=.95,draws=draws,seed=20261103,
                scope='Paired test-instance bootstrap conditional on a fixed trained model; not training-seed or unseen-family uncertainty.')
