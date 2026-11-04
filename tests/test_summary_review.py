import copy
import unittest
from asr_context import Material
from asr_context.summary import prepare
from asr_context.summary_review import prepare_review, assess


class SummaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.request=prepare([Material('source','v1','同环境复现；独立评价尚未完成。')],[dict(id='scope',value='shared',sources=['source'])],role='lead',max_bytes=6000)
        self.candidate=dict(request_sha256=self.request['request_sha256'],text='同环境复现，独立评价未完成。',claims=[dict(id='scope',value='shared',citations=['source'])])
        self.review=prepare_review(self.request,self.candidate,max_bytes=10000)
        self.verdict=dict(review_sha256=self.review['review_sha256'],verdict='accept',explanation='范围和未决事项保持一致。',issues=[],source_quotes=[dict(source='source',quote='独立评价尚未完成')])

    def test_model_opinion_cannot_install_context(self):
        result=assess(self.review,self.verdict,author_session='author',reviewer_session='reviewer')
        self.assertEqual(result['status'],'reviewed')
        self.assertFalse(result['eligible_for_application'])
        self.assertEqual(result['model_opinion'],'accept')

    def test_same_session_stale_binding_and_fabricated_quote_reject(self):
        self.assertEqual(assess(self.review,self.verdict,author_session='same',reviewer_session='same')['status'],'rejected')
        for field,value in [('review_sha256','wrong'),('source_quotes',[dict(source='source',quote='已独立验证')])]:
            wrong=copy.deepcopy(self.verdict);wrong[field]=value
            self.assertEqual(assess(self.review,wrong,author_session='a',reviewer_session='b')['status'],'rejected')

    def test_reject_uncertain_and_conflicting_accept_are_not_success(self):
        for verdict in ['reject','uncertain']:
            wrong=dict(self.verdict,verdict=verdict)
            self.assertEqual(assess(self.review,wrong,author_session='a',reviewer_session='b')['status'],'rejected')
        wrong=dict(self.verdict,issues=['遗漏反证'])
        self.assertEqual(assess(self.review,wrong,author_session='a',reviewer_session='b')['status'],'rejected')

    def test_capacity_and_structural_failures_do_not_reach_reviewer(self):
        self.assertEqual(prepare_review(self.request,self.candidate,max_bytes=100)['status'],'deferred')
        wrong=dict(self.candidate,claims=[])
        self.assertEqual(prepare_review(self.request,wrong,max_bytes=10000)['status'],'rejected')

    def test_installed_memory_quote_uses_explicit_decoded_summary_view(self):
        import json
        source=json.dumps(dict(role='memory',content=json.dumps(dict(schema='asr-installed-context/1',summary='同环境复现；独立评价尚未完成。',replayed_messages=[]))),ensure_ascii=False)
        request=prepare([Material('source','v1',source)],[dict(id='scope',value='shared',sources=['source'])],role='lead',max_bytes=10000)
        candidate=dict(self.candidate,request_sha256=request['request_sha256'])
        review=prepare_review(request,candidate,max_bytes=20000)
        verdict=dict(self.verdict,review_sha256=review['review_sha256'])
        result=assess(review,verdict,author_session='author',reviewer_session='reviewer')
        self.assertEqual(result['status'],'reviewed');self.assertEqual(result['quote_views'][0]['view'],'installed_memory_summary')
        bad=dict(verdict,source_quotes=[dict(source='source',quote='独立评价已经完成')])
        self.assertEqual(assess(review,bad,author_session='author',reviewer_session='reviewer')['status'],'rejected')
