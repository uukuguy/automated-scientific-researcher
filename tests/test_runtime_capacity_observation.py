import unittest


class RuntimeCapacityObservationTests(unittest.TestCase):
    def event(self,used):
        return dict(type='asr_context_capacity',schema='asr-pi-context-capacity/1',status='observed',measurement='estimate',
            used_tokens=used,window_tokens=1000,full_next_request_verified=False,provider_payload_verified=False)

    def test_reserve_boundary_warns_but_does_not_grant_or_deny_admission(self):
        from integrations.runtimes.context_capacity import assess
        low=assess(self.event(650));high=assess(self.event(651))
        self.assertFalse(low['warning'])
        self.assertTrue(high['warning'])
        self.assertEqual(high['estimated_remaining_tokens'],-1)
        self.assertEqual(high['recommendation'],'prepare_context_review')
        self.assertFalse(high['hold_new_model_requests'])
        self.assertFalse(high['installation_authorized'])
        self.assertFalse(high['request_capacity_verified'])

    def test_unknown_usage_and_forged_precision_are_not_silently_accepted(self):
        from integrations.runtimes.context_capacity import assess
        unknown=assess(self.event(None))
        self.assertEqual(unknown['recommendation'],'measurement_required')
        forged=assess(dict(self.event(10),measurement='reported',full_next_request_verified=True))
        self.assertEqual(forged['status'],'deferred')
        self.assertFalse(forged['request_capacity_verified'])

    def test_configurable_reserves_scale_without_fixed_model_window(self):
        import json,tempfile
        from pathlib import Path
        from integrations.runtimes.capacity_policy import load_policy
        from integrations.runtimes.context_capacity import assess
        policy=load_policy();del policy['sha256']
        policy['limits']['context_checkpoint_reserve_bps']['value']=5000
        policy['limits']['context_tool_reserve_bps']['value']=0
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'policy.json';path.write_text(json.dumps(policy))
            result=assess(self.event(401),capacity_policy_path=path)
            self.assertTrue(result['warning'])
            self.assertEqual(result['reserves']['checkpoint'],500)
            self.assertEqual(result['reserves']['tool_results'],0)
            policy['limits']['context_checkpoint_reserve_bps']['value']=9000
            path.write_text(json.dumps(policy))
            with self.assertRaises(ValueError):load_policy(path)
