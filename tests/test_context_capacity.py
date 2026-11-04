import unittest
from asr_context.capacity import decide


class ContextCapacityTests(unittest.TestCase):
    def test_explicit_reserves_trigger_early_checkpoint(self):
        low=decide(used_tokens=600,window_tokens=1000,completion_reserve=100,tool_reserve=100,checkpoint_reserve=100)
        self.assertEqual(low['action'],'continue')
        high=decide(used_tokens=701,window_tokens=1000,completion_reserve=100,tool_reserve=100,checkpoint_reserve=100)
        self.assertEqual(high['action'],'prepare_compression')
        self.assertEqual(high['safe_remaining_tokens'],-1)

    def test_open_interaction_waits_without_cancelling_experiment(self):
        result=decide(used_tokens=950,window_tokens=1000,completion_reserve=100,tool_reserve=100,checkpoint_reserve=100,open_interactions=('tool-call',))
        self.assertEqual(result['action'],'wait_for_boundary')
        self.assertTrue(result['hold_new_model_requests'])
        self.assertFalse(result['cancel_experiments'])

    def test_unknown_usage_is_not_silently_estimated_from_bytes(self):
        result=decide(used_tokens=None,window_tokens=1000,completion_reserve=100,tool_reserve=100,checkpoint_reserve=100)
        self.assertEqual(result['action'],'measurement_required')
        self.assertNotIn('safe_remaining_tokens',result)

    def test_real_capacity_rejection_recovers_without_another_full_prompt(self):
        result=decide(used_tokens=None,window_tokens=None,completion_reserve=100,tool_reserve=100,checkpoint_reserve=100,provider_context_rejected=True)
        self.assertEqual(result['action'],'recover_context')
        self.assertTrue(result['hold_new_model_requests'])

    def test_invalid_units_and_estimates_cannot_drive_exact_admission(self):
        with self.assertRaises(ValueError):decide(used_tokens=True,window_tokens=1000,completion_reserve=100,tool_reserve=100,checkpoint_reserve=100)
        result=decide(used_tokens=800,window_tokens=1000,completion_reserve=100,tool_reserve=100,checkpoint_reserve=100,measurement='estimate')
        self.assertEqual(result['action'],'measure_before_admission')

    def test_actual_context_rejection_is_not_confused_with_transport_errors(self):
        import json
        from pathlib import Path
        cases=json.loads(Path('tests/fixtures/research_context/actual-failures.json').read_text())['cases']
        for case in cases:
            result=decide(used_tokens=None,window_tokens=None,completion_reserve=0,tool_reserve=0,checkpoint_reserve=0,
                          provider_context_rejected=case['observed_category']=='context_capacity')
            self.assertEqual(result['action'],'recover_context' if case['id']=='028-lead_1' else 'measurement_required')
