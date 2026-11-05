"""Advisory capacity assessment from pinned SDK metadata, never an admission gate."""
from asr_context.capacity import decide
from .capacity_policy import load_policy


RESERVES={'completion':'context_completion_reserve_bps',
          'tool_results':'context_tool_reserve_bps','checkpoint':'context_checkpoint_reserve_bps'}


def assess(observation, *, policy=None, capacity_policy_path=None):
    policy=policy if policy is not None else load_policy(capacity_policy_path)
    result=dict(schema='asr-runtime-capacity-observation/1',status='deferred',measurement='estimate',unit='tokens',
        warning=False,recommendation='measurement_required',hold_new_model_requests=False,
        installation_authorized=False,request_capacity_verified=False,model_window_verified=False,
        capacity_policy_sha256=policy['sha256'],scope='request_boundary_advisory',
        purpose='记录SDK投影估算与预留，不据此证明下一完整请求可容纳或授予安装权限。')
    if (type(observation) is not dict or observation.get('type')!='asr_context_capacity' or
        observation.get('schema')!='asr-pi-context-capacity/1' or observation.get('measurement')!='estimate' or
        observation.get('full_next_request_verified') is not False or observation.get('provider_payload_verified') is not False):
        return dict(result,reason='invalid_native_capacity_observation')
    used=observation.get('used_tokens');window=observation.get('window_tokens')
    if (used is not None and (type(used) is not int or used<0) or
        window is not None and (type(window) is not int or window<1)):
        return dict(result,reason='invalid_native_capacity_usage')
    result.update(status='observed' if used is not None and window is not None else 'unknown',
                  used_tokens=used,window_tokens=window,window_source='pinned_sdk_getContextUsage')
    if window is None:return result
    ratios={name:policy['limits'][key]['value'] for name,key in RESERVES.items()}
    reserves={name:(window*value+9999)//10000 for name,value in ratios.items()}
    decision=decide(used_tokens=used,window_tokens=window,completion_reserve=reserves['completion'],
                    tool_reserve=reserves['tool_results'],checkpoint_reserve=reserves['checkpoint'],measurement='estimate')
    result.update(reserves=reserves,reserve_basis_points=ratios,core_recommendation=decision['action'])
    if 'safe_remaining_tokens' in decision:
        remaining=decision['safe_remaining_tokens']
        result.update(estimated_remaining_tokens=remaining,warning=remaining<0,
                      recommendation='prepare_context_review' if remaining<0 else 'observation_only')
    return result
