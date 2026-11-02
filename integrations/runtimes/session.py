"""Run one fenced runtime session; no scheduler or automatic retry."""
from pathlib import Path
import time
import uuid
from .pi import Limits, RuntimeFailure, prepare_oauth


def run_session(runtime, bridge, *, config_dir, native_session_id, prompt, limits, oauth_source=None, on_event=None):
    service=bridge.service
    owner='pi_'+uuid.uuid4().hex
    claim=service.claim_runtime(bridge.supervisor_token,bridge.project,bridge.run,owner,
        idempotency_key=owner,requested_walltime_ms=int(limits.walltime_seconds*1000))
    if claim.get('replayed'): raise RuntimeFailure('runtime_reconciliation_required')
    bridge.runtime_identity=dict(session_id=claim['session_id'],epoch=claim['epoch'],owner=owner)
    started=time.monotonic()
    exited=False
    try:
        prepare_oauth(Path(oauth_source or Path.home()/'.pi/agent/auth.json'),Path(config_dir))
        effective=Limits(min(limits.walltime_seconds,claim['reserved_walltime_ms']/1000),limits.turns,limits.tool_executions)
        with bridge:
            result=runtime.run(workspace=bridge.workspace,config_dir=config_dir,session_id=native_session_id,
                prompt=prompt,limits=effective,bridge_url=bridge.url,bridge_token=bridge.token,on_event=on_event,
                should_stop=lambda: service.get_run(bridge.supervisor_token,bridge.project,bridge.run)['state'] in ('stopping','stopped','failed','finishing','finished'))
        exited=True
        result['runtime_claim']=claim
        if result['status']=='rate_limited':
            run=service.get_run(bridge.supervisor_token,bridge.project,bridge.run)
            service.command(bridge.supervisor_token,bridge.project,bridge.run,'quota',expected_revision=run['control_revision'],
                idempotency_key='quota_'+owner,payload={'state':'rate_limited'})
        return result
    finally:
        # If setup failed before spawn, there is no child to reconcile. A runtime
        # exception after launch is conservatively unresolved unless run returned.
        if not exited and not locals().get('effective'): exited=True
        if exited: service.release_runtime(bridge.supervisor_token,bridge.project,bridge.run,
            claim['session_id'],claim['epoch'],owner,execution_exited=exited,
            actual_walltime_ms=max(1,int((time.monotonic()-started)*1000)))
