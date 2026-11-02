"""Actual pinned upstream ORM integration; optional CPU-only `--extra aar`.

No model calls and no mocked upstream classes. The generated private checkout
contains the tracked worker guard patch and is removed after these checks.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import test_control_service as control_fixtures

HAS_AAR=importlib.util.find_spec('flask_sqlalchemy') is not None


@unittest.skipUnless(HAS_AAR,'requires uv run --extra aar python -m unittest discover -s tests -v')
class UpstreamIntegrationTests(unittest.TestCase):
    setUp=control_fixtures.ControlTests.setUp
    submit=control_fixtures.ControlTests.submit

    @classmethod
    def setUpClass(cls):
        from integrations.aar.prepare_upstream import prepare_checkout
        cls.source_temp=tempfile.TemporaryDirectory()
        cls.checkout=prepare_checkout(Path(cls.source_temp.name)/'upstream')

    @classmethod
    def tearDownClass(cls): cls.source_temp.cleanup()

    def adapter(self):
        from integrations.aar.upstream_adapter import UpstreamAdapter
        return UpstreamAdapter(self.service,checkout=self.checkout)

    def start(self,adapter):
        self.service.publish_contract('human-secret','p','c',self.contract,expected_revision=0,idempotency_key='pub')
        return adapter.create_run('human-secret','p','r','c',1,idempotency_key='create')

    def test_actual_experiment_row_same_database_atomic_mapping_and_legacy_guard(self):
        adapter=self.adapter();record=self.start(adapter)
        self.assertTrue(record['experiment_id'].startswith('aar-experiment:'))
        actual=adapter.experiment('human-secret','p','r')
        self.assertEqual(actual['execution_mode'],'asr')
        self.assertEqual(actual['asr_research_run_id'],'r')
        from asr_service.control import ControlService
        from integrations.aar.upstream_adapter import UpstreamAdapter
        reopened=UpstreamAdapter(ControlService(self.service.path,credentials=self.service.credentials),checkout=self.checkout)
        self.assertEqual(reopened.create_run('human-secret','p','r','c',1,idempotency_key='create'),record)
        with self.service._connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM experiments').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT experiment_id FROM asr_runs').fetchone()[0],record['experiment_id'])
        worker=adapter.legacy_worker()
        with self.assertRaisesRegex(RuntimeError,'disables the legacy'):worker.start()
        self.assertFalse(worker.running)
        with self.assertRaisesRegex(RuntimeError,'owning executor'):
            with adapter.app.app_context():
                worker._run_experiment(adapter.models.Experiment.query.one())

    def test_failed_control_admission_rolls_back_actual_experiment_row(self):
        import copy
        adapter=self.adapter();self.start(adapter)
        self.service.budgets.reserve('p','existing-cost','attempts',2)
        smaller=copy.deepcopy(self.contract);smaller['budget']['attempts']=1
        self.service.publish_contract('human-secret','p','c',smaller,expected_revision=1,idempotency_key='smaller')
        with self.assertRaisesRegex(ValueError,'below_committed_usage'):
            adapter.create_run('human-secret','p','second-run','c',2,idempotency_key='reject')
        with adapter.app.app_context():self.assertEqual(adapter.models.Experiment.query.count(),1)
        with self.service._connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM asr_runs').fetchone()[0],1)

    def test_actual_shared_findings_revision_and_local_snapshot_organization(self):
        from asr_supervisor.store import ExecutionStore
        from integrations.aar.bridge import ResearchBridge
        from powerflow_lab.runner import digest,_inventory
        adapter=self.adapter();self.start(adapter);trial=self.submit()
        store=ExecutionStore(self.service.path);claim=store.claim(trial['execution_attempt_id'],'numerical')
        evidence=Path(self.tmp.name)/'evidence';evidence.mkdir()
        (evidence/'log.txt').write_text('negative numerical result')
        manifest=dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],status='failed',artifacts=_inventory(evidence))
        (evidence/'manifest.json').write_text(json.dumps(manifest))
        store.report(trial['execution_attempt_id'],1,'numerical',dict(execution_exited=True,status='failed',manifest_hash=digest(evidence/'manifest.json'),evidence_path=str(evidence),usage={'attempts':1,'execution_ms':1}))
        for revision in range(2):
            self.service.publish_finding('agent-secret','p','r',finding_id='negative',expected_revision=revision,idempotency_key='finding'+str(revision),statement='Negative result revision '+str(revision+1),trial_ids=[trial['trial_id']],limitations='Calibration only')
        projected=adapter.sync_findings('human-secret','p','r')
        self.assertEqual(len(projected),2)
        self.assertEqual(len(adapter.sync_findings('human-secret','p','r')),2)
        posts=adapter.forum('agent-secret','p')
        self.assertEqual([p['asr_revision'] for p in posts],[1,2])
        self.assertEqual(posts[0]['asr_evidence'][0]['trial_id'],trial['trial_id'])
        self.assertIsNone(posts[0]['pgr'])
        work=Path(self.tmp.name)/'workspace';work.mkdir();(work/'note.md').write_text('negative result with trial '+trial['trial_id'])
        bridge=ResearchBridge(self.service,project='p',run='r',researcher_token='agent-secret',supervisor_token='human-secret',workspace=work,snapshots=Path(self.tmp.name)/'snapshots',organization=adapter)
        snapshot=bridge.call('snapshot',{'paths':['note.md']},'snapshot')
        stored=adapter.register_snapshot('human-secret','p','r',snapshot_root=bridge.snapshots,digest=snapshot['snapshot_sha256'])
        self.assertEqual(stored['commit_id'],snapshot['snapshot_sha256'])
        self.assertEqual(len(adapter.snapshots('agent-secret','p','r')),1)
        destination=Path(self.tmp.name)/'restored'
        adapter.restore_snapshot('human-secret','p','r',snapshot['snapshot_sha256'],destination)
        self.assertEqual((destination/'note.md').read_text(),(work/'note.md').read_text())
        with adapter.app.app_context(): self.assertEqual(adapter.models.Finding.query.count(),3)
        adapter.create_run('human-secret','p','second-run','c',1,idempotency_key='second')
        second=ResearchBridge(self.service,project='p',run='second-run',researcher_token='agent-secret',supervisor_token='human-secret',workspace=work,snapshots=Path(self.tmp.name)/'second-snapshots',organization=adapter)
        shared=second.state()['shared_findings']
        self.assertEqual([row['asr_revision'] for row in shared if row['asr_finding_id']=='negative'],[1,2])
        self.assertTrue(all(row['asr_research_run_id']=='r' for row in shared))
        with self.assertRaises(ValueError):adapter.forum('other-secret','p')

if __name__=='__main__': unittest.main()
