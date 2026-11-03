"""Deterministic labelled reference containers, using the pinned P1 environment."""
import json
import os
import subprocess
from powerflow_lab.reference import REPO, make_request
from powerflow_lab.runner import digest, canonical
from powerflow_lab.validation import validate


class DockerBackend:
    def _candidate_backend(self):
        if not hasattr(self,'_candidate'):
            from .candidate import CandidateBackend
            self._candidate=CandidateBackend()
        return self._candidate

    @staticmethod
    def validate_request(request):
        if request.get('profile')=='octave-candidate/1':
            from .candidate import CandidateBackend
            return CandidateBackend.validate_request(request)
        expected=make_request(max_iterations=request.get("max_iterations"),timeout_seconds=request.get("timeout_seconds"))
        if canonical(expected)!=canonical(request): raise ValueError("unsupported reference execution request")

    @staticmethod
    def _call(args):
        p=subprocess.run(['docker',*args],capture_output=True,timeout=20)
        if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace').strip())
        return p.stdout.decode().strip()

    @staticmethod
    def identity(record):
        if record.get('dispatch',{}).get('execution_request',{}).get('profile')=='octave-candidate/1':
            from .candidate import CandidateBackend
            return CandidateBackend.identity(record)
        return {'backend':'docker','name':'asr-managed-'+record['attempt'],
                'labels':{'asr.attempt':record['attempt'],'asr.trial':record['trial'],
                          'asr.run':record['run'],'asr.epoch':str(record['epoch'])}}

    def create(self, record, path, request):
        if request.get('profile')=='octave-candidate/1': return self._candidate_backend().create(record,path,request)
        identity=self.identity(record)
        for source,expected in request['source_hashes'].items():
            original=REPO/'powerflow_lab'/source
            if source not in ('validation.py','runner.py','reference.py') or digest(original)!=expected:
                raise ValueError('frozen source mismatch')
            (path/('source-'+source)).write_bytes(original.read_bytes())
        (path/'reference_pf.m').write_bytes((REPO/'scripts/reference_pf.m').read_bytes())
        (path/'packages.txt').write_bytes((REPO/'configs/numerical-packages.txt').read_bytes())
        args=['create','--name',identity['name'],'--network','none','--read-only',
              '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128',
              '--memory','1g','--cpus','1','--tmpfs','/tmp:rw,nosuid,nodev,size=128m',
              '--user',f'{os.getuid()}:{os.getgid()}','-e',f"ASR_MAX_IT={request['max_iterations']}",
              '--mount',f'type=bind,src={path.resolve()},dst=/output']
        for key,value in identity['labels'].items(): args+=['--label',f'{key}={value}']
        identity['container_id']=self._call(args+[request['image_id']])
        return identity

    def start(self, identity, path):
        if identity.get('backend')=='docker-candidate': return self._candidate_backend().start(identity,path)
        self._call(['start',identity.get('container_id',identity['name'])])

    def inspect(self, identity):
        if identity.get('backend')=='docker-candidate': return self._candidate_backend().inspect(identity)
        value=json.loads(self._call(['inspect',identity.get('container_id',identity['name'])]))[0]
        if any(value['Config']['Labels'].get(k)!=v for k,v in identity['labels'].items()):
            raise RuntimeError('container identity mismatch')
        if identity.get('container_id') and value['Id']!=identity['container_id']: raise RuntimeError('container ID changed')
        state=value['State']
        if state.get('Status') in ('restarting','removing','dead'): raise RuntimeError('container state uncertain')
        return {'running':state['Running'],'exit_code':state['ExitCode'], 'started':state['Status']!='created'}

    def stop(self, identity):
        if identity.get('backend')=='docker-candidate': return self._candidate_backend().stop(identity)
        self.inspect(identity)  # Never signal a mismatched container.
        self._call(['stop','--time','1',identity.get('container_id',identity['name'])])
        state=self.inspect(identity)
        if state['running']: raise RuntimeError('container termination unconfirmed')
        return state

    def detach(self,identity):
        if identity.get('backend')=='docker-candidate':return self._candidate_backend().detach(identity)

    def finalize(self,path,request,status):
        if request.get('profile')=='octave-candidate/1': return self._candidate_backend().finalize(path,request,status)
        identity=json.loads((path/'identity.json').read_text())
        (path/'solver.log').write_text(self._call(['logs',identity.get('container_id',identity['name'])]))
        if status=='succeeded':
            inp=json.loads((path/'input.json').read_text())
            solution=json.loads((path/'solution.json').read_text())
            (path/'validation.json').write_text(json.dumps(validate(inp,solution,
                tolerance_pu=request['validation_tolerance_pu']),allow_nan=False,indent=2))
