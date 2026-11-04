"""Actual task-bound full-arm training and trusted receipt verification."""
import copy
import json
import os
from pathlib import Path
import unittest

import test_organization_execution as org
import test_acquisition_training as prep
from research_projects.paired_acquisition import training_adapter as t, prototype as p
from integrations.aar.bridge import ResearchBridge


@unittest.skipUnless(os.environ.get('ASR_SCIENTIFIC_IMAGE'), 'requires explicitly selected scientific image')
class TrainingExecutionTests(unittest.TestCase):
    def setUp(self):
        self.org=org.OrganizationExecutionTests('test_real_task_bound_numerical_label')
        self.org.setUp();self.addCleanup(self.org.doCleanups)
        self.f=self.org.f;self.s=self.f.service
        self.config=prep.TrainingPreparationTests('test_all_pins_come_from_frozen_materials_and_sources')
        self.config.setUp()
        document=copy.deepcopy(self.f.contract)
        document['provenance']['paired_sampling']=self.config.policy
        self.s.publish_contract('human-secret','p','c',document,expected_revision=1,idempotency_key='pair')
        state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','apply_contract',expected_revision=state['control_revision'],
            idempotency_key='pair-apply',payload=dict(contract_id='c',revision=2))
        root=Path(self.f.tmp.name)
        self.bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='worker',supervisor_token='human-secret',
            workspace=root/'worker',snapshots=root/'snapshots',capability_profile='research-organization-study/1',
            dispatch=lambda trial:self.f.supervisor.execute(trial['execution_attempt_id'],'training-test'))

    def submit(self,key,request,task='t'):
        result=self.bridge.call('submit_study',dict(request=request,timeout_seconds=60,
            hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1),organization_task=dict(task_id=task,revision=2)),key)
        return result['receipt']['trial_id']

    def test_full_arm_uses_own_labels_and_binds_actual_model(self):
        prepared=self.config.prepare();prep_hash=p.digest(prepared)
        root=Path(self.f.tmp.name)
        (root/'preparation.json').write_bytes(p.canonical(prepared))
        label=self.submit('labels',dict(operation='label',purpose='augmentation',
            coordinates=[row['x'] for row in prepared['plan']['rows']],paired_batch=dict(group_id='g',arm_id='TT')))
        bundle=t.ingest_trial(self.s,'worker','p','r',label,prepared,expected_preparation_hash=prep_hash)
        bundle_hash=p.digest(bundle)
        (root/'label-bundle.json').write_bytes(p.canonical(bundle))
        manifest=t.training_manifest(prepared,bundle,expected_preparation_hash=prep_hash,expected_bundle_hash=bundle_hash)
        manifest_hash=p.digest(manifest)
        (root/'training-manifest.json').write_bytes(p.canonical(manifest))
        self.assertEqual(manifest['labelled'],64)
        self.assertEqual(len(manifest['rows']),192)
        self.org.change('task','t',dict(self.org.task,status='completed',result='All 64 label slots checked',evidence_trial_ids=[label]),'worker',2)
        task=dict(self.org.task,experiment_operations=['study:fit'],status='assigned')
        self.org.change('task','fit',task,'lead')
        self.org.change('task','fit',dict(task,status='in_progress'),'worker',1)
        fitted=self.submit('fit',dict(operation='fit',augmentation_trials=[label]),task='fit')
        result=t.bind_fit(self.s,'worker','p','r',fitted,prepared,bundle,manifest,
            expected_preparation_hash=prep_hash,expected_bundle_hash=bundle_hash,expected_manifest_hash=manifest_hash)
        (root/'model-binding.json').write_bytes(p.canonical(result))
        self.assertEqual(result['receipt']['model']['training_count'],192)
        self.assertEqual(result['receipt']['training_sha256'],manifest['training_sha256'])
        self.assertEqual(result['receipt']['label_reference'],bundle['label_reference'])
        self.assertEqual(self.s.budgets.balance('p','sample_proposals')['spent'],64)
        self.assertEqual(self.s.budgets.balance('p','attempts')['spent'],2)
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],0)
        bad=copy.deepcopy(manifest);bad['rows'][-1]['y'][0]+=.01
        with self.assertRaisesRegex(ValueError,'manifest pin'):
            t.bind_fit(self.s,'worker','p','r',fitted,prepared,bundle,bad,
                expected_preparation_hash=prep_hash,expected_bundle_hash=bundle_hash,expected_manifest_hash=manifest_hash)
        # Matching a digest supplied alongside the edited object cannot replace
        # rebuilding its relationship to the externally pinned label ledger.
        bad['training_sha256']=p.digest(bad['rows'])
        with self.assertRaisesRegex(ValueError,'training manifest correspondence'):
            t.bind_fit(self.s,'worker','p','r',fitted,prepared,bundle,bad,
                expected_preparation_hash=prep_hash,expected_bundle_hash=bundle_hash,expected_manifest_hash=p.digest(bad))


if __name__=='__main__':unittest.main()
