"""Reviewer harness; literal copy of generate/imports/constants/digest, main replaced.
Original source snapshot 044870fa16118d9a8942ebd193ff2c8483b89c59c42eb1596bfe7bd7c67e79b9.
Only reviewer main and instrumentation below are additions. No labels/fit/utility.
"""
import hashlib
import json
import platform
import numpy as np
import scipy
from scipy.stats import qmc

SEEDS = tuple(range(1101, 1109))
NAMES = ('T0', 'TA', 'TB', 'B', 'G')
ARMS = {'TT': ('T0', 'TA', 'TB'), 'BT': ('T0', 'B', 'TB'),
        'TG': ('T0', 'TA', 'G'), 'BG': ('T0', 'B', 'G')}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def generate(data):
    failures = []
    xs = {}
    for split in ('train', 'id_dev', 'diagnostic'):
        try:
            a = np.asarray([row['x'] for row in data[split]], dtype=float)
            if a.ndim != 2 or a.shape[1] != 3 or len(a) == 0:
                failures.append(split + ': empty or malformed coordinates')
            elif not np.isfinite(a).all() or not ((a >= .7) & (a <= 1.6)).all():
                failures.append(split + ': nonfinite or out-of-domain coordinates')
            else:
                xs[split] = a
        except (KeyError, TypeError, ValueError) as exc:
            failures.append(split + ': ' + type(exc).__name__)
    if failures:
        return {'accepted': False, 'failures': failures, 'candidate': None}
    d = xs['diagnostic']
    spread = np.ptp(d, axis=0)
    lo = np.maximum(.7, d.min(axis=0) - .1 * spread)
    hi = np.minimum(1.6, d.max(axis=0) + .1 * spread)
    center = np.median(xs['train'], axis=0)
    inputs = {s: {'count': len(a), 'coordinate_sha256': digest(a.tolist())}
              for s, a in xs.items()}
    if np.any(spread <= 0) or np.any(hi <= lo):
        return {'accepted': False, 'failures': ['degenerate diagnostic target range'],
                'candidate': None, 'inputs': inputs,
                'bounds': [lo.tolist(), hi.tolist()]}
    public = {tuple(x) for a in xs.values() for x in a.tolist()}
    public6 = {tuple(x) for a in xs.values() for x in np.round(a, 6).tolist()}
    batches, groups, collisions = [], [], []
    seen = {}
    check = {'counts': True, 'ranges': True, 'shared_block_reuse': True,
             'exact_arm_overlaps': True, 'no_silent_resampling': True}
    def lhs(n, lower, upper, seed):
        return qmc.scale(qmc.LatinHypercube(d=3, seed=seed).random(n), lower, upper)
    for seed in SEEDS:
        streams = {name: 10 * seed + k for k, name in enumerate(NAMES)}
        blocks = {name: lhs(32 if name == 'T0' else 16, lo, hi, streams[name])
                  for name in NAMES[:3]}
        rng = np.random.default_rng(streams['B'])
        anchors = rng.integers(0, len(d), 16)
        fractions = rng.uniform(.05, .95, (16, 1))
        blocks['B'] = center + (d[anchors] - center) * fractions
        blocks['G'] = lhs(16, [.7] * 3, [1.6] * 3, streams['G'])
        blocks = {name: np.round(blocks[name], 6).tolist() for name in NAMES}
        for name, points in blocks.items():
            check['counts'] &= len(points) == (32 if name == 'T0' else 16)
            for i, x in enumerate(points):
                key, ident = tuple(x), [seed, name, i]
                check['ranges'] &= bool(np.isfinite(x).all() and all(.7 <= v <= 1.6 for v in x))
                if key in public:
                    collisions.append({'kind': 'public_exact', 'point': ident, 'x': x})
                if key in public6:
                    collisions.append({'kind': 'public_rounded6', 'point': ident, 'x': x})
                if key in seen:
                    collisions.append({'kind': 'cross_seed' if seen[key][0] != seed else 'within_seed',
                                       'point': ident, 'previous': seen[key], 'x': x})
                else:
                    seen[key] = ident
        arms = {arm: [x for name in names for x in blocks[name]] for arm, names in ARMS.items()}
        sets = {arm: set(map(tuple, points)) for arm, points in arms.items()}
        for arm, names in ARMS.items():
            check['counts'] &= len(arms[arm]) == 64 and len(sets[arm]) == 64
            offset = 0
            for name in names:
                n = len(blocks[name])
                check['shared_block_reuse'] &= arms[arm][offset:offset+n] == blocks[name]
                offset += n
            for other, other_names in ARMS.items():
                expected = {tuple(x) for name in names if name in other_names for x in blocks[name]}
                check['exact_arm_overlaps'] &= sets[arm] & sets[other] == expected
        batches.append({'seed': seed, 'stream_seeds': streams, 'blocks': blocks,
                        'block_sha256': digest(blocks), 'bridge_anchor_indices': anchors.tolist(),
                        'bridge_fractions': fractions[:, 0].tolist()})
        groups.append({'group_id': str(seed), 'shared_blocks': blocks,
                       'arms': [{'arm_id': arm, 'block_order': list(ARMS[arm]),
                                 'coordinates': points} for arm, points in arms.items()]})
    check['unique_named_count_768'] = len(seen) == 768
    check['charged_slots_2048'] = sum(len(a['coordinates']) for g in groups for a in g['arms']) == 2048
    check['no_collisions'] = len(collisions) == 0
    failures.extend(name for name, passed in check.items() if not passed)
    candidate = {'seeds': list(SEEDS), 'inputs': inputs, 'target_bounds': [lo.tolist(), hi.tolist()],
                 'training_median': center.tolist(), 'batches': batches,
                 'paired_sampling': {'status': 'proposed-not-admitted', 'groups': groups},
                 'draw_policy': 'one fixed draw per stream; round once; no retries or replacement'}
    return {'accepted': not failures, 'failures': failures, 'checks': check,
            'collisions': collisions, 'candidate_sha256': digest(candidate), 'candidate': candidate}


def main(data):
    import copy
    baseline = generate(data)
    tests = {}
    results = {}
    expected_hash = 'f28262870d046f46d3c22c61e06df639b789966ee459c9d4723348bd3bad0176'
    tests['baseline_matches_original_trial'] = baseline['candidate_sha256'] == expected_hash and baseline['accepted']
    class XOnly(dict):
        def __getitem__(self, key):
            if key != 'x':
                raise RuntimeError('forbidden non-coordinate access: ' + str(key))
            return super().__getitem__(key)
    stripped = {s: [XOnly(x=r['x']) for r in data[s]] for s in ('train','id_dev','diagnostic')}
    tests['x_only_trap_invariant'] = generate(stripped) == baseline
    def fresh():
        return {s: [dict(x=list(r['x'])) for r in data[s]] for s in ('train','id_dev','diagnostic')}
    for name, value in [('nan',float('nan')),('infinity',float('inf')),('out_of_domain',1.7)]:
        altered = fresh()
        altered['diagnostic'][0]['x'][0] = value
        result = generate(altered)
        results[name] = result
        tests[name+'_rejected'] = not result['accepted'] and result['candidate'] is None
    altered = fresh()
    altered['diagnostic'] = [dict(x=list(altered['diagnostic'][0]['x'])) for _ in altered['diagnostic']]
    results['degenerate'] = generate(altered)
    tests['degenerate_rejected'] = not results['degenerate']['accepted'] and results['degenerate']['candidate'] is None
    for name, rows in [('empty',[]),('malformed',[{'x':[1.,1.]}])]:
        altered = fresh()
        altered['id_dev'] = rows
        results[name] = generate(altered)
        tests[name+'_rejected'] = not results[name]['accepted']
    altered = fresh()
    collision_point = baseline['candidate']['batches'][0]['blocks']['G'][0]
    altered['id_dev'].append(dict(x=collision_point))
    collision = generate(altered)
    unchanged_blocks = [b['blocks'] for b in collision['candidate']['batches']] == [b['blocks'] for b in baseline['candidate']['batches']]
    tests['public_collision_rejected_without_replacement'] = not collision['accepted'] and unchanged_blocks and {r['kind'] for r in collision['collisions']} == {'public_exact','public_rounded6'}
    results['public_collision'] = collision
    # Instrument only public QMC calls; underlying SciPy internal RNG calls are untouched.
    old_lhs = qmc.LatinHypercube
    draws = []
    class SpyLHS:
        def __init__(self, *args, **kwargs):
            self.seed = kwargs['seed']
            self.inner = old_lhs(*args, **kwargs)
        def random(self, n):
            draws.append([self.seed,n])
            return self.inner.random(n)
    try:
        qmc.LatinHypercube = SpyLHS
        observed = generate(altered)
    finally:
        qmc.LatinHypercube = old_lhs
    expected_draws = [[10*s+k,32 if k==0 else 16] for s in range(1101,1109) for k in (0,1,2,4)]
    tests['collision_fixed_qmc_draw_schedule'] = draws == expected_draws and observed == collision
    results['qmc_draw_schedule'] = draws
    # Mutations are deliberate negative controls, never a replacement accepted generator.
    original_arms = dict(ARMS)
    try:
        ARMS['TT'] = ('TB','TA','T0')
        mutated = generate(data)
    finally:
        ARMS.clear()
        ARMS.update(original_arms)
    tests['negative_control_exposes_order_oracle_gap'] = mutated['accepted'] and mutated['candidate']['paired_sampling']['groups'][0]['arms'][0]['block_order'] != ['T0','TA','TB']
    results['wrong_order_negative_control'] = {'accepted':mutated['accepted'],'checks':mutated['checks'],'candidate_sha256':mutated['candidate_sha256'],'first_order':mutated['candidate']['paired_sampling']['groups'][0]['arms'][0]['block_order']}
    # Independent literal contract checker, not derived from ARMS.
    locked = {'TT':['T0','TA','TB'],'BT':['T0','B','TB'],'TG':['T0','TA','G'],'BG':['T0','B','G']}
    tests['baseline_matches_literal_arm_contract'] = all(a['block_order']==locked[a['arm_id']] for g in baseline['candidate']['paired_sampling']['groups'] for a in g['arms'])
    return {'scope':'reviewer-authored implementation checks, not independent physics/utility validation', 'environment':{'numpy':np.__version__,'scipy':scipy.__version__},'tests':tests,'all_expected_observations':all(tests.values()),'baseline_hash':baseline['candidate_sha256'],'results':results}
