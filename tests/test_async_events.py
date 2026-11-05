import json
from pathlib import Path
import tempfile
import threading
import unittest


class AsyncEventTests(unittest.TestCase):
    def test_slow_disk_does_not_block_submission_and_close_drains_in_order(self):
        from integrations.runtimes.async_events import AsyncEventRecorder
        started=threading.Event();release=threading.Event()
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'events.jsonl'
            def slow_sync(fd): started.set();self.assertTrue(release.wait(3))
            with AsyncEventRecorder(path, sync=slow_sync) as recorder:
                event={'type':'message','text':'原始内容'}
                recorder(event);event['text']='mutated'
                recorder({'type':'end'})
                self.assertEqual(recorder.accepted,2)
                release.set()
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r['sequence'] for r in rows],[1,2])
            self.assertEqual(rows[0]['event']['text'],'原始内容')
            self.assertEqual(recorder.receipt['status'],'complete')
            self.assertTrue(started.is_set())

    def test_write_failure_is_explicit_without_raising_in_producer(self):
        from integrations.runtimes.async_events import AsyncEventRecorder
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'events.jsonl'
            def bad_sync(fd): raise OSError('private diagnostic')
            with AsyncEventRecorder(path,sync=bad_sync) as recorder:
                recorder({'type':'end'})
            receipt=json.loads(path.with_suffix('.recording.json').read_text())
            self.assertEqual(receipt['status'],'incomplete')
            self.assertFalse(receipt['durability_verified'])
            self.assertNotIn('private diagnostic',json.dumps(receipt))
            self.assertFalse(receipt['research_terminated'])

    def test_slow_append_and_pressure_warning_never_block_or_drop(self):
        from integrations.runtimes.async_events import AsyncEventRecorder
        from integrations.runtimes.capacity_policy import load_policy
        started=threading.Event();release=threading.Event();lines=[]
        with tempfile.TemporaryDirectory() as root:
            policy=load_policy();del policy['sha256']
            policy['limits']['async_log_warning_bytes']['value']=100
            config=Path(root)/'policy.json';config.write_text(json.dumps(policy))
            def slow_write(line):
                started.set();self.assertTrue(release.wait(3));lines.append(line)
            with AsyncEventRecorder(Path(root)/'events.jsonl',capacity_policy_path=config,write=slow_write) as recorder:
                recorder({'text':'first'})
                self.assertTrue(started.wait(1))
                recorder({'text':'second'})
                self.assertEqual(recorder.accepted,2)
                release.set()
            self.assertEqual(len(lines),2)
            self.assertEqual(recorder.receipt['pressure']['action'],'record_pressure_continue')

    def test_failed_append_marks_exact_gap_and_does_not_stop_producer(self):
        from integrations.runtimes.async_events import AsyncEventRecorder
        with tempfile.TemporaryDirectory() as root:
            def bad_write(line):raise OSError('secret diagnostic')
            with AsyncEventRecorder(Path(root)/'events.jsonl',write=bad_write) as recorder:
                recorder({'type':'end'})
            self.assertEqual(recorder.receipt['failures'][0]['sequence'],1)
            self.assertEqual(recorder.receipt['written'],0)
            self.assertEqual(recorder.receipt['status'],'incomplete')

    def test_stalled_writer_returns_pending_receipt_and_can_be_reconciled(self):
        from integrations.runtimes.async_events import AsyncEventRecorder
        release=threading.Event();entered=threading.Event()
        with tempfile.TemporaryDirectory() as root:
            def slow_write(line):entered.set();release.wait(3)
            recorder=AsyncEventRecorder(Path(root)/'events.jsonl',write=slow_write)
            recorder({'type':'end'});self.assertTrue(entered.wait(1))
            try:
                result=recorder.close(timeout=.01)
                self.assertEqual(result['status'],'draining')
                self.assertFalse(result['durability_verified'])
                self.assertTrue(recorder.thread.is_alive())
                self.assertFalse(result['research_terminated'])
            finally:release.set()
            result=recorder.close(timeout=1)
            self.assertEqual(result['status'],'complete')
