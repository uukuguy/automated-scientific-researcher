"""Logical model/compute ledgers preserve existing authoritative usage rows."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from asr_service.budgets import BudgetStore, BudgetError


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'budget.db'
        self.store = BudgetStore(self.path)
        for name, amount in {'turns': 5, 'tool_executions': 10, 'research_walltime_ms': 1000,
                             'attempts': 2, 'execution_ms': 100}.items():
            self.store.set_limit('p', name, amount)

    def test_legacy_usage_and_live_reservations_are_not_reset_or_double_counted(self):
        self.store.reserve('p', 'old-model', 'turns', 2)
        self.store.settle('p', 'old-model', 'turns', 2, execution_exited=True)
        self.store.reserve('p', 'in-flight', 'execution_ms', 60)
        with sqlite3.connect(self.path) as db:
            before = db.execute('SELECT * FROM asr_budget_reservations ORDER BY attempt,dimension').fetchall()
        reopened = BudgetStore(self.path)
        view = reopened.ledger_snapshot('p')
        self.assertEqual(view['model']['turns']['spent'], 2)
        self.assertEqual(view['compute']['execution_ms']['reserved'], 60)
        self.assertNotIn('total', view)
        self.assertEqual(view['provider_quota'], {'state': 'unknown'})
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT * FROM asr_budget_reservations ORDER BY attempt,dimension').fetchall(), before)

    def test_cross_ledger_admission_is_atomic_and_replay_does_not_reserve_again(self):
        with self.assertRaisesRegex(BudgetError, 'budget_exhausted'):
            self.store.reserve_ledgers('p', 'a', model={'turns': 1}, compute={'execution_ms': 101})
        self.assertEqual(self.store.ledger_snapshot('p')['model']['turns']['reserved'], 0)
        self.store.reserve_ledgers('p', 'a', model={'turns': 1}, compute={'execution_ms': 50})
        self.store.reserve_ledgers('p', 'a', model={'turns': 1}, compute={'execution_ms': 50})
        self.assertEqual(self.store.ledger_snapshot('p')['compute']['execution_ms']['reserved'], 50)
        with self.assertRaisesRegex(BudgetError, 'idempotency_conflict'):
            self.store.reserve_ledgers('p', 'a', model={'turns': 1}, compute={})

    def test_wrong_ledger_and_unknown_dimensions_are_not_silently_reclassified(self):
        for model, compute in [({'attempts': 1}, {}), ({}, {'turns': 1}), ({'gpu_ms': 1}, {})]:
            with self.assertRaisesRegex(BudgetError, 'invalid_ledger_dimension'):
                self.store.reserve_ledgers('p', 'bad', model=model, compute=compute)
        self.store.set_limit('p', 'legacy_custom', 10)
        self.store.reserve('p', 'legacy', 'legacy_custom', 3)
        view = self.store.ledger_snapshot('p')
        self.assertEqual(view['unclassified']['legacy_custom']['reserved'], 3)
        self.assertNotIn('legacy_custom', view['compute'])
        self.assertEqual(self.store.ledger_snapshot('other')['compute'], {})

    def test_failure_cost_and_unknown_inflight_remain_in_separate_ledgers(self):
        self.store.reserve_ledgers('p', 'failed-operation', model={'turns': 1}, compute={'execution_ms': 50})
        self.store.settle('p', 'failed-operation', 'turns', 1, execution_exited=True)
        with self.assertRaisesRegex(BudgetError, 'execution_not_reconciled'):
            self.store.settle('p', 'failed-operation', 'execution_ms', 0, execution_exited=False)
        view = self.store.ledger_snapshot('p')
        self.assertEqual(view['model']['turns']['spent'], 1)
        self.assertEqual(view['compute']['execution_ms']['reserved'], 50)
        self.store.settle('p', 'failed-operation', 'execution_ms', 20, execution_exited=True)
        self.assertEqual(self.store.ledger_snapshot('p')['compute']['execution_ms']['spent'], 20)

    def test_snapshot_joins_owner_transaction(self):
        with self.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.store.reserve_many_in_transaction(db, 'p', 'owned', {'turns': 1})
            self.assertEqual(self.store.ledger_snapshot_in_transaction(db, 'p')['model']['turns']['reserved'], 1)
            db.rollback()
        self.assertEqual(self.store.ledger_snapshot('p')['model']['turns']['reserved'], 0)


if __name__ == '__main__':
    unittest.main()
