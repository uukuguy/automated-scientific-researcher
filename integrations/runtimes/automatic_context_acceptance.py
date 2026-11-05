"""Explicit zero-science acceptance of automatic context maintenance.

Reuses the existing authorized context-engineering ledger, never adds budget.
The near-full reserve is a named test stimulus, not a production default.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from asr_service.control import ControlService
from integrations.aar.bridge import ResearchBridge
from .async_events import AsyncEventRecorder
from .capacity_policy import load_policy
from .communication_archive import archive
from .context_maintenance import ContextMaintenance,run_with_maintenance,write,reply
from .pi import PiRuntime,Limits
from .process import verify_process_exit
from .summary_acceptance import credentials,drain


def execute(root,*,cycle=1):
    root=Path(root).resolve();prefix=f'automatic-{cycle:03d}';work=root/prefix;work.mkdir(mode=0o700)
    identity=json.loads((root/'identity.json').read_text());p=identity['project_id'];r=identity['research_run_id']
    tokens,principals=credentials(p);service=ControlService(root/'control.db',credentials=principals)
    before=service.get_run(tokens['human'],p,r)
    if any(v['reserved'] for v in before['budget'].values()) or any(s['state']!='exited' for s in before['runtime_sessions']):raise ValueError('reconcile_before_automatic_acceptance')
    for session in before['runtime_sessions']:verify_process_exit(session['process_identity'],terminate=False)
    if before['budget']['attempts']['available'] or before['budget']['execution_ms']['available']:raise ValueError('zero_science_budget_required')
    policy=load_policy();policy.pop('sha256');policy['revision']+=1
    for name in ('context_completion_reserve_bps','context_tool_reserve_bps','context_checkpoint_reserve_bps'):
        policy['limits'][name].update(value=3333,purpose='仅本次验收：用99.99%合计预留触发自然请求边界维护。',adequacy='测试刺激；不是生产默认值，不用于评价科研工作量。')
    write(work/'test-capacity-policy.json',policy)
    configured=dict(cycle=cycle,prior_failures_retained=True,explicit_development_revalidation=True,before_budget=before['budget'],production_policy_changed=False,budget_changes=False,new_scientific_trials=0,
        test_stimulus='一次状态工具调用后的自然请求边界；99.99%测试预留，非真实容量已耗尽证明。')
    configured['source_hashes']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [Path(__file__),Path(__file__).with_name('context_maintenance.py'),Path(__file__).with_name('pi.py'),Path(__file__).with_name('context_installer.py'),Path(__file__).with_name('pi_context_installer.mjs'),Path('asr_service/context_installation.py'),Path('asr_service/context_cursors.py'),Path('asr_service/control.py')]}
    write(work/'configured.json',configured)
    native=json.loads((root/'installation-001/configured.json').read_text())['target_native_id']
    config=root/'installation-001/pi-private'
    pack=Path(__file__).with_name('organization-capabilities.json')
    def runtime(subject):return PiRuntime(model=identity['model'],capabilities_path=pack,capacity_policy_path=work/'test-capacity-policy.json')
    def bridge(subject):
        workspace=root/'installation-001/target-workspace' if subject=='generator' else work/'review-workspace'
        workspace.mkdir(exist_ok=True)
        return ResearchBridge(service,project=p,run=r,researcher_token=tokens[subject],supervisor_token=tokens['supervisor'],workspace=workspace,snapshots=root/'snapshots',capability_profile='research-organization/1')
    case=json.loads(Path('tests/fixtures/research_context/summary-fidelity.json').read_text())
    def obligations(prepared):
        # Only this engineering fixture has seven known facts, never the core.
        sources=[m for m in prepared['materials'] if m['id'].startswith('message:')]
        origin=next((m for m in sources if json.loads(m['text']).get('role')=='memory'),sources[0])
        return [dict(item,sources=[origin['id']]) for item in case['obligations']]
    budget=before['budget'];limits=Limits(min(600,budget['research_walltime_ms']['available']/1000),min(20,budget['turns']['available']),min(20,budget['tool_executions']['available']))
    prior_step=root/'steps'/f'automatic-{cycle-1:03d}-generator/result.json'
    previous=json.loads(prior_step.read_text()) if cycle>1 and prior_step.is_file() else None
    engine=ContextMaintenance(subject='generator',reviewer_subject='reviewer',runtime_factory=runtime,bridge_factory=bridge,
        config_dir=config,evidence_dir=root/'context-maintenance',limits=limits,obligations=obligations,previous_result=previous)
    step=root/'steps'/(prefix+'-generator');step.mkdir(parents=True)
    prompt=('继续原有工程上下文测试，不开展科研、不修改文件。先且仅调用一次asr state读取现行状态，之后不要再调用工具。'
        '然后依据当前研究记忆只返回JSON：input_custody(preserved/lost/unknown)，function_argument_receipt(not_recorded/recorded/unknown)，'
        'reproduction_scope(shared_service/external_independent/unknown)，independent_evaluation(not_completed/completed/unknown)，'
        'new_label_count(整数)，max_weight_difference(数值)，id_error_ratio(字符串数值)。不知道就写unknown，不猜测或重做实验。'
        '如果中途发生上下文维护，继续原问题；已执行的state不要重复调用。')
    write(step/'request.json',dict(subject='generator',prompt=prompt,test_capacity_policy=policy))
    failure=None
    try:
        if before['state']!='running':service.command(tokens['human'],p,r,'resume',expected_revision=before['control_revision'],idempotency_key=prefix+':resume')
        current=service.research_note(tokens['generator'],p,r,operation='read',idempotency_key=prefix+':note-read')
        if current.get('restoration',{}).get('status')!='ready':
            # Test-only engineering note renewal; never do this for science.
            sources=service.organization_records(tokens['generator'],p,r,after=0,limit=100)['records']
            direction=next(x for x in sources if x['kind']=='direction' and x['entity_id']=='context-engineering')
            draft=service.research_note(tokens['generator'],p,r,operation='save',idempotency_key=prefix+':note-save',
                text='工程自动接续验收；保留失败、反证与范围限制，不开展科学实验，不将内部复现称为独立验证。',source_sequences=[direction['seq']])
            adopted=service.research_note(tokens['generator'],p,r,operation='adopt',idempotency_key=prefix+':note-adopt',revision=draft['revision'],expected_note=current['accepted_revision'])
            write(work/'engineering-note-renewal.json',dict(reason='恢复后控制版本改变；开发侧工程笔记显式更新，非自动改写科研笔记。',receipt=adopted))
        with AsyncEventRecorder(step/'events.jsonl') as recorder:
            result=run_with_maintenance(runtime('generator'),bridge('generator'),maintenance=engine,config_dir=config,
                native_session_id=native,prompt=prompt,limits=limits,on_event=recorder)
        result['communication_recording']=recorder.receipt;write(step/'result.json',result)
        answer=reply(result);write(step/'reply.json',answer)
        checks={item['id']:answer.get(item['id'])==item['value'] for item in case['obligations']}
        checks.update(automatic_boundary_observed=bool(result.get('context_maintenance_attempts')),
            installation_verified=result.get('context_installation_verified') is True or any(x.get('status')=='verified' for x in result.get('context_recovery_installations',[])),
            original_native_identity=result['native_session_id']==native)
        if not all(checks.values()):raise ValueError('automatic_acceptance_check_failed')
        write(work/'success.json',dict(status='passed',checks=checks,provider_payload_verified=False,
            boundary='真实模型与原生安装闭环；测试预警刺激，不是生产容量准确性或长程科研验证。'))
    except Exception as error:
        failure=dict(type=type(error).__name__,code=getattr(error,'code',str(error)),automatic_retry=False)
        write(work/'failure.json',failure)
    finally:
        state=drain(service,tokens['human'],p,r)
        write(work/'closeout.json',dict(failure=failure,budget=state['budget'],state=state['state'],sessions=state['runtime_sessions']))
        archive(root,work/'communications')
    print(json.dumps(dict(work=str(work),failure=failure),ensure_ascii=False))
    return failure


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--execute-authorized-subscription',action='store_true');parser.add_argument('--proxy');parser.add_argument('--cycle',type=int,default=1);args=parser.parse_args()
    if not args.execute_authorized_subscription:parser.error('explicit subscription execution flag required')
    if args.proxy:os.environ.update(HTTP_PROXY=args.proxy,HTTPS_PROXY=args.proxy,NO_PROXY='127.0.0.1,localhost')
    raise SystemExit(1 if execute(args.root,cycle=args.cycle) else 0)
