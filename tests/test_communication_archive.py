import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


class CommunicationArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'run';self.root.mkdir();self.out=Path(self.tmp.name)/'archive'
        db=sqlite3.connect(self.root/'control.db')
        for table in ('asr_organization','asr_events','asr_runtime_sessions','asr_commands','asr_contracts','asr_hypotheses','asr_findings'):
            db.execute(f'CREATE TABLE {table}(record TEXT)')
        db.execute('INSERT INTO asr_organization VALUES (?)',(json.dumps(dict(seq=1,author='lead',document=dict(text='full cross-role message'))),));db.commit();db.close()
        (self.root/'recovery-test.json').write_text(json.dumps({'reason':'recorded transport recovery'}))
        brief=self.root/'workspaces/lead/CLIENT-BRIEF.md';brief.parent.mkdir(parents=True);brief.write_text('Complete project instructions')
        step=self.root/'steps/000-lead';step.mkdir(parents=True);self.step=step
        self.journal=self.root/'pi-private/session.jsonl';self.journal.parent.mkdir()
        self.journal.write_text(json.dumps(dict(type='message',message=dict(role='user',content='Exact prompt')))+'\n'+json.dumps(dict(type='message',message=dict(role='assistant',content=[dict(type='text',text='Visible reply'),dict(type='thinking',thinking='private thought')],access_token='do-not-export')))+'\n')
        (step/'request.json').write_text(json.dumps(dict(actor='lead',deliveries=[])))
        (step/'result.json').write_text(json.dumps(dict(status='settled',recovery=dict(native_session_file=str(self.journal)))))
        (step/'events.jsonl').write_text(json.dumps(dict(type='tool_execution_end',result=dict(text='complete tool response',Authorization='Bearer secret')))+'\n')

    def test_preserves_messages_and_tool_results_with_explicit_redaction_manifest(self):
        from integrations.runtimes.communication_archive import archive
        result=archive(self.root,self.out)
        self.assertEqual(result['gaps'],[])
        text='\n'.join(p.read_text() for p in self.out.rglob('*') if p.is_file())
        for value in ('Exact prompt','Visible reply','complete tool response','full cross-role message','recorded transport recovery','Complete project instructions'):self.assertIn(value,text)
        for value in ('do-not-export','private thought','Bearer secret'):self.assertNotIn(value,text)
        self.assertTrue(result['redactions']);self.assertTrue(result['sources'])
        with self.assertRaises(FileExistsError):archive(self.root,self.out)

    def test_missing_native_journal_is_a_gap_not_summary_success(self):
        from integrations.runtimes.communication_archive import archive
        self.journal.unlink();result=archive(self.root,self.out)
        self.assertTrue(any(g['code']=='missing_native_journal' for g in result['gaps']))

    def test_in_progress_partial_record_is_retained_and_marked(self):
        from integrations.runtimes.communication_archive import archive
        (self.step/'result.json').unlink()
        with (self.step/'events.jsonl').open('a') as f:f.write('{"incomplete":')
        result=archive(self.root,self.out)
        self.assertTrue(any(g['code']=='step_not_finalized' for g in result['gaps']))
        self.assertTrue(any(g['code']=='incomplete_or_invalid_jsonl' for g in result['gaps']))

    def test_cannot_export_arbitrary_file_as_native_journal(self):
        from integrations.runtimes.communication_archive import archive
        outside=Path(self.tmp.name)/'credentials.json';outside.write_text('{"secret":"outside"}')
        (self.step/'result.json').write_text(json.dumps(dict(status='settled',recovery=dict(native_session_file=str(outside)))))
        result=archive(self.root,self.out)
        self.assertTrue(any(g['code']=='unsafe_native_journal_path' for g in result['gaps']))
        self.assertNotIn('outside', '\n'.join(p.read_text() for p in self.out.rglob('*.jsonl')))

    def test_event_recorder_preserves_exact_payload_and_records_order_and_time(self):
        from integrations.runtimes.communication_archive import EventRecorder
        from datetime import datetime
        path=self.root/'new-events.jsonl'
        event=dict(type='tool_execution_end',result={'text':'complete '+('x'*20000)})
        with path.open('x') as stream:
            recorder=EventRecorder(stream);recorder(event);recorder({'type':'agent_end'})
        records=[json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual([r['sequence'] for r in records],[1,2])
        self.assertEqual(records[0]['event'],event)
        self.assertIsNotNone(datetime.fromisoformat(records[0]['recorded_at']).tzinfo)

    def test_private_note_versions_and_accepted_heads_are_archived(self):
        from integrations.runtimes.communication_archive import archive
        path=self.root/'research-notes/member/revisions';path.mkdir(parents=True)
        (path/'version.json').write_text(json.dumps(dict(text='preserved research note',access_token='secret-note-token')))
        with sqlite3.connect(self.root/'control.db') as db:
            db.execute('CREATE TABLE asr_note_heads(project TEXT,run TEXT,owner TEXT,revision TEXT)')
            db.execute("INSERT INTO asr_note_heads VALUES ('p','r','lead','version')")
        archive(self.root,self.out)
        self.assertTrue((self.out/'control/asr_note_heads.json').is_file())
        text=(self.out/'research-notes/member/revisions/version.json').read_text()
        self.assertIn('preserved research note',text);self.assertNotIn('secret-note-token',text)

    def test_context_preparation_and_admission_records_are_exported_with_scope(self):
        from integrations.runtimes.communication_archive import archive
        (self.root/'identity.json').write_text(json.dumps(dict(project_id='p',research_run_id='r')))
        with sqlite3.connect(self.root/'control.db') as db:
            db.execute('CREATE TABLE asr_requests(project TEXT,scope TEXT,request_key TEXT,payload TEXT,record TEXT)')
            for project,scope,text in [('p','context-prepare:'+json.dumps(['r','lead']),'original context preparation'),('p','context-admission:'+json.dumps(['r','lead']),'admission record'),('p','context-source:'+json.dumps(['r','lead']),'frozen conversation source'),('p','context-cursor:'+json.dumps(['r','lead']),'runtime cursor binding'),('other','context-prepare:'+json.dumps(['r','lead']),'unrelated private content')]:
                db.execute('INSERT INTO asr_requests VALUES (?,?,?,?,?)',(project,scope,'key','[]',json.dumps(dict(text=text))))
        archive(self.root,self.out)
        text=(self.out/'control/context_requests.json').read_text()
        self.assertIn('original context preparation',text);self.assertIn('admission record',text);self.assertIn('frozen conversation source',text);self.assertIn('runtime cursor binding',text)
        self.assertNotIn('unrelated private content',text)
