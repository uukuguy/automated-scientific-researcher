import unittest
from unittest.mock import patch
import test_control_research_notes as fixture


class NoteIOTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.ControlResearchNotesTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.s=self.case.s

    def writable(self):
        with self.s._connect() as db:
            db.execute('PRAGMA busy_timeout=50');db.execute('BEGIN IMMEDIATE');db.rollback()

    def events(self):
        with self.s._connect() as db:
            return str(db.execute('SELECT record FROM asr_events').fetchall())

    def test_note_save_and_restore_do_not_hold_control_write_lock(self):
        from asr_context.notes import NoteStore
        original_save=NoteStore.save;original_read=NoteStore.read
        def save(store,*args,**kwargs):
            self.writable();return original_save(store,*args,**kwargs)
        def read(store,*args,**kwargs):
            self.writable();return original_read(store,*args,**kwargs)
        with patch.object(NoteStore,'save',save),patch.object(NoteStore,'read',read):
            draft=self.case.save()
            self.case.call('adopt',key='adopt',revision=draft['revision'],expected_note=None)
            self.assertEqual(self.case.call('read')['restoration']['status'],'ready')

    def test_save_control_change_keeps_draft_and_records_failure(self):
        from asr_service import research_notes
        from asr_service.control import ControlError
        original=research_notes._commit_operation
        def commit(*args,**kwargs):
            state=self.s.get_run('human-secret','p','r')
            self.s.command('human-secret','p','r','pause',expected_revision=state['control_revision'],idempotency_key='race-pause')
            return original(*args,**kwargs)
        with patch.object(research_notes,'_commit_operation',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'note_sources_changed') as caught:self.case.save()
        revision=caught.exception.details['retained_draft_revision']
        self.assertEqual(self.case.call('history_read',revision=revision)['status'],'historical_note')
        self.assertEqual(self.case.call('read')['status'],'empty')
        with self.s._connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM asr_requests WHERE request_key='draft'").fetchone())
        self.assertIn(revision,self.events())

    def test_save_membership_revoked_retains_unadopted_draft(self):
        from asr_service import research_notes
        from asr_service.control import ControlError
        import json
        original=research_notes._commit_operation
        def commit(*args,**kwargs):
            with self.s._connect() as db:
                row=db.execute("SELECT record FROM asr_organization WHERE kind='member' AND entity='lead' ORDER BY seq DESC LIMIT 1").fetchone()
            record=json.loads(row[0])
            self.s.change_organization('human-secret','p','r',kind='member',entity_id='lead',expected_revision=record['revision'],idempotency_key='disable',document=dict(record['document'],enabled=False))
            return original(*args,**kwargs)
        with patch.object(research_notes,'_commit_operation',side_effect=commit):
            with self.assertRaises(ControlError) as caught:self.case.save()
        self.assertFalse(caught.exception.details['adopted'])
        self.assertIn(caught.exception.details['retained_draft_revision'],self.events())

    def test_new_head_between_read_and_commit_is_not_overwritten(self):
        from asr_service import research_notes
        from asr_service.control import ControlError
        first=self.case.save()
        other=self.case.call('save',key='other',text='另一份草稿')
        original=research_notes._commit_operation
        def commit(*args,**kwargs):
            with patch.object(research_notes,'_commit_operation',original):
                self.case.call('adopt',key='winner',revision=other['revision'],expected_note=None)
            return original(*args,**kwargs)
        with patch.object(research_notes,'_commit_operation',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'revision_conflict'):
                self.case.call('adopt',key='loser',revision=first['revision'],expected_note=None)
        self.assertEqual(self.case.call('read')['accepted_revision'],other['revision'])

    def test_note_changed_after_read_is_rejected(self):
        from asr_service import research_notes
        from asr_service.control import ControlError
        draft=self.case.save();original=research_notes._commit_operation
        def commit(service,token,project,run,item,**kwargs):
            path=item['store'].store.directory/(draft['revision']+'.json')
            path.write_bytes(path.read_bytes()+b' ')
            return original(service,token,project,run,item,**kwargs)
        with patch.object(research_notes,'_commit_operation',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'note_sources_changed'):
                self.case.call('adopt',revision=draft['revision'],expected_note=None)

    def test_save_and_adopt_replay_do_not_require_note_files(self):
        from asr_context.notes import NoteStore
        draft=self.case.save();result=self.case.call('adopt',revision=draft['revision'],expected_note=None)
        with patch.object(NoteStore,'read',side_effect=AssertionError('unexpected file read')):
            self.assertEqual(draft,self.case.save())
            self.assertEqual(result,self.case.call('adopt',revision=draft['revision'],expected_note=None))

    def test_snapshot_reads_and_pages_do_not_hold_write_lock(self):
        import test_note_artifact_sources as fixture
        from asr_service import note_artifacts
        case=fixture.NoteArtifactTests();case.setUp();self.addCleanup(case.doCleanups);self.s=case.service
        original=note_artifacts._safe_file
        def read(*args):self.writable();return original(*args)
        with patch.object(note_artifacts,'_safe_file',side_effect=read) as reads:
            draft=case.call('save',text='保留附件',artifact_references=[case.ref])
            case.call('adopt',revision=draft['revision'],expected_note=None)
            self.assertEqual(case.call('read')['restoration']['status'],'ready')
            case.call('source_read',artifact_reference=case.ref)
        self.assertGreaterEqual(reads.call_count,8)

    def test_snapshot_replaced_after_read_is_not_adopted(self):
        import test_note_artifact_sources as fixture
        from asr_service import research_notes
        from asr_service.control import ControlError
        case=fixture.NoteArtifactTests();case.setUp();self.addCleanup(case.doCleanups)
        draft=case.call('save',text='保留附件',artifact_references=[case.ref])
        original=research_notes._commit_operation
        def commit(*args,**kwargs):
            (case.snapshots/case.snapshot/'files/method.py').write_text('changed')
            return original(*args,**kwargs)
        with patch.object(research_notes,'_commit_operation',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'note_artifact_unavailable'):
                case.call('adopt',revision=draft['revision'],expected_note=None)

    def test_all_context_installation_note_reads_are_outside_write_lock(self):
        import test_context_installation_service as fixture
        from asr_context.notes import NoteStore
        case=fixture.InstallationServiceTests();original=NoteStore.read;reads=[]
        def read(store,*args,**kwargs):
            self.s=case.base.s;self.writable();reads.append(args)
            return original(store,*args,**kwargs)
        with patch.object(NoteStore,'read',read):
            case.setUp();self.addCleanup(case.doCleanups)
            case.test_actual_sdk_append_is_verified_once_and_original_prefix_survives()
        self.assertGreaterEqual(len(reads),6)

    def test_context_admission_missing_note_is_durably_deferred(self):
        import test_context_admission as fixture
        from asr_service.note_io import PreparedStore
        case=fixture.ContextAdmissionTests();case.setUp();self.addCleanup(case.doCleanups)
        prepared=case.prepare();bundle=case.bundle(prepared)
        store=PreparedStore(case.s,'p','r','lead')
        (store.store.directory/(prepared['note_revision']+'.json')).unlink()
        result=case.admit(prepared,bundle)
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result,case.admit(prepared,bundle))

    def test_context_attachment_reads_through_native_installation_are_unlocked(self):
        import hashlib,json
        import test_context_installation_service as fixture
        from asr_service import note_artifacts
        original=note_artifacts._safe_file;case=fixture.InstallationServiceTests();reads=[]
        def save(base,key='draft'):
            body=b'candidate method\n'
            manifest=json.dumps(dict(schema='asr-workspace-snapshot/1',project_id='p',research_run_id='r',files=[dict(path='method.py',sha256=hashlib.sha256(body).hexdigest(),size=len(body))])).encode()
            digest=hashlib.sha256(manifest).hexdigest();root=base.s.path.parent/'snapshots'/digest
            (root/'files').mkdir(parents=True);(root/'manifest.json').write_bytes(manifest);(root/'files/method.py').write_bytes(body)
            return base.call('save',key=key,text='候选方法仍待验证',source_sequences=[base.source['seq']],artifact_references=[dict(kind='snapshot',snapshot_sha256=digest,path='method.py')])
        def read(*args):
            self.s=case.base.s;self.writable();reads.append(args)
            return original(*args)
        with patch.object(fixture.sources.admission.fixtures.ControlResearchNotesTests,'save',save),patch.object(note_artifacts,'_safe_file',side_effect=read):
            case.setUp();self.addCleanup(case.doCleanups)
            case.test_actual_sdk_append_is_verified_once_and_original_prefix_survives()
        self.assertGreaterEqual(len(reads),14)

    def test_trial_execution_binding_changed_before_adoption_is_rejected(self):
        import test_note_artifact_sources as fixture
        from asr_service import research_notes
        from asr_service.control import ControlError
        case=fixture.NoteArtifactTests();case.setUp();self.addCleanup(case.doCleanups)
        original=research_notes._commit_operation;changed=[]
        def commit(service,token,project,run,item,**kwargs):
            if kwargs['operation']=='adopt':
                with service._connect() as db:db.execute("UPDATE asr_executions SET record='{}'")
                changed.append(True)
            return original(service,token,project,run,item,**kwargs)
        with patch.object(research_notes,'_commit_operation',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'note_artifact_unavailable'):
                case.test_failed_published_trial_file_is_verified_against_original_bytes()
        self.assertEqual(changed,[True])
        with case.service._connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM asr_note_heads').fetchone())
