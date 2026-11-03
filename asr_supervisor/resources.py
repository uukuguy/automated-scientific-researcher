"""Host-side resource diagnostics and bounded trusted metadata commands."""
import math
import os
import selectors
import signal
import subprocess
import time


def limit_event(component,code,name,configured,observed,unit,phase,action,recovery,*,kind='exact',operation=None,evidence_basis='supervisor_measurement'):
    record=dict(schema='asr-limit-event/1',component=component,code=code,
        limit=dict(name=name,configured=configured,unit=unit),observed=dict(value=observed,kind=kind),
        phase=phase,action=action,task_retained=True,recovery=recovery,evidence_basis=evidence_basis)
    if operation is not None:record['operation']=operation
    return record


class LimitViolation(ValueError):
    def __init__(self,diagnostic):
        self.code=diagnostic['code'];self.details=self.diagnostic=diagnostic
        super().__init__(self.code)


def bounded_command(argv,*,component,operation,timeout=5,max_bytes=262144):
    """Bound both streams while reading; kill/reap only this trusted CLI group.

    A CLI timeout never establishes whether Docker executed the request. Callers
    must retain its admitted task/reservation and reconcile the exact intent.
    No raw stderr, command arguments or credentials enter the diagnostic.
    """
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0 or type(max_bytes) is not int or max_bytes<1:
        raise ValueError('positive command resource limits required')
    started=time.monotonic()
    process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    selector=selectors.DefaultSelector();buffers={'stdout':bytearray(),'stderr':bytearray()};total=0
    completed=False
    def timeout_error():
        return LimitViolation(limit_event(component,'docker_operation_timeout','docker_operation_seconds',timeout,time.monotonic()-started,'seconds','docker_operation',
            'cli_aborted_execution_unknown','Retain the task and reservation; reconcile the exact container before an explicit retry.',operation=operation))
    try:
        for stream,name in ((process.stdout,'stdout'),(process.stderr,'stderr')):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        # Do not reap the group leader while descendants still hold these pipes.
        # Its unreaped PID prevents reuse before failure cleanup kills the group.
        while selector.get_map():
            elapsed=time.monotonic()-started
            if elapsed>=timeout:
                raise timeout_error()
            for key,_ in selector.select(min(.05,timeout-elapsed)):
                try:chunk=os.read(key.fileobj.fileno(),65536)
                except BlockingIOError:continue
                if not chunk:
                    selector.unregister(key.fileobj);continue
                available=max_bytes-total
                buffers[key.data].extend(chunk[:available])
                if len(chunk)>available:
                    raise LimitViolation(limit_event(component,'docker_metadata_output_limit','docker_metadata_bytes',max_bytes,total+len(chunk),'bytes','docker_operation',
                        'cli_aborted_execution_unknown','Retain the task; inspect its exact intent and use a reviewed larger metadata limit if needed.',kind='at_least',operation=operation))
                total+=len(chunk)
        try:returncode=process.wait(timeout=max(0,timeout-(time.monotonic()-started)))
        except subprocess.TimeoutExpired:raise timeout_error() from None
        completed=True
        return subprocess.CompletedProcess(argv,returncode,bytes(buffers['stdout']),bytes(buffers['stderr']))
    finally:
        selector.close()
        if not completed:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        process.wait(timeout=1)
        process.stdout.close();process.stderr.close()
