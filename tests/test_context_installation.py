import unittest
from dataclasses import asdict
from asr_context import Material,material_digest
from asr_context.conversation import Message,capture,materials,verify
from asr_context.summary import prepare
from asr_context.summary_review import prepare_review


class InstallationPlanTests(unittest.TestCase):
    def fixture(self):
        rows=[Message('u','user','保留最初要求'),Message('a','assistant','旧分析'),Message('b','assistant','当前工作')]
        snap=capture('scope',rows,source_revision='r',keep_recent_groups=1)
        observed=dict(status='observed',conversation=snap,witness=dict(leaf_id='nb',journal_sha256='x',source_mapping=[dict(message_id=r.id,native_entry_id='n'+r.id,projected_index=0) for r in rows]))
        request=prepare(materials(snap),[dict(id='failure',value='不代表独立复现',sources=['a'])],role='lead',max_bytes=20000)
        candidate=dict(request_sha256=request['request_sha256'],text='旧分析不代表独立复现。',claims=[dict(id='failure',value='不代表独立复现',citations=['a'])])
        rq=prepare_review(request,candidate,max_bytes=30000)
        rv=dict(review_sha256=rq['review_sha256'],verdict='accept',explanation='保留限制',issues=[],source_quotes=[dict(source='a',quote='旧分析')])
        return observed,request,candidate,rq,rv

    def call(self,values=None,cut='nb'):
        from asr_context.installation import compile_plan
        return compile_plan(*(values or self.fixture()),author_session='author',reviewer_session='reviewer',first_kept_entry_id=cut)

    def test_protected_user_is_replayed_exactly_and_tail_retained(self):
        import json
        result=self.call();self.assertEqual(result['status'],'installation_plan',result)
        envelope=json.loads(result['summary']);self.assertEqual(envelope['replayed_messages'][0]['text'],'保留最初要求')
        self.assertEqual(result['coverage']['summarized_ids'],['a']);self.assertEqual(result['coverage']['retained_ids'],['b'])
        self.assertFalse(result['installation_authorized'])

    def test_changed_sources_review_and_unknown_cut_are_rejected(self):
        values=self.fixture();values[1]['payload']['sources'][0]['text']='篡改'
        self.assertEqual(self.call(values)['status'],'rejected')
        values=self.fixture();values[-1]['verdict']='reject'
        self.assertEqual(self.call(values)['status'],'rejected')
        self.assertEqual(self.call(cut='missing')['status'],'rejected')

    def test_replay_requires_exact_full_record_and_groups_cannot_split(self):
        rows=[Message('u','user','要求'),Message('a','assistant','调用',calls=(('call','read'),)),Message('t','tool','结果',result_for='call',tool_name='read'),Message('b','assistant','尾部')]
        snap=capture('s',rows,source_revision='r',keep_recent_groups=1)
        replay={'u':asdict(rows[0])}
        good=verify(snap,summarized_ids=('a','t'),retained_ids=('b',),summary_source_ids=('a','t'),replayed_ids=('u',),replay_messages=replay)
        self.assertEqual(good['status'],'coverage_verified')
        replay['u']['text']='修改'
        self.assertEqual(verify(snap,summarized_ids=('a','t'),retained_ids=('b',),summary_source_ids=('a','t'),replayed_ids=('u',),replay_messages=replay)['status'],'rejected')

    def test_native_checkpoint_replay_does_not_duplicate_system_text_in_summary(self):
        import json
        from asr_context.installation import compile_plan
        observed,request,candidate,rq,rv=self.fixture()
        rows=[Message('sys','system','固定系统说明'),Message('u','user','保留最初要求'),Message('a','assistant','旧分析'),Message('b','assistant','当前工作')]
        snapshot=capture('scope',rows,source_revision='r',keep_recent_groups=1)
        observed=dict(status='observed',conversation=snapshot,witness=dict(leaf_id='nb',source_mapping=[dict(message_id=r.id,native_entry_id='n'+r.id,projected_index=0) for r in rows]))
        request=prepare(materials(snapshot),[],role='lead',max_bytes=20000);candidate=dict(request_sha256=request['request_sha256'],text='旧分析保持范围限制。',claims=[])
        rq=prepare_review(request,candidate,max_bytes=30000);rv=dict(review_sha256=rq['review_sha256'],verdict='accept',explanation='保留原文',issues=[],source_quotes=[dict(source='a',quote='旧分析')])
        result=compile_plan(observed,request,candidate,rq,rv,author_session='a',reviewer_session='b',first_kept_entry_id='nb',native_replay_ids=('sys',))
        self.assertEqual(result['status'],'installation_plan');self.assertNotIn('固定系统说明',result['summary'])
        self.assertEqual(result['native_replayed_messages'][0]['text'],'固定系统说明')
        self.assertEqual([r['id'] for r in json.loads(result['summary'])['replayed_messages']],['u'])
