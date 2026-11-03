"""Freeze AAR's selected fitted models before one independent hidden-test release."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import secrets
import time

from asr_service.control import ControlService
from asr_service.ood_final import CAPABILITY,evaluation_reference
from asr_service.study import completed_material
from asr_supervisor.store import ExecutionStore
from asr_supervisor.supervisor import Supervisor
from asr_evaluation.ood_backend import OODFinalBackend
from asr_supervisor.study import StudyBackend
from powerflow_lab.runner import canonical,digest
from .ood_intake import write


def frozen_proposal(root,project,run):
    names={'FINAL-TEST-PROPOSAL.md','FINAL-TEST-PROPOSAL.json'}
    if any((root/'workspace'/name).is_symlink() for name in names):raise ValueError('ordinary proposal files required')
    current={name:digest(root/'workspace'/name) for name in names}
    for manifest_path in sorted((root/'snapshots').glob('*/manifest.json')):
        manifest=json.loads(manifest_path.read_text())
        if manifest.get('project_id')!=project or manifest.get('research_run_id')!=run:continue
        if hashlib.sha256(canonical(manifest)).hexdigest()!=manifest_path.parent.name:continue
        records={row['path']:row for row in manifest['files']}
        if not names<=records.keys() or any(records[name]['sha256']!=current[name] for name in names):continue
        for name in names:
            path=manifest_path.parent/'files'/name
            if path.is_symlink() or digest(path)!=current[name]:raise ValueError('proposal snapshot corrupt')
        selection=json.loads((manifest_path.parent/'files/FINAL-TEST-PROPOSAL.json').read_text())
        if set(selection)!={'primary_model','model_trials'}:raise ValueError('explicit final model selection required')
        protocol=dict(selection,proposal_sha256=hashlib.sha256(canonical(current)).hexdigest())
        return protocol,manifest_path.parent.name
    raise ValueError('both final proposal files must match an actual AAR snapshot')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--client-root',required=True,type=Path)
    parser.add_argument('--image-manifest',required=True,type=Path)
    parser.add_argument('--hypothesis-id',required=True,help='Exact prospective final-test hypothesis named in the frozen proposal')
    parser.add_argument('--hypothesis-revision',type=int,default=1)
    parser.add_argument('--execute-frozen-evaluation',action='store_true')
    args=parser.parse_args();root=args.root.resolve();client=args.client_root.resolve()
    identity=json.loads((root/'identity.json').read_text());project=identity['project_id'];run=identity['research_run_id']
    token=secrets.token_urlsafe(32)
    service=ControlService(root/'control.db',credentials={token:dict(subject='simulated-client-human',role='human',projects=[project])})
    state=service.get_run(token,project,run)
    if state['state']!='paused' or state['health']!='ok' or any(s['state']!='exited' for s in state['runtime_sessions']):
        raise ValueError('independent final release requires a reconciled paused researcher')
    if state.get('study_final_lock'):raise ValueError('final protocol already admitted; reconcile or recover its exact attempt')
    protocol,snapshot=frozen_proposal(root,project,run)
    confirmation_reference=dict(project_id=project,hypothesis_id=args.hypothesis_id,revision=args.hypothesis_revision)
    with service._connect() as db:
        confirmation=service._hypothesis_ref(db,project,confirmation_reference)
        for trial in protocol['model_trials']:
            material,_=completed_material(db,project,run,trial)
            if material['variables']!={'operation':'fit'}:raise ValueError('proposal must select trusted fitted models')
        primary=json.loads(db.execute('SELECT record FROM asr_dispatch WHERE project=? AND run=? AND trial=?',
            (project,run,protocol['primary_model'])).fetchone()[0])
    proposal_text=(root/'snapshots'/snapshot/'files/FINAL-TEST-PROPOSAL.md').read_text()
    if confirmation['hypothesis_id'] not in proposal_text or confirmation['sha256'] not in proposal_text:
        raise ValueError('final hypothesis is not named with its exact hash in the frozen proposal')
    image=json.loads(args.image_manifest.read_text())
    for source in ('asr_evaluation/ood_metrics.py','asr_evaluation/ood_worker.py'):
        if digest(source)!=image['sources'][source]:raise ValueError('final evaluator source/image drift')
    config=dict(client_root=str(client),preparation_report_sha256=digest(client/'preparation-report.json'),image_id=image['image_id'],
        metric_source_sha256=image['sources']['asr_evaluation/ood_metrics.py'],worker_source_sha256=image['sources']['asr_evaluation/ood_worker.py'])
    doc=copy.deepcopy(state['contract']['document'])
    if doc['provenance']['study']['public_directory']!=str(client/'public'):raise ValueError('client identity changed')
    doc['provenance'].update(capability_profile=CAPABILITY,final=config,final_proposal_snapshot=snapshot)
    doc['objective'].update(success_criteria='One independent frozen-test comparison against the original client utility rule; retain negative outcome.',
        scope='Frozen model confirmation only. All further training/development submissions in this run are closed.')
    reference=evaluation_reference(config);doc['evaluation_ref']=service.references._digest('evaluation',reference)
    if not args.execute_frozen_evaluation:
        print(json.dumps(dict(status='frozen_proposal_ready',protocol=protocol,snapshot=snapshot,hypothesis=confirmation,
            image_id=config['image_id'],budget_changes=False,private_test_opened=False),indent=2));return
    batch='final-'+str(time.time_ns());output=root/batch;output.mkdir(mode=0o700)
    write(output/'protocol.json',dict(protocol=protocol,snapshot=snapshot,hypothesis=confirmation))
    # Replay the already-selected fixed training inputs in a fresh container.
    # This does not select another model or expose any hidden test observation.
    service.command(token,project,run,'resume',expected_revision=state['control_revision'],idempotency_key=batch+'-replication-resume')
    try:
        hypothesis={key:primary['hypothesis_ref'][key] for key in ('project_id','hypothesis_id','revision')}
        replay=service.submit_study(token,project,run,request_key=batch+'-training-replay',
            request=dict(operation='fit',augmentation_trials=[d['trial_id'] for d in primary['dependencies']]),
            timeout_seconds=min(60,doc['execution_policy']['timeout_seconds']),hypothesis_ref=hypothesis)
        worker=Supervisor(ExecutionStore(service.path),root/'study-evidence',backend=StudyBackend(doc['provenance']['study']['image_id']))
        replayed=worker.execute(replay['execution_attempt_id'],'independent-training-replay')
        if replayed['state']!='succeeded':raise ValueError('selected-model training replay failed')
        with service._connect() as db:
            old,_=completed_material(db,project,run,primary['trial_id'])
            new,_=completed_material(db,project,run,replay['trial_id'])
        old_hash=hashlib.sha256(canonical(old['events'][-1]['result']['model'])).hexdigest()
        new_hash=hashlib.sha256(canonical(new['events'][-1]['result']['model'])).hexdigest()
        replication=dict(original_trial_id=primary['trial_id'],replay_trial_id=replay['trial_id'],
            original_model_sha256=old_hash,replayed_model_sha256=new_hash,
            identical_model=old_hash==new_hash,identical_payload=primary['execution_request']['payload_sha256']==replay['execution_request']['payload_sha256'],
            report=replayed['report'],scope='Independent execution of the unchanged trainer on the frozen selected inputs; no hidden test access.')
        write(output/'training-replication.json',replication)
        if not replication['identical_model'] or not replication['identical_payload']:raise ValueError('training reproduction mismatch; final test remains closed')
        write(root/'workspace/INDEPENDENT-TRAINING-REPLAY.json',replication)
    finally:
        state=service.get_run(token,project,run)
        if state['state']=='running':service.command(token,project,run,'pause',expected_revision=state['control_revision'],idempotency_key=batch+'-replication-pause')
    state=service.get_run(token,project,run)
    service.references.register(project,'evaluation',reference)
    contract=service.publish_contract(token,project,state['contract_id'],doc,expected_revision=state['contract_revision'],idempotency_key=batch+'-contract')
    service.command(token,project,run,'apply_contract',expected_revision=state['control_revision'],idempotency_key=batch+'-apply',payload=dict(contract_id=state['contract_id'],revision=contract['revision']))
    state=service.get_run(token,project,run)
    service.command(token,project,run,'resume',expected_revision=state['control_revision'],idempotency_key=batch+'-resume')
    try:
        receipt=service.submit_ood_final(token,project,run,request_key=batch,protocol=protocol,hypothesis_ref=confirmation_reference)
        write(output/'admission.json',receipt)
        supervisor=Supervisor(ExecutionStore(service.path),root/'study-evidence',backend=OODFinalBackend(config['image_id']))
        result=supervisor.execute(receipt['execution_attempt_id'],'independent-final-evaluator')
    except Exception as error:
        write(output/'failure.json',dict(type=type(error).__name__,message=str(error),recovery='Inspect authoritative admission/execution state before retrying the same frozen protocol.'))
        raise
    finally:
        state=service.get_run(token,project,run)
        if state['state']=='running':service.command(token,project,run,'pause',expected_revision=state['control_revision'],idempotency_key=batch+'-pause')
    report=dict(protocol=protocol,snapshot=snapshot,execution=result,scope='Independent final scoring; researcher interpretation and lifecycle closeout remain.')
    write(output/'result.json',report)
    print(json.dumps(dict(result=str(output/'result.json'),state=result['state'],trial_id=receipt['trial_id'])))
    if result['state']!='succeeded':raise SystemExit(2)


if __name__=='__main__':main()
