"""Pure capacity decisions. No provider guesses, scheduler or cancellation."""


def decide(*,used_tokens,window_tokens,completion_reserve,tool_reserve,checkpoint_reserve,
           open_interactions=(),provider_context_rejected=False,measurement='reported'):
    """Reserves must be calibrated by the host for the selected model/load.

    A token count must cover the full next-request context, including retained
    prompts and tool data. Approximate counts are advisory, not admission proof.
    Holding new model requests never cancels existing numerical executions.
    """
    reserves=[completion_reserve,tool_reserve,checkpoint_reserve]
    if any(type(v) is not int or v<0 for v in reserves):raise ValueError('invalid_context_reserve')
    if any(v is not None and (type(v) is not int or v<0) for v in [used_tokens,window_tokens]) or window_tokens==0:raise ValueError('invalid_context_usage')
    if type(provider_context_rejected) is not bool or measurement not in ('reported','estimate'):raise ValueError('invalid_context_observation')
    if type(open_interactions) is not tuple or any(type(v) is not str or not v for v in open_interactions):raise ValueError('invalid_context_boundary')
    result=dict(schema='asr-context-capacity-decision/1',measurement=measurement,unit='tokens',
                used_tokens=used_tokens,window_tokens=window_tokens,
                reserves=dict(completion=completion_reserve,tool_results=tool_reserve,checkpoint=checkpoint_reserve),
                open_interactions=list(open_interactions),cancel_experiments=False)
    if provider_context_rejected:action='recover_context' if not open_interactions else 'wait_for_boundary'
    elif used_tokens is None or window_tokens is None:action='measurement_required'
    else:
        remaining=window_tokens-used_tokens-sum(reserves)
        result['safe_remaining_tokens']=remaining
        if measurement=='estimate':action='measure_before_admission'
        elif remaining>=0:action='continue'
        elif open_interactions:action='wait_for_boundary'
        elif used_tokens>=window_tokens:action='recover_context'
        else:action='prepare_compression'
    result.update(action=action,hold_new_model_requests=action!='continue',
                  purpose='保留回复、工具结果和安全检查点空间，避免在已知容量不足时再发完整提示。',
                  recovery='保留原文与在途执行，取得可靠用量或在完整交互边界准备/恢复上下文；不自动增加研究预算。')
    return result
