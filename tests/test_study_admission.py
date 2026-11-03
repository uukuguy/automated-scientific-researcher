import hashlib
import json
from pathlib import Path
import unittest

import test_control_service as fixtures
from asr_service import study


class StudyAdmissionTests(unittest.TestCase):
    setUp = fixtures.ControlTests.setUp
    start = fixtures.ControlTests.start

    def configure(self):
        public = Path(self.tmp.name) / 'public'
        public.mkdir()
        for name, value in dict(case={'bus': []}, train=[], id_dev=[], diagnostic=[]).items():
            (public / (name + '.json')).write_text(json.dumps(value))
        inventory = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in public.iterdir()}
        (public / 'manifest.json').write_text(json.dumps({'schema': 'asr-client-package/1', 'files': inventory}))
        config = dict(public_directory=str(public), public_manifest_sha256=hashlib.sha256((public / 'manifest.json').read_bytes()).hexdigest(),
                      image_id='sha256:' + 'a' * 64, validator_sha256='b' * 64)
        self.contract['provenance'] = dict(capability_profile='ood-study-development/1', study=config)
        self.contract['budget']['sample_proposals'] = 3
        for kind, document in study.expected_references(config).items():
            self.contract[kind + '_ref'] = self.service.references.register('p', kind, document)
        self.start()
        self.service.publish_hypothesis('agent-secret', 'p', 'h', dict(statement='Coverage helps', prediction='OOD error falls',
            scope='synthetic study', refutation_criteria='No benefit', study_type='exploratory',
            change_reason='initial', analysis_timing='prospective'), expected_revision=0, idempotency_key='h')

    def admit(self, key='label', coordinates=None):
        return self.service.submit_study('agent-secret', 'p', 'r', request_key=key,
            request=dict(operation='label', purpose='augmentation', coordinates=coordinates or [[1., 1., 1.]]),
            timeout_seconds=5, hypothesis_ref=dict(project_id='p', hypothesis_id='h', revision=1))

    def test_shared_ledger_reservation_and_replay(self):
        self.configure()
        trial = self.admit()
        self.assertEqual(self.admit(), trial)
        self.assertEqual(self.service.budgets.balance('p', 'sample_proposals')['reserved'], 1)
        self.assertEqual(self.service.budgets.balance('p', 'attempts')['reserved'], 1)
        self.assertEqual(trial['hypothesis_ref']['revision'], 1)
        self.service.command('human-secret', 'p', 'r', 'stop', expected_revision=1, idempotency_key='stop')
        self.assertEqual(self.service.budgets.balance('p', 'sample_proposals')['reserved'], 0)
        self.assertEqual(self.service.budgets.balance('p', 'sample_proposals')['spent'], 0)

    def test_validation_and_budget_denial_do_not_admit_partial_batch(self):
        self.configure()
        with self.assertRaises(ValueError):
            self.admit(coordinates=[[1, 1, 1], [2, 1, 1]])
        with self.assertRaisesRegex(ValueError, 'budget_exhausted'):
            self.admit(coordinates=[[1 + i * .01, 1, 1] for i in range(4)])
        self.assertEqual(self.service.budgets.balance('p', 'attempts')['reserved'], 0)
        self.assertFalse(self.service.get_run('agent-secret', 'p', 'r')['trials'])

    def test_profile_cannot_use_legacy_trial_path(self):
        self.configure()
        with self.assertRaisesRegex(ValueError, 'capability_unavailable'):
            fixtures.ControlTests.submit(self)

    def test_client_mutation_rejected_before_reservation(self):
        self.configure()
        Path(self.contract['provenance']['study']['public_directory'], 'train.json').write_text('[1]')
        with self.assertRaisesRegex(ValueError, 'client material'):
            self.admit()
        self.assertEqual(self.service.budgets.balance('p', 'attempts')['reserved'], 0)

    def test_profile_limit_is_recorded_and_probe_role_cannot_be_reassigned(self):
        self.configure()
        with self.assertRaisesRegex(ValueError, 'study_batch_limit') as error:
            self.admit(coordinates=[[1,1,1]] * 65)
        self.assertTrue(error.exception.details['recoverable'])
        self.assertEqual(error.exception.details['limit'], 64)
        state=self.service.get_run('human-secret','p','r')
        self.assertEqual(state['state'],'paused')
        self.service.command('human-secret','p','r','resume',expected_revision=state['control_revision'],idempotency_key='resume')
        self.admit()
        with self.assertRaisesRegex(ValueError, 'prior label/probe'):
            self.service.submit_study('agent-secret','p','r',request_key='probe',
                request=dict(operation='label',purpose='probe',coordinates=[[1,1,1]]),timeout_seconds=5,
                hypothesis_ref=dict(project_id='p',hypothesis_id='h',revision=1))


if __name__ == '__main__':
    unittest.main()
