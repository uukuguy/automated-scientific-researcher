import json
from pathlib import Path
import tempfile
import unittest


class CapacityPolicyTests(unittest.TestCase):
    def test_defaults_have_risk_scope_unit_and_recovery(self):
        from integrations.runtimes.capacity_policy import load_policy
        policy = load_policy()
        self.assertGreaterEqual(policy['limits']['context_boundary_ms']['value'], 120000)
        for limit in policy['limits'].values():
            for field in ('unit', 'scope', 'purpose', 'adequacy', 'recovery'):
                self.assertTrue(limit[field])
        self.assertEqual(len(policy['sha256']), 64)

    def test_explicit_revision_is_fingerprinted_without_mutating_defaults(self):
        from integrations.runtimes.capacity_policy import load_policy
        original = load_policy()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'policy.json'
            revised = {k:v for k,v in original.items() if k != 'sha256'}
            revised['revision'] += 1
            revised['limits']['context_boundary_ms']['value'] = 240000
            path.write_text(json.dumps(revised))
            changed = load_policy(path)
        self.assertNotEqual(changed['sha256'], load_policy()['sha256'])
        self.assertEqual(changed['limits']['context_boundary_ms']['value'], 240000)

    def test_invalid_or_incomplete_policy_cannot_silently_fallback(self):
        from integrations.runtimes.capacity_policy import load_policy
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'bad.json'
            for value in ({}, {'schema':'asr-capacity-policy/1','revision':1,'limits':{}}):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError): load_policy(path)

    def test_pi_uses_central_transport_defaults_and_explicit_overrides(self):
        from integrations.runtimes.pi import PiRuntime
        from integrations.runtimes.capacity_policy import load_policy
        runtime = PiRuntime(model='gpt-5.4')
        self.assertEqual(runtime.max_message_bytes, load_policy()['limits']['pi_message_bytes']['value'])
        self.assertEqual(runtime.capacity_policy['sha256'], load_policy()['sha256'])
        self.assertEqual(PiRuntime(model='gpt-5.4', max_message_bytes=123).max_message_bytes, 123)

    def test_wrong_units_and_inconsistent_buffers_are_rejected(self):
        from integrations.runtimes.capacity_policy import load_policy
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'bad.json'
            for invalid in ('unit', 'buffer', 'bool'):
                policy = load_policy()
                del policy['sha256']
                if invalid == 'unit': policy['limits']['context_boundary_ms']['unit'] = 'bytes'
                if invalid == 'buffer': policy['limits']['pi_buffer_bytes']['value'] = 1
                if invalid == 'bool': policy['limits']['journal_bytes']['value'] = True
                path.write_text(json.dumps(policy))
                with self.assertRaises(ValueError): load_policy(path)

    def test_custom_policy_reaches_pi_without_changing_explicit_parameters(self):
        from integrations.runtimes.capacity_policy import load_policy
        from integrations.runtimes.pi import PiRuntime
        with tempfile.TemporaryDirectory() as root:
            policy = load_policy()
            del policy['sha256']
            policy['revision'] = 2
            policy['limits']['pi_records']['value'] = 200000
            path = Path(root)/'custom.json'
            path.write_text(json.dumps(policy))
            runtime = PiRuntime(model='gpt-5.4', capacity_policy_path=path, max_message_bytes=123)
            self.assertEqual(runtime.max_records, 200000)
            self.assertEqual(runtime.max_message_bytes, 123)
            self.assertEqual(runtime.capacity_policy['revision'], 2)
