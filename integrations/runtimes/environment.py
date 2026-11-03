"""D021 subscription environment policy, independent of vendor key names.

The explicit non-Codex pi exception permits an environment setting only. It does
not authorize paid usage, switch providers or activate an API fallback. No current
subscription adapter enables that exception.
"""
import os

COMMON_ENVIRONMENT=('PATH','HOME','TMPDIR','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR',
                    'HTTPS_PROXY','HTTP_PROXY','NO_PROXY')


def api_key_name(name):
    return isinstance(name,str) and (name.upper()=='API_KEY' or name.upper().endswith('_API_KEY'))


def _exception(runtime,provider,allow_api_keys):
    if type(allow_api_keys) is not bool:raise ValueError('invalid_api_key_policy')
    if not allow_api_keys:return False
    normalized=provider.casefold().replace('_','-') if isinstance(provider,str) else ''
    if runtime!='pi' or not normalized or normalized in ('codex','openai-codex'):
        raise ValueError('api_key_exception_requires_explicit_noncodex_pi')
    return True


def reject_api_key_settings(settings,*,runtime,provider,allow_api_keys=False):
    permitted=_exception(runtime,provider,allow_api_keys)
    pending=[settings];seen=set()
    while pending:
        value=pending.pop()
        if isinstance(value,(dict,list,tuple)):
            if id(value) in seen:continue
            seen.add(id(value))
        if isinstance(value,dict):
            if not permitted and any(api_key_name(key) for key in value):
                raise ValueError('subscription_api_key_setting_forbidden')
            pending.extend(value.values())
        elif isinstance(value,(list,tuple)):pending.extend(value)


def build_environment(allowed,*,runtime,provider,inherited=None,overrides=None,allow_api_keys=False):
    permitted=_exception(runtime,provider,allow_api_keys)
    inherited=os.environ if inherited is None else inherited
    overrides={} if overrides is None else overrides
    reject_api_key_settings(overrides,runtime=runtime,provider=provider,allow_api_keys=allow_api_keys)
    if not isinstance(overrides,dict) or any(not isinstance(key,str) or not isinstance(value,str) for key,value in overrides.items()):
        raise ValueError('invalid_runtime_environment')
    allowed=set(allowed)
    if any(key not in allowed and not (permitted and api_key_name(key)) for key in overrides):
        raise ValueError('unsupported_runtime_environment')
    environment={key:value for key,value in inherited.items() if key in allowed and (permitted or not api_key_name(key))}
    environment.update(overrides)
    return environment
