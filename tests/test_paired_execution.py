"""Opt-in real paired solves: accounting and provenance, not sampler efficacy."""
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

import test_study_execution as fixtures
from test_paired_sampling import protocol


@unittest.skipUnless(os.environ.get('ASR_SCIENTIFIC_IMAGE'), 'requires explicitly selected scientific image')
class PairedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.StudyExecutionTests('test_real_batch_and_unchanged_training_through_owning_ledger')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_shared_coordinate_is_solved_and_charged_for_each_arm(self):
        service = self.f.service
        document = copy.deepcopy(self.f.contract)
        document['provenance']['paired_sampling'] = protocol()
        service.publish_contract('human-secret', 'p', 'c', document, expected_revision=1, idempotency_key='paired-contract')
        state = service.get_run('human-secret', 'p', 'r')
        service.command('human-secret', 'p', 'r', 'apply_contract', expected_revision=state['control_revision'],
            idempotency_key='paired-apply', payload=dict(contract_id='c', revision=2))
        from research_projects.paired_acquisition import native_adapter as adapter, prototype
        plan = dict(kind='static-plan/1', rows=[dict(proposal_id=arm, arm=arm, seed=1101,
            stream='shared', x=[1.,1.,1.]) for arm in ('A','B')])
        case = json.loads(Path('artifacts/p4-simulated-client-001/public/case.json').read_text())
        pins = {field:'a'*64 for field in prototype.CONTRACT_FIELDS}
        pins['case_sha256'] = prototype.digest(case)
        for field, source in [('scenario_source_sha256','research_projects/ood_augmentation/project.py'),('validator_source_sha256','powerflow_lab/validation.py')]:
            pins[field] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
        # Compute and persist expected inputs before launching either solver.
        expected = adapter.prepare_inputs(case, plan, pins)
        expected_hashes = {pid:prototype.digest(value) for pid,value in expected.items()}
        (Path(self.f.tmp.name)/'expected-inputs.json').write_bytes(prototype.canonical(expected_hashes))
        trials = []; receipts = []
        for arm in ('A', 'B'):
            trial, execution, path = self.f.execute(arm, dict(operation='label', purpose='augmentation',
                coordinates=[[1., 1., 1.]], paired_batch=dict(group_id='g', arm_id=arm)))
            self.assertEqual(execution['state'], 'succeeded')
            manifest = json.loads((path / 'manifest.json').read_text())
            self.assertEqual(manifest['paired_sampling'], trial['paired_sampling'])
            rows = [event['row'] for event in json.loads((path / 'study-events.json').read_text()) if event['type'] == 'sample']
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'labelled')
            proposal = next(p for p in plan['rows'] if p['arm']==arm)
            receipts.append(adapter.convert(proposal, rows[0], pins, expected[arm]))
            trials.append(trial)
        ledger = prototype.ingest(plan, receipts, pins, expected_hashes)
        self.assertEqual(ledger['proposed'],2)
        (Path(self.f.tmp.name)/'adapter-ledger.json').write_bytes(prototype.canonical(ledger))
        self.assertNotEqual(trials[0]['execution_attempt_id'], trials[1]['execution_attempt_id'])
        self.assertEqual(service.budgets.balance('p', 'sample_proposals')['spent'], 2)
        self.assertEqual(service.budgets.balance('p', 'attempts')['spent'], 2)
        self.assertEqual(service.budgets.balance('p', 'attempts')['reserved'], 0)
        with self.assertRaisesRegex(ValueError, 'paired_fit_one_arm_required'):
            self.f.execute('pooled', dict(operation='fit', augmentation_trials=[t['trial_id'] for t in trials]))
        _, fitted, fitted_path = self.f.execute('fit-A', dict(operation='fit', augmentation_trials=[trials[0]['trial_id']]))
        self.assertEqual(fitted['state'], 'succeeded')
        self.assertEqual(json.loads((fitted_path / 'study-result.json').read_text())['model']['training_count'], 129)
        original_manifest = (path / 'manifest.json').read_bytes()
        manifest = json.loads(original_manifest)
        manifest['paired_sampling']['arm_id'] = 'A'
        (path / 'manifest.json').write_text(json.dumps(manifest))
        try:
            with self.assertRaisesRegex(ValueError, 'manifest paired sampling mismatch'):
                self.f.supervisor._report(execution, path)
        finally:
            (path / 'manifest.json').write_bytes(original_manifest)


if __name__ == '__main__':
    unittest.main()
