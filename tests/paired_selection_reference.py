"""External test reference for one historical team proposal; not ASR runtime logic.

Developer-authored reference only, not a team deliverable or an execution plan.
Do not import this module from production code or expose it as the research workflow.
Inputs must come from independent scoring of the same valid panel rows. These
functions do not authenticate scores/models, release hidden data or persist a
selection lock; those responsibilities remain with Control/evaluator admission.
"""
import copy
import hashlib
import json
import math
import statistics

ARMS = ('TT', 'BT', 'TG', 'BG')
SEEDS = tuple(str(s) for s in range(1101, 1109))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_scores(roster, metrics, panels, count):
    require(type(roster) is dict and set(roster) == {'baseline', 'arms'} and
            type(roster['arms']) is dict and set(roster['arms']) == set(ARMS), 'complete frozen roster required')
    ids = [roster['baseline']]
    for arm in ARMS:
        require(type(roster['arms'][arm]) is dict and set(roster['arms'][arm]) == set(SEEDS), 'complete frozen seed roster required')
        ids.extend(roster['arms'][arm].values())
    require(all(type(i) is str and i.strip() for i in ids) and len(set(ids)) == 33,
            '33 distinct frozen model identities required')
    require(type(metrics) is dict and set(metrics) == set(ids), 'complete frozen model metrics required')
    for value in metrics.values():
        require(type(value) is dict and set(value) == {'id_rmse', 'target_rmse'} and
                all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in value.values()),
                'finite nonnegative independent metrics required')
    require(type(panels) is dict and set(panels) == {'id', 'target'}, 'both panels required')
    for panel in panels.values():
        require(type(panel) is dict and set(panel) == {'proposed', 'valid'} and
                type(panel['proposed']) is int and panel['proposed'] == count and
                type(panel['valid']) is int and 0 <= panel['valid'] <= count, 'frozen panel membership/count required')
    baseline = metrics[roster['baseline']]
    thresholds = dict(target_rmse_max=.8 * baseline['target_rmse'],
                      id_rmse_max=max(1.1 * baseline['id_rmse'], baseline['id_rmse'] + 1e-5))
    models = {}
    for name, score in metrics.items():
        target_ok = score['target_rmse'] <= thresholds['target_rmse_max']
        id_ok = score['id_rmse'] <= thresholds['id_rmse_max']
        models[name] = dict(score, target_pass=target_ok, id_pass=id_ok, joint_pass=target_ok and id_ok,
            id_rmse_delta=score['id_rmse'] - baseline['id_rmse'],
            id_rmse_ratio=score['id_rmse'] / baseline['id_rmse'] if baseline['id_rmse'] else None,
            target_rmse_ratio=score['target_rmse'] / baseline['target_rmse'] if baseline['target_rmse'] else None)
    return dict(roster=copy.deepcopy(roster), models=models, thresholds=thresholds, panels=copy.deepcopy(panels),
                yield_sufficient=all(p['valid'] * 100 >= p['proposed'] * 95 for p in panels.values()),
                scope='Conditional on common equation-valid rows and the frozen fitted models; no unconditional target-law or unseen-family claim.')


def select_development(roster, metrics, panels):
    result = checked_scores(roster, metrics, panels, 256)
    result.update(schema='asr-paired-development-selection/1', primary_model=None, selected_arm=None, arms={})
    for arm in ARMS:
        trials = roster['arms'][arm]
        passed = [seed for seed in SEEDS if result['models'][trials[seed]]['joint_pass']]
        result['arms'][arm] = dict(passing_seeds=len(passed), eligible=len(passed) >= 7,
            median_target_rmse=statistics.median(metrics[trials[s]]['target_rmse'] for s in SEEDS))
    if not result['yield_sufficient']:
        result['assessment'] = 'label_yield_failure'
        return result
    eligible = [a for a in ARMS if result['arms'][a]['eligible']]
    if not eligible:
        result.update(primary_model=roster['baseline'], assessment='development_objective_unmet')
        return result
    arm = min(eligible, key=lambda a: (result['arms'][a]['median_target_rmse'], a))
    seed = min((s for s in SEEDS if result['models'][roster['arms'][arm][s]]['joint_pass']),
               key=lambda s: (metrics[roster['arms'][arm][s]]['target_rmse'], int(s)))
    result.update(primary_model=roster['arms'][arm][seed], selected_arm=arm, assessment='development_primary_selected')
    return result


def confirm_final(roster, metrics, panels, selection, *, expected_selection_sha256):
    require(digest(selection) == expected_selection_sha256, 'external development selection pin mismatch')
    require(selection.get('schema') == 'asr-paired-development-selection/1' and selection.get('roster') == roster,
            'frozen development roster mismatch')
    # Recompute the selection, not merely its self-reported winner, from its
    # externally pinned independent development metrics and panel accounting.
    dev_metrics = {key: {name: value[name] for name in ('id_rmse', 'target_rmse')}
                   for key, value in selection['models'].items()}
    require(select_development(roster, dev_metrics, selection['panels']) == selection,
            'development selection rule mismatch')
    require(selection['primary_model'] is not None, 'development yield prevents final selection')
    result = checked_scores(roster, metrics, panels, 512)
    primary = selection['primary_model']
    result.update(schema='asr-paired-final-decision/1', primary_model=primary,
                  selection_sha256=expected_selection_sha256, selected_arm=selection['selected_arm'])
    if not result['yield_sufficient']:
        result['assessment'] = 'label_yield_failure'
    elif primary != roster['baseline'] and result['models'][primary]['joint_pass']:
        result['assessment'] = 'final_objective_met'
    else:
        result['assessment'] = 'final_objective_unmet'
    return result
