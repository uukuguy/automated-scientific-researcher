import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from integrations.aar.bridge import ResearchBridge
from integrations.runtimes.ood_finalize import frozen_proposal, export_final_result


class FinalProposalTests(unittest.TestCase):
    def test_final_export_requires_intact_successful_evidence(self):
        from powerflow_lab.runner import digest
        from asr_supervisor.supervisor import publication_inventory
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); evidence=root/'evidence';evidence.mkdir()
            workspace=root/'workspace';workspace.mkdir()
            result=dict(schema='asr-ood-independent-validation/1',assessment='objective_not_met_on_frozen_test')
            (evidence/'study-result.json').write_text(json.dumps(result))
            (evidence/'manifest.json').write_text(json.dumps(dict(artifacts=publication_inventory(evidence))))
            report=dict(status='succeeded',execution_exited=True,evidence_path=str(evidence),manifest_hash=digest(evidence/'manifest.json'))
            export_final_result(report,workspace)
            self.assertEqual(json.loads((workspace/'INDEPENDENT-FINAL-RESULT.json').read_text()),result)
            (evidence/'study-result.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'evidence'):export_final_result(report,workspace)
            report['status']='failed'
            with self.assertRaisesRegex(ValueError,'successful'):export_final_result(report,workspace)

    def test_proposal_must_match_both_frozen_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);work=root/'workspace';work.mkdir()
            (work/'FINAL-TEST-PROPOSAL.json').write_text(json.dumps(dict(primary_model='fitted',model_trials=['fitted'])))
            (work/'FINAL-TEST-PROPOSAL.md').write_text('Select using development evidence before final scores.')
            bridge=ResearchBridge(None,project='p',run='r',researcher_token='unused',supervisor_token='unused',
                                  workspace=work,snapshots=root/'snapshots')
            with self.assertRaisesRegex(ValueError,'snapshot'):frozen_proposal(root,'p','r')
            receipt=bridge.snapshot(['FINAL-TEST-PROPOSAL.md','FINAL-TEST-PROPOSAL.json'])
            protocol,snapshot=frozen_proposal(root,'p','r')
            self.assertEqual(snapshot,receipt['snapshot_sha256'])
            self.assertEqual(protocol['primary_model'],'fitted')
            (work/'FINAL-TEST-PROPOSAL.md').write_text('Changed after seeing a score.')
            with self.assertRaisesRegex(ValueError,'snapshot'):frozen_proposal(root,'p','r')


if __name__=='__main__':unittest.main()
