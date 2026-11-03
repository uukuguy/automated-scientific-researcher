import json
import sqlite3
import unittest
from tests import test_supervisor as fixtures
from asr_supervisor.store import ExecutionStore, LeaseError


class EvaluationGateTests(unittest.TestCase):
    setUp=fixtures.ExecutionStoreTests.setUp

    def evaluation(self,state='uncertain',settled=False):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS asr_evaluation_jobs(project,run,evaluation_id,attempt,state,record)')
            db.execute('DELETE FROM asr_evaluation_jobs')
            db.execute('INSERT INTO asr_evaluation_jobs VALUES (?,?,?,?,?,?)',('p','r','v','va',state,json.dumps({'settled':settled})))

    def test_unresolved_evaluator_blocks_numerical_claim_in_same_owner_transaction(self):
        self.evaluation()
        with self.assertRaises(LeaseError):self.store.claim('a','owner')
        self.evaluation('succeeded',True)
        self.assertEqual(self.store.claim('a','owner')['epoch'],1)

    def test_stop_waits_for_settled_evaluation_even_if_state_says_interrupted(self):
        self.evaluation('interrupted',False)
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE asr_runs SET record=?',(json.dumps({'state':'stopping','admission_open':False}),))
            db.execute('UPDATE asr_dispatch SET state=?',('succeeded',))
            ExecutionStore.finalize_controls_in_transaction(db,'p','r')
            self.assertEqual(json.loads(db.execute('SELECT record FROM asr_runs').fetchone()[0])['state'],'stopping')
            db.execute('UPDATE asr_evaluation_jobs SET record=?',(json.dumps({'settled':True}),))
            ExecutionStore.finalize_controls_in_transaction(db,'p','r')
            self.assertEqual(json.loads(db.execute('SELECT record FROM asr_runs').fetchone()[0])['state'],'stopped')
