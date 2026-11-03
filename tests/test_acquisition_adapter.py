"""First execution checks of the preserved team prototype and trusted adapter."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from research_projects.paired_acquisition import prototype as p, native_adapter as adapter


class PrototypeTests(unittest.TestCase):
    def test_preserved_source_and_static_paired_allocation(self):
        self.assertEqual(hashlib.sha256(Path(p.__file__).read_bytes()).hexdigest(),
            '7587e7161c26863df3be96c3376331d44234b37c7da98e391a168aea179fe2fb')
        blocks = {}; offset = 0
        for name, count in [('T0',32), ('TA',16), ('TB',16), ('B',16), ('G',16)]:
            blocks[name] = [[1+(offset+i)*.001,1.,1.] for i in range(count)]
            offset += count
        plan = p.static_plan(blocks,1101)
        self.assertEqual(len(plan['rows']),256)
        self.assertEqual(len({tuple(r['x']) for r in plan['rows']}),96)
        with self.assertRaisesRegex(ValueError,'collision'):
            p.static_plan(blocks,1101,excluded=[blocks['T0'][0]])
        with self.assertRaisesRegex(ValueError,'seed'):
            p.static_plan(blocks,1109)


@unittest.skipUnless(Path('artifacts/p5-task-execution-checks-001/inventory.json').is_file(), 'requires archived real numerical engineering evidence')
class NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        root = Path('artifacts/p5-task-execution-checks-001')
        for entry in json.loads((root/'inventory.json').read_text()):
            self.assertEqual(hashlib.sha256((root/entry['path']).read_bytes()).hexdigest(),entry['sha256'])
        event_path = next((root/'test_real_task_bound_numerical_label/evidence').rglob('study-events.json'))
        self.native = next(e['row'] for e in json.loads(event_path.read_text()) if e['type']=='sample')
        case = json.loads(Path('artifacts/p4-simulated-client-001/public/case.json').read_text())
        self.proposal = dict(proposal_id='1101/TT/T0/0', seed=1101,arm='TT',stream='T0',x=self.native['x'])
        self.plan = dict(kind='static-plan/1',rows=[self.proposal])
        # Fixture pins for fields not consumed by this one-row adapter check.
        self.contract = {field:'a'*64 for field in p.CONTRACT_FIELDS}
        self.contract['case_sha256'] = p.digest(case)
        for field, source in [('scenario_source_sha256','research_projects/ood_augmentation/project.py'),('validator_source_sha256','powerflow_lab/validation.py')]:
            self.contract[field] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
        self.expected = adapter.prepare_inputs(case,self.plan,self.contract)[self.proposal['proposal_id']]

    def convert(self,native=None):
        return adapter.convert(self.proposal,self.native if native is None else native,self.contract,self.expected)

    def ingest(self,receipt):
        return p.ingest(self.plan,[receipt],self.contract,{self.proposal['proposal_id']:p.digest(self.expected)})

    def test_real_native_result_rechecked_and_ingested_without_feasibility_claim(self):
        receipt = self.convert(); ledger = self.ingest(receipt)
        self.assertEqual(ledger['proposed'],1)
        self.assertTrue(receipt['check']['equation_valid'])
        self.assertEqual(receipt['check']['operational_status'],'violated')
        self.assertEqual(receipt['check']['thermal_limits_unassessed'],186)
        self.assertEqual(receipt['native_validation'],self.native['validation'])
        with self.assertRaisesRegex(ValueError,'exactly one'):
            p.ingest(self.plan,[],self.contract,{self.proposal['proposal_id']:p.digest(self.expected)})

    def test_reported_residual_is_preserved_but_independent_equations_govern(self):
        native = copy.deepcopy(self.native)
        native['validation']['max_mismatch_pu'] += 1e-16
        receipt = self.convert(native)
        self.assertNotEqual(receipt['native_validation']['max_mismatch_pu'],
                            receipt['independent_validation']['max_mismatch_pu'])
        self.assertTrue(receipt['check']['equation_valid'])

    def test_target_forgery_and_false_validation_are_not_dropped_as_bad_samples(self):
        for field in ('target','validation','input','source'):
            native = copy.deepcopy(self.native)
            if field == 'target': native['y'][0] += .1
            elif field == 'validation': native['validation']['equation_valid'] = False
            elif field == 'input': native['input']['bus'][0][2] += 1
            else: self.contract['validator_source_sha256'] = 'b'*64
            with self.assertRaises(ValueError):self.convert(native)

    def test_failures_keep_slot_and_cost_and_invalid_equations_keep_reason(self):
        native = copy.deepcopy(self.native)
        native.update(status='label_failure',y=None,error_type='RuntimeError',error='')
        with self.assertRaisesRegex(ValueError,'native exception shape'):self.convert(native)
        for key in ('solution','solution_sha256','validation','solver'):native.pop(key)
        receipt = self.convert(native)
        self.assertEqual(self.ingest(receipt)['elapsed_ms'],native['elapsed_ms'])
        self.assertEqual(receipt['error']['type'],'RuntimeError')
        invalid = copy.deepcopy(self.native)
        invalid['solution']['bus'][0][8] += .5
        invalid['solution_sha256'] = p.digest(invalid['solution'])
        invalid['validation'] = adapter.validate(self.expected,invalid['solution'],1e-7)
        invalid.update(status='invalid_label',y=None)
        receipt = self.convert(invalid)
        self.assertFalse(receipt['check']['equation_valid'])
        self.assertEqual(self.ingest(receipt)['proposed'],1)
        receipt['attempt_count'] = 2
        with self.assertRaisesRegex(ValueError,'one exact integer'):self.ingest(receipt)


if __name__ == '__main__':unittest.main()
