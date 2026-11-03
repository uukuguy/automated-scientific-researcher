"""Native-journal migration for the same bounded research identity; no model."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from integrations.runtimes import p3_acceptance


class ResumeTests(unittest.TestCase):
    def test_migration_preserves_original_journal_and_uses_only_fresh_oauth(self):
        helper=getattr(p3_acceptance,'migrate_native_session',None)
        self.assertTrue(callable(helper),'auth-failure recovery must preserve original native evidence')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);sessions=root/'pi-private/sessions';sessions.mkdir(parents=True)
            original=sessions/'date_research_same.jsonl';raw=b'{"id":"research_same","kind":"historical error"}\n';original.write_bytes(raw)
            (sessions/'interactive-login-unrelated.jsonl').write_text('do not copy')
            auth=root/'private-fresh-auth.json'
            auth.write_text(json.dumps({'other':{'type':'api_key','key':'fixture'},'openai-codex':{'type':'oauth','access':'fresh-fixture','refresh':'fixture','expires':9999999999999}}))
            result=helper(root,'research_same',auth)
            self.assertEqual(original.read_bytes(),raw)
            copied=Path(result['config_dir'])/'sessions'/original.name
            self.assertEqual(copied.read_bytes(),raw)
            self.assertEqual(len(list(copied.parent.iterdir())),1)
            self.assertEqual(result['journals'][0]['sha256'],hashlib.sha256(raw).hexdigest())
            selected=json.loads((Path(result['config_dir'])/'auth.json').read_text())
            self.assertEqual(set(selected),{'openai-codex'})
            self.assertEqual(selected['openai-codex']['access'],'fresh-fixture')
            with self.assertRaises(FileExistsError):helper(root,'research_same',auth)


if __name__=='__main__':unittest.main()
