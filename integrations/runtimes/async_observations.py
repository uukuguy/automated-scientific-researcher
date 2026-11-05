"""FIFO host observations. A drain receipt is not installation authorization."""
import json
import queue
import math
import time
import threading
from .capacity_policy import load_policy


class OrderedObservations:
    def __init__(self, consume, *, capacity_policy_path=None):
        self.policy=load_policy(capacity_policy_path)
        self.timeout=self.policy['limits']['observation_drain_seconds']['value']
        self.watermark=self.policy['limits']['async_log_warning_bytes']['value']
        self.consume=consume;self.queue=queue.SimpleQueue();self.condition=threading.Condition()
        self.accepted=0;self.completed=0;self.pending_bytes=0;self.peak_bytes=0
        self.closed=False;self.failures=[];self.pressure=None
        self.thread=threading.Thread(target=self._run,name='asr-observation-writer',daemon=True)
        self.thread.start()

    def submit(self, value):
        encoded=json.dumps(value,ensure_ascii=False,allow_nan=False)
        value=json.loads(encoded);size=len(encoded.encode())
        with self.condition:
            if self.closed:raise ValueError('observation_queue_closed')
            self.accepted+=1;self.pending_bytes+=size
            self.peak_bytes=max(self.peak_bytes,self.pending_bytes)
            if self.pending_bytes>self.watermark and self.pressure is None:
                self.pressure=dict(limit_name='async_log_warning_bytes',configured=self.watermark,
                                   observed=self.pending_bytes,unit='bytes',action='record_pressure_continue')
            self.queue.put((self.accepted,value,size))

    def _run(self):
        while True:
            item=self.queue.get()
            if item is None:return
            sequence,value,size=item
            try:self.consume(value)
            except Exception:
                # Preserve the failure without leaking provider/credential diagnostics.
                with self.condition:self.failures.append(dict(sequence=sequence,reason='observation_record_failed'))
            finally:
                with self.condition:
                    self.completed=sequence;self.pending_bytes-=size;self.condition.notify_all()

    def barrier(self, *, timeout=None):
        timeout=self.timeout if timeout is None else timeout
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<0:raise ValueError('invalid_observation_drain_timeout')
        began=time.monotonic()
        with self.condition:
            target=self.accepted
            drained=self.condition.wait_for(lambda:self.completed>=target,timeout=timeout)
            return dict(schema='asr-observation-drain/1',drained=drained,accepted=target,completed=self.completed,
                pending=max(0,target-self.completed),wait_requested=timeout>0,limit_exceeded=timeout>0 and not drained,failures=list(self.failures),pressure=self.pressure,
                peak_pending_bytes=self.peak_bytes,limit_name='observation_drain_seconds',configured=timeout,unit='seconds',
                capacity_policy_sha256=self.policy['sha256'],elapsed_seconds=time.monotonic()-began,research_terminated=False,
                recovery='未排空时保留原始事件与在途执行，延迟安装，不授予压缩或重试权限。')

    def close(self, *, timeout=None):
        with self.condition:
            if not self.closed:self.closed=True;self.queue.put(None)
        return self.barrier(timeout=timeout)
