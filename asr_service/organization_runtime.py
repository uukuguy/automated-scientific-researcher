"""Bind organization identity to the existing single-owner runtime reservation."""
import hashlib
import re

from .contracts import encoded
from .organization import latest, member, require

PROFILE = 'research-organization/1'
STUDY_PROFILE = 'research-organization-study/1'


def describe(service, token, project, run, *, capability_profile, capability_pack_sha256):
    principal = service._auth(token, project, {'researcher'})
    with service._connect() as db:
        service._run(db, project, run)
        role = member(db, project, run, principal['subject'])
        record = latest(db, project, run, 'member', principal['subject'])
        binding = dict(subject=principal['subject'], role=role, member_revision=record['revision'],
            member_sha256=hashlib.sha256(encoded(record).encode()).hexdigest(),
            capability_profile=capability_profile, capability_pack_sha256=capability_pack_sha256)
        validate(db, project, run, binding)
        return binding


def validate(db, project, run, binding):
    enabled = latest(db, project, run, 'policy', 'capacity') is not None
    if not enabled:
        require(binding is None, 'organization_policy_required')
        return
    require(type(binding) is dict, 'organization_binding_required')
    require(set(binding) == {'subject','role','member_revision','member_sha256','capability_profile','capability_pack_sha256'},
            'invalid_organization_binding')
    require(type(binding['subject']) is str and type(binding['member_revision']) is int, 'invalid_organization_binding')
    require(binding['capability_profile'] in (PROFILE,STUDY_PROFILE), 'organization_profile_unavailable')
    require(type(binding['capability_pack_sha256']) is str and re.fullmatch('[a-f0-9]{64}', binding['capability_pack_sha256']) is not None,
            'invalid_organization_binding')
    record = latest(db, project, run, 'member', binding['subject'])
    require(record is not None and record['document']['enabled'] and
            record['revision'] == binding['member_revision'] and record['document']['role'] == binding['role'] and
            hashlib.sha256(encoded(record).encode()).hexdigest() == binding['member_sha256'], 'organization_binding_stale')
    if binding['capability_profile'] == STUDY_PROFILE:
        require(binding['role'] in ('lead','worker'), 'organization_scientific_role_required')
        from .control import ControlService
        running=ControlService._run(db,project,run)
        contract=ControlService._contract(db,project,running['contract_id'],running['contract_revision'])
        require(contract['document']['provenance'].get('capability_profile')=='ood-study-development/1',
                'organization_scientific_contract_required')
