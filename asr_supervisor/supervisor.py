"""Execute only admitted work; preserve unknown execution and reconcile before settlement."""
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import time
from powerflow_lab.runner import canonical, digest, _write, _inventory, _sync_directory, EvidenceError
from .docker import DockerBackend
from .store import LeaseError
from .resources import limit_event,LimitViolation


def publication_inventory(path):
    """Keep pinned numerical inventory unchanged; diagnose managed cap overruns.

    The preliminary metadata scan stops at the first overrun or unsafe entry and
    reads no file content. All raw pending material stays in place.
    """
    total=count=0
    for item in path.iterdir():
        if item.name=='manifest.json':continue
        info=item.lstat()
        if not stat.S_ISREG(info.st_mode):raise EvidenceError('only regular flat output files allowed')
        total+=info.st_size;count+=1
        if total>100*1024*1024 or count>100:
            by_count=count>100
            event=limit_event('supervisor','publication_limit','publication_files' if by_count else 'publication_bytes',
                100 if by_count else 100*1024*1024,count if by_count else total,'files' if by_count else 'bytes',
                'publication','pending_evidence_retained','Keep every raw artifact and the reservation; use reviewed export or an explicitly approved publisher profile before reconciliation.',kind='at_least')
            event['pending_path']=str(path.resolve())
            raise LimitViolation(event)
    return _inventory(path)


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
                      execution_exited=True,artifacts=publication_inventory(path))
        if 'organization_task' in record['dispatch']:
            manifest['organization_task']=record['dispatch']['organization_task']
        if 'paired_sampling' in record['dispatch']:
            manifest['paired_sampling']=record['dispatch']['paired_sampling']
        if (path/'resource-events.json').exists():
            manifest['resource_events']=json.loads((path/'resource-events.json').read_text())
        elif (path/'limit-trigger.json').exists():
            manifest['resource_events']=[json.loads((path/'limit-trigger.json').read_text())]
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
        if manifest.get('organization_task')!=record['dispatch'].get('organization_task'):
            raise ValueError('manifest organization binding mismatch')
        if manifest.get('paired_sampling')!=record['dispatch'].get('paired_sampling'):
            raise ValueError('manifest paired sampling mismatch')
        if manifest['artifacts']!=publication_inventory(final): raise ValueError('evidence corrupt')
        report={k:manifest[k] for k in ('trial_id','execution_attempt_id','status','usage','usage_estimated','execution_exited')}
        report.update(manifest_hash=digest(final/'manifest.json'),evidence_path=str(final))
        if 'resource_events' in manifest:report['resource_events']=manifest['resource_events']
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
                        status='succeeded' if state['exit_code']==0 and not state.get('failure_reason') else 'failed'
                        break
                    if state.get('failure_reason'): status='failed';state=self.backend.stop(identity);break
                    if self.store.should_stop(attempt): status='cancelled'; state=self.backend.stop(identity); break
                    if time.monotonic()>=deadline:
                        _write(path/'limit-trigger.json',limit_event('supervisor','execution_timeout','execution_timeout_seconds',timeout,time.monotonic()-(deadline-timeout),'seconds','running',
                            'stop_requested','Preserve this attempt and its cost; reconcile if exit is unknown, then explicitly revise or resubmit within authorized limits.'))
                        status='timed_out';state=self.backend.stop(identity);break
                    time.sleep(self.poll_seconds)
                outcome=self.backend.finalize(path,request,status)
                if isinstance(outcome,dict) and outcome.get('status')=='failed': status='failed'
                return self._publish(record,path,final,status,state['exit_code'],request)
            except Exception as exc:
                # Exceptions do not establish container exit, even during create.
                if getattr(exc,'diagnostic',None) and path.exists() and not (path/'manifest.json').exists() and not (path/'failure-diagnostic.json').exists():
                    _write(path/'failure-diagnostic.json',exc.diagnostic)
                try: self.store.mark_uncertain(attempt,record['epoch'],owner,str(exc),diagnostic=getattr(exc,'diagnostic',None))
                except LeaseError: pass
                raise
            except BaseException:
                if 'identity' in locals() and hasattr(self.backend,'detach'):
                    self.backend.detach(identity)
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
                if manifest['artifacts']!=publication_inventory(path): raise ValueError('evidence corrupt')
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
