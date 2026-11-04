"""Versioned research notes with source verification, no authority ledger."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from asr_context import Material, compact
from asr_context.notes import NoteStore, restore


class ResearchNotesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=NoteStore(Path(self.tmp.name),scope='project/run/lead')
        self.source=Material('trial','r1','原始反证结果'*1000)

    def test_draft_is_immutable_and_acceptance_belongs_to_caller(self):
        first=self.store.save('反证仍成立',sources=[self.source])
        second=self.store.save('旧解释已修订',sources=[self.source],parent=first)
        self.assertNotEqual(first,second)
        self.assertEqual(self.store.read(first)['text'],'反证仍成立')
        self.assertEqual(self.store.read(second)['parent'],first)
        self.assertEqual(self.store.save('反证仍成立',sources=[self.source]),first)
        self.assertEqual(restore(self.store,accepted_revision=first,materials=[self.source],role='lead')['material'].text,'反证仍成立')
        self.assertIsNone(restore(self.store,accepted_revision=None,materials=[],role='lead')['material'])

    def test_stale_missing_or_inaccessible_source_prevents_installation(self):
        rev=self.store.save('发现',sources=[self.source])
        for rows,reason in [([], 'source_unavailable'),([replace(self.source,revision='r2')],'source_changed'),
                            ([replace(self.source,text='修改')],'source_changed'),
                            ([replace(self.source,roles=('validator',))],'source_unavailable')]:
            result=restore(self.store,accepted_revision=rev,materials=rows,role='lead')
            self.assertEqual(result['status'],'deferred');self.assertEqual(result['reason'],reason)
            self.assertNotIn('material',result)

    def test_citation_does_not_force_large_evidence_into_context(self):
        rev=self.store.save('反证未被推翻，后续需复核',sources=[self.source])
        note=restore(self.store,accepted_revision=rev,materials=[self.source],role='lead')['material']
        result=compact([self.source,note],role='lead',max_bytes=2000)
        self.assertEqual(result['status'],'ready')
        self.assertIn(note.id,result['retained']);self.assertIn('trial',result['omitted'])
        self.assertEqual(result['materials'][0]['citations'],['trial'])

    def test_cross_scope_and_corrupt_note_are_rejected(self):
        rev=self.store.save('研究笔记',sources=[self.source])
        with self.assertRaises(ValueError):NoteStore(Path(self.tmp.name),scope='another-run').read(rev)
        path=Path(self.tmp.name)/'revisions'/f'{rev}.json';path.write_text('{}')
        with self.assertRaises(ValueError):self.store.read(rev)

    def test_missing_parent_and_duplicate_sources_rejected(self):
        with self.assertRaises(ValueError):self.store.save('x',sources=[self.source],parent='0'*64)
        with self.assertRaises(ValueError):self.store.save('x',sources=[self.source,self.source])
        with self.assertRaises(ValueError):self.store.save(' ',sources=[])

    def test_unavailable_citation_and_duplicate_restore_input_are_rejected(self):
        with self.assertRaises(ValueError):compact([Material('note','v1','claim',citations=('absent',))],role='lead',max_bytes=2000)
        rev=self.store.save('x',sources=[self.source])
        with self.assertRaises(ValueError):restore(self.store,accepted_revision=rev,materials=[self.source,self.source],role='lead')

    def test_actual_failure_notes_restore_from_citations_under_capacity(self):
        import json
        corpus=json.loads(Path('tests/fixtures/research_context/actual-failures.json').read_text())
        sources=[Material(c['id'],'captured',json.dumps(c,ensure_ascii=False)) for c in corpus['cases']]
        notes=[]
        for case,source in zip(corpus['cases'],sources):
            revision=self.store.save(case['id']+'：'+case['observed_category']+'；'+case['errors'][0],sources=[source])
            notes.append(restore(self.store,accepted_revision=revision,materials=sources,role='lead')['material'])
        result=compact(sources+notes,role='lead',max_bytes=8000)
        self.assertEqual(result['status'],'ready')
        for note in notes:self.assertIn(note.id,result['retained'])
        self.assertTrue(result['omitted'])
        for note in notes:
            original=next(r for r in sources if r.id==note.citations[0])
            self.assertIn(original.id,{r['id'] for r in result['catalog']})
        self.assertIn('context_capacity',next(n.text for n in notes if '028-lead_1' in n.text))
        self.assertIn('connection_terminated',next(n.text for n in notes if '030-organizer' in n.text))
