"""P3 capability and bridge checks; no model inference."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock

from integrations.aar.bridge import ResearchBridge
from integrations.runtimes.pi import PiRuntime, RuntimeFailure


class P3CapabilityTests(unittest.TestCase):
    def test_smoke_bridge_rejects_candidate_operations_before_service_access(self):
        service = Mock()
        with tempfile.TemporaryDirectory() as directory:
            bridge = ResearchBridge(service, project='p', run='r', researcher_token='author',
                                    supervisor_token='supervisor', workspace=directory, snapshots=Path(directory)/'snapshots')
            for operation in ('freeze_candidate','submit_candidate','request_replication','request_evaluation'):
                with self.subTest(operation=operation), self.assertRaisesRegex(ValueError,'unsupported_bridge_operation'):
                    bridge.call(operation, {}, 'forbidden')
        self.assertEqual(service.mock_calls, [])

    def test_p3_profile_is_explicit_and_smoke_keeps_original_permissions(self):
        extra = {'asr.freeze_candidate', 'asr.submit_candidate', 'asr.request_evaluation', 'asr.request_replication'}
        old = PiRuntime(model='test').preflight_capabilities()['pack']
        self.assertFalse(extra.intersection(old['tools']))
        manifest = Path('integrations/runtimes/p3-capabilities.json')
        self.assertTrue(manifest.is_file(), 'P3 requires a separately versioned capability pack')
        new = PiRuntime(model='test', capabilities_path=manifest).preflight_capabilities()['pack']
        self.assertTrue(extra <= set(new['tools']))
        self.assertEqual(new['id'], 'powerflow-candidate-research/1')

    def test_smoke_extension_rejects_undeclared_candidate_operation(self):
        extension = Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code = f'''import extension from {json.dumps(extension)};
let tool, fetched=false;
globalThis.fetch=async()=>{{fetched=true;return {{ok:true,json:async()=>({{}})}}}};
extension({{on:()=>{{}},registerTool:t=>tool=t}});
if(tool.parameters.properties.operation.enum.includes('freeze_candidate'))throw new Error('smoke permission expanded');
let blocked=false;
try{{await tool.execute('1',{{operation:'freeze_candidate',arguments:{{path:'candidate.m'}},key:'k'}})}}catch{{blocked=true}}
if(!blocked||fetched)throw new Error('undeclared operation reached service');'''
        env = dict(os.environ, ASR_MAX_TURNS='1', ASR_MAX_TOOLS='1',
                   ASR_DEADLINE_MS=str(int((time.time()+5)*1000)))
        env.pop('ASR_TOOL_OPERATIONS', None)
        checked = subprocess.run(['node', '--input-type=module', '-e', code], env=env,
                                 capture_output=True, timeout=8)
        self.assertEqual(checked.returncode, 0, checked.stderr.decode())

    def test_declared_candidate_operation_is_visible_and_dispatched(self):
        extension = Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code = f'''import extension from {json.dumps(extension)};
let tool, sent;
globalThis.fetch=async(_url,opts)=>{{sent=JSON.parse(opts.body);return {{ok:true,json:async()=>({{digest:'frozen'}})}}}};
extension({{on:()=>{{}},registerTool:t=>tool=t}});
if(!tool.parameters.properties.operation.enum.includes('freeze_candidate'))throw new Error('missing declared operation');
await tool.execute('1',{{operation:'freeze_candidate',arguments:{{path:'candidate.m'}},key:'k'}});
if(sent.operation!=='freeze_candidate')throw new Error('wrong dispatch');'''
        env = dict(os.environ, ASR_MAX_TURNS='1', ASR_MAX_TOOLS='1',
                   ASR_TOOL_OPERATIONS=json.dumps(['state', 'freeze_candidate']),
                   ASR_DEADLINE_MS=str(int((time.time()+5)*1000)))
        checked = subprocess.run(['node', '--input-type=module', '-e', code], env=env,
                                 capture_output=True, timeout=8)
        self.assertEqual(checked.returncode, 0, checked.stderr.decode())


class CandidateBridgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root/'work'
        self.work.mkdir()
        self.service = Mock()
        self.service.register_candidate.return_value = {'digest': 'candidate-reference', 'path': '/private/service/candidate.m'}
        self.bridge = ResearchBridge(self.service, project='p', run='r', researcher_token='author',
                                     supervisor_token='supervisor', workspace=self.work,
                                     snapshots=self.root/'snapshots', capability_profile='powerflow-candidate-research/1')

    def freeze(self, arguments):
        self.assertTrue(callable(getattr(self.bridge, 'freeze_candidate', None)),
                        'candidate freezing must verify workspace bytes before registration')
        return self.bridge.call('freeze_candidate', arguments, 'freeze-1')

    def test_registration_uses_exact_frozen_bytes_and_researcher_identity(self):
        source = 'function result=candidate(mpc)\n result=mpc;\nend\n'
        (self.work/'candidate.m').write_text(source)
        receipt = self.freeze({'path': 'candidate.m'})
        self.service.register_candidate.assert_called_once_with(
            'author', 'p', request_key='freeze-1', source=source, entrypoint='candidate.m',
            profile='octave-candidate/1', snapshot_ref=receipt['snapshot_sha256'], run='r')
        self.assertEqual(receipt['candidate_ref'], 'candidate-reference')
        self.assertNotIn('path', receipt['registration'])
        frozen = self.root/'snapshots'/receipt['snapshot_sha256']/'files/candidate.m'
        (self.work/'candidate.m').write_text('later method revision')
        self.assertEqual(frozen.read_text(), source)

    def test_candidate_freeze_blocks_symlink_and_host_paths(self):
        (self.work/'candidate.m').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'invalid_snapshot_path'):
            self.freeze({'path': 'candidate.m'})
        for path in ('/etc/passwd', '../candidate.m', 'other.m'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'candidate_entrypoint_required'):
                self.freeze({'path': path})
        self.service.register_candidate.assert_not_called()

    def test_candidate_freeze_caps_code_before_registration(self):
        (self.work/'candidate.m').write_bytes(b'x'*65537)
        with self.assertRaisesRegex(ValueError, 'candidate_too_large'):
            self.freeze({'path': 'candidate.m'})
        self.service.register_candidate.assert_not_called()

    def test_state_exposes_complete_frozen_evaluation_targets(self):
        expected=dict(trial_id='trial',execution_attempt_id='attempt',manifest_hash='a'*64,evaluation_ref='b'*64)
        self.service.get_run.return_value={'trials':[dict(trial_id='trial',execution_attempt_id='attempt',
            references={'evaluation':'b'*64},execution={'report':dict(evidence_path=str(self.root),
                manifest_hash='a'*64,execution_exited=True)})]}
        state=self.bridge.state()
        self.assertEqual(state.get('evaluation_targets'),[expected])

    def test_evaluation_admission_uses_author_and_only_dispatches_queued_job(self):
        self.assertTrue('evaluation_dispatch' in ResearchBridge.__init__.__code__.co_varnames,
                        'independent evaluation requires a separate trusted dispatch seam')
        dispatch = Mock()
        self.bridge.evaluation_dispatch = dispatch
        self.bridge.state = Mock(return_value={'recovered': True})
        receipt = {'evaluation_id': 'evaluation-1'}
        self.service.admit_evaluation.return_value = receipt
        self.service.get_evaluation.side_effect = [{'state': 'queued'}, {'state': 'completed'}]
        arguments = {'target': {'trial_id': 'trial-1'},
                     'requested_budget': {'evaluation_attempts': 1, 'evaluation_ms': 20000}}
        first = self.bridge.call('request_evaluation', arguments, 'evaluate-1')
        self.bridge.call('request_evaluation', arguments, 'evaluate-1')
        self.service.admit_evaluation.assert_called_with('author', 'p', 'r', request_key='evaluate-1', **arguments)
        dispatch.assert_called_once_with(receipt)
        self.assertEqual(first['receipt'], receipt)
        self.service.publish_validation.assert_not_called()

    def test_replication_uses_frozen_service_submission_without_resubmitting_author_request(self):
        self.assertTrue(callable(getattr(self.bridge, 'dispatch_trial', None)),
                        'normal and replicated work must share the admitted dispatch path')
        self.bridge.state = Mock(return_value={})
        dispatch = Mock()
        self.bridge.dispatch = dispatch
        receipt = {'execution_attempt_id': 'replica-attempt'}
        self.service.submit_replication.return_value = receipt
        self.service.get_run.side_effect = [
            {'trials': [{'execution_attempt_id': 'replica-attempt', 'dispatch_state': 'queued'}]},
            {'trials': [{'execution_attempt_id': 'replica-attempt', 'dispatch_state': 'succeeded'}]}]
        arguments = {'trial_id': 'original-trial',
                     'requested_budget': {'attempts': 1, 'execution_ms': 20000}}
        self.bridge.call('request_replication', arguments, 'replicate-1')
        self.bridge.call('request_replication', arguments, 'replicate-1')
        self.service.submit_replication.assert_called_with('author', 'p', 'r', request_key='replicate-1', **arguments)
        self.service.submit_trial.assert_not_called()
        dispatch.assert_called_once_with(receipt)


if __name__ == '__main__':
    unittest.main()
