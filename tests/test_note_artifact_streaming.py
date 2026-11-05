import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_note_artifact_sources as fixture
from asr_service import note_artifacts


class ArtifactStreamingTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.NoteArtifactTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.s=self.case.service

    def test_attachment_body_does_not_use_whole_file_reads(self):
        original=Path.read_bytes
        def read(path):
            if path.name=='method.py':raise AssertionError('whole attachment read')
            return original(path)
        with patch.object(Path,'read_bytes',read):
            draft=self.case.call('save',text='引用原件',artifact_references=[self.case.ref])
            self.case.call('adopt',revision=draft['revision'],expected_note=None)
            page=self.case.call('source_read',artifact_reference=self.case.ref,limit=7)
        self.assertEqual(page['text'],'def sol')

    def snapshot(self,body):
        digest=hashlib.sha256(body).hexdigest()
        manifest=json.dumps(dict(schema='asr-workspace-snapshot/1',project_id='p',research_run_id='r',files=[dict(path='data.txt',sha256=digest,size=len(body))])).encode()
        key=hashlib.sha256(manifest).hexdigest();root=self.s.path.parent/'snapshots'/key
        (root/'files').mkdir(parents=True,exist_ok=True);(root/'manifest.json').write_bytes(manifest);(root/'files/data.txt').write_bytes(body)
        return dict(kind='snapshot',snapshot_sha256=key,path='data.txt'),root/'files/data.txt'

    def test_unicode_pages_cross_small_chunks_without_truncation(self):
        text='甲😀e\u0301\n'*11
        ref,path=self.snapshot(text.encode())
        from asr_service.control import ControlService
        policy=json.loads(json.dumps({k:v for k,v in self.s.artifact_io_policy.items() if k!='sha256'}))
        policy['limits']['artifact_read_chunk_bytes']['value']=3
        config=self.s.path.parent/'unicode-policy.json';config.write_text(json.dumps(policy))
        self.s=ControlService(self.s.path,credentials=self.s.credentials,capacity_policy_path=config);self.case.service=self.s
        draft=self.case.call('save',text='Unicode原件',artifact_references=[ref])
        offset=0;parts=[]
        while True:
            page=self.case.call('source_read',revision=draft['revision'],artifact_reference=ref,offset=offset,limit=7)
            self.assertEqual(page['total_characters'],len(text));parts.append(page['text'])
            if not page['has_more']:break
            offset=page['next_offset']
        self.assertEqual(''.join(parts),text)

    def test_invalid_utf8_after_requested_page_is_still_rejected(self):
        from asr_service.control import ControlError
        ref,path=self.snapshot(b'valid requested page'+b'x'*100+b'\xff')
        draft=self.case.call('save',text='保留二进制原件',artifact_references=[ref])
        with self.assertRaisesRegex(ControlError,'note_source_not_utf8'):
            self.case.call('source_read',revision=draft['revision'],artifact_reference=ref,limit=3)

    def test_corruption_after_page_end_is_not_hidden(self):
        from asr_service.control import ControlError
        ref,path=self.snapshot(b'valid page'+b'x'*100)
        draft=self.case.call('save',text='核验全文',artifact_references=[ref]);path.write_bytes(b'valid page'+b'y'*100)
        with self.assertRaisesRegex(ControlError,'note_artifact_unavailable'):
            self.case.call('source_read',revision=draft['revision'],artifact_reference=ref,limit=3)

    def test_change_between_hash_and_page_read_is_rejected(self):
        from asr_service.control import ControlError
        ref,path=self.snapshot(b'original')
        draft=self.case.call('save',text='原件',artifact_references=[ref]);original=note_artifacts._stream_file
        def read(*args,**kwargs):
            if kwargs.get('page') is not None:path.write_bytes(b'changed!')
            return original(*args,**kwargs)
        with patch.object(note_artifacts,'_stream_file',side_effect=read):
            with self.assertRaisesRegex(ControlError,'note_artifact_unavailable'):
                self.case.call('source_read',revision=draft['revision'],artifact_reference=ref,limit=3)

    def test_large_attachment_preparation_keeps_only_summary(self):
        import tracemalloc
        ref,path=self.snapshot(b'x'*(12*1024*1024))
        tracemalloc.start()
        try:
            with self.s._connect() as db:prepared=note_artifacts.prepare(db,self.s,'p','r',[ref])
            current,peak=tracemalloc.get_traced_memory()
        finally:tracemalloc.stop()
        attachment=prepared.rows[0][1]
        self.assertEqual(attachment.witness.value['bytes'],12*1024*1024)
        self.assertLess(peak,5*1024*1024)
        self.assertLess(current,1024*1024)

    def test_stream_read_allows_another_writer(self):
        original=note_artifacts._stream_file
        def read(*args,**kwargs):
            with self.s._connect() as db:
                db.execute('PRAGMA busy_timeout=50');db.execute('BEGIN IMMEDIATE');db.rollback()
            return original(*args,**kwargs)
        with patch.object(note_artifacts,'_stream_file',side_effect=read):
            draft=self.case.call('save',text='事务外读取',artifact_references=[self.case.ref])
            self.case.call('source_read',revision=draft['revision'],artifact_reference=self.case.ref)

    def test_large_page_read_keeps_only_requested_text(self):
        import tracemalloc
        ref,path=self.snapshot(b'x'*(12*1024*1024))
        with self.s._connect() as db:
            prepared=note_artifacts.prepare(db,self.s,'p','r',[ref])
            tracemalloc.start()
            try:
                page=note_artifacts.read_page(db,self.s,'p','r',ref,offset=12000000,limit=13,prepared=prepared)
                _,peak=tracemalloc.get_traced_memory()
            finally:tracemalloc.stop()
        self.assertEqual(page['text'],'x'*13);self.assertEqual(page['total_characters'],12*1024*1024)
        self.assertLess(peak,6*1024*1024)

    def test_incomplete_utf8_at_eof_and_out_of_range_are_explicit(self):
        from asr_service.control import ControlError
        ref,path=self.snapshot(b'good\xe4')
        draft=self.case.call('save',text='尾部不完整',artifact_references=[ref])
        with self.assertRaisesRegex(ControlError,'note_source_not_utf8'):
            self.case.call('source_read',revision=draft['revision'],artifact_reference=ref,limit=1)
        with self.s._connect() as db:
            page=note_artifacts.read_page(db,self.s,'p','r',self.case.ref,offset=len((self.case.work/'method.py').read_text()),limit=1)
            self.assertEqual(page['text'],'');self.assertFalse(page['has_more'])
            with self.assertRaisesRegex(ControlError,'note_source_offset_out_of_range'):
                note_artifacts.read_page(db,self.s,'p','r',self.case.ref,offset=999,limit=1)

    def test_explicit_service_policy_controls_chunk_and_receipt(self):
        from asr_service.control import ControlService
        policy=json.loads(json.dumps({k:v for k,v in self.s.artifact_io_policy.items() if k!='sha256'}))
        policy['limits']['artifact_read_chunk_bytes']['value']=2
        path=self.s.path.parent/'stream-policy.json';path.write_text(json.dumps(policy))
        service=ControlService(self.s.path,credentials=self.s.credentials,capacity_policy_path=path)
        with service._connect() as db:page=note_artifacts.read_page(db,service,'p','r',self.case.ref,limit=3)
        self.assertEqual(page['read_chunk_bytes'],2)
        self.assertEqual(page['capacity_policy_sha256'],service.artifact_io_policy['sha256'])
