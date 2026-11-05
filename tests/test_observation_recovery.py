import hashlib
import json
from pathlib import Path
import unittest
import test_context_cursor_binding as fixture


class ObservationRecoveryTests(unittest.TestCase):
    setUp=fixture.ContextCursorBindingTests.setUp
    bind=fixture.ContextCursorBindingTests.bind
    event=fixture.ContextCursorBindingTests.event

    def source(self,events,tail=b''):
        path=self.root.parent/'events.jsonl'
        rows=[dict(schema='asr-recorded-runtime-event/1',sequence=i+1,event=event) for i,event in enumerate(events)]
        path.write_bytes((''.join(json.dumps(row)+'\n' for row in rows)).encode()+tail)
        return path

    def recover(self,path,name='recovery',**overrides):
        from integrations.runtimes.observation_recovery import recover
        args=dict(identity=self.ids,expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),destination=self.root.parent/name)
        args.update(overrides)
        return recover(self.s,'human-secret','p','r',path,**args)

    def exit(self):
        self.s.abort_runtime_prelaunch('human-secret','p','r',**self.ids,reason='no model fixture',actual_walltime_ms=1)

    def test_persisted_prefix_replays_idempotently_without_new_permission_or_budget(self):
        self.bind();self.exit();path=self.source([self.event('missed')])
        before=self.s.get_run('human-secret','p','r')['budget']
        first=self.recover(path)
        with self.s._connect() as db:first_count=db.execute('SELECT COUNT(*) FROM asr_requests').fetchone()[0]
        second=self.recover(path,'recovery-2')
        with self.s._connect() as db:self.assertEqual(first_count,db.execute('SELECT COUNT(*) FROM asr_requests').fetchone()[0])
        self.assertEqual(first['status'],'reconciled')
        self.assertEqual(first['observations'],1)
        self.assertEqual(first['outcomes'],{'deferred':1})
        self.assertFalse(first['installation_authorized'])
        self.assertTrue(second['historical_only'])
        self.assertEqual(before,self.s.get_run('human-secret','p','r')['budget'])
        self.assertEqual(path.read_bytes(),(self.root.parent/'recovery/source.jsonl').read_bytes())

    def test_partial_tail_is_retained_and_reported_without_guessing(self):
        self.bind();self.exit();path=self.source([self.event('missed')],b'{"partial":')
        result=self.recover(path)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['observations'],1)
        self.assertEqual(result['gap']['reason'],'incomplete_tail')
        self.assertEqual(path.read_bytes(),(self.root.parent/'recovery/source.jsonl').read_bytes())

    def test_active_or_fenced_session_is_not_recovered_as_current(self):
        self.bind();path=self.source([self.event()])
        self.assertEqual(self.recover(path)['reason'],'execution_reconciliation_required')
        self.exit()
        result=self.recover(path,'fenced',identity=dict(self.ids,epoch=999))
        self.assertEqual(result['reason'],'stale_runtime_epoch')

    def test_bad_hash_or_malformed_middle_has_no_observation_side_effects(self):
        self.bind();self.exit();path=self.source([self.event()])
        self.assertEqual(self.recover(path,expected_sha256='0'*64)['reason'],'source_hash_mismatch')
        path.write_bytes(b'{"broken":\n'+path.read_bytes())
        self.assertEqual(self.recover(path,'bad-lines')['reason'],'invalid_record')
        with self.s._connect() as db:
            events=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_events')]
        self.assertFalse(any(e['type'].startswith('context_cursor_') for e in events))

    def test_partial_tail_after_non_cursor_or_without_complete_record_is_retained(self):
        self.bind();self.exit()
        for index,events in enumerate(([],[dict(type='agent_end')])):
            path=self.source(events,b'{"partial":')
            result=self.recover(path,'partial-'+str(index))
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['observations'],0)

    def test_configured_snapshot_line_and_record_boundaries_defer_without_truncation(self):
        from integrations.runtimes.capacity_policy import load_policy
        self.bind();self.exit();path=self.source([self.event('one'),self.event('two')])
        original=path.read_bytes();lines=original.splitlines(keepends=True)
        cases=[('observation_recovery_snapshot_bytes',len(original)-1,'snapshot_capacity'),
               ('observation_recovery_record_bytes',max(map(len,lines))-1,'record_capacity'),
               ('observation_recovery_records',1,'record_count_capacity')]
        for index,(name,value,reason) in enumerate(cases):
            policy=load_policy();del policy['sha256'];policy['limits'][name]['value']=value
            config=self.root.parent/('config-'+str(index)+'.json');config.write_text(json.dumps(policy))
            result=self.recover(path,'boundary-'+str(index),capacity_policy_path=config)
            self.assertEqual(result['reason'],reason)
            self.assertEqual(result['observations'],0)
            self.assertEqual(path.read_bytes(),original)
        policy=load_policy();del policy['sha256']
        for name,value in [('observation_recovery_snapshot_bytes',len(original)),('observation_recovery_record_bytes',max(map(len,lines))),('observation_recovery_records',2)]:policy['limits'][name]['value']=value
        config=self.root.parent/'exact-boundaries.json';config.write_text(json.dumps(policy))
        self.assertEqual(self.recover(path,'exact-boundaries',capacity_policy_path=config)['observations'],2)

    def test_actual_killed_recorder_recovers_flushed_prefix_and_retains_active_marker(self):
        import subprocess,sys,select
        self.bind();self.exit();path=self.root.parent/'killed-events.jsonl'
        code='''import json,sys,threading
from integrations.runtimes.async_events import AsyncEventRecorder
def stuck_sync(fd):
 print('prefix-ready',flush=True)
 threading.Event().wait()
r=AsyncEventRecorder(sys.argv[1],sync=stuck_sync)
r(json.loads(sys.argv[2]))
r.close(timeout=60)
'''
        process=subprocess.Popen([sys.executable,'-c',code,str(path),json.dumps(self.event('crash-prefix'))],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            self.assertTrue(select.select([process.stdout],[],[],5)[0])
            self.assertEqual(process.stdout.readline().strip(),'prefix-ready')
            process.kill();process.wait(timeout=5)
            self.assertLess(process.returncode,0)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=5)
            process.stdout.close();process.stderr.close()
        self.assertEqual(json.loads(path.with_suffix('.recording.json').read_text())['status'],'recording')
        self.assertEqual(self.recover(path,'actual-crash')['observations'],1)

    def test_resume_helper_uses_original_step_identity_and_keeps_old_result(self):
        from integrations.runtimes.observation_recovery import recover_steps
        self.bind();self.exit()
        step=self.root.parent/'steps/000-lead';step.mkdir(parents=True)
        source=self.source([self.event('pending-step')]);(step/'events.jsonl').write_bytes(source.read_bytes())
        old=dict(status='settled',runtime_claim=self.ids,context_observation_drain=dict(drained=False,pending=1))
        result_path=step/'result.json';result_path.write_text(json.dumps(old));before=result_path.read_bytes()
        report=recover_steps(self.s,'human-secret','p','r',step.parent,destination=self.root.parent/'resume-observations')
        self.assertEqual(report['steps'][0]['recovery']['observations'],1)
        self.assertEqual(result_path.read_bytes(),before)
        self.assertTrue((self.root.parent/'resume-observations/index.json').is_file())

    def test_raw_notification_alone_can_recover_the_recorded_cursor(self):
        self.bind();self.exit()
        notification=dict(type='extension_ui_request',method='notify',message='ASR_CONTEXT_EVENT '+json.dumps(self.event('raw-prefix')))
        result=self.recover(self.source([notification]))
        self.assertEqual(result['observations'],1)
