"""Delegate a prepared simulated-client project to the actual AAR/pi owner.

Intake is not experimental completion. No numerical/candidate/finding tool is
available. A separate supported experiment profile is needed for training work.
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
from integrations.aar.researcher import run_research_session,load_loop
from integrations.aar.upstream_adapter import UpstreamAdapter
from powerflow_lab.reference import make_request
from .pi import PiRuntime,Limits
from .environment import reject_api_key_settings

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def write(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-root',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--oauth-source',required=True,type=Path)
    parser.add_argument('--checkout',type=Path,required=True,help='Prepared, pinned AAR checkout with verified ASR patches')
    parser.add_argument('--run-authorized-subscription',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--proxy')
    args=parser.parse_args()
    if args.proxy:
        from urllib.parse import urlsplit
        proxy=urlsplit(args.proxy)
        if proxy.scheme not in ('http','https') or not proxy.hostname or proxy.username or proxy.password:raise ValueError('credential-free proxy required')
        os.environ.update(HTTP_PROXY=args.proxy,HTTPS_PROXY=args.proxy,NO_PROXY='127.0.0.1,localhost')
    client=args.client_root.resolve();public=client/'public' 
    manifest=json.loads((public/'manifest.json').read_text())
    if {p.name for p in public.iterdir()} != set(manifest['files'])|{'manifest.json'}:raise ValueError('public file membership mismatch')
    for name,sha in manifest['files'].items():
        if Path(name).name!=name or (public/name).is_symlink() or hashlib.sha256((public/name).read_bytes()).hexdigest()!=sha:raise ValueError('public artifact integrity failure')
    if not args.run_authorized_subscription:
        print(json.dumps(dict(status='materials_verified',execution='not requested',public_files=len(manifest['files']))));return
    output=args.output.resolve()
    suffix='-resumed' if args.resume else ''
    prior=None
    if args.resume:
        prior=json.loads((output/'result.json').read_text())
        if prior['trials'] or prior['intake_exists'] or prior['control_state']!='paused' or prior['runtime']['status']!='provider_error':raise ValueError('only clean pre-intake provider failure can resume here')
        if (output/'result-resumed.json').exists():raise ValueError('resumed report already exists; explicit recovery required')
    else:output.mkdir(mode=0o700,parents=True,exist_ok=False)
    work=output/'workspace'
    if not args.resume:shutil.copytree(public,work)
    # Minimal trainer source is supplied as client-owned method documentation.
    import ast
    source=(ROOT/'research_projects/ood_augmentation/project.py').read_text()
    functions=[ast.get_source_segment(source,node) for node in ast.parse(source).body
               if isinstance(node,ast.FunctionDef) and node.name in ('features','fit','predict')]
    (work/'target-method.py').write_text('import numpy as np\nFEATURE_SCHEMA="regional-load-quadratic/1"\n\n'+'\n\n'.join(functions))
    (work/'CLIENT-BRIEF.md').write_text('''# Client research request

We have a trained voltage-prediction surrogate. Its error is substantially larger
on the supplied OOD diagnostic samples than on its original-distribution samples.
Investigate whether generating additional useful training data from related
regimes can improve generalization. Diagnose the problem, propose and test your
own approach, and report limitations or negative results honestly.

The supplied model, original training set, ID development set, diagnostic set,
method source, physical case, metrics and task criteria belong to the client.
The model/training algorithm and final evaluation rules are fixed for this study;
you may research the augmentation data. Do not train on diagnostic labels and
present that as fresh generated data. Keep diagnostic work distinct from testing.

This is a synthetic public-grid project, not an actual industrial dataset.
Labels pass equation checks but include operating violations and missing thermal
ratings. No operating-feasibility claim follows from these labels.

This first session is project intake. Inspect the actual supplied materials,
preserve your own hypotheses and write RESEARCH-INTAKE.md. Specify the minimum
experiment capabilities needed for your approach. Numerical/training execution
is not yet exposed in this profile. Do not pretend to run missing tools or claim
improvements. No particular sampler or enhancement recipe is prescribed.
''')
    # Real macOS access restriction, in addition to native tool path checks.
    profile=output/'private-materials.sb'
    policy='(version 1)\n(allow default)\n(deny file-read* file-write* (subpath '+json.dumps(str(client))+'))\n'
    if args.resume and profile.read_text()!=policy:raise ValueError('private material boundary changed')
    if not args.resume:profile.write_text(policy)
    probe=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),'/bin/cat',str(client/'private/preparation.json')],capture_output=True,timeout=5)
    if probe.returncode==0 or b'Operation not permitted' not in probe.stderr:raise RuntimeError('private-material denial probe failed')
    write(output/('access-check'+suffix+'.json'),dict(status='denied',returncode=probe.returncode,scope='entire client preparation root',
        limitation='This is a targeted filesystem boundary, not a claim of general runtime containment.'))
    binary=shutil.which('pi')
    if not binary:raise RuntimeError('pi unavailable')
    launcher=output/'pi-sandbox'
    launcher.write_text('#!/bin/sh\nexec /usr/bin/sandbox-exec -f '+shlex.quote(str(profile))+' '+shlex.quote(binary)+' "$@"\n');launcher.chmod(0o700)
    settings=json.loads((Path.home()/'.pi/agent/settings.json').read_text())
    reject_api_key_settings(settings,runtime='pi',provider='openai-codex')
    if settings.get('defaultProvider')!='openai-codex':raise ValueError('codex subscription default required')
    model=settings['defaultModel']
    runtime=PiRuntime(executable=str(launcher),model=model,thinking=settings.get('defaultThinkingLevel','high'),capabilities_path=HERE/'ood-intake-capabilities.json')
    pack=runtime.preflight_capabilities();load_loop(args.checkout)
    limits=json.loads((HERE/'ood-intake-limits.json').read_text())
    project=prior['project_id'] if prior else 'ood-client-'+uuid.uuid4().hex[:12]
    run=prior['research_run_id'] if prior else 'research_'+uuid.uuid4().hex
    tokens={role:secrets.token_urlsafe(32) for role in ('human','supervisor','researcher')}
    service=ControlService(output/'control.db',credentials={token:dict(subject='simulated-client-'+role,role=role,projects=[project]) for role,token in tokens.items()})
    organization=UpstreamAdapter(service,checkout=args.checkout)
    reference=make_request()
    refs={kind:service.references.register(project,kind,doc) for kind,doc in dict(
        problem=dict(profile='matpower-case118/1',case_sha256=reference['case_sha256']),
        reference=dict(profile='matpower-reference/1',image_id=reference['image_id']),
        evaluation=dict(profile='powerflow-independent/1',validator_sha256=reference['source_hashes']['validation.py'],tolerance_pu=1e-7)).items()}
    contract=dict(schema_version='asr-contract/1',objective=dict(question='Receive and diagnose the supplied simulated client OOD augmentation project.',success_criteria='Researcher-authored evidence-grounded intake and hypotheses; no experimental success claim.',scope='Project intake only. Numerical, training and final-evaluation execution are not exposed.'),
        variable_policy=json.loads((ROOT/'contracts/examples/research-variables.json').read_text()),problem_ref=refs['problem'],reference_ref=refs['reference'],evaluation_ref=refs['evaluation'],
        budget=dict(attempts=0,execution_ms=0,research_walltime_ms=limits['walltime_seconds']*1000,turns=limits['turns'],tool_executions=limits['tool_executions']),
        execution_policy=dict(researchers=1,candidate_interface='asr-candidate/1',timeout_seconds=1,output_bytes=104857600,max_concurrency=1,retry_limit=0),
        runtime_policy=dict(provider='openai-codex',model=model,auth_mode='subscription_oauth',billing_mode='subscription',quota_state='unknown'),
        intervention_policy=dict(guidance_boundary='next_submission',pause='drain'),
        provenance=dict(source='user-directed simulated human project delegation',capability_profile='ood-project-intake/1',capability_pack_sha256=pack['sha256'],public_manifest_sha256=hashlib.sha256((public/'manifest.json').read_bytes()).hexdigest(),boundary='Intake capability only; legacy numerical reference fields are not a P4 training/evaluation contract.'))
    if not args.resume:
        service.publish_contract(tokens['human'],project,'client-intake',contract,expected_revision=0,idempotency_key='client-contract')
        organization.create_run(tokens['human'],project,run,'client-intake',1,idempotency_key='client-start')
        write(output/'identity.json',dict(project_id=project,research_run_id=run,model=model,capability_profile='ood-project-intake/1',budget=contract['budget']))
    else:
        previous=service.get_run(tokens['human'],project,run)
        if previous['state']!='paused' or any(s['state']!='exited' for s in previous['runtime_sessions']):raise ValueError('unreconciled prior execution')
        if previous['contract']['document']['runtime_policy']['model']!=model:raise ValueError('model changed')
        if previous['contract']['document']['provenance']['public_manifest_sha256']!=hashlib.sha256((public/'manifest.json').read_bytes()).hexdigest():raise ValueError('client materials changed')
        service.command(tokens['human'],project,run,'resume',expected_revision=previous['control_revision'],idempotency_key='resume-verified-network')
    balance=service.get_run(tokens['human'],project,run)['budget']
    effective=Limits(min(limits['walltime_seconds'],balance['research_walltime_ms']['available']/1000),min(limits['turns'],balance['turns']['available']),min(limits['tool_executions'],balance['tool_executions']['available']))
    bridge=ResearchBridge(service,project=project,run=run,researcher_token=tokens['researcher'],supervisor_token=tokens['supervisor'],workspace=work,snapshots=output/'snapshots',organization=organization,capability_profile='ood-project-intake/1')
    events=[];result=None;failure=None
    try:
        result=run_research_session(runtime,bridge,config_dir=output/'pi-private',native_session_id=run,
            prompt='Read CLIENT-BRIEF.md and task.json, inspect the supplied evidence and target method, and independently conduct project intake. Save RESEARCH-INTAKE.md and snapshot it. Preserve any testable hypothesis with the ASR hypothesis tool. State missing execution capabilities honestly. Do not claim any augmentation or training has occurred. You are responsible for research design; the client has not prescribed a method.',
            limits=effective,oauth_source=args.oauth_source,
            on_event=lambda event:events.append(event),checkout=args.checkout)
    except Exception as exc:failure=dict(type=type(exc).__name__,reason=str(exc))
    if result and result['status']!='settled' and failure is None:failure=dict(type='runtime_outcome',reason=result['status'])
    write(output/('native-events'+suffix+'.json'),events)
    state=service.get_run(tokens['supervisor'],project,run)
    # Stop at a recoverable boundary; intake completion is not research completion.
    receipt=None
    if state['state']=='running':
        receipt=service.command(tokens['human'],project,run,'pause',expected_revision=state['control_revision'],idempotency_key='await-experiment-profile'+suffix)
    state=service.get_run(tokens['supervisor'],project,run)
    projection=organization.sync_experiment_state(tokens['supervisor'],project,run,idempotency_key='intake-projection'+suffix,expected_control_revision=state['control_revision'])
    report=dict(projection=projection,prior_report_sha256=hashlib.sha256((output/'result.json').read_bytes()).hexdigest() if prior else None,project_id=project,research_run_id=run,status='intake_returned' if result and result['status']=='settled' else 'intake_incomplete',failure=failure,
        runtime=result,control_state=state['state'],budgets=state['budget'],pause_receipt=receipt,
        hypotheses=service.hypotheses(tokens['human'],project),snapshots=bridge._snapshot_refs(),
        intake_exists=(work/'RESEARCH-INTAKE.md').exists(),trials=len(state['trials']),
        outcome='Project delegated to actual AAR; scientific experiments/training and final evaluation remain outstanding.')
    write(output/('result'+suffix+'.json'),report)
    print(json.dumps({k:report[k] for k in ('project_id','research_run_id','status','failure','control_state','intake_exists','trials')}))
    if report['status']!='intake_returned' or not report['intake_exists']:raise SystemExit(2)

if __name__=='__main__':main()
