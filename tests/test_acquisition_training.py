"""Training provenance checks; the full numerical path is opt-in below."""
import copy
import json
from pathlib import Path
import unittest

from research_projects.paired_acquisition import prototype as p
from research_projects.paired_acquisition import training_adapter as t


@unittest.skipUnless(Path('artifacts/p4-final-image-002/manifest.json').is_file(), 'requires pinned local scientific build')
class TrainingPreparationTests(unittest.TestCase):
    def setUp(self):
        self.image = json.loads(Path('artifacts/p4-final-image-002/manifest.json').read_text())
        self.materials = {name:json.loads(Path(f'artifacts/p4-simulated-client-001/public/{name}.json').read_text())
                          for name in ('case','train','id_dev','diagnostic')}
        self.policy = dict(schema='asr-paired-sampling/1',proposal_sha256='a'*64,purpose='augmentation',
            charging='each_slot_no_retries',groups={'g':dict(blocks={'T0':[[1.001+i*.001,.99,1.01] for i in range(64)]},arms={'TT':['T0']})})

    def prepare(self):
        return t.prepare(self.materials,self.policy,'g','TT',1101,self.image,expected_image_hash=p.digest(self.image))

    def test_all_pins_come_from_frozen_materials_and_sources(self):
        prepared = self.prepare()
        self.assertEqual(len(prepared['plan']['rows']),64)
        self.assertEqual(len(prepared['expected_inputs']),64)
        self.assertEqual(prepared['contract']['original_sha256'],p.digest(self.materials['train']))
        self.assertEqual(prepared['contract']['environment_sha256'],p.digest(self.image))
        self.assertEqual(set(prepared['contract']),p.CONTRACT_FIELDS)
        self.assertNotIn('a'*64,prepared['contract'].values())

    def test_modified_source_original_status_or_public_collision_rejected(self):
        for change in ('source','status','overlap','size'):
            with self.subTest(change=change):
                old=copy.deepcopy((self.image,self.materials,self.policy))
                if change=='source':self.image['sources']['research_projects/ood_augmentation/worker.py']='b'*64
                elif change=='status':self.materials['train'][0]['status']='label_failure'
                elif change=='overlap':self.policy['groups']['g']['blocks']['T0'][0]=self.materials['train'][0]['x']
                else:self.policy['groups']['g']['blocks']['T0'].pop()
                with self.assertRaises(ValueError):self.prepare()
                self.image,self.materials,self.policy=old

    def test_protocol_hash_uses_control_canonicalization_for_unicode_names(self):
        from asr_service.paired_sampling import fingerprint
        self.policy['groups']['方向甲']=self.policy['groups'].pop('g')
        prepared=t.prepare(self.materials,self.policy,'方向甲','TT',1101,self.image,expected_image_hash=p.digest(self.image))
        self.assertEqual(prepared['contract']['protocol_sha256'],fingerprint(self.policy))

    def test_preparation_pin_rejects_post_dispatch_edits(self):
        prepared=self.prepare();pin=p.digest(prepared)
        prepared['plan']['rows'][0]['x'][0]+=.01
        with self.assertRaisesRegex(ValueError,'preparation pin'):
            t.ingest(prepared,[],expected_preparation_hash=pin)


@unittest.skipUnless(Path('artifacts/p5-training-binding-002/inventory.json').is_file(), 'requires archived full-arm training fixture')
class TrainingBundleTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        root=Path('artifacts/p5-training-binding-002')
        for entry in json.loads((root/'inventory.json').read_text()):
            self.assertEqual(hashlib.sha256((root/entry['path']).read_bytes()).hexdigest(),entry['sha256'])
        self.prepared=json.loads((root/'fixture/preparation.json').read_text())
        self.bundle=json.loads((root/'fixture/label-bundle.json').read_text())
        self.prep_hash=p.digest(self.prepared)

    def test_one_failed_slot_retained_without_replacement_or_extra_training_row(self):
        # Constructed exception fixture; not a claimed observed solver failure.
        ledger=self.bundle['ledger'];receipts=[v['receipt'] for v in ledger['records']]
        failed=receipts[0]
        failed.update(status='label_failure',y=None,error=dict(type='FixtureFailure',message='retained'),converged=None)
        for key in ('solution','solution_sha256','y_sha256','check','native_validation','independent_validation'):
            failed.pop(key,None)
        self.bundle['ledger']=p.ingest(ledger['plan'],receipts,self.prepared['contract'],ledger['expected_inputs'])
        result=t.training_manifest(self.prepared,self.bundle,expected_preparation_hash=self.prep_hash,expected_bundle_hash=p.digest(self.bundle))
        self.assertEqual(result['proposed'],64)
        self.assertEqual(result['labelled'],63)
        self.assertEqual(len(result['rows']),191)
        self.assertEqual(self.bundle['ledger']['elapsed_ms'],ledger['elapsed_ms'])
        self.assertEqual(self.bundle['ledger']['records'][0]['receipt']['status'],'label_failure')

    def test_bundle_cannot_substitute_other_plan_even_with_new_self_hash(self):
        self.bundle['ledger']['plan']['rows'][0]['arm']='other'
        with self.assertRaisesRegex(ValueError,'ledger preparation correspondence'):
            t.training_manifest(self.prepared,self.bundle,expected_preparation_hash=self.prep_hash,expected_bundle_hash=p.digest(self.bundle))


if __name__=='__main__':unittest.main()
