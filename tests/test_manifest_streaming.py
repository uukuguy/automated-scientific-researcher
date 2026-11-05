import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_note_artifact_sources as fixture
from asr_service.control import ControlError


class ManifestStreamingTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.NoteArtifactTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.s=self.case.service

    def test_manifest_never_uses_whole_file_read(self):
        original=Path.read_bytes
        def read(path):
            if path.name=='manifest.json':raise AssertionError('whole manifest read')
            return original(path)
        with patch.object(Path,'read_bytes',read):
            result=self.case.call('save',text='流式清单',artifact_references=[self.case.ref])
        self.assertEqual(result['status'],'saved')

    def select(self,raw,kind='snapshot',target='method.py',chunk=7):
        from asr_service.manifest_stream import select
        path=self.case.work/'test-manifest.json';path.write_bytes(raw)
        return select(path,kind,target,chunk)

    def raw(self,entries=None,**extra):
        return json.dumps(dict(schema='asr-workspace-snapshot/1',project_id='p',research_run_id='r',
            files=entries if entries is not None else [dict(path='method.py',sha256='a'*64,size=4)],**extra),ensure_ascii=False).encode()

    def test_chunk_boundaries_unicode_and_full_digest(self):
        raw=self.raw([dict(path='目录/😀.py',sha256='b'*64,size=9)],ignored={'nested':[1,{'value':'保留语法检查'}]})+b' \n\t'
        for chunk in (1,3,17,1048576):
            result=self.select(raw,target='目录/😀.py',chunk=chunk)
            self.assertEqual(result['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(result['bytes'],len(raw));self.assertEqual(result['entry']['size'],9)

    def test_trailing_invalid_data_is_not_hidden_by_early_target(self):
        for suffix in (b'{}',b' garbage',b'\xff',b' /* comment */'):
            with self.assertRaisesRegex(ValueError,'invalid_manifest_json'):
                self.select(self.raw()+suffix)
        with self.assertRaises(ValueError):self.select(self.raw()[:-2])

    def test_duplicate_target_or_binding_is_rejected(self):
        row=dict(path='method.py',sha256='a'*64,size=4)
        with self.assertRaisesRegex(ValueError,'ambiguous_manifest_target'):self.select(self.raw([row,row]))
        raw=self.raw().replace(b'"project_id": "p"',b'"project_id": "p", "project_id": "other"')
        with self.assertRaisesRegex(ValueError,'ambiguous_manifest_field'):self.select(raw)
        raw=self.raw().replace(b'"size": 4',b'"size": 4, "size": 8')
        with self.assertRaisesRegex(ValueError,'ambiguous_manifest_field'):self.select(raw)

    def test_trial_map_keeps_only_exact_target_and_checks_tail(self):
        raw=json.dumps(dict(trial_id='trial',execution_attempt_id='attempt',status='failed',
            artifacts={'unrelated':{'nested':[1,2,3]},'result.json':{'sha256':'c'*64,'bytes':12}})).encode()
        result=self.select(raw,kind='trial',target='result.json')
        self.assertEqual(result['entry'],dict(sha256='c'*64,bytes=12))
        self.assertEqual(result['headers']['status'],'failed')
        with self.assertRaises(ValueError):self.select(raw+b'false',kind='trial',target='result.json')
        duplicate=raw.replace(b'"result.json":',b'"result.json":{},"result.json":')
        with self.assertRaisesRegex(ValueError,'ambiguous_manifest_target'):
            self.select(duplicate,kind='trial',target='result.json')

    def test_missing_target_and_bad_structures_are_explicit(self):
        for raw in (b'[]',self.raw([]),self.raw().replace(b'"files": [',b'"files": {')):
            with self.assertRaises(ValueError):self.select(raw)

    def test_manifest_change_during_streaming_cannot_commit(self):
        from asr_service import manifest_stream
        original=manifest_stream.select
        def select(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            with path.open('ab') as stream:stream.write(b' ')
            return result
        with patch.object(manifest_stream,'select',side_effect=select):
            with self.assertRaisesRegex(ControlError,'note_artifact_unavailable'):
                self.case.call('save',text='变化中的清单',artifact_references=[self.case.ref])

    def test_large_manifest_does_not_retain_all_entries(self):
        import tracemalloc
        from asr_service.manifest_stream import select
        path=self.case.work/'large-manifest.json'
        with path.open('w') as stream:
            stream.write('{"schema":"asr-workspace-snapshot/1","project_id":"p","research_run_id":"r","files":[')
            for index in range(60000):
                if index:stream.write(',')
                json.dump(dict(path=f'file-{index}',sha256='a'*64,size=index),stream)
            stream.write(']}')
        tracemalloc.start()
        try:
            result=select(path,'snapshot','file-59999',1048576)
            current,peak=tracemalloc.get_traced_memory()
        finally:tracemalloc.stop()
        self.assertEqual(result['entry']['size'],59999)
        self.assertLess(current,1024*1024)
        self.assertLess(peak,12*1024*1024)
