import unittest
from integrations.runtimes.context_maintenance import source_obligations, select_cut


class MaintenanceInputsTests(unittest.TestCase):
    def test_source_inventory_does_not_invent_scientific_facts(self):
        request=source_obligations([dict(id='conversation:a',sha256='a'*64,text='负结果')])
        self.assertEqual(request,[dict(id='source:conversation:a',value='a'*64,sources=['conversation:a'])])
        with self.assertRaisesRegex(ValueError,'sources_required'):source_obligations([])

    def test_cut_keeps_whole_last_interaction_group(self):
        observed=dict(conversation=dict(groups=[dict(ids=['u']),dict(ids=['a','t','r']),dict(ids=['b'])]),
                      witness=dict(source_mapping=[dict(message_id=x,native_entry_id='native-'+x) for x in ['u','a','t','r','b']]))
        self.assertEqual(select_cut(observed),'native-b')
        observed['conversation']['groups']=observed['conversation']['groups'][:1]
        with self.assertRaisesRegex(ValueError,'summarizable_prefix_required'):select_cut(observed)


class MaintenanceGateTests(unittest.TestCase):
    def test_control_defers_only_next_turn_and_keeps_running_budget(self):
        import test_recording_backpressure as fixture
        f=fixture.RecordingBackpressureTests();f.setUp();self.addCleanup(f.doCleanups)
        f.bind();f.launch();bridge=f.bridge()
        before=f.s.get_run('human-secret','p','r')['budget']
        bridge.context_maintenance_request=lambda:dict(recommendation='prepare_context_review',measurement='estimate',warning=True,
            runtime_session_id=f.claim['session_id'],capacity_policy_sha256='a'*64)
        result=bridge.call('permit',dict(kind='turn'),'maintenance')
        self.assertEqual(result['reason'],'context_maintenance_required')
        self.assertEqual(result,bridge.call('permit',dict(kind='turn'),'maintenance'))
        state=f.s.get_run('human-secret','p','r')
        self.assertEqual(state['state'],'running');self.assertEqual(before,state['budget'])
        self.assertIn('activity_id',bridge.call('permit',dict(kind='tool_execution'),'finish-tool'))
        self.assertFalse(result['request_capacity_verified'])

    def test_owner_continues_same_native_identity_without_replaying_prompt(self):
        from unittest.mock import Mock,patch
        from integrations.runtimes.context_maintenance import run_with_maintenance
        original=Mock(compact_before_prompt=False)
        bridge=Mock(context_installation_id=None)
        maintenance=Mock();maintenance.prepare.return_value=dict(status='staged',stage_id='stage')
        first=dict(status='context_maintenance_required',runtime_claim=dict(session_id='old'))
        last=dict(status='settled',context_installation_verified=True)
        with patch('integrations.runtimes.context_maintenance.run_session',side_effect=[first,last]) as execute:
            result=run_with_maintenance(original,bridge,maintenance=maintenance,native_session_id='same',prompt='original research instruction')
        self.assertEqual(result['status'],'settled');self.assertEqual(result['context_maintenance_attempts'],[first])
        self.assertEqual(execute.call_args_list[1].kwargs['native_session_id'],'same')
        self.assertNotEqual(execute.call_args_list[1].kwargs['prompt'],'original research instruction')
        self.assertTrue(execute.call_args_list[1].args[0].compact_before_prompt)
        self.assertIsNone(bridge.context_installation_id)

    def test_deferred_maintenance_never_dispatches_continuation(self):
        from unittest.mock import Mock,patch
        from integrations.runtimes.context_maintenance import run_with_maintenance
        bridge=Mock(context_installation_id=None)
        bridge.service.get_run.return_value=dict(state='running',control_revision=1)
        maintenance=Mock();maintenance.prepare.return_value=dict(status='deferred',reason='rejected')
        with patch('integrations.runtimes.context_maintenance.run_session',return_value=dict(status='context_maintenance_required',runtime_claim=dict(session_id='old'))) as execute:
            result=run_with_maintenance(Mock(),bridge,maintenance=maintenance,prompt='original')
        self.assertEqual(execute.call_count,1)
        self.assertEqual(result['status'],'context_maintenance_deferred')
        bridge.service.defer_context_maintenance.assert_called_once()


class MaintenancePipelineTests(unittest.TestCase):
    def setUp(self):
        import json
        import test_context_cursor_binding as fixture
        from integrations.runtimes.context_maintenance import ContextMaintenance
        from integrations.runtimes.pi import PiRuntime,Limits
        from integrations.aar.bridge import ResearchBridge
        self.fixture=fixture.ContextCursorBindingTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.s=f.s;self.base=f.base;self.path=f.path
        self.path.write_text(self.path.read_text().replace('negative evidence','negative evidence '*300))
        draft=f.base.save();f.base.call('adopt',key='adopt-maintenance',revision=draft['revision'],expected_note=None)
        with self.path.open('a') as stream:stream.write(json.dumps(dict(type='message',id='b',parentId='a',message=dict(role='assistant',content=[dict(type='text',text='未完成任务，保留负结果。')],stopReason='stop')))+'\n')
        f.bind();f.launch();f.process.terminate();f.process.wait()
        self.s.release_runtime('human-secret','p','r',**f.ids,execution_exited=True,actual_walltime_ms=100)
        self.previous=dict(runtime_claim=f.claim,recovery=dict(native_session_file=str(self.path),pending_tools=[]))
        def bridge(subject):return ResearchBridge(self.s,project='p',run='r',researcher_token=subject,supervisor_token='human-secret',workspace=self.path.parent/'work',snapshots=self.path.parent/'snapshots',capability_profile='research-organization/1')
        self.engine=ContextMaintenance(subject='lead',reviewer_subject='lead2',runtime_factory=lambda subject:PiRuntime(model='test'),
            bridge_factory=bridge,config_dir=self.path.parent/'private',evidence_dir=self.path.parent/'maintenance',limits=Limits(60,10,10))
        self.calls=[];self.reject=False;self.mutate=False
        self.engine._call=self.model_call

    def model_call(self, work, phase, subject, request):
        import json
        import test_context_admission as fixture
        session=fixture.ContextAdmissionTests.session(self,subject,'maintenance-'+phase)
        self.calls.append((phase,session))
        if phase=='summary':
            value=dict(request_sha256=request['request_sha256'],text='未完成任务。必须保留负结果，原始研究问题与证据限制不变。',
                claims=[dict(id=r['id'],value=r['value'],citations=r['sources']) for r in request['payload']['obligations']])
        else:
            source=request['payload']['original']['payload']['sources'][0]
            value=dict(review_sha256=request['review_sha256'],verdict='reject' if self.reject else 'accept',explanation='原文核对。',issues=['遗漏'] if self.reject else [],source_quotes=[dict(source=source['id'],quote=source['text'])])
            if self.mutate:self.path.write_text(self.path.read_text().replace('negative evidence','changed evidence'))
        return dict(status='settled',runtime_claim=dict(session_id=session),assistant_messages=[dict(content=[dict(type='text',text=json.dumps(value))])])

    def test_actual_control_stages_from_two_exited_sessions_and_sdk_can_install(self):
        import json,subprocess,shutil
        import test_context_installation_service as fixture
        result=self.engine.prepare(self.previous)
        self.assertEqual(result['status'],'staged',result)
        self.assertEqual([r[0] for r in self.calls],['summary','review'])
        self.assertNotEqual(self.calls[0][1],self.calls[1][1])
        ids,cursor=fixture.InstallationServiceTests.live(self)
        ticket=self.s.authorize_context_installation('human-secret','p','r',**ids,stage_id=result['stage_id'],observation=cursor,tokens_before=1000)['ticket']
        from pathlib import Path
        index=Path(shutil.which('pi')).resolve().parents[1]/'index.js'
        code=f'import {{SessionManager}} from {json.dumps(index.as_uri())};let t="";for await(const p of process.stdin)t+=p;const d=JSON.parse(t),m=SessionManager.open(d.path),c=d.compaction;console.log(JSON.stringify(m.appendCompaction(c.summary,c.firstKeptEntryId,c.tokensBefore,c.details,true)));'
        output=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(dict(path=str(self.path),compaction=ticket['compaction'])),text=True,capture_output=True,timeout=10)
        self.assertEqual(output.returncode,0,output.stderr)
        receipt=self.s.complete_context_installation('human-secret','p','r',**ids,boundary_id='boundary',ticket_id=ticket['ticket_id'],entry_id=json.loads(output.stdout),idempotency_key='maintenance-complete')
        self.assertEqual(receipt['status'],'verified',receipt)
        with self.assertRaises(FileExistsError):self.engine.prepare(self.previous)
        self.assertEqual(len(self.calls),2)

    def test_rejected_review_retains_source_and_has_no_staged_installation(self):
        self.reject=True;original=self.path.read_bytes()
        result=self.engine.prepare(self.previous)
        self.assertEqual(result['status'],'deferred',result)
        self.assertEqual(self.path.read_bytes(),original)
        self.assertTrue(list(self.engine.evidence_dir.rglob('deferred.json')))
        self.assertFalse(list(self.engine.evidence_dir.rglob('staged.json')))

    def test_changed_source_after_model_cost_prevents_installation(self):
        self.mutate=True
        result=self.engine.prepare(self.previous)
        self.assertEqual(result['status'],'deferred',result)
        self.assertEqual(len(self.calls),2)
        self.assertFalse(list(self.engine.evidence_dir.rglob('staged.json')))


class MaintenanceNativeTests(unittest.TestCase):
    def test_native_yield_blocks_provider_and_maintenance_mode_blocks_tools(self):
        import json,os,subprocess,time
        from pathlib import Path
        module=Path('integrations/runtimes/asr-extension.mjs').resolve().as_uri()
        code=f'''import extension from {json.dumps(module)};
const handlers={{}},events=[];let requests=0,finished=false;
globalThis.fetch=async()=>{{requests++;return {{ok:true,json:async()=>({{status:'deferred',reason:'context_maintenance_required'}})}}}};
extension({{on:(k,v)=>handlers[k]=v,registerTool:()=>{{}},appendEntry:()=>{{}}}});
const ctx={{abort:()=>{{}},ui:{{notify:text=>events.push(text)}}}};
handlers.before_provider_request({{}},ctx).then(()=>finished=true);
await new Promise(r=>setTimeout(r,20));
const tool=await handlers.tool_call({{toolName:'write',input:{{path:'x'}}}},ctx);
console.log(JSON.stringify({{finished,requests,events,tool}}));process.exit(0);'''
        env=dict(os.environ,ASR_MAINTENANCE_ONLY='1',ASR_MAX_TURNS='10',ASR_MAX_TOOLS='10',ASR_DEADLINE_MS=str(int((time.time()+30)*1000)))
        output=subprocess.run(['node','--input-type=module','-e',code],env=env,text=True,capture_output=True,timeout=5)
        self.assertEqual(output.returncode,0,output.stderr)
        result=json.loads(output.stdout)
        self.assertFalse(result['finished']);self.assertEqual(result['requests'],1)
        self.assertTrue(result['tool']['block']);self.assertIn('asr_context_maintenance',result['events'][0])

    def test_runtime_records_exit_without_claiming_context_installed(self):
        import json,tempfile
        from pathlib import Path
        import test_runtimes
        from integrations.runtimes.pi import PiRuntime,Limits
        event=dict(type='asr_context_maintenance',status='deferred',reason='context_maintenance_required')
        raw=dict(type='extension_ui_request',method='notify',message='ASR_CONTEXT_EVENT '+json.dumps(event))
        with tempfile.TemporaryDirectory() as directory:
            executable=test_runtimes.RuntimeTests().fake(directory,[raw])
            result=PiRuntime(executable=executable,model='test').run(workspace=Path(directory),config_dir=Path(directory),session_id='native',prompt='no model',limits=Limits(3,2,2),bridge_url='http://localhost:1',bridge_token='fixture')
        self.assertEqual(result['status'],'context_maintenance_required')
        self.assertEqual(result['context_maintenance_receipt'],event)
        self.assertIsNotNone(result['exit_code']);self.assertFalse(result['context_installation_verified'])


class MaintenanceRecoveryTests(unittest.TestCase):
    setUp=MaintenancePipelineTests.setUp
    model_call=MaintenancePipelineTests.model_call

    def test_supervisor_defer_is_durable_and_cannot_resume_or_discard_cost(self):
        self.s.credentials['supervisor-test']=dict(subject='supervisor',role='supervisor',projects=['p'])
        before=self.s.get_run('human-secret','p','r')['budget']
        args=dict(session_id=self.previous['runtime_claim']['session_id'],reason='context_note_sources_changed',idempotency_key='maintenance-pause')
        receipt=self.s.defer_context_maintenance('supervisor-test','p','r',**args)
        self.assertEqual(receipt['state'],'paused')
        self.assertEqual(receipt,self.s.defer_context_maintenance('supervisor-test','p','r',**args))
        self.assertEqual(before,self.s.get_run('human-secret','p','r')['budget'])
        from asr_service.control import ControlError
        with self.assertRaisesRegex(ControlError,'forbidden'):
            self.s.command('supervisor-test','p','r','resume',expected_revision=receipt['control_revision'],idempotency_key='forbidden-resume')

    def test_nonshrinking_candidate_is_recorded_but_never_installed(self):
        import json
        original=self.engine._call
        def model(work,phase,subject,request):
            result=original(work,phase,subject,request)
            if phase=='summary':
                value=json.loads(result['assistant_messages'][0]['content'][0]['text']);value['text']='保留原文。'*20000
                result['assistant_messages'][0]['content'][0]['text']=json.dumps(value)
            return result
        self.engine._call=model
        result=self.engine.prepare(self.previous)
        self.assertEqual(result['detail']['reason'],'context_replacement_not_smaller')
        self.assertFalse(list(self.engine.evidence_dir.rglob('staged.json')))

    def test_host_sdk_installer_uses_live_owned_process_and_no_model_turns(self):
        from pathlib import Path
        from integrations.runtimes.pi import PiRuntime,Limits
        from integrations.runtimes.context_installer import install
        stage=self.engine.prepare(self.previous)
        self.assertEqual(stage['status'],'staged',stage)
        identity=self.base.org.fixture.runtime_identity()
        runtime=PiRuntime(model=identity['model'],capabilities_path=Path('integrations/runtimes/organization-capabilities.json'))
        runtime.provider=identity['provider']
        before=self.s.get_run('human-secret','p','r')['budget']
        receipt=install(runtime,self.engine.bridge_factory('lead'),stage=stage,source=dict(self.previous,native_session_id='native'),
            limits=Limits(10,10,10),evidence_dir=self.path.parent/'host-installer')
        self.assertEqual(receipt['status'],'verified',receipt)
        after=self.s.get_run('human-secret','p','r')
        self.assertEqual(before['turns'],after['budget']['turns'])
        self.assertEqual(before['tool_executions'],after['budget']['tool_executions'])
        self.assertTrue(all(x['state']=='exited' for x in after['runtime_sessions']))

    def test_installer_record_cap_preserves_prefix_and_budget_without_installing(self):
        import json
        from pathlib import Path
        from integrations.runtimes.pi import PiRuntime,Limits
        from integrations.runtimes.capacity_policy import load_policy
        from integrations.runtimes.context_installer import install
        stage=self.engine.prepare(self.previous);original=self.path.read_bytes()
        identity=self.base.org.fixture.runtime_identity()
        policy=load_policy();policy.pop('sha256');policy['limits']['pi_message_bytes']['value']=64
        policy_path=self.path.parent/'test-policy.json';policy_path.write_text(json.dumps(policy))
        runtime=PiRuntime(model=identity['model'],capabilities_path=Path('integrations/runtimes/organization-capabilities.json'),capacity_policy_path=policy_path)
        runtime.provider=identity['provider'];directory=self.path.parent/'small-record-installer'
        with self.assertRaisesRegex(ValueError,'context_installer_record_capacity'):
            install(runtime,self.engine.bridge_factory('lead'),stage=stage,source=dict(self.previous,native_session_id='native'),limits=Limits(10,10,10),evidence_dir=directory)
        failed=json.loads((directory/'failure.json').read_text())
        self.assertEqual(failed['configured'],64);self.assertGreater(failed['observed'],64)
        self.assertEqual((directory/'protocol-prefix.bin').stat().st_size,failed['observed'])
        self.assertEqual(self.path.read_bytes(),original)
        state=self.s.get_run('human-secret','p','r')
        self.assertEqual(state['state'],'paused');self.assertTrue(all(x['state']=='exited' for x in state['runtime_sessions']))
        self.assertTrue(all(v['reserved']==0 for v in state['budget'].values()))
