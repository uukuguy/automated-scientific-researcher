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
    (config_dir/'settings.json').write_text(json.dumps({'retry':{'enabled':False,'provider':{'maxRetries':0}},'cacheWarming':'off','compaction':{'enabled':False}}))


class PiRuntime:
    provider='openai-codex'

    def __init__(self, *, executable='pi', model, thinking='high', expected_version='1.5.0', capabilities_path=None):
        if not isinstance(model,str) or not model or ':' in model or '/' in model:
            raise ValueError('explicit_codex_model_id_required')
        self.executable=executable
        self.model=model
        self.thinking=thinking
        self.expected_version=expected_version
        self.capabilities_path=Path(capabilities_path or Path(__file__).with_name('capabilities.json'))

    def preflight_capabilities(self):
        try:
            if self.capabilities_path.is_symlink():raise RuntimeFailure('capability_manifest_symlink_forbidden')
            raw=self.capabilities_path.read_bytes()
            pack=json.loads(raw)
            if not isinstance(pack,dict):raise RuntimeFailure('invalid_capability_pack')
            if pack.get('schema')!='asr-research-capability-pack/1' or pack.get('runtime_protocol')!='pi-rpc/1':
                raise RuntimeFailure('capability_pack_schema_mismatch')
            if pack.get('runtime_version')!=self.expected_version or pack.get('id')!='powerflow-calibration-smoke/3':
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
            expected=['pi.read','pi.edit','pi.write','pi.grep','pi.find','pi.ls']
            tools={'asr.state','asr.publish_hypothesis','asr.submit_trial','asr.publish_finding','asr.snapshot','asr.ack_guidance','asr.resolve_library','asr.query_docs','asr.search_literature'}
            if pack.get('coding_tools')!=expected or set(pack.get('tools',[]))!=tools:
                raise RuntimeFailure('capability_tool_inventory_mismatch')
            return dict(sha256=hashlib.sha256(raw).hexdigest(),pack=pack,skills=verified)
        except (OSError,ValueError,TypeError,KeyError) as error:
            raise RuntimeFailure('invalid_capability_pack') from error

    def run(self, *, workspace, config_dir, session_id, prompt, limits, bridge_url, bridge_token, on_event=None, should_stop=None,on_process=None,on_launch=None):
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?',session_id):
            raise ValueError('invalid_native_session_id')
        capabilities=self.preflight_capabilities()
        version=subprocess.check_output([self.executable,'--version'],text=True,timeout=10).strip()
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
        env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR','HTTPS_PROXY','HTTP_PROXY','NO_PROXY') if k in os.environ}
        env['GIT_CEILING_DIRECTORIES']=str(workspace.parent)
        env['ASR_WORKSPACE']=str(workspace)
        env['ASR_OWNED_PROCESS_GROUP']='1'
        env['ASR_SKILL_PATHS']=json.dumps([skill['frozen_path'] for skill in frozen_skills])
        env['ASR_SKILL_PATH']=frozen_skills[0]['frozen_path']
        env.update(PI_CODING_AGENT_DIR=str(config_dir),PI_OFFLINE='1',ASR_BRIDGE_URL=bridge_url,ASR_BRIDGE_TOKEN=bridge_token,
                   ASR_MAX_TURNS=str(limits.turns),ASR_MAX_TOOLS=str(limits.tool_executions),ASR_DEADLINE_MS=str(int((time.time()+limits.walltime_seconds)*1000)))
        argv=[self.executable,'--mode','rpc','--provider',self.provider,'--model',self.model,'--thinking',self.thinking,
              '--session-id',session_id,'--session-dir',str(sessions),'--no-extensions','--extension',str(extension),
              '--no-skills','--no-prompt-templates','--no-context-files','--tools','asr,read,write,edit,grep,find,ls']
        for skill in frozen_skills:argv.extend(['--skill',skill['frozen_path']])
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
        return dict(runtime='pi-rpc/1',runtime_version=version,capability_pack_sha256=capabilities['sha256'],capability_pack_id=capabilities['pack']['id'],capability_skills=frozen_skills,provider=self.provider,model=self.model,status=status,session=state,
                    native_session_id=session_id,settled=settled,turns=turns,tool_executions=tools,
                    duration_seconds=time.monotonic()-started,assistant_messages=assistant,exit_code=process.returncode)
