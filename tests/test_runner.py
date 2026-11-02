import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from powerflow_lab.runner import run_trial, verify_trial, EvidenceError


def execute(path, request):
    (path / 'result.json').write_text(json.dumps(request))
    return {'exit_code': 0, 'status': 'succeeded'}


def submit(root):
    run_trial(root, 'same', {'seed': 1}, execute)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_duplicate_returns_identical_attempt_and_conflict_rejected(self):
        first = run_trial(self.root, 'key', {'seed': 1}, execute)
        second = run_trial(self.root, 'key', {'seed': 1}, execute)
        self.assertEqual(first, second)
        with self.assertRaises(EvidenceError):
            run_trial(self.root, 'key', {'seed': 2}, execute)

    def test_concurrent_requests_publish_one_attempt(self):
        workers = [multiprocessing.Process(target=submit, args=(self.root,)) for _ in range(2)]
        for p in workers: p.start()
        for p in workers:
            p.join(10)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(len(list(self.root.glob('*/attempts/*/manifest.json'))), 1)

    def test_retains_failure_and_explicit_retry(self):
        def fail(path, request):
            (path / 'log.txt').write_text('failed before result')
            raise RuntimeError('deliberate failure')
        first = run_trial(self.root, 'fail', {}, fail)
        self.assertEqual(first['status'], 'failed')
        self.assertEqual(run_trial(self.root, 'fail', {}, execute), first)
        second = run_trial(self.root, 'fail', {}, execute, retry=True)
        self.assertNotEqual(first['attempt_id'], second['attempt_id'])
        self.assertEqual(len(list(self.root.glob('*/attempts/*/manifest.json'))), 2)

    def test_detects_artifact_corruption(self):
        result = run_trial(self.root, 'key', {}, execute)
        artifact = self.root / result['trial_id'] / 'attempts' / result['attempt_id'] / 'result.json'
        artifact.write_text('changed')
        with self.assertRaises(EvidenceError): verify_trial(self.root, 'key')
        with self.assertRaises(EvidenceError): run_trial(self.root, 'key', {}, execute)

    def test_recovers_crash_between_manifest_and_publication(self):
        with patch('powerflow_lab.runner.publish_attempt', side_effect=OSError('crash')):
            with self.assertRaises(OSError): run_trial(self.root, 'key', {}, execute)
        result = run_trial(self.root, 'key', {}, execute)
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(len(list(self.root.glob('*/attempts/*/manifest.json'))), 1)

    def test_unfinished_attempt_is_not_silently_reexecuted(self):
        def interrupt(path, request):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): run_trial(self.root, 'key', {}, interrupt)
        with self.assertRaises(EvidenceError): run_trial(self.root, 'key', {}, execute)

    def test_rejects_symlink_output_without_reading_target(self):
        def symlink(path, request):
            (path / 'bad').symlink_to('/etc/passwd')
            return {'status': 'succeeded', 'exit_code': 0}
        with self.assertRaises(EvidenceError): run_trial(self.root, 'key', {}, symlink)

    def test_request_is_not_changed_by_executor(self):
        request = {'seed': 1}
        def mutate(path, config):
            config['seed'] = 2
            return execute(path, config)
        run_trial(self.root, 'key', request, mutate)
        self.assertEqual(request, {'seed': 1})

    def test_explicit_replay_has_new_trial_and_same_frozen_request(self):
        a = run_trial(self.root, 'first', {'seed': 1}, execute)
        b = run_trial(self.root, 'replay', {'seed': 1}, execute, replay_of=a['trial_id'])
        self.assertNotEqual(a['trial_id'], b['trial_id'])
        self.assertEqual(a['request_hash'], b['request_hash'])
        self.assertEqual(b['replay_of'], a['trial_id'])

    def test_uncertain_execution_does_not_publish_terminal_manifest(self):
        from powerflow_lab.runner import ExecutionUncertain
        def uncertain(path, request):
            raise ExecutionUncertain('cleanup not confirmed')
        with self.assertRaises(ExecutionUncertain):
            run_trial(self.root, 'key', {}, uncertain)
        self.assertEqual(len(list(self.root.glob('*/attempts/*/manifest.json'))), 0)
