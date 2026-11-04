import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from asr_service.control import ControlError
import test_control_research_notes as fixtures
from integrations.aar.bridge import ResearchBridge


class NoteArtifactTests(unittest.TestCase):
    def setUp(self):
        self.base=fixtures.ControlResearchNotesTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.service=self.base.s
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name);(self.work/'method.py').write_text('def solve(x): return x\n')
        self.snapshots=self.service.path.parent/'snapshots'
        bridge=ResearchBridge(self.service,project='p',run='r',researcher_token='lead',supervisor_token='supervisor-secret',workspace=self.work,snapshots=self.snapshots,capability_profile='research-organization/1')
        self.snapshot=bridge.snapshot(['method.py'])['snapshot_sha256']
        self.ref=dict(kind='snapshot',snapshot_sha256=self.snapshot,path='method.py')

    def call(self, operation, **args):
        return self.service.research_note('lead','p','r',operation=operation,idempotency_key=operation,**args)

    def test_exact_snapshot_file_is_bound_and_mutation_blocks_restore(self):
        note=self.call('save',text='该方法仍是候选',artifact_references=[self.ref])
        self.call('adopt',revision=note['revision'],expected_note=None)
        self.assertEqual(self.call('read')['restoration']['status'],'ready')
        (self.snapshots/self.snapshot/'files/method.py').write_text('changed')
        with self.assertRaisesRegex(ControlError,'note_artifact_unavailable'):self.call('read')

    def test_path_escape_and_cross_project_manifest_rejected(self):
        for name in ['../method.py','/etc/passwd']:
            with self.assertRaises(ControlError):self.call('save',text='x',artifact_references=[dict(self.ref,path=name)])
        path=self.snapshots/self.snapshot/'manifest.json';manifest=json.loads(path.read_text());manifest['project_id']='other'
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ControlError):self.call('save',text='x',artifact_references=[self.ref])

    def test_missing_trial_and_hidden_evaluation_kind_rejected(self):
        for ref in [dict(kind='trial',trial_id='missing',path='study-result.json'),dict(kind='evaluation',path='hidden.json')]:
            with self.assertRaises(ControlError):self.call('save',text='x',artifact_references=[ref])

    def test_failed_published_trial_file_is_verified_against_original_bytes(self):
        from asr_supervisor.store import ExecutionStore
        from powerflow_lab.runner import digest, _inventory
        import test_control_service as control
        fixture=control.ControlTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.start();trial=fixture.submit();self.service=fixture.service
        self.service.credentials['lead']=dict(subject='lead',role='researcher',projects=['p'])
        store=ExecutionStore(self.service.path);claim=store.claim(trial['execution_attempt_id'],'supervisor')
        evidence=self.work/'evidence';evidence.mkdir()
        (evidence/'result.json').write_text('{"result":"negative finding"}')
        manifest=dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],status='failed',artifacts=_inventory(evidence))
        (evidence/'manifest.json').write_text(json.dumps(manifest))
        store.report(trial['execution_attempt_id'],claim['epoch'],'supervisor',dict(execution_exited=True,status='failed',manifest_hash=digest(evidence/'manifest.json'),evidence_path=str(evidence),usage=dict(attempts=1,execution_ms=5)))
        self.service.change_organization('human-secret','p','r',kind='policy',entity_id='capacity',expected_revision=0,idempotency_key='policy',document=dict(max_active_leads=2,max_active_workers=2))
        self.service.change_organization('human-secret','p','r',kind='member',entity_id='lead',expected_revision=0,
            idempotency_key='member',document=dict(role='lead',enabled=True))
        ref=dict(kind='trial',trial_id=trial['trial_id'],path='result.json')
        draft=self.call('save',text='失败结果应保留',artifact_references=[ref])
        self.call('adopt',revision=draft['revision'],expected_note=None)
        self.assertEqual(self.call('read')['restoration']['status'],'ready')
        (evidence/'result.json').write_text('mutated')
        with self.assertRaisesRegex(ControlError,'note_artifact_unavailable'):self.call('read')

    def test_snapshot_symlink_is_not_followed(self):
        file=self.snapshots/self.snapshot/'files/method.py'
        file.unlink();file.symlink_to(self.work/'method.py')
        with self.assertRaisesRegex(ControlError,'note_artifact_unavailable'):
            self.call('save',text='x',artifact_references=[self.ref])

    def test_source_pages_reconstruct_unicode_without_silent_truncation(self):
        (self.work/'method.py').write_text('反证记录\n'*20)
        bridge=ResearchBridge(self.service,project='p',run='r',researcher_token='lead',supervisor_token='supervisor-secret',workspace=self.work,snapshots=self.snapshots,capability_profile='research-organization/1')
        ref=dict(self.ref,snapshot_sha256=bridge.snapshot(['method.py'])['snapshot_sha256'])
        draft=self.call('save',text='保留原文',artifact_references=[ref])
        chunks=[];offset=0
        while True:
            result=self.call('source_read',revision=draft['revision'],artifact_reference=ref,offset=offset,limit=7)
            chunks.append(result['text']);self.assertEqual(result['offset'],offset)
            if not result['has_more']:break
            offset=result['next_offset']
        self.assertEqual(''.join(chunks),'反证记录\n'*20)
        state=self.service.get_run('human-secret','p','r')
        self.service.command('human-secret','p','r','pause',expected_revision=state['control_revision'],idempotency_key='pause-for-history')
        self.assertEqual(self.call('read',revision=draft['revision'])['restoration']['status'],'deferred')
        self.assertEqual(self.call('source_read',revision=draft['revision'],artifact_reference=ref,limit=7)['text'],'反证记录\n反证')
        with self.assertRaises(ControlError):self.call('source_read',revision=draft['revision'],artifact_reference=self.ref)
        with self.assertRaises(ControlError):self.call('source_read',revision=draft['revision'],artifact_reference=ref,limit=16001)
