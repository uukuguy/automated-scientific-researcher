import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from asr_service.budgets import BudgetStore, BudgetError


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.db'
        self.store = BudgetStore(self.path)
        self.store.set_limit('p', 'cpu_ms', 100)

    def test_concurrent_reservations_do_not_overspend(self):
        def reserve(i):
            try:
                self.store.reserve('p', str(i), 'cpu_ms', 60)
                return True
            except BudgetError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(reserve, range(2))), 1)
        self.assertEqual(self.store.balance('p', 'cpu_ms')['reserved'], 60)

    def test_idempotency_and_recovery(self):
        self.store.reserve('p', 'attempt1', 'cpu_ms', 70)
        recovered = BudgetStore(self.path)
        recovered.reserve('p', 'attempt1', 'cpu_ms', 70)
        with self.assertRaises(BudgetError):
            recovered.reserve('p', 'attempt1', 'cpu_ms', 71)
        with self.assertRaises(BudgetError):
            recovered.settle('p', 'attempt1', 'cpu_ms', 20, execution_exited=False)
        self.assertEqual(recovered.balance('p', 'cpu_ms')['reserved'], 70)
        recovered.settle('p', 'attempt1', 'cpu_ms', 20, execution_exited=True)
        recovered.settle('p', 'attempt1', 'cpu_ms', 20, execution_exited=True)
        self.assertEqual(recovered.balance('p', 'cpu_ms'), dict(limit=100, spent=20, reserved=0, available=80))
        with self.assertRaises(BudgetError):
            recovered.settle('p', 'attempt1', 'cpu_ms', 10, execution_exited=True)

    def test_overrun_is_recorded_and_blocks_new_work(self):
        self.store.reserve('p', 'a', 'cpu_ms', 80)
        self.store.settle('p', 'a', 'cpu_ms', 110, execution_exited=True)
        self.assertEqual(self.store.balance('p', 'cpu_ms')['available'], -10)
        with self.assertRaises(BudgetError):
            self.store.reserve('p', 'b', 'cpu_ms', 1)
        with self.assertRaises(BudgetError):
            self.store.set_limit('p', 'cpu_ms', 100)

    def test_invalid_and_cross_project(self):
        for amount in (True, -1, 1.5, float('inf')):
            with self.assertRaises(BudgetError):
                self.store.reserve('p', 'a', 'cpu_ms', amount)
        with self.assertRaises(BudgetError):
            self.store.reserve('other', 'a', 'cpu_ms', 1)
        self.store.reserve('p', 'a', 'cpu_ms', 60)
        with self.assertRaises(BudgetError):
            self.store.set_limit('p', 'cpu_ms', 59)
