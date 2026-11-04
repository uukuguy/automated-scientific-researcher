"""Service-side preparation and recovery; numerical integration is opt-in."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

import test_control_service as base
import test_acquisition_training as research
from asr_service import study
from research_projects.paired_acquisition import prototype as p


class AdapterFlowTests(unittest.TestCase):
    def setUp(self):
        self.f=base.ControlTests('test_authenticated_project_and_role_boundaries')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.service
        if not Path('artifacts/p4-final-image-002/manifest.json').is_file():self.skipTest('requires frozen scientific materials')
        cfg=research.TrainingPreparationTests('test_all_pins_come_from_frozen_materials_and_sources');cfg.setUp()
        self.research=cfg
        public=Path('artifacts/p4-simulated-client-001/public').resolve()
        config=dict(public_directory=str(public),public_manifest_sha256=hashlib.sha256((public/'manifest.json').read_bytes()).hexdigest(),
                    image_id=cfg.image['image_id'],validator_sha256=cfg.image['sources']['powerflow_lab/validation.py'])
        self.adapter=dict(profile='paired-acquisition/1',image_manifest=cfg.image,image_manifest_sha256=p.digest(cfg.image),group_seeds={'g':1101})
        self.f.contract['provenance']=dict(capability_profile=study.CAPABILITY,study=config,paired_sampling=cfg.policy,paired_adapter=self.adapter)
        self.f.contract['budget'].update(attempts=5,execution_ms=300000,sample_proposals=64)
        for kind,doc in study.expected_references(config).items():self.f.contract[kind+'_ref']=self.s.references.register('p',kind,doc)
        self.f.start()
        self.s.publish_hypothesis('agent-secret','p','h',dict(statement='Fixture',prediction='Pinned inputs',scope='Engineering',
            refutation_criteria='Mismatch',study_type='exploratory',change_reason='initial',analysis_timing='prospective'),
            expected_revision=0,idempotency_key='h')
        self.kwargs=dict(request_key='label',request=dict(operation='label',purpose='augmentation',coordinates=cfg.policy['groups']['g']['blocks']['T0'],
                         paired_batch=dict(group_id='g',arm_id='TT')),timeout_seconds=5,
                         hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))

    def submit(self):return self.s.submit_study('agent-secret','p','r',**self.kwargs)

    def test_preparation_is_atomic_durable_and_idempotent(self):
        trial=self.submit()
        self.assertIn('paired_adapter',trial)
        from asr_service.study_adapters import load
        with self.s._connect() as db:
            prepared=load(db,'p','r',trial['paired_adapter']['preparation'])
        self.assertEqual(len(prepared['expected_inputs']),64)
        self.assertEqual(self.submit(),trial)
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],1)
        # A new service object sees exactly the same frozen preparation.
        fresh=type(self.s)(self.s.path,credentials=self.s.credentials)
        with fresh._connect() as db:
            self.assertEqual(load(db,'p','r',trial['paired_adapter']['preparation']),prepared)

    def test_budget_failure_leaves_no_preparation(self):
        self.s.budgets.set_limit('p','sample_proposals',63)
        with self.assertRaisesRegex(ValueError,'budget_exhausted'):self.submit()
        with self.s._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM asr_study_artifacts').fetchone()[0],0)
        self.assertEqual(self.s.budgets.balance('p','attempts')['reserved'],0)

    def test_corrupt_preparation_is_not_silently_reconstructed(self):
        trial=self.submit()
        from asr_service.study_adapters import load
        with self.s._connect() as db:
            db.execute("UPDATE asr_study_artifacts SET body='{}'")
        with self.s._connect() as db:
            with self.assertRaisesRegex(ValueError,'artifact corrupt'):
                load(db,'p','r',trial['paired_adapter']['preparation'])

    def test_adapter_removal_or_seed_change_cannot_reinterpret_accepted_run(self):
        trial=self.submit()
        doc=copy.deepcopy(self.f.contract)
        doc['provenance']['paired_adapter']['group_seeds']['g']=1102
        self.s.publish_contract('human-secret','p','c',doc,expected_revision=1,idempotency_key='changed')
        state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','apply_contract',expected_revision=state['control_revision'],
            idempotency_key='change',payload=dict(contract_id='c',revision=2))
        self.assertEqual(self.submit(),trial)
        kwargs=dict(self.kwargs,request_key='replacement')
        with self.assertRaisesRegex(ValueError,'study_adapter_config_changed'):
            self.s.submit_study('agent-secret','p','r',**kwargs)

    def test_failed_execution_gets_durable_diagnostic_without_retry(self):
        import sys
        from asr_supervisor.process import ProcessBackend
        from asr_supervisor.supervisor import Supervisor
        from asr_supervisor.store import ExecutionStore
        from asr_service.study_adapters import reconcile,summary
        trial=self.submit()
        manager=Supervisor(ExecutionStore(self.s.path),Path(self.f.tmp.name)/'evidence',
            backend=ProcessBackend([sys.executable,'-c','raise SystemExit(7)']),poll_seconds=.01)
        manager.execute(trial['execution_attempt_id'],'fixture')
        result=reconcile(self.s,'agent-secret','p','r',trial['trial_id'])
        self.assertEqual(result['status'],'execution_incomplete')
        self.assertEqual(result['execution_state'],'failed')
        self.assertEqual(summary(self.s,'agent-secret','p','r')[trial['trial_id']],result)
        self.assertEqual(reconcile(self.s,'agent-secret','p','r',trial['trial_id'],retry=True),result)
        self.assertEqual(self.s.budgets.balance('p','attempts')['spent'],1)

    def test_blocked_adapter_keeps_state_readable_when_raw_evidence_is_missing(self):
        from types import SimpleNamespace
        from integrations.aar.study_projection import project_state
        bridge=SimpleNamespace(capability_profile='research-organization-study/1',service=self.s,
            researcher_token='agent-secret',project='p',run='r',workspace=Path(self.f.tmp.name),_snapshot_refs=lambda:[])
        trial=dict(trial_id='missing',execution_attempt_id='attempt',dispatch_state='succeeded',variables={},hypothesis_ref={},
            study_adapter_check=dict(status='blocked',message='missing raw evidence'),
            execution=dict(report=dict(status='succeeded',manifest_hash='a'*64,usage={},execution_exited=True,
                evidence_path=str(Path(self.f.tmp.name)/'missing'))))
        state=project_state(bridge,dict(trials=[trial]))
        self.assertIn('evidence_error',state['trials'][0])
        self.assertNotIn('result',state['trials'][0])

    def test_contract_rejects_arbitrary_profile_or_missing_seed(self):
        for change in ('profile','seeds','digest','null'):
            doc=copy.deepcopy(self.f.contract)
            if change=='profile':doc['provenance']['paired_adapter']['profile']='import:anything'
            elif change=='seeds':doc['provenance']['paired_adapter']['group_seeds']={}
            elif change=='null':doc['provenance']['paired_adapter']=None
            else:doc['provenance']['paired_adapter']['image_manifest_sha256']='b'*64
            with self.assertRaises(ValueError):
                self.s.publish_contract('human-secret','p','c',doc,expected_revision=1,idempotency_key=change)


if __name__=='__main__':unittest.main()
