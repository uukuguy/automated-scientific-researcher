"""Serial context maintenance invoked by the existing research owner.

The files are immutable execution evidence, not a scheduler or authority ledger.
Control revalidates all state and issues the sole installation authorization.
"""
import copy
import json
import os
from pathlib import Path
import uuid

from asr_context import Material
from asr_context.summary import prepare, check
from asr_context.summary_review import prepare_review, assess
from .async_events import AsyncEventRecorder
from .pi import Limits
from .session import run_session


def source_obligations(sources):
    """Inventory binding only; semantic fidelity is explicitly left to review."""
    if not sources:raise ValueError('sources_required')
    return [dict(id='source:'+row['id'],value=row['sha256'],sources=[row['id']]) for row in sources]


def select_cut(observed):
    groups=observed['conversation']['groups']
    if len(groups)<2:raise ValueError('summarizable_prefix_required')
    first=groups[-1]['ids'][0]
    return next(row['native_entry_id'] for row in observed['witness']['source_mapping'] if row['message_id']==first)


def write(path,value):
    # An unfinished intent is deliberately not replayed as another model call.
    with Path(path).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())


def reply(result):
    if result['status']!='settled':raise ValueError('maintenance_session_'+result['status'])
    for message in reversed(result.get('assistant_messages',[])):
        text='\n'.join(p['text'] for p in message.get('content',[]) if p.get('type')=='text').strip()
        if not text:continue
        if text.startswith('```') and text.splitlines()[-1]=='```':text='\n'.join(text.splitlines()[1:-1])
        value=json.loads(text)
        if type(value) is not dict:raise ValueError('maintenance_reply_not_object')
        return value
    raise ValueError('maintenance_reply_missing')


class ContextMaintenance:
    def __init__(self, *, subject, reviewer_subject, runtime_factory, bridge_factory,
                 config_dir, evidence_dir, limits, oauth_source=None, obligations=None, previous_result=None):
        if not subject or not reviewer_subject or subject==reviewer_subject:raise ValueError('separate_reviewer_required')
        self.subject=subject;self.reviewer_subject=reviewer_subject
        self.runtime_factory=runtime_factory;self.bridge_factory=bridge_factory
        self.config_dir=Path(config_dir);self.evidence_dir=Path(evidence_dir)
        self.limits=limits;self.oauth_source=oauth_source;self.obligations=obligations;self.previous_result=previous_result

    def needs_preparation(self, previous):
        if not isinstance(previous,dict):return False
        if previous.get('status')=='settled':
            observations=previous.get('context_capacity_observations',[])
            return bool(observations and observations[-1].get('warning'))
        if previous.get('status')=='context_recovery_required':
            bridge=self.bridge_factory(self.subject)
            state=bridge.service.get_run(bridge.supervisor_token,bridge.project,bridge.run)
            session=next((x for x in state['runtime_sessions'] if x['session_id']==previous.get('runtime_claim',{}).get('session_id')),None)
            if session is None:return False
            native=session.get('native_context',{})
            for prior in reversed(state['runtime_sessions']):
                other=prior.get('native_context',{})
                if prior.get('organization_binding',{}).get('subject')!=self.subject or any(other.get(k)!=native.get(k) for k in ('native_session_id','journal_directory')):continue
                if other.get('pending_installation'):return False
                receipt=other.get('installed_context')
                if receipt:return receipt.get('status')=='verified' and receipt.get('requires_fresh_preparation') is True
            return False
        return False

    def prepare(self, previous):
        """Return a staged receipt or a recorded deferral; never resume on failure."""
        bridge=self.bridge_factory(self.subject);s=bridge.service;p=bridge.project;r=bridge.run;t=bridge.supervisor_token
        claim=previous['runtime_claim'];key='maintenance_'+claim['session_id']
        work=self.evidence_dir/key
        # A crash or prior failed attempt needs explicit reconciliation, not retry.
        work.mkdir(parents=True,mode=0o700,exist_ok=False)
        runtime=self.runtime_factory(self.subject);policy=runtime.capacity_policy
        write(work/'previous-result.json',previous)
        write(work/'intent.json',dict(project=p,run=r,subject=self.subject,reviewer_subject=self.reviewer_subject,
            previous_session=claim['session_id'],capacity_policy=policy,trigger=previous.get('context_maintenance_receipt'),
            scientific_truth_inferred=False))
        try:
            state=s.get_run(t,p,r)
            if state['state']!='running' or any(x['state']!='exited' for x in state['runtime_sessions']):raise ValueError('maintenance_reconciliation_required')
            old=next(x for x in state['runtime_sessions'] if x['session_id']==claim['session_id'])
            from .process import verify_process_exit
            verify_process_exit(old['process_identity'],terminate=False)
            if old.get('execution_exited') is not True or old.get('organization_binding',{}).get('subject')!=self.subject:raise ValueError('maintenance_source_identity_mismatch')
            if previous.get('recovery',{}).get('pending_tools'):raise ValueError('maintenance_open_tool_interaction')
            path=Path(previous['recovery']['native_session_file']).resolve()
            native=old['native_context'];native_id=native['native_session_id']
            if not path.is_relative_to(Path(native['journal_directory']).resolve()):raise ValueError('maintenance_source_outside_owner')
            cap=policy['limits']['journal_bytes']['value'];raw=path.open('rb')
            with raw:data=raw.read(cap+1)
            if len(data)>cap:return self._defer(bridge,work,key,dict(reason='maintenance_journal_capacity',limit_name='journal_bytes',configured=cap,observed=len(data),measurement='at_least_bytes',session_id=claim['session_id'],source=str(path)))
            rows=[json.loads(line) for line in data.splitlines() if line.strip()]
            leaf=next(row['id'] for row in reversed(rows) if row.get('type')!='session' and 'id' in row)
            registration=s.register_context_source(t,p,r,subject=self.subject,idempotency_key=key+':source',path=str(path),
                native_session_id=native_id,leaf_id=leaf,keep_recent_groups=1,max_journal_bytes=cap)
            if registration['status']!='registered':return self._defer(bridge,work,key,registration)
            cut=select_cut(registration['observation'])
            prepared=s.prepare_context(t,p,r,subject=self.subject,reviewer_subject=self.reviewer_subject,
                idempotency_key=key+':prepare',source_registration=key+':source')
            from asr_service.context_admission import source_rows
            materials=[Material(**{k:tuple(v) if k in ('references','roles','citations') else v for k,v in row.items()}) for row in prepared['materials']]
            obligations=self.obligations(prepared) if self.obligations is not None else source_obligations(source_rows(materials))
            if not obligations:raise ValueError('maintenance_obligations_required')
            request=prepare(materials,obligations,role=self.subject,max_bytes=policy['limits']['summary_bytes']['value'])
            write(work/'summary-request.json',request)
            if request['status']!='prepared':return self._defer(bridge,work,key,request)
            generated=self._call(work,'summary',self.subject,request)
            candidate=reply(generated)
            checked=check(request,candidate)
            if checked['status']!='pending_semantic_review':return self._defer(bridge,work,key,checked)
            review_request=prepare_review(request,candidate,max_bytes=policy['limits']['review_bytes']['value'])
            write(work/'review-request.json',review_request)
            if review_request['status']!='prepared':return self._defer(bridge,work,key,review_request)
            reviewed=self._call(work,'review',self.reviewer_subject,review_request)
            review=reply(reviewed);author=generated['runtime_claim']['session_id'];reviewer=reviewed['runtime_claim']['session_id']
            assessment=assess(review_request,review,author_session=author,reviewer_session=reviewer)
            if assessment['status']!='reviewed':return self._defer(bridge,work,key,assessment)
            admission=s.admit_context(t,p,r,subject=self.subject,preparation_id=prepared['preparation_id'],idempotency_key=key+':admission',
                request=request,candidate=candidate,review_request=review_request,review=review,author_session=author,reviewer_session=reviewer)
            if admission['status']!='admitted':return self._defer(bridge,work,key,admission)
            staged=s.stage_context_installation(t,p,r,subject=self.subject,admission_id=key+':admission',first_kept_entry_id=cut,idempotency_key=key+':stage')
            coverage=staged['plan']['coverage']
            replaced=set(coverage['summarized_ids'])|set(coverage['replayed_ids'])
            replaced-=set(row['id'] for row in staged['plan'].get('native_replayed_messages',[]))
            before_bytes=sum(len(row['text'].encode()) for row in registration['observation']['conversation']['body']['messages'] if row['id'] in replaced)
            after_bytes=len(staged['plan']['summary'].encode())
            benefit=dict(measurement='projected_text_utf8_bytes',before=before_bytes,after=after_bytes,
                         token_capacity_verified=False)
            write(work/'replacement-size.json',benefit)
            if after_bytes>=before_bytes:
                return self._defer(bridge,work,key,dict(reason='context_replacement_not_smaller',measurement=benefit))
            staged=dict(staged,native_sdk_recovery_install=rows[-1].get('type')=='compaction')
            write(work/'staged.json',staged)
            return staged
        except (ValueError,OSError,KeyError,StopIteration,RuntimeError) as error:
            return self._defer(bridge,work,key,dict(reason=getattr(error,'code',type(error).__name__),
                detail=str(error) if isinstance(error,ValueError) else None))

    def install_recovery(self,stage,previous):
        from .context_installer import install
        return install(self.runtime_factory(self.subject),self.bridge_factory(self.subject),stage=stage,source=previous,
            limits=self.limits,evidence_dir=self.evidence_dir/('maintenance_'+previous['runtime_claim']['session_id'])/'native-install')

    def _call(self, work, phase, subject, request):
        bridge=self.bridge_factory(subject)
        intent=json.loads((work/'intent.json').read_text())
        if (bridge.project!=intent['project'] or bridge.run!=intent['run'] or
            bridge.service._auth(bridge.researcher_token,bridge.project,{'researcher'})['subject']!=subject):
            raise ValueError('maintenance_model_scope_mismatch')
        state=bridge.service.get_run(bridge.supervisor_token,bridge.project,bridge.run)
        budget=state['budget']
        values=(min(self.limits.walltime_seconds,budget['research_walltime_ms']['available']/1000),
                min(self.limits.turns,budget['turns']['available']),min(self.limits.tool_executions,budget['tool_executions']['available']))
        if any(v<=0 for v in values):raise ValueError('maintenance_budget_exhausted')
        limits=Limits(*values)
        runtime=copy.copy(self.runtime_factory(subject));runtime.maintenance_only=True;runtime.compact_before_prompt=False
        bridge.allowed_operations={'permit'}
        directory=work/phase;directory.mkdir(mode=0o700)
        prompt=('你正在维护已有研究上下文，不开展科研，不修改记录或文件，不调用工具。'
            '来源指纹claims只绑定材料清单，不证明科学事实；正文必须保留重要事实、失败、反证、未决事项和限制，'
            '复核必须独立检查全部原文及正文遗漏。按以下协议只返回JSON。\n'+json.dumps(request,ensure_ascii=False))
        write(directory/'request.json',dict(subject=subject,prompt=prompt,limits=limits.__dict__))
        with AsyncEventRecorder(directory/'events.jsonl') as recorder:
            result=run_session(runtime,bridge,config_dir=self.config_dir,native_session_id=str(uuid.uuid4()),
                prompt=prompt,limits=limits,oauth_source=self.oauth_source,on_event=recorder)
        result['communication_recording']=recorder.receipt
        write(directory/'result.json',result)
        return result

    def _defer(self, bridge,work,key,detail):
        receipt=dict(status='deferred',reason='context_maintenance_deferred',detail=detail,
            context_installed=False,recoverable=True,automatic_retry=False,
            recovery='保留原会话、维护请求、模型费用和原始交流；核对失败原因后显式恢复，不重跑科研。')
        with bridge.service._connect() as db:
            bridge.service._event(db,bridge.project,bridge.run,'context_maintenance_deferred',subject=self.subject,maintenance_id=key,receipt=receipt)
        write(work/'deferred.json',receipt)
        return receipt


def run_with_maintenance(runtime, bridge, *, maintenance=None, **arguments):
    """A subroutine of the existing owner; no parallel scheduler or research replay."""
    attempts=[];current=runtime;prompt=arguments.pop('prompt')
    original_stage=bridge.context_installation_id
    previous=getattr(maintenance,'previous_result',None) if maintenance is not None else None
    pending=previous if isinstance(previous,dict) and maintenance.needs_preparation(previous) else None
    first=True;recovery_installations=[]
    try:
        while True:
            if pending is None:
                result=run_session(current,bridge,prompt=prompt,context_maintenance=maintenance is not None,**arguments)
                if result['status']!='context_maintenance_required' or maintenance is None:
                    return dict(result,context_maintenance_attempts=attempts,context_recovery_installations=recovery_installations)
            else:
                result=pending;pending=None
            attempts.append(result)
            try:
                if result.get('native_session_id') not in (None,arguments.get('native_session_id')):
                    raise ValueError('maintenance_native_identity_mismatch')
                staged=maintenance.prepare(result)
                if staged.get('status')=='staged' and staged.get('native_sdk_recovery_install'):
                    verified=maintenance.install_recovery(staged,result)
                    if verified.get('status')!='verified':staged=dict(status='deferred',reason='native_recovery_installation_unverified',verification=verified)
                    else:staged=dict(staged,native_recovery_verified=verified)
            except (ValueError,OSError,RuntimeError) as error:
                staged=dict(status='deferred',reason=getattr(error,'code',type(error).__name__),automatic_retry=False)
            if staged['status']!='staged':
                service=bridge.service
                receipt=service.defer_context_maintenance(bridge.supervisor_token,bridge.project,bridge.run,
                    session_id=result['runtime_claim']['session_id'],reason=staged.get('reason','context_maintenance_deferred'),
                    idempotency_key='maintenance-defer:'+result['runtime_claim']['session_id'])
                return dict(result,status='context_maintenance_deferred',maintenance=staged,pause_receipt=receipt,
                    context_maintenance_attempts=attempts[:-1])
            current=copy.copy(runtime);current.compact_before_prompt=not bool(staged.get('native_recovery_verified'))
            bridge.context_installation_id=None if staged.get('native_recovery_verified') else staged['stage_id']
            if not (first and result is previous):
                prompt=('上下文维护已完成准备。只有通过Control安装核验后才会发送本提示。'
                    '继续原会话中尚未完成的任务，先核对现行状态和已有执行回执；不得重复已完成或状态未知的实验，'
                    '不得把摘要或维护当作新的科学指令。')
            if staged.get('native_recovery_verified'):recovery_installations.append(staged['native_recovery_verified'])
            first=False
    finally:
        bridge.context_installation_id=original_stage
