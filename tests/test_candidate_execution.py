"""Frozen candidate execution through existing supervisor fences; no model calls."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from asr_service.budgets import BudgetStore
from asr_supervisor.store import ExecutionStore
from asr_supervisor.supervisor import Supervisor
from asr_supervisor.candidate import make_candidate_request, CandidateBackend
from asr_supervisor.docker import DockerBackend
from asr_evaluation import Replay

GOOD = '''function result = candidate(mpc)
  options = mpoption('pf.alg','NR','pf.tol',1e-10,'pf.nr.max_it',20,'pf.enforce_q_lims',0,'exp.use_legacy_core',1,'verbose',0,'out.all',0);
  [result, success] = runpf(mpc, options);
  result.solver_success = logical(success);
  result.method = 'test fixture NR';
end
'''


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.code=self.root/'candidate.m';self.code.write_text(GOOD)
        self.prefix=uuid.uuid4().hex[:12]+'_'

    def request(self, **kwargs):
        body=self.code.read_bytes()
        return make_candidate_request(self.code,hashlib.sha256(body).hexdigest(),len(body),**kwargs)

    def test_freezes_code_wrapper_input_rule_and_rejects_source_drift(self):
        request=self.request(timeout_seconds=5)
        self.assertEqual(request['profile'],'octave-candidate/1')
        self.assertEqual(request['output_bytes'],1048576)
        DockerBackend.validate_request(request)
        self.code.write_text(GOOD+'% changed')
        with self.assertRaises(ValueError):DockerBackend.validate_request(request)

    def test_rejects_symlink_size_hash_and_unbounded_request(self):
        body=self.code.read_bytes()
        for sha,size in [('0'*64,len(body)),(hashlib.sha256(body).hexdigest(),len(body)+1)]:
            with self.assertRaises(ValueError):make_candidate_request(self.code,sha,size,timeout_seconds=5)
        for limit in (0,61,True,float('inf')):
            with self.assertRaises(ValueError):self.request(timeout_seconds=limit)
        link=self.root/'linked.m';link.symlink_to(self.code)
        with self.assertRaises(ValueError):make_candidate_request(link,hashlib.sha256(body).hexdigest(),len(body),timeout_seconds=5)

    def manager(self,attempt,request):
        dbpath=self.root/'state.db'
        budget=BudgetStore(dbpath);budget.set_limit('p','execution_ms',300000)
        budget.reserve('p',attempt,'execution_ms',int(request['timeout_seconds']*1000))
        with sqlite3.connect(dbpath) as db:
            db.executescript('CREATE TABLE IF NOT EXISTS asr_runs(project,run,experiment_id,record); CREATE TABLE IF NOT EXISTS asr_dispatch(id PRIMARY KEY,project,run,trial,attempt,state,record);')
            if not db.execute('SELECT 1 FROM asr_runs').fetchone():db.execute('INSERT INTO asr_runs VALUES (?,?,?,?)',('p','r','e',json.dumps({'state':'running','admission_open':True,'health':'ok'})))
            db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)',(attempt,'p','r','trial_'+attempt,attempt,'queued',json.dumps({'execution_request':request})))
        store=ExecutionStore(dbpath)
        return Supervisor(store,self.root/'evidence',poll_seconds=.02),budget


@unittest.skipUnless(os.environ.get('ASR_REAL_DOCKER')=='1','explicit Docker acceptance only')
class CandidateDockerTests(CandidateTests):
    def run_candidate(self,name,code=GOOD,timeout=5):
        name=self.prefix+name
        self.code.write_text(code);request=self.request(timeout_seconds=timeout)
        manager,budget=self.manager(name,request)
        result=manager.execute(name,'owner')
        return result,manager,budget

    def test_real_candidate_and_fresh_replication_independent_recheck(self):
        source,_,_=self.run_candidate('first')
        replica,_,_=self.run_candidate('replica')
        first_path=Path(source['report']['evidence_path']);second_path=Path(replica['report']['evidence_path'])
        self.assertEqual(source['state'],'succeeded');self.assertEqual(replica['state'],'succeeded')
        self.assertNotEqual(source['identity']['container_id'],replica['identity']['container_id'])
        self.assertEqual((first_path/'candidate.m').read_bytes(),(second_path/'candidate.m').read_bytes())
        for record,path in ((source,first_path),(replica,second_path)):
            check=Replay(self.root/'checks').run(record['attempt'],path,record['report']['manifest_hash'],
                trial_id=record['trial'],execution_attempt_id=record['attempt'],research_run_id='r')
            self.assertTrue(check['result']['equation_valid'])
            config=json.loads((path/'container-inspection.json').read_text())
            self.assertTrue(all(not mount['RW'] for mount in config['Mounts']))
            self.assertEqual(len(config['Mounts']),2)

    def test_malicious_access_and_fixed_input_corruption_do_not_escape(self):
        malicious='''function result=candidate(mpc)
 checks=[exist('/var/run/docker.sock','file')==0, exist('/evaluator','dir')==0, isempty(getenv('OPENAI_API_KEY'))];
 [s,~]=system('touch /candidate/candidate.m /runner/candidate_wrapper.m /host-escape 2>/dev/null');
 assert(all(checks) && s~=0);
 fid=fopen('/tmp/network_check.py','w');
 fputs(fid,'import socket; s=socket.socket(); s.settimeout(.2); assert s.connect_ex(("198.51.100.1",443)) != 0');fclose(fid);
 [network_exit,~]=system('python3 /tmp/network_check.py');assert(network_exit==0);
 fid=fopen('/tmp/fill.bin','w');total=0;block=zeros(1,1048576,'uint8');
 for i=1:140
   try;n=fwrite(fid,block,'uint8');total=total+n;if n<1048576;break;end;catch;break;end
 end
 fclose(fid);unlink('/tmp/fill.bin');assert(total<140*1048576 && total<=128*1048576);
 result=mpc;result.bus(1,3)=result.bus(1,3)+1;
 end
'''
        result,_,_=self.run_candidate('malicious',malicious)
        path=Path(result['report']['evidence_path'])
        self.assertEqual(result['state'],'succeeded')
        check=Replay(self.root/'checks').run('malicious',path,result['report']['manifest_hash'],
            trial_id=result['trial'],execution_attempt_id=result['attempt'],research_run_id='r')
        self.assertFalse(check['result']['input_preserved'])
        self.assertFalse(check['result']['equation_valid'])

    def test_output_flood_and_timeout_are_bounded_and_charged(self):
        for name,code,timeout in [('flood',"function result=candidate(mpc)\nwhile true;fprintf('%s',repmat('x',1,65536));fflush(stdout);end;end",5),
                                 ('fast-overflow',"function result=candidate(mpc)\nfprintf('%s',repmat('x',1,2097152));result=mpc;end",5),
                                 ('timeout','function result=candidate(mpc)\npause(20);result=mpc;end',.1)]:
            with self.subTest(name=name):
                result,_,budget=self.run_candidate(name,code,timeout)
                self.assertIn(result['state'],('failed','timed_out'))
                self.assertTrue(result['report']['execution_exited'])
                path=Path(result['report']['evidence_path'])
                self.assertLessEqual((path/'candidate-stream.log').stat().st_size,1048576)
                self.assertGreater(budget.balance('p','execution_ms')['spent'],0)

    def test_invalid_return_protocol_is_failed_not_unknown_execution(self):
        code="function result=candidate(mpc)\nfprintf('ASR_CANDIDATE_RESULT_V1:{}\\n');result=mpc;end"
        result,_,budget=self.run_candidate('invalid-protocol',code)
        self.assertEqual(result['state'],'failed')
        self.assertTrue(result['report']['execution_exited'])
        self.assertEqual(budget.balance('p','execution_ms')['reserved'],0)

    def test_interruption_reconciles_same_candidate_container_and_retains_cost(self):
        from unittest.mock import patch
        self.code.write_text('function result=candidate(mpc)\npause(20);result=mpc;end')
        attempt=self.prefix+'interrupted'
        request=self.request(timeout_seconds=5);manager,budget=self.manager(attempt,request)
        backend=manager.backend
        original=backend.inspect
        with patch.object(backend,'inspect',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):manager.execute(attempt,'owner')
        record=manager.store.get(attempt);container=record['identity']['container_id']
        self.assertTrue(original(record['identity'])['running'])
        with sqlite3.connect(manager.store.path) as db:
            record['lease_until']=0;db.execute('UPDATE asr_executions SET record=?',(json.dumps(record),))
        restarted=Supervisor(ExecutionStore(manager.store.path),self.root/'evidence',poll_seconds=.02)
        recovered=restarted.reconcile(attempt,'new-owner')
        self.assertEqual(recovered['identity']['container_id'],container)
        self.assertEqual(recovered['state'],'interrupted')
        self.assertFalse(restarted.backend.inspect(recovered['identity'])['running'])
        self.assertGreater(budget.balance('p','execution_ms')['spent'],0)
