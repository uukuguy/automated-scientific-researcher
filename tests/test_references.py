import tempfile
import unittest
from pathlib import Path
from asr_service.references import ReferenceStore, ReferenceError


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.db'
        self.store = ReferenceStore(self.path)

    def test_verified_content_and_immutable_identity(self):
        ref = self.store.register('p', 'problem', {'case_sha256': 'a' * 64})
        self.assertEqual(self.store.get('p', 'problem', ref), {'case_sha256': 'a' * 64})
        self.assertEqual(self.store.register('p', 'problem', {'case_sha256': 'a' * 64}), ref)
        changed = self.store.register('p', 'problem', {'case_sha256': 'b' * 64})
        self.assertNotEqual(changed, ref)
        self.assertEqual(ReferenceStore(self.path).get('p', 'problem', ref)['case_sha256'], 'a' * 64)

    def test_scope_and_kind_are_checked(self):
        ref = self.store.register('p', 'evaluation', {'protocol': 'calibration'})
        for project, kind in [('other', 'evaluation'), ('p', 'problem')]:
            with self.assertRaises(ReferenceError):
                self.store.get(project, kind, ref)
        with self.assertRaises(ReferenceError):
            self.store.register('p', 'unknown', {})
        with self.assertRaises(ReferenceError):
            self.store.register('p', 'problem', {'value': float('nan')})

    def test_corruption_is_not_accepted_as_frozen_reference(self):
        import sqlite3
        ref = self.store.register('p', 'problem', {'case': 'original'})
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE asr_references SET document='{}'")
        with self.assertRaises(ReferenceError):
            self.store.get('p', 'problem', ref)
