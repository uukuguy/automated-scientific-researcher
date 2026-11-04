import json
from pathlib import Path
import tempfile
import unittest
from integrations.runtimes.summary_acceptance import prepare_validation, parse_reply


class SummaryAcceptanceTests(unittest.TestCase):
    def test_preparation_has_zero_scientific_budget_and_frozen_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run'
            result=prepare_validation(root,model='gpt-6.1-sol')
            self.assertEqual(result['budget']['attempts'],0)
            self.assertEqual(result['budget']['execution_ms'],0)
            self.assertTrue((root/'summary-request.json').is_file())
            with self.assertRaises(FileExistsError):prepare_validation(root,model='gpt-6.1-sol')

    def test_reply_parser_uses_visible_final_text_and_rejects_non_json(self):
        value=parse_reply(dict(status='settled',assistant_messages=[dict(content=[dict(type='thinking',thinking='private'),dict(type='text',text='{"text":"visible"}')])]))
        self.assertEqual(value,{'text':'visible'})
        with self.assertRaises(ValueError):parse_reply(dict(status='provider_error',assistant_messages=[]))

    def test_drain_after_explicit_resume_has_a_distinct_command_key(self):
        import test_control_service as fixtures
        from integrations.runtimes.summary_acceptance import drain
        fixture=fixtures.ControlTests();fixture.setUp();self.addCleanup(fixture.doCleanups);fixture.start()
        first=drain(fixture.service,'human-secret','p','r')
        fixture.service.command('human-secret','p','r','resume',expected_revision=first['control_revision'],idempotency_key='resume-once')
        second=drain(fixture.service,'human-secret','p','r')
        self.assertEqual(second['state'],'paused')
        self.assertGreater(second['control_revision'],first['control_revision'])

    def test_tampered_request_is_refused_before_any_model_call(self):
        from unittest.mock import patch
        from integrations.runtimes.summary_acceptance import execute
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run';prepare_validation(root,model='gpt-6.1-sol')
            path=root/'summary-request.json';request=json.loads(path.read_text());request['payload']['instruction']='tampered'
            path.write_text(json.dumps(request))
            with patch('integrations.runtimes.summary_acceptance.run_session') as model:
                with self.assertRaisesRegex(ValueError,'frozen_summary_request_changed'):execute(root)
                model.assert_not_called()
