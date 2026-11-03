import json
from pathlib import Path
import tempfile
import unittest

from integrations.runtimes.organization_pilot import resources,sync_snapshots,check_recovery_contract,remaining_session_limits
from integrations.runtimes.pi import RuntimeFailure
from integrations.aar.bridge import ResearchBridge
import test_control_service as fixtures


class OrganizationPilotTests(unittest.TestCase):
    def test_exhausted_budget_names_dimension_without_starting_session(self):
        policy=resources(Path('integrations/runtimes/organization-limits.json'))
        budget={key:dict(limit=value,spent=0,reserved=0,available=value) for key,value in policy['budget'].items()}
        self.assertEqual(remaining_session_limits(policy['session_limits'],budget).walltime_seconds,240)
        budget['turns'].update(spent=160,available=0)
        with self.assertRaises(RuntimeFailure) as caught:
            remaining_session_limits(policy['session_limits'],budget)
        self.assertEqual(caught.exception.details['kind'],'turns')
        self.assertEqual(caught.exception.details['limit'],160)
        self.assertEqual(caught.exception.details['observed'],160)
        self.assertTrue(caught.exception.details['recoverable'])

    def test_recovery_compares_admitted_contract_and_rejects_changes(self):
        f=fixtures.ControlTests();f.setUp();self.addCleanup(f.doCleanups)
        f.start()
        state=f.service.get_run('human-secret','p','r')
        check_recovery_contract(f.service,'p',state,f.contract)
        changed=json.loads(json.dumps(f.contract))
        changed['objective']['question']='Changed research question'
        with self.assertRaisesRegex(ValueError,'recovery_contract_changed'):
            check_recovery_contract(f.service,'p',state,changed)

    def test_zero_compute_contract_and_explicit_budget(self):
        f=fixtures.ControlTests();f.setUp();self.addCleanup(f.doCleanups)
        f.contract['provenance']['capability_profile']='research-organization/1'
        f.contract['budget'].update(attempts=0,execution_ms=0)
        f.start()
        policy=resources(Path('integrations/runtimes/organization-limits.json'))
        self.assertEqual(policy['budget']['research_walltime_ms'],1200000)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'policy.json';policy['budget']['tool_executions']=0
            path.write_text(json.dumps(policy))
            with self.assertRaisesRegex(ValueError,'finite_model_budget'):resources(path)

    def test_shared_snapshots_are_exact_and_modified_copy_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'writer';work.mkdir()
            (work/'proposal.md').write_text('Author proposal, not validated science.')
            bridge=ResearchBridge(None,project='p',run='r',researcher_token='unused',supervisor_token='unused',
                workspace=work,snapshots=root/'snapshots')
            receipt=bridge.snapshot(['proposal.md']);reader=root/'reader';reader.mkdir()
            sync_snapshots(root,reader)
            path=reader/'shared-artifacts'/receipt['snapshot_sha256']/'proposal.md'
            self.assertEqual(path.read_text(),(work/'proposal.md').read_text())
            path.chmod(0o644);path.write_text('Edited copy')
            with self.assertRaisesRegex(ValueError,'shared_artifact_modified'):sync_snapshots(root,reader)


if __name__=='__main__':unittest.main()
