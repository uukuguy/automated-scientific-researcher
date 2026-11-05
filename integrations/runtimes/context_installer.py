"""Fenced, no-model SDK installation for an already-compacted native leaf."""
import json
import math
import os
from pathlib import Path
import select
import shutil
import subprocess
import time
import uuid

from .environment import build_environment,COMMON_ENVIRONMENT
from .process import identify,verify_process_exit
from .context_maintenance import write


def install(runtime,bridge,*,stage,source,limits,evidence_dir):
    service=bridge.service;p=bridge.project;r=bridge.run;t=bridge.supervisor_token
    work=Path(evidence_dir);work.mkdir(mode=0o700)
    policy=runtime.capacity_policy
    write(work/'intent.json',dict(stage_id=stage['stage_id'],capacity_policy=policy,provider_calls=0,
        purpose='已压缩叶子的受管原生SDK安装；不生成伪造研究消息。'))
    owner='context_installer_'+uuid.uuid4().hex
    pack=runtime.preflight_capabilities()
    binding=service.organization_runtime_binding(bridge.researcher_token,p,r,
        capability_profile=bridge.capability_profile,capability_pack_sha256=pack['sha256'])
    state=service.get_run(t,p,r)
    seconds=min(limits.walltime_seconds,state['budget']['research_walltime_ms']['available']/1000,
                policy['limits']['context_boundary_ms']['value']/1000)
    if seconds<=0:raise ValueError('context_installation_budget_exhausted')
    claim=service.claim_runtime(t,p,r,owner,idempotency_key=owner,
        runtime_identity=dict(provider=runtime.provider,model=runtime.model,auth_mode='subscription_oauth',billing_mode='subscription'),
        requested_walltime_ms=math.ceil(seconds*1000),organization_binding=binding)
    ids=dict(session_id=claim['session_id'],epoch=claim['epoch'],owner=owner)
    from .session import session_engine_deadline
    started=time.monotonic();deadline=session_engine_deadline(limits,claim['reserved_walltime_ms'],started)
    process=None;process_identity=None;receipt=None;buffer=b''
    def read():
        nonlocal buffer
        while b'\n' not in buffer:
            remaining=deadline-time.monotonic()
            if remaining<=0 or not select.select([process.stdout],[],[],max(0,remaining))[0]:raise TimeoutError('context_installer_deadline')
            part=os.read(process.stdout.fileno(),4096)
            if not part:raise ValueError('context_installer_eof')
            buffer+=part
            if len(buffer)>policy['limits']['pi_message_bytes']['value']:raise ValueError('context_installer_record_capacity')
        line,buffer=buffer.split(b'\n',1)
        return json.loads(line)
    try:
        path=Path(source['recovery']['native_session_file']).resolve()
        service.bind_runtime_context(t,p,r,**ids,native_session_id=source['native_session_id'],
            journal_directory=str(path.parent),recovery_stage_id=stage['stage_id'])
        index=Path(shutil.which('pi')).resolve().parents[1]/'index.js'
        service.begin_runtime_launch(t,p,r,**ids)
        with (work/'native-stderr.txt').open('xb') as errors:
            process=subprocess.Popen(['node',str(Path(__file__).with_name('pi_context_installer.mjs')),str(index),str(path)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,start_new_session=True,
                env=build_environment(COMMON_ENVIRONMENT,runtime='pi',provider='openai-codex'))
            process_identity=identify(process.pid);service.attach_runtime_process(t,p,r,**ids,identity=process_identity)
            native=read();cursor=native['cursor'];write(work/'cursor.json',native)
            bound=service.observe_context_cursor(t,p,r,**ids,observation=cursor)
            if bound['status']!='bound':raise ValueError('context_installer_cursor_unbound')
            tokens=native['tokens_before_estimate']
            if type(tokens) is not int or tokens<0:raise ValueError('context_installer_estimate_required')
            authorized=service.authorize_context_installation(t,p,r,**ids,stage_id=stage['stage_id'],observation=cursor,tokens_before=tokens)
            write(work/'authorization.json',dict(receipt=authorized,token_count_source='pinned_sdk_projection_estimate'))
            process.stdin.write((json.dumps(dict(operation='install',authorization_path=str((work/'authorization.json').resolve())))+'\n').encode());process.stdin.flush()
            entry=read()['entry_id'];write(work/'entry.json',dict(entry_id=entry))
            receipt=service.complete_context_installation(t,p,r,**ids,boundary_id=cursor['observation_id'],
                ticket_id=authorized['ticket']['ticket_id'],entry_id=entry,idempotency_key=owner+':complete')
            write(work/'verification.json',receipt)
            process.stdin.write(b'{"operation":"exit"}\n');process.stdin.flush();process.stdin.close()
            process.wait(timeout=max(.001,deadline-time.monotonic()))
        return receipt
    except Exception as error:
        failure=dict(reason=getattr(error,'code',type(error).__name__),stage_id=stage['stage_id'],
            session_id=claim['session_id'],elapsed_ms=math.ceil((time.monotonic()-started)*1000),
            effective_deadline_ms=math.ceil((deadline-started)*1000),capacity_policy_sha256=policy['sha256'],
            recovery='保留原件和已发票据；确认进程退出后核验写入，禁止直接重发。')
        if str(error)=='context_installer_record_capacity':
            prefix=work/'protocol-prefix.bin';prefix.write_bytes(buffer)
            failure.update(limit_name='pi_message_bytes',configured=policy['limits']['pi_message_bytes']['value'],
                observed=len(buffer),unit='bytes',measurement='at_least',retained_prefix=str(prefix),complete_record_verified=False)
            service.observe_runtime_limit(t,p,r,**ids,kind='protocol_message_bytes',limit=failure['configured'],
                observed=failure['observed'],reason='Owned no-model installer record exceeds configured capacity; preserve prefix and defer.',idempotency_key=owner+':record-capacity')
        write(work/'failure.json',failure)
        if isinstance(error,(TimeoutError,subprocess.TimeoutExpired)):
            service.observe_runtime_limit(t,p,r,**ids,kind='model_walltime',limit=failure['effective_deadline_ms'],
                observed=max(failure['elapsed_ms'],failure['effective_deadline_ms']),reason='Owned no-model context installer deadline; retain uncertain write and original journal.',idempotency_key=owner+':deadline')
        raise
    finally:
        exited=False
        if process is not None:
            proof=verify_process_exit(process_identity,terminate=process.poll() is None)
            process.wait();process.stdout.close()
            if not process.stdin.closed:process.stdin.close()
            exited=proof['execution_exited'];write(work/'exit.json',dict(proof=proof,exit_code=process.returncode))
        if exited:
            service.release_runtime(t,p,r,**ids,execution_exited=True,actual_walltime_ms=max(1,math.ceil((time.monotonic()-started)*1000)))
        elif process is None:
            current=service.get_run(t,p,r);session=next(x for x in current['runtime_sessions'] if x['session_id']==claim['session_id'])
            if session.get('launch_state')=='prepared':service.abort_runtime_prelaunch(t,p,r,**ids,reason='context_installer_preflight_failed',actual_walltime_ms=max(1,math.ceil((time.monotonic()-started)*1000)))
