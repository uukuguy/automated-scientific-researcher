import copy
import unittest
from asr_context import Material
from asr_context.summary import prepare
from asr_context.summary_review import prepare_review
from asr_context.application import plan


class ContextApplicationTests(unittest.TestCase):
    def setUp(self):
        self.request=prepare([Material('evidence','v1','原始反证仍然有效。')],[dict(id='negative',value=True,sources=['evidence'])],role='lead',max_bytes=5000)
        self.candidate=dict(request_sha256=self.request['request_sha256'],text='反证仍有效。',claims=[dict(id='negative',value=True,citations=['evidence'])])
        self.review_request=prepare_review(self.request,self.candidate,max_bytes=8000)
        self.review=dict(review_sha256=self.review_request['review_sha256'],verdict='accept',explanation='保留了反证。',issues=[],source_quotes=[dict(source='evidence',quote='原始反证仍然有效')])
        self.state=dict(project_id='p',run_id='r',contract_revision=1,control_revision=1,
            task_revisions={'task':2},unsettled_executions=['attempt-ongoing'],source_fingerprints={s['id']:s['sha256'] for s in self.request['payload']['sources']})

    def invoke(self,**kw):
        return plan(self.request,self.candidate,self.review_request,self.review,author_session='author',reviewer_session='reviewer',expected_state=self.state,current_state=kw.pop('current_state',self.state),**kw)

    def test_accepted_review_only_produces_host_admission_plan(self):
        result=self.invoke()
        self.assertEqual(result['status'],'admission_required')
        self.assertFalse(result['eligible_for_application'])
        self.assertEqual(result['preserve_unsettled_executions'],['attempt-ongoing'])

    def test_rule_task_evidence_or_execution_change_defers_old_summary(self):
        changes={'control_revision':2,'contract_revision':2,'task_revisions':{'task':3},'source_fingerprints':{'evidence':'changed'},'unsettled_executions':[],'run_id':'different'}
        for key,value in changes.items():
            current=copy.deepcopy(self.state);current[key]=value
            self.assertEqual(self.invoke(current_state=current)['status'],'deferred')

    def test_open_tool_interaction_defers_without_cancelling_trials(self):
        result=self.invoke(open_interactions=('tool-call',))
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result['reason'],'interaction_boundary_open')

    def test_review_for_another_candidate_cannot_be_reused(self):
        self.candidate['text']='反证已被推翻。'
        self.assertEqual(self.invoke()['status'],'rejected')

    def test_original_source_binding_is_required_even_if_states_match(self):
        self.state['source_fingerprints']={}
        self.assertEqual(self.invoke()['status'],'rejected')
