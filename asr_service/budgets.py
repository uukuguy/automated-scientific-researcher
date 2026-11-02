"""Trusted local project budget primitive; no execution or authentication.

Amounts are integer metering units (for example milliseconds or microcurrency).
Callers must reconcile process identity before asserting execution_exited.
"""
from asr_service.contracts import PolicyStore


class BudgetError(ValueError):
    pass


class BudgetStore(PolicyStore):
    def __init__(self, path):
        # Reuse connection lifecycle, without initializing policy tables.
        from pathlib import Path
        self.path = Path(path)
        with self._connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS asr_budget_limits (
              project TEXT NOT NULL, dimension TEXT NOT NULL, amount INTEGER NOT NULL,
              PRIMARY KEY(project, dimension));
            CREATE TABLE IF NOT EXISTS asr_budget_reservations (
              project TEXT NOT NULL, attempt TEXT NOT NULL, dimension TEXT NOT NULL,
              amount INTEGER NOT NULL, actual INTEGER,
              PRIMARY KEY(project, attempt, dimension));
            ''')

    @staticmethod
    def _amount(value):
        if type(value) is not int or not 0 <= value <= 2**63 - 1:
            raise BudgetError('invalid_amount')

    @staticmethod
    def _balance(db, project, dimension):
        row = db.execute('SELECT amount FROM asr_budget_limits WHERE project=? AND dimension=?',
                         (project, dimension)).fetchone()
        if row is None:
            raise BudgetError('budget_not_configured')
        # Sum in Python to preserve exact integers even above SQLite SUM limits.
        rows = db.execute('SELECT amount,actual FROM asr_budget_reservations WHERE project=? AND dimension=?',
                          (project, dimension)).fetchall()
        spent = sum(actual for _, actual in rows if actual is not None)
        reserved = sum(amount for amount, actual in rows if actual is None)
        return dict(limit=row[0], spent=spent, reserved=reserved,
                    available=row[0] - spent - reserved)

    def balance(self, project, dimension):
        with self._connect() as db:
            db.execute('BEGIN')
            return self._balance(db, project, dimension)

    def set_limit(self, project, dimension, amount):
        self._identity(project, dimension)
        self._amount(amount)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            exists = db.execute('SELECT 1 FROM asr_budget_limits WHERE project=? AND dimension=?',
                                (project, dimension)).fetchone()
            if exists:
                balance = self._balance(db, project, dimension)
                if amount < balance['spent'] + balance['reserved']:
                    raise BudgetError('below_committed_usage')
            db.execute('INSERT INTO asr_budget_limits VALUES (?,?,?) ON CONFLICT(project,dimension) DO UPDATE SET amount=excluded.amount',
                       (project, dimension, amount))

    def reserve(self, project, attempt, dimension, amount):
        self._identity(project, attempt, dimension)
        self._amount(amount)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT amount FROM asr_budget_reservations WHERE project=? AND attempt=? AND dimension=?',
                               (project, attempt, dimension)).fetchone()
            if prior is not None:
                if prior[0] != amount:
                    raise BudgetError('idempotency_conflict')
                return
            if self._balance(db, project, dimension)['available'] < amount:
                raise BudgetError('budget_exhausted')
            db.execute('INSERT INTO asr_budget_reservations VALUES (?,?,?,?,NULL)',
                       (project, attempt, dimension, amount))

    def settle(self, project, attempt, dimension, actual, *, execution_exited):
        self._identity(project, attempt, dimension)
        self._amount(actual)
        if execution_exited is not True:
            raise BudgetError('execution_not_reconciled')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT actual FROM asr_budget_reservations WHERE project=? AND attempt=? AND dimension=?',
                               (project, attempt, dimension)).fetchone()
            if prior is None:
                raise BudgetError('reservation_not_found')
            if prior[0] is not None:
                if prior[0] != actual:
                    raise BudgetError('idempotency_conflict')
                return
            db.execute('UPDATE asr_budget_reservations SET actual=? WHERE project=? AND attempt=? AND dimension=?',
                       (actual, project, attempt, dimension))
