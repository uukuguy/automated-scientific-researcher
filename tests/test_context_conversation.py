import copy
import unittest
from asr_context.conversation import Message, capture, verify, materials


class ConversationCoverageTests(unittest.TestCase):
    def history(self):
        rows=[Message('system','system','现行规则'),Message('user','user','继续研究'),
              Message('call1','assistant','调用',calls=(('c1','read'),('c2','read'))),
              Message('result1','tool','失败',result_for='c1',tool_name='read',negative=True),
              Message('result2','tool','成功',result_for='c2',tool_name='read'),
              Message('call2','assistant','下一步',calls=(('c3','read'),)),
              Message('result3','tool','结果',result_for='c3',tool_name='read'),
              Message('final','assistant','候选结论')]
        return capture('research/lead',rows,source_revision='source-hash',keep_recent_groups=1)

    def test_calls_results_and_latest_negative_feedback_are_atomic(self):
        history=self.history();group=next(g for g in history['groups'] if 'call1' in g['ids'])
        self.assertEqual(group['ids'],['call1','result1','result2'])
        self.assertTrue(set(group['ids'])<=set(history['protected_ids']))
        projected=materials(history)
        self.assertEqual(next(m for m in projected if m.id=='call1').group,next(m for m in projected if m.id=='result2').group)

    def test_partition_binds_every_message_and_requires_summary_sources(self):
        h=self.history();summarized=('call2','result3');retained=tuple(m['id'] for m in h['body']['messages'] if m['id'] not in summarized)
        good=verify(h,summarized_ids=summarized,retained_ids=retained,summary_source_ids=summarized)
        self.assertEqual(good['status'],'coverage_verified');self.assertFalse(good['installation_authorized'])
        self.assertEqual(verify(h,summarized_ids=summarized,retained_ids=retained,summary_source_ids=())['status'],'rejected')
        self.assertEqual(verify(h,summarized_ids=('call2',),retained_ids=retained+('result3',),summary_source_ids=summarized)['status'],'rejected')

    def test_protected_content_cannot_be_summarized_but_system_can_be_replayed(self):
        h=self.history();ids=tuple(m['id'] for m in h['body']['messages'])
        self.assertEqual(verify(h,summarized_ids=('user',),retained_ids=tuple(i for i in ids if i!='user'),summary_source_ids=ids)['status'],'rejected')
        result=verify(h,summarized_ids=(),retained_ids=tuple(i for i in ids if i!='system'),replayed_ids=('system',),summary_source_ids=())
        self.assertEqual(result['status'],'coverage_verified')

    def test_open_calls_and_corrupt_history_do_not_approve(self):
        h=capture('scope',[Message('call','assistant','等待',calls=(('c','tool'),))],source_revision='sha',keep_recent_groups=1)
        self.assertEqual(verify(h,summarized_ids=(),retained_ids=('call',),summary_source_ids=())['status'],'deferred')
        h=self.history();h['body']['messages'][0]['text']='篡改'
        self.assertEqual(verify(h,summarized_ids=(),retained_ids=(),summary_source_ids=())['status'],'rejected')

    def test_orphan_results_duplicate_calls_and_tool_name_mismatch_reject(self):
        for rows in [[Message('r','tool','x',result_for='absent',tool_name='read')],
                     [Message('a','assistant','x',calls=(('c','read'),)),Message('r','tool','x',result_for='c',tool_name='write')],
                     [Message('duplicate','assistant','x',calls=(('c','read'),('c','read')))]]:
            with self.assertRaises(ValueError):capture('scope',rows,source_revision='sha',keep_recent_groups=1)
