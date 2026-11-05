"""Ordered asynchronous communication capture; completion is explicit, never inferred."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import threading

from .capacity_policy import load_policy


class AsyncEventRecorder:
    """Producers enqueue immutable JSON; only close waits for disk finalization.

    The buffer watermark reports pressure, it does not silently drop events or
    stop research. A stalled writer may still grow memory: this is not an OS
    memory-isolation guarantee. Native originals remain the recovery source.
    """
    def __init__(self, path, *, capacity_policy_path=None, sync=os.fsync, write=None):
        self.path=Path(path)
        self.policy=load_policy(capacity_policy_path)
        self.watermark=self.policy['limits']['async_log_warning_bytes']['value']
        self.stream=self.path.open('x')
        self.append=write or self.stream.write
        self.sync=sync;self.accepted=0;self.written=0;self.pending_bytes=0
        self.peak_bytes=0;self.pressure=None;self.failures=[];self.receipt=None
        self.closed=False;self.lock=threading.Lock();self.queue=queue.SimpleQueue()
        self.thread=threading.Thread(target=self._write,name='asr-event-writer',daemon=True)
        try:
            self.path.with_suffix('.recording.json').write_text(json.dumps(dict(schema='asr-event-recording/1',status='recording',durability_verified=False,capacity_policy_sha256=self.policy['sha256']))+'\n')
        except OSError:
            self.stream.close();raise
        self.thread.start()

    def __enter__(self):return self

    def __call__(self,event):
        with self.lock:
            if self.closed:raise ValueError('event_recorder_closed')
            sequence=self.accepted+1
            record=dict(schema='asr-recorded-runtime-event/1',sequence=sequence,
                        recorded_at=datetime.now(timezone.utc).isoformat(),event=event)
            line=json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n'
            size=len(line.encode())
            self.accepted=sequence;self.pending_bytes+=size
            self.peak_bytes=max(self.peak_bytes,self.pending_bytes)
            if self.pending_bytes>self.watermark and self.pressure is None:
                self.pressure=dict(limit_name='async_log_warning_bytes',configured=self.watermark,
                    observed=self.pending_bytes,unit='bytes',sequence=sequence,action='record_pressure_continue',
                    recovery='检查异步写入器；保留原生日志与活动前缀，不取消研究或自动提高策略。')
            self.queue.put((line,size,sequence))

    def _write(self):
        while True:
            item=self.queue.get()
            if item is None:break
            line,size,sequence=item
            try:
                self.append(line)
                self.written+=1
            except (OSError,ValueError):
                self.failures.append(dict(reason='event_write_failed',sequence=sequence,
                    sha256=hashlib.sha256(line.encode()).hexdigest()))
            finally:
                with self.lock:self.pending_bytes-=size
        try:
            self.stream.flush();self.sync(self.stream.fileno())
        except (OSError,ValueError):self.failures.append(dict(reason='event_sync_failed'))
        finally:
            try:self.stream.close()
            except (OSError,ValueError):self.failures.append(dict(reason='event_close_failed'))

    def close(self):
        with self.lock:
            if not self.closed:self.closed=True;self.queue.put(None)
        self.thread.join()
        if self.receipt is None:
            self.receipt=dict(schema='asr-event-recording/1',status='incomplete' if self.failures else 'complete',
                accepted=self.accepted,written=self.written,failures=self.failures,
                durability_verified=not self.failures,pressure=self.pressure,peak_pending_bytes=self.peak_bytes,
                capacity_policy_sha256=self.policy['sha256'],research_terminated=False,
                recovery='不完整时核对受限原生日志，显式保留缺口；不得宣称完整归档或自动重跑科研实验。')
            self.path.with_suffix('.recording.json').write_text(json.dumps(self.receipt,ensure_ascii=False,indent=2)+'\n')
        return self.receipt

    def __exit__(self,*exc):self.close()
