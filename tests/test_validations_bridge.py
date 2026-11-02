"""Research runtime can read evaluator reports but cannot publish them."""
from pathlib import Path
import unittest
import test_validations
from integrations.aar.bridge import ResearchBridge


class ValidationBridgeTests(unittest.TestCase):
    def test_state_recovers_independent_records_without_author_write_tool(self):
        fixture = test_validations.ValidationTests('test_evaluator_only_publication_and_service_hash_identity')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        report, _ = fixture.complete()
        published = fixture.publish(fixture.document(report))
        root = Path(fixture.tmp.name)
        bridge = ResearchBridge(fixture.service, project='p', run='r',
                                researcher_token='agent-secret', supervisor_token='supervisor-secret',
                                workspace=root/'work', snapshots=root/'snapshots')
        self.assertEqual(bridge.call('state', {}, 'read')['validations'], [published])
        self.assertEqual(bridge.state()['run']['resource_ledgers']['provider_quota']['state'], 'unknown')
        with self.assertRaisesRegex(ValueError, 'unsupported_bridge_operation'):
            bridge.call('publish_validation', {'document': fixture.document(report)}, 'forged')
        self.assertEqual(fixture.service.validations('agent-secret', 'p', 'r'), [published])


if __name__ == '__main__':
    unittest.main()
