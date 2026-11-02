import unittest
from powerflow_lab.reference import make_request


class ReferenceConfigTests(unittest.TestCase):
    def test_reference_request_is_frozen_and_finite(self):
        request = make_request(max_iterations=20, timeout_seconds=120)
        self.assertEqual(request['policy'], 'fixed-pv-pq-single-slack/1')
        self.assertTrue(request['image_id'].startswith('sha256:'))
        self.assertEqual(len(request['case_sha256']), 64)
        self.assertIn('validation.py', request['source_hashes'])

    def test_rejects_unbounded_or_invalid_limits(self):
        for timeout in (0, -1, float('inf')):
            with self.assertRaises(ValueError): make_request(timeout_seconds=timeout)
        with self.assertRaises(ValueError): make_request(max_iterations=-1)
