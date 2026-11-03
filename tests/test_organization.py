import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest

from asr_service.control import ControlService, ControlError
import test_control_service as fixtures


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ControlTests('test_authenticated_project_and_role_boundaries')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.s=self.fixture.service
        for name in ('organizer','lead','lead2','lead3','worker','worker2','outsider'):
            self.s.credentials[name]=dict(subject=name,role='researcher',projects=['p'])
        self.fixture.start();self.counter=0

    def change(self,kind,entity,doc,token='human-secret',revision=0,key=None):
        self.counter+=1
        return self.s.change_organization(token,'p','r',kind=kind,entity_id=entity,
            expected_revision=revision,idempotency_key=key or f'write-{self.counter}',document=doc)

    def setup_org(self,workers=1,leads=2):
        self.change('policy','capacity',dict(max_active_leads=leads,max_active_workers=workers))
        for name,role in [('organizer','organizer'),('lead','lead'),('lead2','lead'),('lead3','lead'),('worker','worker'),('worker2','worker')]:
            self.change('member',name,dict(role=role,enabled=True))

    @staticmethod
    def direction(owner='lead',status='active'):
        return dict(title='Researcher-chosen question',question='Which explanation fits the evidence?',owner=owner,status=status,
                    rationale='Chosen after reading client material',evidence_trial_ids=[])

    @staticmethod
    def task(assignee='worker',direction='d'):
        return dict(direction_id=direction,assignee=assignee,title='Check an explanation',instructions='Return counterevidence if found',
                    status='assigned',result='',evidence_trial_ids=[])

    def test_direction_topics_not_prescribed_and_lead_can_propose(self):
        self.setup_org();proposal=self.direction(status='proposed')
        first=self.change('direction','d',proposal,'lead',key='proposal')
        active=dict(proposal,status='active')
        self.change('direction','d',active,'organizer',revision=1)
        self.assertEqual(first,self.change('direction','d',proposal,'lead',key='proposal'))
        page=self.s.organization_records('organizer','p','r')
        self.assertEqual([x['document']['question'] for x in page['records'] if x['kind']=='direction'],[proposal['question']]*2)
        self.assertEqual(self.s.get_run('human-secret','p','r')['budget']['attempts']['spent'],0)
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.change('direction','evil',self.direction(),'worker')
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.change('member','outsider',dict(role='organizer',enabled=True),'organizer')
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.s.organization_records('outsider','p','r')

    def test_other_lead_cannot_take_over_proposal_or_rewrite_live_direction(self):
        self.setup_org();proposal=self.direction(status='proposed')
        self.change('direction','d',proposal,'lead')
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.change('direction','d',dict(proposal,owner='lead2'),'lead2',revision=1)
        self.change('direction','d',dict(proposal,status='active'),'organizer',revision=1)
        self.change('task','t',self.task(),'lead')
        with self.assertRaisesRegex(ControlError,'direction_has_open_tasks'):
            self.change('direction','d',dict(proposal,status='active',question='A different objective'),'organizer',revision=2)

    def test_capacity_defers_and_is_durable_without_pausing_research(self):
        self.setup_org(leads=1)
        self.change('direction','d',self.direction(),'organizer')
        with self.assertRaisesRegex(ControlError,'organization_capacity') as raised:
            self.change('direction','d2',self.direction('lead2'),'organizer')
        self.assertEqual(raised.exception.details['action'],'request_deferred')
        self.assertEqual(self.s.get_run('human-secret','p','r')['state'],'running')
        self.s=ControlService(self.s.path,credentials=self.s.credentials)
        with self.s._connect() as db:
            events=[json.loads(x[0]) for x in db.execute('SELECT record FROM asr_events')]
        self.assertTrue(any(e['type']=='organization_request_deferred' for e in events))
        self.change('direction','d',self.direction(status='paused'),'organizer',revision=1)
        self.change('direction','d2',self.direction('lead2'),'organizer')

    def test_unique_claim_and_no_live_task_reassignment(self):
        self.setup_org();self.change('direction','d',self.direction(),'organizer')
        task=self.task();self.change('task','t',task,'lead')
        started=dict(task,status='in_progress')
        args=dict(kind='task',entity_id='t',expected_revision=1,document=started)
        def claim(key):
            try:return self.s.change_organization('worker','p','r',idempotency_key=key,**args)
            except ControlError as error:return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(claim,['claim1','claim2']))
        self.assertEqual(sum(isinstance(x,dict) for x in results),1)
        self.assertIn('revision_conflict',results)
        with self.assertRaisesRegex(ControlError,'task_in_progress'):
            self.change('task','t',dict(started,assignee='worker2'),'lead',revision=2)
        with self.assertRaisesRegex(ControlError,'task_in_progress'):
            self.change('task','t',dict(started,instructions='Different question'),'worker',revision=2)
        with self.assertRaisesRegex(ControlError,'direction_has_open_tasks'):
            self.change('direction','d',self.direction(status='closed'),'organizer',revision=1)
        self.change('task','t',dict(started,status='completed',result='No supporting evidence found'),'worker',revision=2)
        with self.assertRaisesRegex(ControlError,'task_terminal'):
            self.change('task','t',task,'lead',revision=3)
        self.change('direction','d',self.direction(status='closed'),'organizer',revision=1)

    def test_worker_capacity_and_role_revision_are_checked(self):
        self.setup_org();self.change('direction','d',self.direction(),'organizer')
        a=self.task();b=self.task('worker2')
        self.change('task','a',a,'lead');self.change('task','b',b,'lead')
        self.change('task','a',dict(a,status='in_progress'),'worker',revision=1)
        with self.assertRaisesRegex(ControlError,'organization_capacity'):
            self.change('task','b',dict(b,status='in_progress'),'worker2',revision=1)
        with self.assertRaisesRegex(ControlError,'member_has_open_work'):
            self.change('member','worker',dict(role='worker',enabled=False),revision=1)
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.change('task','b',dict(b,status='completed',result='fabricated'),'worker',revision=1)

    def test_restart_pagination_and_targeted_immutable_messages(self):
        self.setup_org()
        self.change('message','m',dict(recipients=['lead2'],text='Please challenge this interpretation',evidence_trial_ids=[]),'lead')
        self.s=ControlService(self.s.path,credentials=self.s.credentials)
        records=[];after=0
        while True:
            page=self.s.organization_records('lead2','p','r',after=after,limit=2)
            records+=page['records'];after=page['next_after']
            if not page['has_more']:break
        self.assertEqual(len(records),8)
        with self.assertRaisesRegex(ControlError,'message_immutable'):
            self.change('message','m',dict(recipients=['lead2'],text='Rewrite history',evidence_trial_ids=[]),'lead',revision=1)
        with self.assertRaisesRegex(ControlError,'invalid_organization_page'):
            self.s.organization_records('lead','p','r',limit=501)

    def test_oversize_and_false_evidence_are_not_silently_accepted(self):
        self.setup_org()
        with self.assertRaisesRegex(ControlError,'organization_document_limit') as raised:
            self.change('message','big',dict(recipients=['lead'],text='x'*70000,evidence_trial_ids=[]),'organizer')
        self.assertEqual(raised.exception.details['limit'],65536)
        with self.assertRaisesRegex(ControlError,'organization_evidence_unavailable'):
            self.change('direction','d',dict(self.direction(),evidence_trial_ids=['not-a-trial']),'organizer')
        self.assertEqual(self.s.get_run('human-secret','p','r')['state'],'running')

    def test_capacity_check_is_atomic_and_completed_run_replays_only(self):
        self.setup_org(leads=1)
        def activate(item):
            entity,owner=item
            try:return self.s.change_organization('organizer','p','r',kind='direction',entity_id=entity,
                expected_revision=0,idempotency_key=entity,document=self.direction(owner))
            except ControlError as error:return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(activate,[('a','lead'),('b','lead2')]))
        self.assertEqual(sum(isinstance(x,dict) for x in results),1)
        self.assertIn('organization_capacity',results)
        winner=next(x for x in results if isinstance(x,dict))
        self.s.command('human-secret','p','r','finish',expected_revision=1,idempotency_key='finish')
        self.assertEqual(activate((winner['entity_id'],winner['document']['owner'])),winner)
        with self.assertRaisesRegex(ControlError,'organization_run_closed'):
            self.change('message','late',dict(recipients=['lead'],text='New action',evidence_trial_ids=[]),'organizer')

    def test_page_limit_rejection_is_logged_with_recovery(self):
        self.setup_org()
        with self.assertRaisesRegex(ControlError,'invalid_organization_page') as raised:
            self.s.organization_records('lead','p','r',limit=501)
        self.assertEqual(raised.exception.details['limit'],500)
        with self.s._connect() as db:
            events=[json.loads(x[0]) for x in db.execute('SELECT record FROM asr_events')]
        self.assertTrue(any(e.get('details',{}).get('dimension')=='organization_page_records' for e in events))

    def test_paused_run_keeps_discussion_but_defers_new_work(self):
        self.setup_org();self.change('direction','d',self.direction(),'organizer')
        task=self.task();self.change('task','t',task,'lead')
        self.s.command('human-secret','p','r','pause',expected_revision=1,idempotency_key='pause')
        with self.assertRaisesRegex(ControlError,'organization_work_paused'):
            self.change('task','t',dict(task,status='in_progress'),'worker',revision=1)
        self.change('message','m',dict(recipients=['lead'],text='Work paused; preserve evidence',evidence_trial_ids=[]),'worker')


if __name__=='__main__':unittest.main()
