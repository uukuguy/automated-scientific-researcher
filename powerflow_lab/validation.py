"""Independent AC checks for connected, single-slack, fixed-PV/PQ cases.

Uses Python complex arithmetic, not MATPOWER's Ybus or reported residuals.
Policy: constant power loads, fixed topology, no Q-limit bus switching.
MATPOWER matrix column conventions: https://matpower.org/docs/ref/matpower7.0/lib/idx_bus.html
"""
import cmath
import math


def _check_case(case):
    base = case['baseMVA']
    if not isinstance(base, (int, float)) or not math.isfinite(base) or base <= 0:
        raise ValueError('invalid baseMVA')
    for name, width in [('bus', 13), ('gen', 10), ('branch', 13)]:
        if not isinstance(case[name], list) or not case[name]:
            raise ValueError(f'empty {name}')
        for row in case[name]:
            if len(row) < width or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in row):
                raise ValueError(f'invalid {name} row')
    ids = [b[0] for b in case['bus']]
    if len(set(ids)) != len(ids) or any(x != int(x) for x in ids):
        raise ValueError('invalid bus IDs')
    if any(b[1] not in (1, 2, 3) for b in case['bus']):
        raise ValueError('unsupported isolated/bus type policy')
    refs = [b[0] for b in case['bus'] if b[1] == 3]
    if len(refs) != 1:
        raise ValueError('requires one reference bus')
    for g in case['gen']:
        if g[0] not in ids or g[7] not in (0, 1):
            raise ValueError('invalid generator')
        if g[3] < g[4] or g[8] < g[9]:
            raise ValueError('inverted generator limits')
    graph = {i: set() for i in ids}
    for r in case['branch']:
        if r[0] not in graph or r[1] not in graph or r[10] not in (0, 1):
            raise ValueError('invalid branch')
        if r[5] < 0 or r[8] < 0:
            raise ValueError('negative rating or tap')
        if r[10]:
            if complex(r[2], r[3]) == 0:
                raise ValueError('zero branch impedance')
            graph[r[0]].add(r[1]); graph[r[1]].add(r[0])
    seen, stack = set(), [refs[0]]
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node); stack.extend(graph[node] - seen)
    if seen != set(ids):
        raise ValueError('disconnected case unsupported')
    for b in case['bus']:
        if b[11] < b[12] or b[7] <= 0:
            raise ValueError('invalid voltage or limits')
        gs = [g for g in case['gen'] if g[0] == b[0] and g[7]]
        if b[1] in (2, 3) and (not gs or any(g[5] <= 0 or g[5] != gs[0][5] for g in gs)):
            raise ValueError('missing/conflicting voltage controls')


def validate(input_case, solved_case, tolerance_pu=1e-7):
    """Return separate equation, input and operating results, including invalid data.

    tolerance_pu is for power balance and voltage control; power limits use its
    baseMVA-scaled value, angles its radian-to-degree value. This is a calibration
    policy, not a certified universal acceptance tolerance.
    """
    if not isinstance(tolerance_pu, (int, float)) or not math.isfinite(tolerance_pu) or tolerance_pu <= 0:
        raise ValueError('tolerance_pu must be finite and positive')
    result = dict(input_preserved=False, equation_valid=False, max_mismatch_pu=None,
                  operational_status='not_assessed', thermal_limits_unassessed=0,
                  violations=[], errors=[], policy='fixed-pv-pq-single-slack/1')
    try:
        _check_case(input_case); _check_case(solved_case)
        for key in ('bus', 'gen', 'branch'):
            if len(input_case[key]) != len(solved_case[key]):
                raise ValueError(f'{key} count changed')
        buses = {b[0]: b for b in input_case['bus']}
        ref = next(b[0] for b in buses.values() if b[1] == 3)
        slack_gen = next(i for i, g in enumerate(input_case['gen']) if g[0] == ref and g[7])
        preserved = input_case['baseMVA'] == solved_case['baseMVA']
        for name in ('bus', 'gen', 'branch'):
            for i, (old, new) in enumerate(zip(input_case[name], solved_case[name])):
                mutable = {7, 8} if name == 'bus' else set()
                if name == 'gen':
                    if old[7] and buses[old[0]][1] in (2, 3):
                        mutable.add(2)
                    if i == slack_gen:
                        mutable.add(1)
                    if not old[7]:  # MATPOWER clears offline output injections.
                        mutable.update((1, 2))
                        preserved &= new[1] == 0 and new[2] == 0
                if len(new) < len(old):
                    raise ValueError(f'{name} columns removed')
                preserved &= all(abs(a - new[j]) <= 1e-10 for j, a in enumerate(old) if j not in mutable)
        result['input_preserved'] = bool(preserved)
        base = input_case['baseMVA']
        voltage = {old[0]: cmath.rect(new[7], math.radians(new[8]))
                   for old, new in zip(input_case['bus'], solved_case['bus'])}
        injection = {i: complex(-b[2], -b[3]) / base for i, b in buses.items()}
        current = {i: complex(b[4], b[5]) / base * voltage[i] for i, b in buses.items()}
        # MATPOWER GS is consumed MW, BS is injected MVAr: Ysh = (GS+j BS)/base.
        # S=V*conj(YV) therefore has +GS and -BS, as required.
        for old, g in zip(input_case['gen'], solved_case['gen']):
            if old[7]:
                injection[old[0]] += complex(g[1], g[2]) / base
        angles = {old[0]: new[8] for old, new in zip(input_case['bus'], solved_case['bus'])}
        flows = []
        for row in input_case['branch']:
            f, t = row[:2]
            if not row[10]:
                flows.append((0j, 0j)); continue
            y = 1 / complex(row[2], row[3])
            tap = cmath.rect(row[8] or 1, math.radians(row[9]))
            end = y + 1j * row[4] / 2
            ifrom = end / abs(tap)**2 * voltage[f] - y / tap.conjugate() * voltage[t]
            ito = -y / tap * voltage[f] + end * voltage[t]
            current[f] += ifrom; current[t] += ito
            flows.append((voltage[f] * ifrom.conjugate() * base, voltage[t] * ito.conjugate() * base))
        residuals = [voltage[i] * current[i].conjugate() - injection[i] for i in buses]
        mismatch = max(max(abs(v.real), abs(v.imag)) for v in residuals)
        control_errors = []
        for old, b in zip(input_case['bus'], solved_case['bus']):
            if old[1] in (2, 3):
                g = next(g for g in input_case['gen'] if g[0] == old[0] and g[7])
                if abs(b[7] - g[5]) > tolerance_pu:
                    control_errors.append(f'voltage setpoint at bus {old[0]}')
            if old[1] == 3 and abs(b[8] - old[8]) > math.degrees(tolerance_pu):
                control_errors.append('reference angle changed')
        if not math.isfinite(mismatch):
            raise ValueError('non-finite derived residual')
        result.update(max_mismatch_pu=mismatch,
                      equation_valid=bool(preserved and not control_errors and mismatch <= tolerance_pu))
        result['errors'].extend(control_errors)
        if not preserved:
            result['errors'].append('fixed input changed')
        violations = result['violations']
        def bound(kind, identity, value, low, high, tol):
            if value < low - tol or value > high + tol:
                violations.append(dict(kind=kind, id=identity, value=value, low=low, high=high))
        for old, b in zip(input_case['bus'], solved_case['bus']):
            bound('voltage', old[0], b[7], old[12], old[11], tolerance_pu)
        for i, (old, g) in enumerate(zip(input_case['gen'], solved_case['gen'])):
            if old[7]:
                bound('active_generation', i, g[1], old[9], old[8], tolerance_pu * base)
                bound('reactive_generation', i, g[2], old[4], old[3], tolerance_pu * base)
        for i, (r, flow) in enumerate(zip(input_case['branch'], flows)):
            if not r[10]:
                continue
            if r[5] == 0:
                result['thermal_limits_unassessed'] += 1
            else:
                bound('thermal', i, max(abs(s) for s in flow), 0, r[5], tolerance_pu * base)
            delta = angles[r[0]] - angles[r[1]]
            low, high = r[11], r[12]
            if low != 0 or high != 0:
                if low > -360 and delta < low - math.degrees(tolerance_pu):
                    violations.append(dict(kind='angle_min', id=i, value=delta, limit=low))
                if high < 360 and delta > high + math.degrees(tolerance_pu):
                    violations.append(dict(kind='angle_max', id=i, value=delta, limit=high))
        result['operational_status'] = ('violated' if violations else 'not_fully_assessed'
                                        if result['thermal_limits_unassessed'] else 'satisfied')
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, StopIteration, ZeroDivisionError) as exc:
        result.update(equation_valid=False, operational_status='not_assessed')
        result['errors'].append(str(exc) or 'invalid case')
    return result
