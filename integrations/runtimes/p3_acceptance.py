"""Bounded real AAR candidate trajectory; --preflight never invokes a model.

Actual execution requires --run-authorized-subscription and a new output/report
path. Existing evidence is never overwritten. Private credentials and transcripts
stay under the ignored acceptance directory, never in the sanitized report.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import time
from urllib.parse import urlsplit
import uuid

from asr_service.control import ControlService
from asr_supervisor.store import ExecutionStore
from asr_supervisor.supervisor import Supervisor
from integrations.aar.bridge import ResearchBridge
from integrations.aar.evaluation_projection import validation_document, compare_replication
from integrations.aar.researcher import load_loop, run_research_session
from integrations.aar.upstream_adapter import UpstreamAdapter
from powerflow_lab.reference import make_request
from .pi import Limits, PiRuntime,prepare_oauth
from .process import identify
from .environment import reject_api_key_settings

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PROFILE='powerflow-candidate-research/1'


def write_once(path, value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def source_provenance():
    inventory={}
    for directory in ('asr_service','asr_supervisor','asr_evaluation','powerflow_lab','integrations/aar','integrations/runtimes','contracts','configs'):
        for path in sorted((REPO/directory).rglob('*')):
            if path.is_file() and not path.is_symlink() and path.suffix in ('.py','.m','.mjs','.json','.md'):
                inventory[str(path.relative_to(REPO))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        tracked_dirty_paths=subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=REPO,text=True).splitlines(),
        source_sha256=inventory)


def migrate_native_session(root,run,oauth_source):
    """Continue a copied native journal; original failure evidence stays intact."""
    original=root/'pi-private/sessions'
    journals=list(original.glob('*_'+run+'.jsonl'))
    if len(journals)!=1 or journals[0].is_symlink() or journals[0].stat().st_size>16777216:
        raise ValueError('unique_bounded_native_journal_required')
    target=root/'pi-private-resumed'
    target.mkdir(mode=0o700,exist_ok=False)
    prepare_oauth(Path(oauth_source),target)
    destination=target/'sessions';destination.mkdir(mode=0o700)
    records=[]
    for source in journals:
        with source.open('rb') as stream:raw=stream.read(16777217)
        if len(raw)>16777216:raise ValueError('native_journal_too_large')
        copied=destination/source.name
        with copied.open('xb') as stream:stream.write(raw)
        copied.chmod(0o600)
        records.append(dict(original=str(source.relative_to(root)),copy=str(copied.relative_to(root)),
            sha256=hashlib.sha256(raw).hexdigest()))
    return dict(config_dir=str(target),journals=records)


def preflight(checkout, oauth_source):
    settings=json.loads((Path.home()/'.pi/agent/settings.json').read_text())
    reject_api_key_settings(settings,runtime='pi',provider='openai-codex')
    if settings.get('defaultProvider')!='openai-codex':raise ValueError('default_codex_subscription_required')
    model=settings['defaultModel'];thinking=settings.get('defaultThinkingLevel','high')
    runtime=PiRuntime(model=model,thinking=thinking,capabilities_path=HERE/'p3-capabilities.json')
    pack=runtime.preflight_capabilities()
    version=subprocess.check_output([runtime.executable,'--version'],text=True,timeout=3,env=runtime.environment).strip()
    if version!=runtime.expected_version:raise ValueError('pi_version_drift')
    auth=json.loads(Path(oauth_source).read_text())
    if auth.get('openai-codex',{}).get('type')!='oauth':raise ValueError('subscription_oauth_required')
    expiry=auth['openai-codex'].get('expires')
    if type(expiry) not in (int,float) or expiry<=time.time()*1000:raise ValueError('refresh_subscription_oauth_before_model_launch')
    load_loop(checkout)
    request=make_request()
    image=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',request['image_id']],text=True,timeout=5).strip()
    if image!=request['image_id']:raise ValueError('pinned_numerical_image_required')
    from asr_evaluation.managed import run_evaluation
    required=('register_candidate','submit_replication','admit_evaluation','get_evaluation','evaluations')
    if not all(callable(getattr(ControlService,name,None)) for name in required):raise ValueError('p3_service_interfaces_unavailable')
    limits=json.loads((HERE/'p3-acceptance-limits.json').read_text())
    return dict(runtime=runtime,model=model,thinking=thinking,limits=limits,
                public=dict(status='ready',model=model,thinking=thinking,provider='openai-codex',
                    auth_mode='subscription_oauth',runtime_version=version,capability_pack_sha256=pack['sha256'],
                    limits=limits,pinned_image=image,aar_owner='actual AutonomousAgentLoop.run'))


def configure(service, project, run, human, organization, model, limits, pack_sha):
    request=make_request()
    documents={
        'problem':dict(profile='matpower-case118/1',case_sha256=request['case_sha256']),
        'reference':dict(profile='matpower-reference/1',image_id=request['image_id']),
        'evaluation':dict(profile='powerflow-independent/1',validator_sha256=request['source_hashes']['validation.py'],tolerance_pu=1e-7),
    }
    refs={kind:service.references.register(project,kind,document) for kind,document in documents.items()}
    refs['input_manifest']=service.references.register(project,'input_manifest',dict(profile='matpower-case118-flat/1',problem_ref=refs['problem']))
    policy=json.loads((REPO/'contracts/examples/research-variables.json').read_text())
    contract=dict(schema_version='asr-contract/1',
        objective=dict(question='Investigate a testable solver, initialization or refinement method on the frozen IEEE-118 original power-flow problem.',
            success_criteria='Model-authored frozen method, hypothesis-linked evidence, honest scientific revision, independent material validation and fresh frozen-method replication; negative results are acceptable.',
            scope='Fixed-PV/PQ single-slack case118 development profile; no generalization or novelty claim.'),
        variable_policy=policy,problem_ref=refs['problem'],reference_ref=refs['reference'],evaluation_ref=refs['evaluation'],
        budget=dict(attempts=limits['numerical_attempts'],execution_ms=limits['numerical_execution_ms'],
            evaluation_attempts=limits['evaluation_attempts'],evaluation_ms=limits['evaluation_ms'],
            research_walltime_ms=limits['total_walltime_seconds']*1000,turns=limits['turns'],tool_executions=limits['tool_executions']),
        execution_policy=dict(researchers=1,candidate_interface='asr-candidate/1',candidate_profiles=['octave-candidate/1'],
            max_candidate_revisions=limits['max_method_revisions'],timeout_seconds=limits['per_attempt_timeout_seconds'],
            output_bytes=104857600,max_concurrency=1,retry_limit=0),
        runtime_policy=dict(provider='openai-codex',model=model,auth_mode='subscription_oauth',billing_mode='subscription',quota_state='unknown'),
        intervention_policy=dict(guidance_boundary='next_submission',pause='drain'),
        provenance=dict(source='bounded-P3-AAR-candidate-acceptance',capability_profile=PROFILE,capability_pack_sha256=pack_sha,
            aar_upstream='79a0562fa1a2c246048ed7c009f3684907987b05',
            organization='Actual pinned AutonomousAgentLoop and upstream Experiment/Finding ORM; pi owns inner reasoning/tools.',
            replication_protocol='exact-frozen-solution/1; same candidate/input in distinct admitted containers',
            automatic_assessments='Hypothesis/generalization/design unassessed; separate evaluator identity and artifact proof.'))
    service.publish_contract(human,project,'candidate-study',contract,expected_revision=0,idempotency_key='contract')
    organization.create_run(human,project,run,'candidate-study',1,idempotency_key='start')
    return refs


def research_prompt(refs):
    return '''You are the autonomous scientific researcher owned by the actual AAR loop. Read the scientific-reasoning skill and ASR state. Choose your own testable solver/initialization/refinement hypothesis for the frozen case118 problem. Preregister a prediction, scope and refutation criterion with publish_hypothesis before the first experiment. Author candidate.m using your own method or available MATPOWER functions; freeze exact source with freeze_candidate, then use its candidate_ref in references.candidate. The function is result=candidate(mpc), returning original-problem baseMVA,bus,gen,branch; optional diagnostics are author claims. Do not change original loads, topology, PV/PQ/slack semantics or evaluation code. No host Bash or network/code installation.
Use submit_candidate {variables:{solver:'octave-candidate/1',iterations:INTEGER},references:BASE_REFS plus candidate:RETURNED_REFERENCE,requested_budget:{attempts:1,execution_ms:20000},hypothesis_ref:{project_id:ACTUAL_PROJECT,hypothesis_id:YOUR_ID,revision:ACTUAL_REVISION}}. Existing accepted requests keep their IDs; stable keys deduplicate transport retries.
Preserve every outcome. Request independent checks with request_evaluation {target:EXACT_STATE_EVALUATION_TARGET,requested_budget:{evaluation_attempts:1,evaluation_ms:20000}}. Read the actual completed evaluator report, not just its admission receipt. Request one fresh frozen-method replication with request_replication {trial_id:SOURCE_TRIAL_ID,requested_budget:{attempts:1,execution_ms:20000}}; evaluate that new trial too and review the completed reports.
Revise hypothesis precision/scope honestly from evidence and retain a new hypothesis revision with explicit change_reason/analysis_timing. Do not manufacture a failure or change the algorithm just for a demonstration. If you propose a new test, preregister its prediction and distinguish unexecuted work. At most two frozen method versions and four total numerical attempts; no need to consume the allowance.
Write a concise research-note.md, snapshot it, and publish your own evidence-linked candidate finding using publish_finding {finding_id,expected_revision:0,statement,trial_ids,limitations,hypothesis_evidence:[{hypothesis_ref,trial_id,assessment:'supports'|'opposes'|'uncertain',scope,analysis_timing:'prospective'|'post_hoc'}]}. Include actual Validation IDs in the statement. Distinguish execution, equation validity, operating violations, unassessed thermal ratings, experimental design and generalization. Fixed-case replication is not scientific novelty or generalization. A supported negative observation is acceptable. Finish promptly after publication. BASE_REFS='''+json.dumps({kind:value for kind,value in refs.items() if kind!='reference'})


def execute(args, prepared):
    from asr_evaluation.managed import run_evaluation
    root=args.output.resolve()
    if args.report.exists():raise ValueError('refusing_to_overwrite_report')
    previous=None;migration=None
    if args.resume_existing_auth_failure:
        previous=json.loads((root/'result.json').read_text())
        if previous['run']['trials'] or previous['hypotheses'] or any(item['status']!='provider_error' or item['tool_executions'] for item in previous['runtime_sessions']):
            raise ValueError('only_preexperiment_auth_failure_resume_supported')
        project=previous['project_id'];run=previous['research_run_id']
    else:
        root.mkdir(parents=True,exist_ok=False,mode=0o700)
        project='p3-'+uuid.uuid4().hex[:12];run='research_'+uuid.uuid4().hex
    provenance=source_provenance()
    work=root/'workspace'
    if previous is None:
        work.mkdir()
        subprocess.run(['git','init','--quiet',str(work)],check=True)
    tokens={role:secrets.token_urlsafe(32) for role in ('human','researcher','supervisor','evaluator')}
    credentials={token:dict(subject='p3-'+role,role=role,projects=[project]) for role,token in tokens.items()}
    service=ControlService(root/'control.db',credentials=credentials)
    organization=UpstreamAdapter(service,checkout=args.aar_checkout)
    prior=[]
    if previous:
        current=service.get_run(tokens['human'],project,run)
        if current['trials'] or service.hypotheses(tokens['human'],project) or any(item['state']=='active' for item in current['runtime_sessions']):
            raise ValueError('auth_failure_ledger_changed_or_unresolved')
        document=current['contract']['document']
        if document['runtime_policy']['model']!=prepared['model']:raise ValueError('resumed_model_mismatch')
        refs=dict(problem=document['problem_ref'],reference=document['reference_ref'],evaluation=document['evaluation_ref'])
        refs['input_manifest']=service.references.register(project,'input_manifest',dict(profile='matpower-case118-flat/1',problem_ref=refs['problem']))
        migration=migrate_native_session(root,run,args.oauth_source)
        config_dir=Path(migration['config_dir'])
        prior=[dict(path='result.json',sha256=hashlib.sha256((root/'result.json').read_bytes()).hexdigest(),
                    failures=previous['failures'],runtime_statuses=[item['status'] for item in previous['runtime_sessions']])]
    else:
        refs=configure(service,project,run,tokens['human'],organization,prepared['model'],prepared['limits'],prepared['public']['capability_pack_sha256'])
        config_dir=root/'pi-private'
    result_file=root/('result-resumed.json' if previous else 'result.json')
    event_file=root/('model-events-resumed.json' if previous else 'model-events.json')
    manager=Supervisor(ExecutionStore(service.path),root/'evidence')
    fault=None;events=[];runtime_results=[];failures=[];comparison_records=[];comparison_attempts=[]
    started=time.monotonic()
    remaining=service.get_run(tokens['human'],project,run)['budget']['research_walltime_ms']['available']/1000
    deadline=started+min(prepared['limits']['total_walltime_seconds'],remaining)

    def dispatch(receipt):
        nonlocal fault
        manager.execute(receipt['execution_attempt_id'],'p3-candidate-supervisor')
        state=service.get_run(tokens['supervisor'],project,run)
        trial=next(item for item in state['trials'] if item['execution_attempt_id']==receipt['execution_attempt_id'])
        candidate=service.references.get(project,'candidate',trial['references']['candidate'])
        if fault is None and candidate.get('profile')=='octave-candidate/1':
            report=(trial.get('execution') or {}).get('report')
            if not report or not report.get('execution_exited'):raise RuntimeError('fault_requires_persisted_terminal_evidence')
            active=next(item for item in state['runtime_sessions'] if item['state']=='active')
            identity=active['process_identity']
            if identify(identity['pid'])!=identity:raise RuntimeError('fault_runtime_identity_mismatch')
            fault=dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],
                manifest_hash=report['manifest_hash'],hypothesis_ref=trial.get('hypothesis_ref'),
                runtime_session_id=active['session_id'],process_identity=identity,signal='SIGKILL',signal_sent=False)
            os.killpg(identity['pgid'],signal.SIGKILL)
            fault['signal_sent']=True
            write_once(root/'interruption.json',fault)

    def evaluate(receipt):
        job=run_evaluation(service,tokens['supervisor'],project,run,receipt['evaluation_id'],
            'p3-independent-evaluator',root/'evaluations')
        document=validation_document(job)
        # Only this trusted callback receives the evaluator token. It is absent
        # from the bridge, model environment and native session configuration.
        service.publish_validation(tokens['evaluator'],project,run,'validation_'+job['evaluation_id'],
            document,idempotency_key='publish_'+job['evaluation_id'])
        current=service.get_run(tokens['supervisor'],project,run)
        for replica in current['trials']:
            parent=(replica.get('replicates') or {}).get('trial_id')
            if not parent or any(item['replica']['trial_id']==replica['trial_id'] for item in comparison_records):continue
            source=next(item for item in current['trials'] if item['trial_id']==parent)
            source_job=next((item for item in current['evaluations'] if item['target']['trial_id']==parent and item.get('settled')),None)
            replica_job=next((item for item in current['evaluations'] if item['target']['trial_id']==replica['trial_id'] and item.get('settled')),None)
            if not source_job or not replica_job:continue
            try:comparison=compare_replication(source,replica,source_job,replica_job)
            except ValueError as error:
                comparison_attempts.append(dict(source_trial_id=parent,replica_trial_id=replica['trial_id'],
                    status='unassessed',reason=str(error)))
                continue
            improved=validation_document(replica_job,replication=comparison['status'],comparison=comparison)
            service.publish_validation(tokens['evaluator'],project,run,'validation_replay_'+replica_job['evaluation_id'],
                improved,idempotency_key='publish_replay_'+replica_job['evaluation_id'],
                supersedes='validation_'+replica_job['evaluation_id'])
            comparison_records.append(comparison)

    def bridge():
        return ResearchBridge(service,project=project,run=run,researcher_token=tokens['researcher'],
            supervisor_token=tokens['supervisor'],workspace=work,snapshots=root/'snapshots',dispatch=dispatch,
            organization=organization,evaluation_dispatch=evaluate,capability_profile=PROFILE)

    def event(record):
        if record.get('type') in ('message_end','tool_execution_start','tool_execution_end','agent_settled'):
            events.append(record)

    def session(prompt, seconds):
        current=service.get_run(tokens['supervisor'],project,run)
        budget=current['budget']
        available=min(seconds,deadline-time.monotonic(),budget['research_walltime_ms']['available']/1000)
        if available<=1 or budget['turns']['available']<=0 or budget['tool_executions']['available']<=0:
            raise RuntimeError('remaining_research_budget_insufficient')
        return run_research_session(prepared['runtime'],bridge(),checkout=args.aar_checkout,
            config_dir=config_dir,native_session_id=run,prompt=prompt,
            limits=Limits(available,budget['turns']['available'],budget['tool_executions']['available']),
            oauth_source=args.oauth_source,on_event=event)

    before_reopen=None;after_reopen=None
    try:
        runtime_results.append(session(research_prompt(refs),110))
        before_reopen=service.get_run(tokens['human'],project,run)
        if not fault or not fault['signal_sent']:raise RuntimeError('candidate_interruption_not_reached')
        # Real service/organization reopen; no new run, hypothesis or trial is
        # manufactured by the driver. The recovered model must read old state.
        service=ControlService(service.path,credentials=credentials)
        organization=UpstreamAdapter(service,checkout=args.aar_checkout)
        after_reopen=service.get_run(tokens['human'],project,run)
        recovery='''The previous native pi process was deliberately interrupted after its candidate trial and raw evidence were durably completed. You remain the same AAR research run/native session. First read ASR state and recover the original hypothesis, frozen method and completed trial IDs. Do not resubmit that method trial. Request independent evaluation of the existing trial, then one separate exact frozen-method replication and evaluation. Read actual completed evaluator reports. Revise hypothesis precision/scope from evidence with a new immutable revision and retain counterevidence; no forced algorithm change or predetermined conclusion. Distinguish proposed untested next tests. Snapshot research-note.md and publish your own candidate finding citing BOTH source/replica trial IDs, actual hypothesis/Validation IDs and all limitations. Continue within the remaining original budget.
The initial instructions below are HISTORY and API reference, not a request to restart: DO NOT repeat completed initial preregistration, coding, freezing or submitting. Resume only the missing evaluation, exact method replication, scientific revision and publication. A new method trial is permitted only if actual failure or scientific evidence warrants a changed method; a recovered transport is not such a reason.
INITIAL TASK HISTORY: '''+research_prompt(refs)
        runtime_results.append(session(recovery,prepared['limits']['total_walltime_seconds']))
    except Exception as error:
        failures.append(dict(stage='research_trajectory',category=type(error).__name__,code=getattr(error,'code',None)))
    finally:
        after=service.get_run(tokens['human'],project,run)
        findings=service.findings(tokens['human'],project,run)
        hypotheses=service.hypotheses(tokens['human'],project)
        validations=service.validations(tokens['human'],project,run)
        candidate_refs=[]
        for candidate in service.events(tokens['supervisor'],project):
            if candidate['type']=='candidate_registered':
                candidate_refs.append(dict(candidate_ref=candidate['digest'],snapshot_ref=candidate.get('snapshot_ref'),
                    **service.references.get(project,'candidate',candidate['digest'])))
        write_once(event_file,events)
        native=[dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                for path in sorted((config_dir/'sessions').glob('*.jsonl'))]
        same_ids=bool(before_reopen and after_reopen and
            [item['trial_id'] for item in before_reopen['trials']]==[item['trial_id'] for item in after_reopen['trials']])
        same_hypothesis=bool(fault and any(item['sha256']==(fault.get('hypothesis_ref') or {}).get('sha256') for item in hypotheses))
        old_trials=(before_reopen or {}).get('trials',[])
        old_ids={item['trial_id'] for item in old_trials}
        no_duplicate_method=not any(item['trial_id'] not in old_ids and not item.get('replicates') and
            any(item['execution_request']==old['execution_request'] for old in old_trials) for item in after['trials'])
        snapshots=[]
        for manifest in sorted((root/'snapshots').glob('*/manifest.json')):
            content=json.loads(manifest.read_text())
            snapshots.append(dict(snapshot_sha256=manifest.parent.name,files=content['files']))
        note_snapshotted=any(any(item['path']=='research-note.md' for item in snapshot['files']) for snapshot in snapshots)
        method_written=any(item.get('toolName') in ('write','edit') and Path((item.get('args') or {}).get('path','')).name=='candidate.m' for item in events)
        complete_trials=all(item['dispatch_state'] in ('succeeded','failed','timed_out','interrupted','cancelled') and
            ((item.get('execution') or {}).get('report') or {}).get('execution_exited') is True for item in after['trials'])
        complete_evaluations=all(item.get('settled') for item in after.get('evaluations',[]))
        balanced=all(item['reserved']==0 and item['available']>=0 for item in after['budget'].values())
        evidence_linked=any(item.get('hypothesis_evidence') and any(
            {comparison['source']['trial_id'],comparison['replica']['trial_id']} <= {entry['trial_id'] for entry in item['evidence']} and
            all(any(validation['document']['target']['trial_id']==target and validation['validation_id'] in item['statement']
                    for validation in validations) for target in (comparison['source']['trial_id'],comparison['replica']['trial_id']))
            for comparison in comparison_records) for item in findings)
        checks=dict(actual_aar_owner=bool(runtime_results and all('aar_loop' in item for item in runtime_results)),
            candidate_interrupted_after_evidence=bool(fault and fault['signal_sent']),
            same_trial_ids_on_reopen=same_ids,same_frozen_hypothesis_on_reopen=same_hypothesis,
            no_duplicate_method_submission_after_recovery=no_duplicate_method,
            recovered_model_settled=len(runtime_results)==2 and runtime_results[-1]['status']=='settled',
            hypothesis_revision_retained=bool(hypotheses and max(item['revision'] for item in hypotheses)>=2),
            candidate_method_authored_by_model=method_written,candidate_finding_published=evidence_linked,
            independent_validation_published=bool(validations),independent_replication_verified=bool(comparison_records),
            research_note_snapshot=note_snapshotted,all_admitted_trials_terminal=complete_trials,
            all_admitted_evaluations_settled=complete_evaluations,zero_reservations_and_no_budget_debt=balanced)
        private=dict(schema='asr-p3-private-trajectory/1',project_id=project,research_run_id=run,
            runtime_sessions=runtime_results,interruption=fault,run=after,hypotheses=hypotheses,findings=findings,
            validations=validations,candidate_refs=candidate_refs,source_provenance=provenance,snapshots=snapshots,replication_comparisons=comparison_records,comparison_attempts=comparison_attempts,failures=failures,acceptance_checks=checks)
        private.update(prior_results=prior,native_session_migration=migration)
        write_once(result_file,private)
        public=dict(schema='asr-p3-acceptance-result/1',checked_at=datetime.now(timezone.utc).isoformat(),
            status='passed' if all(checks.values()) and not failures else 'incomplete',
            private_evidence_root=str(root.relative_to(REPO)) if root.is_relative_to(REPO) else str(root),
            private_result_file=result_file.name,prior_results=prior,native_session_migration=migration,
            project_id=project,research_run_id=run,external_experiment_id=after['experiment_id'],
            runtime=prepared['public'],runtime_sessions=[{key:item.get(key) for key in ('status','turns','tool_executions','native_session_id','capability_pack_sha256','runtime_claim','execution_exited')} for item in runtime_results],
            runtime_records=after['runtime_sessions'],
            actor_roles={role:'p3-'+role for role in tokens},hypotheses=hypotheses,findings=findings,
            trials=after['trials'],candidate_refs=candidate_refs,evaluations=after.get('evaluations',[]),validations=validations,snapshots=snapshots,
            replication_comparisons=comparison_records,comparison_attempts=comparison_attempts,interruption=fault,resource_ledgers=after['resource_ledgers'],
            budget=after['budget'],acceptance_checks=checks,failures=failures,
            model_events=dict(path=str(event_file.relative_to(root)),sha256=hashlib.sha256(event_file.read_bytes()).hexdigest()),
            native_transcripts=native,total_duration_seconds=round(time.monotonic()-started,3),
            source_provenance=provenance,
            billing=dict(mode='subscription',actual_dollar_charge=None,remaining_provider_quota='unknown',paid_api_fallback=False),
            limits=['Fixed-case engineering/scientific trajectory only; no novelty or held-out generalization claim.',
                'Independent automatic mapping does not judge freeform hypotheses or experimental design.',
                'Typed evaluation_artifact_verified_by_service proves managed artifact binding; isolation_verified_by_service remains separate and is not full runtime-isolation proof.'])
        write_once(args.report,public)
        print(json.dumps(dict(status=public['status'],report=str(args.report),checks=checks,failures=failures)))
    return 0 if public['status']=='passed' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aar-checkout',type=Path,required=True)
    parser.add_argument('--oauth-source',type=Path,default=Path.home()/'.pi/agent/auth.json')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--run-authorized-subscription',action='store_true')
    parser.add_argument('--resume-existing-auth-failure',action='store_true',help='Resume the same preexperiment failed run with remaining original budget; requires a new report path and refreshed OAuth source')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--report',type=Path,default=REPO/'docs/validation/P3-RESULTS.json')
    parser.add_argument('--proxy',help='Explicit existing credential-free HTTP(S) proxy, if required')
    args=parser.parse_args()
    if args.proxy:
        parsed=urlsplit(args.proxy)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
            parser.error('proxy must be an explicit credential-free HTTP(S) URL')
        os.environ.update(HTTP_PROXY=args.proxy,HTTPS_PROXY=args.proxy,NO_PROXY='127.0.0.1,localhost')
    prepared=preflight(args.aar_checkout,args.oauth_source)
    if args.preflight:
        print(json.dumps(prepared['public'],indent=2));return 0
    if not args.run_authorized_subscription or args.output is None:
        parser.error('actual model trajectory requires explicit authorization flag and a new output path')
    return execute(args,prepared)


if __name__=='__main__':raise SystemExit(main())
