import copy
import unittest
from asr_context import Material
from asr_context.summary import prepare, check


class ResearchSummaryTests(unittest.TestCase):
    def setUp(self):
        self.obligations=[dict(id='scope',value='shared_service',sources=['evidence']),dict(id='hidden',value='not_completed',sources=['evidence'])]
        self.request=prepare([Material('evidence','r1','组织内共用环境复现；独立评价未完成。')],self.obligations,role='lead',max_bytes=6000)
        self.candidate=dict(request_sha256=self.request['request_sha256'],text='同环境复现完成，独立评价未完成。',claims=[dict(id=r['id'],value=r['value'],citations=r['sources']) for r in self.obligations])

    def test_matching_fields_still_require_semantic_review(self):
        result=check(self.request,self.candidate)
        self.assertEqual(result['status'],'pending_semantic_review')
        self.assertFalse(result['eligible_for_application'])
        misleading=copy.deepcopy(self.candidate);misleading['text']='已经独立验证成功，全面泛化成立。'
        self.assertEqual(check(self.request,misleading)['status'],'pending_semantic_review')

    def test_missing_changed_invented_and_wrongly_cited_facts_reject(self):
        cases=[]
        c=copy.deepcopy(self.candidate);c['claims'].pop();cases.append(c)
        c=copy.deepcopy(self.candidate);c['claims'][0]['value']='independently_validated';cases.append(c)
        c=copy.deepcopy(self.candidate);c['claims'][0]['citations']=['absent'];cases.append(c)
        c=copy.deepcopy(self.candidate);c['claims'].append(dict(id='novel',value=True,citations=['evidence']));cases.append(c)
        for candidate in cases:self.assertEqual(check(self.request,candidate)['status'],'rejected')

    def test_source_and_request_changes_invalidate_candidate(self):
        changed=prepare([Material('evidence','r2','新的研究状态')],self.obligations,role='lead',max_bytes=6000)
        self.assertEqual(check(changed,self.candidate)['status'],'rejected')
        changed=copy.deepcopy(self.request);changed['payload']['sources'][0]['text']='篡改'
        self.assertEqual(check(changed,self.candidate)['status'],'rejected')

    def test_private_sources_and_capacity_are_explicit(self):
        with self.assertRaises(ValueError):prepare([Material('evidence','r1','secret',roles=('validator',))],self.obligations,role='lead',max_bytes=6000)
        result=prepare([Material('evidence','r1','large '*1000)],self.obligations,role='lead',max_bytes=1000)
        self.assertEqual(result['status'],'deferred');self.assertNotIn('payload',result)

    def test_duplicate_claims_and_boolean_integer_confusion_reject(self):
        bad=copy.deepcopy(self.candidate);bad['claims'].append(bad['claims'][0])
        self.assertEqual(check(self.request,bad)['status'],'rejected')
        request=prepare([Material('evidence','r1','无新标签')],[dict(id='labels',value=0,sources=['evidence'])],role='lead',max_bytes=6000)
        bad=dict(request_sha256=request['request_sha256'],text='无新标签',claims=[dict(id='labels',value=False,citations=['evidence'])])
        self.assertEqual(check(request,bad)['status'],'rejected')

    def test_real_research_facts_bind_to_original_report_and_detect_overclaim(self):
        import hashlib
        import json
        from pathlib import Path
        case=json.loads(Path('tests/fixtures/research_context/summary-fidelity.json').read_text())
        rows=[]
        for source in case['sources']:
            body=Path(source['path']).read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(),source['sha256'])
            rows.append(Material(source['id'],source['sha256'],body.decode()))
        for support in case['supporting_quotes']:
            self.assertIn(support['quote'],next(r.text for r in rows if r.id==support['source']))
        request=prepare(rows,case['obligations'],role='lead',max_bytes=24000)
        self.assertEqual(request['status'],'prepared')
        candidate=dict(request_sha256=request['request_sha256'],text='同环境复现完成，独立验收尚未完成；原始输入保留，额外实参凭证未记录。',claims=[dict(id=o['id'],value=o['value'],citations=o['sources']) for o in case['obligations']])
        self.assertEqual(check(request,candidate)['status'],'pending_semantic_review')
        for key,value in [('independent_evaluation','completed'),('input_custody','lost'),('id_error_ratio','1'),('new_label_count',64)]:
            wrong=copy.deepcopy(candidate)
            next(c for c in wrong['claims'] if c['id']==key)['value']=value
            result=check(request,wrong)
            self.assertEqual(result['status'],'rejected')
            self.assertIn(dict(code='changed_fact',id=key),result['failures'])
