"""Resource diagnostics preserve task state and bound trusted CLI buffers."""
import sys
import unittest
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from asr_supervisor.resources import bounded_command,LimitViolation
from asr_supervisor.supervisor import publication_inventory


class CommandLimitTests(unittest.TestCase):
    def test_managed_publication_caps_keep_all_raw_pending_material(self):
        for mode in ('files','bytes'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as root:
                pending=Path(root)
                if mode=='files':
                    for index in range(101):(pending/str(index)).write_bytes(b'')
                else:
                    with (pending/'large.bin').open('wb') as stream:stream.truncate(100*1024*1024+1)
                before={path.name:path.stat().st_size for path in pending.iterdir()}
                with self.assertRaises(LimitViolation) as raised:publication_inventory(pending)
                detail=raised.exception.details
                self.assertEqual(detail['limit']['unit'],mode)
                self.assertEqual(detail['pending_path'],str(pending.resolve()))
                self.assertGreater(detail['observed']['value'],detail['limit']['configured'])
                self.assertTrue(detail['task_retained'])
                self.assertEqual({path.name:path.stat().st_size for path in pending.iterdir()},before)

    def test_parent_exit_does_not_leave_descendant_holding_output_open(self):
        with tempfile.TemporaryDirectory() as root:
            pidfile=Path(root)/'child.pid'
            child='import os,time;from pathlib import Path;Path('+repr(str(pidfile))+').write_text(str(os.getpid()));time.sleep(20)'
            parent='import os,subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);os._exit(0)'
            child_pid=None
            try:
                with self.assertRaises(LimitViolation):bounded_command([sys.executable,'-c',parent],component='test',operation='inspect',timeout=.3)
                child_pid=int(pidfile.read_text())
                deadline=time.monotonic()+1
                while time.monotonic()<deadline:
                    result=subprocess.run(['ps','-o','stat=','-p',str(child_pid)],capture_output=True,text=True)
                    if result.returncode or not result.stdout.strip() or result.stdout.strip().startswith('Z'):break
                    time.sleep(.01)
                else:self.fail('owned descendant survived the failed command deadline')
            finally:
                if child_pid is None and pidfile.exists():child_pid=int(pidfile.read_text())
                if child_pid:
                    try:os.kill(child_pid,signal.SIGKILL)
                    except ProcessLookupError:pass

    def test_output_ceiling_is_live_and_diagnostic_is_recoverable(self):
        with self.assertRaises(LimitViolation) as raised:
            bounded_command([sys.executable,'-c','import sys;sys.stdout.buffer.write(b"x"*2000000)'],
                            component='test',operation='inspect',max_bytes=1024,timeout=2)
        event=raised.exception.diagnostic
        self.assertEqual(event['limit']['configured'],1024)
        self.assertGreater(event['observed']['value'],1024)
        self.assertTrue(event['task_retained'])
        self.assertEqual(event['action'],'cli_aborted_execution_unknown')
        self.assertNotIn('x'*100,str(raised.exception))

    def test_deadline_kills_only_owned_cli_and_keeps_execution_unknown(self):
        with self.assertRaises(LimitViolation) as raised:
            bounded_command([sys.executable,'-c','import time;time.sleep(20)'],
                            component='test',operation='create',max_bytes=1024,timeout=.05)
        self.assertEqual(raised.exception.diagnostic['limit']['unit'],'seconds')
        self.assertEqual(raised.exception.diagnostic['operation'],'create')
        self.assertGreaterEqual(raised.exception.diagnostic['observed']['value'],.05)

    def test_small_nonzero_metadata_response_is_returned_without_private_error_text(self):
        result=bounded_command([sys.executable,'-c','import sys;print("ok");sys.stderr.write("private");sys.exit(3)'],
                               component='test',operation='inspect',timeout=2)
        self.assertEqual(result.returncode,3)
        self.assertEqual(result.stdout,b'ok\n')
        self.assertEqual(result.stderr,b'private')
