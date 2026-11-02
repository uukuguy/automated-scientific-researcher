"""Resume an interrupted acceptance from its existing ledger and native session.

No experiment is submitted by this recovery driver. Model conclusions remain
model-generated. A new trusted operator credential map supplies the same roles.
"""
import argparse
import json
from pathlib import Path
import secrets
from asr_service.control import ControlService
from integrations.aar.bridge import ResearchBridge
from .pi import PiRuntime,Limits
from .session import run_session


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);args=p.parse_args();root=args.root.resolve()
    previous=json.loads((root/'result.json').read_text());project=previous['project_id'];run=previous['research_run_id']
    researcher=secrets.token_urlsafe(32);supervisor=secrets.token_urlsafe(32)
    credentials={token:dict(subject=role,role=role,projects=[project]) for token,role in [(researcher,'researcher'),(supervisor,'supervisor')]}
    service=ControlService(root/'control.db',credentials=credentials);before=service.get_run(supervisor,project,run)
    bridge=ResearchBridge(service,project=project,run=run,researcher_token=researcher,supervisor_token=supervisor,workspace=root/'workspace',snapshots=root/'snapshots')
    budget=before['budget'];model=before['contract']['document']['runtime_policy']['model']
    result=run_session(PiRuntime(model=model),bridge,config_dir=root/'pi-private',native_session_id=run,
        prompt='The previous runtime was externally interrupted after completing a numerical trial. Recover the same research run and native session. Do not submit experiments or repeat work. Read ASR state once, then publish your own evidence-linked candidate finding from the already completed trial using publish_finding {finding_id:STRING,expected_revision:0,statement:STRING,trial_ids:[actual trial ID],limitations:STRING}. You have only three provider turns: state, publish, final response. State real limitations and operating/unassessed constraints. Finish immediately.',
        limits=Limits(min(30,budget['research_walltime_ms']['available']/1000),budget['turns']['available'],budget['tool_executions']['available']))
    after=service.get_run(supervisor,project,run)
    report=dict(runtime=result,findings=service.findings(researcher,project,run),budget=after['budget'],trials=after['trials'],
        same_trial_ids=[x['trial_id'] for x in before['trials']]==[x['trial_id'] for x in after['trials']],native_session_id=run)
    (root/'result-recovery.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(status=result['status'],findings=len(report['findings']),same_trial_ids=report['same_trial_ids'])))
    if not report['findings'] or not report['same_trial_ids']:raise SystemExit(1)

if __name__=='__main__':main()
