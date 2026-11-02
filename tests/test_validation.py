import copy
import math
import unittest
from powerflow_lab.validation import validate


def fixture():
    # V1=1, V2=0.98-j0.02 through z=j0.1.
    # S1=0.2+j0.2; S2=-0.2-j0.192, on 100 MVA base.
    bus = [[1, 3, 0, 0, 0, 0, 1, 1, 0, 100, 1, 1.1, 0.9],
           [2, 1, 20, 19.2, 0, 0, 1, 1, 0, 100, 1, 1.1, 0.9]]
    gen = [[1, 0, 0, 100, -100, 1, 100, 1, 100, 0]]
    branch = [[1, 2, 0, 0.1, 0, 0, 0, 0, 0, 0, 1, -360, 360]]
    inp = dict(baseMVA=100, bus=bus, gen=gen, branch=branch)
    out = copy.deepcopy(inp)
    out['bus'][1][7:9] = [abs(complex(.98, -.02)), math.degrees(math.atan2(-.02, .98))]
    out['gen'][0][1:3] = [20, 20]
    return inp, out


class ValidationTests(unittest.TestCase):
    def test_analytic_root(self):
        inp, out = fixture()
        result = validate(inp, out)
        self.assertTrue(result['equation_valid'])
        self.assertLess(result['max_mismatch_pu'], 1e-12)
        self.assertEqual(result['thermal_limits_unassessed'], 1)
        self.assertEqual(result['operational_status'], 'not_fully_assessed')

    def test_rejects_corrupted_voltage(self):
        inp, out = fixture()
        out['bus'][1][7] += .01
        self.assertFalse(validate(inp, out)['equation_valid'])

    def test_rejects_changed_problem_even_when_root_is_valid(self):
        inp, out = fixture()
        inp['bus'][1][2] += 1
        result = validate(inp, out)
        self.assertFalse(result['input_preserved'])
        self.assertFalse(result['equation_valid'])

    def test_nonfinite_result_is_invalid(self):
        inp, out = fixture()
        out['bus'][1][7] = float('nan')
        self.assertFalse(validate(inp, out)['equation_valid'])

    def test_detects_operating_violation_without_rejecting_root(self):
        inp, out = fixture()
        inp['gen'][0][3] = out['gen'][0][3] = 10
        result = validate(inp, out)
        self.assertTrue(result['equation_valid'])
        self.assertEqual(result['operational_status'], 'violated')

    def test_tap_phase_charging_and_shunt(self):
        # Vfrom = tap * Vto gives zero series current, charging and shunt remain.
        inp, out = fixture()
        tap = 1.05
        for case in (inp, out):
            case['branch'][0][4] = .02
            case['branch'][0][8:10] = [tap, 10]
            case['bus'][0][7:9] = [tap, 10]
            case['gen'][0][5] = tap
            case['bus'][1][2:6] = [0, 3, 0, 2]
        out['bus'][1][7:9] = [1, 0]
        out['gen'][0][1:3] = [0, -1]
        self.assertTrue(validate(inp, out)['equation_valid'])

    def test_rejects_generation_redispatch(self):
        inp, out = fixture()
        for case in (inp, out):
            case['gen'].append([2, 0, 0, 100, -100, 1, 100, 1, 100, 0])
        out['gen'][1][1] = 1
        self.assertFalse(validate(inp, out)['input_preserved'])

    def test_rejects_reference_angle_change(self):
        inp, out = fixture()
        for bus in out['bus']:
            bus[8] += 12
        self.assertFalse(validate(inp, out)['equation_valid'])

    def test_rejects_pv_control_violation_even_at_balanced_root(self):
        inp, out = fixture()
        for case in (inp, out):
            case['bus'][1][1] = 2
            case['gen'].append([2, 0, 0, 100, -100, 1, 100, 1, 100, 0])
        self.assertFalse(validate(inp, out)['equation_valid'])

    def test_rejects_changed_branch(self):
        inp, out = fixture()
        out['branch'][0][2] = .01
        self.assertFalse(validate(inp, out)['input_preserved'])

    def test_detects_thermal_limit_at_either_end(self):
        inp, out = fixture()
        for case in (inp, out):
            case['branch'][0][5] = 25
        result = validate(inp, out)
        self.assertTrue(result['equation_valid'])
        self.assertEqual(result['operational_status'], 'violated')
        self.assertTrue(any(v['kind'] == 'thermal' for v in result['violations']))

    def test_rejects_unknown_bus_reference(self):
        inp, out = fixture()
        out['branch'][0][1] = 999
        self.assertFalse(validate(inp, out)['equation_valid'])

    def test_rejects_unsupported_bus_policy(self):
        inp, out = fixture()
        for case in (inp, out):
            case['bus'][1][1] = 4
        self.assertFalse(validate(inp, out)['equation_valid'])

    def test_rejects_bad_shape(self):
        inp, out = fixture()
        out['bus'].pop()
        self.assertFalse(validate(inp, out)['equation_valid'])

    def test_requires_positive_finite_tolerance(self):
        inp, out = fixture()
        with self.assertRaises(ValueError):
            validate(inp, out, tolerance_pu=float('inf'))

    def test_angle_limits_use_reported_angles_without_wrapping(self):
        inp, out = fixture()
        for case in (inp, out):
            case['branch'][0][11:13] = [-30, 30]
        out['bus'][1][8] += 360
        result = validate(inp, out)
        self.assertTrue(result['equation_valid'])
        self.assertEqual(result['operational_status'], 'violated')


if __name__ == '__main__':
    unittest.main()
