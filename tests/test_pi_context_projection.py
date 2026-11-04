import json
from pathlib import Path
import shutil
import tempfile
import unittest
from integrations.runtimes.pi_context import observe


class PiContextProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'session.jsonl'

    def write(self,entries):
        self.path.write_text('\n'.join(json.dumps(x) for x in [dict(type='session',version=3,id='session'),*entries])+'\n')

    def fake(self,entries,leaf):
        by={e['id']:e for e in entries};branch=[]
        while leaf is not None:
            e=by[leaf];branch.append(e);leaf=e['parentId']
        return dict(entries=[dict(source_entry_id=e['id'],messages=[e['message']]) for e in reversed(branch)])

    def call(self,leaf='a',**kwargs):
        return observe(self.path,expected_session_id='session',leaf_id=leaf,scope='p/r/lead',keep_recent_groups=1,max_journal_bytes=100000,**kwargs)

    def test_private_reasoning_and_credentials_are_not_projected(self):
        self.write([dict(type='message',id='u',parentId=None,message=dict(role='user',content='问题')),
            dict(type='message',id='a',parentId='u',message=dict(role='assistant',content=[dict(type='thinking',thinking='private thought'),dict(type='text',text='可见结果 Bearer abc.secret')],stopReason='stop'))])
        result=self.call(projector=self.fake);self.assertEqual(result['status'],'observed')
        text=json.dumps(result,ensure_ascii=False)
        self.assertNotIn('private thought',text);self.assertNotIn('abc.secret',text);self.assertIn('可见结果',text)
        self.assertGreater(result['witness']['redactions'],0);self.assertFalse(result['witness']['active_cursor_verified'])
        self.assertIn('private thought',self.path.read_text())

    def test_explicit_branch_is_used_instead_of_last_file_record(self):
        self.write([dict(type='message',id='u',parentId=None,message=dict(role='user',content='问题')),
            dict(type='message',id='a',parentId='u',message=dict(role='assistant',content='选定分支')),
            dict(type='message',id='b',parentId='u',message=dict(role='assistant',content='其它分支'))])
        result=self.call(projector=self.fake);self.assertEqual(result['status'],'observed')
        self.assertNotIn('其它分支',json.dumps(result,ensure_ascii=False))
        self.assertEqual(self.call(leaf='missing',projector=self.fake)['status'],'deferred')

    def test_unsupported_or_partial_journal_is_deferred_without_truncating(self):
        self.path.write_text('{"incomplete":')
        self.assertEqual(self.call(projector=self.fake)['status'],'deferred')
        result=observe(self.path,expected_session_id='session',leaf_id='a',scope='scope',keep_recent_groups=1,max_journal_bytes=5,projector=self.fake)
        self.assertEqual(result['reason'],'journal_memory_limit')
        self.assertEqual(self.path.read_text(),'{"incomplete":')

    @unittest.skipUnless(shutil.which('pi'),'pinned pi SDK unavailable')
    def test_installed_sdk_projects_compaction_and_context_edits(self):
        self.write([dict(type='message',id='old',parentId=None,message=dict(role='user',content='old content')),
            dict(type='message',id='a',parentId='old',message=dict(role='assistant',content=[dict(type='text',text='old answer')],stopReason='stop')),
            dict(type='message',id='new',parentId='a',message=dict(role='user',content='保留的请求')),
            dict(type='compaction',id='cut',parentId='new',summary='已有研究记忆',firstKeptEntryId='new',tokensBefore=1000,timestamp='2026-11-04T00:00:00Z')])
        result=self.call(leaf='cut');self.assertEqual(result['status'],'observed',result)
        text=json.dumps(result,ensure_ascii=False)
        self.assertNotIn('old content',text);self.assertIn('已有研究记忆',text);self.assertIn('保留的请求',text)
        self.write([dict(type='message',id='u',parentId=None,message=dict(role='user',content='before edit')),
            dict(type='context_edit',id='edit',parentId='u',targetId='u',replacement=dict(content='after edit'))])
        result=self.call(leaf='edit');self.assertEqual(result['status'],'observed',result)
        self.assertIn('after edit',json.dumps(result));self.assertNotIn('before edit',json.dumps(result))

    def test_helper_timeout_keeps_explicit_limit_and_original_journal(self):
        import subprocess
        self.write([dict(type='message',id='a',parentId=None,message=dict(role='user',content='原始请求'))])
        original=self.path.read_bytes()
        def stalled(entries,leaf):raise subprocess.TimeoutExpired('projection-helper',3)
        result=self.call(projector=stalled)
        self.assertEqual(result['reason'],'projection_helper_timeout');self.assertEqual(result['limit'],3)
        self.assertEqual(self.path.read_bytes(),original)

    @unittest.skipUnless(shutil.which('pi'),'pinned pi SDK unavailable')
    def test_helper_preserves_utf8_character_split_across_pipe_chunks(self):
        import subprocess,time
        binary=Path(shutil.which('pi')).resolve();index=binary.parents[1]/'index.js'
        payload=json.dumps(dict(entries=[dict(type='message',id='a',parentId=None,message=dict(role='user',content='中文证据'))],leafId='a'),ensure_ascii=False).encode()
        split=payload.index('中'.encode())+1
        process=subprocess.Popen(['node',str(Path('integrations/runtimes/pi_context_projection.mjs').resolve()),str(index)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            process.stdin.write(payload[:split]);process.stdin.flush();time.sleep(.15)
            process.stdin.write(payload[split:]);process.stdin.close();process.stdin=None
            stdout,stderr=process.communicate(timeout=5)
            self.assertEqual(process.returncode,0,stderr.decode())
            result=json.loads(stdout);self.assertEqual(result['entries'][0]['messages'][0]['content'],'中文证据')
        finally:
            if process.poll() is None:process.kill();process.wait()
