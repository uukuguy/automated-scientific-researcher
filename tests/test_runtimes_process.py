"""Real local child-process reconciliation; no model/provider calls."""
import os
import signal
import subprocess
import tempfile
import unittest
from integrations.runtimes.process import identify, reconcile_process

class ProcessRecoveryTests(unittest.TestCase):
    def test_terminates_exact_live_process_and_confirms_exit(self):
        p=subprocess.Popen(['sleep','30'],start_new_session=True)
        try:
            identity=identify(p.pid)
            self.assertEqual(identity['pid'],p.pid)
            self.assertTrue(reconcile_process(identity))
            p.wait(timeout=3)
            self.assertIsNone(identify(p.pid))
        finally:
            if p.poll() is None: p.kill();p.wait()

    def test_mismatched_birth_identity_never_signals_process(self):
        p=subprocess.Popen(['sleep','30'],start_new_session=True)
        try:
            identity=identify(p.pid);identity['birth']='different'
            with self.assertRaisesRegex(RuntimeError,'identity_mismatch'): reconcile_process(identity)
            self.assertIsNone(p.poll())
        finally:
            p.kill();p.wait()

    def test_missing_identity_retains_unknown(self):
        with self.assertRaisesRegex(RuntimeError,'identity_required'): reconcile_process(None)
