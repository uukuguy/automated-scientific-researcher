import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from asr_service.control import ControlError
from asr_service.note_io import PreparedStore
import test_control_research_notes as fixture


class NoteReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.ControlResearchNotesTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.s=self.case.s

    def audit(self,key='audit',**kwargs):
        return self.s.audit_research_notes('human-secret','p','r',subject='lead',idempotency_key=key,**kwargs)

    def test_actual_exit_after_file_save_is_reported_without_adoption(self):
        code='''import json,os,sys
from asr_service.control import ControlService
import asr_service.research_notes as notes
service=ControlService(sys.argv[1],credentials=json.loads(sys.argv[2]))
notes._commit_operation=lambda *args,**kwargs:os._exit(73)
service.research_note('lead','p','r',operation='save',idempotency_key='crash',text='保留未登记草稿',source_sequences=[])
'''
        child=subprocess.run([sys.executable,'-c',code,str(self.s.path),json.dumps(self.s.credentials)],capture_output=True,text=True)
        self.assertEqual(child.returncode,73,child.stderr)
        result=self.audit();self.assertEqual(result['status'],'inspected')
        orphan=next(row for row in result['entries'] if row['registration']=='unregistered')
        self.assertEqual(orphan['integrity'],'verified');self.assertFalse(orphan['current_accepted'])
        self.assertEqual(self.case.call('history_read',revision=orphan['revision'])['note']['text'],'保留未登记草稿')
        self.assertEqual(self.case.call('read')['status'],'empty')
        self.assertEqual(self.audit(),result)

    def test_registered_adopted_missing_corrupt_and_temporary_are_distinct(self):
        first=self.case.save()
        self.case.call('adopt',revision=first['revision'],expected_note=None)
        second=self.case.call('save',key='second',text='未采纳')
        store=PreparedStore(self.s,'p','r','lead').store
        (store.directory/(first['revision']+'.json')).unlink()
        (store.directory/(second['revision']+'.json')).write_text('corrupt')
        (store.directory/'.note-interrupted').write_text('partial')
        result=self.audit();rows={r['file']:r for r in result['entries']}
        self.assertEqual(rows[first['revision']+'.json']['integrity'],'missing')
        self.assertTrue(rows[first['revision']+'.json']['current_accepted'])
        self.assertEqual(rows[second['revision']+'.json']['integrity'],'invalid')
        self.assertEqual(rows['.note-interrupted']['integrity'],'unpublished_temporary')
        self.assertTrue((store.directory/'.note-interrupted').exists())
        self.assertEqual(result['accepted_revision'],first['revision'])

    def test_reads_are_outside_write_transaction(self):
        from asr_context.notes import NoteStore
        self.case.save();original=NoteStore.read
        def read(*args,**kwargs):
            with self.s._connect() as db:
                db.execute('PRAGMA busy_timeout=50');db.execute('BEGIN IMMEDIATE');db.rollback()
            return original(*args,**kwargs)
        with patch.object(NoteStore,'read',read):self.assertEqual(self.audit()['status'],'inspected')

    def test_changed_file_before_commit_is_durably_deferred(self):
        from asr_service import note_reconciliation as audit
        draft=self.case.save();store=PreparedStore(self.s,'p','r','lead').store;original=audit._commit
        def commit(*args,**kwargs):
            (store.directory/(draft['revision']+'.json')).write_text('changed')
            return original(*args,**kwargs)
        with patch.object(audit,'_commit',side_effect=commit):result=self.audit()
        self.assertEqual(result['status'],'deferred');self.assertEqual(result['reason'],'note_audit_sources_changed')
        self.assertEqual(result,self.audit())

    def test_new_save_during_scan_is_deferred_without_reclassifying(self):
        from asr_service import note_reconciliation as audit
        self.case.save();original=audit._commit
        def commit(*args,**kwargs):
            self.case.call('save',key='during-audit',text='新草稿')
            return original(*args,**kwargs)
        with patch.object(audit,'_commit',side_effect=commit):result=self.audit()
        self.assertEqual(result['status'],'deferred');self.assertEqual(result['reason'],'note_audit_ledger_changed')
        self.assertEqual(self.case.call('read')['status'],'empty')

    def test_scope_and_host_permissions_are_enforced(self):
        self.case.save()
        result=self.s.audit_research_notes('human-secret','p','r',subject='lead2',idempotency_key='other')
        self.assertEqual(result['entries'],[])
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.s.audit_research_notes('lead','p','r',subject='lead',idempotency_key='no-host-authority')

    def test_symlink_is_reported_without_reading_target(self):
        draft=self.case.save();store=PreparedStore(self.s,'p','r','lead').store
        path=store.directory/(draft['revision']+'.json');path.unlink();path.symlink_to('/does-not-exist/private')
        row=self.audit()['entries'][0];self.assertEqual(row['integrity'],'unsafe_file');self.assertTrue(path.is_symlink())

    def test_replay_does_not_rescan_changed_originals(self):
        from asr_service import note_reconciliation as audit
        self.case.save();result=self.audit()
        with patch.object(audit,'_scan',side_effect=AssertionError('historical receipt only')):self.assertEqual(result,self.audit())

    def test_revoked_member_before_commit_prevents_report(self):
        from asr_service import note_reconciliation as audit
        original=audit._commit
        def commit(*args,**kwargs):
            with self.s._connect() as db:
                row=db.execute("SELECT record FROM asr_organization WHERE kind='member' AND entity='lead2' ORDER BY seq DESC LIMIT 1").fetchone()
            member=json.loads(row[0])
            self.s.change_organization('human-secret','p','r',kind='member',entity_id='lead2',expected_revision=member['revision'],idempotency_key='disable',document=dict(member['document'],enabled=False))
            return original(*args,**kwargs)
        with patch.object(audit,'_commit',side_effect=commit):
            with self.assertRaisesRegex(ControlError,'forbidden'):
                self.s.audit_research_notes('human-secret','p','r',subject='lead2',idempotency_key='audit')

    def test_inspection_never_creates_note_directories(self):
        from asr_context.notes import NoteStore
        missing=self.s.path.parent/'never-created'
        NoteStore(missing,scope='test',create=False)
        self.assertFalse(missing.exists())
        with patch.object(Path,'mkdir',side_effect=AssertionError('inspection cannot create directories')):
            self.assertEqual(self.audit()['entries'],[])
        self.case.save()
        with patch.object(Path,'mkdir',side_effect=AssertionError('inspection cannot create directories')):
            self.assertEqual(self.audit(key='existing')['status'],'inspected')
