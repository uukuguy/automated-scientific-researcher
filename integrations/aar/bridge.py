"""AAR research organization bridge: shared evidence, findings and snapshots.

The scientific decision loop lives in the coding runtime. This bridge does not
schedule sessions or experiments, and exposes no author-written validation scores.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import tempfile
import shutil
import os
import threading


class ResearchBridge:
    def __init__(self, service, *, project, run, researcher_token, supervisor_token, workspace, snapshots, dispatch=None, organization=None, evaluation_dispatch=None, capability_profile='powerflow-calibration-smoke/3'):
        from integrations.runtimes.capability_inventory import PROFILE_TOOLS
        if capability_profile not in PROFILE_TOOLS:raise ValueError('unsupported_capability_profile')
        self.allowed_operations={tool.removeprefix('asr.') for tool in PROFILE_TOOLS[capability_profile]}|{'permit'}
        self.service=service; self.project=project; self.run=run
        self.researcher_token=researcher_token; self.supervisor_token=supervisor_token
        self.workspace=Path(workspace).resolve(); self.snapshots=Path(snapshots).resolve()
        self.dispatch=dispatch
        self.evaluation_dispatch=evaluation_dispatch
        self.organization=organization
        self.dispatch_lock=threading.Lock()
        self.token=secrets.token_urlsafe(32); self.server=None
        self.permits=[]
        self.runtime_identity={}
        self.documentation=None

    def call(self, operation, arguments, key):
        if not isinstance(arguments,dict) or not isinstance(key,str) or not key:
            raise ValueError('invalid_bridge_request')
        if operation not in self.allowed_operations:raise ValueError('unsupported_bridge_operation')
        s=self.service; p=self.project; r=self.run; t=self.researcher_token
        if operation in ('resolve_library','query_docs'):
            if self.documentation is None:
                from integrations.research_tools.context7 import Context7Client
                self.documentation=Context7Client()
            return getattr(self.documentation,operation)(**arguments)
        if operation=='search_literature':
            from integrations.research_tools.literature import search
            return search(**arguments)
        if operation=='permit':
            result=s.admit_activity(self.supervisor_token,p,r,kind=arguments['kind'],idempotency_key=key,**self.runtime_identity)
            self.permits.append(result); return result
        if operation=='state':
            return self.state()
        if operation=='freeze_candidate':
            return self.freeze_candidate(arguments,key)
        if operation in ('submit_trial','submit_candidate'):
            if operation=='submit_candidate' and arguments.get('variables',{}).get('solver')!='octave-candidate/1':
                raise ValueError('candidate_profile_required')
            receipt=s.submit_trial(t,p,r,request_key=key,**arguments)
            return self.dispatch_trial(receipt)
        if operation=='request_replication':
            receipt=s.submit_replication(t,p,r,request_key=key,**arguments)
            return self.dispatch_trial(receipt)
        if operation=='request_evaluation':
            receipt=s.admit_evaluation(t,p,r,request_key=key,**arguments)
            if self.evaluation_dispatch:
                with self.dispatch_lock:
                    current=s.get_evaluation(t,p,r,receipt['evaluation_id'])
                    if current['state']=='queued':self.evaluation_dispatch(receipt)
            return dict(receipt=receipt,state=self.state())
        if operation=='ack_guidance':
            return s.ack_guidance(t,p,r,idempotency_key=key,**self.runtime_identity,**arguments)
        if operation=='publish_hypothesis':
            return s.publish_hypothesis(t,p,idempotency_key=key,**arguments)
        if operation=='publish_finding':
            receipt=s.publish_finding(t,p,r,idempotency_key=key,**arguments)
            if self.organization:self.organization.sync_findings(self.supervisor_token,p,r)
            return receipt
        if operation=='snapshot':
            receipt=self.snapshot(arguments.get('paths',[]))
            if self.organization:self.organization.register_snapshot(self.supervisor_token,p,r,snapshot_root=self.snapshots,digest=receipt['snapshot_sha256'])
            return receipt
        raise ValueError('unsupported_bridge_operation')

    def dispatch_trial(self,receipt):
        # Replayed admission returns its original receipt. Only a still-queued
        # authoritative attempt may be dispatched; the supervisor claims it.
        if self.dispatch:
            with self.dispatch_lock:
                current=self.service.get_run(self.researcher_token,self.project,self.run)
                trial=next(x for x in current['trials'] if x['execution_attempt_id']==receipt['execution_attempt_id'])
                if trial['dispatch_state']=='queued':self.dispatch(receipt)
        return dict(receipt=receipt,state=self.state())

    def freeze_candidate(self,arguments,key):
        if arguments!={'path':'candidate.m'}:raise ValueError('candidate_entrypoint_required')
        path=self.workspace/'candidate.m'
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(self.workspace):
            raise ValueError('invalid_snapshot_path')
        if path.stat().st_size>65536:raise ValueError('candidate_too_large')
        snapshot=self.call('snapshot',{'paths':['candidate.m']},key+'-snapshot')
        frozen=self.snapshots/snapshot['snapshot_sha256']/'files/candidate.m'
        with frozen.open('rb') as stream:source=stream.read(65537)
        if len(source)>65536:raise ValueError('candidate_too_large')
        digest=hashlib.sha256(source).hexdigest()
        if digest!=snapshot['manifest']['files'][0]['sha256']:raise ValueError('snapshot_corrupt')
        registered=self.service.register_candidate(self.researcher_token,self.project,request_key=key,
            source=source.decode('utf-8'),entrypoint='candidate.m',profile='octave-candidate/1',
            snapshot_ref=snapshot['snapshot_sha256'],run=self.run)
        public_registration={field:value for field,value in registered.items() if field!='path'}
        return dict(candidate_ref=registered['digest'],registration=public_registration,
                    snapshot_sha256=snapshot['snapshot_sha256'],code_sha256=digest)

    def state(self):
        run=self.service.get_run(self.researcher_token,self.project,self.run)
        observations=[];evaluation_targets=[]
        for trial in run['trials']:
            report=(trial.get('execution') or {}).get('report')
            if not report: continue
            if report.get('execution_exited') is True:
                evaluation_targets.append(dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],
                    manifest_hash=report['manifest_hash'],evaluation_ref=trial['references']['evaluation']))
            path=Path(report['evidence_path'])
            validation=path/'validation.json'
            if validation.is_file():
                observations.append(dict(trial_id=trial['trial_id'],manifest_hash=report['manifest_hash'],validation=json.loads(validation.read_text())))
        return dict(run=run,evaluation_targets=evaluation_targets,evaluations=run.get('evaluations',[]),validations=self.service.validations(self.researcher_token,self.project,self.run),hypotheses=self.service.hypotheses(self.researcher_token,self.project),findings=self.service.findings(self.researcher_token,self.project,self.run),observations=observations,snapshot_refs=self._snapshot_refs(),shared_findings=self.organization.forum(self.supervisor_token,self.project) if self.organization else [])

    def _snapshot_refs(self):
        if not self.snapshots.exists(): return []
        return [p.name for p in sorted(self.snapshots.iterdir()) if not p.name.startswith('.') and p.is_dir() and (p/'manifest.json').is_file()]

    def snapshot(self, paths):
        if not isinstance(paths,list) or not paths or any(not isinstance(x,str) for x in paths) or len(set(paths))!=len(paths): raise ValueError('explicit_snapshot_paths_required')
        entries=[]; content={}; total=0
        for name in paths:
            if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('invalid_snapshot_path')
            path=self.workspace/name
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(self.workspace):
                raise ValueError('invalid_snapshot_path')
            if path.stat().st_size>1048576-total: raise ValueError('snapshot_too_large')
            with path.open('rb') as stream: body=stream.read(1048577-total)
            total+=len(body)
            if total>1048576: raise ValueError('snapshot_too_large')
            content[name]=body; entries.append(dict(path=name,sha256=hashlib.sha256(body).hexdigest(),size=len(body)))
        manifest=dict(schema='asr-workspace-snapshot/1',project_id=self.project,research_run_id=self.run,files=sorted(entries,key=lambda e:e['path']))
        raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode(); digest=hashlib.sha256(raw).hexdigest()
        target=self.snapshots/digest
        self.snapshots.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            staging=Path(tempfile.mkdtemp(prefix='.pending-',dir=self.snapshots))
            try:
                for name,body in content.items():
                    path=staging/'files'/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(body)
                (staging/'manifest.json').write_bytes(raw)
                try: os.rename(staging,target)
                except OSError:
                    if not target.exists(): raise
            finally:
                if staging.exists(): shutil.rmtree(staging)
        if (target/'manifest.json').read_bytes()!=raw or any((target/'files'/name).read_bytes()!=body for name,body in content.items()):
            raise ValueError('snapshot_corrupt')
        return dict(snapshot_sha256=digest,manifest=manifest)

    def __enter__(self):
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                if self.path!='/bridge' or not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner.token):
                    self.send_error(403);return
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if length<=0 or length>262144: raise ValueError('payload_size')
                    data=json.loads(self.rfile.read(length))
                    result=owner.call(data['operation'],data['arguments'],data['key'])
                    raw=json.dumps(result).encode(); self.send_response(200)
                except Exception as error:
                    # Only structured code leaves service; no secrets in diagnostics.
                    code=getattr(error,'code',None)
                    allowed={'explicit_snapshot_paths_required','invalid_snapshot_path','snapshot_too_large','snapshot_corrupt','unsupported_bridge_operation','invalid_bridge_request','candidate_entrypoint_required','candidate_too_large','candidate_profile_required'}
                    if code is None: code=str(error) if str(error) in allowed else 'bridge_rejected'
                    response={'error':code}
                    details=getattr(error,'details',None)
                    if isinstance(details,dict):response['details']=details
                    raw=json.dumps(response).encode(); self.send_response(422)
                self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
                self.end_headers()
                try:self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):pass  # Interrupted native client; durable work remains.
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}/bridge'
        return self

    def __exit__(self,*exc):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
