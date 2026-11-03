"""Continue the existing AAR intake run with admitted development experiments."""
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

from asr_service.control import ControlService
from asr_service.study import CAPABILITY, expected_references, public_materials
from asr_supervisor.store import ExecutionStore
from asr_supervisor.study import StudyBackend
from asr_supervisor.supervisor import Supervisor
from integrations.aar.bridge import ResearchBridge
from integrations.aar.researcher import run_research_session, load_loop
from integrations.aar.upstream_adapter import UpstreamAdapter
from .pi import PiRuntime, Limits
from .ood_intake import write

HERE = Path(__file__).resolve().parent


def successor_document(previous, config, limits, refs, pack_hash):
    """Create a revision, never a new project or a reset resource ledger."""
    doc = json.loads(json.dumps(previous['contract']['document']))
    if limits.get('schema')!='asr-study-resources/1':raise ValueError('unsupported resource policy')
    caps=limits['session_limits']
    Limits(caps['walltime_seconds'],caps['turns'],caps['tool_executions'])
    if type(limits['job_timeout_seconds']) is not int or not 0<limits['job_timeout_seconds']<=300:
        raise ValueError('invalid worker timeout policy')
    totals = limits['budget_totals']
    if set(totals) != {'attempts','execution_ms','sample_proposals','research_walltime_ms','turns','tool_executions'}:
        raise ValueError('explicit model and compute budgets required')
    if any(type(v) is not int or v <= 0 for v in totals.values()) or limits.get('paid_api_authorized') is not False or limits.get('paid_api_fallback') is not False:
        raise ValueError('positive finite subscription-only policy required')
    for key, balance in previous['budget'].items():
        if totals.get(key, 0) < balance['spent'] + balance['reserved']:
            raise ValueError('successor budget cannot erase committed usage')
    doc.update(objective=dict(question='Improve the supplied fixed target method through useful generated OOD training data.',
        success_criteria='Controlled development comparisons, complete negative evidence, and a frozen proposal for independent final evaluation.',
        scope='Synthetic client development only; no access to final test data or change to fixed trainer/evaluation rules.'), budget=totals,
        provenance=dict(source='User-directed continuation of the simulated human research project; finite operator execution policy.',
            capability_profile=CAPABILITY, capability_pack_sha256=pack_hash, study=config,
            resource_policy=limits, prior_contract_sha256=previous['contract']['sha256']))
    doc['execution_policy']['timeout_seconds'] = limits['job_timeout_seconds']
    for kind, reference in refs.items():
        doc[kind + '_ref'] = reference
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--client-root', required=True, type=Path)
    parser.add_argument('--image-manifest', required=True, type=Path)
    parser.add_argument('--checkout', required=True, type=Path)
    parser.add_argument('--limits', type=Path, default=HERE/'ood-study-limits.json')
    parser.add_argument('--execute-authorized-subscription', action='store_true')
    parser.add_argument('--proxy')
    parser.add_argument('--synthesis-only',action='store_true',help='Interpret frozen independent final results; no experiment tools')
    args = parser.parse_args()
    root = args.root.resolve(); client = args.client_root.resolve()
    identity = json.loads((root/'identity.json').read_text())
    image = json.loads(args.image_manifest.read_text())
    limits = json.loads(args.limits.read_text())
    project = identity['project_id']; run = identity['research_run_id']
    tokens = {role: secrets.token_urlsafe(32) for role in ('human','researcher','supervisor')}
    service = ControlService(root/'control.db', credentials={token:dict(subject='simulated-client-'+role,role=role,projects=[project]) for role,token in tokens.items()})
    previous = service.get_run(tokens['human'],project,run)
    if previous.get('study_final_lock') and not args.synthesis_only:raise ValueError('final protocol frozen; development cannot resume')
    if args.synthesis_only and not previous.get('study_final_lock'):raise ValueError('independent final admission required before synthesis')
    if previous['state'] != 'paused' or previous['health'] != 'ok' or any(s['state']!='exited' for s in previous['runtime_sessions']):
        raise ValueError('same-run continuation requires reconciled paused research')
    if any(v['reserved'] for v in previous['budget'].values()):
        raise ValueError('unreconciled reservation; do not launch another owner')
    config = dict(public_directory=str(client/'public'), public_manifest_sha256=hashlib.sha256((client/'public/manifest.json').read_bytes()).hexdigest(),
                  image_id=image['image_id'], validator_sha256=image['sources']['powerflow_lab/validation.py'])
    public_materials(config)
    provenance=previous['contract']['document']['provenance']
    original_manifest = provenance.get('public_manifest_sha256') or provenance.get('study',{}).get('public_manifest_sha256')
    if original_manifest and original_manifest != config['public_manifest_sha256']:
        raise ValueError('client package changed since intake')
    actual = subprocess.check_output(['docker','image','inspect',config['image_id'],'--format','{{.Id}}'],text=True,timeout=20).strip()
    if actual != config['image_id']:
        raise ValueError('scientific image unavailable')
    capability='ood-study-synthesis/1' if args.synthesis_only else CAPABILITY
    pack_path=HERE/('ood-synthesis-capabilities.json' if args.synthesis_only else 'ood-study-capabilities.json')
    runtime = PiRuntime(model=identity['model'],thinking='high',capabilities_path=pack_path)
    pack = runtime.preflight_capabilities(); load_loop(args.checkout)
    refs = {kind:service.references._digest(kind,doc) for kind,doc in expected_references(config).items()}
    document = successor_document(previous,config,limits,refs,pack['sha256'])
    if args.synthesis_only:
        document=json.loads(json.dumps(previous['contract']['document']))
        document['provenance']['capability_pack_sha256']=pack['sha256']
        document['provenance']['interpretation_profile']=capability
    if not args.execute_authorized_subscription:
        print(json.dumps(dict(status='preflight_ready',research_run_id=run,budget_totals=document['budget'],
            prior_usage=previous['budget'],image_id=config['image_id'],boundary='Development only; execution not requested.'),indent=2))
        return
    if args.proxy:
        from urllib.parse import urlsplit
        proxy=urlsplit(args.proxy)
        if proxy.scheme not in ('http','https') or not proxy.hostname or proxy.username or proxy.password:
            raise ValueError('credential-free proxy required')
        os.environ.update(HTTP_PROXY=args.proxy,HTTPS_PROXY=args.proxy,NO_PROXY='127.0.0.1,localhost')
    batch = 'study-' + str(time.time_ns())
    report_root = root/batch; report_root.mkdir(mode=0o700)
    # Additional controller/evidence denial is required now that author code can
    # request compute. Containers separately expose only one frozen public payload.
    denied = [client,root/'asr-artifacts',root/'study-evidence',root/'control.db',root/'control.db-wal',root/'control.db-shm']
    policy='(version 1)\n(allow default)\n' + ''.join('(deny file-read* file-write* (subpath '+json.dumps(str(p))+'))\n' for p in denied)
    profile=report_root/'private-materials.sb';profile.write_text(policy)
    for path in (client/'private/preparation.json',root/'control.db'):
        probe=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),'/bin/cat',str(path)],capture_output=True,timeout=5)
        if probe.returncode==0 or b'Operation not permitted' not in probe.stderr:
            raise RuntimeError('private/controller denial probe failed')
    write(report_root/'access-check.json',dict(status='denied',paths=[str(p) for p in denied],scope='targeted filesystem denial plus offline per-job containers'))
    binary=shutil.which('pi')
    if not binary:raise RuntimeError('pi unavailable')
    launcher=report_root/'pi-sandbox'
    launcher.write_text('#!/bin/sh\nexec /usr/bin/sandbox-exec -f '+shlex.quote(str(profile))+' '+shlex.quote(binary)+' "$@"\n');launcher.chmod(0o700)
    runtime=PiRuntime(executable=str(launcher),model=identity['model'],thinking='high',capabilities_path=pack_path)
    for kind,doc in expected_references(config).items():
        service.references.register(project,kind,doc)
    current_id=previous['contract_id']; revision=previous['contract_revision']
    contract=service.publish_contract(tokens['human'],project,current_id,document,expected_revision=revision,idempotency_key=batch+'-contract')
    service.command(tokens['human'],project,run,'apply_contract',expected_revision=previous['control_revision'],idempotency_key=batch+'-apply',payload=dict(contract_id=current_id,revision=contract['revision']))
    state=service.get_run(tokens['human'],project,run)
    service.command(tokens['human'],project,run,'resume',expected_revision=state['control_revision'],idempotency_key=batch+'-resume')
    organization=UpstreamAdapter(service,checkout=args.checkout)
    supervisor=Supervisor(ExecutionStore(service.path),root/'study-evidence',backend=StudyBackend(config['image_id']))
    bridge=ResearchBridge(service,project=project,run=run,researcher_token=tokens['researcher'],supervisor_token=tokens['supervisor'],
        workspace=root/'workspace',snapshots=root/'snapshots',organization=organization,capability_profile=capability,
        dispatch=None if args.synthesis_only else lambda receipt:supervisor.execute(receipt['execution_attempt_id'],'study-supervisor'))
    balances=service.get_run(tokens['human'],project,run)['budget']; caps=limits['session_limits']
    if args.synthesis_only:caps=dict(walltime_seconds=180,turns=25,tool_executions=50)
    effective=Limits(min(caps['walltime_seconds'],balances['research_walltime_ms']['available']/1000),
        min(caps['turns'],balances['turns']['available']),min(caps['tool_executions'],balances['tool_executions']['available']))
    write(report_root/'contract.json',contract)
    result=None;failure=None
    with (report_root/'native-events.jsonl').open('x') as log:
        def event(value):
            log.write(json.dumps(value,allow_nan=False)+'\n');log.flush()
        try:
            result=run_research_session(runtime,bridge,config_dir=root/'pi-private',native_session_id=run,
                prompt=('Read FINAL-TEST-PROPOSAL.md, INDEPENDENT-TRAINING-REPLAY.json and INDEPENDENT-FINAL-RESULT.json (schema asr-ood-independent-validation/1). These frozen files recover your existing research after context exhaustion; do not request the full historical state. All model selections were frozen before testing and experiment tools are now unavailable. Interpret the actual final evidence against your prospective proposal and original hypotheses. Write FINAL-RESEARCH-REPORT.md, snapshot it and publish your own candidate finding citing the final evaluator trial and relevant original fitted trials. State objective met or not met, ID retention, OOD utility, failed controls, absolute errors and limits. Distinguish held-out performance from unseen-family transfer, operational feasibility, training reproduction and novelty; claim only what the evidence establishes. Mark any new explanatory hypothesis post_hoc. Finish promptly after preserving the evidence-linked report.' if args.synthesis_only else 'Continue your existing project and hypotheses. Read CLIENT-ADDENDUM.md, client-data/index.json, state and pending guidance; acknowledge its adoption or explain disagreement. Development tools now support isolated Python analysis main(data), fresh scenario labeling and fixed training through submit_study. You own the sampler and experiment design; no scientific method has been implemented for you. Review your intake proposal against actual budgets, then execute real controlled experiments and analyze failures. Preserve code, hypotheses, seeds, all trial IDs and development comparisons. Do not train on diagnostics/probes or claim author analysis is independent validation. Final hidden testing is not available in this development session. Finish with a frozen FINAL-TEST-PROPOSAL.md naming the exact fitted trial IDs, selection rule and predictions to submit once for independent final testing, plus a development report. Snapshot your files. A supported null/negative result is valid. Do not call the overall research complete before independent final evaluation.'),
                limits=effective,oauth_source=None,on_event=event,checkout=args.checkout)
        except Exception as error:
            failure=dict(type=type(error).__name__,message=str(error))
    state=service.get_run(tokens['human'],project,run)
    if state['state']=='running':
        service.command(tokens['human'],project,run,'pause',expected_revision=state['control_revision'],idempotency_key=batch+'-pause')
    state=service.get_run(tokens['human'],project,run)
    projection=organization.sync_experiment_state(tokens['supervisor'],project,run,idempotency_key=batch+'-projection',expected_control_revision=state['control_revision'])
    report=dict(research_run_id=run,runtime=result,failure=failure,projection=projection,state=bridge.state(),
                boundary='Independent final scoring and researcher interpretation; lifecycle closeout remains.' if args.synthesis_only else 'Development evidence only; final independent testing remains outstanding.')
    write(report_root/'result.json',report)
    print(json.dumps(dict(report=str(report_root/'result.json'),runtime_status=result['status'] if result else None,failure=failure,state=state['state'],trials=len(state['trials']))))
    if failure or not result or result['status']!='settled':raise SystemExit(2)


if __name__=='__main__':main()
