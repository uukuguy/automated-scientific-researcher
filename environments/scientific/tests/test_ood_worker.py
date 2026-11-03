"""Trusted experiment primitives; these are not model-driven research tests."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from research_projects.ood_augmentation import project
from research_projects.ood_augmentation import worker


class WorkerTests(unittest.TestCase):
    def test_all_coordinates_validated_before_first_solve(self):
        request = dict(operation='label', purpose='augmentation', coordinates=[[1, 1, 1], [2, 1, 1]])
        with patch.object(project, 'solve_sample') as solve:
            with self.assertRaises(ValueError):
                worker.execute(request, {'case': project.load_case()}, lambda event: None)
            solve.assert_not_called()

    def test_failed_proposals_preserved_without_retry(self):
        events = []
        request = dict(operation='label', purpose='probe', coordinates=[[1, 1, 1], [1.1, 1, 1]])
        with patch.object(project, 'solve_sample', side_effect=[
            dict(status='label_failure', y=None), dict(status='invalid_label', y=None),
        ]) as solve:
            result = worker.execute(request, {'case': project.load_case()}, events.append)
        self.assertEqual(solve.call_count, 2)
        self.assertEqual(result['proposed'], 2)
        self.assertEqual(result['labelled'], 0)
        self.assertEqual([e['index'] for e in events], [0, 1])

    def test_training_rejects_probe_material_and_diagnostic_duplicates(self):
        case = project.load_case()
        materials = dict(case=case, train=[], diagnostic=[{'x': [1.2, .9, 1.1]}], id_dev=[])
        materials['augmentation'] = [dict(purpose='probe', rows=[])]
        with self.assertRaisesRegex(ValueError, 'augmentation'):
            worker.execute({'operation': 'fit'}, materials, lambda e: None)
        materials['augmentation'] = [dict(purpose='augmentation', rows=[{'x': [1.2, .9, 1.1]}])]
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            worker.execute({'operation': 'fit'}, materials, lambda e: None)

    def test_real_label_and_forged_target_rejected(self):
        case = project.load_case()
        row = project.solve_sample(case, [1, 1, 1], 'test')
        self.assertEqual(row['status'], 'labelled')
        worker.verify_label(case, row)
        row['y'][0] += .001
        with self.assertRaisesRegex(ValueError, 'target'):
            worker.verify_label(case, row)


if __name__ == '__main__':
    unittest.main()
