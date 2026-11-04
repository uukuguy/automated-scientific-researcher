"""Offline context selection: no runtime, model or credentials."""
import json
import unittest
from dataclasses import replace
from asr_context import Material, compact


class ResearchContextTests(unittest.TestCase):
    def material(self, key, **kw):
        return Material(key, 'r1', kw.pop('text','原始研究材料 '+key), **kw)

    def test_protected_code_dependencies_and_unfinished_groups_survive(self):
        rows=[self.material('code'),self.material('finding',references=('code',),protected=True),
              self.material('call',group='pending',complete=False),self.material('result',group='pending'),
              self.material('old',text='x'*5000)]
        result=compact(rows,role='lead',max_bytes=2400)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(set(result['retained']),{'code','finding','call','result'})
        self.assertEqual(result['omitted'],['old'])
        self.assertLessEqual(len(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()),2400)

    def test_protected_overflow_is_deferred_without_truncation(self):
        result=compact([self.material('negative',text='反证'*500,protected=True)],role='lead',max_bytes=600)
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result['reason'],'protected_material_exceeds_capacity')
        self.assertGreater(result['required_bytes'],600)
        self.assertIn('negative',result['protected'])

    def test_private_material_never_enters_catalog(self):
        result=compact([self.material('public'),self.material('secret',roles=('validator',))],role='lead',max_bytes=2000)
        self.assertNotIn('secret',json.dumps(result))

    def test_unavailable_reference_is_explicit_not_silently_lost(self):
        for rows in [[self.material('claim',references=('missing',))],
                     [self.material('claim',references=('private',)),self.material('private',roles=('validator',))]]:
            with self.assertRaisesRegex(ValueError,'reference_unavailable'):compact(rows,role='lead',max_bytes=2000)

    def test_repeat_compression_requires_original_sources_and_keeps_fingerprints(self):
        rows=[self.material('rule',protected=True),self.material('old',text='x'*3000)]
        first=compact(rows,role='lead',max_bytes=2000)
        again=compact(rows,role='lead',max_bytes=1500)
        self.assertEqual(first['catalog'],again['catalog'])
        self.assertEqual(first['retained'],again['retained'])
        changed=compact([replace(rows[0],revision='r2'),rows[1]],role='lead',max_bytes=1500)
        self.assertNotEqual(first['catalog'],changed['catalog'])

    def test_invalid_inputs_and_duplicate_identity(self):
        for cap in [True,0,-1]:
            with self.assertRaises(ValueError):compact([],role='lead',max_bytes=cap)
        with self.assertRaises(ValueError):compact([self.material('x'),self.material('x')],role='lead',max_bytes=2000)

    def test_actual_failures_keep_exact_error_and_role_across_projections(self):
        from pathlib import Path
        corpus=json.loads(Path('tests/fixtures/research_context/actual-failures.json').read_text())
        rows=[Material(c['id'],'r1',json.dumps(c,ensure_ascii=False),protected=True) for c in corpus['cases']]
        rows.append(Material('large-old-output','r1','discardable '*3000))
        for cap in [16000,14000]:
            result=compact(rows,role='researcher',max_bytes=cap)
            self.assertEqual(result['status'],'ready')
            self.assertEqual(len(result['materials']),6)
            recovered={r['id']:json.loads(r['text']) for r in result['materials']}
            self.assertEqual(recovered['028-lead_1']['observed_category'],'context_capacity')
            self.assertEqual(recovered['030-organizer']['observed_category'],'connection_terminated')
            for original in corpus['cases']:
                self.assertEqual(recovered[original['id']],original)
