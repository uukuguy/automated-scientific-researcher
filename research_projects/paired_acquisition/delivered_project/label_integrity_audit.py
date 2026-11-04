"""Author prefit audit; native host checks remain distinct from this recomputation."""
import copy
import hashlib
import json
import numpy as np


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def scenario(original, x):
    c = copy.deepcopy(original)
    for i, b in enumerate(c['bus']):
        b[2] *= float(x[min(2, i*3//len(c['bus']))])
        b[3] *= float(x[min(2, i*3//len(c['bus']))])
    scale = sum(b[2] for b in c['bus'])/sum(b[2] for b in original['bus'])
    types = {b[0]: b[1] for b in c['bus']}
    for g in c['gen']:
        if g[7] and types[g[0]] != 3:
            g[1] *= scale
    return c


def residual(c, sol):
    n = len(c['bus'])
    lookup = {b[0]: i for i, b in enumerate(c['bus'])}
    y = np.zeros((n, n), dtype=complex)
    for r in c['branch']:
        if not r[10]:
            continue
        f, t = lookup[r[0]], lookup[r[1]]
        adm = 1/complex(r[2], r[3])
        charging = .5j*r[4]
        ratio = r[8] if r[8] else 1.
        tap = ratio*np.exp(1j*np.deg2rad(r[9]))
        y[f, f] += (adm+charging)/(ratio*ratio)
        y[t, t] += adm+charging
        y[f, t] -= adm/np.conj(tap)
        y[t, f] -= adm/tap
    for i, b in enumerate(c['bus']):
        y[i, i] += complex(b[4], b[5])/c['baseMVA']
    v = np.array([b[7]*np.exp(1j*np.deg2rad(b[8])) for b in sol['bus']])
    injection = np.array([-complex(b[2], b[3]) for b in c['bus']])
    for g in sol['gen']:
        if g[7]:
            injection[lookup[g[0]]] += complex(g[1], g[2])
    mismatch = v*np.conj(y@v)-injection/c['baseMVA']
    return float(max(np.max(np.abs(mismatch.real)), np.max(np.abs(mismatch.imag))))


def main(data):
    trials = data['trials']
    manifest_trial = trials['trial_14ac543babbf48e8904161e0999c20b3']
    original_result = [e['result'] for e in manifest_trial['events'] if e['type'] == 'result'][0]
    manifest = original_result['author_output']['candidate']
    assert digest(manifest) == '0b421c2571c97183c628cd495bbb684cbaf01f3f97d1f42cbca38e7d4522e3a7'
    assert digest(data['case']) == '1fa94780bf0e3bfb3bdd571c7b1e7031db5942923c39adf599f1624fd6fdd41e'
    by_hash = {b['coordinate_sha256']: (i, b) for i, b in enumerate(manifest['batches'])}
    audits, ledger, raw, issues = [], [], {}, []
    labels = [(tid, t) for tid, t in trials.items() if t['variables'].get('operation') == 'label']
    for tid, t in labels:
        events = [e for e in t['events'] if e['type'] == 'sample']
        rows = [e['row'] for e in events]
        raw[tid] = t
        xyhash = digest([r['x'] for r in rows])
        if xyhash not in by_hash:
            issues.append([tid, 'coordinate manifest mismatch', xyhash])
            continue
        batch_index, b = by_hash[xyhash]
        batch_issues = []
        if len(rows) != 64 or [e['index'] for e in events] != list(range(64)) or [r['x'] for r in rows] != b['coordinates']:
            batch_issues.append('count/index/order mismatch')
        if t['variables'].get('purpose') != 'augmentation':
            batch_issues.append('wrong purpose')
        counts = dict(labelled=0, invalid_label=0, label_failure=0, converged=0, equation_valid=0, input_preserved=0, operationally_violating=0)
        residuals, host_residuals, thermal = [], [], []
        for i, r in enumerate(rows):
            checks = {}
            expected = scenario(data['case'], b['coordinates'][i])
            checks['intended_input'] = r.get('input') == expected and r.get('input_sha256') == digest(expected)
            status = r.get('status')
            if status in ('labelled', 'invalid_label', 'label_failure'):
                counts[status] += 1
            else:
                checks['known_status'] = False
            observed = dict(trial_id=tid, index=i, status=status, x=r['x'], expected_input_sha256=digest(expected), input_sha256=r.get('input_sha256'), solution_sha256=r.get('solution_sha256'), elapsed_ms=r.get('elapsed_ms'))
            if status == 'labelled':
                sol, validation = r.get('solution'), r.get('validation', {})
                checks['solution_present'] = isinstance(sol, dict)
                if sol is not None:
                    checks['solution_hash'] = digest(sol) == r.get('solution_sha256')
                    checks['canonical_bus_order'] = [a[0] for a in sol['bus']] == [a[0] for a in expected['bus']]
                    checks['fixed_solution_fields'] = sol['baseMVA'] == expected['baseMVA'] and len(sol['bus']) == 118 and len(sol['gen']) == len(expected['gen']) and len(sol['branch']) == len(expected['branch'])
                    checks['fixed_solution_fields'] &= all(all(a[j] == v for j, v in enumerate(z) if j not in (7, 8)) for a, z in zip(sol['bus'], expected['bus']))
                    checks['fixed_solution_fields'] &= all(all(a[j] == v for j, v in enumerate(z) if j not in (1, 2)) for a, z in zip(sol['gen'], expected['gen']))
                    checks['fixed_solution_fields'] &= all(a[:len(z)] == z for a, z in zip(sol['branch'], expected['branch']))
                    target = [a[7] for a in sol['bus']] + [a[8] for a in sol['bus']]
                    a = np.asarray(r.get('y'), dtype=float)
                    checks['target236_finite_ordered'] = a.shape == (236,) and bool(np.isfinite(a).all()) and r['y'] == target
                    types = {z[0]: z[1] for z in expected['bus']}
                    checks['fixed_dispatch'] = all(abs(a[1]-z[1]) <= 1e-10 for a, z in zip(sol['gen'], expected['gen']) if z[7] and types[z[0]] != 3)
                    setpoints = {}
                    for g in expected['gen']:
                        if g[7]:
                            setpoints.setdefault(g[0], []).append(g[5])
                    checks['controlled_voltage_angle'] = all(z[0] in setpoints and all(abs(a[7]-vg) <= 1e-12 for vg in setpoints[z[0]]) for a, z in zip(sol['bus'], expected['bus']) if z[1] in (2, 3)) and all(abs(a[8]-z[8]) <= 1e-12 for a, z in zip(sol['bus'], expected['bus']) if z[1] == 3)
                    value = residual(expected, sol)
                    checks['author_equation_residual'] = bool(np.isfinite(value) and value <= 1e-7)
                    residuals.append(value)
                    observed.update(target_sha256=digest(r['y']), author_residual_pu=value)
                checks['host_equation_evidence'] = validation.get('equation_valid') is True and validation.get('errors') == [] and validation.get('max_mismatch_pu', float('inf')) <= 1e-7
                checks['host_input_preserved'] = validation.get('input_preserved') is True
                checks['host_policy'] = validation.get('policy') == 'fixed-pv-pq-single-slack/1'
                counts['converged'] += int(r.get('solver', {}).get('converged') is True)
                counts['equation_valid'] += int(validation.get('equation_valid') is True)
                counts['input_preserved'] += int(validation.get('input_preserved') is True)
                counts['operationally_violating'] += int(validation.get('operational_status') == 'violated')
                host_residuals.append(validation.get('max_mismatch_pu'))
                thermal.append(validation.get('thermal_limits_unassessed'))
            else:
                checks['failed_target_absent'] = r.get('y') is None
            observed['checks'] = {k: bool(v) for k, v in checks.items()}
            ledger.append(observed)
            for name, passed in checks.items():
                if not passed:
                    batch_issues.append([i, name])
        if counts['labelled']/64 < .95:
            batch_issues.append('label yield below95percent')
        issues.extend([[tid, x] for x in batch_issues])
        audits.append(dict(trial_id=tid, batch_index=batch_index, arm=b['arm'], seed=b['seed'], coordinate_sha256=xyhash, counts=counts, issues=batch_issues,
                           max_author_residual_pu=max(residuals) if residuals else None, max_host_residual_pu=max(host_residuals) if host_residuals else None,
                           thermal_limits_unassessed_values=sorted(set(thermal))))
    if len(labels) not in (2, 3) or len({a['batch_index'] for a in audits}) != len(labels):
        issues.append('expected two or three distinct complete label batches per bounded audit')
    return dict(audit_scope='author prefit subset audit; not independent validation', subset_pass=not issues, issues=issues,
                audited_batches=audits, row_ledger=ledger, raw_native_trials=raw,
                provenance_limits='Native host validation and governed request/contract binding; external loaded-validator/image/original-file attestations absent and dispositioned by Organizer seq21. Raw native events preserved; no solves or fits rerun.')
