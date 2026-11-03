"""Explicit read-only engineering closeout of an existing scientific trajectory.

--prepare publishes the finite revision and records its receipts without model
inference. --run-authorized-subscription requires that prepared plan; it never
repeats numerical experiments, evaluations, hypotheses or findings.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import secrets
import time

from asr_service.control import ControlService
from integrations.aar.bridge import ResearchBridge
from integrations.aar.researcher import run_research_session
from integrations.aar.upstream_adapter import UpstreamAdapter
from .pi import Limits,PiRuntime
from .p3_acceptance import HERE,write_once,source_provenance,migrate_native_session

PROFILE='powerflow-readonly-finalization/1'


def reports_match(root,plan):
    if set(plan['source_reports'])!={'result.json','result-resumed.json'}:return False
    return all(not (root/name).is_symlink() and hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
               for name,digest in plan['source_reports'].items())


def closeout_document(original,*,original_spent,source_reports):
    limits=json.loads((HERE/'p3-finalization-limits.json').read_text())
    result=copy.deepcopy(original)
    for dimension,increment in (('research_walltime_ms','additional_research_walltime_ms'),('turns','additional_turns'),('tool_executions','additional_tool_executions')):
        result['budget'][dimension]+=limits[increment]
    provenance=result['provenance']
    provenance.update(original_walltime_limit_ms=original['budget']['research_walltime_ms'],
        original_walltime_spent_ms=original_spent,original_walltime_overrun_ms=max(0,original_spent-original['budget']['research_walltime_ms']),
        original_timeout_retained=True,source_reports=source_reports,engineering_closeout=limits,
        scientific_capability_pack_sha256=provenance.get('capability_pack_sha256'),capability_profile=PROFILE,
        capability_pack_sha256=hashlib.sha256((HERE/'p3-finalization-capabilities.json').read_bytes()).hexdigest())
    return result


def counts(service,token,project,run):
    state=service.get_run(token,project,run)
    return dict(trials=len(state['trials']),evaluations=len(state['evaluations']),
        hypotheses=len(service.hypotheses(token,project)),findings=len(service.findings(token,project,run)),
        validations=len(service.validations(token,project,run)))


def context(root,checkout):
    initial=json.loads((root/'result.json').read_text());recovered=json.loads((root/'result-resumed.json').read_text())
    project=initial['project_id'];run=initial['research_run_id']
    tokens={role:secrets.token_urlsafe(32) for role in ('human','researcher','supervisor')}
    credentials={token:dict(subject='p3-'+role,role=role,projects=[project]) for role,token in tokens.items()}
    service=ControlService(root/'control.db',credentials=credentials)
    organization=UpstreamAdapter(service,checkout=checkout)
    return initial,recovered,project,run,tokens,service,organization


def prepare(root,checkout):
    initial,recovered,project,run,tokens,service,organization=context(root,checkout)
    plan_path=root/'finalization-plan.json'
    if plan_path.exists():return json.loads(plan_path.read_text())
    reports={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('result.json','result-resumed.json')}
    document=closeout_document(initial['run']['contract']['document'],
        original_spent=recovered['run']['budget']['research_walltime_ms']['spent'],source_reports=reports)
    # Retrospective operator receipt is explicitly sourced to the immutable
    # measured report; it does not pretend the old launcher emitted a live event.
    session=recovered['run']['runtime_sessions'][-1]
    retrospective=service.observe_runtime_limit(tokens['human'],project,run,session_id=session['session_id'],
        epoch=session['epoch'],owner=session['owner'],kind='model_walltime',
        limit=initial['run']['contract']['document']['budget']['research_walltime_ms'],
        observed=recovered['run']['budget']['research_walltime_ms']['spent'],
        reason='Retrospective operator observation from frozen result-resumed.json: original project research-walltime acceptance budget was insufficient; measured timeout and original debt remain retained.',
        idempotency_key='p3_original_cap_retrospective')
    intent_path=root/'finalization-intent.json'
    if intent_path.exists():intent=json.loads(intent_path.read_text())
    else:
        intent=dict(document=document,contract_id=initial['run']['contract_id'],original_revision=initial['run']['contract_revision'],
            expected_control_revision=service.get_run(tokens['human'],project,run)['control_revision'])
        write_once(intent_path,intent)
    if intent['document']!=document:raise ValueError('finalization_intent_conflict')
    contract=service.publish_contract(tokens['human'],project,intent['contract_id'],document,
        expected_revision=intent['original_revision'],idempotency_key='p3_finalization_contract')
    applied=service.command(tokens['human'],project,run,'apply_contract',expected_revision=intent['expected_control_revision'],
        idempotency_key='p3_finalization_apply',payload=dict(contract_id=intent['contract_id'],revision=contract['revision']))
    resumed=service.command(tokens['human'],project,run,'resume',expected_revision=applied['control_revision'],idempotency_key='p3_finalization_resume')
    plan=dict(schema='asr-p3-closeout-plan/1',project_id=project,research_run_id=run,contract=contract,
        apply_receipt=applied,resume_receipt=resumed,retrospective_limit_receipt=retrospective,
        before_counts=counts(service,tokens['human'],project,run),source_reports=reports,
        limits=json.loads((HERE/'p3-finalization-limits.json').read_text()))
    write_once(plan_path,plan)
    return plan


def execute(args):
    root=args.root.resolve();plan=json.loads((root/'finalization-plan.json').read_text())
    if not reports_match(root,plan):raise ValueError('original_report_hash_changed')
    if args.report.exists() or (root/'result-finalization.json').exists():raise ValueError('finalization_evidence_already_exists')
    initial,recovered,project,run,tokens,service,organization=context(root,args.aar_checkout)
    before=counts(service,tokens['human'],project,run)
    if before!=plan['before_counts']:raise ValueError('scientific_entities_changed_after_prepare')
    state=service.get_run(tokens['human'],project,run)
    if state['contract_revision']!=plan['contract']['revision'] or state['state']!='running':raise ValueError('prepared_closeout_not_active')
    model=state['contract']['document']['runtime_policy']['model']
    runtime=PiRuntime(model=model,thinking='low',capabilities_path=HERE/'p3-finalization-capabilities.json')
    runtime.preflight_capabilities()
    migration=migrate_native_session(root,run,args.oauth_source,source_directory='pi-private-resumed',target_directory='pi-private-final')
    config=Path(migration['config_dir']);events=[];result=None;failure=None;finish=None;projection=None
    source=source_provenance();started=time.monotonic()
    try:
        available=state['budget']['research_walltime_ms']['available']/1000
        limits=Limits(min(30,available),min(2,state['budget']['turns']['available']),min(3,state['budget']['tool_executions']['available']))
        bridge=ResearchBridge(service,project=project,run=run,researcher_token=tokens['researcher'],supervisor_token=tokens['supervisor'],
            workspace=root/'workspace',snapshots=root/'snapshots',organization=organization,capability_profile=PROFILE)
        prompt='Engineering closeout only. Scientific work is already durably complete. Call ASR state exactly once, confirm the existing run/finding/Validation IDs and their narrow fixed-case limits in a brief final reply, then finish. Do not propose, modify, publish or run any experiment, evaluation, hypothesis, finding or snapshot. The original model timeout and 37ms cap overrun remain historical facts; this is a separately authorized read-only closeout. No additional scientific conclusion is requested.'
        result=run_research_session(runtime,bridge,checkout=args.aar_checkout,config_dir=config,native_session_id=run,
            prompt=prompt,limits=limits,oauth_source=args.oauth_source,on_event=events.append)
        after=service.get_run(tokens['human'],project,run)
        if result['status']=='settled' and reports_match(root,plan) and counts(service,tokens['human'],project,run)==before and all(balance['reserved']==0 and balance['available']>=0 for balance in after['budget'].values()):
            finish=service.command(tokens['human'],project,run,'finish',expected_revision=after['control_revision'],idempotency_key='p3_finalization_finish')
            if finish['status']=='applied':
                projection=organization.sync_experiment_state(tokens['human'],project,run,expected_control_revision=finish['control_revision'],idempotency_key='p3_finalization_projection')
    except Exception as error:failure=dict(category=type(error).__name__,code=getattr(error,'code',None))
    after=service.get_run(tokens['human'],project,run);after_counts=counts(service,tokens['human'],project,run)
    checks=dict(scientific_counts_unchanged=after_counts==before,original_report_hashes_unchanged=reports_match(root,plan),native_model_settled=bool(result and result['status']=='settled'),
        zero_reservations_and_no_debt=all(balance['reserved']==0 and balance['available']>=0 for balance in after['budget'].values()),
        upstream_projection_synchronized=bool(projection and projection['projected_status']==after['state']),
        finish_receipt_applied=bool(finish and finish['status']=='applied'),run_completed=after['state'] in ('completed','finished'))
    write_once(root/'model-events-finalization.json',events)
    write_once(root/'result-finalization.json',dict(runtime=result,run=after,checks=checks,failure=failure,finish_receipt=finish,source_provenance=source))
    transcripts=[dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in (config/'sessions').glob('*.jsonl')]
    report=dict(schema='asr-p3-finalization-result/1',status='closed_with_retained_original_timeout' if all(checks.values()) and failure is None else 'incomplete',
        project_id=project,research_run_id=run,prepared_plan=dict(path=str(root/'finalization-plan.json'),sha256=hashlib.sha256((root/'finalization-plan.json').read_bytes()).hexdigest()),
        prior_reports=plan['source_reports'],original_phase_checks=recovered['acceptance_checks'],original_timeout_retained=True,
        original_walltime_limit_ms=plan['contract']['document']['provenance']['original_walltime_limit_ms'],
        original_walltime_spent_ms=plan['contract']['document']['provenance']['original_walltime_spent_ms'],
        original_walltime_overrun_ms=plan['contract']['document']['provenance']['original_walltime_overrun_ms'],
        finalization_checks=checks,counts_before=before,counts_after=after_counts,finish_receipt=finish,projection_receipt=projection,
        budget=after['budget'],resource_ledgers=after['resource_ledgers'],runtime_records=after['runtime_sessions'],
        runtime={key:result.get(key) for key in ('status','turns','tool_executions','duration_seconds','capability_pack_sha256','capability_pack_id','limit_observations','cleanup')} if result else None,
        source_provenance=source,native_session_migration=migration,native_transcripts=transcripts,
        model_events_sha256=hashlib.sha256((root/'model-events-finalization.json').read_bytes()).hexdigest(),
        actual_aar_experiment=organization.experiment(tokens['supervisor'],project,run),failure=failure,
        scope='Read-only engineering closeout only. No new scientific result, hypothesis judgment, generalization or novelty promotion.',
        billing=dict(mode='subscription',actual_dollar_charge=None,paid_api_fallback=False),elapsed_seconds=round(time.monotonic()-started,3))
    write_once(args.report,report);print(json.dumps(dict(status=report['status'],checks=checks,report=str(args.report))))
    return 0 if all(checks.values()) else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path);parser.add_argument('--aar-checkout',required=True,type=Path)
    parser.add_argument('--oauth-source',required=True,type=Path);parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--run-authorized-subscription',action='store_true');parser.add_argument('--report',type=Path,default=HERE.parents[1]/'docs/validation/P3-RESULTS-FINAL.json')
    parser.add_argument('--proxy')
    args=parser.parse_args()
    if args.proxy:
        from urllib.parse import urlsplit
        import os
        proxy=urlsplit(args.proxy)
        if proxy.scheme not in ('http','https') or not proxy.hostname or proxy.username or proxy.password:parser.error('credential-free proxy required')
        os.environ.update(HTTP_PROXY=args.proxy,HTTPS_PROXY=args.proxy,NO_PROXY='127.0.0.1,localhost')
    if args.prepare:
        plan=prepare(args.root.resolve(),args.aar_checkout)
        print(json.dumps(dict(status='prepared_without_model',contract_revision=plan['contract']['revision'],budget=plan['contract']['document']['budget'],counts=plan['before_counts'])));return 0
    if not args.run_authorized_subscription:parser.error('explicit finite model authorization required')
    return execute(args)


if __name__=='__main__':raise SystemExit(main())
