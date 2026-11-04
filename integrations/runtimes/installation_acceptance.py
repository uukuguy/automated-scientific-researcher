"""Explicit subscription installation acceptance, reusing the existing funded ledger."""
import argparse,hashlib,json,os,uuid,shutil,sqlite3
from pathlib import Path
from asr_context import Material
from asr_context.summary import prepare,check
from asr_context.summary_review import prepare_review,assess
from asr_service.control import ControlService
from integrations.aar.bridge import ResearchBridge
from .summary_acceptance import credentials,parse_reply,drain
from .communication_archive import EventRecorder,archive
from .pi import PiRuntime,Limits
from .session import run_session

HERE=Path(__file__).resolve().parent

def execute(root,*,resume_reason=None,cycle=1):
    root=Path(root).resolve();identity=json.loads((root/'identity.json').read_text());project=identity['project_id'];run=identity['research_run_id']
    prefix=f'installation-{cycle:03d}';work=root/prefix;work.mkdir(mode=0o700,exist_ok=True)
    if (work/'success.json').exists():raise ValueError('installation_validation_already_completed')
    tokens,principals=credentials(project);service=ControlService(root/'control.db',credentials=principals)
    def write(name,value):
        path=work/name
        with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2)
    def state():return service.get_run(tokens['human'],project,run)
    def command(kind,payload=None):
        current=state();return service.command(tokens['human'],project,run,kind,expected_revision=current['control_revision'],idempotency_key=prefix+':'+kind,payload=payload)
    failure=None;steps=[]
    try:
        if cycle>1 and not (work/'configured.json').exists():
            from .process import verify_process_exit
            current=state()
            if any(v['reserved'] for v in current['budget'].values()):raise ValueError('reconcile_before_second_cycle')
            for session in current['runtime_sessions']:
                if session['state']!='exited':raise ValueError('reconcile_before_second_cycle')
                verify_process_exit(session['process_identity'],terminate=False)
            base=json.loads((root/'installation-001'/'configured.json').read_text())
            command('resume')
            write('configured.json',dict(contract_revision=current['contract_revision'],budget_changes=False,before_budget=current['budget'],run=run,target_native_id=base['target_native_id'],purpose='检验第二轮真实压缩、RPC通知与继续执行保护，复用同一订阅工程预算。'))
        if not (work/'configured.json').exists():
            current=state()
            if any(s['state']!='exited' for s in current['runtime_sessions']) or any(v['reserved'] for v in current['budget'].values()):raise ValueError('reconcile_existing_sessions_first')
            with service._connect() as db:contract=service._contract(db,project,current['contract_id'],current['contract_revision'])
            document=contract['document'];document['objective']=dict(question='验证研究会话摘要的真实安装、原件保护和继续执行。',success_criteria='独立会话摘要复核；真实pi写入与投影核验；订阅会话继续回忆事实。',scope='用户本轮明确要求完成压缩闭环；零科研实验，仅工程上下文安装验证。')
            published=service.publish_contract(tokens['human'],project,current['contract_id'],document,expected_revision=contract['revision'],idempotency_key=prefix+':contract')
            command('apply_contract',dict(contract_id=current['contract_id'],revision=published['revision']))
            service.change_organization(tokens['human'],project,run,kind='policy',entity_id='capacity',expected_revision=0,idempotency_key=prefix+':policy',document=dict(max_active_leads=2,max_active_workers=1))
            for subject in ('generator','reviewer'):
                service.change_organization(tokens['human'],project,run,kind='member',entity_id=subject,expected_revision=0,idempotency_key=prefix+':member:'+subject,document=dict(role='lead',enabled=True))
            command('resume')
            direction=service.change_organization(tokens['generator'],project,run,kind='direction',entity_id='context-engineering',expected_revision=0,idempotency_key=prefix+':direction',document=dict(title='上下文工程验收',question='记录安装后能否保留范围限制并继续任务？',owner='generator',status='proposed',rationale='开发侧工程测试，不是新增科学方向。',evidence_trial_ids=[]))
            draft=service.research_note(tokens['generator'],project,run,operation='save',idempotency_key=prefix+':note',text='这是工程验收。保留失败、反证与范围限制，不把内部复现称为独立验证；不重复科研实验。',source_sequences=[direction['seq']])
            service.research_note(tokens['generator'],project,run,operation='adopt',idempotency_key=prefix+':adopt',revision=draft['revision'],expected_note=None)
            write('configured.json',dict(contract_revision=published['revision'],budget_changes=False,before_budget=current['budget'],run=run,target_native_id=str(uuid.uuid4())))
        elif state()['state']!='running':
            if not resume_reason:raise ValueError('explicit_recovery_required')
            from .process import verify_process_exit
            for prior in state()['runtime_sessions']:
                if prior['state']!='exited':raise ValueError('reconcile_before_recovery')
                verify_process_exit(prior['process_identity'],terminate=False)
            recovery='installation-recovery-'+uuid.uuid4().hex
            prior_state=state()
            service.command(tokens['human'],project,run,'resume',expected_revision=prior_state['control_revision'],idempotency_key=recovery)
            write(recovery+'.json',dict(reason=resume_reason,prior_budget=prior_state['budget'],budget_changes=False,repeated_model_calls=False))
        current_note=service.research_note(tokens['generator'],project,run,operation='read',idempotency_key='installation-current-note')
        if current_note.get('restoration',{}).get('status')!='ready':
            records=service.organization_records(tokens['generator'],project,run,after=0,limit=100)['records']
            source=next(r for r in records if r['kind']=='direction' and r['entity_id']=='context-engineering')
            revision_key='installation-note-current-'+str(state()['control_revision'])
            draft=service.research_note(tokens['generator'],project,run,operation='save',idempotency_key=revision_key,text='这是工程验收。保留失败、反证与范围限制，不把内部复现称为独立验证；不重复科研实验。',source_sequences=[source['seq']])
            service.research_note(tokens['generator'],project,run,operation='adopt',idempotency_key=revision_key+':adopt',revision=draft['revision'],expected_note=current_note['accepted_revision'])
        config=json.loads((work/'configured.json').read_text());native_id=config['target_native_id']
        os.environ.update(HTTP_PROXY='http://127.0.0.1:7897',HTTPS_PROXY='http://127.0.0.1:7897',NO_PROXY='127.0.0.1,localhost')
        def call(name,subject,prompt,*,native=None,compact=False,stage=None):
            step=work/name
            if (step/'runtime-result.json').exists():return json.loads((step/'runtime-result.json').read_text()),json.loads((step/'reply.json').read_text())
            step.mkdir(mode=0o700)
            with (step/'request.json').open('x') as f:json.dump(dict(subject=subject,prompt=prompt,compact_before_prompt=compact,stage_id=stage),f,ensure_ascii=False)
            budget=state()['budget'];seconds=min(600,budget['research_walltime_ms']['available']/1000)
            if seconds<10:raise ValueError('authorized_budget_exhausted')
            workspace=(root/'installation-001'/'target-workspace') if native else work/(name+'-workspace');workspace.mkdir(exist_ok=True)
            bridge=ResearchBridge(service,project=project,run=run,researcher_token=tokens[subject],supervisor_token=tokens['supervisor'],workspace=workspace,snapshots=root/'snapshots',capability_profile='research-organization/1')
            bridge.context_installation_id=stage
            runtime=PiRuntime(model=identity['model'],capabilities_path=HERE/'organization-capabilities.json',compact_before_prompt=compact)
            with (step/'events.jsonl').open('x') as stream:
                result=run_session(runtime,bridge,config_dir=(root/'installation-001'/'pi-private') if native else work/'pi-private',native_session_id=native or str(uuid.uuid4()),prompt=prompt,limits=Limits(seconds,min(20,budget['turns']['available']),min(20,budget['tool_executions']['available'])),on_event=EventRecorder(stream))
            with (step/'runtime-result.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
            if result['status']!='settled':raise ValueError('model_session_'+result['status'])
            reply=parse_reply(result)
            with (step/'reply.json').open('x') as f:json.dump(reply,f,ensure_ascii=False,indent=2)
            steps.append(dict(step=name,session_id=result['runtime_claim']['session_id'],status=result['status']))
            print(name,'settled',flush=True);return result,reply
        case=json.loads(Path('tests/fixtures/research_context/summary-fidelity.json').read_text());report=Path(case['sources'][0]['path']).read_bytes()
        if hashlib.sha256(report).hexdigest()!=case['sources'][0]['sha256']:raise ValueError('frozen_source_changed')
        if cycle==1:
            first,_=call('01-source','generator','只读工程记忆测试，不使用工具、不开展研究。阅读下列冻结的实际研究报告，返回JSON {"limitations":中文限制说明}。不得把内部复现称为外部验证。\n'+report.decode(),native=native_id)
            second,_=call('02-tail','generator','继续同一工程测试。只返回JSON {"pending":中文说明下一步仍需核对什么}，不要执行实验、不要调用工具。',native=native_id)
        else:
            prior=next(directory for directory in reversed(sorted(root.glob('installation-*'))) if directory!=work and (directory/'success.json').is_file())
            second=json.loads((prior/'05-installed-continuation'/'runtime-result.json').read_text())
        path=Path(second['recovery']['native_session_file']).resolve()
        from .pi_context import observe
        lines=[json.loads(line) for line in path.read_text().splitlines() if line.strip()];leaf=lines[-1]['id']
        registration=service.register_context_source(tokens['human'],project,run,subject='generator',idempotency_key=prefix+':source',path=str(path),native_session_id=native_id,leaf_id=leaf,keep_recent_groups=1,max_journal_bytes=134217728)
        if registration['status']!='registered':raise ValueError('source_registration_deferred')
        prepared=service.prepare_context(tokens['human'],project,run,subject='generator',reviewer_subject='reviewer',idempotency_key=prefix+':prepare',source_registration=prefix+':source')
        rows=registration['observation']['conversation']['body']['messages'];users=[r for r in rows if r['role']=='user'];origin=next((r['id'] for r in rows if r['role']=='memory'),users[0]['id']);tail=users[-1]['id']
        mapping={r['message_id']:r['native_entry_id'] for r in registration['observation']['witness']['source_mapping']};cut=mapping[tail]
        obligations=[dict(item,sources=[origin]) for item in case['obligations']]
        material_rows=[Material(**{k:tuple(v) if k in ('references','roles','citations') else v for k,v in m.items()}) for m in prepared['materials']]
        request=prepare(material_rows,obligations,role='generator',max_bytes=524288)
        if not (work/'summary-request.json').exists():write('summary-request.json',request)
        generated,candidate=call('03-summary','generator','你是摘要生成器，只返回JSON。严格且仅按obligations生成claims，额外事实放正文text。保留失败、限制与未决事项。不调用工具。\n'+json.dumps(request,ensure_ascii=False))
        if check(request,candidate)['status']!='pending_semantic_review':raise ValueError('candidate_rejected')
        review_request=prepare_review(request,candidate,max_bytes=1048576)
        reviewed,review=call('04-review','reviewer','你是未参与摘要生成的独立会话复核员。核对正文与原文，不能只信claims。只返回协议JSON，不调用工具。\n'+json.dumps(review_request,ensure_ascii=False))
        author=generated['runtime_claim']['session_id'];reviewer=reviewed['runtime_claim']['session_id']
        assessment=assess(review_request,review,author_session=author,reviewer_session=reviewer)
        if assessment['status']!='reviewed':raise ValueError('semantic_review_rejected')
        admission=service.admit_context(tokens['human'],project,run,subject='generator',preparation_id=prepared['preparation_id'],idempotency_key=prefix+':admission',request=request,candidate=candidate,review_request=review_request,review=review,author_session=author,reviewer_session=reviewer)
        if admission['status']!='admitted':raise ValueError('admission_deferred')
        staged=service.stage_context_installation(tokens['human'],project,run,subject='generator',admission_id=prefix+':admission',first_kept_entry_id=cut,idempotency_key=prefix+':stage')
        write('installation-plan.json',staged)
        prompt='继续原工程测试，依据当前上下文中的研究记忆回答，只返回JSON，不使用工具。请返回以下字段：input_custody(preserved/lost/unknown)，function_argument_receipt(not_recorded/recorded/unknown)，reproduction_scope(shared_service/external_independent/unknown)，independent_evaluation(not_completed/completed/unknown)，new_label_count(整数)，max_weight_difference(数值)，id_error_ratio(字符串数值)。不知道就写unknown，不能猜测或重做实验。'
        continued,reply=call('05-installed-continuation','generator',prompt,native=native_id,compact=True,stage=staged['stage_id'])
        expected={item['id']:item['value'] for item in case['obligations']}
        checks={key:reply.get(key)==value for key,value in expected.items()}
        current=state();sessions=current['runtime_sessions'];latest=next(s for s in sessions if s['session_id']==continued['runtime_claim']['session_id'])
        installed=latest.get('native_context',{}).get('installed_context')
        if not installed or installed['status']!='verified' or not all(checks.values()):raise ValueError('installation_or_continuation_check_failed')
        write('success.json',dict(status='passed',checks=checks,installed=installed,journal_bytes_after_continuation=path.stat().st_size,steps=steps,new_scientific_trials=0,provider_payload_verified=False))
    except Exception as error:
        failure=dict(type=type(error).__name__,code=getattr(error,'code',str(error)),automatic_retry=False)
        print('FAILURE',failure,flush=True)
    finally:
        current=drain(service,tokens['human'],project,run)
        suffix=uuid.uuid4().hex[:8]
        write('closeout-'+suffix+'.json',dict(failure=failure,steps=steps,budget=current['budget'],sessions=current['runtime_sessions'],state=current['state']))
        with (work/'identity.json').open('w') as f:json.dump(identity,f)
        export_communications(root,work,'communications-complete-'+suffix)
    return failure

def export_communications(root,work,name):
    """Freeze a read-only Control backup and standard step layout for the exporter."""
    root=Path(root);work=Path(work)
    outside=any(not Path(json.loads(p.read_text()).get('recovery',{}).get('native_session_file',str(work))).is_relative_to(work) for p in work.glob('0*/runtime-result.json'))
    if outside:
        for cycle_dir in sorted(root.glob('installation-*')):
            if not cycle_dir.is_dir():continue
            for step in sorted(cycle_dir.glob('0*')):
                if not step.is_dir() or not (step/'request.json').is_file():continue
                dest=root/'steps'/(cycle_dir.name+'-'+step.name);dest.mkdir(parents=True,exist_ok=True)
                for origin,target in [('request.json','request.json'),('events.jsonl','events.jsonl'),('runtime-result.json','result.json'),('reply.json','reply.json')]:
                    if (step/origin).is_file() and not (dest/target).exists():shutil.copyfile(step/origin,dest/target)
        return archive(root,work/name)
    with sqlite3.connect(root/'control.db') as source,sqlite3.connect(work/'control.db') as target:source.backup(target)
    for step in sorted(work.glob('0*')):
        if not step.is_dir() or not (step/'request.json').is_file():continue
        dest=work/'steps'/step.name;dest.mkdir(parents=True,exist_ok=True)
        for origin,target in [('request.json','request.json'),('events.jsonl','events.jsonl'),('runtime-result.json','result.json'),('reply.json','reply.json')]:
            if (step/origin).is_file() and not (dest/target).exists():shutil.copyfile(step/origin,dest/target)
    if (root/'research-notes').exists():shutil.copytree(root/'research-notes',work/'research-notes',dirs_exist_ok=True)
    return archive(work,work/name)



def retrieve_after_installation(root):
    root=Path(root).resolve();work=root/'installation-005';identity=json.loads((root/'identity.json').read_text());project=identity['project_id'];run=identity['research_run_id']
    tokens,principals=credentials(project);service=ControlService(root/'control.db',credentials=principals)
    current=service.get_run(tokens['human'],project,run)
    if any(s['state']!='exited' for s in current['runtime_sessions']):raise ValueError('reconcile_before_source_retrieval')
    source_id='installation-001:source'
    from asr_service.context_admission import _scope
    with service._connect() as db:
        source=json.loads(db.execute('SELECT record FROM asr_requests WHERE project=? AND scope=? AND request_key=?',(project,_scope('source',run,'generator'),source_id)).fetchone()[0])
    record=next(r for r in source['observation']['conversation']['body']['messages'] if r['role']=='user')
    step=work/'06-source-retrieval';step.mkdir(mode=0o700)
    before=current['budget']
    service.command(tokens['human'],project,run,'resume',expected_revision=current['control_revision'],idempotency_key='installation-source-read:resume')
    os.environ.update(HTTP_PROXY='http://127.0.0.1:7897',HTTPS_PROXY='http://127.0.0.1:7897',NO_PROXY='127.0.0.1,localhost')
    prompt='工程验收：不要凭摘要回忆作答。先实际调用asr工具 operation=research_note，arguments='+json.dumps(dict(operation='conversation_read',source_registration=source_id,message_id=record['id'],offset=0,limit=16000),ensure_ascii=False)+'，key请自行选唯一字符串。读取返回的冻结旧原文，不读本机文件，不做实验。随后只输出JSON {"input_quote":原文中关于完整任务输入同期保留的短句,"scope_quote":原文中关于共用同一宿主训练服务的短句}，每段引文必须逐字来自工具返回原文，不要转述。'
    with (step/'request.json').open('x') as f:json.dump(dict(subject='generator',prompt=prompt),f,ensure_ascii=False)
    bridge=ResearchBridge(service,project=project,run=run,researcher_token=tokens['generator'],supervisor_token=tokens['supervisor'],workspace=root/'installation-001'/'target-workspace',snapshots=root/'snapshots',capability_profile='research-organization/1')
    budget=service.get_run(tokens['human'],project,run)['budget'];native=json.loads((root/'installation-001'/'configured.json').read_text())['target_native_id']
    try:
        with (step/'events.jsonl').open('x') as stream:
            result=run_session(PiRuntime(model=identity['model'],capabilities_path=HERE/'organization-capabilities.json'),bridge,config_dir=root/'installation-001'/'pi-private',native_session_id=native,prompt=prompt,limits=Limits(min(600,budget['research_walltime_ms']['available']/1000),min(20,budget['turns']['available']),min(20,budget['tool_executions']['available'])),on_event=EventRecorder(stream))
        with (step/'runtime-result.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
        reply=parse_reply(result)
        with (step/'reply.json').open('x') as f:json.dump(reply,f,ensure_ascii=False,indent=2)
        events=[json.loads(line)['event'] for line in (step/'events.jsonl').read_text().splitlines()]
        calls=[e for e in events if e.get('type')=='tool_execution_start' and e.get('args',{}).get('operation')=='research_note' and e['args'].get('arguments',{}).get('operation')=='conversation_read']
        checks=dict(actual_source_tool_called=bool(calls),input_quote_exact=bool(reply.get('input_quote')) and reply['input_quote'] in record['text'],scope_quote_exact=bool(reply.get('scope_quote')) and reply['scope_quote'] in record['text'])
        if not all(checks.values()):raise ValueError('actual_source_retrieval_failed')
        receipt=dict(status='passed',checks=checks,source_registration=source_id,message_id=record['id'],source_text_sha256=hashlib.sha256(record['text'].encode()).hexdigest(),session_id=result['runtime_claim']['session_id'],tool_executions=result['tool_executions'],reply=reply,before_budget=before)
        with (work/'source-retrieval-receipt.json').open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
        print('source_retrieval_passed',checks,flush=True)
    finally:
        final=drain(service,tokens['human'],project,run)
        with (work/'source-retrieval-closeout.json').open('x') as f:json.dump(dict(budget=final['budget'],sessions=final['runtime_sessions'],state=final['state']),f,ensure_ascii=False,indent=2)
        export_communications(root,work,'communications-with-source-read')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--resume-reason');parser.add_argument('--read-source',action='store_true');parser.add_argument('--cycle',type=int,choices=(1,2,3,4,5),default=1);args=parser.parse_args()
    if args.read_source:retrieve_after_installation(args.root)
    else:raise SystemExit(1 if execute(args.root,resume_reason=args.resume_reason,cycle=args.cycle) else 0)

