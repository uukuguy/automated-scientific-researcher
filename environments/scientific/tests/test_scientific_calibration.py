"""Real numerical checks, run only inside the isolated scientific environment."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calibrate import load_fixture, solve_reference, compare, validate


FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures' / 'matpower-case118'


def test_real_case118_converts_and_matches_frozen_matpower_problem():
    original, reference, provenance = load_fixture(FIXTURE)
    solution, metadata = solve_reference(original)
    actual = validate(original, solution)
    expected = validate(original, reference)
    differences = compare(reference, solution)
    assert metadata['converged']
    assert actual['input_preserved']
    assert actual['equation_valid'], actual
    assert actual['operational_status'] == expected['operational_status'] == 'violated'
    assert actual['thermal_limits_unassessed'] == 186
    assert differences['max_vm_pu'] < 1e-8
    assert differences['max_va_degree'] < 1e-6
    assert differences['max_pg_mw'] < 1e-6
    assert differences['max_qg_mvar'] < 1e-6
    assert provenance['original_manifest_sha256']
    assert metadata['bus_map_count'] == 118
    assert metadata['generator_map_count'] == 54
    assert metadata['frozen_request_preserved']
    assert metadata['initial_va_degree_min'] == pytest.approx(30)
    assert metadata['initial_va_degree_max'] == pytest.approx(30)
    assert metadata['max_admittance_difference_pu'] < 1e-10
    assert differences['max_branch_p_mw'] < 1e-6
    assert differences['max_branch_q_mvar'] < 1e-6
    assert not metadata['conversion_audit']['raw_aligned_validation']['input_preserved']
    assert metadata['conversion_audit']['fixed_column_differences']['bus']['VMAX']['count'] == 118
    assert metadata['conversion_audit']['fixed_column_differences']['branch']['RATE_A']['count'] == 186


def test_mutated_solution_fails_independent_equations():
    original, _, _ = load_fixture(FIXTURE)
    solution, _ = solve_reference(original)
    solution['bus'][0][7] += .01
    assert not validate(original, solution)['equation_valid']


def test_fixture_corruption_rejected(tmp_path):
    import shutil
    shutil.copytree(FIXTURE, tmp_path / 'fixture')
    (tmp_path / 'fixture' / 'input.json').write_text('{}')
    with pytest.raises(ValueError, match='fixture hash'):
        load_fixture(tmp_path / 'fixture')
