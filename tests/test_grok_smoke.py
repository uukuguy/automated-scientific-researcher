"""No-model checks for native dialogue evidence publication."""
import json
from pathlib import Path
import tempfile
import unittest

from integrations.runtimes import grok_smoke


class GrokEvidenceTests(unittest.TestCase):
    def publish(self, path, result):
        helper = getattr(grok_smoke, 'publish_result', None)
        self.assertTrue(callable(helper), 'exclusive evidence publication helper required')
        return helper(path, result)

    def test_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            original = b'original immutable evidence\n'
            path.write_bytes(original)
            with self.assertRaises(FileExistsError):
                self.publish(path, {'status': 'failed'})
            self.assertEqual(path.read_bytes(), original)

    def test_success_requires_explicit_process_group_exit_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, proof in enumerate((None, False, 1)):
                with self.subTest(proof=proof):
                    path = Path(directory) / f'result-{index}.json'
                    result = {'status': 'passed'}
                    if proof is not None:
                        result['owned_process_group_exit_verified'] = proof
                    self.publish(path, result)
                    self.assertEqual(result['status'], 'cleanup_unconfirmed')
                    self.assertEqual(json.loads(path.read_text())['status'], 'cleanup_unconfirmed')

    def test_verified_success_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            result = {'status': 'passed', 'owned_process_group_exit_verified': True}
            self.publish(path, result)
            self.assertEqual(json.loads(path.read_text()), result)
            self.assertEqual(result['status'], 'passed')

    def test_failed_dialogue_remains_failed_after_verified_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            result = {'status': 'timed_out', 'owned_process_group_exit_verified': True}
            self.publish(path, result)
            self.assertEqual(json.loads(path.read_text())['status'], 'timed_out')


if __name__ == '__main__':
    unittest.main()
