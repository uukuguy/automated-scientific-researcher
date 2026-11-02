"""Authenticated local ASR control authority. SQLite is the owning ledger.

This service maps external AAR Experiment identities; it never runs a competing
research scheduler. Tokens come from operator configuration, never request actors.
Only the trusted supervisor may claim work or publish execution facts.
"""
import copy
import hashlib
import hmac
import json
from pathlib import Path
import uuid
from datetime import datetime, timezone

from asr_service.contracts import PolicyStore, PolicyError, encoded, resolve_policy, check_change
from asr_service.budgets import BudgetStore, BudgetError
from asr_service.references import ReferenceStore
from jsonschema import Draft202012Validator

CONTRACT_SCHEMA = json.loads((Path(__file__).resolve().parent.parent / 'contracts/research-contract.schema.json').read_text())
CONTRACT_VALIDATOR = Draft202012Validator(CONTRACT_SCHEMA)


class ControlError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def now():
    return datetime.now(timezone.utc).isoformat()


class ControlService(PolicyStore):
    def __init__(self, path, *, credentials):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not isinstance(credentials, dict) or not credentials:
            raise ControlError('credentials_required')
        self.credentials = copy.deepcopy(credentials)
        for token, principal in self.credentials.items():
            if not isinstance(token, str) or not token or principal.get('role') not in ('human','researcher','supervisor','viewer') or not isinstance(principal.get('projects'),list) or not principal.get('subject'):
                raise ControlError('invalid_credentials')
        self.budgets = BudgetStore(path)
        self.references = ReferenceStore(path)
        with self._connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS asr_contracts(project TEXT, contract_id TEXT, revision INTEGER, record TEXT, PRIMARY KEY(project,contract_id,revision));
            CREATE TABLE IF NOT EXISTS asr_runs(project TEXT, run TEXT, experiment_id TEXT UNIQUE, record TEXT, PRIMARY KEY(project,run));
            CREATE TABLE IF NOT EXISTS asr_requests(project TEXT, scope TEXT, request_key TEXT, payload TEXT, record TEXT, PRIMARY KEY(project,scope,request_key));
            CREATE TABLE IF NOT EXISTS asr_events(seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, run TEXT, record TEXT);
            CREATE TABLE IF NOT EXISTS asr_dispatch(id TEXT PRIMARY KEY, project TEXT, run TEXT, trial TEXT, attempt TEXT UNIQUE, state TEXT, record TEXT);
            CREATE TABLE IF NOT EXISTS asr_commands(project TEXT, run TEXT, command_id TEXT PRIMARY KEY, record TEXT);
            CREATE TABLE IF NOT EXISTS asr_findings(project TEXT, run TEXT, finding_id TEXT, revision INTEGER, record TEXT, PRIMARY KEY(project,run,finding_id,revision));
            ''')

    def _auth(self, token, project, roles=None):
        principal = None
        if isinstance(token,str):
            for secret, candidate in self.credentials.items():
                if hmac.compare_digest(secret, token): principal=candidate
        if principal is None:
            raise ControlError('unauthorized')
        if project not in principal['projects'] or (roles and principal['role'] not in roles):
            raise ControlError('forbidden')
        self._identity(project)
        return principal

    @staticmethod
    def _event(db, project, run, event_type, **fields):
        db.execute('INSERT INTO asr_events(project,run,record) VALUES (?,?,?)',
                   (project,run,encoded({'type':event_type,'created_at':now(),**fields})))

    @staticmethod
    def _replay(db, project, scope, key, payload):
        row=db.execute('SELECT payload,record FROM asr_requests WHERE project=? AND scope=? AND request_key=?',(project,scope,key)).fetchone()
        if row:
            if row[0] != encoded(payload): raise ControlError('idempotency_conflict')
            return json.loads(row[1])

    @staticmethod
    def _remember(db, project, scope, key, payload, record):
        db.execute('INSERT INTO asr_requests VALUES (?,?,?,?,?)',(project,scope,key,encoded(payload),encoded(record)))

    @staticmethod
    def _run(db, project, run):
        row=db.execute('SELECT record FROM asr_runs WHERE project=? AND run=?',(project,run)).fetchone()
        if not row: raise ControlError('run_not_found')
        return json.loads(row[0])

    @staticmethod
    def _contract(db, project, contract_id, revision):
        row=db.execute('SELECT record FROM asr_contracts WHERE project=? AND contract_id=? AND revision=?',(project,contract_id,revision)).fetchone()
        if not row: raise ControlError('contract_not_found')
        return json.loads(row[0])

    def _validate_contract(self, db, project, document):
        required={'schema_version','objective','variable_policy','problem_ref','reference_ref','evaluation_ref','budget','execution_policy','intervention_policy','provenance','runtime_policy'}
        if type(document) is not dict or set(document)!=required:
            raise ControlError('invalid_contract_fields')
        encoded(document)
        doc=copy.deepcopy(document)
        if doc['schema_version']!='asr-contract/1': raise ControlError('unsupported_schema')
        if type(doc['objective']) is not dict or set(doc['objective'])!={'question','success_criteria','scope'} or any(type(v) is not str or not v.strip() for v in doc['objective'].values()):
            raise ControlError('invalid_objective')
        doc['variable_policy']=resolve_policy(doc['variable_policy'])
        from powerflow_lab.reference import make_request
        baseline=make_request()
        expected_refs={
            'problem': {'profile':'matpower-case118/1','case_sha256':baseline['case_sha256']},
            'reference': {'profile':'matpower-reference/1','image_id':baseline['image_id']},
            'evaluation': {'profile':'powerflow-independent/1','validator_sha256':baseline['source_hashes']['validation.py'],'tolerance_pu':1e-7},
        }
        for field,kind in [('problem_ref','problem'),('reference_ref','reference'),('evaluation_ref','evaluation')]:
            reference=ReferenceStore.get_in_transaction(db,project,kind,doc[field])
            if reference != expected_refs[kind]: raise ControlError('unsupported_'+kind+'_profile')
        if type(doc['budget']) is not dict or not {'attempts','execution_ms','research_walltime_ms','turns','tool_executions'} <= set(doc['budget']): raise ControlError('invalid_budget')
        if set(doc['budget'])-{'attempts','execution_ms','research_walltime_ms','turns','tool_executions'}: raise ControlError('unsupported_budget_dimension')
        for amount in doc['budget'].values(): BudgetStore._amount(amount)
        if doc['budget']['attempts']<1 or doc['budget']['execution_ms']<1: raise ControlError('invalid_budget')
        runtime=doc['runtime_policy']
        if type(runtime) is not dict or runtime.get('billing_mode') not in ('subscription','paid_api'): raise ControlError('invalid_runtime_policy')
        if runtime['billing_mode']=='subscription' and (runtime.get('auth_mode') not in ('subscription_oauth','subscription_cli') or runtime.get('paid_api_authorized',False)): raise ControlError('invalid_runtime_policy')
        if runtime['billing_mode']=='paid_api' and (runtime.get('auth_mode')!='api_key' or runtime.get('paid_api_authorized') is not True): raise ControlError('paid_api_not_authorized')
        execution=doc['execution_policy']
        if type(execution) is not dict or set(execution)!={'researchers','candidate_interface','timeout_seconds','output_bytes','max_concurrency','retry_limit'}: raise ControlError('invalid_execution_policy')
        if execution['researchers']!=1 or execution['candidate_interface']!='asr-candidate/1' or execution['max_concurrency']!=1:
            raise ControlError('capability_unavailable')
        for key in ('researchers','timeout_seconds','output_bytes','max_concurrency'):
            if type(execution[key]) is not int or execution[key]<1: raise ControlError('invalid_execution_policy')
        if type(execution['retry_limit']) is not int or execution['retry_limit']<0: raise ControlError('invalid_execution_policy')
        if doc['intervention_policy']!={'guidance_boundary':'next_submission','pause':'drain'}: raise ControlError('capability_unavailable')
        if type(doc['provenance']) is not dict or not doc['provenance']: raise ControlError('invalid_provenance')
        if execution['output_bytes']!=104857600 or execution['retry_limit']!=0 or execution['timeout_seconds']>3600: raise ControlError('capability_unavailable')
        if next(CONTRACT_VALIDATOR.iter_errors(doc),None) is not None: raise ControlError('invalid_contract_schema')
        return doc

    def publish_contract(self, token, project, contract_id, document, *, expected_revision, idempotency_key):
        principal=self._auth(token,project,{'human'})
        self._identity(contract_id,idempotency_key);self._revision(expected_revision)
        payload=[principal['subject'],contract_id,document,expected_revision]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'contract',idempotency_key,payload)
            if replay: return replay
            doc=self._validate_contract(db,project,document)
            latest=db.execute('SELECT COALESCE(MAX(revision),0) FROM asr_contracts WHERE project=? AND contract_id=?',(project,contract_id)).fetchone()[0]
            if latest!=expected_revision: raise ControlError('revision_conflict')
            record=dict(project_id=project,contract_id=contract_id,revision=latest+1,document=doc,sha256=hashlib.sha256(encoded(doc).encode()).hexdigest(),author=principal['subject'],created_at=now())
            db.execute('INSERT INTO asr_contracts VALUES (?,?,?,?)',(project,contract_id,latest+1,encoded(record)))
            self._remember(db,project,'contract',idempotency_key,payload,record)
            self._event(db,project,None,'contract_published',contract_id=contract_id,revision=latest+1)
            return record

    def _set_limits(self, db, project, amounts):
        for dimension,amount in amounts.items():
            exists=db.execute('SELECT 1 FROM asr_budget_limits WHERE project=? AND dimension=?',(project,dimension)).fetchone()
            if exists:
                balance=self.budgets._balance(db,project,dimension)
                if amount < balance['spent']+balance['reserved']: raise ControlError('below_committed_usage')
            db.execute('INSERT INTO asr_budget_limits VALUES (?,?,?) ON CONFLICT(project,dimension) DO UPDATE SET amount=excluded.amount',(project,dimension,amount))

    def create_run(self, token, project, run_id, experiment_id, contract_id, contract_revision, *, idempotency_key):
        principal=self._auth(token,project,{'human'})
        self._identity(run_id,experiment_id,contract_id,idempotency_key);self._revision(contract_revision)
        payload=[principal['subject'],run_id,experiment_id,contract_id,contract_revision]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'create_run',idempotency_key,payload)
            if replay:return replay
            if db.execute('SELECT 1 FROM asr_runs WHERE (project=? AND run=?) OR experiment_id=?',(project,run_id,experiment_id)).fetchone(): raise ControlError('run_mapping_conflict')
            contract=self._contract(db,project,contract_id,contract_revision)
            self._set_limits(db,project,contract['document']['budget'])
            record=dict(project_id=project,research_run_id=run_id,experiment_id=experiment_id,contract_id=contract_id,contract_revision=contract_revision,control_revision=1,state='running',admission_open=True,health='ok',quota_state=contract['document']['runtime_policy']['quota_state'],walltime_metered_ms=0,created_at=now())
            db.execute('INSERT INTO asr_runs VALUES (?,?,?,?)',(project,run_id,experiment_id,encoded(record)))
            self._remember(db,project,'create_run',idempotency_key,payload,record)
            self._event(db,project,run_id,'run_bound',**record)
            return record

    def get_run(self, token, project, run):
        self._auth(token,project)
        with self._connect() as db:
            db.execute('BEGIN')
            record=self._run(db,project,run)
            record['contract']=self._contract(db,project,record['contract_id'],record['contract_revision'])
            record['budget']={d:self.budgets._balance(db,project,d) for d in record['contract']['document']['budget']}
            record['trials']=[dict(json.loads(body),dispatch_state=state) for state,body in db.execute('SELECT state,record FROM asr_dispatch WHERE project=? AND run=? ORDER BY rowid',(project,run))]
            commands=[json.loads(r[0]) for r in db.execute('SELECT record FROM asr_commands WHERE project=? AND run=? ORDER BY rowid',(project,run))]
            record['guidance']=[r for r in commands if r['kind']=='guidance']
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='asr_executions'").fetchone():
                for trial in record['trials']:
                    execution=db.execute('SELECT record FROM asr_executions WHERE attempt=?',(trial['execution_attempt_id'],)).fetchone()
                    trial['execution']=json.loads(execution[0]) if execution else None
            record['commands']=commands
            return record

    @staticmethod
    def owning_gate(db, dispatch):
        run=ControlService._run(db,dispatch['project_id'],dispatch['research_run_id'])
        return run['state']=='running' and run['admission_open'] and run['health']=='ok' and run.get('quota_state','unknown') in ('unknown','available')

    def submit_trial(self, token, project, run, *, request_key, variables, references, requested_budget):
        principal=self._auth(token,project,{'researcher','human'})
        self._identity(run,request_key)
        payload=[principal['subject'],variables,references,requested_budget]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'trial:'+run,request_key,payload)
            if replay:return replay
            running=self._run(db,project,run)
            if not self.owning_gate(db,{'project_id':project,'research_run_id':run}): raise ControlError('admission_closed')
            contract=self._contract(db,project,running['contract_id'],running['contract_revision'])
            doc=contract['document']
            # Revalidate frozen reference availability in the same owning transaction.
            self._validate_contract(db,project,doc)
            if type(variables) is not dict: raise ControlError('invalid_variables')
            values={k:v['value'] for k,v in doc['variable_policy']['variables'].items()}
            for key,value in variables.items(): values[key]=check_change(doc['variable_policy'],key,value,principal['role'])
            if type(references) is not dict or set(references)!={'problem','evaluation','candidate','input_manifest'}: raise ControlError('invalid_references')
            if references['problem']!=doc['problem_ref'] or references['evaluation']!=doc['evaluation_ref']: raise ControlError('reference_contract_conflict')
            for kind,digest in references.items(): ReferenceStore.get_in_transaction(db,project,kind,digest)
            if type(requested_budget) is not dict or set(requested_budget)!={'attempts','execution_ms'} or requested_budget['attempts']!=1 or type(requested_budget['attempts']) is not int: raise ControlError('invalid_trial_budget')
            if type(requested_budget['execution_ms']) is not int or not 1<=requested_budget['execution_ms']<=doc['execution_policy']['timeout_seconds']*1000: raise ControlError('invalid_trial_budget')
            from powerflow_lab.reference import make_request
            execution_request=make_request(max_iterations=values.get('iterations',20),timeout_seconds=requested_budget['execution_ms']/1000)
            candidate=ReferenceStore.get_in_transaction(db,project,'candidate',references['candidate'])
            if candidate!={'profile':'matpower-reference/1','image_id':execution_request['image_id'],'solver':'newton_raphson'} or values.get('solver','newton_raphson')!='newton_raphson' or values.get('network','case118')!='case118':
                raise ControlError('capability_unavailable')
            if set(variables)-{'iterations','solver','network'}: raise ControlError('capability_unavailable')
            inputs=ReferenceStore.get_in_transaction(db,project,'input_manifest',references['input_manifest'])
            if inputs!={'profile':'matpower-case118-flat/1','problem_ref':doc['problem_ref']}: raise ControlError('unsupported_input_profile')
            trial='trial_'+uuid.uuid4().hex;attempt='attempt_'+uuid.uuid4().hex
            self.budgets.reserve_many_in_transaction(db,project,attempt,requested_budget)
            record=dict(project_id=project,research_run_id=run,trial_id=trial,execution_attempt_id=attempt,contract_id=running['contract_id'],contract_revision=running['contract_revision'],contract=contract,variables=values,references=references,requested_budget=requested_budget,execution_request=execution_request,state='queued',created_at=now())
            db.execute('INSERT INTO asr_dispatch VALUES (?,?,?,?,?,?,?)',(attempt,project,run,trial,attempt,'queued',encoded(record)))
            self._remember(db,project,'trial:'+run,request_key,payload,record)
            self._event(db,project,run,'trial_admitted',trial_id=trial,execution_attempt_id=attempt)
            return record

    def command(self, token, project, run, kind, *, expected_revision, idempotency_key, payload=None):
        principal=self._auth(token,project,{'human','supervisor'} if kind=='quota' else {'human'})
        self._identity(run,idempotency_key);self._revision(expected_revision)
        payload={} if payload is None else payload
        request=[principal['subject'],kind,expected_revision,payload]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'command:'+run,idempotency_key,request)
            if replay:return replay
            record=self._run(db,project,run)
            if record['control_revision']!=expected_revision: raise ControlError('revision_conflict')
            if type(payload) is not dict: raise ControlError('invalid_payload')
            scope='new_submissions_and_queued_dispatch'
            if kind in ('pause','resume'):
                if payload: raise ControlError('invalid_payload')
                if kind=='resume' and record.get('quota_state','unknown') not in ('unknown','available'): raise ControlError('provider_quota_unavailable')
                record.update(state='paused' if kind=='pause' else 'running',admission_open=kind=='resume')
            elif kind=='quota':
                if set(payload)!={'state'} or payload['state'] not in ('unknown','available','exhausted','rate_limited'): raise ControlError('invalid_quota_state')
                record['quota_state']=payload['state']
                if payload['state'] in ('exhausted','rate_limited'): record.update(state='paused',admission_open=False)
                scope='subsequent_submissions'
            elif kind=='guidance':
                if set(payload)!={'text'} or type(payload['text']) is not str or not payload['text'].strip(): raise ControlError('invalid_guidance')
                scope='next_submission'
            elif kind=='apply_contract':
                if set(payload)!={'contract_id','revision'}: raise ControlError('invalid_payload')
                contract=self._contract(db,project,payload['contract_id'],payload['revision'])
                self._set_limits(db,project,contract['document']['budget'])
                record.update(contract_id=payload['contract_id'],contract_revision=payload['revision'],quota_state=contract['document']['runtime_policy']['quota_state'])
                scope='subsequent_submissions'
            else: raise ControlError('unsupported_command')
            record['control_revision']+=1
            db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(record),project,run))
            receipt=dict(command_id='command_'+uuid.uuid4().hex,kind=kind,project_id=project,research_run_id=run,author=principal['subject'],payload=payload,status='applied',effective_scope=scope,control_revision=record['control_revision'],created_at=now())
            db.execute('INSERT INTO asr_commands VALUES (?,?,?,?)',(project,run,receipt['command_id'],encoded(receipt)))
            self._remember(db,project,'command:'+run,idempotency_key,request,receipt)
            self._event(db,project,run,'command_applied',**receipt)
            return receipt

    def events(self, token, project, after=0):
        self._auth(token,project)
        if type(after) is not int or after<0: raise ControlError('invalid_cursor')
        with self._connect() as db:
            return [dict(json.loads(body),seq=seq,research_run_id=run) for seq,run,body in db.execute('SELECT seq,run,record FROM asr_events WHERE project=? AND seq>? ORDER BY seq LIMIT 1000',(project,after))]

    def pending_dispatch(self, token, project):
        self._auth(token,project,{'supervisor','human'})
        with self._connect() as db:
            db.execute('BEGIN')
            return [record for body, in db.execute('SELECT record FROM asr_dispatch WHERE project=? AND state=? ORDER BY rowid',(project,'queued')) if self.owning_gate(db,record:=json.loads(body))]

    def register_reference(self, token, project, kind, document):
        self._auth(token,project,{'human','supervisor'})
        return {'digest':self.references.register(project,kind,document),'kind':kind}

    def get_reference(self, token, project, kind, digest):
        self._auth(token,project)
        return self.references.get(project,kind,digest)

    def publish_finding(self, token, project, run, *, finding_id, expected_revision,
                        idempotency_key, statement, trial_ids, limitations):
        principal=self._auth(token,project,{'human','researcher'})
        self._identity(run,finding_id,idempotency_key);self._revision(expected_revision)
        if type(statement) is not str or not statement.strip() or type(limitations) is not str or not limitations.strip(): raise ControlError('invalid_finding')
        if type(trial_ids) is not list or not trial_ids or any(type(t) is not str for t in trial_ids) or len(set(trial_ids))!=len(trial_ids): raise ControlError('invalid_trial_ids')
        payload=[principal['subject'],finding_id,expected_revision,statement,trial_ids,limitations]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'finding:'+run,idempotency_key,payload)
            if replay:return replay
            self._run(db,project,run)
            evidence=[]
            for trial in trial_ids:
                row=db.execute('SELECT attempt,state FROM asr_dispatch WHERE project=? AND run=? AND trial=?',(project,run,trial)).fetchone()
                if row is None: raise ControlError('trial_not_found')
                if row[1] not in ('succeeded','failed','cancelled','timed_out','interrupted'): raise ControlError('evidence_not_published')
                from asr_supervisor.store import ExecutionStore
                execution=ExecutionStore._read(db,row[0])
                if not execution['report'] or not execution['report'].get('manifest_hash'): raise ControlError('evidence_not_published')
                evidence.append(dict(trial_id=trial,execution_attempt_id=row[0],manifest_hash=execution['report']['manifest_hash']))
            latest=db.execute('SELECT COALESCE(MAX(revision),0) FROM asr_findings WHERE project=? AND run=? AND finding_id=?',(project,run,finding_id)).fetchone()[0]
            if latest!=expected_revision: raise ControlError('revision_conflict')
            record=dict(project_id=project,research_run_id=run,finding_id=finding_id,revision=latest+1,statement=statement,limitations=limitations,evidence=evidence,status='candidate',author=principal['subject'],created_at=now())
            db.execute('INSERT INTO asr_findings VALUES (?,?,?,?,?)',(project,run,finding_id,latest+1,encoded(record)))
            self._remember(db,project,'finding:'+run,idempotency_key,payload,record)
            self._event(db,project,run,'candidate_finding_published',finding_id=finding_id,revision=latest+1)
            return record

    def findings(self, token, project, run):
        self._auth(token,project)
        with self._connect() as db:
            self._run(db,project,run)
            return [json.loads(row[0]) for row in db.execute('SELECT record FROM asr_findings WHERE project=? AND run=? ORDER BY finding_id,revision',(project,run))]

    def admit_activity(self, token, project, run, *, kind, idempotency_key):
        """Debit a finite runtime permit; retain elapsed time even on exhaustion.

        The runtime must enforce remaining_walltime_ms while executing. Failed
        turns/tools retain their already issued permit. No billing fallback.
        """
        principal=self._auth(token,project,{'human','supervisor'})
        self._identity(run,idempotency_key)
        if kind not in ('turn','tool_execution'): raise ControlError('invalid_activity_kind')
        payload=[principal['subject'],kind]
        exhausted=False
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'activity:'+run,idempotency_key,payload)
            if replay:return replay
            record=self._run(db,project,run)
            if not self.owning_gate(db,{'project_id':project,'research_run_id':run}): raise ControlError('admission_closed')
            elapsed=max(0,int((datetime.now(timezone.utc)-datetime.fromisoformat(record['created_at'])).total_seconds()*1000))
            walltime=max(0,elapsed-record['walltime_metered_ms'])
            dimension='turns' if kind=='turn' else 'tool_executions'
            activity='activity_'+uuid.uuid4().hex
            # This is observed consumption, not a request for future execution.
            # Actual overrun must survive rejection of the next activity.
            db.execute('INSERT INTO asr_budget_reservations VALUES (?,?,?,?,?)',(project,activity,'research_walltime_ms',0,walltime))
            record['walltime_metered_ms']=elapsed
            remaining=self.budgets._balance(db,project,'research_walltime_ms')['available']
            if remaining<=0 or self.budgets._balance(db,project,dimension)['available']<1:
                exhausted=True
                record.update(state='paused',admission_open=False)
                self._event(db,project,run,'runtime_budget_exhausted',kind=kind)
            else:
                self.budgets.reserve_many_in_transaction(db,project,activity+'_permit',{dimension:1})
                db.execute('UPDATE asr_budget_reservations SET actual=amount WHERE project=? AND attempt=?',(project,activity+'_permit'))
                permit=dict(activity_id=activity,kind=kind,project_id=project,research_run_id=run,remaining_walltime_ms=remaining,created_at=now())
                self._remember(db,project,'activity:'+run,idempotency_key,payload,permit)
                self._event(db,project,run,'runtime_activity_admitted',**permit)
            db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(record),project,run))
        if exhausted: raise ControlError('budget_exhausted')
        return permit
