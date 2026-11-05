import json
import unittest
from unittest.mock import patch
import asr_service.context_sources as sources
from asr_service.control import ControlError
import test_context_sources as fixture


class ContextMaterialIOTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.ContextSourcesTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.s=self.case.s;self.case.register()

    def test_preparation_rebuilds_materials_without_writer_lock(self):
        original=sources.materials
        def rebuild(*args,**kwargs):
            with self.s._connect() as db:
                db.execute('PRAGMA busy_timeout=50');db.execute('BEGIN IMMEDIATE');db.rollback()
            return original(*args,**kwargs)
        with patch.object(sources,'materials',side_effect=rebuild) as calls:self.case.prepared()
        self.assertEqual(calls.call_count,1)

    def test_source_record_changed_after_rebuild_cannot_commit(self):
        original=sources.materials
        def rebuild(*args,**kwargs):
            result=original(*args,**kwargs)
            with self.s._connect() as db:
                row=db.execute("SELECT record FROM asr_requests WHERE scope LIKE 'context-source:%'").fetchone()
                record=json.loads(row[0]);record['reader']['keep_recent_groups']=2
                db.execute("UPDATE asr_requests SET record=? WHERE scope LIKE 'context-source:%'",(json.dumps(record),))
            return result
        with patch.object(sources,'materials',side_effect=rebuild):
            with self.assertRaisesRegex(ControlError,'context_source_changed'):self.case.prepared()

    def test_file_changed_during_rebuild_cannot_commit(self):
        original=sources.materials
        def rebuild(*args,**kwargs):
            result=original(*args,**kwargs)
            with self.case.path.open('a') as stream:stream.write('\n')
            return result
        with patch.object(sources,'materials',side_effect=rebuild):
            with self.assertRaisesRegex(ControlError,'context_source_changed'):self.case.prepared()
