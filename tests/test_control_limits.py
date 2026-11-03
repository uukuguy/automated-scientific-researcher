"""Resource exhaustion pauses durable research and retains the denied intent."""
import copy
import json
import unittest
from asr_service.budgets import BudgetError
from asr_service.control import ControlService
import test_control_service as fixtures


class ControlLimitTests(unittest.TestCase):
    setUp=fixtures.ControlTests.setUp
    start=fixtures.ControlTests.start
    submit=fixtures.ControlTests.submit
    runtime_identity=fixtures.ControlTests.runtime_identity

    def test_budget_exception_identifies_exact_dimension_and_balance(self):
        self.service.budgets.set_limit('p','turns',3)
        self.service.budgets.reserve('p','reserved','turns',2)
        with self.assertRaises(BudgetError) as caught:self.service.budgets.reserve('p','new','turns',2)
        self.assertEqual(caught.exception.details,dict(dimension='turns',limit=3,spent=0,reserved=2,available=1,requested=2))
        self.assertEqual(self.service.budgets.balance('p','turns')['reserved'],2)

    def test_denied_trial_is_durable_paused_and_recoverable_after_budget_revision(self):
        self.contract['budget'].update(attempts=1,execution_ms=5000)
        self.start();first=self.submit()
        with self.assertRaisesRegex(BudgetError,'budget_exhausted') as caught:self.submit('second')
        details=caught.exception.details
        self.assertEqual({k:details[k] for k in ('dimension','limit','spent','reserved','requested')},dict(dimension='attempts',limit=1,spent=0,reserved=1,requested=1))
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        run=self.service.get_run('agent-secret','p','r')
        self.assertEqual(run['state'],'paused');self.assertFalse(run['admission_open'])
        self.assertEqual(run['budget_blocks'][0]['request_key'],'second')
        self.assertEqual(run['budget_blocks'][0]['request']['requested_budget'],dict(attempts=1,execution_ms=5000))
        self.assertEqual(run['trials'][0]['trial_id'],first['trial_id'])
        expanded=copy.deepcopy(self.contract);expanded['budget'].update(attempts=2,execution_ms=10000)
        self.service.publish_contract('human-secret','p','c',expanded,expected_revision=1,idempotency_key='expand')
        self.service.command('human-secret','p','r','apply_contract',expected_revision=run['control_revision'],idempotency_key='apply',payload=dict(contract_id='c',revision=2))
        revision=self.service.get_run('human-secret','p','r')['control_revision']
        self.service.command('human-secret','p','r','resume',expected_revision=revision,idempotency_key='resume')
        second=self.submit('second')
        self.assertNotEqual(second['trial_id'],first['trial_id'])
        self.assertEqual(len(self.service.get_run('agent-secret','p','r')['budget_blocks']),1)

    def test_runtime_limit_receipt_pauses_without_losing_session_or_usage(self):
        self.start()
        session=self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='runtime',runtime_identity=self.runtime_identity(),requested_walltime_ms=5000)
        request=dict(session_id=session['session_id'],epoch=1,owner='worker',kind='tool_executions',limit=2,observed=2,reason='No further tool permit remains',idempotency_key='limit')
        with self.assertRaises(ValueError):self.service.observe_runtime_limit('agent-secret','p','r',**request)
        receipt=self.service.observe_runtime_limit('human-secret','p','r',**request)
        self.assertEqual(self.service.observe_runtime_limit('human-secret','p','r',**request),receipt)
        self.assertEqual(receipt['unit'],'count')
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        run=self.service.get_run('agent-secret','p','r')
        self.assertEqual(run['state'],'paused')
        self.assertEqual(run['runtime_sessions'][0]['limit_observations'],[receipt])
        self.assertEqual(run['runtime_sessions'][0]['state'],'active')
        self.assertEqual(self.service.budgets.balance('p','research_walltime_ms')['reserved'],5000)
        self.assertEqual(len([event for event in self.service.events('human-secret','p') if event['type']=='runtime_limit_observed']),1)

    def test_measured_prelaunch_timeout_charges_setup_and_preserves_limit_receipt(self):
        self.contract['budget']['research_walltime_ms']=10
        self.start()
        session=self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='runtime',runtime_identity=self.runtime_identity(),requested_walltime_ms=10)
        observation=self.service.observe_runtime_limit('human-secret','p','r',session_id=session['session_id'],epoch=1,owner='worker',kind='model_walltime',limit=10,observed=12,reason='Version/setup deadline exhausted before provider launch',idempotency_key='setup-limit')
        ended=self.service.abort_runtime_prelaunch('human-secret','p','r',session['session_id'],1,'worker',reason='setup_deadline_exhausted',actual_walltime_ms=12)
        self.assertEqual(ended['actual_walltime_ms'],12)
        self.assertEqual(ended['exit_receipt']['actual_walltime_ms'],12)
        self.assertEqual(ended['limit_observations'],[observation])
        self.assertEqual(self.service.budgets.balance('p','research_walltime_ms'),dict(limit=10,spent=12,reserved=0,available=-2))
        self.assertEqual(self.service.budgets.balance('p','turns')['spent'],0)
        self.assertEqual(self.service.abort_runtime_prelaunch('human-secret','p','r',session['session_id'],1,'worker',reason='setup_deadline_exhausted',actual_walltime_ms=12),ended)
        with self.assertRaisesRegex(ValueError,'idempotency_conflict'):
            self.service.abort_runtime_prelaunch('human-secret','p','r',session['session_id'],1,'worker',reason='setup_deadline_exhausted',actual_walltime_ms=13)
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        run=self.service.get_run('agent-secret','p','r')
        self.assertEqual(run['state'],'paused')
        self.assertFalse(run['admission_open'])
        self.assertTrue(any(event['type']=='budget_debt_observed' for event in run['limit_events']))

    def test_prelaunch_abort_rejects_invalid_measured_cost_before_settlement(self):
        self.start()
        session=self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='runtime',runtime_identity=self.runtime_identity(),requested_walltime_ms=10)
        for amount in (True,-1,1.5,float('inf')):
            with self.subTest(amount=amount),self.assertRaises(ValueError):
                self.service.abort_runtime_prelaunch('human-secret','p','r',session['session_id'],1,'worker',reason='fixture',actual_walltime_ms=amount)
        self.assertEqual(self.service.budgets.balance('p','research_walltime_ms')['reserved'],10)
        ended=self.service.abort_runtime_prelaunch('human-secret','p','r',session['session_id'],1,'worker',reason='Immediate operator cancellation')
        self.assertEqual(ended['actual_walltime_ms'],0)

    def test_protocol_safeguards_have_explicit_byte_or_count_receipts(self):
        self.start()
        session=self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='runtime',runtime_identity=self.runtime_identity(),requested_walltime_ms=5000)
        for kind,unit in [('protocol_message_bytes','bytes'),('protocol_buffer_bytes','bytes'),('protocol_pending_records','count'),('protocol_records','count')]:
            with self.subTest(kind=kind):
                receipt=self.service.observe_runtime_limit('human-secret','p','r',session_id=session['session_id'],epoch=1,owner='worker',kind=kind,limit=100,observed=101,reason='Bounded transport checkpoint',idempotency_key=kind)
                self.assertEqual(receipt['unit'],unit)
        self.assertEqual(len(self.service.get_run('human-secret','p','r')['runtime_sessions'][0]['limit_observations']),4)

    def test_exhausted_runtime_allocation_records_the_session_walltime_cause(self):
        from datetime import datetime,timedelta,timezone
        from asr_service.contracts import encoded
        self.start()
        session=self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='runtime',runtime_identity=self.runtime_identity(),requested_walltime_ms=1)
        with self.service._connect() as db:
            row=db.execute('SELECT record FROM asr_runtime_sessions WHERE session_id=?',(session['session_id'],)).fetchone()
            record=json.loads(row[0]);record['started_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
            db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(encoded(record),session['session_id']))
        with self.assertRaisesRegex(BudgetError,'budget_exhausted') as caught:
            self.service.admit_activity('human-secret','p','r',kind='turn',idempotency_key='too-late',session_id=session['session_id'],epoch=1,owner='worker')
        self.assertEqual(caught.exception.details['scope'],'runtime_session')
        self.assertEqual(caught.exception.details['limit'],1)
        self.assertGreaterEqual(caught.exception.details['spent'],1000)
        run=self.service.get_run('agent-secret','p','r')
        self.assertEqual(run['state'],'paused')
        self.assertEqual(run['budget_blocks'][0]['request_key'],'too-late')
        self.assertEqual(self.service.budgets.balance('p','research_walltime_ms')['reserved'],1)

    def test_http_budget_response_exposes_structured_recoverable_cause(self):
        import threading,urllib.request,urllib.error
        from asr_service.http import make_server
        self.contract['budget'].update(attempts=1,execution_ms=5000)
        self.start();self.submit()
        server=make_server(self.service,port=0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        body=dict(request_key='http-denied',variables={'iterations':30},references={k:v for k,v in self.refs.items() if k!='reference'},requested_budget=dict(attempts=1,execution_ms=5000))
        request=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/v1/projects/p/runs/r/trials',data=json.dumps(body).encode(),headers={'Authorization':'Bearer agent-secret','Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(request)
        response=json.load(caught.exception)
        self.assertEqual(caught.exception.code,409)
        self.assertEqual(response['details']['dimension'],'attempts')
        self.assertTrue(response['details']['recoverable'])
        self.assertNotIn('agent-secret',json.dumps(response))


if __name__=='__main__':unittest.main()
