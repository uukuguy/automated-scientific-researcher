import unittest
from datetime import datetime,timedelta,timezone
import test_control_service as fixtures

class QuotaObservationTests(unittest.TestCase):
    setUp=fixtures.ControlTests.setUp
    start=fixtures.ControlTests.start
    submit=fixtures.ControlTests.submit

    def observe(self,state,key,seconds=0):
        return self.service.observe_quota('human-secret','p','r',request_key=key,provider='codex',state=state,source='operator_observation',observed_at=(self.origin+timedelta(seconds=seconds)).isoformat())

    def test_unknown_and_stale_observations_preserve_block_and_consumption(self):
        self.start();self.submit();self.origin=datetime.now(timezone.utc)
        exhausted=self.observe('exhausted','exhausted')
        self.assertEqual(self.observe('exhausted','exhausted'),exhausted)
        self.observe('unknown','unknown',1)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['quota_state'],'exhausted')
        self.observe('available','stale',-1)
        self.assertEqual(self.service.get_run('agent-secret','p','r')['quota_state'],'exhausted')
        self.assertEqual(self.service.budgets.balance('p','attempts')['reserved'],1)
        self.observe('available','fresh',2)
        run=self.service.get_run('agent-secret','p','r')
        self.assertEqual(run['quota_state'],'available');self.assertFalse(run['admission_open'])
        self.assertEqual(len(run['quota_observations']),4)
        with self.assertRaises(ValueError):self.service.observe_quota('agent-secret','p','r',request_key='forged',provider='codex',state='available',source='provider_response',observed_at=self.origin.isoformat())

    def test_legacy_unknown_and_contract_switch_do_not_clear_sourced_block(self):
        self.start();self.origin=datetime.now(timezone.utc)
        self.observe('exhausted','known')
        run=self.service.get_run('human-secret','p','r')
        self.service.command('human-secret','p','r','quota',expected_revision=run['control_revision'],idempotency_key='legacy-unknown',payload={'state':'unknown'})
        self.assertEqual(self.service.get_run('human-secret','p','r')['quota_state'],'exhausted')
        self.service.publish_contract('human-secret','p','c',self.contract,expected_revision=1,idempotency_key='same-provider')
        run=self.service.get_run('human-secret','p','r')
        self.service.command('human-secret','p','r','apply_contract',expected_revision=run['control_revision'],idempotency_key='apply',payload={'contract_id':'c','revision':2})
        self.assertEqual(self.service.get_run('human-secret','p','r')['quota_state'],'exhausted')
        with self.assertRaisesRegex(ValueError,'invalid_quota_observation'):
            self.observe('available','future',86400)

if __name__=='__main__':unittest.main()
