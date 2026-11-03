import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from integrations.aar.bridge import ResearchBridge
from integrations.runtimes.ood_finalize import frozen_proposal


class FinalProposalTests(unittest.TestCase):
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
