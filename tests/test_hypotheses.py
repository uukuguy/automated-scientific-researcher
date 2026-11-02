"""D016 hypothesis revisions and frozen trial associations; no model costs."""
import json
import threading
import urllib.error
import urllib.request
import unittest

import test_control_service as control_fixtures
from asr_service.control import ControlService


class HypothesisTests(unittest.TestCase):
    setUp=control_fixtures.ControlTests.setUp
    start=control_fixtures.ControlTests.start
    submit=control_fixtures.ControlTests.submit

    def document(self):
        return dict(statement='Newton reference reaches an equation root',prediction='Maximum mismatch below 1e-6 pu',scope='Fixed case118 flat initialization',refutation_criteria='Valid original-input trial exceeds threshold',study_type='confirmatory',change_reason='Initial bounded hypothesis',analysis_timing='prospective')

    def publish(self,expected_revision=0,key='hypothesis',document=None):
        return self.service.publish_hypothesis('agent-secret','p','h',self.document() if document is None else document,expected_revision=expected_revision,idempotency_key=key)

    def reference(self,revision=1):return dict(project_id='p',hypothesis_id='h',revision=revision)

    def trial(self,key='linked',reference=None):
        return self.service.submit_trial('agent-secret','p','r',request_key=key,variables={'iterations':20},references={k:v for k,v in self.refs.items() if k!='reference'},requested_budget={'attempts':1,'execution_ms':5000},hypothesis_ref=self.reference() if reference is None else reference)

    def test_immutable_revisions_replay_conflicts_and_strict_document(self):
        first=self.publish()
        self.assertEqual(self.publish(),first)
        changed=self.document();changed['prediction']='Maximum mismatch below 1e-7 pu';changed['change_reason']='More precise prediction'
        second=self.publish(1,'second',changed)
        self.assertEqual(first['revision'],1);self.assertEqual(second['parent_revision'],1)
        self.assertEqual(self.service.hypotheses('human-secret','p','h'),[first,second])
        with self.assertRaisesRegex(ValueError,'revision_conflict'):self.publish(0,'stale')
        with self.assertRaisesRegex(ValueError,'idempotency_conflict'):self.publish(0,'hypothesis',changed)
        invalid=self.document();invalid['validation_status']='verified'
        with self.assertRaisesRegex(ValueError,'invalid_hypothesis'):self.publish(2,'self-validated',invalid)
        for token in ('missing','other-secret'):
            with self.assertRaises(ValueError):self.service.hypotheses(token,'p')
        self.assertEqual(len(self.service.hypotheses('agent-secret','p')),2)

    def test_concurrent_revision_publication_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        def attempt(key):
            try:return self.publish(key=key)
            except ValueError as error:return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,['a','b']))
        self.assertEqual(sum(isinstance(result,dict) for result in results),1)
        self.assertIn('revision_conflict',results)
        self.assertEqual(len(self.service.hypotheses('human-secret','p')),1)
        self.assertEqual(sum(event['type']=='hypothesis_published' for event in self.service.events('human-secret','p')),1)

    def test_frozen_trial_binding_survives_revision_and_reopened_service(self):
        self.start();first=self.publish();trial=self.trial()
        self.assertEqual(trial['hypothesis_ref']['sha256'],first['sha256'])
        changed=self.document();changed.update(prediction='A different prediction',change_reason='Observed new evidence')
        self.publish(1,'revised',changed)
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        self.assertEqual(self.trial(),trial)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['trials'][0]['hypothesis_ref']['revision'],1)
        second=self.trial('new',self.reference(2))
        self.assertEqual(second['hypothesis_ref']['revision'],2)
        self.assertEqual(len(self.service.hypotheses('agent-secret','p','h')),2)

    def test_cross_project_and_invalid_revision_leave_no_partial_admission(self):
        self.start();self.publish()
        self.service.publish_hypothesis('other-secret','other','h',self.document(),expected_revision=0,idempotency_key='other')
        bad=[dict(project_id='other',hypothesis_id='h',revision=1),self.reference(0),self.reference(True),self.reference(2**80),self.reference(99),dict(project_id='p',hypothesis_id='missing',revision=1)]
        for index,reference in enumerate(bad):
            with self.assertRaises(ValueError):self.trial('bad'+str(index),reference)
        self.assertEqual(self.service.get_run('human-secret','p','r')['trials'],[])
        self.assertEqual(self.service.budgets.balance('p','attempts')['reserved'],0)

    def test_legacy_request_payload_and_receipt_remain_replayable(self):
        from asr_service.contracts import encoded
        self.start();receipt=self.submit()
        with self.service._connect() as db:
            body,payload=db.execute('SELECT record,payload FROM asr_requests WHERE project=? AND scope=? AND request_key=?',('p','trial:r','trial')).fetchone()
            record=json.loads(body)
            record.pop('hypothesis_ref',None);record.pop('hypothesis_linkage',None)
            legacy=encoded(record)
            db.execute('UPDATE asr_requests SET record=? WHERE project=? AND scope=? AND request_key=?',(legacy,'p','trial:r','trial'))
            db.execute('UPDATE asr_dispatch SET record=? WHERE attempt=?',(legacy,receipt['execution_attempt_id']))
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        self.assertEqual(self.submit(),record)
        view=self.service.get_run('agent-secret','p','r')['trials'][0]
        self.assertEqual(view['hypothesis_linkage'],'legacy_unlinked')
        self.assertIsNone(view['hypothesis_ref'])
        self.publish()
        with self.assertRaisesRegex(ValueError,'idempotency_conflict'):
            self.service.submit_trial('agent-secret','p','r',request_key='trial',variables={'iterations':30},references={k:v for k,v in self.refs.items() if k!='reference'},requested_budget={'attempts':1,'execution_ms':5000},hypothesis_ref=self.reference())
        with self.service._connect() as db:
            self.assertEqual(db.execute('SELECT payload FROM asr_requests WHERE project=? AND scope=? AND request_key=?',('p','trial:r','trial')).fetchone()[0],payload)

    def completed(self,trial):
        from pathlib import Path
        from asr_supervisor.store import ExecutionStore
        from powerflow_lab.runner import digest,_inventory
        store=ExecutionStore(self.service.path);store.claim(trial['execution_attempt_id'],'numerical')
        evidence=Path(self.tmp.name)/trial['trial_id'];evidence.mkdir()
        (evidence/'output.txt').write_text('Observed numerical failure; validity not assessed')
        manifest=dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],status='failed',artifacts=_inventory(evidence))
        (evidence/'manifest.json').write_text(json.dumps(manifest))
        store.report(trial['execution_attempt_id'],1,'numerical',dict(execution_exited=True,status='failed',manifest_hash=digest(evidence/'manifest.json'),evidence_path=str(evidence),usage={'attempts':1,'execution_ms':10}))

    def test_candidate_finding_relations_remain_author_claims_and_preserve_opposition(self):
        self.start();self.publish();trial=self.trial();self.completed(trial)
        relation=dict(hypothesis_ref=self.reference(),trial_id=trial['trial_id'],assessment='opposes',scope='This fixed input only; experiment validity unassessed',analysis_timing='prospective')
        kwargs=dict(finding_id='f',expected_revision=0,idempotency_key='opposing',statement='Candidate interpretation requires validation',trial_ids=[trial['trial_id']],limitations='No scientific refutation established',hypothesis_evidence=[relation])
        first=self.service.publish_finding('agent-secret','p','r',**kwargs)
        self.assertEqual(first['status'],'candidate')
        self.assertEqual(first['hypothesis_evidence'][0]['assessment_kind'],'author_claim')
        self.assertEqual(first['hypothesis_evidence'][0]['assessment'],'opposes')
        relation['assessment']='uncertain'
        kwargs.update(expected_revision=1,idempotency_key='uncertain')
        second=self.service.publish_finding('agent-secret','p','r',**kwargs)
        self.assertEqual(second['hypothesis_evidence'][0]['assessment'],'uncertain')
        self.assertEqual(self.service.findings('agent-secret','p','r')[0],first)
        invalid=dict(relation,validation_status='verified')
        kwargs.update(expected_revision=2,idempotency_key='self-validation',hypothesis_evidence=[invalid])
        with self.assertRaisesRegex(ValueError,'invalid_hypothesis_evidence'):
            self.service.publish_finding('agent-secret','p','r',**kwargs)

    def test_legacy_trial_requires_explicit_post_hoc_interpretation(self):
        self.start();trial=self.submit();self.completed(trial);self.publish()
        relation=dict(hypothesis_ref=self.reference(),trial_id=trial['trial_id'],assessment='uncertain',scope='Legacy observation',analysis_timing='prospective')
        kwargs=dict(finding_id='post-hoc',expected_revision=0,idempotency_key='post-hoc',statement='Observation precedes this prediction',trial_ids=[trial['trial_id']],limitations='Not a preregistered prediction',hypothesis_evidence=[relation])
        with self.assertRaisesRegex(ValueError,'post_hoc_label_required'):
            self.service.publish_finding('agent-secret','p','r',**kwargs)
        relation['analysis_timing']='post_hoc'
        finding=self.service.publish_finding('agent-secret','p','r',**kwargs)
        self.assertEqual(finding['hypothesis_evidence'][0]['analysis_timing'],'post_hoc')
        self.assertIsNone(self.service.get_run('agent-secret','p','r')['trials'][0]['hypothesis_ref'])

    def test_http_publish_list_and_linked_trial(self):
        from asr_service.http import make_server
        self.start()
        server=make_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path,body=None,token='agent-secret'):
            request=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/v1/projects/p/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            with urllib.request.urlopen(request) as response:return json.load(response)
        try:
            first=request('hypotheses',dict(hypothesis_id='h',document=self.document(),expected_revision=0,idempotency_key='http'))
            self.assertEqual(request('hypotheses'),[first]);self.assertEqual(request('hypotheses/h'),[first])
            trial=request('runs/r/trials',dict(request_key='http-trial',variables={},references={k:v for k,v in self.refs.items() if k!='reference'},requested_budget={'attempts':1,'execution_ms':5000},hypothesis_ref=self.reference()))
            self.assertEqual(trial['hypothesis_ref']['revision'],1)
            self.completed(trial)
            finding=request('runs/r/findings',dict(finding_id='http-finding',expected_revision=0,idempotency_key='http-finding',statement='Candidate uncertain assessment',trial_ids=[trial['trial_id']],limitations='Validity unassessed',hypothesis_evidence=[dict(hypothesis_ref=self.reference(),trial_id=trial['trial_id'],assessment='uncertain',scope='This trial',analysis_timing='prospective')]))
            self.assertEqual(finding['hypothesis_evidence'][0]['assessment_kind'],'author_claim')
            with self.assertRaises(urllib.error.HTTPError) as error:
                request('hypotheses',dict(hypothesis_id='h',document=self.document(),expected_revision=0,idempotency_key='stale'))
            self.assertEqual(error.exception.code,409)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
