"""Project requirements and real capabilities, without a prescribed research path."""
import copy
import json
from pathlib import Path

from powerflow_lab.runner import digest
from .pi import Limits

ROOT = Path(__file__).resolve().parents[2]


def resources(path):
    value = json.loads(path.read_text())
    if (value.get('schema') != 'asr-organization-project-resources/1' or
            value.get('paid_api_authorized') is not False or value.get('paid_api_fallback') is not False):
        raise ValueError('explicit_subscription_project_resources_required')
    budget = value['budget']
    if (set(budget) != {'attempts','execution_ms','sample_proposals','research_walltime_ms','turns','tool_executions'} or
            any(type(v) is not int or not 0 <= v <= 2**63-1 for v in budget.values()) or
            any(budget[k] <= 0 for k in ('research_walltime_ms','turns','tool_executions'))):
        raise ValueError('explicit_project_budget_required')
    operations = value['study_operations']
    if (type(operations) is not list or not operations or any(x not in ('analysis','label','fit') for x in operations)
            or len(set(operations)) != len(operations)):
        raise ValueError('explicit_project_operations_required')
    Limits(**value['session_limits'])
    if type(value['analysis_timeout_seconds']) is not int or not 1 <= value['analysis_timeout_seconds'] <= 300:
        raise ValueError('explicit_job_timeout_required')
    if (set(value['capacity']) != {'max_active_leads','max_active_workers'} or
            any(type(v) is not int or v <= 0 for v in value['capacity'].values())):
        raise ValueError('explicit_organization_capacity_required')
    return value


def load_spec(path):
    value = json.loads(path.read_text())
    if (type(value) is not dict or set(value) != {'schema','title','objective','requirements','deliverables','materials'} or
            value['schema'] != 'asr-research-project/1'):
        raise ValueError('invalid_project_specification')
    if (type(value['objective']) is not dict or set(value['objective']) != {'question','success_criteria','scope'} or
            any(type(v) is not str or not v.strip() for v in [value['title'],*value['objective'].values()])):
        raise ValueError('project_objective_required')
    for key in ('requirements','deliverables'):
        if type(value[key]) is not list or not value[key] or any(type(v) is not str or not v.strip() for v in value[key]):
            raise ValueError('project_requirements_required')
    if type(value['materials']) is not dict:
        raise ValueError('project_materials_required')
    paths = {}
    for name, reference in value['materials'].items():
        if (type(name) is not str or Path(name).name != name or name in ('.','..','CLIENT-BRIEF.md','PROJECT-SPEC.json')):
            raise ValueError('invalid_workspace_material_name')
        if type(reference) is not dict or set(reference) != {'path','sha256'}:
            raise ValueError('invalid_material_reference')
        source = Path(reference['path'])
        source = source if source.is_absolute() else ROOT / source
        if source.is_symlink() or not source.is_file() or digest(source) != reference['sha256']:
            raise ValueError('project_material_pin_mismatch')
        paths[name] = source
    return value, paths


def scientific_configuration(policy):
    from asr_service.study import public_materials
    image = json.loads((ROOT / policy['image_manifest']).read_text())
    for relative, sha in image['sources'].items():
        if digest(ROOT / relative) != sha:
            raise ValueError('scientific_image_source_changed')
    public = (ROOT / policy['public_directory']).resolve()
    config = dict(public_directory=str(public), public_manifest_sha256=digest(public / 'manifest.json'),
                  image_id=image['image_id'], validator_sha256=image['sources']['powerflow_lab/validation.py'])
    public_materials(config)
    return config


def contract_fields(spec, policy, study_config):
    return dict(objective=copy.deepcopy(spec['objective']), provenance=dict(
        capability_profile='ood-study-development/1', study=study_config,
        study_operations=list(policy['study_operations'])))


def brief(spec):
    requirements = '\n'.join('- ' + v for v in spec['requirements'])
    deliverables = '\n'.join('- ' + v for v in spec['deliverables'])
    return f'''# Project requirements: {spec['title']}

Question: {spec['objective']['question']}
Acceptance: {spec['objective']['success_criteria']}
Scope: {spec['objective']['scope']}

## Project requirements
{requirements}

## Deliverables
{deliverables}

## Research ownership
Organizer, Leads and Workers own problem decomposition, scientific directions,
methods, experimental design, project code and intermediate artifacts. Historical
plans and developer-authored adapters are optional references, not instructions.
No research departments, particular sampler, model count or experiment sequence
are assigned by the host. Change scientific protocols prospectively and explicitly;
do not alter formal acceptance rules to turn a negative result into success.
Developers observe externally and repair infrastructure, not supply your research.

## Available execution interfaces and honest limits
Read state/effective contract for the authoritative current budget, operations,
versions and permissions. There is no short time target: complete useful work,
preserve progress, and stop when delivered. Never spend remaining quota for its
own sake or silently repeat failed computations. Subscription only; no API keys.
Role sessions currently execute serially. Organizer has coordination tools;
Leads/Workers have governed study tools. Task owners must be in_progress with
explicit experiment_operations and pass organization_task {{task_id,revision}}.
Scientific operations, when admitted: analysis accepts self-contained main(data)
source in the fixed offline scientific image; label solves submitted coordinates;
fit uses the fixed client trainer and declared augmentation dependencies.
These are capabilities, not a required scientific sequence. Use actual tool
schemas and receipts; do not claim execution from reading source or task status.
The current image/tool interface does not dynamically install new dependencies
or load arbitrary local modules. Report a concrete capability gap if it prevents
your chosen approach. Do not evade isolation, use host computation for experiments,
or pretend that an unavailable capability was exercised.
Independent hidden evaluation is not available to researcher tools. Public or
researcher-visible assessments are exploratory; request an explicit independent
evaluation protocol through Organizer when scientifically appropriate. Do not
reuse known historical outcomes as fresh hidden-test evidence.

## Coordination and delivery
Use current organization_records and exact revisions. Organizers manage direction
state; Leads own scientific judgments and delegate tasks; assignees own execution.
Share snapshots and real evidence references through directed records. Messages
should carry substantive requests/results, not acknowledgement loops. Snapshot
early enough to survive interruptions; failures remain useful project evidence.
Organizer delivers the human-facing synthesis in ORGANIZATION-REPORT.md and a
snapshot, with actual evidence, negative outcomes, limitations and any unfulfilled
project requirements. This report filename is an interface, not a research plan.
'''
