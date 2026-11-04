"""Prospective team coordinate policy r1; execute only via governed analysis.
No solves, fits, evaluation labels, independent validation or host execution.
"""
import copy
import hashlib
import json
import platform
import numpy as np
import scipy
from scipy.stats import qmc


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def coordinate_inputs(data):
    result = {}
    for split in ('train', 'id_dev', 'diagnostic'):
        a = np.asarray([r['x'] for r in data[split]], dtype=float)
        if a.ndim != 2 or a.shape[1] != 3 or len(a) == 0:
            raise ValueError(split + ': nonempty Nx3 required')
        if not np.isfinite(a).all() or np.any((a < .7) | (a > 1.6)):
            raise ValueError(split + ': finite domain coordinates required')
        result[split] = a
    return result


def literal_checks(candidate):
    """Literal contract separate from construction; mutation controls in main."""
    batches = candidate['batches']
    checks = {'batch_identity_order': [(b['arm'], b['seed']) for b in batches] == [
        ('target', 4101), ('target', 4102), ('target', 4103), ('target', 4104),
        ('mixed', 5101), ('mixed', 5102), ('mixed', 5103), ('mixed', 5104)],
        'counts': len(batches) == 8, 'literal_order': True,
        'literal_streams': True, 'block_hashes': True}
    for b in batches:
        blocks = b['blocks']
        s = b['seed']
        if b['arm'] == 'target':
            checks['literal_order'] &= b['block_order'] == ['T']
            checks['counts'] &= set(blocks) == {'T'} and len(blocks['T']) == 64
            expected = list(blocks['T'])
            streams = {'T': 10*s}
        elif b['arm'] == 'mixed':
            checks['literal_order'] &= b['block_order'] == ['T', 'B', 'G']
            checks['counts'] &= set(blocks) == {'T', 'B', 'G'}
            checks['counts'] &= (len(blocks['T']), len(blocks['B']), len(blocks['G'])) == (32, 16, 16)
            expected = list(blocks['T']) + list(blocks['B']) + list(blocks['G'])
            streams = {'T': 10*s, 'B': 10*s+1, 'G': 10*s+2}
        else:
            checks['literal_order'] = False
            continue
        checks['literal_order'] &= b['coordinates'] == expected
        checks['literal_streams'] &= b['stream_seeds'] == streams
        checks['block_hashes'] &= b['coordinate_sha256'] == digest(b['coordinates'])
        checks['counts'] &= len(b['coordinates']) == 64
    return {k: bool(v) for k, v in checks.items()}


def generate(data):
    try:
        xs = coordinate_inputs(data)
    except (KeyError, TypeError, ValueError) as exc:
        return {'accepted': False, 'candidate': None,
                'failures': [type(exc).__name__ + ': ' + str(exc)]}
    center = np.median(xs['train'], axis=0)
    lo, hi = np.array([1.2, .85, 1.05]), np.array([1.45, 1., 1.25])
    batches = []
    for arm, seeds in [('target', range(4101, 4105)), ('mixed', range(5101, 5105))]:
        for seed in seeds:
            n = 64 if arm == 'target' else 32
            target = qmc.scale(qmc.LatinHypercube(d=3, seed=10*seed).random(n), lo, hi)
            blocks = {'T': np.round(target, 6).tolist()}
            streams = {'T': 10*seed}
            order = ['T']
            metadata = {}
            if arm == 'mixed':
                rng = np.random.default_rng(10*seed+1)
                anchors = rng.uniform(lo, hi, (16, 3))
                fractions = rng.uniform(.05, .95, (16, 1))
                bridges = center + (anchors-center)*fractions
                global_points = qmc.scale(qmc.LatinHypercube(d=3, seed=10*seed+2).random(16), [.7]*3, [1.6]*3)
                blocks.update(B=np.round(bridges, 6).tolist(), G=np.round(global_points, 6).tolist())
                streams.update(B=10*seed+1, G=10*seed+2)
                order += ['B', 'G']
                metadata = {'bridge_anchors': anchors.tolist(), 'bridge_fractions': fractions[:, 0].tolist()}
            points = [x for name in order for x in blocks[name]]
            batches.append(dict(arm=arm, seed=seed, block_order=order, blocks=blocks,
                                stream_seeds=streams, coordinates=points,
                                coordinate_sha256=digest(points), **metadata))
    candidate = dict(protocol='target-versus-mixed/1', batches=batches,
                     training_median=center.tolist(), target_bounds=[lo.tolist(), hi.tolist()],
                     inputs={s: dict(count=len(a), coordinate_sha256=digest(a.tolist())) for s, a in xs.items()},
                     cost=dict(label_proposals=512, independent_batches=8),
                     draw_policy='one fixed draw; round once to six decimals; abort without replacement')
    public = {tuple(x) for a in xs.values() for x in a.tolist()}
    public6 = {tuple(x) for a in xs.values() for x in np.round(a, 6).tolist()}
    seen, collisions = {}, []
    valid_domain = True
    for b in batches:
        for i, x in enumerate(b['coordinates']):
            point, ident = tuple(x), [b['arm'], b['seed'], i]
            valid_domain &= bool(np.isfinite(x).all() and all(.7 <= v <= 1.6 for v in x))
            for kind, registry in [('public_exact', public), ('public_rounded6', public6)]:
                if point in registry:
                    collisions.append(dict(kind=kind, point=ident, x=x))
            if point in seen:
                collisions.append(dict(kind='generated_duplicate', point=ident, previous=seen[point], x=x))
            else:
                seen[point] = ident
    checks = literal_checks(candidate)
    checks.update(finite_domain=valid_domain, no_collisions=not collisions, unique512=len(seen) == 512)
    return dict(accepted=all(checks.values()), failures=[k for k, v in checks.items() if not v],
                checks=checks, collisions=collisions, candidate=candidate, candidate_sha256=digest(candidate))


def main(data):
    baseline = generate(data)
    stripped = {s: [{'x': r['x']} for r in data[s]] for s in ('train', 'id_dev', 'diagnostic')}
    poisoned = {s: [dict(x=r['x'], y=object(), validation=object(), error=object()) for r in data[s]]
                for s in ('train', 'id_dev', 'diagnostic')}
    tests = {'deterministic': baseline == generate(data),
             'deleted_labels_invariant': baseline == generate(stripped),
             'poisoned_labels_invariant': baseline == generate(poisoned)}
    if baseline['candidate'] is not None:
        wrong_order = copy.deepcopy(baseline['candidate'])
        b = wrong_order['batches'][4]
        b['block_order'] = ['G', 'B', 'T']
        b['coordinates'] = b['blocks']['G'] + b['blocks']['B'] + b['blocks']['T']
        b['coordinate_sha256'] = digest(b['coordinates'])
        tests['reject_wrong_order_even_with_consistent_hash'] = not all(literal_checks(wrong_order).values())
        wrong_seed = copy.deepcopy(baseline['candidate'])
        wrong_seed['batches'][0]['seed'] = 4109
        wrong_seed['batches'][0]['stream_seeds']['T'] = 41090
        tests['reject_wrong_seed'] = not all(literal_checks(wrong_seed).values())
    return dict(scope='author coordinate analysis only; not independent validation',
                environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                case_sha256=digest(data['case']), metamorphic_checks=tests,
                implementation_checks_pass=baseline['accepted'] and all(tests.values()), result=baseline)
