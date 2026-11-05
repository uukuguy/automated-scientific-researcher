import json
from pathlib import Path
import tempfile
import unittest
from asr_service.control import ControlService,ControlError
from integrations.runtimes.capacity_policy import load_policy


class CapacityCloseoutTests(unittest.TestCase):
    def policy(self,root,**limits):
        value=load_policy();del value['sha256']
        for name,limit in limits.items():value['limits'][name]['value']=limit
        path=Path(root)/'capacity.json';path.write_text(json.dumps(value));return path

    def test_note_pages_use_default_max_and_durable_rejection(self):
        import test_note_artifact_sources as fixture
        case=fixture.NoteArtifactTests();case.setUp();self.addCleanup(case.doCleanups)
        path=self.policy(case.service.path.parent,source_page_default_characters=3,source_page_max_characters=7)
        case.service=ControlService(case.service.path,credentials=case.service.credentials,capacity_policy_path=path)
        note=case.call('save',text='引用',artifact_references=[case.ref])
        page=case.call('source_read',revision=note['revision'],artifact_reference=case.ref)
        self.assertEqual(page['text'],'def')
        self.assertEqual(len(case.call('source_read',revision=note['revision'],artifact_reference=case.ref,limit=7)['text']),7)
        before=case.service.get_run('human-secret','p','r')
        with self.assertRaisesRegex(ControlError,'invalid_note_source_page') as error:
            case.call('source_read',revision=note['revision'],artifact_reference=case.ref,limit=8)
        self.assertEqual(error.exception.details['max_characters'],7)
        self.assertEqual(before,case.service.get_run('human-secret','p','r'))
        with case.service._connect() as db:
            events=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_events')]
        self.assertTrue(any(e['type']=='source_page_deferred' and e['details']['max_characters']==7 for e in events))

    def test_conversation_pages_share_policy(self):
        import test_context_sources as fixture
        case=fixture.ContextSourcesTests();case.setUp();self.addCleanup(case.doCleanups);receipt=case.register()
        path=self.policy(case.s.path.parent,source_page_default_characters=3,source_page_max_characters=7)
        service=ControlService(case.s.path,credentials=case.s.credentials,capacity_policy_path=path)
        message=receipt['observation']['conversation']['body']['messages'][0]
        args=dict(source_registration='source',message_id=message['id'])
        self.assertEqual(service.read_context_source('lead','p','r',**args)['text'],message['text'][:3])
        with self.assertRaisesRegex(ControlError,'invalid_context_source_page') as error:
            service.read_context_source('lead','p','r',**args,limit=8)
        self.assertEqual(error.exception.details['max_characters'],7)

    def test_snapshot_custom_boundary_preserves_files_and_budget(self):
        import test_snapshot_limits as fixture
        case=fixture.SnapshotLimitTests();case.setUp();self.addCleanup(case.doCleanups)
        path=self.policy(case.service.path.parent,workspace_snapshot_bytes=10)
        service=ControlService(case.service.path,credentials=case.service.credentials,capacity_policy_path=path);case.bridge.service=service
        (case.work/'a').write_bytes(b'x'*10)
        self.assertIn('snapshot_sha256',case.bridge.call('snapshot',dict(paths=['a']),'equal'))
        (case.work/'b').write_bytes(b'x'*11);before=service.get_run('agent-secret','p','r')
        with self.assertRaises(ValueError) as error:case.bridge.call('snapshot',dict(paths=['b']),'over')
        self.assertEqual(error.exception.details['limit'],10);self.assertEqual(error.exception.details['requested'],11)
        self.assertEqual(error.exception.details['capacity_policy_sha256'],service.artifact_io_policy['sha256'])
        self.assertEqual(before['budget'],service.get_run('agent-secret','p','r')['budget'])
        self.assertTrue((case.work/'b').exists())

    def test_pi_skill_boundaries_and_policy_receipt(self):
        from integrations.runtimes.pi import PiRuntime,RuntimeFailure
        runtime=PiRuntime(model='test');skills=runtime.preflight_capabilities()['skills']
        count=len(skills);largest=max(len(s['content']) for s in skills);total=sum(len(s['content']) for s in skills)
        with tempfile.TemporaryDirectory() as root:
            path=self.policy(root,capability_skill_count=count,capability_skill_bytes=largest,capability_pack_bytes=total)
            self.assertEqual(len(PiRuntime(model='test',capacity_policy_path=path).preflight_capabilities()['skills']),count)
            for name,value in [('capability_skill_count',count-1),('capability_skill_bytes',largest-1),('capability_pack_bytes',total-1)]:
                if value<1:continue
                path=self.policy(root,**{name:value})
                if name=='capability_pack_bytes':
                    policy=json.loads(path.read_text());policy['limits']['capability_skill_bytes']['value']=min(largest,value);path.write_text(json.dumps(policy))
                with self.assertRaises(RuntimeFailure) as error:PiRuntime(model='test',capacity_policy_path=path).preflight_capabilities()
                self.assertEqual(error.exception.code,'capability_skill_capacity_exceeded')
                self.assertEqual(error.exception.details['kind'],name);self.assertTrue(error.exception.details['recoverable'])
            pack=runtime.preflight_capabilities()['pack'];pack['skills']=pack['skills']*2
            manifest=Path(root)/'capabilities.json';manifest.write_text(json.dumps(pack))
            path=self.policy(root,capability_skill_count=count)
            with self.assertRaises(RuntimeFailure) as error:PiRuntime(model='test',capacity_policy_path=path,capabilities_path=manifest).preflight_capabilities()
            self.assertEqual(error.exception.details['kind'],'capability_skill_count')

    def test_organization_page_and_document_limits_use_policy(self):
        import test_control_research_notes as fixture
        case=fixture.ControlResearchNotesTests();case.setUp();self.addCleanup(case.doCleanups)
        path=self.policy(case.s.path.parent,organization_page_default_records=1,organization_page_max_records=2,organization_document_bytes=64)
        service=ControlService(case.s.path,credentials=case.s.credentials,capacity_policy_path=path)
        self.assertEqual(len(service.organization_records('lead','p','r')['records']),1)
        self.assertEqual(len(service.organization_records('lead','p','r',limit=2)['records']),2)
        with self.assertRaises(ControlError) as error:service.organization_records('lead','p','r',limit=3)
        self.assertEqual(error.exception.details['limit'],2)
        before=service.get_run('human-secret','p','r')
        with self.assertRaisesRegex(ControlError,'organization_document_limit') as error:
            service.change_organization('lead','p','r',kind='direction',entity_id='new',expected_revision=0,idempotency_key='oversize',document=case.org.direction())
        self.assertEqual(error.exception.details['limit'],64)
        after=service.get_run('human-secret','p','r');self.assertEqual(before['budget'],after['budget']);self.assertEqual(before['state'],after['state'])

    def test_organization_document_exact_boundary_is_accepted(self):
        import test_control_research_notes as fixture
        from asr_service.contracts import encoded
        case=fixture.ControlResearchNotesTests();case.setUp();self.addCleanup(case.doCleanups)
        document=dict(role='worker',enabled=False)
        path=self.policy(case.s.path.parent,organization_document_bytes=len(encoded(document).encode()))
        service=ControlService(case.s.path,credentials=case.s.credentials,capacity_policy_path=path)
        result=service.change_organization('human-secret','p','r',kind='member',entity_id='disabled-new',expected_revision=0,idempotency_key='equal',document=document)
        self.assertEqual(result['document'],document)
