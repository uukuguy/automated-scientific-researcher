"""Evaluator-only immutable reports, independently scoped from author findings."""
import copy
import hashlib
import json
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request

import test_control_service as control_fixtures
from asr_service.control import ControlService


class ValidationTests(unittest.TestCase):
    def setUp(self):
        control_fixtures.ControlTests.setUp(self)
        credentials=dict(self.service.credentials)
        credentials['evaluator-secret']={'subject':'independent-checker','role':'evaluator','projects':['p','other']}
        credentials['supervisor-secret']={'subject':'executor','role':'supervisor','projects':['p']}
        self.service=ControlService(self.service.path,credentials=credentials)
        control_fixtures.ControlTests.start(self)
        self.trial=control_fixtures.ControlTests.submit(self)

    def complete(self,trial=None):
        from asr_supervisor.store import ExecutionStore
        from powerflow_lab.runner import digest,_inventory
        trial=self.trial if trial is None else trial
        store=ExecutionStore(self.service.path)
        claim=store.claim(trial['execution_attempt_id'],'supervisor')
        path=Path(self.tmp.name)/trial['trial_id'];path.mkdir()
        (path/'output.json').write_text('{"observation":"negative calibration"}')
        manifest=dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],status='failed',artifacts=_inventory(path))
        (path/'manifest.json').write_text(json.dumps(manifest))
        report=dict(execution_exited=True,status='failed',manifest_hash=digest(path/'manifest.json'),evidence_path=str(path),usage={'attempts':1,'execution_ms':5})
        store.report(trial['execution_attempt_id'],claim['epoch'],'supervisor',report)
        return report,path

    def document(self,report):
        return dict(target=dict(trial_id=self.trial['trial_id'],execution_attempt_id=self.trial['execution_attempt_id'],manifest_hash=report['manifest_hash'],evaluation_ref=self.refs['evaluation']),assessments=dict(experiment_validity='valid',equation_validity='invalid',operating_checks='unassessed',replication='unassessed',generalization='unassessed',hypothesis_assessment='unassessed'),provenance=dict(method='Independent frozen-material check',independence=dict(execution='not_observed',frozen_materials='observed',mathematics='unknown'),limits=['Evaluator attestation only; no OS isolation or replication claim']),summary='Negative numerical observation retained separately from experimental validity')

    def publish(self,document,identifier='v1',key='validation',supersedes=None,token='evaluator-secret'):
        return self.service.publish_validation(token,'p','r',identifier,document,idempotency_key=key,supersedes=supersedes)

    def test_evaluator_only_publication_and_service_hash_identity(self):
        report,_=self.complete();document=self.document(report)
        for token in ('agent-secret','human-secret','supervisor-secret','missing'):
            with self.assertRaises(ValueError):self.publish(document,token=token)
        first=self.publish(document)
        from asr_service.contracts import encoded
        self.assertEqual(first['sha256'],hashlib.sha256(encoded(document).encode()).hexdigest())
        self.assertEqual(first['author'],'independent-checker')
        self.assertEqual(first['author_role'],'evaluator')
        self.assertFalse(first['isolation_verified_by_service'])
        self.assertEqual(first['independence_basis'],'evaluator_attestation')
        self.assertEqual(self.service.validations('agent-secret','p','r'),[first])
        forged=copy.deepcopy(document);forged['author_role']='evaluator'
        with self.assertRaisesRegex(ValueError,'invalid_validation'):self.publish(forged,'forged','forged')

    def test_replay_reopen_conflicts_and_negative_supersession_retained(self):
        report,_=self.complete();document=self.document(report)
        first=self.publish(document)
        self.service=ControlService(self.service.path,credentials=self.service.credentials)
        self.assertEqual(self.publish(document),first)
        changed=copy.deepcopy(document);changed['assessments']['equation_validity']='valid'
        with self.assertRaisesRegex(ValueError,'idempotency_conflict'):self.publish(changed)
        with self.assertRaisesRegex(ValueError,'validation_id_conflict'):self.publish(changed,key='new-key')
        second=self.publish(changed,'v2','revised','v1')
        self.assertEqual(second['supersedes'],'v1')
        self.assertEqual(self.service.validations('human-secret','p','r'),[first,second])
        self.assertEqual(first['document']['assessments']['equation_validity'],'invalid')
        run=self.service.get_run('human-secret','p','r')
        self.assertEqual(run['trials'][0]['dispatch_state'],'failed')
        self.assertEqual(self.service.findings('human-secret','p','r'),[])

    def test_target_hash_evaluation_and_raw_bytes_are_verified(self):
        report,path=self.complete();document=self.document(report)
        for key,value in [('manifest_hash','0'*64),('evaluation_ref','0'*64),('execution_attempt_id','another-attempt'),('trial_id','another-project-trial')]:
            invalid=copy.deepcopy(document);invalid['target'][key]=value
            with self.assertRaises(ValueError):self.publish(invalid,identifier=key,key=key)
        (path/'output.json').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'evidence_unavailable'):self.publish(document)
        self.assertEqual(self.service.validations('human-secret','p','r'),[])

    def test_inflight_and_cross_project_targets_are_not_publishable(self):
        document=self.document({'manifest_hash':'0'*64})
        with self.assertRaisesRegex(ValueError,'evidence_not_published'):self.publish(document)
        for kind,reference in self.refs.items():
            self.service.references.register('other',kind,self.service.references.get('p',kind,reference))
        self.service.publish_contract('other-secret','other','other-contract',self.contract,expected_revision=0,idempotency_key='other-contract')
        self.service.create_run('other-secret','other','r','other-experiment','other-contract',1,idempotency_key='other-run')
        with self.assertRaisesRegex(ValueError,'trial_not_found'):
            self.service.publish_validation('evaluator-secret','other','r','cross',document,idempotency_key='cross')
        self.assertEqual(self.service.validations('human-secret','p','r'),[])

    def test_supersedes_must_refer_to_the_same_completed_target(self):
        report,_=self.complete();self.publish(self.document(report))
        other=control_fixtures.ControlTests.submit(self,key='other')
        other_report,_=self.complete(other)
        document=self.document(other_report)
        document['target'].update(trial_id=other['trial_id'],execution_attempt_id=other['execution_attempt_id'])
        with self.assertRaisesRegex(ValueError,'supersedes_target_conflict'):
            self.publish(document,'other-validation','other-validation','v1')
        self.assertEqual(len(self.service.validations('human-secret','p','r')),1)
        with self.assertRaisesRegex(ValueError,'validation_not_found'):
            self.publish(document,'missing-prior','missing-prior','no-such-validation')

    def test_observed_independence_remains_attestation_not_service_proof(self):
        report,_=self.complete();document=self.document(report)
        document['provenance']['independence']={axis:'observed' for axis in ('execution','frozen_materials','mathematics')}
        validation=self.publish(document)
        self.assertFalse(validation['isolation_verified_by_service'])
        self.assertEqual(validation['independence_basis'],'evaluator_attestation')
        forged=copy.deepcopy(document);forged['provenance']['isolation_proven']=True
        with self.assertRaisesRegex(ValueError,'invalid_validation'):
            self.publish(forged,'forged-proof','forged-proof')

    def test_invalid_or_unassessed_experiment_cannot_support_or_refute_or_generalize(self):
        report,_=self.complete();document=self.document(report)
        for validity in ('invalid','unassessed'):
            for assessment in ('supports','opposes'):
                invalid=copy.deepcopy(document);invalid['assessments'].update(experiment_validity=validity,hypothesis_assessment=assessment)
                with self.assertRaises(ValueError):self.publish(invalid,identifier=validity+assessment,key=validity+assessment)
            invalid=copy.deepcopy(document);invalid['assessments'].update(experiment_validity=validity,generalization='supported')
            with self.assertRaises(ValueError):self.publish(invalid,identifier=validity+'generalization',key=validity+'generalization')
        invalid=copy.deepcopy(document);invalid['assessments']['experiment_validity']='executed'
        with self.assertRaisesRegex(ValueError,'invalid_validation'):self.publish(invalid,'enum','enum')

    def test_hypothesis_assessment_requires_bound_version_or_explicit_post_hoc(self):
        report,_=self.complete();document=self.document(report)
        self.service.publish_hypothesis('agent-secret','p','h',dict(statement='A later hypothesis',prediction='Equation residual below threshold',scope='case118',refutation_criteria='Valid experiment exceeds threshold',study_type='exploratory',change_reason='After observation',analysis_timing='post_hoc'),expected_revision=0,idempotency_key='h')
        document.update(hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1),analysis_timing='prospective')
        document['assessments']['hypothesis_assessment']='opposes'
        with self.assertRaisesRegex(ValueError,'post_hoc_label_required'):self.publish(document)
        document['analysis_timing']='post_hoc'
        validation=self.publish(document)
        self.assertEqual(validation['document']['analysis_timing'],'post_hoc')
        self.assertIsNone(self.service.get_run('human-secret','p','r')['trials'][0]['hypothesis_ref'])

    def test_http_roles_publish_list_and_immutable_conflict(self):
        from asr_service.http import make_server
        report,_=self.complete();document=self.document(report)
        server=make_server(self.service,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(token,body=None):
            request=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/v1/projects/p/runs/r/validations',data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            with urllib.request.urlopen(request) as response:return json.load(response)
        body=dict(validation_id='http-validation',document=document,idempotency_key='http')
        try:
            for role in ('human-secret','agent-secret','supervisor-secret'):
                with self.assertRaises(urllib.error.HTTPError) as error:request(role,body)
                self.assertEqual(error.exception.code,403)
            first=request('evaluator-secret',body)
            self.assertEqual(request('human-secret'),[first])
            body['document']['summary']='Different immutable content'
            with self.assertRaises(urllib.error.HTTPError) as error:request('evaluator-secret',body)
            self.assertEqual(error.exception.code,409)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
