"""Final-evaluator integration using PUBLIC training rows as artificial test data.

The real private test is never opened by this engineering test.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import unittest

import test_study_execution as fixtures
from asr_evaluation.ood_backend import OODFinalBackend
from asr_service.ood_final import evaluation_reference
from asr_supervisor.supervisor import Supervisor
from asr_supervisor.store import ExecutionStore


@unittest.skipUnless(os.environ.get('ASR_FINAL_IMAGE'),'requires final scientific image')
class FinalExecutionTests(unittest.TestCase):
    execute=fixtures.StudyExecutionTests.execute
    remove_owned_containers=fixtures.StudyExecutionTests.remove_owned_containers

    def setUp(self):
        from unittest.mock import patch
        with patch.dict(os.environ,ASR_SCIENTIFIC_IMAGE=os.environ['ASR_FINAL_IMAGE']):
            fixtures.StudyExecutionTests.setUp(self)

    def test_final_release_freezes_fitted_model_and_scores_in_separate_container(self):
        trial,fit,_=self.execute('baseline',dict(operation='fit',augmentation_trials=[]))
        self.assertEqual(fit['state'],'succeeded')
        client=Path(self.tmp.name)/'artificial-client';client.mkdir()
        original=Path('artifacts/p4-simulated-client-001')
        shutil.copytree(original/'public',client/'public')
        inventory={}
        for split,offset in (('private_id',0),('private_ood',64)):
            directory=client/'raw'/split;directory.mkdir(parents=True)
            for i in range(64):
                body=(original/'raw/train'/f'{offset+i:04d}.json').read_bytes()
                (directory/f'{i:04d}.json').write_bytes(body)
                inventory[f'{split}/{i:04d}.json']=hashlib.sha256(body).hexdigest()
        preparation=client/'preparation-report.json';preparation.write_text(json.dumps({'raw_inventory':inventory}))
        config=dict(client_root=str(client),preparation_report_sha256=hashlib.sha256(preparation.read_bytes()).hexdigest(),
            image_id=self.image,metric_source_sha256=hashlib.sha256(Path('asr_evaluation/ood_metrics.py').read_bytes()).hexdigest(),
            worker_source_sha256=hashlib.sha256(Path('asr_evaluation/ood_worker.py').read_bytes()).hexdigest())
        doc=copy.deepcopy(self.contract)
        doc['provenance'].update(capability_profile='ood-study-confirmation/1',final=config)
        doc['provenance']['study']['public_directory']=str(client/'public')
        doc['evaluation_ref']=self.service.references.register('p','evaluation',evaluation_reference(config))
        self.service.publish_contract('human-secret','p','c',doc,expected_revision=1,idempotency_key='final-contract')
        self.service.command('human-secret','p','r','apply_contract',expected_revision=1,idempotency_key='apply-final',payload=dict(contract_id='c',revision=2))
        protocol=dict(primary_model=trial['trial_id'],model_trials=[trial['trial_id']],proposal_sha256='a'*64)
        receipt=self.service.submit_ood_final('human-secret','p','r',request_key='final',protocol=protocol,
            hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))
        backend=OODFinalBackend(self.image)
        # Register final backend collectors in the same fixture cleanup.
        self.addCleanup(lambda:self._remove_final(backend))
        supervisor=Supervisor(ExecutionStore(self.service.path),Path(self.tmp.name)/'final-evidence',backend=backend)
        final=supervisor.execute(receipt['execution_attempt_id'],'independent-evaluator')
        path=Path(final['report']['evidence_path'])
        self.assertEqual(final['state'],'succeeded',(path/'candidate-stream.log').read_text()[-1500:])
        report=json.loads((path/'study-result.json').read_text())
        self.assertEqual(report['schema'],'asr-ood-independent-validation/1')
        self.assertEqual(report['assessment'],'objective_not_met_on_frozen_test')
        self.assertEqual(report['label_validity']['private_id']['equation_valid'],64)
        self.assertEqual(report['label_validity']['private_ood']['equation_valid'],64)
        self.assertNotIn('private_id',receipt['execution_request'])
        with self.assertRaisesRegex(ValueError,'final_protocol_frozen'):
            self.execute('forbidden-after-test',dict(operation='fit',augmentation_trials=[]))

    @staticmethod
    def _remove_final(backend):
        import subprocess
        for identity in backend.collectors:
            subprocess.run(['docker','rm','-f',identity],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)


if __name__=='__main__':unittest.main()
