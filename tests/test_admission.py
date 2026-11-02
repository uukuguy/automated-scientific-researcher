import json
import tempfile
import unittest
from pathlib import Path
from asr_service.admission import AdmissionStore, AdmissionError
from asr_service.budgets import BudgetStore
from asr_service.contracts import PolicyStore
from asr_service.references import ReferenceStore


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.db'
        policy = json.loads(Path('contracts/examples/research-variables.json').read_text())
        self.policies = PolicyStore(self.path)
        self.policies.publish('p', 'policy', policy, expected_revision=0, idempotency_key='pub', actor='human')
        self.policies.apply('p', 'run', 'policy', 1, expected_revision=0, actor='human')
        self.budgets = BudgetStore(self.path)
        self.budgets.set_limit('p', 'cpu_ms', 100)
        refs = ReferenceStore(self.path)
        self.refs = {kind: refs.register('p', kind, {'frozen': kind}) for kind in
                     ('problem', 'evaluation', 'candidate', 'input_manifest')}
        self.gate = lambda db, project, run: True
        self.store = AdmissionStore(self.path)

    def submit(self, key='request', **changes):
        args = dict(project='p', run='run', request_key=key, policy_id='policy', policy_revision=1,
                    references=self.refs, requested_budget={'cpu_ms': 60}, owner_gate=self.gate,
                    authorize=lambda *args: True)
        args.update(changes)
        return self.store.admit(**args)

    def test_atomic_replay_and_frozen_policy(self):
        first = self.submit()
        self.assertEqual(self.submit(), first)
        self.assertEqual(self.budgets.balance('p', 'cpu_ms')['reserved'], 60)
        self.assertEqual(self.store.pending('p'), [first])
        with self.assertRaises(AdmissionError):
            self.submit(requested_budget={'cpu_ms': 61})
        self.assertEqual(self.store.pending('p'), [first])

    def test_rejection_leaves_no_trial_or_reservation(self):
        with self.assertRaises(AdmissionError):
            self.submit(owner_gate=lambda *args: False)
        with self.assertRaises(AdmissionError):
            self.submit(policy_revision=2)
        with self.assertRaises(ValueError):
            self.submit(references={**self.refs, 'problem': 'missing'})
        self.assertEqual(self.store.pending('p'), [])
        self.assertEqual(self.budgets.balance('p', 'cpu_ms')['reserved'], 0)

    def test_budget_failure_and_lost_response_recovery(self):
        first = self.submit()
        with self.assertRaises(ValueError):
            self.submit('second')
        recovered = AdmissionStore(self.path)
        self.assertEqual(recovered.pending('p'), [first])
        self.assertEqual(self.budgets.balance('p', 'cpu_ms')['reserved'], 60)

    def test_replay_after_pause_requires_authorization_but_not_open_gate(self):
        first = self.submit()
        self.gate = lambda *args: False
        self.assertEqual(self.submit(authorize=lambda *args: True), first)
        with self.assertRaises(AdmissionError):
            self.submit('new', authorize=lambda *args: True)
        with self.assertRaises(AdmissionError):
            self.submit(authorize=lambda *args: False)
