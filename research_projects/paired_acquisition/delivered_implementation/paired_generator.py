"""Exact frozen coordinate recipe. Author analysis, not utility validation."""
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
    baseline = generate(data)
    repeated = generate(data)
    # Replace or remove every non-coordinate field, not merely known label keys.
    poisoned = {s: [dict(x=row['x'], y=object(), validation=object(), label=object())
                    for row in data[s]] for s in ('train', 'id_dev', 'diagnostic')}
    deleted = {s: [dict(x=row['x']) for row in data[s]] for s in ('train', 'id_dev', 'diagnostic')}
    tests = {'deterministic_rerun': baseline == repeated,
             'poisoned_labels_invariant': baseline == generate(poisoned),
             'deleted_labels_invariant': baseline == generate(deleted)}
    return {'scope': 'author implementation analysis only; no labels, fits or utility evaluation',
            'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                            'scipy': scipy.__version__},
            'metamorphic_checks': tests, 'implementation_checks_pass': baseline['accepted'] and all(tests.values()),
            'result': baseline}
