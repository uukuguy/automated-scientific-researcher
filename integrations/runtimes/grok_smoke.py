"""Explicit single-prompt Grok ACP diagnostic; not an ASR runtime adapter.

Requires existing cached native authentication and explicit authorization. Copies
credentials only into a disposable private home, never prints auth responses or
thoughts, disables tools/leader reuse, and preserves each evidence file. Proxy
support: https://docs.x.ai/build/enterprise#proxy-support
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
from integrations.runtimes.process import identify, verify_process_exit


HINTS = {'startupHints':{'nonInteractive':True,'skipGitStatus':True,'skipProjectLayout':True}}
PROMPT = 'Reply with exactly ASR_GROK_OK. Do not use tools.'


def publish_result(output, result):
    """Preserve existing evidence and require cleanup proof for success."""
    if result.get('status') == 'passed' and result.get('owned_process_group_exit_verified') is not True:
        result['status'] = 'cleanup_unconfirmed'
    serialized = json.dumps(result, indent=2) + '\n'
    # The early probe check is only a convenience; exclusive creation closes
    # the race with another publisher while the native dialogue is running.
    with output.open('x', encoding='utf-8') as stream:
        stream.write(serialized)


async def probe(output, proxy, expected_model=None):
    if output.exists(): raise ValueError('refusing to overwrite existing evidence')
    parsed=urlsplit(proxy)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('explicit credential-free HTTP proxy URL required')
    binary=shutil.which('grok')
    if not binary:raise RuntimeError('native Grok executable unavailable')
    source=Path(os.environ.get('GROK_HOME',str(Path.home()/'.grok')))/'auth.json'
    if not source.is_file() or source.stat().st_size>1048576:raise RuntimeError('existing cached native authentication required')
    started=time.monotonic();deadline=started+42
    result=dict(schema='asr-grok-acp-conversation/1',started_at=datetime.now(timezone.utc).isoformat(),
        runtime='grok-acp',runtime_version=subprocess.check_output([binary,'--version'],text=True,timeout=3).strip(),
        status='not_completed',requested_reply='ASR_GROK_OK',prompt_count=0,tool_call_count=0,permission_request_count=0,
        billing={'authentication_method':'cached_token','api_key_environment_present':False,'paid_api_fallback':False,'actual_charge':None,'remaining_subscription_quota':None},
        limits={'total_walltime_seconds':45,'model_prompts':1,'research_tools':False,'client_fs':False,'client_terminal':False},
        correction='Explicit operator-configured HTTP(S)_PROXY; no native model override',expected_model=expected_model,
        prior_failure='GROK-ACP-CONVERSATION.json',prior_model_observation='GROK-ACP-CONVERSATION-PROXY.json',notes=['Native dialogue only, not AAR or scientific acceptance.','Credentials, authentication responses, thoughts and raw transcripts are not retained.'])
    process=None;identity=None;stderr_task=None;session_id=None;cancelled=False;sequence=0;frames=0;reply=[];terminal=None
    server_methods=[];stderr_lines=0
    temporary=tempfile.TemporaryDirectory(prefix='asr-grok-acp-proxy-')
    async def send(record):
        process.stdin.write(json.dumps({'jsonrpc':'2.0',**record},ensure_ascii=False).encode()+b'\n')
        await asyncio.wait_for(process.stdin.drain(),max(.01,min(2,deadline-time.monotonic())))
    async def cancel():
        nonlocal cancelled
        if session_id and not cancelled:
            await send({'method':'session/cancel','params':{'sessionId':session_id}});cancelled=True
    async def dispatch(record):
        if 'method' not in record:return
        method=record['method'];params=record.get('params') or {}
        if 'id' in record:
            server_methods.append(method)
            if method=='session/request_permission':
                result['permission_request_count']+=1
                await send({'id':record['id'],'result':{'outcome':{'outcome':'cancelled'}}})
                await cancel()
            else:await send({'id':record['id'],'error':{'code':-32601,'message':'Unsupported client capability'}})
            return
        if method not in ('session/update','x.ai/session/update'):return
        update=params.get('update') or {};kind=update.get('sessionUpdate')
        if kind=='agent_message_chunk':
            content=update.get('content') or {}
            if content.get('type')=='text' and sum(map(len,reply))<4096:reply.append(content.get('text',''))
        elif kind=='tool_call':
            result['tool_call_count']+=1;await cancel()
    async def request(method,params,seconds=8):
        nonlocal sequence,frames
        sequence+=1;request_id=sequence
        await send({'id':request_id,'method':method,'params':params})
        until=min(deadline,time.monotonic()+seconds)
        while True:
            remaining=until-time.monotonic()
            if remaining<=0:raise asyncio.TimeoutError('bounded stage deadline exceeded')
            raw=await asyncio.wait_for(process.stdout.readline(),remaining)
            if not raw:raise RuntimeError('native ACP process ended')
            frames+=1
            if frames>4096 or len(raw)>1048576:raise RuntimeError('ACP stream limit exceeded')
            record=json.loads(raw)
            if 'method' in record:await dispatch(record);continue
            if record.get('id')!=request_id:raise RuntimeError('uncorrelated ACP response')
            if 'error' in record:
                result['remote_error_code']=(record['error'] or {}).get('code')
                raise RuntimeError('native ACP request rejected')
            return record.get('result',{})
    async def drain_stderr():
        nonlocal stderr_lines
        while True:
            raw=await process.stderr.read(4096)
            if not raw:return
            stderr_lines+=raw.count(b'\n')
    try:
        network=[]
        for route,arguments in [('direct',['--noproxy','*']),('configured_proxy',['--proxy',proxy,'--noproxy',''])]:
            checked=subprocess.run(['curl',*arguments,'--head','--silent','--output','/dev/null','--connect-timeout','3','--max-time','4','--write-out','%{http_code} %{time_connect} %{time_total}','https://cli-chat-proxy.grok.com/'],capture_output=True,text=True,timeout=5)
            network.append({'route':route,'exit_code':checked.returncode,'http_status_connect_total':checked.stdout.strip()})
        result['anonymous_connectivity']=network
        if network[1]['exit_code']!=0:raise RuntimeError('configured proxy unreachable; no prompt sent')
        root=Path(temporary.name);home=root/'home';grok_home=home/'.grok';grok_home.mkdir(parents=True,mode=0o700);workspace=root/'workspace';workspace.mkdir()
        descriptor=os.open(grok_home/'auth.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as stream:stream.write(source.read_bytes())
        allowed=('PATH','TMPDIR','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR')
        env={key:os.environ[key] for key in allowed if key in os.environ}
        env.update(HOME=str(home),GROK_HOME=str(grok_home),HTTP_PROXY=proxy,HTTPS_PROXY=proxy,NO_PROXY='127.0.0.1,localhost')
        command=[binary,'--no-auto-update','--no-subagents','--disable-web-search','--permission-mode','dontAsk','--deny','*','--leader-socket',str(root/'leader.sock'),'agent','--no-leader','stdio']
        process=await asyncio.create_subprocess_exec(*command,cwd=workspace,env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,start_new_session=True,limit=1048576)
        identity=identify(process.pid);stderr_task=asyncio.create_task(drain_stderr())
        initial=await request('initialize',{'protocolVersion':1,'clientCapabilities':{'fs':{'readTextFile':False,'writeTextFile':False},'terminal':False},'clientInfo':{'name':'asr-conversation-smoke','version':'1'},'_meta':HINTS})
        result['protocol_version']=initial.get('protocolVersion')
        methods=[row['id'] for row in initial.get('authMethods',[])];result['advertised_auth_methods']=methods
        if 'cached_token' not in methods:raise RuntimeError('cached native authentication unavailable')
        await request('authenticate',{'methodId':'cached_token','_meta':{'headless':True}})
        result['cached_token_authentication_succeeded']=True
        session=await request('session/new',{'cwd':str(workspace),'mcpServers':[],'_meta':HINTS})
        session_id=session['sessionId'];result['native_session_id']=session_id
        model=(session.get('models') or {}).get('currentModelId')
        if model is None:
            model=next((row.get('currentValue') for row in session.get('configOptions',[]) if row.get('id')=='model'),None)
        result['model']=model;result['model_selection']='session-advertised default; no model change requested'
        if expected_model is not None and model!=expected_model:raise RuntimeError('unexpected default model; no prompt sent')
        result['selection_rationale']='Use actual session-advertised default, explicitly checked against expected_model when supplied; no provider or billing fallback.'
        result['prompt_count']=1
        response=await request('session/prompt',{'sessionId':session_id,'prompt':[{'type':'text','text':PROMPT}]},seconds=30)
        terminal=response.get('stopReason');result['terminal_stop_reason']=terminal
        text=''.join(reply).strip();result['reply']=text[:500]
        result['status']='passed' if terminal=='end_turn' and text=='ASR_GROK_OK' and result['tool_call_count']==0 and result['permission_request_count']==0 else 'not_passed'
    except Exception as error:
        result['status']='timed_out' if isinstance(error,(TimeoutError,asyncio.TimeoutError)) else 'failed'
        result['error_category']=type(error).__name__
        if process and session_id:
            try:await cancel()
            except Exception:pass
    finally:
        if process:
            process.stdin.close()
            try:await asyncio.wait_for(process.wait(),.5)
            except asyncio.TimeoutError:
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:await asyncio.wait_for(process.wait(),.5)
                except asyncio.TimeoutError:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    await asyncio.wait_for(process.wait(),.5)
            if stderr_task:
                try:await asyncio.wait_for(stderr_task,.2)
                except asyncio.TimeoutError:stderr_task.cancel()
            try:result['owned_process_group_exit_verified']=verify_process_exit(identity,terminate=False)['execution_exited']
            except Exception:result['owned_process_group_exit_verified']=False
            result['owned_process_exit_code']=process.returncode
        temporary.cleanup()
        result.update(cancel_notification_sent=cancelled,server_request_methods=server_methods,stderr_line_count=stderr_lines,finished_at=datetime.now(timezone.utc).isoformat(),total_duration_seconds=round(time.monotonic()-started,3))
        publish_result(output, result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-authorized-subscription-probe',action='store_true',required=True)
    parser.add_argument('--proxy',required=True)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--expected-model',help='Optional explicit default-model guard; never changes the native model')
    args=parser.parse_args()
    result=asyncio.run(probe(args.output,args.proxy,args.expected_model))
    print(json.dumps({key:result.get(key) for key in ('status','model','reply','terminal_stop_reason','total_duration_seconds','tool_call_count','permission_request_count','owned_process_group_exit_verified','error_category')}))
    if result['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
