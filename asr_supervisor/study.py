"""Isolated study worker backend for the existing fenced Supervisor.

No admission, scheduler, credential, or hidden-test access is implemented here.
Only a controller-frozen payload and a configured immutable image are accepted.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess

from powerflow_lab.runner import canonical, digest
from .candidate import CandidateBackend
from .resources import LimitViolation, limit_event

PROFILE = 'ood-study-worker/1'
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
PREFIX = b'ASR_OOD_EVENT_V1:'


def frozen_payload(path, sha256, *, operations=('label','fit','analysis')):
    path = Path(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
            raise ValueError('regular single-link study payload required')
        body = stream.read(MAX_PAYLOAD_BYTES + 1)
    if len(body) > MAX_PAYLOAD_BYTES:
        raise LimitViolation(limit_event('study', 'study_payload_limit', 'study_payload_bytes',
            MAX_PAYLOAD_BYTES, len(body), 'bytes', 'admission', 'submission_rejected',
            'Preserve the research task. Split the batch or obtain a reviewed larger profile.', kind='at_least'))
    if hashlib.sha256(body).hexdigest() != sha256:
        raise ValueError('study payload hash mismatch')
    value = json.loads(body)
    canonical(value)  # Reject NaN/Infinity even though json.loads accepts them.
    if set(value) != {'request', 'materials'} or value['request'].get('operation') not in operations:
        raise ValueError('unsupported study payload')
    return body


class StudyBackend(CandidateBackend):
    worker_module = 'research_projects.ood_augmentation.worker'
    output_bytes = MAX_OUTPUT_BYTES
    profile = PROFILE
    operations = ('label','fit','analysis')

    def __init__(self, image_id):
        super().__init__()
        if re.fullmatch(r'sha256:[a-f0-9]{64}', image_id) is None:
            raise ValueError('immutable scientific image ID required')
        self.image_id = image_id

    def validate_request(self, request):
        if set(request) != {'profile', 'image_id', 'payload_path', 'payload_sha256', 'timeout_seconds'}:
            raise ValueError('invalid study execution request')
        if request['profile'] != self.profile or request['image_id'] != self.image_id:
            raise ValueError('study image/profile mismatch')
        timeout = request['timeout_seconds']
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError('study timeout must be finite in (0,300] seconds')
        frozen_payload(request['payload_path'], request['payload_sha256'],operations=self.operations)

    @classmethod
    def identity(cls, record):
        request = record['dispatch']['execution_request']
        return dict(backend='docker-study', name='asr-managed-' + record['attempt'],
                    labels={'asr.attempt': record['attempt'], 'asr.trial': record['trial'],
                            'asr.run': record['run'], 'asr.epoch': str(record['epoch']),
                            'asr.profile': cls.profile, 'asr.payload': request['payload_sha256']})

    def create(self, record, path, request):
        self.validate_request(request)
        identity = self.identity(record)
        (path / 'study-input.json').write_bytes(frozen_payload(request['payload_path'], request['payload_sha256'],operations=self.operations))
        (path / 'study-input.json').chmod(0o444)
        arguments = ['create', '--name', identity['name'], '--network', 'none', '--read-only',
                     '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '65532:65532',
                     '--pids-limit', '64', '--memory', '1g', '--memory-swap', '1g', '--cpus', '1',
                     '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=128m', '--log-driver', 'none',
                     '--entrypoint', 'python3', '-e', 'HOME=/tmp', '--mount',
                     f'type=bind,src={(path / "study-input.json").resolve()},dst=/input.json,readonly']
        for key, value in identity['labels'].items():
            arguments += ['--label', key + '=' + value]
        identity['container_id'] = self._call(arguments + [self.image_id, '-m',
            self.worker_module, '--input', '/input.json'])
        inspected = self._raw_inspect(identity)
        self.verify_container(inspected, identity, path)
        (path / 'container-inspection.json').write_bytes(canonical(inspected))
        return identity

    def verify_container(self, value, identity, path):
        config = value['Config']; host = value['HostConfig']
        if (value['Image'] != self.image_id or config['Image'] != self.image_id or
            config['User'] != '65532:65532' or config['Entrypoint'] != ['python3'] or
            config['Cmd'] != ['-m', self.worker_module, '--input', '/input.json']):
            raise RuntimeError('study executable policy mismatch')
        mounts = value['Mounts']
        if (len(mounts) != 1 or mounts[0]['Type'] != 'bind' or mounts[0]['RW'] or
            mounts[0]['Source'] != str((path / 'study-input.json').resolve()) or mounts[0]['Destination'] != '/input.json'):
            raise RuntimeError('unexpected study mounts')
        exact = dict(NetworkMode='none', ReadonlyRootfs=True, Privileged=False, Memory=1073741824,
                     MemorySwap=1073741824, NanoCpus=1000000000, PidsLimit=64)
        if (any(host.get(k) != v for k, v in exact.items()) or host.get('CapAdd') or
            host.get('CapDrop') != ['ALL'] or host.get('SecurityOpt') not in (['no-new-privileges'], ['no-new-privileges:true']) or
            host.get('Tmpfs') != {'/tmp': 'rw,nosuid,nodev,noexec,size=128m'} or
            host.get('LogConfig', {}).get('Type') != 'none' or
            host.get('RestartPolicy') != {'Name': 'no', 'MaximumRetryCount': 0} or
            any(host.get(k) for k in ('Binds', 'Devices', 'VolumesFrom', 'PortBindings', 'PidMode', 'UTSMode'))):
            raise RuntimeError('study isolation/resource policy mismatch')
        env = dict(item.split('=', 1) for item in config['Env'])
        allowed = {'PATH', 'LANG', 'GPG_KEY', 'PYTHON_VERSION', 'PYTHON_SHA256', 'OPENBLAS_NUM_THREADS',
                   'OMP_NUM_THREADS', 'HOME', 'MPLCONFIGDIR', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE'}
        if set(env) - allowed or env.get('HOME') != '/tmp' or env.get('PYTHONPATH') != '/opt/asr/source':
            raise RuntimeError('unexpected study environment')

    def finalize(self, path, request, status):
        identity = json.loads((path / 'identity.json').read_text())
        collector = self.collectors.get(identity['container_id'])
        if collector:
            collector['thread'].join(timeout=2)
            process = collector['process']
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=1)
            collector['thread'].join(timeout=1)
            if collector['thread'].is_alive():
                raise RuntimeError('study capture unresolved')
        inspected = self._raw_inspect(identity)
        if inspected['State']['Running']:
            raise RuntimeError('study exit unconfirmed')
        self.verify_container(inspected, identity, path)
        (path / 'study-exit.json').write_bytes(canonical(inspected))
        if digest(path / 'study-input.json') != request['payload_sha256']:
            raise ValueError('study frozen material changed')
        capture = dict(collector_available=collector is not None, max_bytes=self.output_bytes,
                       overflow=bool(collector and collector['overflow']), error=bool(collector and collector['error']),
                       observed_bytes=collector['observed_bytes'] if collector else None)
        (path / 'capture.json').write_bytes(canonical(capture))
        diagnostics = []
        if capture['overflow']:
            diagnostics.append(limit_event('study', 'study_output_limit', 'study_output_bytes', self.output_bytes,
                capture['observed_bytes'], 'bytes', 'running', 'container_stopped',
                'Retain partial sample events and cost. Reduce batch size before a new admitted attempt.', kind='at_least'))
        if inspected['State'].get('OOMKilled'):
            diagnostics.append(limit_event('study', 'study_memory_limit', 'study_memory_bytes', 1073741824,
                None, 'bytes', 'running', 'container_oom_killed',
                'Retain partial evidence and cost. Reduce the batch or request a reviewed resource revision.', kind='oom_kill_observed'))
        if capture['error'] or not collector:
            diagnostics.append(dict(code='study_capture_incomplete', task_retained=True,
                                    recovery='Preserve partial evidence; reconcile before resubmitting.'))
        if diagnostics:
            (path / 'resource-events.json').write_bytes(canonical(diagnostics))
        events = []
        try:
            raw = (path / 'candidate-stream.log').read_bytes()
            for line in raw.splitlines(keepends=True):
                if line.startswith(PREFIX) and line.endswith(b'\n'):
                    events.append(json.loads(line[len(PREFIX):]))
            (path / 'study-events.json').write_bytes(canonical(events))
            if status != 'succeeded':
                return
            if diagnostics or not events or events[-1].get('type') != 'result':
                raise ValueError('study output incomplete')
            if sum(e.get('type') == 'result' for e in events) != 1 or any(e.get('type') == 'error' for e in events):
                raise ValueError('ambiguous study output')
            payload = json.loads((path / 'study-input.json').read_text())
            if payload['request']['operation'] == 'label':
                count = len(payload['request']['coordinates'])
                if [e.get('index') for e in events[:-1]] != list(range(count)) or events[-1]['result']['proposed'] != count:
                    raise ValueError('incomplete proposal evidence')
            (path / 'study-result.json').write_bytes(canonical(events[-1]['result']))
        except (OSError, ValueError, KeyError, TypeError) as error:
            (path / 'study-output-error.json').write_bytes(canonical(dict(error_type=type(error).__name__,
                message=str(error), task_retained=True)))
            return dict(status='failed')
