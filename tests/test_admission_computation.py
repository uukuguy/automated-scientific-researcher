import json
import unittest
from unittest.mock import patch
import asr_service.context_admission as admission
from asr_service.control import ControlError
import test_context_admission as fixture


class AdmissionComputationTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.ContextAdmissionTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.s=self.case.s;self.prepared=self.case.prepare();self.bundle=self.case.bundle(self.prepared)

    def admit(self):return self.case.admit(self.prepared,self.bundle)

    def test_review_computation_allows_another_control_writer(self):
        original=admission.plan
        def compute(*args,**kwargs):
            with self.s._connect() as db:
                db.execute('PRAGMA busy_timeout=50');db.execute('BEGIN IMMEDIATE');db.rollback()
            return original(*args,**kwargs)
        with patch.object(admission,'plan',side_effect=compute):self.assertEqual(self.admit()['status'],'admitted')

    def test_changed_control_during_review_is_durably_deferred(self):
        original=admission.plan
        def compute(*args,**kwargs):
            result=original(*args,**kwargs)
            state=self.s.get_run('human-secret','p','r')
            self.s.command('human-secret','p','r','pause',expected_revision=state['control_revision'],idempotency_key='during-review')
            return result
        with patch.object(admission,'plan',side_effect=compute):result=self.admit()
        self.assertEqual(result['status'],'deferred')
        with patch.object(admission,'plan',side_effect=AssertionError('must replay')):self.assertEqual(result,self.admit())

    def test_changed_preparation_before_commit_cannot_reuse_review(self):
        original=admission._admit
        def commit(*args,**kwargs):
            with self.s._connect() as db:
                row=db.execute("SELECT record FROM asr_requests WHERE scope LIKE 'context-prepare:%'").fetchone()
                record=json.loads(row[0]);record['materials'][0]['text']='changed'
                db.execute("UPDATE asr_requests SET record=? WHERE scope LIKE 'context-prepare:%'",(json.dumps(record),))
            return original(*args,**kwargs)
        with patch.object(admission,'_admit',side_effect=commit):result=self.admit()
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result['check']['reason'],'context_admission_inputs_changed')

    def test_changed_request_after_review_cannot_be_committed(self):
        original=admission._admit
        def commit(*args,**kwargs):
            kwargs['candidate']['text']='changed after verification'
            return original(*args,**kwargs)
        with patch.object(admission,'_admit',side_effect=commit):result=self.admit()
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result['check']['reason'],'context_admission_inputs_changed')

    def test_reviewer_revoked_during_review_cannot_support_admission(self):
        original=admission.plan
        def compute(*args,**kwargs):
            result=original(*args,**kwargs)
            with self.s._connect() as db:
                row=db.execute("SELECT record FROM asr_organization WHERE kind='member' AND entity='lead2' ORDER BY seq DESC LIMIT 1").fetchone()
            record=json.loads(row[0])
            self.s.change_organization('human-secret','p','r',kind='member',entity_id='lead2',expected_revision=record['revision'],idempotency_key='disable-reviewer',document=dict(record['document'],enabled=False))
            return result
        with patch.object(admission,'plan',side_effect=compute):
            with self.assertRaisesRegex(ControlError,'forbidden'):self.admit()
        with self.s._connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM asr_requests WHERE scope LIKE 'context-admission:%'").fetchone())

    def test_review_session_changed_during_computation_is_rejected(self):
        original=admission.plan
        def compute(*args,**kwargs):
            result=original(*args,**kwargs)
            with self.s._connect() as db:
                row=db.execute('SELECT record FROM asr_runtime_sessions WHERE session_id=?',(self.bundle['reviewer_session'],)).fetchone()
                record=json.loads(row[0]);record['execution_exited']=False
                db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(json.dumps(record),self.bundle['reviewer_session']))
            return result
        with patch.object(admission,'plan',side_effect=compute):
            with self.assertRaisesRegex(ControlError,'context_review_session_unavailable'):self.admit()

    def test_successful_replay_skips_review_computation(self):
        result=self.admit()
        with patch.object(admission,'plan',side_effect=AssertionError('must replay')):self.assertEqual(result,self.admit())

    def test_new_unsettled_execution_during_review_invalidates_state_stamp(self):
        original=admission.plan
        def compute(*args,**kwargs):
            result=original(*args,**kwargs)
            with self.s._connect() as db:
                db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)',('new','p','r','trial-new','attempt-new','running','{}'))
            return result
        with patch.object(admission,'plan',side_effect=compute):result=self.admit()
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result['check']['reason'],'research_state_changed')

    def test_invalid_reviewer_does_not_trigger_expensive_review(self):
        self.bundle['reviewer_session']=self.bundle['author_session']
        with patch.object(admission,'plan',side_effect=AssertionError('must reject before computation')):
            with self.assertRaises(ControlError):self.admit()
