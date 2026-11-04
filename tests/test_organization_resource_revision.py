import copy
import json
from pathlib import Path
import tempfile
import unittest

import test_study_admission as fixtures


class ModelPolicyRevisionTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.StudyAdmissionTests('test_shared_ledger_reservation_and_replay');f.setUp();self.addCleanup(f.doCleanups);f.configure();self.f=f
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.old=json.loads(Path('integrations/runtimes/organization-implementation-limits.json').read_text())
        self.old['budget']=copy.deepcopy(f.contract['budget'])
        self.new=copy.deepcopy(self.old)
        for k in ('research_walltime_ms','turns','tool_executions'):self.new['budget'][k]*=2
        self.new['session_limits']['walltime_seconds']*=2
        from powerflow_lab.runner import canonical
        import hashlib
        self.old_hash=hashlib.sha256(canonical(self.old)).hexdigest()
        document=copy.deepcopy(f.contract);document['provenance']['resource_policy_sha256']=self.old_hash
        f.service.publish_contract('human-secret','p','c',document,expected_revision=1,idempotency_key='resource-base')
        st=f.service.get_run('human-secret','p','r');f.service.command('human-secret','p','r','apply_contract',expected_revision=st['control_revision'],idempotency_key='base',payload=dict(contract_id='c',revision=2))
        st=f.service.get_run('human-secret','p','r');f.service.command('human-secret','p','r','pause',expected_revision=st['control_revision'],idempotency_key='pause')
        (self.root/'resource-policy.json').write_bytes(canonical(self.old))

    def revise(self, policy=None):
        from integrations.runtimes.organization_resources import revise_model_policy
        return revise_model_policy(self.f.service,'human-secret','p','r',self.root,policy or self.new,'User requests complete delivery with larger subscription allowance.')

    def test_extension_replays_without_resetting_cost_or_changing_science(self):
        # A settled charge survives the actual Control revision, not a new ledger.
        s=self.f.service
        with s._connect() as db:
            db.execute("INSERT INTO asr_budget_reservations(project,attempt,dimension,amount,actual) VALUES(?,?,?,?,?)",('p','past-model','research_walltime_ms',11,11))
        before=s.get_run('human-secret','p','r');receipt=self.revise()
        with s._connect() as db:
            db.execute("INSERT INTO asr_budget_reservations(project,attempt,dimension,amount,actual) VALUES(?,?,?,?,?)",('p','later-model','research_walltime_ms',7,7))
        again=self.revise()
        after=s.get_run('human-secret','p','r');self.assertEqual(receipt,again)
        self.assertEqual(after['budget']['research_walltime_ms']['spent'],18)
        self.assertEqual(after['contract_revision'],3);self.assertEqual(after['state'],'paused')
        for k in ('objective','execution_policy','runtime_policy','problem_ref','evaluation_ref'):
            self.assertEqual(before['contract']['document'][k],after['contract']['document'][k])
        self.assertEqual(json.loads((self.root/'resource-policy.json').read_text()),self.new)

    def test_rejects_compute_or_capacity_expansion(self):
        for key in ('attempts','execution_ms'):
            bad=copy.deepcopy(self.new);bad['budget'][key]+=1
            with self.assertRaisesRegex(ValueError,'model_only'):self.revise(bad)
        bad=copy.deepcopy(self.new);bad['capacity']['max_active_workers']+=1
        with self.assertRaisesRegex(ValueError,'model_only'):self.revise(bad)

    def test_rejects_running_owner(self):
        s=self.f.service;st=s.get_run('human-secret','p','r');s.command('human-secret','p','r','resume',expected_revision=st['control_revision'],idempotency_key='run')
        with self.assertRaisesRegex(ValueError,'reconcile'):self.revise()

    def test_reformatted_local_policy_requires_exact_original_source(self):
        from integrations.runtimes.organization_resources import revise_model_policy
        source=self.root/'original.json';source.write_bytes((self.root/'resource-policy.json').read_bytes())
        (self.root/'resource-policy.json').write_text(json.dumps(self.old,indent=2))
        with self.assertRaisesRegex(ValueError,'policy_contract_mismatch'):self.revise()
        receipt=revise_model_policy(self.f.service,'human-secret','p','r',self.root,self.new,
            'Explicit user revision',previous_policy_path=source)
        self.assertEqual(receipt['contract_revision'],3)

    def test_recovers_between_contract_application_and_local_receipt(self):
        from unittest.mock import patch
        from integrations.runtimes import organization_resources as module
        original=module.save
        def fail(path,value):
            if path.name=='receipt.json':raise OSError('injected interrupted receipt')
            original(path,value)
        with patch.object(module,'save',side_effect=fail):
            with self.assertRaisesRegex(OSError,'interrupted'):self.revise()
        receipt=self.revise()
        self.assertEqual(receipt['contract_revision'],3)
        self.assertEqual(self.f.service.get_run('human-secret','p','r')['contract_revision'],3)
