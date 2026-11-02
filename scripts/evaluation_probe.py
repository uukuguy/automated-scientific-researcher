"""Run bounded real local evaluator acceptance; no model calls or API publication.

Usage: uv run python -m scripts.evaluation_probe --root data/evaluator-acceptance
Stopped, labelled containers are retained for audit; no foreign process is touched.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from asr_evaluation.replay import Replay, freeze_source, _read, IMAGE_ID, INPUT_SHA256, VALIDATOR_SHA256
from powerflow_lab.runner import canonical

REPO = Path(__file__).resolve().parents[1]
PROVENANCE = REPO/'environments/scientific/fixtures/matpower-case118/provenance.json'


def main():
    provenance = json.loads(PROVENANCE.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=REPO/provenance['source_attempt_path'])
    arguments = parser.parse_args()
    manifest_hash = provenance['original_manifest_sha256']
    source_identity = dict(trial_id=provenance['source_trial_id'], execution_attempt_id=provenance['source_attempt_id'], research_run_id='r')
    freeze_source(arguments.source, manifest_hash, **source_identity)
    runner = Replay(arguments.root/'evidence')
    reports = {}
    reports['baseline'] = runner.run('baseline', arguments.source, manifest_hash, **source_identity)
    reports['isolation_probe'] = runner.run('isolation-probe', arguments.source, manifest_hash, mode='probe', **source_identity)
    reports['timeout'] = runner.run('timeout', arguments.source, manifest_hash, timeout_seconds=.01, mode='probe', **source_identity)
    # These are explicit synthetic corruption fixtures, not admitted numerical
    # executions. Never publish their manifests as evidence for the source trial.
    for name, change in [('invalid_voltage', lambda case:case['bus'][0].__setitem__(7,case['bus'][0][7]+.01)),
                         ('changed_fixed_load', lambda case:case['bus'][0].__setitem__(2,case['bus'][0][2]+1))]:
        target = arguments.root/'synthetic-fixtures'/name
        target.mkdir(parents=True,exist_ok=True)
        if not (target/'manifest.json').exists():
            for path in arguments.source.iterdir():
                (target/path.name).write_bytes(_read(path))
            freeze_source(target,manifest_hash,**source_identity)
            value = json.loads((target/'solution.json').read_text()); change(value)
            (target/'solution.json').write_bytes(canonical(value))
            manifest = json.loads((target/'manifest.json').read_text())
            manifest.update(trial_id='synthetic_'+name,execution_attempt_id='synthetic_'+name,research_run_id='synthetic_diagnostics',
                synthetic_fixture=dict(parent_manifest_sha256=manifest_hash,kind=name,not_admitted_execution=True))
            body = (target/'solution.json').read_bytes()
            manifest['artifacts']['solution.json'] = dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            (target/'manifest.json').write_bytes(canonical(manifest))
        mutated_hash = hashlib.sha256((target/'manifest.json').read_bytes()).hexdigest()
        reports[name] = runner.run(name,target,mutated_hash,trial_id='synthetic_'+name,
            execution_attempt_id='synthetic_'+name,research_run_id='synthetic_diagnostics')
    freeze_source(arguments.source,manifest_hash,**source_identity)  # Original evidence remains untouched.
    summary = dict(schema='asr-isolated-evaluation-acceptance/1', checked_at=datetime.now(timezone.utc).isoformat(),
        docker_context=runner._docker(['context','show']),source_fixture=str(PROVENANCE.relative_to(REPO)),
        source_manifest_sha256=manifest_hash,trusted_original_input_sha256=INPUT_SHA256,
        validator_sha256=VALIDATOR_SHA256,image_id=IMAGE_ID,
        scope='Frozen-material numerical recheck; no solver replication, generalization, Control publication or reservations.',
        diagnostics='invalid_voltage and changed_fixed_load use explicitly synthetic corrupted copies, not admitted executions.',
        reports={})
    for name,report in reports.items():
        path = runner.root/hashlib.sha256({'isolation_probe':'isolation-probe'}.get(name,name).encode()).hexdigest()
        launch = json.loads((path/'launch-inspection.json').read_text())
        summary['reports'][name] = dict(evaluation_id=report['evaluation_id'],manifest_sha256=hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest(),
            source=report['source'],execution_status=report['execution_status'],execution_exited=report['execution_exited'],exit_code=report['exit_code'],
            result=report['result'],mounts=[dict(destination=m['Destination'],read_only=not m['RW']) for m in launch['Mounts']],
            security={key:launch['HostConfig'][key] for key in ('NetworkMode','ReadonlyRootfs','Privileged','CapDrop','SecurityOpt','Memory','MemorySwap','NanoCpus','PidsLimit')},
            user=launch['Config']['User'])
    summary['acceptance_checks'] = dict(
        original_equations_valid=reports['baseline']['result']['equation_valid'] is True,
        operating_limits_separate=reports['baseline']['result']['operational_status']=='violated',
        isolation_probe_passed=all(reports['isolation_probe']['result']['checks'].values()),
        invalid_voltage_rejected=reports['invalid_voltage']['result']['equation_valid'] is False,
        changed_fixed_load_rejected=reports['changed_fixed_load']['result']['input_preserved'] is False,
        external_timeout_confirmed=reports['timeout']['execution_status']=='timed_out',
        all_execution_exits_confirmed=all(report['execution_exited'] for report in reports.values()))
    destination = arguments.root/'receipt.json'; destination.write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(destination)
    return 0 if all(summary['acceptance_checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
