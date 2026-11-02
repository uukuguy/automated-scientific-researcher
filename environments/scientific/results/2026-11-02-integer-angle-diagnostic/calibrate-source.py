"""Calibrate the pinned pandapower backend against frozen MATPOWER evidence.

This trusted developer command does not admit trials or authorize candidate code.
It reconstructs an original-order solution using only pandapower result tables;
independent checks always use the frozen original electrical problem.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandapower as pp
from pandapower.converter.pypower.from_ppc import from_ppc

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from powerflow_lab.validation import validate


PACKAGES = ('pandapower', 'numpy', 'scipy', 'pandas', 'pyarrow', 'networkx',
            'matplotlib', 'pytest', 'jupyterlab', 'ipykernel')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_fixture(path):
    path = Path(path)
    provenance = json.loads((path / 'provenance.json').read_text())
    for name, record in provenance['files'].items():
        if Path(name).name != name or sha256(path / name) != record['sha256']:
            raise ValueError('fixture hash mismatch: ' + name)
    manifest = json.loads((path / 'original-manifest.json').read_text())
    if sha256(path / 'original-manifest.json') != provenance['original_manifest_sha256']:
        raise ValueError('fixture hash mismatch: original manifest')
    for name in ('input.json', 'solution.json', 'solver.json'):
        if manifest['artifacts'][name] != provenance['files'][name]:
            raise ValueError('fixture hash does not match original publication')
    return (json.loads((path / 'input.json').read_text()),
            json.loads((path / 'solution.json').read_text()), provenance)


def original_admittance(case):
    """Original MATPOWER pi branch/shunt model, independent of converter Ybus."""
    ids = {row[0]: i for i, row in enumerate(case['bus'])}
    ybus = np.zeros((len(ids), len(ids)), dtype=complex)
    for bus in case['bus']:
        ybus[ids[bus[0]], ids[bus[0]]] += complex(bus[4], bus[5]) / case['baseMVA']
    for branch in case['branch']:
        if not branch[10]:
            continue
        f, t = ids[branch[0]], ids[branch[1]]
        y = 1 / complex(branch[2], branch[3])
        tap = (branch[8] or 1) * np.exp(1j * np.deg2rad(branch[9]))
        end = y + .5j * branch[4]
        ybus[f, f] += end / abs(tap)**2
        ybus[f, t] -= y / tap.conjugate()
        ybus[t, f] -= y / tap
        ybus[t, t] += end
    return ybus


def solve_reference(original):
    before = json.dumps(original, sort_keys=True, allow_nan=False)
    ppc = {name: np.asarray(original[name], dtype=float).copy()
           for name in ('bus', 'gen', 'branch')}
    ppc.update(baseMVA=original['baseMVA'], version='2')
    network = from_ppc(ppc, f_hz=60, validate_conversion=False)
    ids = [int(bus[0]) for bus in original['bus']]
    if list(network.bus.index) != ids:
        raise ValueError('unsupported converter bus mapping')
    ref_angle = next(bus[8] for bus in original['bus'] if bus[1] == 3)
    # MATPOWER input has a flat common reference angle (30 degrees here), not
    # zero degrees. Numeric init disables auto DC initialization and reproduces
    # that same flat vector; both solvers apply generator voltage setpoints.
    options = dict(algorithm='nr', init='auto', init_vm_pu=1.0,
                   init_va_degree=ref_angle, calculate_voltage_angles=True,
                   enforce_q_lims=False, enforce_p_lims=False, trafo_model='pi',
                   voltage_depend_loads=False, distributed_slack=False,
                   max_iteration=20, tolerance_mva=1e-10 * original['baseMVA'],
                   numba=False, lightsim2grid=False, v_debug=True)
    started = time.perf_counter()
    pp.runpp(network, **options)
    elapsed = time.perf_counter() - started
    solution = copy.deepcopy(original)
    for row in solution['bus']:
        result = network.res_bus.loc[int(row[0])]
        row[7], row[8] = float(result.vm_pu), float(result.va_degree)
    generator_map = []
    for index, row in enumerate(solution['gen']):
        lookup = network._from_ppc_lookups['gen'].loc[index]
        kind, element = lookup.element_type, int(lookup.element)
        result = network['res_' + kind].loc[element]
        row[1], row[2] = float(result.p_mw), float(result.q_mvar)
        generator_map.append(dict(original_row=index, bus=int(row[0]),
                                  element_type=kind, element=element))
    branch_map = []
    for index, row in enumerate(solution['branch']):
        lookup = network._from_ppc_lookups['branch'].loc[index]
        kind, element = lookup.element_type, int(lookup.element)
        result = network['res_' + kind].loc[element]
        data = network[kind].loc[element]
        if kind in ('line', 'impedance'):
            same_direction = data.from_bus == row[0]
            flow = [result.p_from_mw, result.q_from_mvar, result.p_to_mw, result.q_to_mvar]
        elif kind == 'trafo':
            same_direction = data.hv_bus == row[0]
            flow = [result.p_hv_mw, result.q_hv_mvar, result.p_lv_mw, result.q_lv_mvar]
        else:
            raise ValueError('unsupported converter branch element: ' + kind)
        if not same_direction:
            flow = flow[2:] + flow[:2]
        row[13:17] = [float(x) for x in flow]
        branch_map.append(dict(original_row=index, element_type=kind, element=element,
                               same_direction=bool(same_direction)))
    lookup = network._pd2ppc_lookups['bus']
    ordering = [int(lookup[bus]) for bus in ids]
    actual_ybus = network._ppc['internal']['Ybus'].toarray()[np.ix_(ordering, ordering)]
    discrepancy = float(np.max(np.abs(actual_ybus - original_admittance(original))))
    initial_vm = network._ppc['internal']['Vm_it'][:, 0]
    initial_va = network._ppc['internal']['Va_it'][:, 0]
    return solution, dict(converged=bool(network.converged),
        iterations=int(network._ppc['iterations']), solver_elapsed_seconds=elapsed,
        options=options, bus_map_count=len(ids), generator_map_count=len(generator_map),
        generator_map=generator_map, branch_map=branch_map,
        element_counts={kind:len(network[kind]) for kind in ('bus','gen','sgen','ext_grid','line','trafo','impedance','load','shunt')},
        max_admittance_difference_pu=discrepancy,
        initial_vm_pu_min=float(min(initial_vm)), initial_vm_pu_max=float(max(initial_vm)),
        initial_va_degree_min=float(np.rad2deg(min(initial_va))),
        initial_va_degree_max=float(np.rad2deg(max(initial_va))),
        frozen_request_preserved=before == json.dumps(original, sort_keys=True, allow_nan=False))


def compare(reference, candidate):
    def maximum(name, columns):
        return max(abs(a[column] - b[column]) for a, b in zip(reference[name], candidate[name])
                   for column in columns)
    return dict(max_vm_pu=maximum('bus', [7]), max_va_degree=maximum('bus', [8]),
                max_pg_mw=maximum('gen', [1]), max_qg_mvar=maximum('gen', [2]),
                max_branch_p_mw=maximum('branch', [13, 15]),
                max_branch_q_mvar=maximum('branch', [14, 16]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=HERE / 'fixtures' / 'matpower-case118')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original, reference, provenance = load_fixture(args.fixture)
    solution, solver = solve_reference(original)
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    report = dict(schema='asr-pandapower-calibration/1', created_at=datetime.now(timezone.utc).isoformat(),
        profile='fixed-pv-pq-single-slack/1', purpose='development calibration; not generalization or formal replication',
        environment=dict(python=sys.version, platform=platform.platform(), machine=platform.machine(), packages=versions,
                         uv_lock_sha256=sha256(HERE / 'uv.lock'),
                         calibration_source_sha256=sha256(__file__),
                         independent_validator_sha256=sha256(REPO / 'powerflow_lab' / 'validation.py')),
        fixture=provenance, case_size={key:len(original[key]) for key in ('bus','gen','branch')},
        matpower_solver=json.loads((args.fixture / 'solver.json').read_text()), pandapower_solver=solver,
        matpower_validation=validate(original, reference), pandapower_validation=validate(original, solution),
        differences=compare(reference, solution))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'solution.json').write_text(json.dumps(solution, allow_nan=False) + '\n')
    report['solution_sha256'] = sha256(args.output / 'solution.json')
    (args.output / 'calibration.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(differences=report['differences'], validation=report['pandapower_validation'],
                         admittance_difference_pu=solver['max_admittance_difference_pu']), indent=2))
    if not report['pandapower_validation']['equation_valid']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
