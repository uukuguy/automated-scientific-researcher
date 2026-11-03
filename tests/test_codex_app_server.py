"""Native App Server protocol plumbing with fake processes; no model inference."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from integrations.runtimes.codex_app_server import (
    CodexAppServerClient, AppServerClosed, AppServerProtocolError,
    AppServerRemoteError, AppServerTimeout,
)

FAKE = r'''
import json,os,sys
initialized=False
held=[]
waiting=None
for line in sys.stdin.buffer:
    message=json.loads(line)
    method=message.get('method')
    def send(value):print(json.dumps(value,ensure_ascii=False),flush=True)
    def result(value):send({'id':message['id'],'result':value})
    if method=='initialize':
        result({'userAgent':'fake-codex/0.166.0','platformFamily':'unix','platformOs':'fake','codexHome':'private'})
    elif method=='initialized':initialized=True
    elif 'method' not in message and message.get('id')==900:
        send({'id':waiting,'result':message});waiting=None
    elif not initialized:send({'id':message['id'],'error':{'code':-32000,'message':'Not initialized'}})
    elif method=='thread/start':
        send({'method':'thread/started','params':{'thread':{'id':'thread-1'}}})
        result({'thread':{'id':'thread-1'},'sandbox':message['params'].get('sandbox')})
    elif method=='thread/resume':result({'thread':{'id':message['params']['threadId']}})
    elif method=='turn/start':
        result({'turn':{'id':'turn-1','status':'inProgress'}})
        send({'method':'item/agentMessage/delta','params':{'threadId':'thread-1','turnId':'turn-1','delta':'A\u2028B'}})
    elif method=='turn/interrupt':
        result({})
        send({'method':'turn/completed','params':{'threadId':message['params']['threadId'],'turn':{'id':message['params']['turnId'],'status':'interrupted'}}})
    elif method=='reorder':
        held.append(message)
        if len(held)==2:
            for item in reversed(held):send({'id':item['id'],'result':item['params']})
            held=[]
    elif method=='ask':
        waiting=message['id'];send({'id':900,'method':'item/commandExecution/requestApproval','params':{'command':'example'}})
    elif method=='error':send({'id':message['id'],'error':{'code':422,'message':'Rejected','data':{'reason':'fixture'}}})
    elif method=='env':result({'api_key_present':'OPENAI_API_KEY' in os.environ,'aws_present':'AWS_ACCESS_KEY_ID' in os.environ})
    elif method=='stall':pass
    elif method=='invalid':print('not-json',flush=True)
    elif method=='oversize':print('x'*5000,flush=True)
    elif method=='flood':
        for n in range(20):send({'method':'fixture/event','params':{'n':n}})
    elif method=='exit':sys.exit(3)
    else:result(message['params'])
'''


class CodexClientTests(unittest.TestCase):
    def test_protocol_overflow_retains_explicit_recoverable_receipt(self):
        client=self.client(max_message_bytes=1024)
        client.initialize()
        with self.assertRaises(Exception):client.request('oversize',{})
        receipt=client.close()
        self.assertTrue(receipt.get('limit_observations'),'native overflow must not be a bare disconnect')
        event=receipt['limit_observations'][0]
        self.assertEqual(event['kind'],'protocol_message_bytes')
        self.assertEqual(event['configured'],1024)
        self.assertGreater(event['observed'],1024)
        self.assertTrue(event['recoverable'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.script=self.root/'server.py';self.script.write_text(FAKE)

    def client(self,**options):
        client=CodexAppServerClient(command=[sys.executable,'-u',str(self.script)],cwd=self.root,
            walltime_seconds=options.pop('walltime_seconds',5),request_timeout=options.pop('request_timeout',1),**options)
        self.addCleanup(client.close);return client

    def test_handshake_thread_resume_and_interrupt_completion_are_distinct(self):
        c=self.client(allow_model_turns=True)
        with self.assertRaises(RuntimeError):c.start_thread()
        self.assertEqual(c.initialize()['platformOs'],'fake')
        with self.assertRaises(RuntimeError):c.initialize()
        self.assertEqual(c.start_thread()['thread']['id'],'thread-1')
        self.assertEqual(c.next_event()['method'],'thread/started')
        self.assertEqual(c.resume_thread('thread-1')['thread']['id'],'thread-1')
        accepted=c.start_turn('thread-1',[{'type':'text','text':'fixture only'}])
        self.assertEqual(accepted['turn']['status'],'inProgress')
        self.assertEqual(c.next_event()['params']['delta'],'A'+chr(0x2028)+'B')
        self.assertEqual(c.interrupt_turn('thread-1','turn-1'),{})
        event=c.next_event();self.assertEqual(event['params']['turn']['status'],'interrupted')
        receipt=c.close();self.assertTrue(receipt['direct_child_exited']);self.assertIsNotNone(c.process.poll())

    def test_correlates_out_of_order_concurrent_responses(self):
        c=self.client();c.initialize()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(c.request,'reorder',{'value':n}) for n in range(2)]
            self.assertEqual([f.result()['value'] for f in futures],[0,1])

    def test_server_requests_default_reject_without_approval(self):
        c=self.client();c.initialize()
        response=c.request('ask',{})
        self.assertEqual(response['error']['code'],-32601)
        self.assertNotIn('result',response)

    def test_explicit_manual_server_request_roundtrip(self):
        c=self.client(server_request_mode='manual');c.initialize()
        with ThreadPoolExecutor(max_workers=1) as pool:
            request=pool.submit(c.request,'ask',{})
            incoming=c.next_server_request()
            self.assertEqual(incoming['method'],'item/commandExecution/requestApproval')
            c.respond(incoming['id'],result={'decision':'decline'})
            self.assertEqual(request.result()['result'],{'decision':'decline'})
            with self.assertRaises(ValueError):c.respond(incoming['id'],result={})

    def test_remote_error_preserves_structured_code(self):
        c=self.client();c.initialize()
        with self.assertRaises(AppServerRemoteError) as raised:c.request('error',{})
        self.assertEqual(raised.exception.code,422)
        self.assertEqual(raised.exception.data,{'reason':'fixture'})

    def test_timeout_closes_unknown_in_flight_request_without_retry(self):
        c=self.client();c.initialize()
        with self.assertRaises(AppServerTimeout):c.request('stall',{},timeout=.05)
        self.assertIsNotNone(c.process.poll())
        with self.assertRaises(AppServerClosed):c.request('echo',{})

    def test_overall_deadline_reaps_even_without_an_outstanding_request(self):
        c=self.client(walltime_seconds=.15);c.initialize()
        c.process.wait(timeout=2)
        with self.assertRaises(AppServerClosed):c.request('echo',{})

    def test_invalid_oversized_and_unconsumed_event_streams_fail_closed(self):
        for method,options in [('invalid',{}),('oversize',{'max_message_bytes':1024}),('flood',{'max_events':4})]:
            with self.subTest(method=method):
                c=self.client(**options);c.initialize()
                with self.assertRaises(AppServerProtocolError):c.request(method,{})
                self.assertIsNotNone(c.process.poll())

    def test_child_exit_fails_pending_request(self):
        c=self.client();c.initialize()
        with self.assertRaises(AppServerClosed):c.request('exit',{})
        self.assertIsNotNone(c.process.poll())

    def test_default_blocks_inference_and_removes_ambient_api_credentials(self):
        from unittest.mock import patch
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fixture-not-a-secret','AWS_ACCESS_KEY_ID':'fixture'}):
            c=self.client();c.initialize()
            self.assertEqual(c.request('env',{}),{'api_key_present':False,'aws_present':False})
            with self.assertRaises(PermissionError):c.start_turn('thread-1',[{'type':'text','text':'do not send'}])

    def test_immediate_exit_during_reader_startup_completes_cleanup(self):
        import threading
        from unittest.mock import patch
        original=threading.Thread.start;thread_errors=[]
        def start(thread):
            if getattr(thread,'_target',None).__name__=='_drain_stderr':time.sleep(.1)
            return original(thread)
        with patch.object(threading.Thread,'start',start),patch.object(threading,'excepthook',lambda args:thread_errors.append(args.exc_value)):
            c=CodexAppServerClient(command=[sys.executable,'-c','pass'],cwd=self.root,walltime_seconds=2)
            self.addCleanup(c.close)
            self.assertTrue(c._closed.wait(2))
            self.assertIsNotNone(c.process.poll())
            self.assertTrue(c.process.stdout.closed);self.assertTrue(c.process.stderr.closed)
        self.assertEqual(thread_errors,[])

    def test_finite_limits_required_before_spawn(self):
        for value in (0,-1,float('inf'),True):
            with self.assertRaises(ValueError):self.client(walltime_seconds=value)
