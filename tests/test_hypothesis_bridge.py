"""Researcher tool integration: durable hypotheses survive runtime replacement."""
from pathlib import Path
import unittest
from unittest.mock import patch

import test_control_service
from integrations.aar.bridge import ResearchBridge


class HypothesisBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_control_service.ControlTests('test_authenticated_project_and_role_boundaries')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.start()
        root = Path(self.fixture.tmp.name)
        self.options = dict(project='p', run='r', researcher_token='agent-secret',
                            supervisor_token='human-secret', workspace=root/'work', snapshots=root/'snapshots')
        self.bridge = ResearchBridge(self.fixture.service, **self.options)

    def test_researcher_can_publish_then_recover_hypothesis_history(self):
        document = dict(statement='One iteration is insufficient', prediction='Residual exceeds tolerance',
                        scope='case118 flat start', refutation_criteria='Equation-valid after one iteration',
                        study_type='exploratory', change_reason='Initial hypothesis', analysis_timing='prospective')
        args = dict(hypothesis_id='one-step', document=document, expected_revision=0)
        first = self.bridge.call('publish_hypothesis', args, 'hypothesis-1')
        self.assertEqual(first, self.bridge.call('publish_hypothesis', args, 'hypothesis-1'))
        restored = ResearchBridge(self.fixture.service, **self.options)
        self.assertEqual(restored.call('state', {}, 'state')['hypotheses'], [first])
        self.assertEqual(first['revision'], 1)
        trial_args = dict(variables={'iterations': 1},
                          references={k: v for k, v in self.fixture.refs.items() if k != 'reference'},
                          requested_budget={'attempts': 1, 'execution_ms': 5000},
                          hypothesis_ref={'project_id': 'p', 'hypothesis_id': 'one-step', 'revision': 1})
        trial = restored.call('submit_trial', trial_args, 'linked-trial')['receipt']
        self.assertEqual(trial['hypothesis_ref']['sha256'], first['sha256'])
        args.update(expected_revision=1, document=dict(document, prediction='Revised prediction', change_reason='New question'))
        restored.call('publish_hypothesis', args, 'hypothesis-2')
        state = restored.call('state', {}, 'recovered-state')
        self.assertEqual(len(state['hypotheses']), 2)
        self.assertEqual(state['run']['trials'][0]['hypothesis_ref']['revision'], 1)


    def test_bridge_uses_researcher_not_supervisor_for_hypothesis_writes(self):
        with patch.object(self.fixture.service, 'publish_hypothesis', create=True) as publish:
            publish.return_value = {'revision': 1}
            self.bridge.call('publish_hypothesis', {'hypothesis_id': 'h', 'document': {}, 'expected_revision': 0}, 'key')
            self.assertEqual(publish.call_args.args[:2], ('agent-secret', 'p'))


if __name__ == '__main__':
    unittest.main()
