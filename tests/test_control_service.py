import copy
import json
from pathlib import Path
import tempfile
import unittest

from asr_service.control import ControlService, ControlError


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = ControlService(Path(self.tmp.name) / 'control.db', credentials={
            'human-secret': {'subject': 'alice', 'role': 'human', 'projects': ['p']},
            'agent-secret': {'subject': 'aar', 'role': 'researcher', 'projects': ['p']},
            'other-secret': {'subject': 'bob', 'role': 'human', 'projects': ['other']},
        })
        from powerflow_lab.reference import make_request
        request=make_request()
        documents={
            'problem': {'profile':'matpower-case118/1','case_sha256':request['case_sha256']},
            'reference': {'profile':'matpower-reference/1','image_id':request['image_id']},
            'evaluation': {'profile':'powerflow-independent/1','validator_sha256':request['source_hashes']['validation.py'],'tolerance_pu':1e-7},
            'candidate': {'profile':'matpower-reference/1','image_id':request['image_id'],'solver':'newton_raphson'},
        }
        self.refs={k:self.service.references.register('p',k,v) for k,v in documents.items()}
        self.refs['input_manifest']=self.service.references.register('p','input_manifest',{'profile':'matpower-case118-flat/1','problem_ref':self.refs['problem']})
        policy = json.loads(Path('contracts/examples/powerflow-policy.json').read_text()) if Path('contracts/examples/powerflow-policy.json').exists() else json.loads(next(Path('contracts/examples').glob('*.json')).read_text())
        self.contract = dict(schema_version='asr-contract/1', objective={'question': 'Diagnose power flow', 'success_criteria': 'independent equation checks', 'scope': 'case118'},
            variable_policy=policy, problem_ref=self.refs['problem'], reference_ref=self.refs['reference'], evaluation_ref=self.refs['evaluation'],
            budget={'attempts': 2, 'execution_ms': 10000, 'research_walltime_ms':3600000, 'turns':20, 'tool_executions':100},
            execution_policy={'researchers': 1, 'candidate_interface': 'asr-candidate/1', 'timeout_seconds': 5, 'output_bytes': 104857600, 'max_concurrency': 1, 'retry_limit': 0},
            runtime_policy={'provider':'codex','auth_mode':'subscription_oauth','billing_mode':'subscription','quota_state':'available'}, intervention_policy={'guidance_boundary': 'next_submission', 'pause': 'drain'}, provenance={'source': 'test'})

    def start(self):
        self.service.publish_contract('human-secret', 'p', 'c', self.contract, expected_revision=0, idempotency_key='pub')
        return self.service.create_run('human-secret', 'p', 'r', 'experiment-1', 'c', 1, idempotency_key='start')

    def submit(self, key='trial'):
        return self.service.submit_trial('agent-secret','p','r',request_key=key,variables={'iterations': 30}, references={k:v for k,v in self.refs.items() if k != 'reference'},requested_budget={'attempts':1,'execution_ms':5000})

    def test_authenticated_project_and_role_boundaries(self):
        self.start()
        for token in ('missing', 'other-secret'):
            with self.assertRaises(ControlError): self.service.get_run(token,'p','r')
        with self.assertRaises(ControlError):
            self.service.command('agent-secret','p','r','pause',expected_revision=1,idempotency_key='pause')

    def test_atomic_admission_pause_replay_and_restart(self):
        self.start()
        trial = self.submit()
        receipt = self.service.command('human-secret','p','r','pause',expected_revision=1,idempotency_key='pause')
        self.assertEqual(receipt['status'], 'applied')
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        self.assertEqual(self.submit(), trial)
        with self.assertRaises(ControlError): self.submit('new')
        self.assertEqual(self.service.pending_dispatch('human-secret','p'), [])
        self.service.command('human-secret','p','r','resume',expected_revision=2,idempotency_key='resume')
        self.assertEqual(len(self.service.pending_dispatch('human-secret','p')), 1)
        self.assertEqual(self.service.budgets.balance('p','attempts')['reserved'],1)
        self.assertEqual(self.service.command('human-secret','p','r','pause',expected_revision=1,idempotency_key='pause'), receipt)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['trials'][0]['trial_id'],trial['trial_id'])

    def test_complete_contract_and_capability_validation(self):
        for key in ('budget','evaluation_ref','execution_policy'):
            bad=copy.deepcopy(self.contract);del bad[key]
            with self.assertRaises(ValueError): self.service.publish_contract('human-secret','p','c',bad,expected_revision=0,idempotency_key=key)
        bad=copy.deepcopy(self.contract);bad['execution_policy']['researchers']=2
        with self.assertRaisesRegex(ValueError,'capability_unavailable'): self.service.publish_contract('human-secret','p','c',bad,expected_revision=0,idempotency_key='two')

    def test_variable_budget_and_reference_rejections_leave_no_partial_trial(self):
        self.start()
        with self.assertRaises(ValueError):
            self.service.submit_trial('agent-secret','p','r',request_key='bad',variables={'iterations':101},references={k:v for k,v in self.refs.items() if k!='reference'},requested_budget={'attempts':1,'execution_ms':5000})
        self.assertEqual(self.service.get_run('human-secret','p','r')['trials'],[])
        self.submit()
        self.submit('two')
        with self.assertRaises(ValueError): self.submit('three')
        self.assertEqual(len(self.service.get_run('human-secret','p','r')['trials']),2)

    def test_metadata_only_reference_cannot_authorize_execution(self):
        bad=copy.deepcopy(self.contract)
        bad['problem_ref']=self.service.references.register('p','problem',{'version':1})
        with self.assertRaisesRegex(ValueError,'unsupported_problem_profile'):
            self.service.publish_contract('human-secret','p','c',bad,expected_revision=0,idempotency_key='bad-ref')

    def test_unsupported_candidate_is_not_silently_run_as_reference(self):
        self.start()
        refs={k:v for k,v in self.refs.items() if k!='reference'}
        refs['candidate']=self.service.references.register('p','candidate',{'profile':'novel/1'})
        with self.assertRaisesRegex(ValueError,'capability_unavailable'):
            self.service.submit_trial('agent-secret','p','r',request_key='novel',variables={},references=refs,requested_budget={'attempts':1,'execution_ms':5000})

    def test_concurrent_last_budget_slot_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        self.start();self.submit()
        def attempt(key):
            try: return self.submit(key)['trial_id']
            except ValueError: return None
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(attempt,['a','b']))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(self.service.budgets.balance('p','attempts')['reserved'],2)
        self.assertEqual(len(self.service.get_run('human-secret','p','r')['trials']),2)

    def test_unknown_subscription_quota_is_allowed_and_paid_api_requires_authorization(self):
        self.contract['runtime_policy']['quota_state']='unknown'
        self.start();self.submit()
        paid=copy.deepcopy(self.contract)
        paid['runtime_policy'].update(auth_mode='api_key',billing_mode='paid_api')
        with self.assertRaisesRegex(ValueError,'paid_api_not_authorized'):
            self.service.publish_contract('human-secret','p','c',paid,expected_revision=1,idempotency_key='api')
        paid['runtime_policy']['paid_api_authorized']=True
        published=self.service.publish_contract('human-secret','p','c',paid,expected_revision=1,idempotency_key='api-authorized')
        self.assertEqual(published['revision'],2)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['contract']['document']['runtime_policy']['billing_mode'],'subscription')

    def test_runtime_reserves_walltime_exclusively_and_settles_only_after_exit(self):
        self.start()
        session=self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='session')
        with self.assertRaisesRegex(ValueError,'runtime_already_active'):
            self.service.claim_runtime('human-secret','p','r','other',idempotency_key='other')
        self.assertEqual(self.service.budgets.balance('p','research_walltime_ms')['reserved'],3600000)
        self.assertTrue(self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='session')['replayed'])
        with self.assertRaisesRegex(ValueError,'execution_not_reconciled'):
            self.service.release_runtime('human-secret','p','r',session['session_id'],session['epoch'],'worker',execution_exited=False,actual_walltime_ms=500)
        self.service.release_runtime('human-secret','p','r',session['session_id'],session['epoch'],'worker',execution_exited=True,actual_walltime_ms=500)
        self.assertEqual(self.service.budgets.balance('p','research_walltime_ms')['spent'],500)
        self.assertEqual(self.service.budgets.balance('p','research_walltime_ms')['reserved'],0)

    def test_subscription_quota_and_runtime_activity_admission(self):
        self.start()
        session=self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='session')
        identity=dict(session_id=session['session_id'],epoch=session['epoch'],owner='worker')
        permit=self.service.admit_activity('human-secret','p','r',kind='turn',idempotency_key='turn1',**identity)
        self.assertEqual(permit['kind'],'turn')
        self.assertEqual(self.service.admit_activity('human-secret','p','r',kind='turn',idempotency_key='turn1',**identity),permit)
        self.assertEqual(self.service.budgets.balance('p','turns')['spent'],1)
        self.service.command('human-secret','p','r','quota',expected_revision=1,idempotency_key='quota',payload={'state':'exhausted'})
        with self.assertRaisesRegex(ValueError,'admission_closed'):self.submit()
        with self.assertRaisesRegex(ValueError,'admission_closed'):
            self.service.admit_activity('human-secret','p','r',kind='turn',idempotency_key='turn2',**identity)
        self.assertEqual(self.service.admit_activity('human-secret','p','r',kind='turn',idempotency_key='turn1',**identity),permit)

    def test_unsupported_effective_defaults_cannot_be_ignored(self):
        bad=copy.deepcopy(self.contract)
        bad['variable_policy']['variables']['load_scale']={'type':'number','unit':'ratio','default':2,'mode':'fixed','scope':'project','modifiable_by':['human']}
        with self.assertRaisesRegex(ValueError,'capability_unavailable'):
            self.service.publish_contract('human-secret','p','c',bad,expected_revision=0,idempotency_key='bad')

    def test_stop_cancels_unstarted_work_and_settles_only_unstarted_cost(self):
        self.start();self.submit()
        receipt=self.service.command('human-secret','p','r','stop',expected_revision=1,idempotency_key='stop')
        self.assertEqual(receipt['status'],'applied')
        self.assertEqual(self.service.get_run('human-secret','p','r')['state'],'stopped')
        self.assertEqual(self.service.budgets.balance('p','attempts')['reserved'],0)
        self.assertEqual(self.service.budgets.balance('p','attempts')['spent'],0)

    def test_finish_waits_for_runtime_exit_and_replay_updates(self):
        self.start()
        session=self.service.claim_runtime('human-secret','p','r','worker',idempotency_key='runtime')
        receipt=self.service.command('human-secret','p','r','finish',expected_revision=1,idempotency_key='finish')
        self.assertEqual(receipt['status'],'pending')
        with self.assertRaisesRegex(ValueError,'control_transition_pending'):
            self.service.command('human-secret','p','r','resume',expected_revision=2,idempotency_key='resume')
        self.service.release_runtime('human-secret','p','r',session['session_id'],session['epoch'],'worker',execution_exited=True,actual_walltime_ms=12)
        self.assertEqual(self.service.get_run('human-secret','p','r')['state'],'completed')
        self.assertEqual(self.service.command('human-secret','p','r','finish',expected_revision=1,idempotency_key='finish')['status'],'applied')

    def test_apply_exhausted_quota_closes_queued_dispatch(self):
        self.start();self.submit()
        bad=copy.deepcopy(self.contract);bad['runtime_policy']['quota_state']='exhausted'
        self.service.publish_contract('human-secret','p','c',bad,expected_revision=1,idempotency_key='exhausted')
        self.service.command('human-secret','p','r','apply_contract',expected_revision=1,idempotency_key='apply-exhausted',payload={'contract_id':'c','revision':2})
        self.assertEqual(self.service.pending_dispatch('human-secret','p'),[])
        from asr_supervisor.store import ExecutionStore,LeaseError
        trial=self.service.get_run('human-secret','p','r')['trials'][0]
        with self.assertRaises(LeaseError):ExecutionStore(self.service.path).claim(trial['execution_attempt_id'],'worker')

    def test_guidance_receipt_and_contract_switch_freeze_trials(self):
        self.start(); trial=self.submit()
        receipt=self.service.command('human-secret','p','r','guidance',expected_revision=1,idempotency_key='g',payload={'text':'Try sensitivity analysis'})
        self.assertEqual(receipt['effective_scope'],'next_submission')
        self.assertEqual(self.service.get_run('agent-secret','p','r')['guidance'][0]['command_id'],receipt['command_id'])
        contract=copy.deepcopy(self.contract);contract['objective']['question']='New question'
        self.service.publish_contract('human-secret','p','c',contract,expected_revision=1,idempotency_key='pub2')
        self.service.command('human-secret','p','r','apply_contract',expected_revision=2,idempotency_key='apply',payload={'contract_id':'c','revision':2})
        self.assertEqual(trial['contract_revision'],1)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['contract']['revision'],2)


class HttpTests(unittest.TestCase):
    def test_http_auth_json_and_actual_control_roundtrip(self):
        import threading
        import urllib.request
        import urllib.error
        from asr_service.http import make_server
        with tempfile.TemporaryDirectory() as tmp:
            service=ControlService(Path(tmp)/'db',credentials={'secret':{'subject':'alice','role':'human','projects':['p']}})
            server=make_server(service, port=0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)+'/v1/projects/p/events'
                with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(url)
                self.assertEqual(error.exception.code,401)
                request=urllib.request.Request(url,headers={'Authorization':'Bearer secret'})
                with urllib.request.urlopen(request) as response: self.assertEqual(json.load(response),[])
                request=urllib.request.Request(url,data=b'{"bad":NaN}',headers={'Authorization':'Bearer secret','Content-Type':'application/json'},method='POST')
                with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,400)
            finally: server.shutdown();server.server_close();thread.join()

class FindingsTests(unittest.TestCase):
    setUp=ControlTests.setUp
    start=ControlTests.start
    submit=ControlTests.submit
    def test_candidate_findings_require_terminal_evidence_and_replay(self):
        self.start();trial=self.submit()
        kwargs=dict(finding_id='f',expected_revision=0,idempotency_key='finding',statement='No generalization claim',trial_ids=[trial['trial_id']],limitations='Reference calibration only')
        with self.assertRaisesRegex(ValueError,'evidence_not_published'):
            self.service.publish_finding('agent-secret','p','r',**kwargs)
        from asr_supervisor.store import ExecutionStore
        execution=ExecutionStore(self.service.path)
        claimed=execution.claim(trial['execution_attempt_id'],'worker')
        from powerflow_lab.runner import _inventory,digest
        evidence=Path(self.tmp.name)/'evidence';evidence.mkdir()
        (evidence/'log.txt').write_text('negative result')
        manifest={'trial_id':trial['trial_id'],'execution_attempt_id':trial['execution_attempt_id'],'status':'failed','artifacts':_inventory(evidence)}
        (evidence/'manifest.json').write_text(json.dumps(manifest))
        execution.report(trial['execution_attempt_id'],claimed['epoch'],'worker',{'execution_exited':True,'status':'failed','manifest_hash':digest(evidence/'manifest.json'),'evidence_path':str(evidence),'usage':{'attempts':1,'execution_ms':10}})
        finding=self.service.publish_finding('agent-secret','p','r',**kwargs)
        self.assertEqual(finding['status'],'candidate')
        self.assertEqual(self.service.publish_finding('agent-secret','p','r',**kwargs),finding)
        self.assertEqual(self.service.findings('agent-secret','p','r'),[finding])
        (evidence/'log.txt').write_text('tampered')
        kwargs.update(finding_id='f2',idempotency_key='finding2')
        with self.assertRaisesRegex(ValueError,'evidence_unavailable'):
            self.service.publish_finding('agent-secret','p','r',**kwargs)

if __name__ == '__main__': unittest.main()
