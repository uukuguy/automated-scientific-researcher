"""Control lifecycle tests. Mock artifact verifier proves orchestration only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_control_service as fixtures
import test_validations as validation_fixtures
from asr_service.control import ControlService
from asr_service.contracts import encoded


class EvaluationJobTests(unittest.TestCase):
    def setUp(self):
        fixtures.ControlTests.setUp(self)
        credentials=dict(self.service.credentials)
        credentials.update({'supervisor-secret':dict(subject='supervisor',role='supervisor',projects=['p']), 'evaluator-secret':dict(subject='evaluator',role='evaluator',projects=['p'])})
        self.service=ControlService(self.service.path,credentials=credentials)
        self.contract['budget'].update(evaluation_attempts=2,evaluation_ms=10000)
        fixtures.ControlTests.start(self)
        self.trial=fixtures.ControlTests.submit(self)
        report,_=validation_fixtures.ValidationTests.complete(self)
        self.target=validation_fixtures.ValidationTests.document(self,report)['target']

    def admit(self,key='evaluate'):
        return self.service.admit_evaluation('agent-secret','p','r',request_key=key,target=self.target,requested_budget={'evaluation_attempts':1,'evaluation_ms':5000})

    def claim(self,job,owner='executor'):
        return self.service.claim_evaluation('supervisor-secret','p','r',job['evaluation_id'],owner)

    def expire(self,identifier):
        with self.service._connect() as db:
            row=db.execute('SELECT record FROM asr_evaluation_jobs WHERE evaluation_id=?',(identifier,)).fetchone()
            record=json.loads(row[0]);record['lease_until']=0
            db.execute('UPDATE asr_evaluation_jobs SET record=? WHERE evaluation_id=?',(encoded(record),identifier))

    def artifact(self,claim):
        authority={key:claim[key] for key in ('project_id','research_run_id','evaluation_id','evaluation_attempt_id')};authority['epoch']=claim['execution_epoch']
        manifest=dict(authority=authority,source=dict(identity={key:self.trial[key] for key in ('trial_id','execution_attempt_id','research_run_id')},manifest_sha256=self.target['manifest_hash']),execution_status='failed',execution_exited=True,elapsed_seconds=.02,result=None,evaluation_ref=self.target['evaluation_ref'])
        if claim.get('launch_state')=='prepared' and claim['state']!='reconciling':self.service.begin_evaluation_launch('supervisor-secret','p','r',claim['evaluation_id'],claim['epoch'],claim['owner'])
        self.service.attach_evaluation('supervisor-secret','p','r',claim['evaluation_id'],claim['epoch'],claim['owner'],dict(claim['launch_intent'],container_id='fixture-container'))
        root=Path(self.tmp.name)/claim['evaluation_id'];root.mkdir()
        (root/'manifest.json').write_text(json.dumps(manifest))
        digest=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()
        return root,digest,dict(manifest=manifest,isolation_facts={'container_id':'fixture-container','labels':claim['launch_intent']['labels'],'attestation_only':True})

    def test_admission_reserves_atomically_replay_and_closed_gate(self):
        job=self.admit()
        self.assertEqual(self.admit(),job)
        self.assertEqual(self.service.budgets.balance('p','evaluation_attempts')['reserved'],1)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['evaluations'][0]['evaluation_id'],job['evaluation_id'])
        self.service.command('human-secret','p','r','pause',expected_revision=1,idempotency_key='pause')
        self.assertEqual(self.admit(),job)
        with self.assertRaisesRegex(ValueError,'admission_closed'):self.admit('new')
        self.assertEqual(len(self.service.evaluations('agent-secret','p','r')),1)

    def test_claim_fence_unknown_retains_cost_and_terminal_settles_same_execution_epoch(self):
        job=self.admit();claimed=self.claim(job)
        self.assertEqual(claimed['launch_intent']['labels']['asr.evaluation_attempt'],claimed['evaluation_attempt_id'])
        self.service.begin_evaluation_launch('supervisor-secret','p','r',claimed['evaluation_id'],claimed['epoch'],'executor')
        self.service.mark_evaluation_uncertain('supervisor-secret','p','r',job['evaluation_id'],claimed['epoch'],'executor','daemon unavailable')
        self.assertFalse(self.service.get_run('agent-secret','p','r')['admission_open'])
        self.assertEqual(self.service.budgets.balance('p','evaluation_attempts')['reserved'],1)
        with self.assertRaises(ValueError):self.claim(job,'duplicate')
        self.expire(job['evaluation_id'])
        reopened=ControlService(self.service.path,credentials=self.service.credentials);self.service=reopened
        recovered=self.service.reconcile_evaluation_claim('supervisor-secret','p','r',job['evaluation_id'],'recovery')
        self.assertEqual(recovered['epoch'],2);self.assertEqual(recovered['execution_epoch'],1)
        path,digest,verified=self.artifact(recovered)
        with patch('asr_service.evaluation_jobs.verify_artifact',return_value=verified):
            with self.assertRaisesRegex(ValueError,'stale_evaluation_epoch'):
                self.service.complete_evaluation('supervisor-secret','p','r',job['evaluation_id'],1,'executor',artifact_path=str(path),artifact_sha256=digest,usage_ms=21)
            done=self.service.complete_evaluation('supervisor-secret','p','r',job['evaluation_id'],2,'recovery',artifact_path=str(path),artifact_sha256=digest,usage_ms=21)
            self.assertEqual(done['state'],'failed');self.assertTrue(done['settled'])
            self.assertEqual(self.service.budgets.balance('p','evaluation_ms')['spent'],21)
            self.assertEqual(self.service.budgets.balance('p','evaluation_ms')['reserved'],0)

    def test_unknown_evaluation_prevents_false_stop_until_settled(self):
        job=self.admit();claimed=self.claim(job)
        path,digest,verified=self.artifact(claimed)
        receipt=self.service.command('human-secret','p','r','stop',expected_revision=1,idempotency_key='stop')
        self.assertEqual(receipt['status'],'pending')
        self.assertEqual(self.service.get_run('agent-secret','p','r')['state'],'stopping')
        self.assertTrue(self.service.evaluation_should_stop('supervisor-secret','p','r',job['evaluation_id'],1,'executor'))
        with patch('asr_service.evaluation_jobs.verify_artifact',return_value=verified):
            self.service.complete_evaluation('supervisor-secret','p','r',job['evaluation_id'],1,'executor',artifact_path=str(path),artifact_sha256=digest,usage_ms=21)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['state'],'stopped')

    def test_container_identity_is_machine_bound_not_just_authority_labels(self):
        claimed=self.claim(self.admit());path,digest,verified=self.artifact(claimed)
        verified['isolation_facts']['container_id']='replaced-container'
        with patch('asr_service.evaluation_jobs.verify_artifact',return_value=verified):
            with self.assertRaisesRegex(ValueError,'evaluation_artifact_conflict'):
                self.service.complete_evaluation('supervisor-secret','p','r',claimed['evaluation_id'],1,'executor',artifact_path=str(path),artifact_sha256=digest,usage_ms=20)
        self.assertEqual(self.service.budgets.balance('p','evaluation_attempts')['reserved'],1)

    def test_prelaunch_recovery_fences_old_owner_and_retains_consumed_setup(self):
        claimed=self.claim(self.admit())
        self.expire(claimed['evaluation_id'])
        recovered=self.service.reconcile_evaluation_claim('supervisor-secret','p','r',claimed['evaluation_id'],'recovery')
        with self.assertRaisesRegex(ValueError,'stale_evaluation_epoch'):
            self.service.begin_evaluation_launch('supervisor-secret','p','r',claimed['evaluation_id'],1,'executor')
        done=self.service.abort_evaluation_prelaunch('supervisor-secret','p','r',claimed['evaluation_id'],2,'recovery',reason='Source preflight could not complete',usage_ms=15)
        self.assertTrue(done['settled']);self.assertEqual(done['state'],'failed')
        self.assertGreaterEqual(self.service.budgets.balance('p','evaluation_ms')['spent'],15)
        self.assertEqual(self.service.budgets.balance('p','evaluation_attempts')['spent'],1)
        self.assertNotIn('artifact',done)
        self.assertFalse(self.service.get_run('agent-secret','p','r')['admission_open'])

    def test_launched_missing_container_is_uncertain_not_free_budget(self):
        claimed=self.claim(self.admit())
        self.service.begin_evaluation_launch('supervisor-secret','p','r',claimed['evaluation_id'],1,'executor')
        with self.assertRaisesRegex(ValueError,'evaluation_launch_already_authorized'):
            self.service.abort_evaluation_prelaunch('supervisor-secret','p','r',claimed['evaluation_id'],1,'executor',reason='No container visible',usage_ms=0)
        self.assertEqual(self.service.budgets.balance('p','evaluation_attempts')['reserved'],1)

    def test_validation_machine_links_the_settled_artifact_and_rejects_changed_bytes(self):
        claimed=self.claim(self.admit());path,_,verified=self.artifact(claimed)
        manifest=verified['manifest'];manifest.update(execution_status='succeeded',result=dict(equation_valid=False,operational_status='violated',input_preserved=True))
        (path/'manifest.json').write_text(json.dumps(manifest));digest=hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()
        with patch('asr_service.evaluation_jobs.verify_artifact',return_value=verified):
            self.service.complete_evaluation('supervisor-secret','p','r',claimed['evaluation_id'],1,'executor',artifact_path=str(path),artifact_sha256=digest,usage_ms=20)
            document=validation_fixtures.ValidationTests.document(self,{'manifest_hash':self.target['manifest_hash']})
            document['evaluation_artifact']=dict(evaluation_id=claimed['evaluation_id'],evaluation_attempt_id=claimed['evaluation_attempt_id'],artifact_sha256=digest)
            validation=self.service.publish_validation('evaluator-secret','p','r','linked',document,idempotency_key='linked')
            self.assertTrue(validation['evaluation_artifact_verified_by_service'])
            self.assertEqual(validation['evaluation_artifact']['artifact_sha256'],digest)
            (path/'manifest.json').write_text('{}')
            with self.assertRaises(ValueError):self.service.publish_validation('evaluator-secret','p','r','tampered',document,idempotency_key='tampered')

    def test_http_researcher_requests_but_only_supervisor_can_claim_or_abort(self):
        import threading
        import urllib.request
        import urllib.error
        from asr_service.http import make_server
        server=make_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        root='http://127.0.0.1:'+str(server.server_port)+'/v1/projects/p/runs/r/evaluations'
        def request(token,path='',body=None):
            data=None if body is None else json.dumps(body).encode()
            req=urllib.request.Request(root+path,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as error:return error.code,json.load(error)
        body=dict(request_key='http',target=self.target,requested_budget={'evaluation_attempts':1,'evaluation_ms':5000})
        status,job=request('agent-secret',body=body)
        self.assertEqual(status,200)
        self.assertEqual(request('agent-secret',body=body),(200,job))
        path='/'+job['evaluation_id']
        self.assertEqual(request('agent-secret',path+'/claim',dict(owner='http-worker'))[0],403)
        status,claim=request('supervisor-secret',path+'/claim',dict(owner='http-worker'))
        self.assertEqual(status,200)
        status,done=request('supervisor-secret',path+'/abort-prelaunch',dict(epoch=claim['epoch'],owner='http-worker',usage_ms=3,reason='No launch grant issued'))
        self.assertEqual(status,200)
        self.assertTrue(done['settled']);self.assertNotIn('artifact',done)
        self.assertEqual(request('agent-secret',path),(200,done))
        self.assertEqual(self.service.budgets.balance('p','evaluation_ms')['reserved'],0)

    def test_applied_contract_must_opt_in_even_when_old_ledger_limits_remain(self):
        changed=copy.deepcopy(self.contract)
        del changed['budget']['evaluation_attempts'];del changed['budget']['evaluation_ms']
        self.service.publish_contract('human-secret','p','c',changed,expected_revision=1,idempotency_key='no-evaluation')
        self.service.command('human-secret','p','r','apply_contract',expected_revision=1,idempotency_key='disable-evaluation',payload={'contract_id':'c','revision':2})
        with self.assertRaisesRegex(ValueError,'capability_unavailable'):self.admit()
        self.assertEqual(self.service.evaluations('agent-secret','p','r'),[])
        self.assertEqual(self.service.budgets.balance('p','evaluation_attempts')['reserved'],0)

    def test_artifact_wrong_authority_rejected_and_no_actor_boolean_settlement(self):
        claimed=self.claim(self.admit());path,digest,verified=self.artifact(claimed)
        verified['manifest']['authority']['epoch']=99
        with patch('asr_service.evaluation_jobs.verify_artifact',return_value=verified):
            with self.assertRaisesRegex(ValueError,'evaluation_artifact_conflict'):
                self.service.complete_evaluation('supervisor-secret','p','r',claimed['evaluation_id'],1,'executor',artifact_path=str(path),artifact_sha256=digest,usage_ms=20)
        self.assertEqual(self.service.budgets.balance('p','evaluation_attempts')['reserved'],1)
        with self.assertRaises(ValueError):self.service.claim_evaluation('agent-secret','p','r',claimed['evaluation_id'],'forged')

if __name__=='__main__':unittest.main()
