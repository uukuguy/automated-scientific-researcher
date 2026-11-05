"""Shared historical-source paging policy; refusal preserves the research."""
from .control import ControlError


def parameters(service,project,run,offset,limit,*,code):
    policy=service.artifact_io_policy;caps=policy['limits']
    required=('source_page_default_characters','source_page_max_characters')
    if any(name not in caps for name in required):raise ControlError('capacity_policy_fields_required')
    effective=caps[required[0]]['value'] if limit is None else limit
    maximum=caps[required[1]]['value']
    if type(offset) is int and offset>=0 and type(effective) is int and 1<=effective<=maximum:return effective
    error=ControlError(code)
    error.details=dict(offset=offset if type(offset) is int else type(offset).__name__,limit=effective if type(effective) is int else type(effective).__name__,
        max_characters=maximum,unit='unicode_characters',capacity_policy_sha256=policy['sha256'],purpose=caps[required[1]]['purpose'],
        action='request_deferred',recovery=f'Use limit 1..{maximum} and follow next_offset; originals and the research are unchanged.')
    with service._connect() as db:
        service._event(db,project,run,'source_page_deferred',reason=code,details=error.details)
    raise error
