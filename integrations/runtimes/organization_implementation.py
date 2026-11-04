"""Configuration and client brief for the next actual team implementation slice."""
import hashlib
import json
from pathlib import Path

from powerflow_lab.runner import canonical, digest
from .pi import Limits

ROOT=Path(__file__).resolve().parents[2]
SNAPSHOT='29c1fa7302d7ded1492ce5b7b9b17457f8ad3fe3401c7be2a3587b1354dac262'


def resources(path):
    value=json.loads(path.read_text())
    if value.get('schema')!='asr-organization-implementation-resources/1' or value.get('paid_api_authorized') is not False or value.get('paid_api_fallback') is not False:
        raise ValueError('explicit_subscription_only_resources_required')
    budget=value['budget']
    if set(budget)!={'attempts','execution_ms','sample_proposals','research_walltime_ms','turns','tool_executions'} or budget['sample_proposals']!=0:
        raise ValueError('implementation_analysis_only_budget_required')
    if any(type(v) is not int or v<=0 for k,v in budget.items() if k!='sample_proposals'):
        raise ValueError('finite_implementation_budget_required')
    if type(value['analysis_timeout_seconds']) is not int or not 1<=value['analysis_timeout_seconds']<=300:
        raise ValueError('explicit_analysis_timeout_required')
    Limits(**value['session_limits'])
    if set(value['capacity'])!={'max_active_leads','max_active_workers'} or any(type(v) is not int or v<=0 for v in value['capacity'].values()):
        raise ValueError('explicit_organization_capacity_required')
    return value


def role_profile(role):
    return 'research-organization/1' if role=='organizer' else 'research-organization-study/1'


def preflight(policy):
    from asr_service.study import public_materials
    image_path=ROOT/policy['image_manifest'];image=json.loads(image_path.read_text())
    for relative,sha in image['sources'].items():
        if digest(ROOT/relative)!=sha:raise ValueError('scientific_image_source_changed')
    public=(ROOT/policy['public_directory']).resolve()
    config=dict(public_directory=str(public),public_manifest_sha256=digest(public/'manifest.json'),
                image_id=image['image_id'],validator_sha256=image['sources']['powerflow_lab/validation.py'])
    public_materials(config)
    snapshot=ROOT/'artifacts/p5-organization-delivery-001/snapshots'/SNAPSHOT
    manifest=json.loads((snapshot/'manifest.json').read_text())
    if hashlib.sha256(canonical(manifest)).hexdigest()!=SNAPSHOT:raise ValueError('prior_team_snapshot_corrupt')
    source_files={row['path']:row['sha256'] for row in manifest['files']}
    names={'PREVIOUS-PROTOCOL.md':'NEXT-EXPERIMENT.md','PREVIOUS-PROTOTYPE.py':'acquisition_ledger.py','PREVIOUS-PROTOTYPE-NOTES.md':'PROTOTYPE-NOTES.md'}
    paths={}
    for name,relative in names.items():
        path=snapshot/'files'/relative
        if path.is_symlink() or digest(path)!=source_files[relative]:raise ValueError('prior_team_source_corrupt')
        paths[name]=path
    paths.update({'PREVIOUS-ORGANIZER-REPORT.md':ROOT/'artifacts/p5-organization-delivery-001/ORGANIZATION-REPORT.md',
                  'TOOL-RECOVERY.md':ROOT/'docs/validation/P5-STUDY-ADAPTER-FLOW.md'})
    return config,paths


BRIEF='''# Human client continuation: implement and test the team's proposal

The prior team proposed a static paired acquisition comparison in PREVIOUS-PROTOCOL.md.
The platform now has task-bound analysis/label/fit tools and a governed paired
adapter. This new run should turn the team's coordinate-generator design into
executable, reviewed project code, with actual isolated analysis evidence.
You may identify defects, revise or reject scientific choices with explicit
reasons. No department/direction is assigned by the host. Organizer chooses the
organization; Leads retain scientific responsibility; Workers execute assigned tasks.

This run admits up to12 isolated analysis jobs of at most60 seconds each, zero
new labels, and no new hidden evaluation. Scientific computations must use
submit_study operation analysis through the task gate. Managers explicitly give
appropriate tasks experiment_operations:['study:analysis']; assignees claim them
in_progress and submit with organization_task:{task_id,revision}. Publish a
prospective hypothesis using publish_hypothesis, then cite its exact revision.
The scientific runtime profile belongs to Leads/Workers; Organizer coordinates.
Do not request label/fit jobs or bypass the owning budget with host calculations.

Implement a self-contained analysis source with main(data), using the frozen
public coordinate inputs and NumPy/SciPy in the scientific container. Follow the
prospective recipe precisely, or report a justified revision before claiming it.
Produce all named blocks and seeds, a proposed paired_sampling manifest, and
checks for deterministic rerun, counts, ranges, public/cross-seed collisions,
shared-block reuse and no silent resampling. Test invariance when labels change
but coordinates do not; the generator must not use diagnostic labels. A collision
or degenerate range is useful failure evidence, not a reason to secretly resample.
Preserve source and complete coordinate/check output in snapshots before handoff.
A second role should inspect actual code and trial evidence and run targeted
adversarial checks if useful. Do not describe source review as an executed test.

The old ledger prototype is reference source, not an installed utility in the
analysis container. Supply self-contained source, and remember analysis cannot
provide training labels or independent validation verdicts. Trials must be cited
by their returned real IDs. Large analysis output may be exported by state to
study-result-<trial>.json in your workspace; read it by offsets and snapshot it.
All failures remain part of the record.

Original P4 outcomes are known development evidence. This implementation run
cannot establish OOD utility, full paired-comparison execution or P5 completion.
Keep original method/evaluation rules distinct from your proposed generator.

Use authoritative organization_records with current revisions. A new active
direction wakes its Lead; assignments wake assignees; completed tasks wake Leads;
directed messages wake recipients. Shared snapshots are delivered under
shared-artifacts/<snapshot-hash>/. Snapshot files before sharing exact references.
Avoid acknowledgement loops; use messages for concrete review and decisions.

Organizer: finish ORGANIZATION-REPORT.md with delivered source/snapshot/trial
references, checks actually run, findings/limitations and the next frozen proposal.
Leads: review results and honestly close completed implementation directions.
Workers: preserve outputs early, finish assigned tasks and hand back evidence.
Shared model time is20 minutes; each session is at most4 minutes. Finish promptly
after a useful handoff, preserve partial work before limits, and do not relaunch
failed jobs or increase budgets automatically. A rejected design is a valid result.
'''
