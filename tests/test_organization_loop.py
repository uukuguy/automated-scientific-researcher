import unittest
import test_organization as fixtures
from integrations.aar.organization_loop import pending,acknowledge
from asr_service.control import ControlError


class OrganizationLoopTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.OrganizationTests('test_direction_topics_not_prescribed_and_lead_can_propose')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.setup_org();self.s=self.f.s

    def test_model_records_choose_targets_without_fixed_scientific_directions(self):
        self.assertEqual([x['recipient'] for x in pending(self.s,'human-secret','p','r')],['organizer'])
        self.f.change('direction','chosen',dict(self.f.direction('lead2'),title='A model-chosen topic'),'organizer')
        self.f.change('message','review',dict(recipients=['lead'],text='Challenge the assumptions',evidence_trial_ids=[]),'lead2')
        self.assertEqual([x['recipient'] for x in pending(self.s,'human-secret','p','r')],['organizer','lead2','lead'])

    def test_ack_requires_matching_exited_runtime_and_is_durable(self):
        deliveries=pending(self.s,'human-secret','p','r')
        binding=self.s.organization_runtime_binding('organizer','p','r',capability_profile='research-organization/1',capability_pack_sha256='a'*64)
        session=self.s.claim_runtime('human-secret','p','r','worker',idempotency_key='runtime',
            runtime_identity=self.f.fixture.runtime_identity(),requested_walltime_ms=1000,organization_binding=binding)
        with self.assertRaisesRegex(ControlError,'execution_not_reconciled'):
            acknowledge(self.s,'human-secret','p','r',deliveries,session['session_id'])
        self.f.fixture.attach_exited_process(session)
        self.s.release_runtime('human-secret','p','r',session['session_id'],1,'worker',execution_exited=True,actual_walltime_ms=1)
        # Trusted-host acknowledgement plumbing only; no claim of actual model delivery.
        receipt=acknowledge(self.s,'human-secret','p','r',deliveries,session['session_id'])
        self.assertEqual(receipt,acknowledge(self.s,'human-secret','p','r',deliveries,session['session_id']))
        self.assertEqual(pending(self.s,'human-secret','p','r'),[])


if __name__=='__main__':unittest.main()
