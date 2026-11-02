"""Control-service owned execution facts, joining the admission SQLite database.

This trusted internal adapter is not an authentication boundary. Public callers
must go through ControlService. Expired leases never authorize a second launch:
reconciliation grants only the right to inspect/terminate the original identity.
"""
import json
import time
from datetime import datetime, timezone
from asr_service.contracts import PolicyStore, encoded


class LeaseError(ValueError):
    pass


class ExecutionStore(PolicyStore):
    def __init__(self, path):
        from pathlib import Path
        self.path = Path(path)
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS asr_executions (attempt TEXT PRIMARY KEY, record TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS asr_events(seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, run TEXT, record TEXT)')

    @staticmethod
    def _read(db, attempt):
        row = db.execute('SELECT record FROM asr_executions WHERE attempt=?',(attempt,)).fetchone()
        if row is None: raise LeaseError('execution_not_found')
        return json.loads(row[0])

    @staticmethod
    def _event(db, record, kind):
        db.execute('INSERT INTO asr_events(project,run,record) VALUES (?,?,?)',
                   (record['project'],record['run'],encoded(dict(type=kind,execution_attempt_id=record['attempt'],
                    trial_id=record['trial'],epoch=record['epoch'],state=record['state'],created_at=datetime.now(timezone.utc).isoformat()))))

    @staticmethod
    def _save(db, record):
        db.execute('INSERT INTO asr_executions VALUES (?,?) ON CONFLICT(attempt) DO UPDATE SET record=excluded.record',
                   (record['attempt'],encoded(record)))

    def get(self, attempt):
        with self._connect() as db: return self._read(db,attempt)

    def claim(self, attempt, owner, *, lease_seconds=30, now=None):
        self._identity(attempt,owner)
        if not 0 < lease_seconds <= 3600: raise LeaseError('invalid_lease')
        now = time.time() if now is None else now
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM asr_executions WHERE attempt=?',(attempt,)).fetchone():
                raise LeaseError('reconciliation_required')
            row=db.execute('SELECT id,project,run,trial,state,record FROM asr_dispatch WHERE attempt=?',(attempt,)).fetchone()
            if not row or row[4]!='queued': raise LeaseError('not_dispatchable')
            run=db.execute('SELECT record FROM asr_runs WHERE project=? AND run=?',(row[1],row[2])).fetchone()
            run=json.loads(run[0]) if run else {}
            if run.get('state')!='running' or not run.get('admission_open') or run.get('health','ok')!='ok': raise LeaseError('dispatch_gate_closed')
            for body, in db.execute('SELECT record FROM asr_executions'):
                existing=json.loads(body)
                if existing['run']==row[2] and existing['project']==row[1] and existing['report'] is None:
                    raise LeaseError('run_execution_active')
            reservations=db.execute('SELECT dimension,amount,actual FROM asr_budget_reservations WHERE project=? AND attempt=?',(row[1],attempt)).fetchall()
            if not reservations or any(r[2] is not None for r in reservations): raise LeaseError('reservation_required')
            record=dict(attempt=attempt,trial=row[3],project=row[1],run=row[2],dispatch_id=row[0],
                        dispatch=json.loads(row[5]),epoch=1,owner=owner,lease_until=now+lease_seconds,
                        state='starting',started_at=now,identity=None,report=None)
            self._save(db,record)
            self._event(db,record,'attempt_state_changed')
            db.execute('UPDATE asr_dispatch SET state=? WHERE id=?',('claimed',row[0]))
            return record

    @staticmethod
    def _fence(record, epoch, owner, now):
        if record['epoch']!=epoch or record['owner']!=owner: raise LeaseError('stale_epoch')
        if record['lease_until']<now: raise LeaseError('lease_expired')

    def _update(self, attempt, epoch, owner, change, now=None):
        now=time.time() if now is None else now
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record=self._read(db,attempt)
            self._fence(record,epoch,owner,now)
            if record['report'] is not None: raise LeaseError('already_terminal')
            before=record['state']
            change(record)
            self._save(db,record)
            if record['state']!=before: self._event(db,record,'attempt_state_changed')
            return record

    def heartbeat(self, attempt, epoch, owner, *, lease_seconds=30, now=None):
        if not 0 < lease_seconds <= 3600: raise LeaseError('invalid_lease')
        now=time.time() if now is None else now
        return self._update(attempt,epoch,owner,lambda r:r.update(lease_until=now+lease_seconds),now)

    def attach(self, attempt, epoch, owner, identity, *, now=None):
        def change(r):
            if r['state']!='starting' or r['identity'] is not None: raise LeaseError('identity_already_attached')
            r.update(identity=identity,state='running')
        return self._update(attempt,epoch,owner,change,now)

    def mark_uncertain(self, attempt, epoch, owner, reason, *, now=None):
        now=time.time() if now is None else now
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            r=self._read(db,attempt)
            self._fence(r,epoch,owner,now)
            if r['report'] is not None: raise LeaseError('already_terminal')
            r.update(state='interrupted',uncertainty=reason)
            self._save(db,r)
            self._event(db,r,'attempt_state_changed')
            row=db.execute('SELECT record FROM asr_runs WHERE project=? AND run=?',(r['project'],r['run'])).fetchone()
            run=json.loads(row[0]); run.update(admission_open=False,health='reconciling')
            db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(run),r['project'],r['run']))
            return r

    def dispatch_gate_open(self, attempt):
        with self._connect() as db:
            r=self._read(db,attempt)
            row=db.execute('SELECT record FROM asr_runs WHERE project=? AND run=?',(r['project'],r['run'])).fetchone()
            run=json.loads(row[0]) if row else {}
            return run.get('state')=='running' and run.get('admission_open') is True and run.get('health','ok')=='ok'


    def reconcile_claim(self, attempt, owner, *, lease_seconds=30, now=None):
        self._identity(attempt,owner)
        now=time.time() if now is None else now
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            r=self._read(db,attempt)
            if r['report'] is not None: return r
            if r['lease_until']>=now: raise LeaseError('lease_active')
            r.update(owner=owner,epoch=r['epoch']+1,lease_until=now+lease_seconds,state='reconciling')
            self._save(db,r)
            self._event(db,r,'attempt_state_changed')
            return r

    def should_stop(self, attempt):
        with self._connect() as db:
            r=self._read(db,attempt)
            row=db.execute('SELECT state FROM asr_dispatch WHERE id=?',(r['dispatch_id'],)).fetchone()
            run=db.execute('SELECT record FROM asr_runs WHERE project=? AND run=?',(r['project'],r['run'])).fetchone()
            return not row or row[0] in ('cancelled','cancelling','cancel_requested') or not run or json.loads(run[0]).get('state') in ('stopping','stopped','failed')

    def report(self, attempt, epoch, owner, report, *, now=None):
        now=time.time() if now is None else now
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            r=self._read(db,attempt)
            if r['epoch']!=epoch or r['owner']!=owner: raise LeaseError('stale_epoch')
            if r['report'] is not None:
                if encoded(r['report'])!=encoded(report): raise LeaseError('report_conflict')
                return r
            self._fence(r,epoch,owner,now)
            if report.get('execution_exited') is not True: raise LeaseError('execution_not_reconciled')
            if report.get('status') not in ('succeeded','failed','cancelled','timed_out','interrupted'): raise LeaseError('invalid_status')
            if not report.get('manifest_hash'): raise LeaseError('manifest_required')
            usage=report.get('usage',{})
            rows=db.execute('SELECT dimension,actual FROM asr_budget_reservations WHERE project=? AND attempt=?',(r['project'],attempt)).fetchall()
            if set(usage)!= {row[0] for row in rows}: raise LeaseError('usage_dimensions_mismatch')
            previous=dict(rows)
            for dimension,actual in usage.items():
                if type(actual) is not int or not 0<=actual<=2**63-1: raise LeaseError('invalid_usage')
                if previous[dimension] is not None and previous[dimension]!=actual: raise LeaseError('usage_conflict')
                db.execute('UPDATE asr_budget_reservations SET actual=? WHERE project=? AND attempt=? AND dimension=?',(actual,r['project'],attempt,dimension))
            r.update(state=report['status'],report=report,finished_at=now)
            row=db.execute('SELECT record FROM asr_runs WHERE project=? AND run=?',(r['project'],r['run'])).fetchone()
            if row:
                run=json.loads(row[0])
                if run.get('health')=='reconciling':
                    run['health']='ok'
                    db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(run),r['project'],r['run']))
            self._save(db,r)
            self._event(db,r,'attempt_state_changed')
            self._event(db,r,'artifact_published')
            self._event(db,r,'budget_updated')
            db.execute('UPDATE asr_dispatch SET state=? WHERE id=?',(report['status'],r['dispatch_id']))
            return r

    def reservations(self, record):
        with self._connect() as db:
            return dict(db.execute('SELECT dimension,amount FROM asr_budget_reservations WHERE project=? AND attempt=?',(record['project'],record['attempt'])))
