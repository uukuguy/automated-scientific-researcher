"""Pure pre-application checks. The host still owns authority and installation."""
from . import _encode
from .summary import check,_digest
from .summary_review import assess


def _state(value):
    keys={'project_id','run_id','contract_revision','control_revision','task_revisions','unsettled_executions','source_fingerprints'}
    if type(value) is not dict or set(value)!=keys:raise ValueError('invalid_application_state')
    if any(type(value[k]) is not str or not value[k] for k in ('project_id','run_id')):raise ValueError('invalid_application_scope')
    if any(type(value[k]) is not int or value[k]<0 for k in ('contract_revision','control_revision')):raise ValueError('invalid_application_revision')
    for key in ('task_revisions','source_fingerprints'):
        if type(value[key]) is not dict or any(type(k) is not str or not k for k in value[key]):raise ValueError('invalid_application_binding')
    if any(type(v) is not int or v<0 for v in value['task_revisions'].values()):raise ValueError('invalid_application_task')
    if any(type(v) is not str or not v for v in value['source_fingerprints'].values()):raise ValueError('invalid_application_source')
    executions=value['unsettled_executions']
    if type(executions) is not list or any(type(v) is not str or not v for v in executions) or len(set(executions))!=len(executions):raise ValueError('invalid_application_execution')


def plan(request,candidate,review_request,review,*,author_session,reviewer_session,
         expected_state,current_state,open_interactions=()):
    """Recompute checks rather than trusting an incoming 'passed' label.

    State snapshots/session identities must come from the authorized host, never
    from a model's self-report. No permission, state mutation or file write here.
    """
    base=dict(schema='asr-context-application-plan/1',eligible_for_application=False,
              boundary='只读准备检查；仍须Control准入、实际安装及生效核对，不是科学验证。')
    try:
        _state(expected_state);_state(current_state)
        if type(open_interactions) is not tuple or any(type(v) is not str or not v for v in open_interactions):raise ValueError('invalid_application_boundary')
        if check(request,candidate)['status']!='pending_semantic_review':raise ValueError('structural_review_required')
        payload=review_request['payload']
        if _encode(payload['original'])!=_encode(request) or _encode(payload['candidate'])!=_encode(candidate):raise ValueError('candidate_review_mismatch')
        semantic=assess(review_request,review,author_session=author_session,reviewer_session=reviewer_session)
        if semantic['status']!='reviewed':raise ValueError('accepted_semantic_review_required')
        bindings={s['id']:s['sha256'] for s in request['payload']['sources']}
        if any(expected_state['source_fingerprints'].get(k)!=v for k,v in bindings.items()):raise ValueError('original_source_binding_missing')
        if _encode(expected_state)!=_encode(current_state):return dict(base,status='deferred',reason='research_state_changed')
        if open_interactions:return dict(base,status='deferred',reason='interaction_boundary_open',open_interactions=list(open_interactions))
        return dict(base,status='admission_required',request_sha256=request['request_sha256'],candidate_sha256=_digest(candidate),
                    review_sha256=review_request['review_sha256'],review_reply_sha256=_digest(review),state_sha256=_digest(current_state),
                    preserve_unsettled_executions=list(current_state['unsettled_executions']))
    except (ValueError,TypeError,KeyError) as error:
        return dict(base,status='rejected',reason=str(error) if isinstance(error,ValueError) else 'malformed_application_input')
