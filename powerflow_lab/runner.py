"""Local single-host evidence runner. Not the future ASR control/budget service.

A trusted executor writes flat files into an attempt directory and must finish
all child work before returning. Failed publication remains recoverable. An
unfinished executor requires explicit process reconciliation, never auto-retry.
"""
import copy
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import time
import uuid


class EvidenceError(RuntimeError):
    pass


class ExecutionUncertain(EvidenceError):
    """External execution may still be active; preserve unresolved attempt."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _inventory(path):
    records = {}
    total = 0
    for item in sorted(path.iterdir()):
        if item.name == 'manifest.json':
            continue
        if item.is_symlink() or not item.is_file():
            raise EvidenceError('only regular flat output files allowed')
        total += item.stat().st_size
        if total > 100 * 1024 * 1024 or len(records) >= 100:
            raise EvidenceError('output exceeds local publication limit')
        with item.open('rb') as stream:
            os.fsync(stream.fileno())
        records[item.name] = {'sha256': digest(item), 'bytes': item.stat().st_size}
    return records


def _verify(path):
    manifest = path / 'manifest.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise EvidenceError('missing regular manifest')
    value = json.loads(manifest.read_text())
    if not re.fullmatch(r'[0-9]{4}_[a-f0-9]{32}', value['attempt_id']):
        raise EvidenceError('invalid attempt identity')
    execution = json.loads((path / 'execution.json').read_text())
    if execution['attempt_id'] != value['attempt_id']:
        raise EvidenceError('attempt identity changed')
    if path.name != '.pending' and path.name != value['attempt_id']:
        raise EvidenceError('attempt path changed')
    if value['artifacts'] != _inventory(path):
        raise EvidenceError('artifact hash, size or membership changed')
    request = json.loads((path.parent.parent / 'request.json').read_text())
    if value['request_hash'] != hashlib.sha256(canonical(request['request'])).hexdigest():
        raise EvidenceError('request identity changed')
    if value['trial_id'] != path.parent.parent.name:
        raise EvidenceError('trial identity changed')
    return value


def publish_attempt(pending, final):
    if final.exists():
        raise EvidenceError('attempt already exists')
    pending.rename(final)
    _sync_directory(final.parent)


def _trial_path(root, key):
    if not isinstance(key, str) or not key:
        raise ValueError('nonempty request key required')
    return Path(root).resolve() / hashlib.sha256(key.encode()).hexdigest()


def verify_trial(root, key):
    trial = _trial_path(root, key)
    attempts = sorted((trial / 'attempts').glob('[0-9]*'))
    if not attempts:
        raise EvidenceError('no published attempt')
    results = [_verify(path) for path in attempts]
    return results[-1]


def run_trial(root, key, request, executor, *, retry=False, replay_of=None):
    """Execute once per request key; explicit retries keep every prior attempt."""
    payload = canonical(request)  # Reject non-JSON/non-finite requests before admission.
    request_hash = hashlib.sha256(payload).hexdigest()
    trial = _trial_path(root, key)
    trial.mkdir(parents=True, exist_ok=True)
    with (trial / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        request_path = trial / 'request.json'
        record = dict(request=request, replay_of=replay_of)
        if request_path.exists():
            if canonical(json.loads(request_path.read_text())) != canonical(record):
                raise EvidenceError('idempotency key reused for different request')
        else:
            _write(request_path, record)
        attempts = trial / 'attempts'
        attempts.mkdir(exist_ok=True)
        pending = attempts / '.pending'
        if pending.exists():
            if not (pending / 'manifest.json').exists():
                raise EvidenceError('unfinished attempt: reconcile external process before retry')
            recovered = _verify(pending)
            publish_attempt(pending, attempts / recovered['attempt_id'])
        existing = sorted(attempts.glob('[0-9]*'))
        if existing:
            previous = verify_trial(root, key)
            if not retry:
                return previous
        attempt_id = f'{len(existing) + 1:04d}_{uuid.uuid4().hex}'
        pending.mkdir()
        start = time.time()
        _write(pending / 'execution.json', {'attempt_id': attempt_id, 'started_at': start})
        try:
            outcome = executor(pending, copy.deepcopy(request))
            if outcome.get('status') not in ('succeeded', 'failed', 'timed_out', 'cancelled', 'interrupted'):
                raise ValueError('executor returned invalid status')
        except ExecutionUncertain:
            raise
        except Exception as exc:
            outcome = {'status': 'failed', 'exit_code': None, 'error': f'{type(exc).__name__}: {exc}'}
        # BaseException leaves a visibly unresolved attempt; no process-state guessing.
        artifacts = _inventory(pending)
        manifest = dict(schema='asr-local-trial/1', trial_id=trial.name, attempt_id=attempt_id,
                        request_hash=request_hash, replay_of=replay_of, started_at=start,
                        finished_at=time.time(), outcome=outcome, status=outcome['status'], artifacts=artifacts)
        _write(pending / 'manifest.json', manifest)
        publish_attempt(pending, attempts / attempt_id)
        return manifest
