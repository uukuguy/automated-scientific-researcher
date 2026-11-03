"""Compact development observations, with lossless large-output delivery."""
import json
from pathlib import Path

from powerflow_lab.runner import canonical, digest
from asr_supervisor.supervisor import publication_inventory


def project_state(bridge, run):
    trials = []
    for trial in run['trials']:
        item = {key: trial[key] for key in ('trial_id', 'execution_attempt_id', 'dispatch_state', 'variables', 'hypothesis_ref')}
        report = (trial.get('execution') or {}).get('report')
        if report:
            item['report'] = {key: report[key] for key in ('status', 'manifest_hash', 'usage', 'execution_exited')}
            path = Path(report['evidence_path'])
            if digest(path / 'manifest.json') != report['manifest_hash'] or json.loads((path / 'manifest.json').read_text())['artifacts'] != publication_inventory(path):
                raise ValueError('study evidence corrupt')
            result_path = path / 'study-result.json'
            if result_path.exists():
                result = json.loads(result_path.read_text())
                result.pop('model', None)  # Available to analysis through its immutable trial dependency.
                if len(canonical(result)) <= 40000:
                    item['result'] = result
                else:
                    output = bridge.workspace / ('study-result-' + trial['trial_id'] + '.json')
                    body = json.dumps(result, indent=2, allow_nan=False) + '\n'
                    if output.is_symlink():
                        raise ValueError('unsafe study result path')
                    if output.exists() and output.read_text() != body:
                        raise ValueError('study result export conflict')
                    if not output.exists():
                        with output.open('x') as stream:
                            stream.write(body)
                    item['result_file'] = dict(path=output.name, sha256=digest(output), bytes=output.stat().st_size,
                        recovery='Read by line offsets. The complete original result is also available as an analysis input dependency.')
            if 'resource_events' in report:
                item['resource_events'] = report['resource_events']
            if (path / 'study-output-error.json').exists():
                item['output_error'] = json.loads((path / 'study-output-error.json').read_text())
        trials.append(item)
    return dict(projection='ood-study-development/1', run={key: run[key] for key in
        ('project_id', 'research_run_id', 'state', 'health', 'control_revision', 'contract', 'budget', 'guidance', 'limit_events') if key in run},
        trials=trials, hypotheses=bridge.service.hypotheses(bridge.researcher_token, bridge.project),
        findings=bridge.service.findings(bridge.researcher_token, bridge.project, bridge.run), snapshot_refs=bridge._snapshot_refs(),
        boundary='Development only. Author analysis and development scores do not establish unseen-test performance.')
