import json
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request

import test_organization as fixtures
from asr_service.http import make_server
from integrations.aar.bridge import ResearchBridge
from integrations.runtimes.pi import PiRuntime


class OrganizationTransportTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.OrganizationTests('test_direction_topics_not_prescribed_and_lead_can_propose')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.setup_org()

    def test_authenticated_http_revision_and_deferred_capacity(self):
        server=make_server(self.f.s,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url=f'http://127.0.0.1:{server.server_port}/v1/projects/p/runs/r/organization'
        body=dict(kind='direction',entity_id='d',expected_revision=0,idempotency_key='http-direction',document=self.f.direction())
        def request(token,body=None,suffix=''):
            req=urllib.request.Request(url+suffix,data=json.dumps(body).encode() if body else None,
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            with urllib.request.urlopen(req) as response:return json.load(response)
        result=request('organizer',body);self.assertEqual(result['revision'],1)
        page=request('lead',suffix='?after=0&limit=2');self.assertTrue(page['has_more'])
        with self.assertRaises(urllib.error.HTTPError) as raised:request('outsider')
        self.assertEqual(raised.exception.code,403)
        with self.assertRaises(urllib.error.HTTPError) as raised:request('organizer',dict(body,idempotency_key='new-key'))
        self.assertEqual(raised.exception.code,409)

    def test_explicit_bridge_profile_does_not_grant_roles_or_experiments(self):
        root=Path(self.f.fixture.tmp.name)
        def bridge(token):return ResearchBridge(self.f.s,project='p',run='r',researcher_token=token,
            supervisor_token='human-secret',workspace=root/'workspace',snapshots=root/'snapshots',
            capability_profile='research-organization/1')
        b=bridge('organizer')
        state=b.call('state',{},'read-effective-state')
        self.assertIn('budget',state['run'])
        self.assertNotIn('trials',state['run'])
        with self.assertRaisesRegex(ValueError,'forbidden'):bridge('outsider').call('state',{},'no-membership')
        args=dict(kind='direction',entity_id='d',expected_revision=0,document=self.f.direction())
        result=b.call('organization_change',args,'bridge-direction')
        self.assertEqual(result['author'],'organizer')
        self.assertTrue(b.call('organization_records',dict(limit=1),'page')['has_more'])
        with self.assertRaisesRegex(ValueError,'forbidden'):
            bridge('worker').call('organization_change',dict(args,entity_id='other'),'spoof')
        with self.assertRaisesRegex(ValueError,'unsupported_bridge_operation'):
            b.call('submit_study',{},'no-compute')
        pack=PiRuntime(model='gpt-6.1-sol',capabilities_path=Path('integrations/runtimes/organization-capabilities.json')).preflight_capabilities()
        self.assertEqual(pack['pack']['id'],'research-organization/1')


if __name__=='__main__':unittest.main()
