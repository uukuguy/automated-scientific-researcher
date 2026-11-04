"""Coordinate policy r1, checker implementation r2. Governed analysis only."""
import copy
import hashlib
import json
import platform
import numpy as np
import scipy
from scipy.stats import qmc


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def inputs(data):
    xs = {}
    for split, count in [('train', 128), ('id_dev', 32), ('diagnostic', 32)]:
        a = np.asarray([r['x'] for r in data[split]], dtype=float)
        if a.shape != (count, 3) or not np.isfinite(a).all() or np.any((a < .7) | (a > 1.6)):
            raise ValueError(split + ': fixed count/shape/domain violation')
        xs[split] = a
    return xs


def construct(xs):
    center = np.median(xs['train'], axis=0)
    lo, hi = np.array([1.2, .85, 1.05]), np.array([1.45, 1., 1.25])
    batches = []
    for arm, seeds in [('target', range(4101, 4105)), ('mixed', range(5101, 5105))]:
        for s in seeds:
            n = 64 if arm == 'target' else 32
            t = qmc.scale(qmc.LatinHypercube(d=3, seed=10*s).random(n), lo, hi)
            blocks, order, streams, metadata = {'T': np.round(t, 6).tolist()}, ['T'], {'T': 10*s}, {}
            if arm == 'mixed':
                rng = np.random.default_rng(10*s+1)
                anchors = rng.uniform(lo, hi, (16, 3))
                fractions = rng.uniform(.05, .95, (16, 1))
                b = center + (anchors-center)*fractions
                g = qmc.scale(qmc.LatinHypercube(d=3, seed=10*s+2).random(16), [.7]*3, [1.6]*3)
                blocks.update(B=np.round(b, 6).tolist(), G=np.round(g, 6).tolist())
                order += ['B', 'G']
                streams.update(B=10*s+1, G=10*s+2)
                metadata = dict(bridge_anchors=anchors.tolist(), bridge_fractions=fractions[:, 0].tolist())
            points = [x for name in order for x in blocks[name]]
            batches.append(dict(arm=arm, seed=s, blocks=blocks, block_order=order, stream_seeds=streams,
                                coordinates=points, coordinate_sha256=digest(points), **metadata))
    return dict(protocol='target-versus-mixed/1', batches=batches, training_median=center.tolist(),
                target_bounds=[lo.tolist(), hi.tolist()], inputs={k: dict(count=len(a), coordinate_sha256=digest(a.tolist())) for k, a in xs.items()},
                cost=dict(label_proposals=512, independent_batches=8),
                draw_policy='one fixed draw; round once to six decimals; abort without replacement')


def verify(candidate, xs):
    """Reconstruct from literal specification/public train, never candidate seeds/blocks."""
    checks = dict(identity=True, streams=True, order=True, counts=True, reconstructed_blocks=True,
                  metadata=True, block_bounds=True, coordinate_hash=True, concatenation=True,
                  public_input_binding=True, no_collisions=True, unique512=True)
    expected_ids = [('target', 4101), ('target', 4102), ('target', 4103), ('target', 4104),
                    ('mixed', 5101), ('mixed', 5102), ('mixed', 5103), ('mixed', 5104)]
    actual = candidate['batches']
    checks['identity'] = [(b['arm'], b['seed']) for b in actual] == expected_ids
    checks['counts'] = len(actual) == 8
    median = np.median(xs['train'], axis=0)
    checks['public_input_binding'] = candidate['training_median'] == median.tolist() and candidate['target_bounds'] == [[1.2, .85, 1.05], [1.45, 1., 1.25]]
    checks['public_input_binding'] &= candidate['inputs'] == {k: dict(count=len(a), coordinate_sha256=digest(a.tolist())) for k, a in xs.items()}
    checks['public_input_binding'] &= candidate['protocol'] == 'target-versus-mixed/1' and candidate['cost'] == dict(label_proposals=512, independent_batches=8)
    public = {tuple(x) for a in xs.values() for x in a.tolist()}
    rounded_public = {tuple(x) for a in xs.values() for x in np.round(a, 6).tolist()}
    seen, collisions = {}, []
    for b, (arm, seed) in zip(actual, expected_ids):
        # Separate literal draws: do not call construct or use candidate metadata to choose streams.
        count = 64 if arm == 'target' else 32
        expected_t = np.round(qmc.scale(qmc.LatinHypercube(d=3, seed=seed*10).random(count), [1.2, .85, 1.05], [1.45, 1., 1.25]), 6).tolist()
        expected_blocks, expected_order, expected_streams = {'T': expected_t}, ['T'], {'T': seed*10}
        if arm == 'mixed':
            bridge_rng = np.random.default_rng(seed*10+1)
            expected_anchors = bridge_rng.uniform([1.2, .85, 1.05], [1.45, 1., 1.25], size=(16, 3))
            expected_fractions = bridge_rng.uniform(.05, .95, size=(16, 1))
            expected_b = np.round(median + (expected_anchors-median)*expected_fractions, 6).tolist()
            expected_g = np.round(qmc.scale(qmc.LatinHypercube(d=3, seed=seed*10+2).random(16), [.7, .7, .7], [1.6, 1.6, 1.6]), 6).tolist()
            expected_blocks.update(B=expected_b, G=expected_g)
            expected_order = ['T', 'B', 'G']
            expected_streams = {'T': seed*10, 'B': seed*10+1, 'G': seed*10+2}
            checks['metadata'] &= b['bridge_anchors'] == expected_anchors.tolist() and b['bridge_fractions'] == expected_fractions[:, 0].tolist()
        else:
            checks['metadata'] &= 'bridge_anchors' not in b and 'bridge_fractions' not in b
        checks['streams'] &= b['stream_seeds'] == expected_streams
        checks['order'] &= b['block_order'] == expected_order
        checks['reconstructed_blocks'] &= b['blocks'] == expected_blocks
        expected_coordinates = [x for name in expected_order for x in expected_blocks[name]]
        checks['concatenation'] &= b['coordinates'] == expected_coordinates
        checks['counts'] &= len(b['coordinates']) == 64 and set(b['blocks']) == set(expected_order)
        for name, expected in expected_blocks.items():
            a = np.asarray(b['blocks'][name], dtype=float)
            lower, upper = (np.array([1.2, .85, 1.05]), np.array([1.45, 1., 1.25])) if name == 'T' else ((np.minimum(median, [1.2, .85, 1.05]), np.maximum(median, [1.45, 1., 1.25])) if name == 'B' else (np.array([.7]*3), np.array([1.6]*3)))
            checks['block_bounds'] &= a.shape == (len(expected), 3) and bool(np.isfinite(a).all() and np.all(a >= lower-5e-7) and np.all(a <= upper+5e-7))
        checks['coordinate_hash'] &= b['coordinate_sha256'] == digest(b['coordinates'])
        for i, x in enumerate(b['coordinates']):
            p, ident = tuple(x), [arm, seed, i]
            for name, registry in [('public_exact', public), ('public_rounded6', rounded_public)]:
                if p in registry:
                    collisions.append(dict(kind=name, point=ident, x=x))
            if p in seen:
                collisions.append(dict(kind='generated_duplicate', point=ident, previous=seen[p], x=x))
            else:
                seen[p] = ident
    checks['no_collisions'], checks['unique512'] = not collisions, len(seen) == 512
    return dict(accepted=all(checks.values()), checks={k: bool(v) for k, v in checks.items()}, collisions=collisions)


def main(data):
    try:
        xs = inputs(data)
    except (KeyError, TypeError, ValueError) as exc:
        return dict(implementation_checks_pass=False, input_failure=type(exc).__name__+': '+str(exc))
    candidate = construct(xs)
    checked = verify(candidate, xs)
    stripped = {s: [dict(x=r['x']) for r in data[s]] for s in ('train', 'id_dev', 'diagnostic')}
    poisoned = {s: [dict(x=r['x'], y=object(), validation=object(), error=object()) for r in data[s]] for s in ('train', 'id_dev', 'diagnostic')}
    tests = dict(deterministic=candidate == construct(xs), deleted_labels_invariant=candidate == construct(inputs(stripped)),
                 poisoned_labels_invariant=candidate == construct(inputs(poisoned)))
    controls = {}
    def reject(name, mutated):
        outcome = verify(mutated, xs)
        controls[name] = outcome
        tests[name] = not outcome['accepted']
    tampered = copy.deepcopy(candidate)
    b = tampered['batches'][0]
    b['blocks']['T'][0] = [1.1, 1.1, 1.1]
    b['coordinates'][0] = [1.1, 1.1, 1.1]
    b['coordinate_sha256'] = digest(b['coordinates'])
    reject('reject_consistent_hash_outside_target', tampered)
    tampered = copy.deepcopy(candidate)
    b = tampered['batches'][0]
    b['blocks']['T'][0][0] += .000001
    b['coordinates'][0][0] = b['blocks']['T'][0][0]
    b['coordinate_sha256'] = digest(b['coordinates'])
    reject('reject_consistent_hash_point_tamper', tampered)
    changed_draw = copy.deepcopy(candidate)
    b = changed_draw['batches'][0]
    b['blocks']['T'] = np.round(qmc.scale(qmc.LatinHypercube(d=3, seed=41011).random(64), [1.2, .85, 1.05], [1.45, 1., 1.25]), 6).tolist()
    b['coordinates'] = copy.deepcopy(b['blocks']['T'])
    b['coordinate_sha256'] = digest(b['coordinates'])
    reject('reject_changed_draw_unchanged_metadata', changed_draw)
    stale = copy.deepcopy(candidate)
    stale['batches'][0]['coordinate_sha256'] = '0'*64
    reject('reject_stale_hash', stale)
    wrong = copy.deepcopy(candidate)
    b = wrong['batches'][4]
    b['block_order'] = ['G', 'B', 'T']
    b['coordinates'] = b['blocks']['G'] + b['blocks']['B'] + b['blocks']['T']
    b['coordinate_sha256'] = digest(b['coordinates'])
    reject('reject_wrong_order', wrong)
    wrong = copy.deepcopy(candidate)
    wrong['batches'][0]['seed'] = 4109
    wrong['batches'][0]['stream_seeds']['T'] = 41090
    reject('reject_wrong_seed', wrong)
    return dict(scope='author implementation preflight, not independent scientific validation',
                environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                available_data_keys=sorted(data.keys()), public_row_fields={s: sorted(data[s][0].keys()) for s in xs},
                case_sha256=digest(data['case']), public_full_payload_sha256={s: digest(data[s]) for s in xs},
                candidate_sha256=digest(candidate), candidate=candidate, verification=checked,
                metamorphic_checks=tests, negative_control_outcomes=controls,
                implementation_checks_pass=checked['accepted'] and all(tests.values()))
