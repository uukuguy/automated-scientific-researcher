import json
import unittest
from unittest.mock import patch
from asr_service.control import ControlError
import asr_service.context_installation as installation
import test_context_installation_service as fixture


class CompilationIOTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.InstallationServiceTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.s=self.case.s

    def unlocked(self,original):
        def call(*args,**kwargs):
            with self.s._connect() as db:
                db.execute('PRAGMA busy_timeout=50');db.execute('BEGIN IMMEDIATE');db.rollback()
            return original(*args,**kwargs)
        return call

    def test_compilation_and_application_validation_release_writer_through_sdk_install(self):
        with (patch.object(installation,'compile_plan',side_effect=self.unlocked(installation.compile_plan)) as compiler,
              patch.object(installation,'application_plan',side_effect=self.unlocked(installation.application_plan)) as application):
            self.case.test_actual_sdk_append_is_verified_once_and_original_prefix_survives()
        self.assertEqual(compiler.call_count,2)
        self.assertEqual(application.call_count,1)

    def authorize(self):
        stage=self.case.staged();ids,cursor=self.case.live()
        return ids,cursor,dict(stage_id=stage['stage_id'],observation=cursor,tokens_before=1000)

    def assert_no_ticket(self):
        with self.s._connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM asr_requests WHERE scope LIKE 'context-ticket:%'").fetchone())

    def test_control_change_during_application_check_rejects_old_state(self):
        ids,cursor,args=self.authorize();original=installation.application_plan
        def check(*args,**kwargs):
            result=original(*args,**kwargs)
            state=self.s.get_run('human-secret','p','r')
            self.s.command('human-secret','p','r','pause',expected_revision=state['control_revision'],idempotency_key='changed-while-compiling')
            return result
        with patch.object(installation,'application_plan',side_effect=check):
            with self.assertRaisesRegex(ControlError,'context_note_sources_changed|research_state_changed'):
                self.s.authorize_context_installation('human-secret','p','r',**ids,**args)
        self.assert_no_ticket()

    def test_native_file_change_during_compilation_cannot_issue_ticket(self):
        ids,cursor,args=self.authorize();original=installation.compile_plan
        def compile(*args,**kwargs):
            result=original(*args,**kwargs)
            with self.case.path.open('a') as stream:stream.write('\n')
            return result
        with patch.object(installation,'compile_plan',side_effect=compile):
            with self.assertRaisesRegex(ControlError,'context_source_changed'):
                self.s.authorize_context_installation('human-secret','p','r',**ids,**args)
        self.assert_no_ticket()

    def test_changed_staging_receipt_after_compilation_cannot_issue_ticket(self):
        ids,cursor,args=self.authorize();original=installation._authorize
        def commit(*arguments,**keywords):
            with self.s._connect() as db:
                row=db.execute("SELECT record FROM asr_requests WHERE scope LIKE 'context-installation:%'").fetchone()
                record=json.loads(row[0]);record['bundle'][3]['text']='changed'
                db.execute("UPDATE asr_requests SET record=? WHERE scope LIKE 'context-installation:%'",(json.dumps(record),))
            return original(*arguments,**keywords)
        with patch.object(installation,'_authorize',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'context_compilation_inputs_changed'):
                self.s.authorize_context_installation('human-secret','p','r',**ids,**args)
        self.assert_no_ticket()

    def test_stage_rechecks_original_admission_after_compilation(self):
        original=installation._stage
        def commit(*arguments,**keywords):
            with self.s._connect() as db:
                row=db.execute("SELECT payload FROM asr_requests WHERE scope LIKE 'context-admission:%'").fetchone()
                payload=json.loads(row[0]);payload[3]['text']='changed'
                db.execute("UPDATE asr_requests SET payload=? WHERE scope LIKE 'context-admission:%'",(json.dumps(payload),))
            return original(*arguments,**keywords)
        with patch.object(installation,'_stage',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'context_compilation_inputs_changed'):self.case.staged()
        with self.s._connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM asr_requests WHERE scope LIKE 'context-installation:%'").fetchone())

    def test_process_exit_during_compilation_cannot_issue_ticket(self):
        from integrations.runtimes.process import verify_process_exit
        ids,cursor,args=self.authorize();original=installation.compile_plan
        def compile(*args,**kwargs):
            result=original(*args,**kwargs)
            state=self.s.get_run('human-secret','p','r')
            session=next(s for s in state['runtime_sessions'] if s['session_id']==ids['session_id'])
            verify_process_exit(session['process_identity'],terminate=True)
            return result
        with patch.object(installation,'compile_plan',side_effect=compile):
            with self.assertRaisesRegex(ControlError,'context_process_unavailable'):
                self.s.authorize_context_installation('human-secret','p','r',**ids,**args)
        self.assert_no_ticket()

    def test_stage_replay_does_not_compile_again(self):
        result=self.case.staged()
        with patch.object(installation,'compile_plan',side_effect=AssertionError('unexpected compilation')):
            self.assertEqual(result,self.case.staged())
