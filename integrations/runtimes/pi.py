"""Replaceable subscription runtime using pi 1.5.0's documented JSONL RPC.

This adapter owns one bounded session, never a research scheduler. OS isolation
for arbitrary coding tools belongs to the execution supervisor, not this module.
"""
from dataclasses import dataclass
import json
import hashlib
import math
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import threading
import time
from .capability_inventory import PROFILE_TOOLS,PROFILE_CODING_TOOLS
from .environment import COMMON_ENVIRONMENT,build_environment,reject_api_key_settings


class RuntimeFailure(RuntimeError):
    def __init__(self,code,*,details=None):
        self.code=code;self.details=details or {}
        super().__init__(code)


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
    reject_api_key_settings(auth,runtime='pi',provider='openai-codex')
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as stream: json.dump({'openai-codex':auth},stream)
    (config_dir/'settings.json').write_text(json.dumps({'retry':{'enabled':False,'provider':{'maxRetries':0}},'cacheWarming':'off','compaction':{'enabled':False}}))


class PiRuntime:
    provider='openai-codex'

    def __init__(self, *, executable='pi', model, thinking='high', expected_version='1.5.0', capabilities_path=None, environment=None,
                 max_message_bytes=4194304,max_buffer_bytes=16777216,max_pending_records=256,max_records=100000,abort_grace_seconds=1.5):
        if not isinstance(model,str) or not model or ':' in model or '/' in model:
            raise ValueError('explicit_codex_model_id_required')
        self.executable=executable
        self.model=model
        self.thinking=thinking
        self.expected_version=expected_version
        self.capabilities_path=Path(capabilities_path or Path(__file__).with_name('capabilities.json'))
        self.environment=build_environment(COMMON_ENVIRONMENT,runtime='pi',provider=self.provider,overrides=environment)
        for value in (max_message_bytes,max_buffer_bytes,max_pending_records,max_records):
            if type(value) is not int or value<1:raise ValueError('finite_positive_protocol_cap_required')
        if type(abort_grace_seconds) not in (int,float) or not math.isfinite(abort_grace_seconds) or not 0<abort_grace_seconds<=3:
            raise ValueError('abort_grace_must_fit_cleanup_headroom')
        self.max_message_bytes=max_message_bytes;self.max_buffer_bytes=max_buffer_bytes
        self.max_pending_records=max_pending_records;self.max_records=max_records;self.abort_grace_seconds=abort_grace_seconds

    def preflight_capabilities(self):
        try:
            if self.capabilities_path.is_symlink():raise RuntimeFailure('capability_manifest_symlink_forbidden')
            raw=self.capabilities_path.read_bytes()
            pack=json.loads(raw)
            if not isinstance(pack,dict):raise RuntimeFailure('invalid_capability_pack')
            if pack.get('schema')!='asr-research-capability-pack/1' or pack.get('runtime_protocol')!='pi-rpc/1':
                raise RuntimeFailure('capability_pack_schema_mismatch')
            if pack.get('runtime_version')!=self.expected_version or pack.get('id') not in PROFILE_TOOLS:
                raise RuntimeFailure('capability_pack_version_mismatch')
            if pack.get('ambient_resources') is not False:
                raise RuntimeFailure('ambient_capabilities_forbidden')
            skills=pack.get('skills',[])
            if type(skills) is not list or not 1<=len(skills)<=32:
                raise RuntimeFailure('capability_skill_inventory_invalid')
            verified=[];seen_ids=set();seen_names=set();seen_paths=set();total=0
            root=self.capabilities_path.parent.resolve()
            for entry in skills:
                if type(entry) is not dict or set(entry)-{'id','name','path','sha256'} or not {'id','path','sha256'}<=set(entry):
                    raise RuntimeFailure('capability_skill_inventory_invalid')
                identity=entry['id']
                match=re.fullmatch(r'([a-z0-9]+(?:-[a-z0-9]+)*)/([1-9][0-9]{0,8})',identity) if isinstance(identity,str) else None
                if not match or len(match[1])>64:raise RuntimeFailure('capability_skill_identity_invalid')
                name=match[1]
                if entry.get('name',name)!=name:raise RuntimeFailure('capability_skill_name_mismatch')
                relative='skills/'+name+'/SKILL.md'
                if entry['path']!=relative:raise RuntimeFailure('capability_skill_path_mismatch')
                if identity in seen_ids or name in seen_names or relative in seen_paths:raise RuntimeFailure('capability_skill_duplicate')
                seen_ids.add(identity);seen_names.add(name);seen_paths.add(relative)
                path=root/relative
                if any(candidate.is_symlink() for candidate in (root/'skills',path.parent,path)):
                    raise RuntimeFailure('capability_skill_symlink_forbidden')
                if not path.is_file() or path.stat().st_size>1048576:raise RuntimeFailure('capability_skill_size_invalid')
                content=path.read_bytes();total+=len(content)
                if len(content)>1048576 or total>8388608:raise RuntimeFailure('capability_skill_size_invalid')
                digest=entry['sha256']
                if not isinstance(digest,str) or re.fullmatch(r'[a-f0-9]{64}',digest) is None or hashlib.sha256(content).hexdigest()!=digest:
                    raise RuntimeFailure('capability_skill_hash_mismatch')
                lines=content.decode('utf-8').splitlines()
                if not lines or lines[0]!='---' or '---' not in lines[1:]:raise RuntimeFailure('capability_skill_frontmatter_invalid')
                frontmatter=lines[1:lines[1:].index('---')+1]
                names=[line.split(':',1)[1].strip() for line in frontmatter if re.match(r'^name\s*:',line)]
                if len(names)!=1:raise RuntimeFailure('capability_skill_name_mismatch')
                declared=names[0]
                if len(declared)>=2 and declared[0]==declared[-1] and declared[0] in ('"',"'"):declared=declared[1:-1]
                if declared!=name:raise RuntimeFailure('capability_skill_name_mismatch')
                verified.append(dict(id=identity,name=name,path=relative,sha256=digest,content=content))
            expected=PROFILE_CODING_TOOLS[pack['id']]
            tools=PROFILE_TOOLS[pack['id']]
            if pack.get('coding_tools')!=expected or set(pack.get('tools',[]))!=tools:
                raise RuntimeFailure('capability_tool_inventory_mismatch')
            return dict(sha256=hashlib.sha256(raw).hexdigest(),pack=pack,skills=verified)
        except (OSError,ValueError,TypeError,KeyError) as error:
            raise RuntimeFailure('invalid_capability_pack') from error

    def run(self, *, workspace, config_dir, session_id, prompt, limits, bridge_url, bridge_token, on_event=None, should_stop=None,on_process=None,on_launch=None,absolute_deadline=None):
        setup_started=time.monotonic()
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?',session_id):
            raise ValueError('invalid_native_session_id')
        if absolute_deadline is not None and (type(absolute_deadline) not in (int,float) or not math.isfinite(absolute_deadline)):
            raise ValueError('finite_absolute_deadline_required')
        def setup_remaining():
            remaining=10 if absolute_deadline is None else absolute_deadline-time.monotonic()
            if remaining<=0:
                configured=max(1,math.ceil(((absolute_deadline or setup_started)-setup_started)*1000))
                failure=RuntimeFailure('setup_deadline_exhausted',details=dict(kind='model_walltime',limit=configured,
                    observed=max(configured,math.ceil((time.monotonic()-setup_started)*1000)),
                    reason='Absolute engine setup deadline exhausted before a native research process was launched.'))
                if on_event:on_event(dict(type='asr_limit',recoverable=True,**failure.details))
                raise failure
            return min(10,remaining)
        capabilities=self.preflight_capabilities()
        version_timeout=setup_remaining()
        try:version=subprocess.check_output([self.executable,'--version'],text=True,timeout=version_timeout,env=self.environment).strip()
        except subprocess.TimeoutExpired:
            configured=max(1,math.ceil(version_timeout*1000))
            failure=RuntimeFailure('version_preflight_timeout',details=dict(kind='model_walltime',limit=configured,
                observed=max(configured,math.ceil((time.monotonic()-setup_started)*1000)),
                reason='Version-probe setup deadline exhausted; no native research process was launched.'))
            if on_event:on_event(dict(type='asr_limit',recoverable=True,**failure.details))
            raise failure from None
        if version!=self.expected_version: raise RuntimeFailure('runtime_version_mismatch')
        workspace=Path(workspace).resolve(); config_dir=Path(config_dir).resolve()
        sessions=config_dir/'sessions'; sessions.mkdir(exist_ok=True)
        extension=Path(__file__).with_name('asr-extension.mjs').resolve()
        # Source registry entries grant no tools. Freeze only the declared,
        # verified methodology bytes before issuing the sole process launch.
        frozen_skills=[]
        for skill in capabilities['skills']:
            skill_dir=config_dir/'capabilities'/skill['sha256']
            frozen_skill=skill_dir/'SKILL.md'
            if any(path.is_symlink() for path in (skill_dir.parent,skill_dir,frozen_skill)):
                raise RuntimeFailure('frozen_skill_symlink_forbidden')
            skill_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
            if frozen_skill.exists():
                if not frozen_skill.is_file() or frozen_skill.stat().st_nlink!=1 or frozen_skill.read_bytes()!=skill['content']:raise RuntimeFailure('frozen_skill_corrupt')
                frozen_skill.chmod(0o400)
            else:
                fd=os.open(frozen_skill,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o400)
                with os.fdopen(fd,'wb') as stream:
                    stream.write(skill['content']);stream.flush();os.fsync(stream.fileno())
            frozen_skills.append(dict(id=skill['id'],name=skill['name'],path=skill['path'],sha256=skill['sha256'],frozen_path=str(frozen_skill)))
        # Allowlist avoids ambient paid credentials and arbitrary shell startup hooks.
        env=build_environment(COMMON_ENVIRONMENT,runtime='pi',provider=self.provider,inherited=self.environment)
        env['GIT_CEILING_DIRECTORIES']=str(workspace.parent)
        env['ASR_WORKSPACE']=str(workspace)
        env['ASR_OWNED_PROCESS_GROUP']='1'
        env['ASR_SKILL_PATHS']=json.dumps([skill['frozen_path'] for skill in frozen_skills])
        env['ASR_SKILL_PATH']=frozen_skills[0]['frozen_path']
        env['ASR_TOOL_OPERATIONS']=json.dumps([tool.removeprefix('asr.') for tool in capabilities['pack']['tools']])
        setup_remaining()
        runtime_deadline=min(time.monotonic()+limits.walltime_seconds,absolute_deadline or float('inf'))
        engine_started=time.monotonic();engine_budget_ms=max(1,math.ceil((runtime_deadline-engine_started)*1000))
        env.update(PI_CODING_AGENT_DIR=str(config_dir),PI_OFFLINE='1',ASR_BRIDGE_URL=bridge_url,ASR_BRIDGE_TOKEN=bridge_token,
                   ASR_MAX_TURNS=str(limits.turns),ASR_MAX_TOOLS=str(limits.tool_executions),ASR_ABORT_GRACE_MS=str(math.ceil(self.abort_grace_seconds*1000)),ASR_MAX_WALLTIME_MS=str(engine_budget_ms),ASR_DEADLINE_MS=str(int((time.time()+runtime_deadline-time.monotonic())*1000)))
        argv=[self.executable,'--mode','rpc','--provider',self.provider,'--model',self.model,'--thinking',self.thinking,
              '--session-id',session_id,'--session-dir',str(sessions),'--no-extensions','--extension',str(extension),
              '--no-skills','--no-prompt-templates','--no-context-files','--tools',','.join(['asr']+[tool.removeprefix('pi.') for tool in capabilities['pack']['coding_tools']])]
        for skill in frozen_skills:argv.extend(['--skill',skill['frozen_path']])
        if on_launch: on_launch()
        process=subprocess.Popen(argv,cwd=workspace,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        records=queue.Queue(maxsize=self.max_pending_records); stderr=[]
        stream_lock=threading.Condition();queued_bytes=0;stream_failure=[]
        reader_stop=threading.Event()
        flow=dict(peak_pending_records=0,peak_buffer_bytes=0,backpressure_waits=0)
        def read_stdout():
            nonlocal queued_bytes
            count=0
            def failed(kind,configured,observed):
                if not stream_failure:stream_failure.append((kind,configured,observed))
            try:
                while True:
                    line=process.stdout.readline(self.max_message_bytes+1)
                    if not line:break
                    count+=1
                    with stream_lock:
                        if len(line)>self.max_message_bytes:failed('protocol_message_bytes',self.max_message_bytes,len(line));return
                        if count>self.max_records:failed('protocol_records',self.max_records,count);return
                        # Capacity limits protect retained memory, not event
                        # arrival rate. Slow the pipe producer until the consumer
                        # drains; never discard an ordinary burst of token events.
                        if len(line)>self.max_buffer_bytes:failed('protocol_buffer_bytes',self.max_buffer_bytes,len(line));return
                        while records.full() or queued_bytes+len(line)>self.max_buffer_bytes:
                            if reader_stop.is_set() or time.monotonic()>=runtime_deadline:return
                            flow['backpressure_waits']+=1
                            stream_lock.wait(timeout=.05)
                        if reader_stop.is_set():return
                        try:
                            record=json.loads(line)
                            if not isinstance(record,dict):record={'type':'protocol_error'}
                        except (ValueError,UnicodeDecodeError,RecursionError):record={'type':'protocol_error'}
                        try:records.put_nowait((record,len(line)))
                        except queue.Full:failed('protocol_pending_records',self.max_pending_records,self.max_pending_records+1);return
                        queued_bytes+=len(line)
                        flow['peak_pending_records']=max(flow['peak_pending_records'],records.qsize())
                        flow['peak_buffer_bytes']=max(flow['peak_buffer_bytes'],queued_bytes)
            finally:
                with stream_lock:
                    while records.full() and not reader_stop.is_set() and time.monotonic()<runtime_deadline:
                        stream_lock.wait(timeout=.05)
                    if not records.full():records.put_nowait((None,0))
        def drain_stderr():
            while True:
                line=process.stderr.read(4096)
                if not line:break
                # Diagnostics are deliberately not returned or persisted: providers
                # and extensions can put credentials in error text.
                if len(stderr)<20: stderr.append(len(line))
        readers=[threading.Thread(target=read_stdout,daemon=True),threading.Thread(target=drain_stderr,daemon=True)]
        for reader in readers: reader.start()
        def send(command):
            process.stdin.write(json.dumps(command).encode()+b'\n'); process.stdin.flush()
        status='interrupted'; state=None; assistant=[]; turns=tools=0; started=time.monotonic(); settled=False
        limit_observations=[];pending_tools={};cleanup=dict(native_abort_requested=False,sigterm=False,sigkill=False)
        def limit(kind,configured,observed,reason):
            value=dict(type='asr_limit',kind=kind,limit=max(1,int(configured)),observed=max(int(configured),int(observed)),reason=reason,recoverable=True)
            limit_observations.append(value)
            if on_event:on_event(value)
        try:
            if on_process:
                from .process import identify
                on_process(identify(process.pid))
            send({'id':'state','type':'get_state'})
            while True:
                if should_stop and should_stop(): status='cancelled'; break
                with stream_lock:failure=stream_failure[0] if stream_failure else None
                if failure:
                    status='limit_reached';limit(*failure,'Native transport cap reached; retain the session prefix and inspect state before recovery.');break
                remaining=runtime_deadline-time.monotonic()
                if remaining<=0:
                    status='timed_out'
                    limit('model_walltime',engine_budget_ms,math.ceil((time.monotonic()-engine_started)*1000),'Engine walltime exhausted; cleanup headroom is reserved. Resume the native journal and read authoritative ASR state.')
                    break
                try: record,consumed=records.get(timeout=min(.1,remaining))
                except queue.Empty: continue
                with stream_lock:
                    queued_bytes-=consumed
                    stream_lock.notify_all()
                    failure=stream_failure[0] if stream_failure else None
                if failure:
                    status='limit_reached';limit(*failure,'Native transport cap reached; retain the session prefix and inspect state before recovery.');break
                if record is None: break
                kind=record.get('type')
                if on_event: on_event(record)
                if kind=='asr_limit':
                    limit_observations.append(record);status='limit_reached';break
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
                if kind=='tool_execution_start':
                    tools+=1
                    args=record.get('args') or {}
                    pending_tools[record.get('toolCallId')]=dict(tool_call_id=record.get('toolCallId'),tool_name=record.get('toolName'),operation=args.get('operation'),request_key=args.get('key'))
                if kind=='tool_execution_end':pending_tools.pop(record.get('toolCallId'),None)
                if turns>limits.turns or tools>limits.tool_executions:
                    status='budget_exhausted'
                    limit('provider_turns' if turns>limits.turns else 'tool_executions',limits.turns if turns>limits.turns else limits.tool_executions,turns if turns>limits.turns else tools,'Runtime count cap reached; preserve accepted requests and recover by their original IDs.')
                    break
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
            reader_stop.set()
            with stream_lock:stream_lock.notify_all()
            # Reap the process group even after a settled RPC response. Closing
            # stdin alone can leave descendant tools running after a timeout.
            if process.poll() is None:
                if status in ('timed_out','limit_reached','budget_exhausted','cancelled'):
                    try:send({'id':'abort','type':'abort'});cleanup['native_abort_requested']=True
                    except (OSError,ValueError):pass
                try: process.stdin.close()
                except OSError: pass
                try: process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    try: os.killpg(process.pid,signal.SIGTERM);cleanup['sigterm']=True
                    except ProcessLookupError: pass
                    try: process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        try: os.killpg(process.pid,signal.SIGKILL);cleanup['sigkill']=True
                        except ProcessLookupError: pass
                        process.wait()
            # Also terminate descendants when the main process exited first.
            try: os.killpg(process.pid,signal.SIGKILL);cleanup['sigkill']=True
            except ProcessLookupError: pass
            for reader in readers: reader.join(timeout=1)
            for stream in (process.stdout,process.stderr): stream.close()
            if process.stdin and not process.stdin.closed: process.stdin.close()
        if process.returncode==75 and status=='interrupted': status='gate_closed'
        return dict(runtime='pi-rpc/1',runtime_version=version,capability_pack_sha256=capabilities['sha256'],capability_pack_id=capabilities['pack']['id'],capability_skills=frozen_skills,provider=self.provider,model=self.model,status=status,session=state,
                    native_session_id=session_id,settled=settled,turns=turns,tool_executions=tools,
                    duration_seconds=time.monotonic()-started,assistant_messages=assistant,exit_code=process.returncode,
                    limit_observations=limit_observations,cleanup=cleanup,protocol_flow=flow,
                    protocol_caps=dict(message_bytes=self.max_message_bytes,buffer_bytes=self.max_buffer_bytes,pending_records=self.max_pending_records,records=self.max_records,abort_grace_ms=math.ceil(self.abort_grace_seconds*1000)),
                    recovery=dict(native_session_id=session_id,native_session_file=(state or {}).get('sessionFile'),
                        pending_tools=list(pending_tools.values()),instruction='Read authoritative state before retrying; reuse accepted request keys and reconcile uncertain execution.'))
