"""Public-only engineering fixtures; no fresh hidden panel is opened."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from asr_evaluation.ood_worker import sha


@unittest.skipUnless(Path('artifacts/p4-simulated-client-001/raw/train/0000.json').exists(),'requires public calibration rows')
class IsolatedConfirmationTests(unittest.TestCase):
    def materials(self):
        root=Path('artifacts/p4-simulated-client-001')
        rows=[json.loads((root/'raw/train'/f'{i:04d}.json').read_text()) for i in range(2)]
        case=json.loads((root/'public/case.json').read_text())
        model=json.loads((root/'public/baseline.json').read_text())
        protocol=dict(schema='asr-isolated-confirmation/1',counts={'private_id':1,'private_ood':1},
            minimum_valid_fraction=0.95,case_sha256=sha(case),primary_model='candidate',baseline_model='baseline',
            models={'candidate':sha(model),'baseline':sha(model)},
            acceptance=dict(relative_ood_rmse_reduction=.2,id_rmse_max_ratio=1.1,id_rmse_absolute_allowance_pu=1e-5),
            coordinate_policy='public-fixture-only',history_sha256=sha([]))
        panels={'private_id':[rows[0]['x']],'private_ood':[rows[1]['x']]}
        protocol['panels_sha256']=sha(panels)
        return dict(protocol=protocol,case=case,models={'candidate':model,'baseline':model},panels=panels,history=[]),rows

    def execute(self,materials,rows):
        from asr_evaluation.isolated_confirmation import execute
        events=[]
        with patch('asr_evaluation.isolated_confirmation.solve_sample',side_effect=rows):
            result=execute(dict(operation='isolated_final',protocol_sha256=sha(materials['protocol'])),materials,events.append)
        return result,events

    def test_frozen_public_fixture_has_separate_summary_and_raw_events(self):
        data,rows=self.materials();result,events=self.execute(data,rows)
        self.assertEqual(result['assessment'],'objective_not_met_on_frozen_test')
        self.assertEqual(len(events),2)
        self.assertEqual(result['label_validity']['private_id']['equation_valid'],1)
        self.assertNotIn('x',result);self.assertNotIn('sample_voltage_mse',str(result))
        self.assertEqual(result['independence'],'internal_permission_data_execution_isolation')

    def test_failed_label_preserved_and_no_success_claim(self):
        data,rows=self.materials();rows[1]=dict(status='label_failure',x=rows[1]['x'],y=None,error='solver failed')
        result,events=self.execute(data,rows)
        self.assertEqual(result['assessment'],'inconclusive_label_coverage')
        self.assertEqual(events[1]['row']['status'],'label_failure')
        self.assertEqual(result['label_validity']['private_ood']['failed'],1)

    def test_model_panel_history_and_integrity_tampering_fail(self):
        from asr_evaluation.isolated_confirmation import execute
        original,rows=self.materials()
        for mutation in ('model','panel','history','protocol'):
            data=copy.deepcopy(original);request=dict(operation='isolated_final',protocol_sha256=sha(data['protocol']))
            if mutation=='model':data['models']['candidate']['weights'][0][0]+=1
            if mutation=='panel':data['panels']['private_id'][0][0]+=.001
            if mutation=='history':data['history'].append('a'*64)
            if mutation=='protocol':data['protocol']['minimum_valid_fraction']=0
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):execute(request,data,lambda e:None)
        rows[0]['y'][0]+=.01
        with self.assertRaises(ValueError):self.execute(original,rows)

    def test_overlap_and_duplicate_coordinates_rejected_before_solving(self):
        from asr_evaluation.isolated_confirmation import coordinate_keys
        data,rows=self.materials();data['history']=list(coordinate_keys(rows[0]['x']))
        data['protocol']['history_sha256']=sha(data['history'])
        with self.assertRaisesRegex(ValueError,'overlap'):self.execute(data,rows)
        data,rows=self.materials();data['panels']['private_ood']=data['panels']['private_id']
        data['protocol']['panels_sha256']=sha(data['panels'])
        with self.assertRaisesRegex(ValueError,'overlap'):self.execute(data,rows)

class IsolatedAdmissionTests(unittest.TestCase):
    def test_development_and_researcher_cannot_admit_fresh_protocol(self):
        import test_ood_final as old
        f=old.FinalAdmissionTests('test_researcher_or_development_contract_cannot_release_test')
        f.setUp();self.addCleanup(f.doCleanups)
        with self.assertRaisesRegex(ValueError,'forbidden'):
            f.service.submit_ood_final('agent-secret','p','r',**f.arguments)
        with self.assertRaisesRegex(ValueError,'final_not_authorized'):
            f.service.submit_ood_final('human-secret','p','r',**f.arguments)

    def test_fresh_configuration_is_explicitly_bound_to_reference(self):
        from asr_service.ood_final import evaluation_reference
        config=dict(client_root='/fixture',preparation_report_sha256='a'*64,image_id='sha256:'+'b'*64,
            metric_source_sha256='c'*64,worker_source_sha256='d'*64,
            isolated_panel=dict(path='/private/frozen-panel.json',sha256='e'*64))
        ref=evaluation_reference(config)
        self.assertEqual(ref['profile'],'ood-isolated-confirmation/1')
        self.assertEqual(ref['panel_sha256'],'e'*64)
        config['isolated_panel']['path']='relative'
        with self.assertRaises(ValueError):evaluation_reference(config)

import os

@unittest.skipUnless(os.environ.get('ASR_ISOLATED_IMAGE'),'requires isolated evaluator image')
class IsolatedContainerTests(unittest.TestCase):
    def test_actual_container_admission_evidence_and_budget(self):
        import hashlib
        import shutil
        import test_study_execution as fixtures
        from asr_service.ood_final import evaluation_reference
        from asr_evaluation.ood_backend import IsolatedConfirmationBackend
        from asr_supervisor.store import ExecutionStore
        from asr_supervisor.supervisor import Supervisor
        with patch.dict(os.environ,ASR_SCIENTIFIC_IMAGE=os.environ['ASR_ISOLATED_IMAGE']):
            f=fixtures.StudyExecutionTests('test_real_batch_and_unchanged_training_through_owning_ledger')
            f.setUp();self.addCleanup(f.doCleanups)
        first,one,_=f.execute('baseline',dict(operation='fit',augmentation_trials=[]))
        second,two,_=f.execute('candidate',dict(operation='fit',augmentation_trials=[]))
        self.assertEqual(one['state'],'succeeded');self.assertEqual(two['state'],'succeeded')
        data,_=IsolatedConfirmationTests().materials();p=data['protocol']
        p['primary_model']=second['trial_id'];p['baseline_model']=first['trial_id']
        from asr_service.study import completed_material
        with f.service._connect() as db:
            models={}
            for trial in (first,second):
                material,_=completed_material(db,'p','r',trial['trial_id'])
                models[trial['trial_id']]=material['events'][-1]['result']['model']
        p['models']={k:sha(v) for k,v in models.items()}
        panel=Path(f.tmp.name)/'panel.json'
        panel.write_text(json.dumps({k:data[k] for k in ('protocol','panels','history')}))
        config=dict(client_root='/unused-new-panel',preparation_report_sha256='a'*64,image_id=f.image,
            metric_source_sha256=hashlib.sha256(Path('asr_evaluation/ood_metrics.py').read_bytes()).hexdigest(),
            worker_source_sha256=hashlib.sha256(Path('asr_evaluation/isolated_confirmation.py').read_bytes()).hexdigest(),
            isolated_panel=dict(path=str(panel),sha256=hashlib.sha256(panel.read_bytes()).hexdigest()))
        doc=copy.deepcopy(f.contract);doc['provenance'].update(capability_profile='ood-study-confirmation/1',final=config)
        doc['evaluation_ref']=f.service.references.register('p','evaluation',evaluation_reference(config))
        f.service.publish_contract('human-secret','p','c',doc,expected_revision=1,idempotency_key='confirm')
        f.service.command('human-secret','p','r','apply_contract',expected_revision=1,idempotency_key='apply',payload=dict(contract_id='c',revision=2))
        arguments=dict(request_key='confirmation',protocol=dict(primary_model=second['trial_id'],model_trials=[first['trial_id'],second['trial_id']],proposal_sha256='b'*64),hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))
        admitted=f.service.submit_ood_final('human-secret','p','r',**arguments)
        self.assertEqual(admitted['requested_budget']['sample_proposals'],2)
        self.assertEqual(admitted,f.service.submit_ood_final('human-secret','p','r',**arguments))
        backend=IsolatedConfirmationBackend(f.image,output_bytes=doc['execution_policy']['output_bytes'])
        import test_ood_final_execution as final_fixture
        self.addCleanup(lambda:final_fixture.FinalExecutionTests._remove_final(backend))
        supervisor=Supervisor(ExecutionStore(f.service.path),Path(f.tmp.name)/'isolated-evidence',backend=backend)
        outcome=supervisor.execute(admitted['execution_attempt_id'],'isolated-evaluator')
        path=Path(outcome['report']['evidence_path'])
        if os.environ.get('ASR_ISOLATED_EVIDENCE'):
            destination=Path(os.environ['ASR_ISOLATED_EVIDENCE']);destination.mkdir(parents=True,exist_ok=False)
            shutil.copytree(path,destination/'evidence')
            (destination/'receipt.json').write_text(json.dumps(dict(admission=admitted,execution=outcome),indent=2))
        self.assertEqual(outcome['state'],'succeeded',(path/'candidate-stream.log').read_text()[-1500:])
        result=json.loads((path/'study-result.json').read_text())
        self.assertTrue(result['engineering_fixture']);self.assertEqual(result['assessment'],'objective_not_met_on_frozen_test')
        from asr_service.note_artifacts import resolve
        with f.service._connect() as db:
            with self.assertRaisesRegex(ValueError,'note_artifact_unavailable'):
                resolve(db,f.service,'p','r',[dict(kind='trial',trial_id=admitted['trial_id'],path='study-events.json')])
        with self.assertRaisesRegex(ValueError,'isolated_evaluation_runtime_closed'):
            f.service.claim_runtime('human-secret','p','r','researcher',idempotency_key='no-reopen',runtime_identity={})
        self.assertEqual(f.service.budgets.balance('p','sample_proposals')['spent'],2)
        self.assertEqual(f.service.budgets.balance('p','sample_proposals')['reserved'],0)
        inspected=json.loads((path/'container-inspection.json').read_text())
        self.assertEqual(len(inspected['Mounts']),1);self.assertFalse(inspected['Mounts'][0]['RW'])
        self.assertEqual(inspected['HostConfig']['NetworkMode'],'none')
        with self.assertRaisesRegex(ValueError,'final_protocol_frozen'):
            f.execute('no-after-final',dict(operation='fit',augmentation_trials=[]))

class IsolatedDeliveryTests(unittest.TestCase):
    @unittest.skipUnless(Path('artifacts/p5-isolated-confirmation-public-002/receipt.json').exists(),'requires public isolated execution evidence')
    def test_verified_delivery_only_exports_aggregate_result(self):
        import tempfile
        from integrations.runtimes.ood_finalize import export_final_result
        root=Path('artifacts/p5-isolated-confirmation-public-002')
        report=json.loads((root/'receipt.json').read_text())['execution']['report']
        report['evidence_path']=str(root/'evidence')
        with tempfile.TemporaryDirectory() as work:
            export_final_result(report,work)
            files=list(Path(work).iterdir())
            self.assertEqual([p.name for p in files],['INTERNAL-ISOLATED-EVALUATION.json'])
            output=json.loads(files[0].read_text())
            self.assertTrue(output['engineering_fixture'])
            self.assertNotIn('panels',output);self.assertNotIn('history',output)
