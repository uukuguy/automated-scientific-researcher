import unittest
from asr_service.control import ControlError
import test_organization as fixtures


class ControlResearchNotesTests(unittest.TestCase):
    def setUp(self):
        self.org=fixtures.OrganizationTests();self.org.setUp();self.addCleanup(self.org.doCleanups)
        self.org.setup_org();self.s=self.org.s
        self.source=self.org.change('direction','d',self.org.direction(status='proposed'),'lead')

    def call(self, operation, token='lead', key='key', **kw):
        return self.s.research_note(token,'p','r',operation=operation,idempotency_key=key,**kw)

    def save(self,key='draft'):
        return self.call('save',key=key,text='方向尚待验证，保留反证。',source_sequences=[self.source['seq']])

    def test_explicit_adoption_replay_and_restoration(self):
        draft=self.save();self.assertIsNone(self.call('read')['accepted_revision'])
        result=self.call('adopt',key='adopt',revision=draft['revision'],expected_note=None)
        self.assertEqual(result,self.call('adopt',key='adopt',revision=draft['revision'],expected_note=None))
        read=self.call('read');self.assertEqual(read['accepted_revision'],draft['revision'])
        self.assertEqual(read['restoration']['status'],'ready')
        self.assertEqual(self.s.get_run('human-secret','p','r')['budget']['attempts']['spent'],0)

    def test_member_cannot_read_or_adopt_another_members_note(self):
        draft=self.save()
        for operation in ['read','adopt']:
            with self.assertRaises(ControlError):self.call(operation,token='lead2',revision=draft['revision'],expected_note=None)
        with self.assertRaisesRegex(ControlError,'forbidden'):self.call('save',token='outsider',text='x',source_sequences=[])

    def test_source_revision_change_defers_restore_and_blocks_adoption(self):
        draft=self.save()
        self.org.change('direction','d',dict(self.org.direction(status='proposed'),question='新问题'),'lead',revision=1)
        with self.assertRaisesRegex(ControlError,'note_sources_changed'):
            self.call('adopt',revision=draft['revision'],expected_note=None)
        preview=self.call('read',revision=draft['revision'])
        self.assertEqual(preview['restoration']['status'],'deferred')

    def test_competing_drafts_cannot_overwrite_new_head(self):
        first=self.save()
        second=self.call('save',key='second',text='另一份草稿',source_sequences=[self.source['seq']])
        self.call('adopt',key='first-adopt',revision=first['revision'],expected_note=None)
        with self.assertRaisesRegex(ControlError,'revision_conflict'):
            self.call('adopt',key='second-adopt',revision=second['revision'],expected_note=None)
        self.assertEqual(self.call('read')['accepted_revision'],first['revision'])

    def test_bridge_tool_uses_authenticated_owner_and_survives_service_reopen(self):
        import tempfile
        from pathlib import Path
        from integrations.aar.bridge import ResearchBridge
        from asr_service.control import ControlService
        with tempfile.TemporaryDirectory() as directory:
            bridge=ResearchBridge(self.s,project='p',run='r',researcher_token='lead',supervisor_token='supervisor-secret',
                workspace=Path(directory),snapshots=Path(directory)/'snapshots',capability_profile='research-organization/1')
            restricted=ResearchBridge(self.s,project='p',run='r',researcher_token='lead',supervisor_token='supervisor-secret',
                workspace=Path(directory),snapshots=Path(directory)/'snapshots')
            with self.assertRaisesRegex(ValueError,'unsupported_bridge_operation'):
                restricted.call('research_note',dict(operation='read'),'denied')
            draft=bridge.call('research_note',dict(operation='save',text='由正式工具保存',source_sequences=[self.source['seq']]),'bridge-save')
            bridge.call('research_note',dict(operation='adopt',revision=draft['revision'],expected_note=None),'bridge-adopt')
            reopened=ControlService(self.s.path,credentials=self.s.credentials)
            result=reopened.research_note('lead','p','r',operation='read',idempotency_key='read')
            self.assertEqual(result['accepted_revision'],draft['revision'])
            self.assertEqual(result['restoration']['material']['text'],'由正式工具保存')

    def test_old_source_cannot_be_silently_bound_to_new_version(self):
        self.org.change('direction','d',dict(self.org.direction(status='proposed'),question='新问题'),'lead',revision=1)
        with self.assertRaisesRegex(ControlError,'note_source_not_current'):self.save()
        with self.s._connect() as db:
            import json
            events=[json.loads(r[0]) for r in db.execute('select record from asr_events')]
        self.assertTrue(any(e['type']=='research_note_deferred' and e['reason']=='note_source_not_current' for e in events))

    def test_control_change_invalidates_prior_draft(self):
        draft=self.save()
        state=self.s.get_run('human-secret','p','r')
        self.s.command('human-secret','p','r','pause',expected_revision=state['control_revision'],idempotency_key='pause')
        with self.assertRaisesRegex(ControlError,'note_sources_changed'):
            self.call('adopt',revision=draft['revision'],expected_note=None)
