"""Explicit, bounded subscription acceptance. No paid API fallback.

uv run python -m integrations.runtimes.acceptance --output artifacts/p2-pi-<unique>
This runs a real subscription model and up to two offline numerical containers.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import time
import uuid
from asr_service.control import ControlService
from asr_supervisor.store import ExecutionStore
from asr_supervisor.supervisor import Supervisor
from powerflow_lab.reference import make_request
from integrations.aar.bridge import ResearchBridge
from .pi import PiRuntime, Limits, prepare_oauth
from .session import run_session


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--aar-checkout',type=Path,help='Use actual pinned AAR loop and upstream organization backend')
    parser.add_argument('--oauth-source',type=Path,default=Path.home()/'.pi/agent/auth.json')
    parser.add_argument('--refresh-oauth',action='store_true',help='Refresh isolated OAuth copy after provider expiry; never rewrites user auth')
    args=parser.parse_args();root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    settings=json.loads((Path.home()/'.pi/agent/settings.json').read_text())
    if settings.get('defaultProvider')!='openai-codex': raise ValueError('default_codex_subscription_required')
    model=settings['defaultModel'];thinking=settings.get('defaultThinkingLevel','high')
    if args.refresh_oauth:
        private=root/'pi-private';prepare_oauth(args.oauth_source,private)
        authfile=private/'auth.json';auth=json.loads(authfile.read_text());auth['openai-codex']['expires']=0
        authfile.write_text(json.dumps(auth))
        import os
        env={k:v for k,v in os.environ.items() if 'KEY' not in k and 'TOKEN' not in k}
        env['PI_CODING_AGENT_DIR']=str(private)
        checked=subprocess.run(['pi','auth','check','--provider','openai-codex','--json'],env=env,capture_output=True,timeout=30)
        if checked.returncode: raise RuntimeError('isolated_subscription_oauth_refresh_failed; run pi /login openai-codex')
    work=root/'workspace';work.mkdir()
    subprocess.run(['git','init','--quiet',str(work)],check=True)
    human,researcher,supervisor=[secrets.token_urlsafe(32) for _ in range(3)]
    project='p2-subscription';run='research_'+uuid.uuid4().hex
    credentials={token:dict(subject=role,role=role,projects=[project]) for token,role in [(human,'human'),(researcher,'researcher'),(supervisor,'supervisor')]}
    service=ControlService(root/'control.db',credentials=credentials)
    request=make_request()
    documents={
        'problem':dict(profile='matpower-case118/1',case_sha256=request['case_sha256']),
        'reference':dict(profile='matpower-reference/1',image_id=request['image_id']),
        'evaluation':dict(profile='powerflow-independent/1',validator_sha256=request['source_hashes']['validation.py'],tolerance_pu=1e-7),
        'candidate':dict(profile='matpower-reference/1',image_id=request['image_id'],solver='newton_raphson')}
    refs={k:service.references.register(project,k,v) for k,v in documents.items()}
    refs['input_manifest']=service.references.register(project,'input_manifest',dict(profile='matpower-case118-flat/1',problem_ref=refs['problem']))
    contract=dict(schema_version='asr-contract/1',objective=dict(question='Choose a testable numerical hypothesis about the case118 flat-start Newton reference and investigate it using the currently supported iteration budget variable.',success_criteria='A model-generated evidence-linked candidate finding with explicit limitations. Negative results are valid.',scope='case118 fixed-pv-pq calibration; bounded iteration experiments only'),
        variable_policy=json.loads(Path('contracts/examples/research-variables.json').read_text()),problem_ref=refs['problem'],reference_ref=refs['reference'],evaluation_ref=refs['evaluation'],
        budget=dict(attempts=2,execution_ms=30000,research_walltime_ms=120000,turns=12,tool_executions=20),
        execution_policy=dict(researchers=1,candidate_interface='asr-candidate/1',timeout_seconds=15,output_bytes=104857600,max_concurrency=1,retry_limit=0),
        runtime_policy=dict(provider='openai-codex',model=model,auth_mode='subscription_oauth',billing_mode='subscription',quota_state='unknown'),
        intervention_policy=dict(guidance_boundary='next_submission',pause='drain'),provenance=dict(source='bounded-subscription-acceptance',aar_upstream='79a0562fa1a2c246048ed7c009f3684907987b05',organization='Actual pinned AAR AutonomousAgentLoop and Experiment/Finding ORM with pi sessions; Claude SDK imported but not invoked' if args.aar_checkout else 'AAR-inspired research/finding/snapshot bridge; upstream loop/ORM not launched'))
    service.publish_contract(human,project,'calibration',contract,expected_revision=0,idempotency_key='publish')
    organization=None
    if args.aar_checkout:
        from integrations.aar.upstream_adapter import UpstreamAdapter
        organization=UpstreamAdapter(service,checkout=args.aar_checkout)
        organization.create_run(human,project,run,'calibration',1,idempotency_key='start')
        from integrations.aar.researcher import run_research_session
        def driver(*positional,**kwargs):return run_research_session(*positional,**kwargs,checkout=args.aar_checkout)
    else:
        service.create_run(human,project,run,'pi-experiment-'+run,'calibration',1,idempotency_key='start')
        driver=run_session
    service.command(human,project,run,'guidance',expected_revision=1,idempotency_key='guidance',payload={'text':'Report operating violations and unassessed limits separately from equation validity; no feasibility claim.'})
    store=ExecutionStore(service.path);manager=Supervisor(store,root/'evidence')
    def dispatch(receipt): manager.execute(receipt['execution_attempt_id'],'acceptance-supervisor')
    def bridge(): return ResearchBridge(service,project=project,run=run,researcher_token=researcher,supervisor_token=supervisor,workspace=work,snapshots=root/'snapshots',dispatch=dispatch,organization=organization)
    trialrefs={k:v for k,v in refs.items() if k!='reference'}
    prompt='''You are the single autonomous scientific researcher. Read the curated scientific-reasoning skill, create a concise research-note.md with the pi write tool, and snapshot it with ASR snapshot before publishing. Acknowledge received guidance with ack_guidance arguments {command_id:ID,status:'adopted',reason:STRING}. Use ASR tools to read your contract and budgets. Choose and state your own testable hypothesis, choose an allowed iterations value, submit at least one real trial, inspect independent validation observations, and publish your own candidate finding citing actual trial IDs. Work within the bounded calibration profile; broader sampler/solver research is allowed conceptually but currently unsupported execution returns capability_unavailable. Do not claim generalization, feasibility, or novel-method discovery from this smoke test. Tool submit_trial arguments are {variables:{iterations: INTEGER}, references:REFERENCES, requested_budget:{attempts:1,execution_ms:15000}}. Tool publish_finding arguments are {finding_id:STRING,expected_revision:0,statement:STRING,trial_ids:[ACTUAL_TRIAL_ID],limitations:STRING}. Stable key strings deduplicate requests. Read state for guidance and evidence. Published findings are candidate author claims, independent validation is separate. No need to spend both attempts. Finish promptly after publishing. REFERENCES='''+json.dumps(trialrefs)
    started=time.monotonic();events=[]
    def event(record):
        # Full native transcript stays in private pi config; evidence records final
        # responses and tool lifecycle without streaming thought duplication.
        if record.get('type') in ('message_end','tool_execution_start','tool_execution_end','agent_settled'):
            events.append(record)
    first=driver(PiRuntime(model=model,thinking=thinking),bridge(),config_dir=root/'pi-private',native_session_id=run,prompt=prompt,limits=Limits(100,12,20),on_event=event,oauth_source=args.oauth_source)
    before=service.get_run(human,project,run)
    # Reopen the same ledger and native session; do not reinitialize identities.
    service=ControlService(service.path,credentials=credentials)
    if organization: organization=UpstreamAdapter(service,checkout=args.aar_checkout)
    remaining=120-(time.monotonic()-started)
    second=None
    if first['status']=='settled' and service.findings(human,project,run) and remaining>3:
        second=driver(PiRuntime(model=model,thinking=thinking),bridge(),config_dir=root/'pi-private',native_session_id=run,
            prompt='Recovery check only: read ASR state, report the existing research run, accepted trial and candidate finding IDs. Do not submit or repeat experiments. Finish immediately.',
            limits=Limits(min(remaining,20),12-first['turns'],max(1,20-first['tool_executions'])),on_event=event,oauth_source=args.oauth_source)
    after=service.get_run(human,project,run);findings=service.findings(human,project,run)
    result=dict(schema='asr-subscription-acceptance-result/1',project_id=project,research_run_id=run,
        external_experiment_id=after['experiment_id'],runtime_sessions=[x for x in (first,second) if x],
        findings=findings,trials=after['trials'],budget=after['budget'],events=events,
        same_trial_ids_after_reopen=[x['trial_id'] for x in before['trials']]==[x['trial_id'] for x in after['trials']],
        billing=dict(mode='subscription',actual_dollar_charge=None,model_reported_cost_is_estimate=True),
        limits=dict(json.loads(Path(__file__).with_name('acceptance-limits.json').read_text()),model=model,thinking=thinking),
        upstream_snapshots=organization.snapshots(supervisor,project,run) if organization else None,
        upstream_forum=organization.forum(supervisor,project) if organization else None,
        aar_integration='actual pinned AutonomousAgentLoop and Experiment/Finding ORM' if organization else 'organization bridge only; pinned upstream researcher loop and Experiment ORM not launched')
    (root/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(output=str(root/'result.json'),status=first['status'],recovery_status=second['status'] if second else None,trials=len(after['trials']),findings=len(findings))))
    if organization and not result['upstream_snapshots']:raise SystemExit('actual_aar_snapshot_missing')
    if not findings or not second or second['status']!='settled' or not result['same_trial_ids_after_reopen']: raise SystemExit(1)

if __name__=='__main__':main()
