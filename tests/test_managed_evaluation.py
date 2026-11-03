"""Real Control reservations and managed isolated replay, no model calls."""
import os
import json
import sqlite3
from pathlib import Path
import unittest
from tests import test_control_service as fixtures
from tests.test_candidate_execution import GOOD
from asr_service.control import ControlService
from asr_supervisor.store import ExecutionStore
from asr_supervisor.supervisor import Supervisor
from asr_evaluation.managed import run_evaluation,verify_managed_artifact


@unittest.skipUnless(os.environ.get('ASR_REAL_DOCKER')=='1','explicit local Docker acceptance')
class ManagedEvaluationTests(unittest.TestCase):
    start=fixtures.ControlTests.start

    def setUp(self):
        fixtures.ControlTests.setUp(self)
        credentials=dict(self.service.credentials)
        credentials['supervisor-secret']=dict(subject='executor',role='supervisor',projects=['p'])
        self.service=ControlService(self.service.path,credentials=credentials)
        self.contract['execution_policy']['candidate_profiles']=['octave-candidate/1']
        self.contract['budget'].update(evaluation_attempts=3,evaluation_ms=30000)
        self.start()
        registered=self.service.register_candidate('agent-secret','p',request_key='code',source=GOOD,entrypoint='candidate.m',profile='octave-candidate/1')
        refs={k:v for k,v in self.refs.items() if k!='reference'};refs['candidate']=registered['digest']
        trial=self.service.submit_trial('agent-secret','p','r',request_key='candidate',variables={'solver':'octave-candidate/1'},references=refs,requested_budget={'attempts':1,'execution_ms':5000})
        manager=Supervisor(ExecutionStore(self.service.path),Path(self.tmp.name)/'executions',poll_seconds=.02)
        execution=manager.execute(trial['execution_attempt_id'],'owner')
        self.target=dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],manifest_hash=execution['report']['manifest_hash'],evaluation_ref=refs['evaluation'])

    def test_real_authorized_recheck_settles_distinct_evaluator_budget(self):
        job=self.service.admit_evaluation('agent-secret','p','r',request_key='evaluation',target=self.target,requested_budget={'evaluation_attempts':1,'evaluation_ms':5000})
        completed=run_evaluation(self.service,'supervisor-secret','p','r',job['evaluation_id'],'evaluator-owner',Path(self.tmp.name)/'evaluation')
        self.assertTrue(completed['settled'])
        self.assertTrue(completed['report']['result']['equation_valid'])
        self.assertEqual(completed['report']['authority']['evaluation_attempt_id'],job['evaluation_attempt_id'])
        self.assertEqual(self.service.budgets.balance('p','evaluation_attempts')['spent'],1)
        self.assertEqual(self.service.budgets.balance('p','evaluation_ms')['reserved'],0)
        self.assertGreater(self.service.budgets.balance('p','evaluation_ms')['spent'],0)
        checked=verify_managed_artifact(completed['artifact']['path'],completed['artifact']['authority'])
        self.assertEqual(checked['isolation_facts']['container_id'],completed['identity']['container_id'])
        with self.assertRaises(ValueError):verify_managed_artifact(completed['artifact']['path'],dict(completed['artifact']['authority'],epoch=999))

    def job(self,key):
        return self.service.admit_evaluation('agent-secret','p','r',request_key=key,target=self.target,requested_budget={'evaluation_attempts':1,'evaluation_ms':5000})

    def expire(self,identifier):
        with sqlite3.connect(self.service.path) as db:
            body=db.execute('SELECT record FROM asr_evaluation_jobs WHERE evaluation_id=?',(identifier,)).fetchone()[0]
            record=json.loads(body);record['lease_until']=0
            db.execute('UPDATE asr_evaluation_jobs SET record=? WHERE evaluation_id=?',(json.dumps(record),identifier))

    def test_prepared_claim_crash_aborts_without_launch_and_fences_old_owner(self):
        job=self.job('prepared')
        claim=self.service.claim_evaluation('supervisor-secret','p','r',job['evaluation_id'],'old-owner')
        self.expire(job['evaluation_id'])
        ended=run_evaluation(self.service,'supervisor-secret','p','r',job['evaluation_id'],'new-owner',Path(self.tmp.name)/'eval',reconcile=True)
        self.assertTrue(ended['settled'])
        self.assertEqual(ended['report_type'],'no_launch_grant_issued')
        self.assertNotIn('artifact',ended)
        with self.assertRaises(ValueError):self.service.begin_evaluation_launch('supervisor-secret','p','r',job['evaluation_id'],claim['epoch'],'old-owner')
        self.assertEqual(self.service.budgets.balance('p','evaluation_ms')['reserved'],0)

    def test_postgrant_missing_container_retains_reservation_and_never_auto_retries(self):
        job=self.job('unknown-create')
        claim=self.service.claim_evaluation('supervisor-secret','p','r',job['evaluation_id'],'old-owner')
        self.service.begin_evaluation_launch('supervisor-secret','p','r',job['evaluation_id'],claim['epoch'],'old-owner')
        self.expire(job['evaluation_id'])
        with self.assertRaises(Exception):run_evaluation(self.service,'supervisor-secret','p','r',job['evaluation_id'],'new-owner',Path(self.tmp.name)/'eval',reconcile=True)
        record=self.service.get_evaluation('supervisor-secret','p','r',job['evaluation_id'])
        self.assertFalse(record['settled']);self.assertEqual(record['state'],'uncertain')
        self.assertEqual(self.service.budgets.balance('p','evaluation_ms')['reserved'],5000)
        with self.assertRaises(ValueError):run_evaluation(self.service,'supervisor-secret','p','r',job['evaluation_id'],'third-owner',Path(self.tmp.name)/'eval')

    def test_actual_created_container_reconciliation_keeps_execution_epoch(self):
        from unittest.mock import patch
        from asr_evaluation.replay import Replay
        job=self.job('created-interrupt');native=Replay._docker
        def interrupt(manager,args):
            result=native(manager,args)
            if args[0]=='start':raise KeyboardInterrupt
            return result
        with patch.object(Replay,'_docker',interrupt):
            with self.assertRaises(KeyboardInterrupt):run_evaluation(self.service,'supervisor-secret','p','r',job['evaluation_id'],'old-owner',Path(self.tmp.name)/'eval')
        old=self.service.get_evaluation('supervisor-secret','p','r',job['evaluation_id']);self.expire(job['evaluation_id'])
        ended=run_evaluation(self.service,'supervisor-secret','p','r',job['evaluation_id'],'new-owner',Path(self.tmp.name)/'eval',reconcile=True)
        self.assertTrue(ended['settled']);self.assertEqual(ended['epoch'],2)
        self.assertEqual(ended['report']['authority']['epoch'],1)
        self.assertEqual(ended['identity']['container_id'],old['identity']['container_id'])
        self.assertEqual(self.service.budgets.balance('p','evaluation_ms')['reserved'],0)
