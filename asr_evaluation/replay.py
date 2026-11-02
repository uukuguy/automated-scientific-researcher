"""Bounded local Docker recheck of immutable case118 numerical material.

This is not solver replication, a research scheduler, an authenticated Validation
publisher, or budget integration. Unknown execution keeps a durable pending job
and blocks automatic replay. Only trusted host code may choose source paths.
"""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import uuid

from powerflow_lab.runner import canonical, _sync_directory

REPO = Path(__file__).resolve().parents[1]
IMAGE_ID = 'sha256:d40dc592523126c64abb42a730c4cc9652083efa5593d01e56238202200d9831'
INPUT_SHA256 = 'bc436a7e82eb7a4d0d571942189795a5ac9aee29672804e603b56b5400b9ca14'
CASE_SHA256 = 'bc2e6f22b4b9e776572885ee4b50e4f4ab2ee0c5577e9126e86d906f14c4b5f7'
VALIDATOR_SHA256 = '090499c1c180e63215dd444a7f3a0cb10da02a724904e3a684c74ae5beb562d3'
PROFILE = 'matpower-case118-flat/1'
POLICY = 'fixed-pv-pq-single-slack/1'
LIMITS = ['Frozen-material numerical recheck only; candidate method was not rerun.',
          'No held-out generalization or independent scientific claim assessment.',
          'Standalone local execution; no Control authorization, Validation publication or budget reservations.',
          'timeout_seconds bounds running polling; Docker setup and cleanup operations each allow an additional five seconds.']
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
FIXTURE_INPUT = REPO/'environments/scientific/fixtures/matpower-case118/input.json'


class ReplayError(RuntimeError):
    pass


class UnresolvedReplay(ReplayError):
    """Container exit or publication is unresolved. No automatic retry is allowed."""


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _read(path, limit=MAX_FILE_BYTES, *, sync=False):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ReplayError('regular files required')
            if sync:
                os.fsync(stream.fileno())
            body = stream.read(limit + 1)
    except OSError as error:
        raise ReplayError('evidence file unavailable or symlinked') from error
    if len(body) > limit:
        raise ReplayError('evidence file exceeds size limit')
    return body


def _json(body):
    try:
        def reject_constant(value):
            raise ValueError('nonfinite JSON')
        return json.loads(body, parse_constant=reject_constant)
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ReplayError('invalid evidence JSON') from error


def _write(path, body):
    if not isinstance(body, bytes):
        body = canonical(body)
    with path.open('xb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    _sync_directory(path.parent)


def freeze_source(source_path, manifest_hash, *, trial_id, execution_attempt_id, research_run_id):
    """Verify every published artifact, then retain only nonexecutable inputs."""
    source = Path(source_path)
    if source.is_symlink() or not source.is_dir():
        raise ReplayError('regular evidence directory required')
    raw = _read(source/'manifest.json', 65536)
    if _sha(raw) != manifest_hash:
        raise ReplayError('source manifest hash mismatch')
    manifest = _json(raw)
    identity = dict(trial_id=trial_id, execution_attempt_id=execution_attempt_id, research_run_id=research_run_id)
    if not isinstance(manifest, dict) or any(manifest.get(k) != v for k, v in identity.items()):
        raise ReplayError('source identity mismatch')
    if manifest.get('schema') != 'asr-managed-attempt/1' or manifest.get('execution_exited') is not True or manifest.get('status') not in ('succeeded','failed','timed_out','interrupted','cancelled'):
        raise ReplayError('published terminal managed evidence required')
    artifacts = manifest.get('artifacts')
    if not isinstance(artifacts, dict) or not 1 <= len(artifacts) <= 100:
        raise ReplayError('invalid source artifact inventory')
    if {p.name for p in source.iterdir()} != set(artifacts) | {'manifest.json'}:
        raise ReplayError('source artifact membership changed')
    retained = {'source-manifest.json': raw}
    total = 0
    for name, metadata in artifacts.items():
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in ('.', '..', 'manifest.json'):
            raise ReplayError('unsafe artifact name')
        body = _read(source/name)
        total += len(body)
        if total > MAX_TOTAL_BYTES or metadata != dict(bytes=len(body), sha256=_sha(body)):
            raise ReplayError('source artifact hash or size mismatch')
        if name in ('input.json', 'solution.json', 'request.json'):
            retained[name] = body
    if not {'input.json','solution.json','request.json'} <= set(retained):
        raise ReplayError('source input, solution and request required')
    if _sha(retained['request.json']) != manifest.get('request_sha256'):
        raise ReplayError('source request hash mismatch')
    request = _json(retained['request.json'])
    if not isinstance(request, dict) or any(request.get(k) != v for k, v in dict(
            policy=POLICY, case='case118', case_sha256=CASE_SHA256, image_id=IMAGE_ID, initialization='flat',validation_tolerance_pu=1e-7).items()):
        raise ReplayError('unsupported source profile')
    if not isinstance(request.get('source_hashes'),dict) or request['source_hashes'].get('validation.py') != VALIDATOR_SHA256:
        raise ReplayError('unsupported frozen validator')
    trusted = _read(FIXTURE_INPUT)
    if _sha(trusted) != INPUT_SHA256 or retained['input.json'] != trusted:
        raise ReplayError('source does not preserve pinned original input')
    # Shape/NaN checks occur inside the isolated validator, not by executing any
    # source-provided code. Source bytes remain identical to the hashed artifact.
    return dict(identity=identity, manifest_sha256=manifest_hash, input_sha256=INPUT_SHA256,
                solution_sha256=_sha(retained['solution.json']), files=retained)


def verify_container(value, identity, pending):
    """Check actual Docker inspect facts, rather than only intended CLI flags."""
    try:
        config, host = value['Config'], value['HostConfig']
        if value['Id'] != identity['container_id'] or value['Image'] != IMAGE_ID or config['Image'] != IMAGE_ID:
            raise ReplayError('container image or identity mismatch')
        if any(config['Labels'].get(k) != v for k,v in identity['labels'].items()):
            raise ReplayError('container labels changed')
        if config['User'] != '65532:65532' or config['Entrypoint'] != ['python3'] or config['Cmd'] != ['-I','-S','/evaluator/entrypoint.py']:
            raise ReplayError('evaluator entrypoint or user changed')
        environment = dict(item.split('=',1) for item in config['Env'])
        allowed = {'PATH','LANG','GPG_KEY','PYTHON_VERSION','PYTHON_SHA256','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','HOME','PYTHONDONTWRITEBYTECODE'}
        if set(environment)-allowed or environment.get('HOME') != '/tmp' or environment.get('PYTHONDONTWRITEBYTECODE') != '1':
            raise ReplayError('unexpected evaluator environment')
        exact = dict(NetworkMode='none', ReadonlyRootfs=True, Privileged=False, PidsLimit=32,
                     Memory=268435456, MemorySwap=268435456, NanoCpus=1000000000)
        if any(host.get(k) != v for k,v in exact.items()) or host.get('CapAdd') or host.get('CapDrop') != ['ALL']:
            raise ReplayError('container resource or privilege policy changed')
        if host.get('SecurityOpt') not in (['no-new-privileges'], ['no-new-privileges:true']):
            raise ReplayError('no-new-privileges required')
        if host.get('Tmpfs') != {'/tmp':'rw,nosuid,nodev,noexec,size=16m'}:
            raise ReplayError('unexpected temporary filesystem')
        if host.get('LogConfig',{}).get('Type') != 'none' or host.get('RestartPolicy') != {'Name':'no','MaximumRetryCount':0}:
            raise ReplayError('container logging and restart must be disabled')
        if any(host.get(k) for k in ('Binds','Devices','VolumesFrom','PortBindings','PidMode','UTSMode')):
            raise ReplayError('unexpected host or namespace access')
        expected = {(str((pending/name).resolve()), destination, rw) for name,destination,rw in (
            ('inputs','/inputs',False), ('code','/evaluator',False), ('output','/output',True))}
        mounts = value['Mounts']
        actual = {(m['Source'],m['Destination'],m['RW']) for m in mounts if m['Type']=='bind'}
        if len(mounts) != 3 or actual != expected:
            raise ReplayError('unexpected evaluator mounts')
    except (KeyError, TypeError, ValueError) as error:
        raise ReplayError('invalid container inspection') from error


def _inventory(path):
    records = {}; total = 0
    for entry in sorted(path.rglob('*')):
        if entry.is_symlink(): raise ReplayError('symlinks forbidden in evaluator evidence')
        if entry.is_dir(): continue
        if entry == path/'manifest.json': continue
        body = _read(entry,sync=True)
        total += len(body)
        if total > MAX_TOTAL_BYTES or len(records) >= 100:
            raise ReplayError('evaluator evidence exceeds limits')
        records[str(entry.relative_to(path))] = dict(bytes=len(body), sha256=_sha(body))
    return records


def _verify_staging(pending, request):
    """Recheck copies immediately before launch and before evidence publication."""
    expected = {
        'inputs/input.json': INPUT_SHA256,
        'inputs/solution.json': request['source']['solution_sha256'],
        'inputs/source-manifest.json': request['source']['manifest_sha256'],
        'inputs/evaluation-request.json': _sha(canonical(request)),
        'code/validation.py': VALIDATOR_SHA256,
        'code/entrypoint.py': request['evaluator']['entrypoint_sha256'],
    }
    source_manifest = _json(_read(pending/'inputs/source-manifest.json',65536))
    if any(source_manifest.get(k) != v for k,v in request['source']['identity'].items()) or request['source']['input_sha256'] != INPUT_SHA256:
        raise ReplayError('staged source identity or original input binding changed')
    if request['tolerance_pu'] != 1e-7 or any(request['evaluator'].get(k) != v for k,v in dict(
            profile=PROFILE,policy=POLICY,image_id=IMAGE_ID,validator_sha256=VALIDATOR_SHA256).items()):
        raise ReplayError('staged evaluator policy changed')
    expected['inputs/request.json'] = source_manifest['request_sha256']
    for name, digest in expected.items():
        body = _read(pending/name)
        if _sha(body) != digest:
            raise ReplayError('staged evaluator material changed')
        if name in ('inputs/input.json','inputs/solution.json'):
            original_name = name.split('/')[1]
            if source_manifest['artifacts'][original_name] != dict(bytes=len(body),sha256=digest):
                raise ReplayError('staged material contradicts source manifest')
    if {p.name for p in (pending/'code').iterdir()} != {'entrypoint.py','validation.py'} or {p.name for p in (pending/'inputs').iterdir()} != {'input.json','solution.json','request.json','source-manifest.json','evaluation-request.json'}:
        raise ReplayError('staged file membership changed')


def _manifest_metadata(path, job, value, outcome):
    """Derive publication fields from individually hashed evidence artifacts."""
    request = job['request']
    _verify_staging(path,request)
    identity = _json(_read(path/'identity.json',65536)) if (path/'identity.json').exists() else job['identity']
    if any(value['Config']['Labels'].get(k) != v for k,v in job['identity']['labels'].items()) or value['Image'] != IMAGE_ID or value['Name'] != '/'+job['identity']['name']:
        raise ReplayError('exit evidence identity changed')
    if identity.get('container_id') and identity['container_id'] != value['Id']:
        raise ReplayError('exit evidence container changed')
    state = value['State']; status = outcome['execution_status']
    if state['Running'] or state['Status'] not in ('created','exited') or status not in ('succeeded','failed','timed_out','interrupted'):
        raise ReplayError('evaluator exit is not confirmed')
    if (status=='succeeded' and (state['Status']!='exited' or state['ExitCode']!=0)) or (status=='failed' and state['ExitCode']==0) or (state['Status']=='created' and status!='interrupted'):
        raise ReplayError('execution outcome contradicts exit evidence')
    if outcome['execution_exited'] is not True or outcome['exit_code'] != state['ExitCode'] or outcome['exit_inspection_sha256'] != _sha(_read(path/'exit-inspection.json')):
        raise ReplayError('terminal outcome does not match exit evidence')
    elapsed = outcome['elapsed_seconds']
    if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ReplayError('invalid elapsed time')
    result = _json(_read(path/'output/result.json',65536)) if status=='succeeded' else None
    if status=='succeeded' and not isinstance(result,dict): raise ReplayError('invalid evaluator result')
    return dict(schema='asr-isolated-material-evaluation/1',evaluation_id=job['identity']['labels']['asr.evaluation'],
        source=request['source'],request_sha256=_sha(canonical(request)),evaluator=request['evaluator'],
        execution_status=status,execution_exited=True,exit_code=state['ExitCode'],result=result,
        elapsed_seconds=elapsed,limits=LIMITS)


class Replay:
    """One local evaluation per idempotency key. No auth or budget authority."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _paths(self, key):
        if not isinstance(key, str) or not 1 <= len(key) <= 512:
            raise ValueError('bounded nonempty replay key required')
        name = _sha(key.encode())
        return self.root/(name+'.pending'), self.root/name, self.root/(name+'.lock')

    def _docker(self, arguments):
        try:
            result = subprocess.run(['docker', *arguments], capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ReplayError('Docker operation unavailable or timed out') from error
        if result.returncode or len(result.stdout) > 262144:
            raise ReplayError('Docker operation failed or exceeded output limit')
        return result.stdout.decode().strip()

    def _inspect(self, identity):
        records = _json(self._docker(['inspect',identity.get('container_id',identity['name'])]))
        if not isinstance(records, list) or len(records) != 1:
            raise ReplayError('invalid container inspection')
        value = records[0]
        if identity.get('container_id') and value['Id'] != identity['container_id']:
            raise ReplayError('container identity changed')
        if any(value['Config']['Labels'].get(k) != v for k,v in identity['labels'].items()):
            raise ReplayError('container ownership changed')
        return value

    def _exit(self, identity):
        value = self._inspect(identity)
        state = value['State']
        if state.get('Status') in ('dead','removing','restarting','paused'):
            raise ReplayError('uncertain evaluator state')
        if state['Running']:
            self._docker(['stop','--time','1',value['Id']])
            value = self._inspect(identity)
        if value['State']['Running']:
            raise ReplayError('evaluator exit unconfirmed')
        return value

    def _verified_final(self, final, request=None):
        manifest = _json(_read(final/'manifest.json',65536))
        if not isinstance(manifest,dict) or manifest.get('artifacts') != _inventory(final):
            raise ReplayError('evaluator evidence changed')
        try:
            job = _json(_read(final/'job.json',65536))
            value = _json(_read(final/'exit-inspection.json'))
            outcome = _json(_read(final/'outcome.json',65536))
            expected = _manifest_metadata(final,job,value,outcome)
            if manifest != dict(expected,artifacts=manifest['artifacts']):
                raise ReplayError('publication metadata contradicts hashed evidence')
        except (KeyError,TypeError,AttributeError,ValueError) as error:
            raise ReplayError('invalid evaluator publication metadata') from error
        if request is not None and manifest['request_sha256'] != _sha(canonical(request)):
            raise ReplayError('idempotency key reused for a different evaluation')
        return manifest

    def _publish(self, pending, final, job, status, value):
        exit_path = pending/'exit-inspection.json'
        if exit_path.exists():
            if _read(exit_path) != canonical(value):
                raise ReplayError('previous exit inspection changed')
        else:
            _write(exit_path, value)
        outcome_path = pending/'outcome.json'
        if not outcome_path.exists():
            _write(outcome_path,dict(execution_status=status,execution_exited=True,exit_code=value['State']['ExitCode'],
                exit_inspection_sha256=_sha(_read(exit_path)),elapsed_seconds=max(0,time.time()-job['started_at'])))
        outcome = _json(_read(outcome_path,65536))
        manifest = dict(_manifest_metadata(pending,job,value,outcome),artifacts=_inventory(pending))
        _write(pending/'manifest.json', manifest)
        pending.rename(final); _sync_directory(self.root)
        return self._verified_final(final)

    def run(self, key, source_path, manifest_hash, *, trial_id, execution_attempt_id, research_run_id,
            timeout_seconds=60, mode='check'):
        if type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60:
            raise ValueError('evaluation timeout must be finite in (0,60]')
        if mode not in ('check','probe'): raise ValueError('unsupported evaluator mode')
        frozen = freeze_source(source_path, manifest_hash, trial_id=trial_id,
                               execution_attempt_id=execution_attempt_id, research_run_id=research_run_id)
        validator = _read(REPO/'powerflow_lab/validation.py')
        if _sha(validator) != VALIDATOR_SHA256: raise ReplayError('trusted validator changed')
        entrypoint = _read(Path(__file__).with_name('entrypoint.py'))
        request = dict(schema='asr-material-recheck-request/1', mode=mode, timeout_seconds=timeout_seconds,
            tolerance_pu=1e-7, source={k:v for k,v in frozen.items() if k != 'files'},
            evaluator=dict(profile=PROFILE, policy=POLICY, image_id=IMAGE_ID,
                           validator_sha256=VALIDATOR_SHA256, entrypoint_sha256=_sha(entrypoint)))
        pending, final, lock_path = self._paths(key)
        with lock_path.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if pending.exists(): raise UnresolvedReplay('pending evaluation requires explicit reconciliation')
            if final.exists(): return self._verified_final(final, request)
            pending.mkdir(mode=0o700)
            for name in ('inputs','code','output'): (pending/name).mkdir()
            (pending/'output').chmod(0o777)
            for name,body in frozen['files'].items():
                _write(pending/'inputs'/name,body)
                if _read(pending/'inputs'/name) != body: raise ReplayError('staged source changed')
                (pending/'inputs'/name).chmod(0o444)
            _write(pending/'inputs/evaluation-request.json',request)
            _write(pending/'code/validation.py',validator); _write(pending/'code/entrypoint.py',entrypoint)
            for name in ('inputs','code'):
                for item in (pending/name).iterdir(): item.chmod(0o444)
                (pending/name).chmod(0o555)
            identity = dict(name='asr-eval-'+uuid.uuid4().hex)
            identity['labels'] = {'asr.evaluation':identity['name'][9:], 'asr.owner':'isolated-material-evaluator'}
            job = dict(request=request, identity=identity, started_at=time.time())
            _write(pending/'job.json',job)  # Persist deterministic name before Docker create.
            try:
                arguments = ['create','--name',identity['name'],'--network','none','--read-only',
                    '--cap-drop','ALL','--security-opt','no-new-privileges','--user','65532:65532',
                    '--pids-limit','32','--memory','256m','--memory-swap','256m','--cpus','1',
                    '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=16m','--log-driver','none',
                    '-e','HOME=/tmp','-e','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python3']
                for k,v in identity['labels'].items(): arguments += ['--label',k+'='+v]
                for name,destination,readonly in [('inputs','/inputs',True),('code','/evaluator',True),('output','/output',False)]:
                    arguments += ['--mount',f'type=bind,src={pending/name},dst={destination}'+(',readonly' if readonly else '')]
                identity['container_id'] = self._docker(arguments+[IMAGE_ID,'-I','-S','/evaluator/entrypoint.py'])
                _write(pending/'identity.json',identity)
                value = self._inspect(identity)
                verify_container(value,identity,pending)
                _verify_staging(pending,request)
                _write(pending/'launch-inspection.json',value)
                self._docker(['start',identity['container_id']])
                deadline = time.monotonic()+timeout_seconds
                while True:
                    value = self._inspect(identity)
                    if not value['State']['Running']:
                        status = 'succeeded' if value['State']['ExitCode']==0 else 'failed'
                        break
                    if time.monotonic() >= deadline:
                        value = self._exit(identity); status = 'timed_out'; break
                    time.sleep(.05)
                return self._publish(pending,final,job,status,value)
            except Exception as error:
                # A timeout/error of the Docker CLI is not evidence of daemon or
                # container exit. Persist pending material and require reconcile.
                if not (pending/'uncertain.json').exists():
                    _write(pending/'uncertain.json',dict(reason=type(error).__name__))
                raise UnresolvedReplay('evaluation unresolved; pending evidence retained') from error

    def reconcile(self, key):
        pending, final, lock_path = self._paths(key)
        with lock_path.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if final.exists(): return self._verified_final(final)
            if not pending.exists(): raise ReplayError('no pending evaluation')
            if (pending/'manifest.json').exists():
                self._verified_final(pending)
                pending.rename(final); _sync_directory(self.root)
                return self._verified_final(final)
            job = _json(_read(pending/'job.json',65536))
            identity = _json(_read(pending/'identity.json',65536)) if (pending/'identity.json').exists() else job['identity']
            try:
                value = self._exit(identity)
                checked_identity = dict(identity,container_id=value['Id'])
                verify_container(value,checked_identity,pending)
                return self._publish(pending,final,job,'interrupted',value)
            except Exception as error:
                raise UnresolvedReplay('evaluation remains unresolved; pending evidence retained') from error
