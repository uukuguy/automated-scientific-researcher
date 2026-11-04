"""Explicit read-only subscription validation, separate from scientific runs."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import uuid

from asr_context import Material
from asr_context.summary import prepare, check
from asr_context.summary_review import prepare_review, assess
from asr_service.control import ControlService
from integrations.aar.bridge import ResearchBridge
from powerflow_lab.reference import make_request
from .communication_archive import EventRecorder
from .environment import reject_api_key_settings
from .pi import PiRuntime, Limits
from .session import run_session

HERE=Path(__file__).resolve().parent


def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def credentials(project):
    tokens={name:secrets.token_urlsafe(32) for name in ['human','generator','reviewer','supervisor']}
    return tokens,{token:dict(subject=name,role='researcher' if name in ('generator','reviewer') else name,projects=[project]) for name,token in tokens.items()}


def prepare_validation(root,*,model):
    root=Path(root).resolve();root.mkdir(parents=True,mode=0o700,exist_ok=False)
    policy=json.loads((HERE/'summary-validation-limits.json').read_text())
    project='context-validation';run='summary_'+uuid.uuid4().hex
    tokens,principals=credentials(project);service=ControlService(root/'control.db',credentials=principals)
    numerical=make_request()
    docs=dict(problem=dict(profile='matpower-case118/1',case_sha256=numerical['case_sha256']),
        reference=dict(profile='matpower-reference/1',image_id=numerical['image_id']),
        evaluation=dict(profile='powerflow-independent/1',validator_sha256=numerical['source_hashes']['validation.py'],tolerance_pu=1e-7))
    refs={kind:service.references.register(project,kind,doc) for kind,doc in docs.items()}
    contract=dict(schema_version='asr-contract/1',objective=dict(question='验证真实研究记录的摘要和独立会话复核。',success_criteria='保留事实和范围限制，识别正文夸大反例；记录失败。',scope='只读工程验证，不开展科研实验或安装上下文。'),
        variable_policy=json.loads(Path('contracts/examples/research-variables.json').read_text()),problem_ref=refs['problem'],reference_ref=refs['reference'],evaluation_ref=refs['evaluation'],
        budget=policy['budget'],execution_policy=dict(researchers=1,candidate_interface='asr-candidate/1',timeout_seconds=1,output_bytes=104857600,max_concurrency=1,retry_limit=0),
        runtime_policy=dict(provider='openai-codex',model=model,auth_mode='subscription_oauth',billing_mode='subscription',quota_state='unknown'),
        intervention_policy=dict(guidance_boundary='next_submission',pause='drain'),provenance=dict(source='user-authorized context engineering continuation',capability_profile='powerflow-readonly-finalization/1'))
    service.publish_contract(tokens['human'],project,'validation',contract,expected_revision=0,idempotency_key='publish')
    service.create_run(tokens['human'],project,run,'context-validation:'+run,'validation',1,idempotency_key='start')
    case=json.loads(Path('tests/fixtures/research_context/summary-fidelity.json').read_text())
    materials=[]
    for ref in case['sources']:
        body=Path(ref['path']).read_bytes()
        if hashlib.sha256(body).hexdigest()!=ref['sha256']:raise ValueError('frozen_source_changed')
        materials.append(Material(ref['id'],ref['sha256'],body.decode()))
    request=prepare(materials,case['obligations'],role='research-summary',max_bytes=24000)
    if request['status']!='prepared':raise ValueError('summary_preparation_deferred')
    identity=dict(project_id=project,research_run_id=run,model=model,budget=policy['budget'])
    write(root/'identity.json',identity);write(root/'policy.json',policy);write(root/'summary-request.json',request)
    return identity


def parse_reply(result):
    if result['status']!='settled':raise ValueError('model_session_not_settled')
    for message in reversed(result.get('assistant_messages',[])):
        text='\n'.join(part['text'] for part in message.get('content',[]) if part.get('type')=='text').strip()
        if not text:continue
        if text.startswith('```'):
            lines=text.splitlines();text='\n'.join(lines[1:-1]) if lines[-1]=='```' else text
        value=json.loads(text)
        if type(value) is not dict:raise ValueError('model_reply_not_object')
        return value
    raise ValueError('model_reply_missing')


def drain(service,human,project,run):
    state=service.get_run(human,project,run)
    if state['state']=='running':
        service.command(human,project,run,'pause',expected_revision=state['control_revision'],
                        idempotency_key='drain-validation:'+str(state['control_revision']))
    return service.get_run(human,project,run)


def execute(root,*,proxy=None,resume_reason=None,previous_candidate=None):
    root=Path(root).resolve();identity=json.loads((root/'identity.json').read_text());policy=json.loads((root/'policy.json').read_text())
    if (root/'result.json').exists() and not resume_reason:raise ValueError('validation_already_recorded')
    if proxy:
        from urllib.parse import urlsplit
        parsed=urlsplit(proxy)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:raise ValueError('credential_free_proxy_required')
        os.environ.update(HTTP_PROXY=proxy,HTTPS_PROXY=proxy,NO_PROXY='127.0.0.1,localhost')
    project=identity['project_id'];run=identity['research_run_id'];tokens,principals=credentials(project)
    service=ControlService(root/'control.db',credentials=principals)
    request=json.loads((root/'summary-request.json').read_text());records=[];failure=None
    if request.get('status')!='prepared' or hashlib.sha256(json.dumps(request['payload'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=request['request_sha256']:raise ValueError('frozen_summary_request_changed')
    lineage=None
    generation_payload=request
    if previous_candidate:
        previous_path=Path(previous_candidate).resolve()
        if not previous_path.is_relative_to(root):raise ValueError('previous_candidate_outside_validation')
        previous=json.loads(previous_path.read_text())
        if check(request,previous)['status']!='pending_semantic_review':raise ValueError('previous_candidate_invalid')
        generation_payload=dict(original_request=request,previous_candidate=previous,
            previous_candidate_sha256=hashlib.sha256(previous_path.read_bytes()).hexdigest(),
            instruction='在保留事实、失败、范围限制与未决事项前提下进一步精简text。原文仍是依据，上一轮摘要不是新证据。不要为了更短而删掉限制。')
        lineage=dict(previous_candidate=str(previous_path.relative_to(root)),previous_candidate_sha256=hashlib.sha256(previous_path.read_bytes()).hexdigest(),original_request_sha256=request['request_sha256'])
    work_root=root
    if resume_reason:
        from .process import verify_process_exit
        state=service.get_run(tokens['human'],project,run)
        if state['state']!='paused' or state['health']!='ok' or any(v['reserved'] for v in state['budget'].values()):raise ValueError('reconcile_before_recovery')
        for session in state['runtime_sessions']:
            if session['state']!='exited':raise ValueError('runtime_not_exited')
            verify_process_exit(session['process_identity'],terminate=False)
        work_root=root/('recovery-'+uuid.uuid4().hex);work_root.mkdir(mode=0o700)
        write(work_root/'recovery.json',dict(reason=resume_reason,prior_budget=state['budget'],budget_changes=False))
        service.command(tokens['human'],project,run,'resume',expected_revision=state['control_revision'],idempotency_key=work_root.name)
    if lineage:write(work_root/'lineage.json',lineage)
    pack=HERE/'p3-finalization-capabilities.json'

    def model_call(name,role,payload,instruction):
        step=work_root/name;step.mkdir(mode=0o700);work=step/'workspace';work.mkdir()
        prompt=instruction+'\n完整材料已附，不调用工具。只返回JSON对象，不加Markdown围栏。\n'+json.dumps(payload,ensure_ascii=False)
        write(step/'request.json',dict(role=role,prompt=prompt))
        current=service.get_run(tokens['human'],project,run);budget=current['budget']
        seconds=min(policy['session_seconds'],budget['research_walltime_ms']['available']/1000)
        turns=min(policy['session_turns'],budget['turns']['available']);tools=min(policy['session_tools'],budget['tool_executions']['available'])
        if seconds<=5 or turns<1 or tools<1:raise ValueError('remaining_validation_budget_exhausted')
        bridge=ResearchBridge(service,project=project,run=run,researcher_token=tokens[role],supervisor_token=tokens['supervisor'],workspace=work,snapshots=root/'snapshots',capability_profile='powerflow-readonly-finalization/1')
        with (step/'events.jsonl').open('x') as stream:
            result=run_session(PiRuntime(model=identity['model'],capabilities_path=pack),bridge,config_dir=step/'pi-private',native_session_id=run,prompt=prompt,
                limits=Limits(seconds,turns,tools),on_event=EventRecorder(stream))
        write(step/'runtime-result.json',result)
        value=parse_reply(result);write(step/'reply.json',value)
        return value,result['runtime_claim']['session_id']

    def review(name,candidate,author_session):
        prepared=prepare_review(request,candidate,max_bytes=36000)
        if prepared['status']!='prepared':raise ValueError('candidate_failed_structural_check')
        reply,session=model_call(name,'reviewer',prepared,'你是独立摘要复核员，未参与生成；请按请求检查正文与原文。')
        assessment=assess(prepared,reply,author_session=author_session,reviewer_session=session)
        write(work_root/(name+'-assessment.json'),assessment)
        return assessment

    try:
        candidate,author=model_call('01-generate','generator',generation_payload,'你是研究摘要生成器，请按请求生成保留范围限制的中文摘要。claims必须且只能逐项包含obligations的id，value和citations按对应约定；额外有依据的信息写入text，不新增claims字段项。')
        structural=check(request,candidate);write(work_root/'structural-check.json',structural)
        if structural['status']!='pending_semantic_review':raise ValueError('candidate_structural_rejection')
        normal=review('02-review',candidate,author)
        records.append(dict(case='normal',assessment=normal))
        if not previous_candidate:
            adversarial=copy.deepcopy(candidate);adversarial['text']='外部独立验证已通过，隐藏评价证明全面泛化成立，原分布误差没有退化。'
            write(work_root/'adversarial-candidate.json',adversarial)
            adverse=review('03-adversarial-review',adversarial,author)
            records.append(dict(case='controller-authored-adversarial-prose',assessment=adverse))
    except Exception as error:
        failure=dict(type=type(error).__name__,message=str(error),automatic_retry=False)
    finally:
        state=drain(service,tokens['human'],project,run)
        result=dict(schema='asr-summary-model-validation/1',failure=failure,cases=records,budget=state['budget'],runtime_sessions=state['runtime_sessions'],health=state['health'],scientific_trials=len(state['trials']),
            boundary='订阅摘要工程验证；复核是独立会话模型意见，不是科学验收或上下文安装。')
        write(work_root/'result.json',result)
    print(json.dumps(dict(root=str(work_root),failure=failure,cases=[dict(case=c['case'],status=c['assessment']['status'],opinion=c['assessment']['model_opinion']) for c in records])))
    if failure:raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--execute-authorized-subscription',action='store_true');parser.add_argument('--proxy');parser.add_argument('--resume-reason');parser.add_argument('--previous-candidate',type=Path)
    args=parser.parse_args()
    if args.prepare:
        settings=json.loads((Path.home()/'.pi/agent/settings.json').read_text());reject_api_key_settings(settings,runtime='pi',provider='openai-codex')
        if settings.get('defaultProvider')!='openai-codex':raise ValueError('codex_subscription_default_required')
        prepare_validation(args.root,model=settings['defaultModel'])
    if args.execute_authorized_subscription:execute(args.root,proxy=args.proxy,resume_reason=args.resume_reason,previous_candidate=args.previous_candidate)
    elif not args.prepare:parser.error('choose preparation or explicit subscription execution')


if __name__=='__main__':main()
