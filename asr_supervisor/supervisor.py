"""Execute only admitted work; preserve unknown execution and reconcile before settlement."""
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import time
from powerflow_lab.runner import canonical, digest, _write, _inventory, _sync_directory
from .docker import DockerBackend
from .store import LeaseError


class Supervisor:
    def __init__(self,store,evidence_root,*,backend=None,poll_seconds=.2):
        self.store=store
        self.root=Path(evidence_root).resolve()
        self.backend=backend or DockerBackend()
        self.poll_seconds=poll_seconds

    def _paths(self,record):
        for key in ('trial','attempt'):
            if not re.fullmatch(r'[A-Za-z0-9_-]+',record[key]): raise ValueError('unsafe identity')
        parent=self.root/record['trial']
        parent.mkdir(parents=True,exist_ok=True)
        return parent/(record['attempt']+'.pending'),parent/record['attempt']

    def _publish(self,record,path,final,status,exit_code,request,*,estimated=False):
        usage={}
        for dimension,reserved in self.store.reservations(record).items():
            if dimension=='execution_ms' and not estimated:
                usage[dimension]=max(1,math.ceil((time.time()-record['started_at'])*1000))
            elif dimension in ('attempts','trial_attempts'): usage[dimension]=1
            else: usage[dimension]=reserved
        manifest=dict(schema='asr-managed-attempt/1',trial_id=record['trial'],
                      execution_attempt_id=record['attempt'],research_run_id=record['run'],
                      epoch=record['epoch'],status=status,exit_code=exit_code,
                      request_sha256=hashlib.sha256(canonical(request)).hexdigest(),
                      usage=usage,usage_estimated=estimated or any(k not in ('execution_ms','attempts','trial_attempts') for k in usage),
                      execution_exited=True,artifacts=_inventory(path))
        _write(path/'manifest.json',manifest)
        path.rename(final); _sync_directory(final.parent)
        return self._report(record,final)

    def _report(self,record,final):
        manifest=json.loads((final/'manifest.json').read_text())
        frozen=record['dispatch'].get('execution_request')
        if manifest.get('schema')!='asr-managed-attempt/1' or manifest.get('request_sha256')!=hashlib.sha256(canonical(frozen)).hexdigest():
            raise ValueError('manifest request mismatch')
        if manifest['trial_id']!=record['trial'] or manifest['execution_attempt_id']!=record['attempt']:
            raise ValueError('manifest identity mismatch')
        if manifest['artifacts']!=_inventory(final): raise ValueError('evidence corrupt')
        report={k:manifest[k] for k in ('trial_id','execution_attempt_id','status','usage','usage_estimated','execution_exited')}
        report.update(manifest_hash=digest(final/'manifest.json'),evidence_path=str(final))
        return self.store.report(record['attempt'],record['epoch'],record['owner'],report)

    def execute(self,attempt,owner,request=None):
        # The admitted dispatch owns the request; trusted callers cannot replace it.
        with self.store._connect() as db:
            row=db.execute("SELECT record FROM asr_dispatch WHERE attempt=?",(attempt,)).fetchone()
        if row is None: raise LeaseError("not_dispatchable")
        frozen=json.loads(row[0]).get("execution_request")
        if frozen is None: raise ValueError("frozen execution_request required")
        if request is not None and canonical(request)!=canonical(frozen): raise ValueError("execution request conflict")
        request=frozen
        self.backend.validate_request(request)
        timeout=request.get('timeout_seconds')
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0: raise ValueError('finite timeout required')
        record=self.store.claim(attempt,owner)
        path,final=self._paths(record)
        # Never wait on a different executor while holding a lease.
        with (path.parent/(attempt+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            path.mkdir()
            _write(path/'request.json',request)
            _write(path/'execution.json',{'attempt_id':attempt,'trial_id':record['trial'],'epoch':record['epoch']})
            try:
                identity=self.backend.create(record,path,request)
                _write(path/'identity.json',identity)
                self.store.attach(attempt,record['epoch'],owner,identity)
                # The control gate is checked again after container creation.
                if self.store.should_stop(attempt) or not self.store.dispatch_gate_open(attempt):
                    return self._publish(record,path,final,'cancelled',None,request)
                self.store.heartbeat(attempt,record['epoch'],owner)
                self.backend.start(identity,path)
                deadline=time.monotonic()+timeout
                while True:
                    self.store.heartbeat(attempt,record['epoch'],owner)
                    state=self.backend.inspect(identity)
                    if not state['running']:
                        status='succeeded' if state['exit_code']==0 else 'failed'
                        break
                    if self.store.should_stop(attempt): status='cancelled'; state=self.backend.stop(identity); break
                    if time.monotonic()>=deadline: status='timed_out'; state=self.backend.stop(identity); break
                    time.sleep(self.poll_seconds)
                self.backend.finalize(path,request,status)
                return self._publish(record,path,final,status,state['exit_code'],request)
            except Exception as exc:
                # Exceptions do not establish container exit, even during create.
                try: self.store.mark_uncertain(attempt,record['epoch'],owner,str(exc))
                except LeaseError: pass
                raise

    def reconcile(self,attempt,owner):
        old=self.store.get(attempt)
        path,final=self._paths(old)
        with (path.parent/(attempt+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            record=self.store.reconcile_claim(attempt,owner)
            if record['report'] is not None: return record
            if final.exists(): return self._report(record,final)
            if (path/'manifest.json').exists():
                # Publication interruption: validate contents before rename/report.
                manifest=json.loads((path/'manifest.json').read_text())
                if manifest['artifacts']!=_inventory(path): raise ValueError('evidence corrupt')
                path.rename(final); _sync_directory(final.parent)
                return self._report(record,final)
            identity=record['identity']
            if identity is None and (path/'identity.json').exists(): identity=json.loads((path/'identity.json').read_text())
            if identity is None and isinstance(self.backend,DockerBackend): identity=self.backend.identity(old)
            if identity is None: raise RuntimeError('unknown execution; reservation retained')
            state=self.backend.inspect(identity)
            if state['running']: state=self.backend.stop(identity)
            if state['running']: raise RuntimeError('execution exit unconfirmed')
            request=json.loads((path/'request.json').read_text())
            self.backend.finalize(path,request,'interrupted')
            return self._publish(record,path,final,'interrupted',state['exit_code'],request,estimated=True)
