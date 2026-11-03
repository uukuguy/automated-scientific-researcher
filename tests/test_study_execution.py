"""Opt-in real isolated pipeline checks, not autonomous research evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest

import test_control_service as fixtures
from asr_service import study
from asr_supervisor.study import StudyBackend
from asr_supervisor.store import ExecutionStore
from asr_supervisor.supervisor import Supervisor


@unittest.skipUnless(os.environ.get('ASR_SCIENTIFIC_IMAGE'), 'requires explicitly selected scientific image')
class StudyExecutionTests(unittest.TestCase):
    def setUp(self):
        fixtures.ControlTests.setUp(self)
        self.image = os.environ['ASR_SCIENTIFIC_IMAGE']
        public = Path('artifacts/p4-simulated-client-001/public').resolve()
        if not public.is_dir():
            self.skipTest('requires prepared immutable simulated client')
        config = dict(public_directory=str(public), public_manifest_sha256=hashlib.sha256((public / 'manifest.json').read_bytes()).hexdigest(),
                      image_id=self.image, validator_sha256=hashlib.sha256(Path('powerflow_lab/validation.py').read_bytes()).hexdigest())
        self.contract['provenance'] = dict(capability_profile=study.CAPABILITY, study=config)
        self.contract['budget'].update(attempts=5, execution_ms=300000, sample_proposals=64)
        self.contract['execution_policy']['timeout_seconds'] = 60
        for kind, document in study.expected_references(config).items():
            self.contract[kind + '_ref'] = self.service.references.register('p', kind, document)
        fixtures.ControlTests.start(self)
        self.service.publish_hypothesis('agent-secret', 'p', 'h', dict(statement='Engineering calibration',
            prediction='Frozen worker reproduces labels and trainer', scope='interface test only',
            refutation_criteria='Mismatch', study_type='exploratory', change_reason='initial', analysis_timing='prospective'),
            expected_revision=0, idempotency_key='h')
        self.backend = StudyBackend(self.image)
        self.supervisor = Supervisor(ExecutionStore(self.service.path), Path(self.tmp.name) / 'evidence', backend=self.backend)
        self.addCleanup(self.remove_owned_containers)

    def remove_owned_containers(self):
        for container in self.backend.collectors:
            subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=True)

    def execute(self, key, request, timeout=60):
        trial = self.service.submit_study('agent-secret', 'p', 'r', request_key=key, request=request,
            timeout_seconds=timeout, hypothesis_ref=dict(project_id='p', hypothesis_id='h', revision=1))
        execution = self.supervisor.execute(trial['execution_attempt_id'], 'test-worker')
        return trial, execution, Path(execution['report']['evidence_path'])

    def test_real_batch_and_unchanged_training_through_owning_ledger(self):
        # Deliberately arbitrary engineering coordinates, not a sampler proposal.
        points = [[1 + (i + 1) * .001, .99, 1.01] for i in range(64)]
        trial, result, path = self.execute('labels', dict(operation='label', purpose='augmentation', coordinates=points))
        self.assertEqual(result['state'], 'succeeded', (path / 'candidate-stream.log').read_text()[-2000:])
        outcome = json.loads((path / 'study-result.json').read_text())
        self.assertEqual(outcome['labelled'], 64)
        self.assertEqual(self.service.budgets.balance('p', 'sample_proposals')['spent'], 64)
        baseline_trial, baseline, baseline_path = self.execute('baseline', dict(operation='fit', augmentation_trials=[]))
        self.assertEqual(baseline['state'], 'succeeded')
        actual = json.loads((baseline_path / 'study-result.json').read_text())
        expected = json.loads(Path('artifacts/p4-simulated-client-001/public/baseline-report.json').read_text())['metrics']
        for name in ('id_dev', 'diagnostic'):
            self.assertAlmostEqual(actual['development'][name]['pq_voltage_rmse_pu'], expected[name]['pq_voltage_rmse_pu'], places=12)
        _, fitted, fitted_path = self.execute('fit', dict(operation='fit', augmentation_trials=[trial['trial_id']]))
        self.assertEqual(fitted['state'], 'succeeded')
        self.assertEqual(json.loads((fitted_path / 'study-result.json').read_text())['model']['training_count'], 192)
        with self.assertRaisesRegex(ValueError, 'completed_label_trial_required|augmentation_label_trial_required'):
            self.execute('bad', dict(operation='fit', augmentation_trials=[baseline_trial['trial_id']]))
        inspected = json.loads((path / 'container-inspection.json').read_text())
        altered = copy.deepcopy(inspected); altered['HostConfig']['NetworkMode'] = 'bridge'
        identity = json.loads((path / 'identity.json').read_text())
        # Published paths differ from the original mount paths; use recorded one.
        original_path = Path(inspected['Mounts'][0]['Source']).parent
        with self.assertRaisesRegex(RuntimeError, 'isolation'):
            self.backend.verify_container(altered, identity, original_path)
        self.assertFalse(any(self.service.budgets.balance('p', d)['reserved'] for d in ('attempts', 'execution_ms', 'sample_proposals')))

    def test_timeout_preserves_raw_evidence_and_charges_proposals(self):
        _, result, path = self.execute('timeout', dict(operation='label', purpose='probe',
            coordinates=[[1 + (i + 1) * .001, .99, 1.01] for i in range(64)]), timeout=1)
        self.assertEqual(result['state'], 'timed_out')
        self.assertTrue((path / 'limit-trigger.json').is_file())
        self.assertTrue((path / 'study-events.json').is_file())
        self.assertEqual(self.service.budgets.balance('p', 'sample_proposals')['spent'], 64)
        self.assertEqual(self.service.get_run('agent-secret', 'p', 'r')['state'], 'running')

    def test_author_analysis_is_isolated_and_cannot_supply_training_labels(self):
        source = '''def main(data):
    import os, pathlib, socket
    checks = {"uid": os.getuid(), "train_count": len(data["train"]),
              "docker_socket": pathlib.Path("/var/run/docker.sock").exists(),
              "api_keys": [k for k in os.environ if k.upper().endswith("_API_KEY")]}
    try:
        pathlib.Path("/input.json").write_text("corrupt")
        checks["write_denied"] = False
    except OSError:
        checks["write_denied"] = True
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=1).close()
        checks["network_denied"] = False
    except OSError:
        checks["network_denied"] = True
    return checks
'''
        trial, result, path = self.execute('analysis', dict(operation='analysis', source=source, input_trials=[]))
        self.assertEqual(result['state'], 'succeeded', (path / 'candidate-stream.log').read_text()[-2000:])
        output = json.loads((path / 'study-result.json').read_text())
        self.assertFalse(output['independently_validated'])
        self.assertEqual(output['author_output'], dict(uid=65532, train_count=128, docker_socket=False,
            api_keys=[], write_denied=True, network_denied=True))
        with self.assertRaisesRegex(ValueError, 'augmentation_label_trial_required'):
            self.execute('forged-training', dict(operation='fit', augmentation_trials=[trial['trial_id']]))

    def test_output_overflow_has_receipt_and_retains_failed_attempt(self):
        source = 'def main(data):\n    print("x" * (17 * 1024 * 1024), flush=True)\n    return {}\n'
        _, result, path = self.execute('overflow', dict(operation='analysis',source=source,input_trials=[]))
        self.assertEqual(result['state'],'failed')
        self.assertEqual((path/'candidate-stream.log').stat().st_size,16*1024*1024)
        events=json.loads((path/'resource-events.json').read_text())
        self.assertTrue(any(event['code']=='study_output_limit' for event in events))
        self.assertEqual(self.service.budgets.balance('p','attempts')['spent'],1)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['state'],'running')


if __name__ == '__main__':
    unittest.main()
