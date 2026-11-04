"""Frozen author synthesis of ALL nine native fits; no refitting or acquisition."""
import hashlib
import json
import numpy as np

BASE = 'trial_a2989bb71afe49508465861b51f65902'
FITS = [
    (BASE, 'baseline', 0, None),
    ('trial_b655c56b27d74ef994dad2a73e892e1f', 'target', 4101, 'trial_ef15581518534f0fb20a75ac9b292a81'),
    ('trial_8a652f6fa7464b739c9260301d77ec05', 'target', 4102, 'trial_5e71994bcefb4f89919e3e6029b34211'),
    ('trial_cf645292f5c141acb207a8fa79cd945c', 'target', 4103, 'trial_8d0eee1271614ac5b94e1a44a7709128'),
    ('trial_c1597a2d68b445c4b770d7daecf764b2', 'target', 4104, 'trial_bd40876f4c5540f7a40fe7f73a762706'),
    ('trial_4cdbe53a0cd9481aae17b86e3711e65d', 'mixed', 5101, 'trial_b296487880384ebe8e2f0a3bbb62ef1d'),
    ('trial_efafb4b736904cd2b875aecb7bf55b9d', 'mixed', 5102, 'trial_387145453cb144c5a6f7f2c690d24622'),
    ('trial_863580bc6ddd44dc9be17c31ce13f017', 'mixed', 5103, 'trial_91453057bb8d41b38b5aac6591935e03'),
    ('trial_4e5431dcd3144fe982ba09de2fee1633', 'mixed', 5104, 'trial_4dc9844732a1414b85c88269fc7168dc')]


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def result(t):
    values = [e['result'] for e in t['events'] if e['type'] == 'result']
    return values[-1]


def models(v, path='root'):
    found = []
    if isinstance(v, dict):
        if 'weights' in v and 'schema' in v:
            found.append((path, v))
        else:
            for k, value in v.items():
                found += models(value, path+'/'+str(k))
    elif isinstance(v, list):
        for i, value in enumerate(v):
            if isinstance(value, (dict, list)):
                found += models(value, path+'/'+str(i))
    return found


def features(x):
    z = np.asarray(x, dtype=float)-1
    return np.column_stack([np.ones(len(z)), z, z*z, z[:, 0]*z[:, 1], z[:, 0]*z[:, 2], z[:, 1]*z[:, 2]])


def main(data):
    trials = data['trials']
    native = {tid: trials[tid] for tid, _, _, _ in FITS}
    results = {tid: result(t) for tid, t in native.items()}
    baseline = results[BASE]['development']
    metric = 'pq_voltage_rmse_pu'
    id0, ood0 = baseline['id_dev'][metric], baseline['diagnostic'][metric]
    thresholds = dict(id_pu=max(1.1*id0, id0+1e-5), diagnostic_pu=.8*ood0)
    table, issues = [], []
    n = len(data['case']['bus'])
    pq = [i for i, b in enumerate(data['case']['bus']) if b[1] == 1]
    angle = [n+i for i, b in enumerate(data['case']['bus']) if b[1] != 3]
    for tid, arm, seed, label in FITS:
        r = results[tid]
        assert r['operation'] == 'fit'
        counts_ok = r['augmentation_labelled'] == (0 if arm == 'baseline' else 64) and r['augmentation_proposed'] == (0 if arm == 'baseline' else 64)
        if not counts_ok:
            issues.append([tid, 'unexpected augmentation counts'])
        dev = r['development']
        iv, ov = dev['id_dev'][metric], dev['diagnostic'][metric]
        ip, op = iv <= thresholds['id_pu'], ov <= thresholds['diagnostic_pu']
        row = dict(trial_id=tid, arm=arm, seed=seed, augmentation_trial=label, native_development=dev,
                   id_rmse_pu=iv, diagnostic_rmse_pu=ov, id_ratio=iv/id0, diagnostic_ratio=ov/ood0,
                   id_absolute_increase_pu=iv-id0, diagnostic_absolute_reduction_pu=ood0-ov,
                   diagnostic_relative_reduction=1-ov/ood0, id_margin_pu=thresholds['id_pu']-iv,
                   diagnostic_margin_pu=thresholds['diagnostic_pu']-ov, id_pass=ip, diagnostic_pass=op, joint_pass=ip and op,
                   result_fields=sorted(r), event_types=[e['type'] for e in native[tid]['events']])
        found = models(native[tid])
        row['model_paths'] = [p for p, _ in found]
        row['model_available'] = bool(found)
        if found:
            model = found[0][1]
            weights = np.asarray(model['weights'], dtype=float)
            assert model['schema'] == 'regional-load-quadratic/1' and weights.shape == (10, 236) and np.isfinite(weights).all()
            row['model_sha256'] = digest(model)
            row['author_scores'] = {}
            for split in ('id_dev', 'diagnostic'):
                valid = [a for a in data[split] if a['status'] == 'labelled']
                error = features([a['x'] for a in valid])@weights-np.asarray([a['y'] for a in valid])
                voltage = float(np.sqrt(np.mean(error[:, pq]**2)))
                angles = float(np.sqrt(np.mean(error[:, angle]**2)))
                row['author_scores'][split] = dict(pq_voltage_rmse_pu=voltage, nonreference_angle_rmse_degree=angles,
                    scenario_pq_voltage_mse_pu2=np.mean(error[:, pq]**2, axis=1).tolist())
                if abs(voltage-dev[split][metric]) > 1e-12 or abs(angles-dev[split]['nonreference_angle_rmse_degree']) > 1e-10:
                    issues.append([tid, split, 'native/author metric mismatch'])
        table.append(row)
    summaries = {}
    for arm in ('target', 'mixed'):
        rows = [r for r in table if r['arm'] == arm]
        assert len(rows) == 4
        values = [r['diagnostic_rmse_pu'] for r in rows]
        ids = [r['id_rmse_pu'] for r in rows]
        passes = sum(r['joint_pass'] for r in rows)
        summaries[arm] = dict(joint_pass_count=passes, eligible=passes >= 3, median_diagnostic_rmse_pu=float(np.median(values)),
                              diagnostic_range_pu=[min(values), max(values)], median_id_rmse_pu=float(np.median(ids)), id_range_pu=[min(ids), max(ids)])
    eligible = [arm for arm in ('target', 'mixed') if summaries[arm]['eligible']]
    if eligible:
        arm = min(eligible, key=lambda a: (summaries[a]['median_diagnostic_rmse_pu'], 0 if a == 'target' else 1))
        selected = min([r for r in table if r['arm'] == arm and r['joint_pass']], key=lambda r: (r['diagnostic_rmse_pu'], r['seed']))
    else:
        selected = table[0]
    training_rows = [dict(x=r['x'], y=r['y']) for r in data['train'] if r['status'] == 'labelled']
    assert len(training_rows) == 128
    if selected['augmentation_trial'] is not None:
        rows = [e['row'] for e in trials[selected['augmentation_trial']]['events'] if e['type'] == 'sample']
        training_rows += [dict(x=r['x'], y=r['y']) for r in rows if r['status'] == 'labelled']
    return dict(scope='author development synthesis; selection optimistic; not independently validated', analysis_issues=issues,
                baseline=baseline, thresholds=thresholds, all9=table, arm_summaries=summaries, selection=selected,
                hypothesis_observations=dict(target_joint_at_least3=summaries['target']['joint_pass_count'] >= 3,
                   target_median_not_worse=summaries['target']['median_diagnostic_rmse_pu'] <= summaries['mixed']['median_diagnostic_rmse_pu']),
                masks=dict(pq_count=len(pq), nonreference_angle_count=len(angle), pq_indices=pq, angle_indices=angle),
                native_fit_trials=native, selected_training_payload_author_reconstruction=training_rows,
                selected_training_payload_author_sha256=digest(training_rows),
                public_payload_sha256={s: digest(data[s]) for s in ('train', 'id_dev', 'diagnostic')},
                baseline_agreement_status='Pinned public baseline file not supplied in documented main(data) keys; native original-only fit is same-panel reference, not independent baseline-file/replay verification.',
                limitations='All public scores, known regime, unpaired packages/four seeds; no component causality/equivalence/population reliability/feasibility. No further numerical jobs after this24th direction attempt. Missing model/payload fields, if any, are explicit capability gaps, not invented artifacts.')
