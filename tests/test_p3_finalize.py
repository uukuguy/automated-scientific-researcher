"""Explicit bounded engineering closeout; no model calls."""
import importlib
import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
import hashlib
from unittest.mock import Mock

from integrations.runtimes.pi import PiRuntime,Limits
from integrations.aar.bridge import ResearchBridge


class FinalizationTests(unittest.TestCase):
    def test_original_reports_are_reverified_before_and_after_closeout(self):
        module=importlib.import_module('integrations.runtimes.p3_finalize')
        helper=getattr(module,'reports_match',None)
        self.assertTrue(callable(helper))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);reports={}
            for name in ('result.json','result-resumed.json'):
                (root/name).write_bytes(b'original evidence')
                reports[name]=hashlib.sha256(b'original evidence').hexdigest()
            plan={'source_reports':reports}
            self.assertTrue(helper(root,plan))
            (root/'result.json').write_bytes(b'changed evidence')
            self.assertFalse(helper(root,plan))

    def test_readonly_bridge_blocks_every_scientific_mutation_before_service_access(self):
        service=Mock()
        with tempfile.TemporaryDirectory() as directory:
            bridge=ResearchBridge(service,project='p',run='r',researcher_token='reader',supervisor_token='supervisor',
                workspace=directory,snapshots=Path(directory)/'snapshots',capability_profile='powerflow-readonly-finalization/1')
            for operation in ('snapshot','publish_hypothesis','publish_finding','submit_trial','freeze_candidate','submit_candidate','request_replication','request_evaluation'):
                with self.subTest(operation=operation),self.assertRaisesRegex(ValueError,'unsupported_bridge_operation'):
                    bridge.call(operation,{},'blocked')
        self.assertEqual(service.mock_calls,[])

    def test_actual_runtime_argv_does_not_enable_native_write_or_edit(self):
        from test_runtimes import RuntimeTests
        with tempfile.TemporaryDirectory() as directory:
            executable=RuntimeTests().fake(directory,[{'type':'agent_settled'}])
            path=Path(executable)
            path.write_text(path.read_text().replace('"sessionId":"native"','"toolArg":sys.argv[sys.argv.index("--tools")+1],"sessionId":"native"'))
            runtime=PiRuntime(executable=executable,model='test',capabilities_path=Path('integrations/runtimes/p3-finalization-capabilities.json'))
            result=runtime.run(workspace=Path(directory),config_dir=Path(directory),session_id='readonly',prompt='fixture',
                limits=Limits(2,1,1),bridge_url='http://localhost:1',bridge_token='fixture')
            self.assertEqual(result['session']['toolArg'],'asr,read,grep,find,ls')

    def test_readonly_pack_grants_no_scientific_writes_or_host_edit_tools(self):
        path=Path('integrations/runtimes/p3-finalization-capabilities.json')
        self.assertTrue(path.exists(),'engineering closeout requires a separate read-only role')
        pack=PiRuntime(model='test',capabilities_path=path).preflight_capabilities()['pack']
        self.assertEqual(pack['tools'],['asr.state'])
        self.assertEqual(pack['coding_tools'],['pi.read','pi.grep','pi.find','pi.ls'])

    def test_contract_adds_only_explicit_closeout_budget_and_retains_overrun(self):
        name='integrations.runtimes.p3_finalize'
        self.assertIsNotNone(importlib.util.find_spec(name),'explicit revision helper required')
        module=importlib.import_module(name)
        original=dict(budget=dict(research_walltime_ms=180000,turns=20,tool_executions=32,
            attempts=4,execution_ms=80000,evaluation_attempts=3,evaluation_ms=60000),provenance={'source':'original'})
        document=module.closeout_document(original,original_spent=180037,source_reports={'original':'a'*64,'recovered':'b'*64})
        self.assertEqual(document['budget']['research_walltime_ms'],210000)
        self.assertEqual(document['budget']['turns'],22)
        self.assertEqual(document['budget']['tool_executions'],35)
        for dimension in ('attempts','execution_ms','evaluation_attempts','evaluation_ms'):
            self.assertEqual(document['budget'][dimension],original['budget'][dimension])
        self.assertEqual(document['provenance']['original_walltime_overrun_ms'],37)
        self.assertEqual(original['budget']['research_walltime_ms'],180000)


if __name__=='__main__':unittest.main()
