"""Replaceable subscription runtime using pi 1.0.0's documented JSONL RPC.

This adapter owns one bounded session, never a research scheduler. OS isolation
for arbitrary coding tools belongs to the execution supervisor, not this module.
"""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import threading
import time


class RuntimeFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    walltime_seconds: float
    turns: int
    tool_executions: int

    def __post_init__(self):
        if isinstance(self.walltime_seconds, bool) or not isinstance(self.walltime_seconds,(int,float)) or not math.isfinite(self.walltime_seconds) or self.walltime_seconds <= 0:
            raise ValueError('finite_positive_walltime_required')
        if any(type(n) is not int or n <= 0 for n in (self.turns,self.tool_executions)):
            raise ValueError('positive_integer_limits_required')


def prepare_oauth(source: Path, config_dir: Path):
    """Copy only Codex OAuth into private runtime config; never resolve API keys.

    The runtime keeps refreshes in its own directory. Reusing that directory on
    recovery preserves refreshed credentials without rewriting the user's store.
    """
    config_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=config_dir/'auth.json'
    data=json.loads((target if target.exists() else source).read_text())
    auth=data.get('openai-codex',{})
    if auth.get('type') != 'oauth':
        raise RuntimeFailure('codex_subscription_oauth_required')
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as stream: json.dump({'openai-codex':auth},stream)
    (config_dir/'settings.json').write_text(json.dumps({'retry':{'enabled':False},'compaction':{'enabled':False}}))


class PiRuntime:
    provider='openai-codex'

    def __init__(self, *, executable='pi', model, thinking='high', expected_version='1.5.0'):
        if not isinstance(model,str) or not model or ':' in model or '/' in model:
            raise ValueError('explicit_codex_model_id_required')
        self.executable=executable
        self.model=model
        self.thinking=thinking
        self.expected_version=expected_version

    def run(self, *, workspace, config_dir, session_id, prompt, limits, bridge_url, bridge_token, on_event=None, should_stop=None,on_process=None,on_launch=None):
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?',session_id):
            raise ValueError('invalid_native_session_id')
        version=subprocess.check_output([self.executable,'--version'],text=True,timeout=10).strip()
        if version!=self.expected_version: raise RuntimeFailure('runtime_version_mismatch')
        workspace=Path(workspace).resolve(); config_dir=Path(config_dir).resolve()
        sessions=config_dir/'sessions'; sessions.mkdir(exist_ok=True)
        extension=Path(__file__).with_name('asr-extension.mjs').resolve()
        # Allowlist avoids ambient paid credentials and arbitrary shell startup hooks.
        env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR','HTTPS_PROXY','HTTP_PROXY','NO_PROXY') if k in os.environ}
        env['GIT_CEILING_DIRECTORIES']=str(workspace.parent)
        env['ASR_WORKSPACE']=str(workspace)
        env['ASR_OWNED_PROCESS_GROUP']='1'
        env['ASR_SKILL_PATH']=str(Path(__file__).with_name('skills')/'scientific-reasoning'/'SKILL.md')
        env.update(PI_CODING_AGENT_DIR=str(config_dir),PI_OFFLINE='1',ASR_BRIDGE_URL=bridge_url,ASR_BRIDGE_TOKEN=bridge_token,
                   ASR_MAX_TURNS=str(limits.turns),ASR_MAX_TOOLS=str(limits.tool_executions),ASR_DEADLINE_MS=str(int((time.time()+limits.walltime_seconds)*1000)))
        argv=[self.executable,'--mode','rpc','--provider',self.provider,'--model',self.model,'--thinking',self.thinking,
              '--session-id',session_id,'--session-dir',str(sessions),'--no-extensions','--extension',str(extension),
              '--no-skills','--skill',str(Path(__file__).with_name('skills')/'scientific-reasoning'/'SKILL.md'),'--no-prompt-templates','--no-context-files','--tools','asr,read,write,edit,grep,find,ls']
        if on_launch: on_launch()
        process=subprocess.Popen(argv,cwd=workspace,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        records=queue.Queue(); stderr=[]
        def read_stdout():
            try:
                for line in process.stdout:
                    try: records.put(json.loads(line))
                    except (ValueError,UnicodeDecodeError): records.put({'type':'protocol_error'})
            finally: records.put(None)
        def drain_stderr():
            for line in process.stderr:
                # Diagnostics are deliberately not returned or persisted: providers
                # and extensions can put credentials in error text.
                if len(stderr)<20: stderr.append(len(line))
        readers=[threading.Thread(target=read_stdout,daemon=True),threading.Thread(target=drain_stderr,daemon=True)]
        for reader in readers: reader.start()
        def send(command):
            process.stdin.write(json.dumps(command).encode()+b'\n'); process.stdin.flush()
        status='interrupted'; state=None; assistant=[]; turns=tools=0; started=time.monotonic(); settled=False
        try:
            if on_process:
                from .process import identify
                on_process(identify(process.pid))
            send({'id':'state','type':'get_state'})
            while True:
                if should_stop and should_stop(): status='cancelled'; break
                remaining=limits.walltime_seconds-(time.monotonic()-started)
                if remaining<=0: status='timed_out'; break
                try: record=records.get(timeout=min(.1,remaining))
                except queue.Empty: continue
                if record is None: break
                kind=record.get('type')
                if on_event: on_event(record)
                if kind=='protocol_error': status='protocol_error'; break
                if kind=='response' and record.get('id')=='state':
                    if not record.get('success'): status='startup_failed'; break
                    state=record['data']
                    model=state.get('model',{})
                    if model.get('provider')!=self.provider or model.get('id')!=self.model:
                        status='model_mismatch'; break
                    send({'id':'prompt','type':'prompt','message':prompt})
                if kind=='response' and record.get('id')=='prompt':
                    if not record.get('success'): status='prompt_rejected'; break
                    if record.get('data',{}).get('disposition')=='handled': status='prompt_handled'; break
                if kind=='turn_start': turns+=1
                if kind=='tool_execution_start': tools+=1
                if turns>limits.turns or tools>limits.tool_executions: status='budget_exhausted'; break
                if kind=='message_end' and record.get('message',{}).get('role')=='assistant':
                    msg=record['message']; assistant.append(msg)
                    if msg.get('stopReason') in ('error','aborted'):
                        error=msg.get('errorMessage','').lower()
                        status='rate_limited' if any(s in error for s in ('429','rate limit','quota','usage limit')) else 'provider_error'
                if kind=='agent_settled':
                    settled=True
                    if status=='interrupted': status='settled'
                    break
        finally:
            # Reap the process group even after a settled RPC response. Closing
            # stdin alone can leave descendant tools running after a timeout.
            if process.poll() is None:
                try: process.stdin.close()
                except OSError: pass
                try: process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    try: os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        try: os.killpg(process.pid,signal.SIGKILL)
                        except ProcessLookupError: pass
                        process.wait()
            # Also terminate descendants when the main process exited first.
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            for reader in readers: reader.join(timeout=1)
            for stream in (process.stdout,process.stderr): stream.close()
            if process.stdin and not process.stdin.closed: process.stdin.close()
        if process.returncode==75 and status=='interrupted': status='gate_closed'
        return dict(runtime='pi-rpc/1',runtime_version=version,provider=self.provider,model=self.model,status=status,session=state,
                    native_session_id=session_id,settled=settled,turns=turns,tool_executions=tools,
                    duration_seconds=time.monotonic()-started,assistant_messages=assistant,exit_code=process.returncode)
