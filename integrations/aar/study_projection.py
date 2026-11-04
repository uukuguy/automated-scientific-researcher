"""Compact development observations, with lossless large-output delivery."""
import json
import hashlib
from pathlib import Path

from powerflow_lab.runner import canonical, digest
from asr_supervisor.supervisor import publication_inventory


def project_state(bridge, run):
    trials = []
    for trial in run['trials']:
        item = {key: trial[key] for key in ('trial_id', 'execution_attempt_id', 'dispatch_state', 'variables', 'hypothesis_ref')}
        if 'paired_sampling' in trial:item['paired_sampling']=trial['paired_sampling']
        if 'paired_adapter' in trial:item['paired_adapter']=trial['paired_adapter']
        if 'study_adapter_check' in trial:item['study_adapter_check']=trial['study_adapter_check']
        binding=trial.get('organization_task')
        if binding:
            item['organization_task']=dict(subject=binding['subject'],operation=binding['operation'],
                task_id=binding['task']['entity_id'],task_revision=binding['task']['revision'],
                direction_id=binding['direction']['entity_id'],direction_revision=binding['direction']['revision'],
                member_revision=binding['member']['revision'],binding_sha256=hashlib.sha256(canonical(binding)).hexdigest())
        report = (trial.get('execution') or {}).get('report')
        if report:
            item['report'] = {key: report[key] for key in ('status', 'manifest_hash', 'usage', 'execution_exited')}
            path = Path(report['evidence_path'])
            try:
                if digest(path / 'manifest.json') != report['manifest_hash'] or json.loads((path / 'manifest.json').read_text())['artifacts'] != publication_inventory(path):
                    raise ValueError('study evidence corrupt')
            except Exception as error:
                if trial.get('study_adapter_check',{}).get('status')!='blocked':raise
                item['evidence_error']=dict(error_type=type(error).__name__,message=str(error),
                    recovery='Raw evidence is unavailable or corrupt. Keep this attempt; repair from its immutable copy before explicit verification replay.')
                trials.append(item)
                continue
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
    return dict(projection=bridge.capability_profile, run={key: run[key] for key in
        ('project_id', 'research_run_id', 'state', 'health', 'control_revision', 'contract', 'budget', 'guidance', 'limit_events') if key in run},
        trials=trials, hypotheses=bridge.service.hypotheses(bridge.researcher_token, bridge.project),
        findings=bridge.service.findings(bridge.researcher_token, bridge.project, bridge.run), snapshot_refs=bridge._snapshot_refs(),
        boundary=('Frozen final evaluator results are available; further experimentation is closed. Author interpretation remains distinct from independent scoring.'
                  if bridge.capability_profile=='ood-study-synthesis/1' else
                  'Development only. Author analysis and development scores do not establish unseen-test performance.'))
