"""Worker_1 prospective exact comparator. No fitting, solving or rescoring.
Freeze before the single purpose-declared native replay. main(data) consumes
only packet, original native fit and one new native fit. Receipt/exit/dependency
verification is performed against governed service records, not inferred here.
"""
import hashlib
import json
import platform
import numpy as np
import scipy

PACKET = 'trial_eae7b796dde4408382d930d27dbc410c'
ORIGINAL = 'trial_c1597a2d68b445c4b770d7daecf764b2'
AUGMENTATION = 'trial_bd40876f4c5540f7a40fe7f73a762706'
MODEL_HASH = 'cf81c81f7208ff452f7be06595ff0afdcf7f4e4c8072aad1eed234ae46b4f589'
PACKET_HASH = '1c7c27ed77ea933825a2d3d2bbebcce020b9455e7c6ea4a38a8d849a66f20611'
XY_HASH = 'b94ad271ee83e10a05443ece530a1b3ceb88fdfcc7a04a85a7f6612d57c64101'
CASE_HASH = '1fa94780bf0e3bfb3bdd571c7b1e7031db5942923c39adf599f1624fd6fdd41e'
TRAIN_HASH = 'd536db8339fdfe8ad52c32ae993c66f76da9d8823b3dc02469946df035519e3f'
CHECK_NAMES = sorted(['all_rows_labelled', 'augmentation_coordinates',
    'augmentation_count', 'augmentation_event_order',
    'exact_previous_author_reconstruction', 'finite_dimensions', 'fixed_case',
    'fixed_original_payload', 'frozen_paired_payload_hash', 'model_policy',
    'native_augmentation_counts', 'native_model_equals_synthesis_copy',
    'original_count', 'original_model'])
POLICY = dict(schema='regional-load-quadratic/1',
    features=['1','z0','z1','z2','z0^2','z1^2','z2^2','z0*z1','z0*z2','z1*z2'],
    z='x-1', ridge=1e-10, unpenalized_intercept=True, row_weight='equal',
    original_count=128, augmentation_count=64)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def result(trial):
    found = [e['result'] for e in trial['events'] if e['type'] == 'result']
    if len(found) != 1:
        raise ValueError('Expected exactly one terminal result, got ' + str(len(found)))
    return found[0]


def array_info(value):
    try:
        a = np.asarray(value, dtype=float)
        return dict(shape=list(a.shape), finite=bool(np.isfinite(a).all())), a
    except (TypeError, ValueError) as exc:
        return dict(shape=None, finite=False, error=str(exc)), None


def differences(a, b, path='$'):
    """Retain every differing field/value/shape; never use tolerances."""
    out = []
    if type(a) is not type(b):
        out.append(dict(path=path, kind='type', original_type=type(a).__name__,
                        replay_type=type(b).__name__, original=a, replay=b))
    elif isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            p = path + '.' + key
            if key not in a or key not in b:
                out.append(dict(path=p, kind='missing_field',
                    in_original=key in a, in_replay=key in b,
                    original=a.get(key), replay=b.get(key)))
            else:
                out.extend(differences(a[key], b[key], p))
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(dict(path=path, kind='length', original=len(a), replay=len(b)))
        for i in range(min(len(a), len(b))):
            out.extend(differences(a[i], b[i], path + '[' + str(i) + ']'))
        if len(a) != len(b):
            out.append(dict(path=path, kind='unmatched_tail',
                            original=a[min(len(a),len(b)):], replay=b[min(len(a),len(b)):]))
    elif a != b:
        out.append(dict(path=path, kind='value', original=a, replay=b))
    return out


def main(data):
    trials = data['trials']
    replay_ids = sorted(set(trials) - {PACKET, ORIGINAL})
    if len(trials) != 3 or len(replay_ids) != 1:
        return dict(comparison_complete=False, error='Expected exactly packet/original/one replay',
                    provided_trial_ids=sorted(trials))
    replay_id = replay_ids[0]
    packet_result, old, new = result(trials[PACKET]), result(trials[ORIGINAL]), result(trials[replay_id])
    report = packet_result['author_output']
    packet = report['packet']
    original, replay = old.get('model'), new.get('model')
    paired = packet['ordered_xy_payload']
    weights = {}
    checks = dict(
        packet_operation=packet_result.get('operation') == 'analysis',
        packet_ready=report.get('packet_ready') is True,
        exact_packet_check_names=sorted(report.get('checks', {})) == CHECK_NAMES,
        packet_all_checks=all(v is True for v in report.get('checks', {}).values()),
        packet_no_failures=report.get('failures') == [],
        packet_hash=digest(packet) == PACKET_HASH == report.get('packet_sha256'),
        packet_schema=packet.get('schema') == 'team-frozen-training-replay-packet/1',
        packet_sources=packet.get('source_trials') == dict(synthesis='trial_13fa49dde9024b41921d1ba0cbbbca29', primary=ORIGINAL, augmentation=AUGMENTATION),
        packet_fit_request=packet.get('proposed_native_fit_request') == dict(operation='fit', augmentation_trials=[AUGMENTATION]),
        packet_policy=packet.get('trainer_policy') == POLICY,
        fixed_case=digest(data['case']) == CASE_HASH == packet.get('case_canonical_sha256'),
        original128_full_hash=digest(data['train']) == TRAIN_HASH == packet.get('train_full_canonical_sha256'),
        original128_count=len(data['train']) == 128,
        original128_labelled=all(r.get('status') == 'labelled' for r in data['train']),
        original128_xy_order=paired[:128] == [dict(x=r['x'], y=r['y']) for r in data['train']],
        ordered192_count=len(paired) == 192,
        ordered192_hash=digest(paired) == XY_HASH == packet.get('ordered_xy_sha256'),
        augmentation_coordinate_hash=digest([r['x'] for r in paired[128:]]) == '8dccc1e9c2029383658f947f8a90d4f45729b71c16cb58f620a3da5786c69930',
        packet_model=packet.get('original_model') == original,
        original_model_hash=digest(original) == MODEL_HASH == packet.get('original_model_sha256'),
        replay_distinct_trial=replay_id not in (ORIGINAL, PACKET))
    for name, rows, shape in [('x', [r['x'] for r in paired], [192,3]),
                              ('y', [r['y'] for r in paired], [192,236])]:
        info, _ = array_info(rows)
        checks['ordered192_' + name] = info['shape'] == shape and info['finite']
    arrays = {}
    for name, native, model, tid in [('original', old, original, ORIGINAL), ('replay', new, replay, replay_id)]:
        is_model = isinstance(model, dict)
        weights[name], arrays[name] = array_info(model.get('weights') if is_model else None)
        checks[name + '_fit_operation'] = native.get('operation') == 'fit' and trials[tid]['variables'].get('operation') == 'fit'
        checks[name + '_model_fields'] = is_model and sorted(model) == ['ridge','schema','training_count','weights']
        checks[name + '_policy'] = is_model and model.get('schema') == POLICY['schema'] and model.get('ridge') == 1e-10 and model.get('training_count') == 192
        checks[name + '_finite_weights'] = weights[name]['shape'] == [10,236] and weights[name]['finite']
        checks[name + '_augmentation_counts'] = native.get('augmentation_labelled') == 64 and native.get('augmentation_proposed') == 64
    object_equal = original == replay
    hash_equal = digest(original) == digest(replay)
    weight_difference = None
    differing_weights = None
    a, b = arrays['original'], arrays['replay']
    if a is not None and b is not None and a.shape == b.shape and a.size and np.isfinite(a).all() and np.isfinite(b).all():
        weight_difference = float(np.max(np.abs(a-b)))
        differing_weights = int(np.count_nonzero(a != b))
    checks = {k: bool(v) for k,v in checks.items()}
    return dict(comparison_complete=True, integrity_checks=checks,
        integrity_failures=[k for k,v in checks.items() if not v],
        exact_reproduction=all(checks.values()) and object_equal and hash_equal,
        model_object_exact_equal=object_equal, canonical_model_hash_equal=hash_equal,
        original_model_sha256=digest(original), replay_model_sha256=digest(replay),
        structured_differences=differences(original,replay), weight_details=weights,
        max_absolute_weight_difference=weight_difference, differing_weight_count=differing_weights,
        packet_sha256=digest(packet), ordered_xy_sha256=digest(paired),
        case_sha256=digest(data['case']), original128_sha256=digest(data['train']),
        source_trial_ids=dict(packet=PACKET, original=ORIGINAL, replay=replay_id),
        raw_native_fit_trials={ORIGINAL:trials[ORIGINAL], replay_id:trials[replay_id]},
        packet_check_report=dict(packet_ready=report['packet_ready'], checks=report['checks'], failures=report['failures']),
        environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform()),
        limits='Role-separated governed reproduction, shared service/trainer/runtime, visible inputs. Not externally independent replay, hidden evaluation, operating feasibility or a historical function-argument attestation. Original complete contemporaneous task input is preserved per external custody report; absent extra function-argument receipt is not input loss. Analysis versions measured here do not attest native-fit loaded bytes. Dependencies/attempt IDs/terminal exits must be checked against service receipts outside this author analysis. Public development scores retained only as incidental native output; no scoring or candidate switching performed.')
