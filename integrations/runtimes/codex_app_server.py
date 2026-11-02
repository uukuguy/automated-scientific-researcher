"""Bounded native Codex App Server stdio foundation, checked with CLI 0.166.0.

Protocol: https://developers.openai.com/codex/app-server/
Wire messages are JSONL JSON-RPC without the ``jsonrpc`` member. This module is
transport plumbing, not AAR integration, experiment admission, sandbox proof or
subscription inference acceptance. It never reads credentials or logs protocol
payloads. Default launch requests native ChatGPT auth and strips ambient API keys;
existing CODEX_HOME/config/plugins are inherited and have not been scoped here.
"""
from collections import deque
from concurrent.futures import Future, TimeoutError as FutureTimeout
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import threading
import time


class AppServerClosed(RuntimeError):
    pass


class AppServerProtocolError(RuntimeError):
    pass


class AppServerTimeout(TimeoutError):
    pass


class AppServerRemoteError(RuntimeError):
    def __init__(self, error):
        self.code = error.get('code')
        self.data = error.get('data')
        super().__init__(error.get('message', 'App Server request rejected'))


_UNSET = object()


def subscription_environment():
    """Preserve native login location/proxy, exclude ambient paid API credentials."""
    allowed = ('PATH', 'HOME', 'CODEX_HOME', 'TMPDIR', 'LANG', 'LC_ALL',
               'SSL_CERT_FILE', 'SSL_CERT_DIR', 'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY')
    return {key: os.environ[key] for key in allowed if key in os.environ}


def _positive_seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('finite positive timeout required')
    return value


def _valid_id(value):
    return type(value) in (int, str)


class CodexAppServerClient:
    """One finite POSIX child process and connection; no automatic retries.

    Default server requests are rejected, including approvals. Explicit ``manual``
    mode requires the caller to consume/respond to requests within the connection
    deadline. Generation is disabled unless ``allow_model_turns`` is explicitly
    enabled. This is only a convenience gate for known generation methods: raw
    request() can invoke other native methods, including code execution. It is
    not an authorization boundary, inference-proof allowlist or ASR reservation.
    ``command`` overrides are for an explicitly selected executable/test fixture;
    they do not inherit the native command's auth configuration guarantees.
    """
    def __init__(self, *, cwd, command=None, walltime_seconds=30, request_timeout=5,
                 server_request_mode='reject', allow_model_turns=False,
                 max_message_bytes=1048576, max_events=256, max_buffer_bytes=8388608,
                 max_messages=4096, max_pending_requests=32):
        _positive_seconds(walltime_seconds); _positive_seconds(request_timeout)
        for limit in (max_message_bytes, max_events, max_buffer_bytes, max_messages, max_pending_requests):
            if type(limit) is not int or limit < 1: raise ValueError('positive integer transport limits required')
        if server_request_mode not in ('reject', 'manual'): raise ValueError('invalid server request mode')
        self.request_timeout = request_timeout
        self.deadline = time.monotonic() + walltime_seconds
        self.server_request_mode = server_request_mode
        self.allow_model_turns = allow_model_turns
        self.max_message_bytes = max_message_bytes
        self.max_events = max_events
        self.max_buffer_bytes = max_buffer_bytes
        self.max_messages = max_messages
        self.max_pending_requests = max_pending_requests
        self._condition = threading.Condition()
        self._write_lock = threading.Lock()
        self._closed = threading.Event()
        self._closing = False
        self._state = 'new'
        self._failure = None
        self._sequence = 0
        self._pending = {}
        self._incoming_pending = set()
        self._events = deque()
        self._server_requests = deque()
        self._buffer_bytes = 0
        self._stderr_bytes = 0
        self._readers = []
        self._startup_complete = threading.Event()
        argv = command if command is not None else [
            'codex', 'app-server', '--listen', 'stdio://',
            '-c', 'model_provider="openai"', '-c', 'forced_login_method="chatgpt"',
        ]
        if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(x, str) or not x for x in argv):
            raise ValueError('explicit executable argument list required')
        self.process = subprocess.Popen(argv, cwd=Path(cwd).resolve(), env=subscription_environment(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            os.set_blocking(stream.fileno(), False)
        self._readers = [threading.Thread(target=self._read_stdout, daemon=True),
                         threading.Thread(target=self._drain_stderr, daemon=True)]
        try:
            for reader in self._readers: reader.start()
        except Exception as error:
            self._startup_complete.set(); self.close(error=error); raise
        self._startup_complete.set()
        self._watchdog = threading.Thread(target=self._watch, daemon=True)
        self._watchdog.start()

    def __enter__(self): return self

    def __exit__(self, *error): self.close()

    def _watch(self):
        if not self._closed.wait(max(0, self.deadline-time.monotonic())):
            self.close(error=AppServerTimeout('App Server connection deadline exceeded'))

    def _live(self):
        if self._closing:
            raise AppServerClosed('App Server connection is closed') from self._failure

    def _limit_deadline(self, timeout):
        duration = self.request_timeout if timeout is None else _positive_seconds(timeout)
        return min(self.deadline, time.monotonic()+duration)

    def _write(self, record, deadline):
        encoded = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()+b'\n'
        if len(encoded) > self.max_message_bytes: raise ValueError('outgoing protocol message too large')
        if not self._write_lock.acquire(timeout=max(0, deadline-time.monotonic())):
            raise AppServerTimeout('App Server write deadline exceeded')
        try:
            self._live()
            selector = selectors.DefaultSelector()
            try:
                selector.register(self.process.stdin, selectors.EVENT_WRITE)
                remaining = memoryview(encoded)
                while remaining:
                    self._live()
                    wait = deadline-time.monotonic()
                    if wait <= 0: raise AppServerTimeout('App Server write deadline exceeded')
                    if not selector.select(min(wait, .1)): continue
                    try: count = os.write(self.process.stdin.fileno(), remaining)
                    except BlockingIOError: continue
                    remaining = remaining[count:]
            finally: selector.close()
        finally: self._write_lock.release()

    def initialize(self, client_info=None, *, timeout=None):
        with self._condition:
            self._live()
            if self._state != 'new': raise RuntimeError('initialize exactly once per connection')
            self._state = 'initializing'
        info = client_info or {'name':'asr_native_foundation', 'title':'ASR Native Runtime Foundation', 'version':'0.1.0'}
        result = self._exchange('initialize', {'clientInfo':info}, timeout=timeout)
        try: self._write({'method':'initialized', 'params':{}}, self._limit_deadline(timeout))
        except Exception as error:
            self.close(error=error); raise
        with self._condition: self._state = 'ready'
        return result

    def request(self, method, params=None, *, timeout=None):
        if not isinstance(method, str) or not method: raise ValueError('method required')
        with self._condition:
            self._live()
            if self._state != 'ready': raise RuntimeError('initialize before requests')
        if method == 'initialize': raise RuntimeError('use initialize exactly once')
        if method in ('turn/start', 'turn/steer', 'review/start', 'thread/goal/set') and not self.allow_model_turns:
            raise PermissionError('model generation requires explicit runtime authorization')
        return self._exchange(method, {} if params is None else params, timeout=timeout)

    def _exchange(self, method, params, *, timeout):
        deadline = self._limit_deadline(timeout)
        future = Future()
        with self._condition:
            self._live()
            if len(self._pending) >= self.max_pending_requests: raise ValueError('too many pending requests')
            self._sequence += 1
            identity = 'asr-'+str(self._sequence)
            self._pending[identity] = future
        try:
            self._write({'id':identity, 'method':method, 'params':params}, deadline)
            try: return future.result(timeout=max(0, deadline-time.monotonic()))
            except FutureTimeout:
                if future.done(): raise
                error = AppServerTimeout('App Server request deadline exceeded: '+method)
                self.close(error=error)
                raise error
        except (AppServerRemoteError,): raise
        except Exception as error:
            self.close(error=error)
            raise
        finally:
            with self._condition: self._pending.pop(identity, None)

    def _enqueue(self, target, record, size):
        with self._condition:
            if len(target) >= self.max_events or self._buffer_bytes+size > self.max_buffer_bytes:
                raise AppServerProtocolError('unconsumed App Server stream exceeded buffer limits')
            target.append((size, record)); self._buffer_bytes += size
            self._condition.notify_all()

    def _dispatch(self, record, size):
        if not isinstance(record, dict): raise AppServerProtocolError('protocol record must be an object')
        if 'method' in record:
            if not isinstance(record['method'], str): raise AppServerProtocolError('invalid protocol method')
            if 'id' not in record:
                self._enqueue(self._events, record, size); return
            identity = record['id']
            if not _valid_id(identity): raise AppServerProtocolError('invalid server request id')
            if self.server_request_mode == 'reject':
                self._write({'id':identity, 'error':{'code':-32601, 'message':'Server request unsupported by this client'}}, self._limit_deadline(None))
                return
            with self._condition:
                if identity in self._incoming_pending: raise AppServerProtocolError('duplicate server request id')
                if len(self._incoming_pending) >= self.max_pending_requests: raise AppServerProtocolError('too many server requests')
                self._incoming_pending.add(identity)
            self._enqueue(self._server_requests, record, size); return
        identity = record.get('id')
        if not _valid_id(identity) or ('result' in record) == ('error' in record):
            raise AppServerProtocolError('invalid App Server response')
        with self._condition: future = self._pending.pop(identity, None)
        if future is None: raise AppServerProtocolError('uncorrelated App Server response')
        if 'error' in record:
            if not isinstance(record['error'], dict):
                future.set_exception(AppServerProtocolError('invalid remote error')); return
            future.set_exception(AppServerRemoteError(record['error']))
        else: future.set_result(record['result'])

    def _read_stdout(self):
        self._startup_complete.wait()
        if self._closing: return
        selector = selectors.DefaultSelector(); buffer = bytearray(); count = 0
        try:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while not self._closing:
                if not selector.select(.1): continue
                try: chunk = os.read(self.process.stdout.fileno(), 65536)
                except BlockingIOError: continue
                if not chunk:
                    if buffer: raise AppServerProtocolError('incomplete JSONL protocol record')
                    raise AppServerClosed('App Server process closed stdout')
                buffer.extend(chunk)
                while b'\n' in buffer:
                    index = buffer.index(b'\n')
                    if index+1 > self.max_message_bytes: raise AppServerProtocolError('protocol message too large')
                    raw = bytes(buffer[:index]); del buffer[:index+1]
                    count += 1
                    if count > self.max_messages: raise AppServerProtocolError('protocol message count exceeded')
                    try: record = json.loads(raw)
                    except (ValueError, UnicodeDecodeError) as error: raise AppServerProtocolError('invalid JSONL protocol record') from error
                    self._dispatch(record, len(raw)+1)
                if len(buffer) > self.max_message_bytes: raise AppServerProtocolError('protocol message too large')
        except Exception as error:
            if not self._closing: self.close(error=error)
        finally: selector.close()

    def _drain_stderr(self):
        self._startup_complete.wait()
        if self._closing: return
        selector = selectors.DefaultSelector()
        try:
            selector.register(self.process.stderr, selectors.EVENT_READ)
            while not self._closing:
                if not selector.select(.1): continue
                try: data = os.read(self.process.stderr.fileno(), 65536)
                except BlockingIOError: continue
                if not data: return
                # Discard raw diagnostics: providers may include sensitive values.
                self._stderr_bytes = min(2**63-1, self._stderr_bytes+len(data))
        except OSError: pass
        finally: selector.close()

    def _take(self, target, timeout):
        deadline = self._limit_deadline(timeout)
        with self._condition:
            while not target:
                self._live()
                remaining = deadline-time.monotonic()
                if remaining <= 0: raise AppServerTimeout('App Server event wait deadline exceeded')
                self._condition.wait(remaining)
            size, record = target.popleft(); self._buffer_bytes -= size
            return record

    def next_event(self, *, timeout=None): return self._take(self._events, timeout)

    def next_server_request(self, *, timeout=None):
        if self.server_request_mode != 'manual': raise RuntimeError('server requests are rejected by default')
        return self._take(self._server_requests, timeout)

    def respond(self, identity, *, result=_UNSET, error=_UNSET, timeout=None):
        if (result is _UNSET) == (error is _UNSET): raise ValueError('provide exactly one result or error')
        with self._condition:
            self._live()
            if identity not in self._incoming_pending: raise ValueError('server request is not awaiting a response')
            self._incoming_pending.remove(identity)
        try: self._write({'id':identity, **({'result':result} if error is _UNSET else {'error':error})}, self._limit_deadline(timeout))
        except Exception as failure:
            self.close(error=failure); raise

    def start_thread(self, *, timeout=None, **params):
        if params.get('modelProvider', 'openai') != 'openai': raise PermissionError('paid provider fallback is not authorized')
        return self.request('thread/start', {'sandbox':'read-only', 'approvalPolicy':'never', **params}, timeout=timeout)

    def resume_thread(self, thread_id, *, timeout=None, **params):
        if not isinstance(thread_id, str) or not thread_id: raise ValueError('thread id required')
        if 'threadId' in params: raise ValueError('thread id cannot be overridden')
        if params.get('modelProvider', 'openai') != 'openai': raise PermissionError('paid provider fallback is not authorized')
        return self.request('thread/resume', {'threadId':thread_id, 'sandbox':'read-only', 'approvalPolicy':'never', **params}, timeout=timeout)

    def start_turn(self, thread_id, input, *, timeout=None, **params):
        if not isinstance(thread_id, str) or not thread_id or not isinstance(input, list): raise ValueError('thread id and input list required')
        if 'threadId' in params or 'input' in params: raise ValueError('turn identity/input cannot be overridden')
        return self.request('turn/start', {'threadId':thread_id, 'input':input, **params}, timeout=timeout)

    def interrupt_turn(self, thread_id, turn_id, *, timeout=None):
        if any(not isinstance(value, str) or not value for value in (thread_id, turn_id)): raise ValueError('thread and turn ids required')
        return self.request('turn/interrupt', {'threadId':thread_id, 'turnId':turn_id}, timeout=timeout)

    def close(self, *, error=None):
        with self._condition:
            first = not self._closing
            if first:
                self._closing = True
                self._failure = error or AppServerClosed('App Server connection closed')
                pending = list(self._pending.values()); self._pending.clear()
        if not first:
            if threading.current_thread() not in self._readers: self._closed.wait(2)
            return {'direct_child_exited':self.process.poll() is not None, 'exit_code':self.process.poll()}
        try:
            try: self.process.stdin.close()
            except OSError: pass
            try: self.process.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                try: os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: self.process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    try: os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    self.process.wait(timeout=.5)
        finally:
            try:
                for future in pending:
                    if not future.done(): future.set_exception(self._failure)
                with self._condition: self._condition.notify_all()
                for reader in self._readers:
                    if reader.ident is not None and reader is not threading.current_thread(): reader.join(timeout=.2)
                for stream, reader in zip((self.process.stdout, self.process.stderr), self._readers):
                    if not reader.is_alive() or reader is threading.current_thread(): stream.close()
            finally:
                self._closed.set()
        return {'direct_child_exited':self.process.poll() is not None, 'exit_code':self.process.poll()}
