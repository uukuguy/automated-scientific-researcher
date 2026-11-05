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


SNAPSHOT_BYTES = 16 * 1024 * 1024


class SnapshotLimit(ValueError):
    code = 'snapshot_too_large'

    def __init__(self, observed, path):
        super().__init__(self.code)
        self.details = dict(dimension='snapshot_bytes',limit=SNAPSHOT_BYTES,requested=observed,
            observed_kind='at_least',scope='workspace_snapshot',path=path,recoverable=True,
            reason='Bound in-memory publication and replication of shared workspace snapshots.',
            recovery='Original workspace and experiment evidence are retained. Publish smaller explicit snapshots or reference immutable evidence by hash; do not rerun experiments.')


class ResearchBridge:
    def __init__(self, service, *, project, run, researcher_token, supervisor_token, workspace, snapshots, dispatch=None, organization=None, evaluation_dispatch=None, capability_profile='powerflow-calibration-smoke/3'):
        from integrations.runtimes.capability_inventory import PROFILE_TOOLS
        if capability_profile not in PROFILE_TOOLS:raise ValueError('unsupported_capability_profile')
        self.allowed_operations={tool.removeprefix('asr.') for tool in PROFILE_TOOLS[capability_profile]}|{'permit'}
        if capability_profile in ('research-organization/1','research-organization-study/1'):self.allowed_operations.update({'context_boundary','context_installed'})
        self.capability_profile=capability_profile
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
        self.context_installation_id=None
        self.context_observation_barrier=None
        self.recording_pressure=None
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
        if operation=='context_boundary':
            if self.context_observation_barrier is not None:
                drained=self.context_observation_barrier()
                if not drained['drained']:
                    return dict(action='cancel',reason='context_observations_pending',installation_authorized=False,context_installed=False,observation_drain=drained)
            if not {'observation'}<=set(arguments)<= {'observation','tokens_before'} or type(arguments['observation']) is not dict or arguments['observation'].get('observation_id')!=key or arguments['observation'].get('boundary')!='session_before_compact':
                raise ValueError('invalid_bridge_request')
            receipt=s.observe_context_cursor(self.supervisor_token,p,r,**self.runtime_identity,observation=arguments['observation'])
            if self.context_installation_id and receipt['status']=='bound':
                try:
                    return s.authorize_context_installation(self.supervisor_token,p,r,**self.runtime_identity,stage_id=self.context_installation_id,
                        observation=receipt['observation'],tokens_before=arguments.get('tokens_before'))
                except ValueError as error:
                    with s._connect() as db:s._event(db,p,r,'context_installation_deferred',session_id=self.runtime_identity.get('session_id'),stage_id=self.context_installation_id,reason=getattr(error,'code','context_installation_check_failed'))
                    return dict(action='cancel',reason=getattr(error,'code','context_installation_check_failed'),installation_authorized=False,context_installed=False)
            reason='context_installation_not_ready' if receipt['status']=='bound' else receipt['reason']
            result=dict(action='cancel',reason=reason,context_installed=False,installation_authorized=False,cursor_receipt=receipt)
            with s._connect() as db:
                s._event(db,p,r,'context_boundary_deferred',session_id=self.runtime_identity.get('session_id'),observation_id=key,reason=reason,context_installed=False)
            return result
        if operation=='context_installed':
            if set(arguments)!={'boundary_id','ticket_id','entry_id','cursor'}:raise ValueError('invalid_bridge_request')
            cursor=arguments['cursor']
            if type(cursor) is not dict or cursor.get('status')!='observed' or cursor.get('leaf_id')!=arguments['entry_id']:raise ValueError('invalid_bridge_request')
            return s.complete_context_installation(self.supervisor_token,p,r,**self.runtime_identity,idempotency_key=key,
                **{k:v for k,v in arguments.items() if k!='cursor'})
        if operation=='permit':
            pressure=self.recording_pressure() if arguments.get('kind')=='turn' and self.recording_pressure is not None else None
            result=s.admit_activity(self.supervisor_token,p,r,kind=arguments['kind'],idempotency_key=key,recording_pressure=pressure,**self.runtime_identity)
            if 'activity_id' in result:self.permits.append(result)
            return result
        if operation=='research_note':
            if arguments.get('operation')=='conversation_read':
                return s.read_context_source(t,p,r,**{k:v for k,v in arguments.items() if k!='operation'})
            return s.research_note(t,p,r,idempotency_key=key,**arguments)
        if operation=='organization_records':
            return s.organization_records(t,p,r,**arguments)
        if operation=='organization_change':
            return s.change_organization(t,p,r,idempotency_key=key,**arguments)
        if operation=='state':
            return self.state()
        if operation=='freeze_candidate':
            return self.freeze_candidate(arguments,key)
        if operation=='submit_study':
            self._reconcile_studies(s.get_run(t,p,r))
            receipt=s.submit_study(t,p,r,request_key=key,**arguments)
            return self.dispatch_trial(receipt)
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
            try:
                receipt=self.snapshot(arguments.get('paths',[]))
            except SnapshotLimit as error:
                block=s._record_budget_block(t,p,r,'snapshot',(),dict(request_key=key,paths=arguments.get('paths',[])),error.details,pause=False)
                error.details['block_id']=block['block_id']
                raise
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
        if 'paired_adapter' in receipt:
            from asr_service.study_adapters import reconcile
            reconcile(self.service,self.researcher_token,self.project,self.run,receipt['trial_id'],retry=True)
        return dict(receipt=receipt,state=self.state())

    def _reconcile_studies(self,run):
        from asr_service.study_adapters import reconcile
        for trial in run['trials']:
            if 'paired_adapter' in trial:
                trial['study_adapter_check']=reconcile(self.service,self.researcher_token,self.project,self.run,trial['trial_id'])

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
        if self.capability_profile=='research-organization/1':
            history=self.service.organization_records(self.researcher_token,self.project,self.run)
            run=self.service.get_run(self.researcher_token,self.project,self.run)
            contract=run['contract']['document']
            return dict(projection=self.capability_profile,
                run={key:run[key] for key in ('project_id','research_run_id','state','health','control_revision','contract_revision','budget')},
                objective=contract['objective'],runtime_policy=contract['runtime_policy'],organization=history,
                boundary='Organization records only; follow history pages. No role execution or scientific validation is implied.')
        run=self.service.get_run(self.researcher_token,self.project,self.run)
        if self.capability_profile in ('ood-study-development/1','ood-study-synthesis/1','research-organization-study/1'):
            from .study_projection import project_state
            self._reconcile_studies(run)
            return project_state(self,run)
        if self.capability_profile=='powerflow-readonly-finalization/1':
            return dict(projection='readonly-finalization/1',run={key:run[key] for key in ('project_id','research_run_id','experiment_id','state','contract_revision','budget')},
                hypotheses=[{key:item[key] for key in ('hypothesis_id','revision','sha256')} for item in self.service.hypotheses(self.researcher_token,self.project)],
                trials=[dict(trial_id=item['trial_id'],execution_attempt_id=item['execution_attempt_id'],state=item['dispatch_state'],replicates=item.get('replicates')) for item in run['trials']],
                findings=self.service.findings(self.researcher_token,self.project,self.run),
                validations=[{key:item[key] for key in ('validation_id','document')} for item in self.service.validations(self.researcher_token,self.project,self.run)],
                omitted='Full contract, source/evaluation bytes and native transcripts are intentionally outside this closeout projection; their original evidence references remain retained.')
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
            size=path.stat().st_size
            if size>SNAPSHOT_BYTES-total: raise SnapshotLimit(total+size,name)
            with path.open('rb') as stream: body=stream.read(SNAPSHOT_BYTES+1-total)
            total+=len(body)
            if total>SNAPSHOT_BYTES: raise SnapshotLimit(total,name)
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
