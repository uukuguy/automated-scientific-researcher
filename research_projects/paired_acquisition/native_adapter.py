"""Trusted local adapter for the frozen IEEE118 regional-scaling experiment.

Callers must authenticate native evidence and contract pins before calling this
module. Hash equality is integrity checking, not evidence authentication.
Prepare expected inputs before dispatch; never construct that map from receipts.
"""
import copy
import hashlib
from pathlib import Path

from powerflow_lab.validation import validate
from .prototype import check_contract, digest, point, require

ROOT = Path(__file__).resolve().parents[2]


def check_sources(contract):
    check_contract(contract)
    for field, relative in (
        ('scenario_source_sha256', 'research_projects/ood_augmentation/project.py'),
        ('validator_source_sha256', 'powerflow_lab/validation.py'),
    ):
        require(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == contract[field],
                f'fixed source mismatch: {field}')


def prepare_inputs(case, plan, contract):
    """Reconstruct the frozen synthetic dispatch rule without solver dependencies."""
    check_sources(contract)
    require(digest(case) == contract['case_sha256'], 'fixed case mismatch')
    require(plan.get('kind') == 'static-plan/1', 'plan schema')
    inputs = {}
    for proposal in plan['rows']:
        pid = proposal['proposal_id']
        require(pid not in inputs, 'duplicate proposal IDs')
        scales = point(proposal['x'])
        scenario = copy.deepcopy(case)
        for i, bus in enumerate(scenario['bus']):
            multiplier = scales[min(2, i * 3 // len(scenario['bus']))]
            bus[2] *= multiplier
            bus[3] *= multiplier
        scale = sum(b[2] for b in scenario['bus']) / sum(b[2] for b in case['bus'])
        types = {b[0]: b[1] for b in scenario['bus']}
        for gen in scenario['gen']:
            if gen[7] and types[gen[0]] != 3:
                gen[1] *= scale
        inputs[pid] = scenario
    return inputs


def convert(proposal, native, contract, expected_input):
    """Recompute physics and target ordering; preserve negative outcomes in place."""
    check_sources(contract)
    require(point(native['x']) == point(proposal['x']), 'native coordinates mismatch')
    require(native['input_sha256'] == digest(native['input']) == digest(expected_input),
            'exact attempted input mismatch')
    require(type(native['elapsed_ms']) is int and native['elapsed_ms'] >= 0, 'invalid cost')
    status = native['status']
    require(status in ('labelled', 'invalid_label', 'label_failure'), 'native terminal status')
    receipt = dict(proposal_id=proposal['proposal_id'], proposal_sha256=digest(proposal),
        contract_sha256=digest(contract), attempt_count=1, elapsed_ms=native['elapsed_ms'],
        input=copy.deepcopy(native['input']), input_sha256=native['input_sha256'],
        status=status, y=None, converged=None, native_sha256=digest(native))
    if status == 'label_failure':
        require(native.get('y') is None and bool(native.get('error_type'))
                and not any(k in native for k in ('solution', 'solution_sha256', 'validation', 'solver')),
                'failed slot must preserve native exception shape')
        # Some genuine exceptions have an empty str(exception); retain the type.
        receipt['error'] = dict(type=native['error_type'], message=native.get('error', ''))
        return receipt
    solution = native['solution']
    require(native['solution_sha256'] == digest(solution), 'native solution hash')
    check = validate(expected_input, solution, 1e-7)
    require(check['input_preserved'] is True, 'solution changed the problem')
    # Cross-platform libm arithmetic need not produce bit-identical residuals.
    # Recomputed equations govern acceptance; retain both full reports.
    verdicts = ('input_preserved', 'equation_valid', 'operational_status',
                'thermal_limits_unassessed', 'errors', 'policy')
    require(all(native['validation'].get(k) == check[k] for k in verdicts),
            'native validation contradicts independent recomputation')
    require((status == 'labelled') == check['equation_valid'], 'native status contradicts equations')
    target = [b[7] for b in solution['bus']] + [b[8] for b in solution['bus']]
    require(native.get('y') == (target if check['equation_valid'] else None), 'native target order/value mismatch')
    converged = native['solver']['converged']
    require(type(converged) is bool, 'native convergence claim must be boolean')
    receipt.update(solution=copy.deepcopy(solution), solution_sha256=digest(solution),
        converged=converged, native_validation=copy.deepcopy(native['validation']),
        independent_validation=copy.deepcopy(check))
    receipt['check'] = dict(input_sha256=receipt['input_sha256'], solution_sha256=digest(solution),
        validator_source_sha256=contract['validator_source_sha256'], input_preserved=True,
        scenario_matches_proposal=True, target_matches_solution=True,
        equation_valid=check['equation_valid'], tolerance_pu=1e-7,
        operational_status=check['operational_status'] if check['operational_status'] in ('violated', 'satisfied') else 'unassessed',
        thermal_limits_unassessed=check['thermal_limits_unassessed'])
    if status == 'labelled':
        receipt.update(y=target, y_sha256=digest(target))
        receipt['check']['y_sha256'] = digest(target)
    else:
        receipt['reason'] = dict(errors=check['errors'], max_mismatch_pu=check['max_mismatch_pu'])
    return receipt
