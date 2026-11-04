import unittest
from asr_context import Material
from asr_context.summary import prepare
from asr_context.summary_review import prepare_review
from asr_service.control import ControlError
import test_control_research_notes as fixtures


class ContextAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.base=fixtures.ControlResearchNotesTests();self.base.setUp();self.addCleanup(self.base.doCleanups);self.s=self.base.s
        draft=self.base.save();self.base.call('adopt',key='adopt',revision=draft['revision'],expected_note=None)

    def prepare(self):
        return self.s.prepare_context('human-secret','p','r',subject='lead',reviewer_subject='lead2',idempotency_key='prep')

    def session(self,subject,key):
        binding=self.s.organization_runtime_binding(subject,'p','r',capability_profile='research-organization/1',capability_pack_sha256='a'*64)
        claim=self.s.claim_runtime('human-secret','p','r','worker',idempotency_key=key,runtime_identity=self.base.org.fixture.runtime_identity(),requested_walltime_ms=1000,organization_binding=binding)
        self.base.org.fixture.attach_exited_process(claim)
        self.s.release_runtime('human-secret','p','r',claim['session_id'],claim['epoch'],'worker',execution_exited=True,actual_walltime_ms=100)
        return claim['session_id']

    def bundle(self,prepared):
        rows=[Material(**{k:tuple(v) if k in ('references','citations','roles') else v for k,v in row.items()}) for row in prepared['materials']]
        source=next(r for r in rows if r.id.startswith('note:'))
        request=prepare(rows,[dict(id='scope',value='unverified',sources=[source.id])],role='lead',max_bytes=20000)
        candidate=dict(request_sha256=request['request_sha256'],text=source.text,claims=[dict(id='scope',value='unverified',citations=[source.id])])
        review_request=prepare_review(request,candidate,max_bytes=30000)
        review=dict(review_sha256=review_request['review_sha256'],verdict='accept',explanation='保留限制。',issues=[],source_quotes=[dict(source=source.id,quote=source.text)])
        return dict(request=request,candidate=candidate,review_request=review_request,review=review,author_session=self.session('lead','author'),reviewer_session=self.session('lead2','reviewer'))

    def admit(self,prepared,bundle,token='human-secret',key='admit'):
        return self.s.admit_context(token,'p','r',subject='lead',preparation_id=prepared['preparation_id'],idempotency_key=key,**bundle)

    def test_host_reads_sources_and_records_admission_without_installation(self):
        prepared=self.prepare();bundle=self.bundle(prepared);result=self.admit(prepared,bundle)
        self.assertEqual(result['status'],'admitted');self.assertFalse(result['context_installed']);self.assertFalse(result['installation_authorized'])
        self.assertEqual(result,self.admit(prepared,bundle))

    def test_researcher_cannot_self_prepare_or_admit(self):
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.s.prepare_context('lead','p','r',subject='lead',reviewer_subject='lead2',idempotency_key='bad')
        prepared=self.prepare();bundle=self.bundle(prepared)
        with self.assertRaisesRegex(ControlError,'forbidden'):self.admit(prepared,bundle,token='lead')

    def test_changed_rule_rejects_prepared_context(self):
        prepared=self.prepare();bundle=self.bundle(prepared)
        state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','pause',expected_revision=state['control_revision'],idempotency_key='pause')
        self.assertEqual(self.admit(prepared,bundle)['status'],'deferred')

    def test_other_reviewer_or_edited_source_cannot_be_substituted(self):
        prepared=self.prepare();bundle=self.bundle(prepared);bundle['reviewer_session']=bundle['author_session']
        with self.assertRaises(ControlError):self.admit(prepared,bundle)

    def test_edited_request_cannot_replace_server_frozen_materials(self):
        prepared=self.prepare();bundle=self.bundle(prepared)
        bundle['request']['payload']['sources'][0]['text']='修改来源'
        result=self.admit(prepared,bundle)
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result['check']['reason'],'context_request_sources_mismatch')

    def test_unlaunched_session_cannot_support_admission(self):
        prepared=self.prepare();bundle=self.bundle(prepared)
        binding=self.s.organization_runtime_binding('lead2','p','r',capability_profile='research-organization/1',capability_pack_sha256='a'*64)
        claim=self.s.claim_runtime('human-secret','p','r','worker',idempotency_key='unlaunched',runtime_identity=self.base.org.fixture.runtime_identity(),requested_walltime_ms=1000,organization_binding=binding)
        self.s.abort_runtime_prelaunch('human-secret','p','r',claim['session_id'],claim['epoch'],'worker',reason='preflight failed',actual_walltime_ms=1)
        bundle['reviewer_session']=claim['session_id']
        with self.assertRaisesRegex(ControlError,'context_review_session_unavailable'):self.admit(prepared,bundle)

    def test_cross_project_operator_is_rejected(self):
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.s.prepare_context('other-secret','p','r',subject='lead',reviewer_subject='lead2',idempotency_key='other-project')

    def test_run_and_member_ids_with_delimiters_do_not_share_a_namespace(self):
        from asr_service.context_admission import _scope
        self.assertNotEqual(_scope('prepare','r','lead:other'),_scope('prepare','r:lead','other'))
