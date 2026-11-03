import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from asr_service.budgets import BudgetStore
from asr_supervisor.store import ExecutionStore, LeaseError


class ExecutionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.db'
        self.budget = BudgetStore(self.path)
        self.budget.set_limit('p', 'execution_ms', 10000)
        self.budget.reserve('p', 'a', 'execution_ms', 5000)
        with sqlite3.connect(self.path) as db:
            db.executescript('CREATE TABLE asr_runs(project,run,experiment_id,record); CREATE TABLE asr_dispatch(id PRIMARY KEY,project,run,trial,attempt,state,record);')
            db.execute('INSERT INTO asr_runs VALUES (?,?,?,?)', ('p','r','e',json.dumps({'state':'running','admission_open':True,'health':'ok'})))
            db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)', ('d','p','r','t','a','queued',json.dumps({'request':{'x':1}})))
        self.store = ExecutionStore(self.path)

    def test_exclusive_fencing_and_reconciled_settlement(self):
        claim = self.store.claim('a', 'owner', lease_seconds=1, now=10)
        with self.assertRaises(LeaseError): self.store.claim('a', 'other', now=12)
        self.store.attach('a', claim['epoch'], 'owner', {'container_id':'abc'}, now=10)
        with self.assertRaises(LeaseError): self.store.report('a', 0, 'owner', {'status':'failed'}, now=11)
        self.store.mark_uncertain('a', claim['epoch'], 'owner', 'daemon unavailable', now=10)
        self.assertEqual(self.budget.balance('p','execution_ms')['reserved'],5000)
        takeover = self.store.reconcile_claim('a', 'other', now=12)
        with self.assertRaises(LeaseError): self.store.heartbeat('a',1,'owner', now=12)
        report = {'status':'failed','manifest_hash':'abc','usage':{'execution_ms':200},'execution_exited':True}
        self.store.report('a',takeover['epoch'],'other',report,now=13)
        self.assertEqual(self.budget.balance('p','execution_ms')['spent'],200)
        self.assertEqual(self.store.report('a',takeover['epoch'],'other',report,now=14)['report'],report)

    def test_paused_dispatch_and_expiry_do_not_grant_new_execution(self):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE asr_runs SET record=?', (json.dumps({'state':'running','admission_open':False}),))
        with self.assertRaises(LeaseError): self.store.claim('a','x')
        self.assertEqual(self.budget.balance('p','execution_ms')['reserved'],5000)

    def test_prequeued_attempt_cannot_claim_after_project_execution_overrun(self):
        self.budget.reserve('p','b','execution_ms',5000)
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)',('d2','p','r','t2','b','queued','{}'))
        first=self.store.claim('a','one')
        self.store.report('a',first['epoch'],'one',dict(status='failed',manifest_hash='retained',execution_exited=True,usage={'execution_ms':6000}))
        self.assertEqual(self.budget.balance('p','execution_ms')['available'],-1000)
        with self.assertRaisesRegex(LeaseError,'dispatch_gate_closed'):self.store.claim('b','two')
        self.assertEqual(self.budget.balance('p','execution_ms')['spent'],6000)
        self.assertEqual(self.budget.balance('p','execution_ms')['reserved'],5000)
        self.assertTrue(self.store.get('a')['report']['execution_exited'])

    def test_claimed_attempt_rechecks_all_project_dimensions_before_start(self):
        self.store.claim('a','one')
        self.budget.set_limit('p','turns',1)
        self.budget.reserve('p','model-activity','turns',1)
        self.budget.settle('p','model-activity','turns',2,execution_exited=True)
        self.assertFalse(self.store.dispatch_gate_open('a'))
        self.assertEqual(self.budget.balance('p','execution_ms')['reserved'],5000)
        self.assertEqual(self.budget.balance('p','turns')['spent'],2)

    def test_unknown_execution_cannot_release_budget(self):
        claim=self.store.claim('a','x')
        with self.assertRaises(LeaseError):
            self.store.report('a',claim['epoch'],'x',{'status':'interrupted','usage':{'execution_ms':0},'execution_exited':False})
        self.assertEqual(self.budget.balance('p','execution_ms')['reserved'],5000)

class SupervisorExecutionTests(ExecutionStoreTests):
    def freeze(self,request):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE asr_dispatch SET record=?',(json.dumps({'execution_request':request}),))

    def test_real_process_timeout_failed_cost_and_same_identity(self):
        self.freeze({'timeout_seconds':.1})
        from asr_supervisor.supervisor import Supervisor
        from asr_supervisor.process import ProcessBackend
        import sys
        backend=ProcessBackend([sys.executable,'-c','import time; time.sleep(10)'])
        manager=Supervisor(self.store,Path(self.temp.name)/'evidence',backend=backend,poll_seconds=.01)
        result=manager.execute('a','worker',{'timeout_seconds':.1})
        self.assertEqual(result['state'],'timed_out')
        self.assertEqual(result['report']['trial_id'],'t')
        self.assertEqual(result['report']['execution_attempt_id'],'a')
        self.assertGreater(self.budget.balance('p','execution_ms')['spent'],0)
        self.assertEqual(self.budget.balance('p','execution_ms')['reserved'],0)
        with self.assertRaises(LeaseError): manager.execute('a','worker',{'timeout_seconds':.1})

    def test_publication_crash_reconciles_without_second_execution(self):
        self.freeze({"timeout_seconds":2})
        from asr_supervisor.supervisor import Supervisor
        from asr_supervisor.process import ProcessBackend
        from unittest.mock import patch
        import sys
        backend=ProcessBackend([sys.executable,'-c','print("done")'])
        manager=Supervisor(self.store,Path(self.temp.name)/'evidence',backend=backend,poll_seconds=.01)
        original=manager._report
        with patch.object(manager,'_report',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): manager.execute('a','worker',{'timeout_seconds':2})
        with sqlite3.connect(self.path) as db:
            r=self.store.get('a'); r['lease_until']=0
            db.execute('UPDATE asr_executions SET record=?',(json.dumps(r),))
        restored=manager.reconcile('a','new-worker')
        self.assertEqual(restored['state'],'succeeded')
        self.assertEqual(restored['epoch'],2)
        self.assertEqual(len(list((Path(self.temp.name)/'evidence'/'t').glob('a'))),1)

    def test_conflicting_execution_request_rejected_before_claim(self):
        from asr_supervisor.supervisor import Supervisor
        from asr_supervisor.process import ProcessBackend
        self.freeze({'timeout_seconds':1})
        manager=Supervisor(self.store,Path(self.temp.name)/'evidence',backend=ProcessBackend(['false']))
        with self.assertRaises(ValueError): manager.execute('a','worker',{'timeout_seconds':2})
        with self.assertRaises(LeaseError): self.store.get('a')

    def test_unknown_backend_keeps_reservation_and_closes_run(self):
        from asr_supervisor.supervisor import Supervisor
        from asr_supervisor.process import ProcessBackend
        from unittest.mock import patch
        self.freeze({'timeout_seconds':1})
        backend=ProcessBackend(['true'])
        manager=Supervisor(self.store,Path(self.temp.name)/'evidence',backend=backend)
        with patch.object(backend,'inspect',side_effect=RuntimeError('unknown execution')):
            with self.assertRaises(RuntimeError): manager.execute('a','worker')
        backend.processes['a'].wait(timeout=5)
        self.assertEqual(self.budget.balance('p','execution_ms')['reserved'],5000)
        with sqlite3.connect(self.path) as db: run=json.loads(db.execute('SELECT record FROM asr_runs').fetchone()[0])
        self.assertFalse(run['admission_open'])
        self.assertEqual(run['health'],'reconciling')

    def test_stop_gate_terminates_active_process_and_retains_usage(self):
        from asr_supervisor.supervisor import Supervisor
        from asr_supervisor.process import ProcessBackend
        import sys, threading, time
        self.freeze({'timeout_seconds':5})
        backend=ProcessBackend([sys.executable,'-c','import time;time.sleep(10)'])
        manager=Supervisor(self.store,Path(self.temp.name)/'evidence',backend=backend,poll_seconds=.01)
        def stop():
            for _ in range(100):
                if backend.processes: break
                time.sleep(.01)
            with sqlite3.connect(self.path) as db:
                db.execute('UPDATE asr_runs SET record=?',(json.dumps({'state':'stopping','admission_open':False}),))
        controller=threading.Thread(target=stop); controller.start()
        try: result=manager.execute('a','worker')
        finally: controller.join()
        self.assertEqual(result['state'],'cancelled')
        self.assertFalse(backend.inspect(result['identity'])['running'])
        self.assertGreater(self.budget.balance('p','execution_ms')['spent'],0)

    def test_second_attempt_cannot_start_while_first_is_unresolved(self):
        self.store.claim('a','one')
        self.budget.reserve('p','b','execution_ms',1000)
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)',('d2','p','r','t2','b','queued','{}'))
        with self.assertRaises(LeaseError): self.store.claim('b','two')

    def test_stop_receipt_waits_for_runtime_exit_and_replay_updates(self):
        claimed=self.store.claim('a','owner')
        with sqlite3.connect(self.path) as db:
            db.executescript('CREATE TABLE asr_runtime_sessions(project,run,session_id,state,record); CREATE TABLE asr_commands(project,run,command_id PRIMARY KEY,record); CREATE TABLE asr_requests(project,scope,request_key,payload,record);')
            db.execute('INSERT INTO asr_runtime_sessions VALUES (?,?,?,?,?)',('p','r','s','active','{}'))
            receipt={'command_id':'stop1','kind':'stop','status':'pending','payload':{}}
            db.execute('INSERT INTO asr_commands VALUES (?,?,?,?)',('p','r','stop1',json.dumps(receipt)))
            db.execute('INSERT INTO asr_requests VALUES (?,?,?,?,?)',('p','command:r','key','[]',json.dumps(receipt)))
            db.execute('UPDATE asr_runs SET record=?',(json.dumps({'state':'stopping','admission_open':False}),))
        self.store.report('a',claimed['epoch'],'owner',{'execution_exited':True,'status':'cancelled','manifest_hash':'abc','usage':{'execution_ms':5}})
        with sqlite3.connect(self.path) as db:
            self.assertEqual(json.loads(db.execute('SELECT record FROM asr_runs').fetchone()[0])['state'],'stopping')
            self.assertEqual(json.loads(db.execute('SELECT record FROM asr_commands').fetchone()[0])['status'],'pending')
            db.execute("UPDATE asr_runtime_sessions SET state='exited'")
            ExecutionStore.finalize_controls_in_transaction(db,'p','r')
            self.assertEqual(json.loads(db.execute('SELECT record FROM asr_runs').fetchone()[0])['state'],'stopped')
            self.assertEqual(json.loads(db.execute('SELECT record FROM asr_commands').fetchone()[0])['status'],'applied')
            self.assertEqual(json.loads(db.execute('SELECT record FROM asr_requests').fetchone()[0])['status'],'applied')

    def test_cancel_completion_race_receipt_reports_real_outcome(self):
        claimed=self.store.claim('a','owner')
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE asr_commands(project,run,command_id PRIMARY KEY,record)')
            receipt={'command_id':'cancel1','kind':'cancel_trial','status':'pending','payload':{'trial_id':'t'}}
            db.execute('INSERT INTO asr_commands VALUES (?,?,?,?)',('p','r','cancel1',json.dumps(receipt)))
        self.store.report('a',claimed['epoch'],'owner',{'execution_exited':True,'status':'succeeded','manifest_hash':'abc','usage':{'execution_ms':5}})
        with sqlite3.connect(self.path) as db:
            receipt=json.loads(db.execute('SELECT record FROM asr_commands').fetchone()[0])
        self.assertEqual(receipt['status'],'applied')
        self.assertEqual(receipt['effective_outcome'],'succeeded')
