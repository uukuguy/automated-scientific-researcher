from pathlib import Path
import unittest
import test_study_admission as fixtures
from integrations.aar.bridge import ResearchBridge


class SnapshotLimitTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.StudyAdmissionTests('test_shared_ledger_reservation_and_replay')
        fixture.setUp();self.addCleanup(fixture.doCleanups);fixture.configure()
        self.service=fixture.service
        root=Path(fixture.tmp.name);self.work=root/'workspace';self.work.mkdir(exist_ok=True)
        self.bridge=ResearchBridge(self.service,project='p',run='r',researcher_token='agent-secret',
            supervisor_token='human-secret',workspace=self.work,snapshots=root/'snapshots',capability_profile='ood-study-development/1')

    def test_actual_sized_utility_report_fits_default_and_is_not_truncated(self):
        body=b'x'*(2300*1024);(self.work/'utility.json').write_bytes(body)
        result=self.bridge.call('snapshot',{'paths':['utility.json']},'utility')
        saved=self.bridge.snapshots/result['snapshot_sha256']/'files/utility.json'
        self.assertEqual(saved.read_bytes(),body)

    def test_oversize_has_durable_diagnostics_without_pausing_or_deleting(self):
        size=16*1024*1024+1
        with (self.work/'large.json').open('wb') as stream:stream.truncate(size)
        before=self.service.get_run('agent-secret','p','r')
        with self.assertRaises(ValueError) as caught:self.bridge.call('snapshot',{'paths':['large.json']},'large')
        error=caught.exception
        self.assertEqual(error.code,'snapshot_too_large')
        self.assertEqual(error.details['limit'],16*1024*1024)
        self.assertEqual(error.details['requested'],size)
        self.assertTrue(error.details['recoverable']);self.assertIn('block_id',error.details)
        self.assertEqual((self.work/'large.json').stat().st_size,size)
        after=self.service.get_run('agent-secret','p','r')
        self.assertEqual(after['state'],before['state']);self.assertEqual(after['budget'],before['budget'])
        record=after['budget_blocks'][-1]
        self.assertEqual(record['request_key'],'large');self.assertEqual(record['action'],'request_deferred')
        self.assertEqual(record['budget']['requested'],size)
        self.assertFalse(self.bridge.snapshots.exists())
