import json
from pathlib import Path
import shutil
import unittest
from asr_service.control import ControlError
import test_context_admission as admission


@unittest.skipUnless(shutil.which('pi'),'pinned pi SDK unavailable')
class ContextSourcesTests(unittest.TestCase):
    # Reuse fixture helpers without repeating the base test cases.
    bundle=admission.ContextAdmissionTests.bundle
    session=admission.ContextAdmissionTests.session
    admit=admission.ContextAdmissionTests.admit
    def setUp(self):
        admission.ContextAdmissionTests.setUp(self)
        self.path=self.s.path.parent/'native.jsonl'
        self.path.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in [dict(type='session',version=3,id='native'),dict(type='message',id='u',parentId=None,message=dict(role='user',content='研究问题')),dict(type='message',id='a',parentId='u',message=dict(role='assistant',content=[dict(type='text',text='失败结果必须保留')],stopReason='stop'))])+'\n')

    def register(self,token='human-secret',key='source',subject='lead'):
        return self.s.register_context_source(token,'p','r',subject=subject,idempotency_key=key,path=str(self.path),native_session_id='native',leaf_id='a',keep_recent_groups=1,max_journal_bytes=100000)

    def prepared(self):
        return self.s.prepare_context('human-secret','p','r',subject='lead',reviewer_subject='lead2',idempotency_key='prep-source',source_registration='source')

    def test_host_registration_freezes_visible_sources_without_active_cursor_claim(self):
        receipt=self.register();self.assertEqual(receipt['status'],'registered')
        self.assertFalse(receipt['active_cursor_verified']);self.assertFalse(receipt['installation_authorized'])
        self.assertEqual(receipt,self.register())
        prepared=self.prepared()
        self.assertTrue(any('失败结果必须保留' in m['text'] for m in prepared['materials']))
        result=self.admit(prepared,self.bundle(prepared))
        self.assertEqual(result['status'],'admitted');self.assertFalse(result['installation_authorized'])

    def test_researcher_and_other_member_cannot_supply_sources(self):
        with self.assertRaisesRegex(ControlError,'forbidden'):self.register(token='lead')
        self.register(subject='lead2')
        with self.assertRaisesRegex(ControlError,'context_source_unavailable'):self.prepared()

    def test_mutated_journal_cannot_be_prepared(self):
        self.register();self.path.write_text(self.path.read_text().replace('失败结果必须保留','篡改结果'))
        with self.assertRaisesRegex(ControlError,'context_source_changed'):self.prepared()

    def test_mutated_journal_defers_existing_admission(self):
        self.register();prepared=self.prepared();bundle=self.bundle(prepared)
        self.path.write_text(self.path.read_text().replace('失败结果必须保留','篡改结果'))
        result=self.admit(prepared,bundle)
        self.assertEqual(result['status'],'deferred');self.assertEqual(result['check']['reason'],'context_source_changed')
        self.assertNotEqual(result['check']['details']['expected_journal_sha256'],result['check']['details']['observed_journal_sha256'])
        self.assertIn('recovery',result['check']['details'])

    def test_parser_limit_is_recorded_without_registering_partial_source(self):
        result=self.s.register_context_source('human-secret','p','r',subject='lead',idempotency_key='limited',path=str(self.path),native_session_id='native',leaf_id='a',keep_recent_groups=1,max_journal_bytes=5)
        self.assertEqual(result['status'],'deferred');self.assertEqual(result['observation']['reason'],'journal_memory_limit')
        with self.assertRaisesRegex(ControlError,'context_source_unavailable'):
            self.s.prepare_context('human-secret','p','r',subject='lead',reviewer_subject='lead2',idempotency_key='limited-prep',source_registration='limited')
