import os
from pathlib import Path
import unittest
from unittest.mock import patch

from asr_service.control import ControlError


class ContextIOTests(unittest.TestCase):
    def setUp(self):
        import test_context_sources as fixture
        self.fixture=fixture.ContextSourcesTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.s=self.fixture.s;self.path=self.fixture.path.resolve()
        self.fixture.register()

    def unlocked(self,original):
        def observe(arguments):
            with self.s._connect() as db:
                db.execute('PRAGMA busy_timeout=50')
                db.execute('BEGIN IMMEDIATE');db.rollback()
            return original(arguments)
        return observe

    def test_preparation_and_admission_project_without_write_lock(self):
        import asr_service.context_sources as sources
        with patch.object(sources,'_observe',side_effect=self.unlocked(sources._observe)) as observed:
            prepared=self.fixture.prepared()
            bundle=self.fixture.bundle(prepared)
            result=self.fixture.admit(prepared,bundle)
        self.assertEqual(result['status'],'admitted');self.assertGreaterEqual(observed.call_count,2)

    def test_file_write_with_restored_size_and_mtime_rejects_detached_read(self):
        import asr_service.context_sources as sources
        original=sources._observe
        def observe(arguments):
            result=original(arguments);before=self.path.stat()
            data=self.path.read_bytes();self.path.write_bytes(data.replace(b'question',b'QUESTION') if b'question' in data else data.replace(b'"user"',b'"tool"'))
            os.utime(self.path,ns=(before.st_atime_ns,before.st_mtime_ns))
            return result
        with patch.object(sources,'_observe',side_effect=observe):
            with self.assertRaisesRegex(ControlError,'context_source_changed'):self.fixture.prepared()
        with self.s._connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM asr_requests WHERE request_key='prep-source'").fetchone())

    def test_changed_membership_between_read_and_commit_is_not_accepted(self):
        import asr_service.context_admission as admission
        original=admission._prepare
        def commit(*args,**kwargs):
            with self.s._connect() as db:
                row=db.execute("SELECT record FROM asr_organization WHERE project='p' AND run='r' AND kind='member' AND entity='lead' ORDER BY seq DESC LIMIT 1").fetchone()
            import json
            member=json.loads(row[0]);document=dict(member['document'],enabled=False)
            self.s.change_organization('human-secret','p','r',kind='member',entity_id='lead',expected_revision=member['revision'],idempotency_key='disable-during-parse',document=document)
            return original(*args,**kwargs)
        with patch.object(admission,'_prepare',side_effect=commit):
            with self.assertRaises(ControlError):self.fixture.prepared()

    def test_replay_does_not_read_or_require_original_again(self):
        prepared=self.fixture.prepared();self.path.unlink()
        self.assertEqual(prepared,self.fixture.prepared())

    def test_full_native_installation_and_recovery_project_without_write_lock(self):
        import test_context_installation_service as fixture
        import asr_service.context_installation as installation
        import asr_service.context_sources as sources
        for method in ('test_actual_sdk_append_is_verified_once_and_original_prefix_survives',
                       'test_exited_write_can_be_reconciled_but_cannot_grant_current_admission'):
            case=fixture.InstallationServiceTests();case.setUp()
            old_service=self.s;self.s=case.s
            try:
                with (patch.object(installation,'_observe',side_effect=self.unlocked(installation._observe)) as live,
                      patch.object(sources,'_observe',side_effect=self.unlocked(sources._observe))):
                    getattr(case,method)()
                self.assertGreaterEqual(live.call_count,2)
            finally:self.s=old_service;case.doCleanups()

    def test_file_change_after_detached_read_is_rejected_at_commit(self):
        import asr_service.context_admission as admission
        original=admission._prepare
        def commit(*args,**kwargs):
            self.path.write_bytes(self.path.read_bytes()+b'\n')
            return original(*args,**kwargs)
        with patch.object(admission,'_prepare',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'context_source_changed'):self.fixture.prepared()

    def test_process_exit_during_projection_cannot_receive_installation_ticket(self):
        import test_context_installation_service as fixture
        import asr_service.context_installation as installation
        from integrations.runtimes.process import verify_process_exit
        case=fixture.InstallationServiceTests();case.setUp();self.addCleanup(case.doCleanups)
        stage=case.staged();ids,cursor=case.live()
        original=installation._observe
        def observe(reader):
            result=original(reader)
            state=case.s.get_run('human-secret','p','r')
            session=next(s for s in state['runtime_sessions'] if s['session_id']==ids['session_id'])
            verify_process_exit(session['process_identity'],terminate=True)
            return result
        with patch.object(installation,'_observe',side_effect=observe):
            with self.assertRaisesRegex(ControlError,'context_process_unavailable'):
                case.s.authorize_context_installation('human-secret','p','r',**ids,stage_id=stage['stage_id'],observation=cursor,tokens_before=1000)
        state=case.s.get_run('human-secret','p','r')
        session=next(s for s in state['runtime_sessions'] if s['session_id']==ids['session_id'])
        self.assertNotIn('pending_installation',session['native_context'])

    def test_missing_source_is_a_control_rejection_not_an_unhandled_io_error(self):
        self.path.unlink()
        with self.assertRaisesRegex(ControlError,'context_source_changed'):self.fixture.prepared()

    def test_deferred_admission_cannot_be_staged_or_trigger_another_projection(self):
        prepared=self.fixture.prepared();bundle=self.fixture.bundle(prepared)
        self.path.write_bytes(self.path.read_bytes()+b'\n')
        result=self.fixture.admit(prepared,bundle)
        self.assertEqual(result['status'],'deferred')
        with patch('asr_service.context_sources._observe',side_effect=AssertionError('unexpected projection')):
            with self.assertRaisesRegex(ControlError,'context_admission_required'):
                self.s.stage_context_installation('human-secret','p','r',subject='lead',admission_id='admit',first_kept_entry_id='a',idempotency_key='cannot-stage')
