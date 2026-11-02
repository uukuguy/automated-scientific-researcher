"""Local transactional admission preparation, not a public execution service.

The trusted authorize callback checks caller access on every request.
The owner_gate must verify the
external run's active/open/healthy state, assets, full contract and supported
capabilities using the supplied transaction. No default gate is provided.
This module creates no research runs, starts no processes and grants no leases.
"""
import json
import uuid
from pathlib import Path
from asr_service.contracts import PolicyStore, encoded
from asr_service.budgets import BudgetStore
from asr_service.references import ReferenceStore


class AdmissionError(ValueError):
    pass


class AdmissionStore(PolicyStore):
    def __init__(self, path):
        self.path = Path(path)
        # Owners initialize policy, budget and reference tables beforehand.
        with self._connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS asr_admission_requests (
                project TEXT NOT NULL, run TEXT NOT NULL, request_key TEXT NOT NULL,
                payload TEXT NOT NULL, record TEXT NOT NULL,
                PRIMARY KEY(project,run,request_key));
            CREATE TABLE IF NOT EXISTS asr_admission_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL,
                record TEXT NOT NULL);
            ''')

    def admit(self, *, project, run, request_key, policy_id, policy_revision, references,
              requested_budget, owner_gate, authorize):
        self._identity(project, run, request_key, policy_id)
        self._revision(policy_revision)
        if type(references) is not dict or set(references) != {
                'problem', 'evaluation', 'candidate', 'input_manifest'}:
            raise AdmissionError('invalid_references')
        payload = encoded([policy_id, policy_revision, references, requested_budget])
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Authorization is also required for replays to avoid data leaks.
            if authorize(db, project, run) is not True:
                raise AdmissionError('forbidden')
            prior = db.execute('SELECT payload,record FROM asr_admission_requests WHERE project=? AND run=? AND request_key=?',
                               (project, run, request_key)).fetchone()
            if prior:
                if prior[0] != payload:
                    raise AdmissionError('idempotency_conflict')
                return json.loads(prior[1])
            if owner_gate(db, project, run) is not True:
                raise AdmissionError('owner_gate_rejected')
            row = db.execute('SELECT record FROM asr_policy_bindings WHERE project=? AND run_id=?',
                             (project, run)).fetchone()
            if row is None:
                raise AdmissionError('run_not_bound')
            binding = json.loads(row[0])
            if binding['policy_id'] != policy_id or binding['policy_revision'] != policy_revision:
                raise AdmissionError('policy_revision_conflict')
            for kind, digest in references.items():
                ReferenceStore.get_in_transaction(db, project, kind, digest)
            trial = 'trial_' + uuid.uuid4().hex
            attempt = 'attempt_' + uuid.uuid4().hex
            # Reuse the budget implementation without opening another writer.
            budget = object.__new__(BudgetStore)
            budget.reserve_many_in_transaction(db, project, attempt, requested_budget)
            record = dict(project_id=project, research_run_id=run, trial_id=trial,
                          execution_attempt_id=attempt, policy_id=binding['policy_id'],
                          policy_revision=policy_revision, references=references,
                          requested_budget=requested_budget, state='queued')
            body = encoded(record)
            db.execute('INSERT INTO asr_admission_requests VALUES (?,?,?,?,?)',
                       (project, run, request_key, payload, body))
            db.execute('INSERT INTO asr_admission_events(project,record) VALUES (?,?)',
                       (project, encoded({'type': 'trial_admitted', **record})))
            # This immutable queued record is a preparation intent, not a lease.
            return json.loads(body)

    def pending(self, project):
        """Trusted owner inspection only; no public or dispatch authorization."""
        with self._connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                'SELECT record FROM asr_admission_requests WHERE project=? ORDER BY rowid', (project,))]
