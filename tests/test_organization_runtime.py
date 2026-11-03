import unittest

import test_organization as fixtures
from asr_service.control import ControlError


class OrganizationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.OrganizationTests('test_direction_topics_not_prescribed_and_lead_can_propose')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.setup_org();self.s=self.f.s
        self.identity=self.f.fixture.runtime_identity()

    def binding(self,token='organizer'):
        return self.s.organization_runtime_binding(token,'p','r',capability_profile='research-organization/1',capability_pack_sha256='a'*64)

    def claim(self,binding=None,key='claim'):
        args={} if binding is None else dict(organization_binding=binding)
        return self.s.claim_runtime('human-secret','p','r','host-owner',idempotency_key=key,
            runtime_identity=self.identity,requested_walltime_ms=1000,**args)

    def test_cannot_enable_organization_over_an_unreconciled_legacy_session(self):
        fixture=fixtures.OrganizationTests('test_direction_topics_not_prescribed_and_lead_can_propose')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.s.claim_runtime('human-secret','p','r','legacy',idempotency_key='legacy',
            runtime_identity=fixture.fixture.runtime_identity(),requested_walltime_ms=1000)
        with self.assertRaisesRegex(ControlError,'organization_runtime_reconciliation_required'):
            fixture.change('policy','capacity',dict(max_active_leads=2,max_active_workers=2))

    def test_membership_and_profile_are_frozen_in_existing_claim(self):
        with self.assertRaisesRegex(ControlError,'organization_binding_required'):self.claim()
        binding=self.binding();session=self.claim(binding)
        self.assertEqual(session['organization_binding']['subject'],'organizer')
        self.assertEqual(session['organization_binding']['member_revision'],1)
        self.assertTrue(self.claim(binding)['replayed'])
        with self.assertRaisesRegex(ControlError,'runtime_already_active'):self.claim(self.binding('lead'),key='parallel')
        self.assertEqual(self.s.get_run('human-secret','p','r')['budget']['research_walltime_ms']['reserved'],1000)

    def test_active_member_cannot_be_disabled_and_spent_cost_survives_role_change(self):
        session=self.claim(self.binding())
        with self.assertRaisesRegex(ControlError,'member_runtime_active'):
            self.f.change('member','organizer',dict(role='organizer',enabled=False),revision=1)
        self.s.abort_runtime_prelaunch('human-secret','p','r',session['session_id'],1,'host-owner',reason='preflight failure',actual_walltime_ms=100)
        self.f.change('member','organizer',dict(role='organizer',enabled=False),revision=1)
        second=self.claim(self.binding('lead'),key='lead-session')
        self.assertEqual(second['organization_binding']['role'],'lead')
        budget=self.s.get_run('human-secret','p','r')['budget']['research_walltime_ms']
        self.assertEqual(budget['spent'],100);self.assertEqual(budget['reserved'],1000)

    def test_active_identity_cannot_be_invalidated_by_a_noop_member_revision(self):
        self.claim(self.binding())
        with self.assertRaisesRegex(ControlError,'member_runtime_active'):
            self.f.change('member','organizer',dict(role='organizer',enabled=True),revision=1)

    def test_session_adapter_keeps_role_contexts_separate_and_charges_setup(self):
        import json
        from pathlib import Path
        from integrations.aar.bridge import ResearchBridge
        from integrations.runtimes.session import run_session
        from integrations.runtimes.pi import Limits, PiRuntime, RuntimeFailure
        root=Path(self.f.fixture.tmp.name);source=root/'fixture-auth.json'
        source.write_text(json.dumps({'openai-codex':{'type':'oauth','access':'fixture','refresh':'fixture'}}))
        pack=PiRuntime(model='gpt-6.1-sol',capabilities_path=Path('integrations/runtimes/organization-capabilities.json')).preflight_capabilities()
        contexts=[]
        class SetupOnly:
            provider='codex';model='gpt-6.1-sol'
            def preflight_capabilities(self):return pack
            def run(self,**arguments):
                contexts.append(Path(arguments['config_dir']))
                raise RuntimeFailure('deliberate_prelaunch_fixture')
        for actor in ('organizer','lead'):
            bridge=ResearchBridge(self.s,project='p',run='r',researcher_token=actor,supervisor_token='human-secret',
                workspace=root/actor,snapshots=root/'snapshots',capability_profile='research-organization/1')
            with self.assertRaisesRegex(RuntimeFailure,'deliberate_prelaunch_fixture'):
                run_session(SetupOnly(),bridge,config_dir=root/'private',native_session_id='r',prompt='No model call',
                            limits=Limits(3,1,1),oauth_source=source)
        self.assertEqual(len(set(contexts)),2)
        state=self.s.get_run('human-secret','p','r')
        self.assertEqual([x['organization_binding']['subject'] for x in state['runtime_sessions']],['organizer','lead'])
        self.assertEqual(state['budget']['research_walltime_ms']['reserved'],0)
        self.assertGreater(state['budget']['research_walltime_ms']['spent'],0)

    def test_stale_membership_and_unapproved_tool_profile_are_rejected(self):
        binding=self.binding('worker')
        self.f.change('member','worker',dict(role='lead',enabled=True),revision=1)
        with self.assertRaisesRegex(ControlError,'organization_binding_stale'):self.claim(binding)
        with self.assertRaisesRegex(ControlError,'organization_profile_unavailable'):
            self.s.organization_runtime_binding('lead','p','r',capability_profile='ood-study-development/1',capability_pack_sha256='b'*64)
        with self.assertRaisesRegex(ControlError,'forbidden'):self.binding('outsider')


if __name__=='__main__':unittest.main()
