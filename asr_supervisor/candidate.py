"""Run one frozen untrusted Octave file; never mount a host-writable directory.

The only host mounts are two read-only files. stdout/stderr is consumed by a
bounded trusted collector, with Docker logging disabled. Overflow causes external
container stopping through the existing Supervisor, not a candidate promise.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import stat
import subprocess
import threading
import time
from datetime import datetime

from powerflow_lab.reference import REPO, make_request
from powerflow_lab.runner import canonical, digest
from asr_evaluation.replay import IMAGE_ID, INPUT_SHA256, FIXTURE_INPUT, VALIDATOR_SHA256
from .resources import bounded_command,limit_event,LimitViolation

PROFILE = 'octave-candidate/1'
MAX_CODE_BYTES = 65536
MAX_OUTPUT_BYTES = 1048576
PREFIX = b'ASR_CANDIDATE_RESULT_V1:'
WRAPPER = Path(__file__).with_name('candidate_wrapper.m')


def _source(path):
    raw = Path(path)
    if raw.is_symlink(): raise ValueError('candidate source must not be a symlink')
    try:
        descriptor = os.open(raw,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode): raise ValueError('regular candidate source required')
            body = stream.read(MAX_CODE_BYTES+1)
    except OSError as error:
        raise ValueError('candidate source unavailable') from error
    if not body:raise ValueError('candidate source must not be empty')
    if len(body)>MAX_CODE_BYTES:
        raise LimitViolation(limit_event('candidate','candidate_code_limit','candidate_code_bytes',MAX_CODE_BYTES,max(info.st_size,len(body)),'bytes','admission',
            'submission_rejected','Keep the research task; revise the single-file method or request an explicitly approved profile with a larger source limit.',evidence_basis='fstat_and_bounded_read'))
    try: body.decode('utf-8')
    except UnicodeError as error: raise ValueError('candidate source must be UTF-8') from error
    return body


def make_candidate_request(path, sha256, size, *, timeout_seconds=60, max_iterations=20):
    if type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 0<timeout_seconds<=60:
        if type(timeout_seconds) in (int,float) and math.isfinite(timeout_seconds) and timeout_seconds>60:
            raise LimitViolation(limit_event('candidate','candidate_timeout_limit','candidate_timeout_seconds',60,timeout_seconds,'seconds','admission',
                'submission_rejected','Request at most 60 seconds or obtain an explicitly approved profile revision; keep the research task pending.'))
        raise ValueError('candidate timeout must be finite in (0,60]')
    body = _source(path)
    if type(size) is not int or len(body)!=size or hashlib.sha256(body).hexdigest()!=sha256:
        raise ValueError('candidate source hash or size mismatch')
    baseline = make_request(max_iterations=max_iterations,timeout_seconds=timeout_seconds)
    if baseline['image_id']!=IMAGE_ID or digest(FIXTURE_INPUT)!=INPUT_SHA256 or baseline['source_hashes']['validation.py']!=VALIDATOR_SHA256:
        raise ValueError('unsupported candidate environment or evaluator profile')
    baseline.update(profile=PROFILE,candidate=dict(path=str(Path(path).resolve()),sha256=sha256,size=size),
                    original_input_sha256=INPUT_SHA256,wrapper_sha256=digest(WRAPPER),output_bytes=MAX_OUTPUT_BYTES)
    return baseline


class CandidateBackend:
    def __init__(self):
        self.collectors = {}

    @staticmethod
    def validate_request(request):
        candidate=request.get('candidate',{})
        expected=make_candidate_request(candidate.get('path'),candidate.get('sha256'),candidate.get('size'),
            timeout_seconds=request.get('timeout_seconds'),max_iterations=request.get('max_iterations'))
        if canonical(expected)!=canonical(request): raise ValueError('unsupported frozen candidate request')

    @staticmethod
    def identity(record):
        request=record['dispatch']['execution_request']
        return dict(backend='docker-candidate',name='asr-managed-'+record['attempt'],
            labels={'asr.attempt':record['attempt'],'asr.trial':record['trial'],'asr.run':record['run'],
                    'asr.epoch':str(record['epoch']),'asr.profile':PROFILE,'asr.candidate':request['candidate']['sha256']})

    @staticmethod
    def _call(arguments):
        result=bounded_command(['docker',*arguments],component='candidate',operation=arguments[0])
        if result.returncode: raise RuntimeError('candidate Docker operation failed')
        return result.stdout.decode().strip()

    def create(self,record,path,request):
        self.validate_request(request)
        identity=self.identity(record)
        (path/'candidate.m').write_bytes(_source(request['candidate']['path']))
        (path/'candidate_wrapper.m').write_bytes(WRAPPER.read_bytes())
        # Canonical original input is host-owned and is NEVER exposed writable to
        # candidate code. Exported/forged candidate input cannot replace it.
        (path/'input.json').write_bytes(FIXTURE_INPUT.read_bytes())
        for source,expected in request['source_hashes'].items():
            if source not in ('validation.py','runner.py','reference.py') or digest(REPO/'powerflow_lab'/source)!=expected:
                raise ValueError('frozen source mismatch')
            (path/('source-'+source)).write_bytes((REPO/'powerflow_lab'/source).read_bytes())
        for name in ('candidate.m','candidate_wrapper.m','input.json'): (path/name).chmod(0o444)
        arguments=['create','--name',identity['name'],'--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--user','65532:65532','--pids-limit','64',
            '--memory','1g','--memory-swap','1g','--cpus','1','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=128m',
            '--log-driver','none','--entrypoint','octave','-e','HOME=/tmp','-e',f"ASR_MAX_IT={request['max_iterations']}"]
        for key,value in identity['labels'].items(): arguments+=['--label',key+'='+value]
        for name,destination in [('candidate.m','/candidate/candidate.m'),('candidate_wrapper.m','/runner/candidate_wrapper.m')]:
            arguments+=['--mount',f'type=bind,src={(path/name).resolve()},dst={destination},readonly']
        identity['container_id']=self._call(arguments+[IMAGE_ID,'--no-gui','--quiet','/runner/candidate_wrapper.m'])
        value=self._raw_inspect(identity)
        self.verify_container(value,identity,path)
        if digest(path/'candidate.m')!=request['candidate']['sha256'] or digest(path/'candidate_wrapper.m')!=request['wrapper_sha256'] or digest(path/'input.json')!=INPUT_SHA256:
            raise ValueError('copied candidate material changed')
        (path/'container-inspection.json').write_bytes(canonical(value))
        return identity

    @staticmethod
    def verify_container(value,identity,path):
        config=value['Config'];host=value['HostConfig']
        if value['Image']!=IMAGE_ID or config['Image']!=IMAGE_ID or config['User']!='65532:65532' or config['Entrypoint']!=['octave'] or config['Cmd']!=['--no-gui','--quiet','/runner/candidate_wrapper.m']:
            raise RuntimeError('candidate executable policy mismatch')
        expected={(str((path/name).resolve()),destination,False) for name,destination in (
            ('candidate.m','/candidate/candidate.m'),('candidate_wrapper.m','/runner/candidate_wrapper.m'))}
        actual={(m.get('Source'),m.get('Destination'),m.get('RW')) for m in value['Mounts'] if m['Type']=='bind'}
        if len(value['Mounts'])!=2 or actual!=expected: raise RuntimeError('unexpected candidate mounts')
        exact=dict(NetworkMode='none',ReadonlyRootfs=True,Privileged=False,Memory=1073741824,MemorySwap=1073741824,NanoCpus=1000000000,PidsLimit=64)
        if any(host.get(k)!=v for k,v in exact.items()) or host.get('CapAdd') or host.get('CapDrop')!=['ALL'] or host.get('SecurityOpt') not in (['no-new-privileges'],['no-new-privileges:true']):
            raise RuntimeError('candidate isolation or resource policy mismatch')
        if host.get('Tmpfs')!={'/tmp':'rw,nosuid,nodev,noexec,size=128m'} or host.get('LogConfig',{}).get('Type')!='none' or host.get('RestartPolicy')!={'Name':'no','MaximumRetryCount':0}:
            raise RuntimeError('candidate scratch, logging or restart policy mismatch')
        if any(host.get(k) for k in ('Binds','Devices','VolumesFrom','PortBindings','PidMode','UTSMode')):
            raise RuntimeError('candidate host access denied')
        allowed={'PATH','LANG','GPG_KEY','PYTHON_VERSION','PYTHON_SHA256','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','HOME','ASR_MAX_IT'}
        env=dict(item.split('=',1) for item in config['Env'])
        if set(env)-allowed or env.get('HOME')!='/tmp': raise RuntimeError('unexpected candidate environment')

    def _raw_inspect(self,identity):
        value=json.loads(self._call(['inspect',identity.get('container_id',identity['name'])]))[0]
        if identity.get('container_id') and value['Id']!=identity['container_id']:
            raise RuntimeError('candidate container ID changed')
        if any(value['Config']['Labels'].get(k)!=v for k,v in identity['labels'].items()):
            raise RuntimeError('candidate ownership changed')
        return value

    def _collect(self,collector):
        process=collector['process'];selector=selectors.DefaultSelector();count=0
        try:
            os.set_blocking(process.stdout.fileno(),False)
            selector.register(process.stdout,selectors.EVENT_READ)
            with collector['path'].open('xb') as stream:
                while True:
                    if not selector.select(.1):
                        if process.poll() is not None: break
                        continue
                    try: chunk=os.read(process.stdout.fileno(),65536)
                    except BlockingIOError: continue
                    if not chunk: break
                    available=MAX_OUTPUT_BYTES-count
                    collector['observed_bytes']=count+len(chunk)
                    stream.write(chunk[:available]);count+=min(len(chunk),available)
                    if len(chunk)>available:
                        collector['overflow']=True
                        break
                stream.flush();os.fsync(stream.fileno())
        except Exception:
            collector['error']=True
        finally:
            selector.close()
            process.stdout.close()

    def start(self,identity,path):
        process=subprocess.Popen(['docker','start','--attach',identity['container_id']],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        collector=dict(process=process,path=path/'candidate-stream.log',overflow=False,error=False,observed_bytes=0)
        collector['thread']=threading.Thread(target=self._collect,args=(collector,),daemon=True)
        self.collectors[identity['container_id']]=collector;collector['thread'].start()
        deadline=time.monotonic()+5
        while self._raw_inspect(identity)['State']['Status']=='created':
            if process.poll() is not None or time.monotonic()>=deadline: raise RuntimeError('candidate start not confirmed')
            time.sleep(.01)

    def inspect(self,identity):
        state=self._raw_inspect(identity)['State']
        if state.get('Status') in ('dead','removing','restarting','paused'): raise RuntimeError('candidate state uncertain')
        collector=self.collectors.get(identity.get('container_id'))
        return dict(running=state['Running'],exit_code=state['ExitCode'],started=state['Status']!='created',
                    failure_reason='output_limit' if collector and collector['overflow'] else 'capture_error' if collector and collector['error'] else None)

    def stop(self,identity):
        state=self.inspect(identity)
        if state['running']: self._call(['stop','--time','1',identity.get('container_id',identity['name'])])
        state=self.inspect(identity)
        if state['running']: raise RuntimeError('candidate exit unconfirmed')
        return state

    def detach(self,identity):
        collector=self.collectors.get(identity.get('container_id'))
        if collector:
            # SIGKILL only our attach client; do not proxy a cancellation to the
            # container. Its actual execution remains for fenced reconciliation.
            if collector['process'].poll() is None:collector['process'].kill()
            collector['process'].wait(timeout=2)
            collector['thread'].join(timeout=2)

    def finalize(self,path,request,status):
        identity=json.loads((path/'identity.json').read_text())
        collector=self.collectors.get(identity.get('container_id'))
        if collector:
            collector['thread'].join(timeout=2)
            if collector['process'].poll() is None:
                collector['process'].terminate()
                try:collector['process'].wait(timeout=1)
                except subprocess.TimeoutExpired:collector['process'].kill();collector['process'].wait(timeout=1)
            collector['thread'].join(timeout=1)
            if collector['thread'].is_alive(): raise RuntimeError('candidate stream collector unresolved')
            (path/'capture.json').write_bytes(canonical(dict(overflow=collector['overflow'],error=collector['error'],max_bytes=MAX_OUTPUT_BYTES,observed_bytes=collector['observed_bytes'],
                observed_kind='at_least' if collector['overflow'] else 'exact',retained_bytes=(path/'candidate-stream.log').stat().st_size if (path/'candidate-stream.log').exists() else 0)))
        value=self._raw_inspect(identity)
        if value['State']['Running']: raise RuntimeError('candidate exit unconfirmed')
        self.verify_container(value,identity,path)
        (path/'candidate-exit.json').write_bytes(canonical(value))
        events=[]
        if collector and collector['overflow']:
            events.append(limit_event('candidate','candidate_output_limit','candidate_output_bytes',MAX_OUTPUT_BYTES,collector['observed_bytes'],'bytes','running',
                'container_stopped','Reduce diagnostic output or revise the candidate; submit a new explicitly admitted attempt. The raw prefix and failed attempt remain preserved.',kind='at_least'))
        if status=='timed_out':
            state=value['State']
            elapsed=max(0,(datetime.fromisoformat(state['FinishedAt'].replace('Z','+00:00'))-datetime.fromisoformat(state['StartedAt'].replace('Z','+00:00'))).total_seconds())
            events.append(limit_event('candidate','candidate_timeout','candidate_timeout_seconds',request['timeout_seconds'],elapsed,'seconds','running',
                'container_stopped','Keep the method and evidence; revise it or explicitly request another authorized attempt within the profile limit.',kind='container_lifetime_including_stop',evidence_basis='docker_started_and_finished_timestamps'))
        if value['State'].get('OOMKilled'):
            events.append(limit_event('candidate','candidate_oom_killed','candidate_memory_bytes',1073741824,None,'bytes','running',
                'container_oom_killed','Reduce memory use or obtain an explicitly approved resource profile; preserve this failed attempt.',kind='oom_kill_observed',evidence_basis='docker_state_oom_killed'))
        if collector and collector['error']:
            events.append(dict(schema='asr-execution-diagnostic/1',component='candidate',code='candidate_capture_error',task_retained=True,
                recovery='Inspect capture/storage availability and reconcile before an explicitly authorized new attempt.'))
        if events:(path/'resource-events.json').write_bytes(canonical(events))
        if digest(path/'candidate.m')!=request['candidate']['sha256'] or digest(path/'candidate_wrapper.m')!=request['wrapper_sha256'] or digest(path/'input.json')!=INPUT_SHA256:
            raise ValueError('candidate modified immutable host evidence')
        if status!='succeeded': return
        try:
            if not collector or collector['overflow'] or collector['error']: raise ValueError('candidate output incomplete')
            raw=(path/'candidate-stream.log').read_bytes()
            messages=[line[len(PREFIX):] for line in raw.split(b'\n') if line.startswith(PREFIX)]
            if len(messages)!=1: raise ValueError('exactly one candidate result required')
            payload=json.loads(messages[0])
            if not isinstance(payload,dict) or set(payload)!={'solution','claims'}: raise ValueError('invalid candidate result')
            solution=canonical(payload['solution']);claims=canonical(dict(author_claims=payload['claims'],independently_validated=False,candidate_sha256=request['candidate']['sha256']))
        except (ValueError,TypeError,UnicodeError,RecursionError) as error:
            (path/'candidate-output-error.json').write_bytes(canonical(dict(reason=type(error).__name__,assessment='invalid_candidate_output')))
            return {'status':'failed'}
        (path/'solution.json').write_bytes(solution)
        (path/'solver.json').write_bytes(claims)
