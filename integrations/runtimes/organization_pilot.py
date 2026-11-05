"""Run actual AAR role sessions from model-authored organization records.

Serial role execution driven by the owning Control ledger. Project mode exposes
explicitly admitted scientific tools; historical design mode exposes no compute.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import time
import uuid

from asr_service.control import ControlService
from integrations.aar.bridge import ResearchBridge
from integrations.aar.organization_loop import pending, acknowledge
from integrations.aar.researcher import run_research_session, load_loop
from integrations.aar.upstream_adapter import UpstreamAdapter
from powerflow_lab.reference import make_request
from powerflow_lab.runner import digest, canonical
from .pi import PiRuntime, Limits, RuntimeFailure
from .environment import reject_api_key_settings
from .ood_intake import write

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ACTORS={'organizer':'organizer','lead_1':'lead','lead_2':'lead','worker_1':'worker','worker_2':'worker'}


def context_generations(root):
    """Derive explicit context rotations from immutable recovery receipts."""
    generations={actor:0 for actor in ACTORS}
    for path in root.glob('recovery-*.json'):
        if path.name.endswith('-result.json'):continue
        for actor in json.loads(path.read_text()).get('fresh_context_for',[]):
            if actor not in generations:raise ValueError('unknown_context_actor')
            generations[actor]+=1
    return generations


def check_recovery_contract(service, project, previous, proposed):
    # Admission resolves variable defaults. Compare the same canonical form,
    # while still validating every frozen reference and resource constraint.
    with service._connect() as db:
        admitted=service._validate_contract(db,project,proposed)
    if previous['contract']['document']!=admitted:
        raise ValueError('recovery_contract_changed')


def remaining_session_limits(caps, budget):
    for dimension in ('research_walltime_ms','turns','tool_executions'):
        balance=budget[dimension]
        if balance['available']<=0:
            raise RuntimeFailure('organization_budget_exhausted',details=dict(
                kind=dimension,limit=balance['limit'],observed=balance['spent'],
                reserved=balance['reserved'],available=balance['available'],recoverable=True,
                reason='Shared research allowance exhausted before role launch; preserve pending deliveries and pause. No automatic increase or retry.'))
    return Limits(min(caps['walltime_seconds'],budget['research_walltime_ms']['available']/1000),
        min(caps['turns'],budget['turns']['available']),min(caps['tool_executions'],budget['tool_executions']['available']))


def resources(path):
    value=json.loads(path.read_text())
    if value.get('schema')!='asr-organization-resources/1' or value.get('paid_api_authorized') is not False or value.get('paid_api_fallback') is not False:
        raise ValueError('explicit_subscription_only_resources_required')
    budget=value['budget']
    if set(budget)!={'attempts','execution_ms','research_walltime_ms','turns','tool_executions'} or budget['attempts']!=0 or budget['execution_ms']!=0:
        raise ValueError('organization_pilot_has_no_compute')
    if any(type(budget[k]) is not int or budget[k]<=0 for k in ('research_walltime_ms','turns','tool_executions')):
        raise ValueError('finite_model_budget_required')
    Limits(**value['session_limits'])
    if set(value['capacity'])!={'max_active_leads','max_active_workers'} or any(type(x) is not int or x<=0 for x in value['capacity'].values()):
        raise ValueError('explicit_organization_capacity_required')
    return value


def sync_snapshots(root, workspace):
    for source in sorted((root/'snapshots').glob('*/manifest.json')):
        manifest=json.loads(source.read_text())
        if hashlib.sha256(canonical(manifest)).hexdigest()!=source.parent.name:raise ValueError('snapshot_manifest_corrupt')
        for item in manifest['files']:
            name=Path(item['path'])
            if name.is_absolute() or '..' in name.parts:raise ValueError('unsafe_snapshot_path')
            file=source.parent/'files'/name
            if file.is_symlink() or digest(file)!=item['sha256']:raise ValueError('snapshot_file_corrupt')
            target=workspace/'shared-artifacts'/source.parent.name/name
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if target.is_symlink() or digest(target)!=item['sha256']:raise ValueError('shared_artifact_modified')
            else:
                shutil.copyfile(file,target);target.chmod(0o444)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--checkout',required=True,type=Path)
    parser.add_argument('--limits',type=Path)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--implementation',action='store_true',help='Historical analysis-only implementation acceptance')
    mode.add_argument('--project-spec',type=Path,help='Project requirements; research organization chooses its own process')
    parser.add_argument('--proxy')
    parser.add_argument('--resume',action='store_true',help='Explicit recovery of the same paused reconciled run; no budget reset')
    parser.add_argument('--recovery-reason')
    parser.add_argument('--fresh-context-for',action='append',choices=list(ACTORS),default=[],help='Explicit context recovery; preserve prior journals and research budget')
    parser.add_argument('--oauth-source',type=Path)
    parser.add_argument('--execute-authorized-subscription',action='store_true')
    args=parser.parse_args()
    if args.fresh_context_for and not args.resume:raise ValueError('context_rotation_requires_resume')
    from . import organization_implementation as implementation
    from . import organization_project as project_mode
    scientific=bool(args.implementation or args.project_spec)
    specification=None
    if args.project_spec:specification,project_materials=project_mode.load_spec(args.project_spec)
    args.limits=args.limits or HERE/('organization-project-limits.json' if args.project_spec else 'organization-implementation-limits.json' if args.implementation else 'organization-limits.json')
    limits=project_mode.resources(args.limits) if args.project_spec else implementation.resources(args.limits) if args.implementation else resources(args.limits)
    settings=json.loads((Path.home()/'.pi/agent/settings.json').read_text())
    reject_api_key_settings(settings,runtime='pi',provider='openai-codex')
    if settings.get('defaultProvider')!='openai-codex':raise ValueError('subscription_default_required')
    model=settings['defaultModel'];pack_path=HERE/'organization-capabilities.json'
    pack=PiRuntime(model=model,capabilities_path=pack_path).preflight_capabilities();load_loop(args.checkout)
    material_paths={
        'P4-RESULTS.md':ROOT/'docs/validation/P4-SCIENTIFIC-RESULTS.md',
        'P4-RESEARCHER-REPORT.md':ROOT/'docs/validation/P4-RESEARCHER-FINAL.md',
        'P4-SAMPLER.py':ROOT/'artifacts/p4-intake-001/workspace/study/audit_and_sampler.py',
        'TARGET-METHOD.py':ROOT/'research_projects/ood_augmentation/project.py',
        'CLIENT-TASK.json':ROOT/'artifacts/p4-simulated-client-001/public/task.json'}
    study_config=None
    if args.implementation:
        study_config,additional=implementation.preflight(limits)
        material_paths.update(additional)
        PiRuntime(model=model,capabilities_path=HERE/'organization-study-capabilities.json').preflight_capabilities()
    if args.project_spec:
        study_config=project_mode.scientific_configuration(limits)
        material_paths=dict(project_materials,**{'PROJECT-SPEC.json':args.project_spec})
        PiRuntime(model=model,capabilities_path=HERE/'organization-study-capabilities.json').preflight_capabilities()
    boundary=('Project-directed team research; inspect actual evidence and independent validation before claims.' if args.project_spec else
              'Analysis-only team implementation; no label/fit jobs.' if args.implementation else
              'Organization/design pilot only; no numerical execution.')
    material_hashes={name:digest(path) for name,path in material_paths.items()}
    if not args.execute_authorized_subscription:
        print(json.dumps(dict(status='preflight_ready',model=model,budget=limits['budget'],public_materials=material_hashes,
            boundary=boundary),indent=2));return
    if args.proxy:
        from urllib.parse import urlsplit
        url=urlsplit(args.proxy)
        if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:raise ValueError('credential_free_proxy_required')
        os.environ.update(HTTP_PROXY=args.proxy,HTTPS_PROXY=args.proxy,NO_PROXY='127.0.0.1,localhost')
    root=args.root.resolve()
    recovery_id='recovery-'+str(time.time_ns()) if args.resume else None
    if args.resume:
        if not args.recovery_reason:raise ValueError('explicit_recovery_reason_required')
        identity=json.loads((root/'identity.json').read_text())
        project=identity['project_id'];run=identity['research_run_id']
        if identity['model']!=model or identity['actors']!=ACTORS or json.loads((root/'resource-policy.json').read_text())!=limits:
            raise ValueError('recovery_identity_or_budget_changed')
    else:
        root.mkdir(mode=0o700,parents=True,exist_ok=False)
        project='organization-'+uuid.uuid4().hex[:12];run='research_'+uuid.uuid4().hex
    tokens={name:secrets.token_urlsafe(32) for name in ['human','supervisor',*ACTORS]}
    service=ControlService(root/'control.db',credentials={token:dict(subject=name,role=name if name in ('human','supervisor') else 'researcher',projects=[project]) for name,token in tokens.items()})
    aar=UpstreamAdapter(service,checkout=args.checkout);reference=make_request()
    refs={kind:service.references.register(project,kind,doc) for kind,doc in dict(
        problem=dict(profile='matpower-case118/1',case_sha256=reference['case_sha256']),
        reference=dict(profile='matpower-reference/1',image_id=reference['image_id']),
        evaluation=dict(profile='powerflow-independent/1',validator_sha256=reference['source_hashes']['validation.py'],tolerance_pu=1e-7)).items()}
    if scientific:
        from asr_service.study import expected_references
        refs={kind:service.references.register(project,kind,value) for kind,value in expected_references(study_config).items()}
    contract=dict(schema_version='asr-contract/1',objective=dict(question='Organize autonomous investigation of useful OOD training-data generation from known P4 evidence.',
        success_criteria='Model-originated direction formation, evidence-grounded review/delegation, concrete snapshotted artifacts, and organizer synthesis with limitations.',
        scope='Organization/design pilot. P4 final outcomes are historical development knowledge, not a reusable hidden test. No new numerical performance claims.'),
        variable_policy=json.loads((ROOT/'contracts/examples/research-variables.json').read_text()),problem_ref=refs['problem'],reference_ref=refs['reference'],evaluation_ref=refs['evaluation'],budget=limits['budget'],
        execution_policy=dict(researchers=1,candidate_interface='asr-candidate/1',timeout_seconds=1,output_bytes=104857600,max_concurrency=1,retry_limit=0),
        runtime_policy=dict(provider='openai-codex',model=model,auth_mode='subscription_oauth',billing_mode='subscription',quota_state='unknown'),
        intervention_policy=dict(guidance_boundary='next_submission',pause='drain'),
        provenance=dict(source='user-authorized P5 continuation',capability_profile='research-organization/1',capability_pack_sha256=pack['sha256'],materials=material_hashes,resource_policy_sha256=digest(args.limits)))
    if args.implementation:
        contract['objective']=dict(question='Implement and adversarially check the team-proposed coordinate generator.',
            success_criteria='Team-authored executable source, actual isolated analysis trials, cross-review and snapshotted coordinate/check outputs.',
            scope='Analysis-only implementation acceptance; zero new labels or fit jobs, no scientific utility claim.')
        contract['execution_policy']['timeout_seconds']=limits['analysis_timeout_seconds']
        contract['provenance'].update(capability_profile='ood-study-development/1',study=study_config,study_operations=['analysis'])
    if args.project_spec:
        fields=project_mode.contract_fields(specification,limits,study_config)
        contract['objective']=fields['objective']
        contract['execution_policy']['timeout_seconds']=limits['analysis_timeout_seconds']
        contract['provenance'].update(fields['provenance'],project_spec_sha256=digest(args.project_spec))
    if args.resume:
        previous=service.get_run(tokens['human'],project,run)
        if (previous['state']!='paused' or previous['health']!='ok' or
            any(x['state']!='exited' for x in previous['runtime_sessions']) or any(x['reserved'] for x in previous['budget'].values())):
            raise ValueError('reconcile_before_recovery')
        check_recovery_contract(service,project,previous,contract)
        for step in (root/'steps').glob('*'):
            if not (step/'result.json').exists():raise ValueError('unrecorded_step_requires_reconciliation')
            old=json.loads((step/'result.json').read_text())
            if old['status']=='settled' and not (step/'delivery-receipt.json').exists():raise ValueError('delivery_ack_reconciliation_required')
        write(root/(recovery_id+'.json'),dict(reason=args.recovery_reason,prior_budget=previous['budget'],contract_revision=previous['contract_revision'],budget_changes=False,fresh_context_for=sorted(set(args.fresh_context_for))))
        from .observation_recovery import recover_steps
        recover_steps(service,tokens['supervisor'],project,run,root/'steps',destination=root/'observation-recovery'/recovery_id)
    else:
        service.publish_contract(tokens['human'],project,'organization-pilot',contract,expected_revision=0,idempotency_key='contract')
        aar.create_run(tokens['human'],project,run,'organization-pilot',1,idempotency_key='start')
        service.change_organization(tokens['human'],project,run,kind='policy',entity_id='capacity',expected_revision=0,idempotency_key='capacity',document=limits['capacity'])
        for actor,role in ACTORS.items():
            service.change_organization(tokens['human'],project,run,kind='member',entity_id=actor,expected_revision=0,idempotency_key='member-'+actor,document=dict(role=role,enabled=True))
        write(root/'identity.json',dict(project_id=project,research_run_id=run,model=model,actors=ACTORS,budget=limits['budget']))
        write(root/'resource-policy.json',limits)
    generations=context_generations(root)
    brief='''# Human client request and candidate architecture

Investigate how to generate useful additional training samples for a target method
that performs poorly on some OOD regimes. Known P4 materials are historical
starting evidence. You decide scientific directions and can use one or more
available Leads; no department or topic is assigned by the host.

The human supplied a candidate two-layer design: feasible-region discovery and
active sampling; difficult-sample solving, with shared research memory. This is a
human suggestion, not an ASR implementation or a prior agent invention. Challenge,
modify or reject it if evidence warrants. Two method layers need not map to two
Leads. Equation solvability, operating feasibility, algorithm convergence and
training utility are different properties. No new experiments are enabled here.

This pilot tests actual organization and design, not numerical improvement.
Produce concrete useful artifacts (diagnosis, executable-source prototype or
precise research design), cross-review and an evidence-grounded next experiment
proposal. Code cannot be executed in this profile: label it untested. Do not claim
reproduced numbers from reading a report. No hidden data, new labels or training.

Direction ownership and task assignments are authoritative Control records.
A new active direction wakes its Lead. An assigned task wakes its assignee; task
completion wakes the owning Lead. Directed messages wake their recipients. The
host serially delivers these wakeups; the model chooses topics and recipients.
Use messages for substantive review/handoff, not repeated acknowledgement loops.
Read current revisions before acting; a wakeup may have been superseded. Snapshot
files before sharing their exact digest/path. Other role snapshots appear under
shared-artifacts/<snapshot-hash>/; your workspace is private to your role.

Organizer: synthesize the team outcome in ORGANIZATION-REPORT.md and snapshot it;
state what was actually achieved, disagreements, untested claims and next steps.
Leads: retain scientific responsibility, use Workers for bounded useful tasks and
review returned evidence. Workers: start only your assigned task, produce and
snapshot artifacts, then return a concise result with snapshot references.
Do not fabricate nonexistent trial IDs; empty evidence_trial_ids is appropriate
for prospective work with file sources cited in text. Shared budgets are finite;
write durable output early and finish each session promptly after your handoff.
'''
    if args.implementation:brief=implementation.BRIEF
    if args.project_spec:brief=project_mode.brief(specification)
    for actor in ACTORS:
        work=root/'workspaces'/actor
        if not args.resume:
            work.mkdir(parents=True)
            (work/'CLIENT-BRIEF.md').write_text(brief)
            for name,path in material_paths.items():shutil.copyfile(path,work/name)
        elif (work/'CLIENT-BRIEF.md').read_text()!=brief or any(digest(work/name)!=sha for name,sha in material_hashes.items()):
            raise ValueError('recovery_client_material_changed')
    binary=shutil.which('pi')
    if not binary:raise ValueError('pi_unavailable')
    dispatch=None
    if scientific:
        from asr_supervisor.study import StudyBackend
        from asr_supervisor.store import ExecutionStore
        from asr_supervisor.supervisor import Supervisor
        supervisor=Supervisor(ExecutionStore(service.path),root/'study-evidence',backend=StudyBackend(study_config['image_id']))
        dispatch=lambda trial:supervisor.execute(trial['execution_attempt_id'],'organization-implementation')
    steps=[];failure=None
    for old in sorted((root/'steps').glob('*/result.json')):
        prior=json.loads(old.read_text());steps.append(dict(actor=old.parent.name.split('-',1)[1],path=str(old.parent),status=prior['status']))
    with service._connect() as db:
        review_requested=db.execute("SELECT 1 FROM asr_organization WHERE project=? AND run=? AND kind='message' AND entity='closing-review'",(project,run)).fetchone() is not None
    try:
        # Material and executable checks above must finish while still paused.
        # Once resumed, every exit path passes through reconciliation below.
        if args.resume:
            service.command(tokens['human'],project,run,'resume',expected_revision=previous['control_revision'],idempotency_key=recovery_id)
        while True:
            deliveries=pending(service,tokens['supervisor'],project,run)
            if not deliveries:
                if review_requested:break
                service.change_organization(tokens['human'],project,run,kind='message',entity_id='closing-review',expected_revision=0,
                    idempotency_key='closing-review',document=dict(recipients=['organizer'],text='Controller-generated lifecycle check, not a new human scientific instruction. No pending role deliveries remain. Review actual organization/task state and artifacts. Preserve a final ORGANIZATION-REPORT.md and snapshot; identify incomplete work honestly. Continue only if a concrete necessary task remains.',evidence_trial_ids=[]))
                review_requested=True;continue
            actor=deliveries[0]['recipient'];deliveries=[x for x in deliveries if x['recipient']==actor]
            state=service.get_run(tokens['human'],project,run)
            if state['state']!='running' or any(v['reserved'] for v in state['budget'].values()):raise ValueError('reconcile_before_role_launch')
            caps=limits['session_limits'];budget=state['budget']
            effective=remaining_session_limits(caps,budget)
            step=root/'steps'/f'{len(steps):03d}-{actor}';step.mkdir(parents=True)
            work=root/'workspaces'/actor;sync_snapshots(root,work)
            denied=[ROOT/'artifacts/p4-intake-001',ROOT/'artifacts/p4-simulated-client-001',root/'control.db',root/'control.db-wal',root/'control.db-shm',root/'research-notes',root/'steps',root/'snapshots',Path.home()/'.pi/agent']
            denied += [root/'workspaces'/name for name in ACTORS if name!=actor]
            if scientific:denied += [root/'study-evidence',root/'asr-artifacts']
            for name,role in ACTORS.items():
                if name!=actor:
                    context=hashlib.sha256(json.dumps([project,run,name,role],separators=(',',':')).encode()).hexdigest()
                    denied.append(root/'pi-private/organization'/context)
            profile=step/'private-materials.sb';profile.write_text('(version 1)\n(allow default)\n'+''.join('(deny file-read* file-write* (subpath '+json.dumps(str(p))+'))\n' for p in denied))
            probe=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),'/bin/cat',str(root/'control.db')],capture_output=True,timeout=5)
            if probe.returncode==0 or b'Operation not permitted' not in probe.stderr:raise ValueError('private_boundary_probe_failed')
            launcher=root/f'pi-{actor}'
            launcher.write_text('#!/bin/sh\nexec /usr/bin/sandbox-exec -f '+shlex.quote(str(profile))+' '+shlex.quote(binary)+' "$@"\n');launcher.chmod(0o700)
            role_profile=implementation.role_profile(ACTORS[actor]) if scientific else 'research-organization/1'
            role_pack=HERE/'organization-study-capabilities.json' if role_profile=='research-organization-study/1' else pack_path
            runtime=PiRuntime(executable=str(launcher),model=model,thinking='high',capabilities_path=role_pack,context_generation=generations[actor])
            bridge=ResearchBridge(service,project=project,run=run,researcher_token=tokens[actor],supervisor_token=tokens['supervisor'],workspace=work,snapshots=root/'snapshots',organization=aar,capability_profile=role_profile,dispatch=dispatch)
            prompt=f'You are authenticated member {actor}, role {ACTORS[actor]}. Read CLIENT-BRIEF.md, state and organization_records pages. Your pending deliveries: '+json.dumps(deliveries)+'. Inspect actual sources, act within your role, preserve useful artifacts and hand off using organization records. No fixed scientific direction has been assigned by the host.'
            if generations[actor]:prompt+=' Native conversation context was explicitly rotated after capacity exhaustion; recover from your existing files, snapshots and authoritative records. Prior journals and research identity/budget are preserved. Do not repeat completed experiments.'
            write(step/'request.json',dict(context_generation=generations[actor],actor=actor,role=ACTORS[actor],prompt=prompt,client_brief=brief,client_brief_sha256=digest(work/'CLIENT-BRIEF.md'),deliveries=deliveries,budget=budget,limits=effective.__dict__,access_probe='controller_read_denied'))
            from .async_events import AsyncEventRecorder
            with AsyncEventRecorder(step/'events.jsonl') as event:
                result=run_research_session(runtime,bridge,config_dir=root/'pi-private',native_session_id=run,
                    prompt=prompt,
                    limits=effective,oauth_source=args.oauth_source,on_event=event,checkout=args.checkout)
            result['communication_recording']=event.receipt
            write(step/'result.json',result);steps.append(dict(actor=actor,path=str(step),status=result['status']))
            if result['status']!='settled':raise ValueError('role_session_'+result['status'])
            receipt=acknowledge(service,tokens['supervisor'],project,run,deliveries,result['runtime_claim']['session_id'])
            write(step/'delivery-receipt.json',receipt)
    except Exception as error:
        failure=dict(type=type(error).__name__,message=str(error),recovery='Inspect authoritative runtime/task state and this step before recovery; no automatic retry or allowance increase.')
        if isinstance(error,RuntimeFailure) and error.details:
            failure['details']=error.details
            with service._connect() as db:
                service._event(db,project,run,'organization_delivery_deferred',**error.details)
    finally:
        state=service.get_run(tokens['human'],project,run)
        if state['state']=='running':service.command(tokens['human'],project,run,'pause',expected_revision=state['control_revision'],idempotency_key=(recovery_id or 'pilot')+'-pause')
        state=service.get_run(tokens['human'],project,run)
        projection=aar.sync_experiment_state(tokens['supervisor'],project,run,idempotency_key=(recovery_id or 'pilot')+'-projection',expected_control_revision=state['control_revision'])
        report_path=root/((recovery_id+'-result.json') if recovery_id else 'result.json')
        communication=dict(status='pending')
        try:
            from .communication_archive import archive
            destination=root/'communications'/(recovery_id or 'initial')
            archived=archive(root,destination)
            communication=dict(status='archived',path=str(destination),gaps=archived['gaps'],
                inventory_sha256=digest(destination/'inventory.json'))
        except Exception as error:
            communication=dict(status='failed',error_type=type(error).__name__,message=str(error),
                recovery='Preserve native originals and explicitly retry archive to a new destination; do not repeat research.')
            if failure is None:failure=dict(type='CommunicationArchiveError',message='communication_archive_failed')
        write(report_path,dict(project_id=project,research_run_id=run,steps=steps,failure=failure,state=state['state'],budget=state['budget'],projection=projection,
            boundary=boundary,communication_archive=communication))
    print(json.dumps(dict(report=str(report_path),steps=len(steps),failure=failure,state=state['state'])))
    if failure:raise SystemExit(2)


if __name__=='__main__':main()
