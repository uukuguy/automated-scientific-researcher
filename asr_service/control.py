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
            if not isinstance(token, str) or not token or principal.get('role') not in ('human','researcher','supervisor','viewer','evaluator') or not isinstance(principal.get('projects'),list) or not principal.get('subject'):
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
            CREATE TABLE IF NOT EXISTS asr_runtime_sessions(project TEXT, run TEXT, session_id TEXT PRIMARY KEY, state TEXT, record TEXT);
            CREATE TABLE IF NOT EXISTS asr_hypotheses(project TEXT NOT NULL, hypothesis_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL, PRIMARY KEY(project,hypothesis_id,revision));
            CREATE TABLE IF NOT EXISTS asr_findings(project TEXT, run TEXT, finding_id TEXT, revision INTEGER, record TEXT, PRIMARY KEY(project,run,finding_id,revision));
            ''')
            from .validations import initialize
            initialize(db)

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
        effective={k:v['value'] for k,v in doc['variable_policy']['variables'].items()}
        if set(effective)-{'network','iterations','solver'} or effective.get('network','case118')!='case118' or effective.get('solver','newton_raphson')!='newton_raphson': raise ControlError('capability_unavailable')
        if type(effective.get('iterations',20)) is not int or not 0<=effective.get('iterations',20)<=1000: raise ControlError('capability_unavailable')
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
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return self.create_run_in_transaction(db,token,project,run_id,experiment_id,contract_id,contract_revision,idempotency_key=idempotency_key)

    def create_run_in_transaction(self, db, token, project, run_id, experiment_id, contract_id, contract_revision, *, idempotency_key):
        """Join the owning transaction, including a real upstream Experiment row."""
        if not db.in_transaction: raise ControlError('transaction_required')
        principal=self._auth(token,project,{'human'})
        self._identity(run_id,experiment_id,contract_id,idempotency_key);self._revision(contract_revision)
        payload=[principal['subject'],run_id,experiment_id,contract_id,contract_revision]
        replay=self._replay(db,project,'create_run',idempotency_key,payload)
        if replay:return replay
        if db.execute('SELECT 1 FROM asr_runs WHERE (project=? AND run=?) OR experiment_id=?',(project,run_id,experiment_id)).fetchone(): raise ControlError('run_mapping_conflict')
        contract=self._contract(db,project,contract_id,contract_revision)
        self._set_limits(db,project,contract['document']['budget'])
        record=dict(project_id=project,research_run_id=run_id,experiment_id=experiment_id,contract_id=contract_id,contract_revision=contract_revision,control_revision=1,state='running',admission_open=True,health='ok',quota_state=contract['document']['runtime_policy']['quota_state'],created_at=now())
        if record['quota_state'] in ('rate_limited','exhausted'): record.update(state='paused',admission_open=False)
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
            record['resource_ledgers']=self.budgets.ledger_snapshot_in_transaction(db,project)
            record['trials']=[dict(json.loads(body),dispatch_state=state) for state,body in db.execute('SELECT state,record FROM asr_dispatch WHERE project=? AND run=? ORDER BY rowid',(project,run))]
            for trial in record['trials']:
                trial.setdefault('hypothesis_ref',None)
                trial.setdefault('hypothesis_linkage','linked' if trial['hypothesis_ref'] else 'legacy_unlinked')
            commands=[json.loads(r[0]) for r in db.execute('SELECT record FROM asr_commands WHERE project=? AND run=? ORDER BY rowid',(project,run))]
            record['guidance']=[r for r in commands if r['kind']=='guidance']
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='asr_executions'").fetchone():
                for trial in record['trials']:
                    execution=db.execute('SELECT record FROM asr_executions WHERE attempt=?',(trial['execution_attempt_id'],)).fetchone()
                    trial['execution']=json.loads(execution[0]) if execution else None
            record['commands']=commands
            record['runtime_sessions']=[json.loads(r[0]) for r in db.execute('SELECT record FROM asr_runtime_sessions WHERE project=? AND run=? ORDER BY rowid',(project,run))]
            return record

    @staticmethod
    def owning_gate(db, dispatch):
        run=ControlService._run(db,dispatch['project_id'],dispatch['research_run_id'])
        return run['state']=='running' and run['admission_open'] and run['health']=='ok' and run.get('quota_state','unknown') in ('unknown','available')

    def submit_trial(self, token, project, run, *, request_key, variables, references, requested_budget, hypothesis_ref=None):
        principal=self._auth(token,project,{'researcher','human'})
        self._identity(run,request_key)
        payload=[principal['subject'],variables,references,requested_budget]
        # Preserve byte-for-byte request identity for historical unlinked trials.
        if hypothesis_ref is not None: payload.append(hypothesis_ref)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'trial:'+run,request_key,payload)
            if replay:return replay
            running=self._run(db,project,run)
            frozen_hypothesis=self._hypothesis_ref(db,project,hypothesis_ref) if hypothesis_ref is not None else None
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
            record.update(hypothesis_ref=frozen_hypothesis,hypothesis_linkage='linked' if frozen_hypothesis else 'legacy_unlinked')
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
            status='applied'
            if record['state'] in ('stopped','completed') and kind not in ('guidance',): raise ControlError('run_terminal')
            if record['state'] in ('stopping','finishing') and kind not in ('guidance','cancel_trial','quota'): raise ControlError('control_transition_pending')
            if kind in ('pause','resume'):
                if payload: raise ControlError('invalid_payload')
                if kind=='resume' and record.get('quota_state','unknown') not in ('unknown','available'): raise ControlError('provider_quota_unavailable')
                record.update(state='paused' if kind=='pause' else 'running',admission_open=kind=='resume')
            elif kind=='quota':
                if set(payload)!={'state'} or payload['state'] not in ('unknown','available','exhausted','rate_limited'): raise ControlError('invalid_quota_state')
                record['quota_state']=payload['state']
                if payload['state'] in ('exhausted','rate_limited'):
                    record['admission_open']=False
                    if record['state'] not in ('stopping','finishing'): record['state']='paused'
                scope='subsequent_submissions'
            elif kind=='guidance':
                if set(payload)!={'text'} or type(payload['text']) is not str or not payload['text'].strip(): raise ControlError('invalid_guidance')
                scope='next_submission'
            elif kind=='apply_contract':
                if set(payload)!={'contract_id','revision'}: raise ControlError('invalid_payload')
                contract=self._contract(db,project,payload['contract_id'],payload['revision'])
                self._set_limits(db,project,contract['document']['budget'])
                record.update(contract_id=payload['contract_id'],contract_revision=payload['revision'],quota_state=contract['document']['runtime_policy']['quota_state'])
                if record['quota_state'] in ('rate_limited','exhausted'): record.update(state='paused',admission_open=False)
                scope='subsequent_submissions'
            elif kind in ('stop','finish','cancel_trial'):
                if (kind=='cancel_trial' and set(payload)!={'trial_id'}) or (kind!='cancel_trial' and payload): raise ControlError('invalid_payload')
                query='SELECT attempt,state FROM asr_dispatch WHERE project=? AND run=?'
                args=[project,run]
                if kind=='cancel_trial': query+=' AND trial=?';args.append(payload['trial_id'])
                targets=db.execute(query,args).fetchall()
                if kind=='cancel_trial' and not targets: raise ControlError('trial_not_found')
                for attempt,state in targets:
                    if state=='queued':
                        db.execute('UPDATE asr_dispatch SET state=? WHERE attempt=?',('cancelled',attempt))
                        # Claim and cancellation share the same SQLite write lock;
                        # a queued item has no process and may safely release cost.
                        db.execute('UPDATE asr_budget_reservations SET actual=0 WHERE project=? AND attempt=? AND actual IS NULL',(project,attempt))
                    elif state not in ('succeeded','failed','cancelled','timed_out','interrupted'):
                        status='pending'
                        if kind!='finish': db.execute('UPDATE asr_dispatch SET state=? WHERE attempt=?',('cancel_requested',attempt))
                if kind in ('stop','finish'):
                    if db.execute("SELECT 1 FROM asr_runtime_sessions WHERE project=? AND run=? AND state!='exited'",(project,run)).fetchone(): status='pending'
                    record.update(state=('stopping' if kind=='stop' else 'finishing') if status=='pending' else ('stopped' if kind=='stop' else 'completed'),admission_open=False)
                scope='cancel_requested' if kind=='cancel_trial' else 'stop_and_preserve_evidence' if kind=='stop' else 'drain_inflight_and_close'
            else: raise ControlError('unsupported_command')
            record['control_revision']+=1
            db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(record),project,run))
            receipt=dict(command_id='command_'+uuid.uuid4().hex,kind=kind,project_id=project,research_run_id=run,author=principal['subject'],payload=payload,status=status,effective_scope=scope,control_revision=record['control_revision'],created_at=now())
            if kind=='guidance': receipt.update(delivery_status='undelivered',acknowledgements=[])
            db.execute('INSERT INTO asr_commands VALUES (?,?,?,?)',(project,run,receipt['command_id'],encoded(receipt)))
            self._remember(db,project,'command:'+run,idempotency_key,request,receipt)
            self._event(db,project,run,'command_applied' if status=='applied' else 'command_received',**receipt)
            if kind=='cancel_trial':
                actual=db.execute('SELECT state FROM asr_dispatch WHERE project=? AND run=? AND trial=?',(project,run,payload['trial_id'])).fetchone()[0]
                receipt['effective_outcome']=actual
                db.execute('UPDATE asr_commands SET record=? WHERE command_id=?',(encoded(receipt),receipt['command_id']))
                db.execute('UPDATE asr_requests SET record=? WHERE project=? AND scope=? AND request_key=?',(encoded(receipt),project,'command:'+run,idempotency_key))
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
                        idempotency_key, statement, trial_ids, limitations, hypothesis_evidence=None):
        principal=self._auth(token,project,{'human','researcher'})
        self._identity(run,finding_id,idempotency_key);self._revision(expected_revision)
        if type(statement) is not str or not statement.strip() or type(limitations) is not str or not limitations.strip(): raise ControlError('invalid_finding')
        if type(trial_ids) is not list or not trial_ids or any(type(t) is not str for t in trial_ids) or len(set(trial_ids))!=len(trial_ids): raise ControlError('invalid_trial_ids')
        payload=[principal['subject'],finding_id,expected_revision,statement,trial_ids,limitations]
        if hypothesis_evidence is not None: payload.append(hypothesis_evidence)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'finding:'+run,idempotency_key,payload)
            if replay:return replay
            self._run(db,project,run)
            evidence=[]
            admitted_trials={}
            for trial in trial_ids:
                row=db.execute('SELECT attempt,state,record FROM asr_dispatch WHERE project=? AND run=? AND trial=?',(project,run,trial)).fetchone()
                if row is None: raise ControlError('trial_not_found')
                if row[1] not in ('succeeded','failed','cancelled','timed_out','interrupted'): raise ControlError('evidence_not_published')
                from asr_supervisor.store import ExecutionStore
                execution=ExecutionStore._read(db,row[0])
                if not execution['report'] or not execution['report'].get('manifest_hash'): raise ControlError('evidence_not_published')
                report=execution['report']
                try:
                    from powerflow_lab.runner import digest, _inventory
                    evidence_path=Path(report['evidence_path'])
                    manifest_path=evidence_path/'manifest.json'
                    if not evidence_path.is_dir() or manifest_path.is_symlink() or digest(manifest_path)!=report['manifest_hash']: raise ValueError('manifest_mismatch')
                    manifest=json.loads(manifest_path.read_text())
                    if manifest.get('trial_id')!=trial or manifest.get('execution_attempt_id')!=row[0] or manifest.get('status')!=report['status'] or manifest.get('artifacts')!=_inventory(evidence_path): raise ValueError('evidence_mismatch')
                except (OSError,ValueError,KeyError,RuntimeError) as exc:
                    raise ControlError('evidence_unavailable') from exc
                evidence.append(dict(trial_id=trial,execution_attempt_id=row[0],manifest_hash=execution['report']['manifest_hash']))
                admitted_trials[trial]=json.loads(row[2])
            latest=db.execute('SELECT COALESCE(MAX(revision),0) FROM asr_findings WHERE project=? AND run=? AND finding_id=?',(project,run,finding_id)).fetchone()[0]
            if latest!=expected_revision: raise ControlError('revision_conflict')
            record=dict(project_id=project,research_run_id=run,finding_id=finding_id,revision=latest+1,statement=statement,limitations=limitations,evidence=evidence,status='candidate',author=principal['subject'],created_at=now())
            if hypothesis_evidence is not None:
                record['hypothesis_evidence']=self._finding_hypothesis_evidence(db,project,hypothesis_evidence,admitted_trials,evidence,principal['subject'])
            db.execute('INSERT INTO asr_findings VALUES (?,?,?,?,?)',(project,run,finding_id,latest+1,encoded(record)))
            self._remember(db,project,'finding:'+run,idempotency_key,payload,record)
            self._event(db,project,run,'candidate_finding_published',finding_id=finding_id,revision=latest+1)
            return record

    def findings(self, token, project, run):
        self._auth(token,project)
        with self._connect() as db:
            self._run(db,project,run)
            return [json.loads(row[0]) for row in db.execute('SELECT record FROM asr_findings WHERE project=? AND run=? ORDER BY finding_id,revision',(project,run))]

    def claim_runtime(self, token, project, run, owner, *, idempotency_key, runtime_identity, requested_walltime_ms=None):
        """Reserve a single bounded external runtime; never launch on replay."""
        principal=self._auth(token,project,{'human','supervisor'})
        self._identity(run,owner,idempotency_key)
        payload=[principal['subject'],owner,requested_walltime_ms,runtime_identity]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'runtime:'+run,idempotency_key,payload)
            if replay:
                row=db.execute('SELECT record FROM asr_runtime_sessions WHERE session_id=?',(replay['session_id'],)).fetchone()
                return dict(json.loads(row[0]),replayed=True)
            record=self._run(db,project,run)
            policy=self._contract(db,project,record['contract_id'],record['contract_revision'])['document']['runtime_policy']
            expected_identity={k:policy[k] for k in ('provider','model','auth_mode','billing_mode')}
            if runtime_identity!=expected_identity: raise ControlError('runtime_binding_conflict')
            if not self.owning_gate(db,{'project_id':project,'research_run_id':run}): raise ControlError('admission_closed')
            if db.execute("SELECT 1 FROM asr_runtime_sessions WHERE project=? AND run=? AND state!='exited'",(project,run)).fetchone(): raise ControlError('runtime_already_active')
            amount=self.budgets._balance(db,project,'research_walltime_ms')['available'] if requested_walltime_ms is None else requested_walltime_ms
            BudgetStore._amount(amount)
            if amount<=0: raise ControlError('budget_exhausted')
            session='session_'+uuid.uuid4().hex
            self.budgets.reserve_many_in_transaction(db,project,session,{'research_walltime_ms':amount})
            record=dict(project_id=project,research_run_id=run,session_id=session,epoch=1,owner=owner,state='active',runtime_identity=runtime_identity,reserved_walltime_ms=amount,started_at=now(),process_identity=None,launch_state='prepared')
            db.execute('INSERT INTO asr_runtime_sessions VALUES (?,?,?,?,?)',(project,run,session,'active',encoded(record)))
            self._remember(db,project,'runtime:'+run,idempotency_key,payload,record)
            self._event(db,project,run,'runtime_claimed',**record)
            return dict(record,replayed=False)

    @staticmethod
    def _session(db,project,run,session_id,epoch,owner):
        if type(epoch) is not int or epoch<1: raise ControlError('stale_runtime_epoch')
        row=db.execute('SELECT record FROM asr_runtime_sessions WHERE project=? AND run=? AND session_id=?',(project,run,session_id)).fetchone()
        if not row: raise ControlError('runtime_not_found')
        record=json.loads(row[0])
        if record['epoch']!=epoch or record['owner']!=owner: raise ControlError('stale_runtime_epoch')
        return record

    def release_runtime(self, token, project, run, session_id, epoch, owner, *, execution_exited, actual_walltime_ms):
        self._auth(token,project,{'human','supervisor'})
        if execution_exited is not True: raise ControlError('execution_not_reconciled')
        BudgetStore._amount(actual_walltime_ms)
        with self._connect() as db:
            session=self._session(db,project,run,session_id,epoch,owner)
        if session['state']=='exited':
            if session['actual_walltime_ms']!=actual_walltime_ms: raise ControlError('idempotency_conflict')
            return session
        from integrations.runtimes.process import verify_process_exit
        if not session.get('process_identity'): raise ControlError('process_identity_required')
        exit_receipt=verify_process_exit(session['process_identity'],terminate=False)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session=self._session(db,project,run,session_id,epoch,owner)
            if session['state']=='exited':
                if session['actual_walltime_ms']!=actual_walltime_ms: raise ControlError('idempotency_conflict')
                return session
            db.execute('UPDATE asr_budget_reservations SET actual=? WHERE project=? AND attempt=? AND dimension=?',(actual_walltime_ms,project,session_id,'research_walltime_ms'))
            session.update(state='exited',actual_walltime_ms=actual_walltime_ms,execution_exited=True,exit_receipt=exit_receipt,finished_at=now())
            db.execute('UPDATE asr_runtime_sessions SET state=?,record=? WHERE session_id=?',('exited',encoded(session),session_id))
            record=self._run(db,project,run)
            if self.budgets._balance(db,project,'research_walltime_ms')['available']<=0 and record['state']=='running':
                record.update(state='paused',admission_open=False)
                db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(record),project,run))
            self._event(db,project,run,'runtime_exited',**session)
            from asr_supervisor.store import ExecutionStore
            finalize=getattr(ExecutionStore,'finalize_controls_in_transaction',None)
            if finalize: finalize(db,project,run)
            return session

    def admit_activity(self, token, project, run, *, kind, idempotency_key, session_id, epoch, owner):
        """Issue one finite permit within the exclusively reserved runtime session."""
        principal=self._auth(token,project,{'human','supervisor'})
        self._identity(run,idempotency_key)
        if kind not in ('turn','tool_execution'): raise ControlError('invalid_activity_kind')
        payload=[principal['subject'],kind,session_id,epoch,owner]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session=self._session(db,project,run,session_id,epoch,owner)
            replay=self._replay(db,project,'activity:'+run,idempotency_key,payload)
            if replay:return replay
            if session['state']!='active': raise ControlError('runtime_not_active')
            running=self._run(db,project,run)
            policy=self._contract(db,project,running['contract_id'],running['contract_revision'])['document']['runtime_policy']
            if session['runtime_identity']!={k:policy[k] for k in ('provider','model','auth_mode','billing_mode')}: raise ControlError('runtime_binding_conflict')
            if not self.owning_gate(db,{'project_id':project,'research_run_id':run}): raise ControlError('admission_closed')
            elapsed=max(0,int((datetime.now(timezone.utc)-datetime.fromisoformat(session['started_at'])).total_seconds()*1000))
            remaining=session['reserved_walltime_ms']-elapsed
            if remaining<=0: raise ControlError('budget_exhausted')
            dimension='turns' if kind=='turn' else 'tool_executions'
            activity='activity_'+uuid.uuid4().hex
            self.budgets.reserve_many_in_transaction(db,project,activity,{dimension:1})
            db.execute('UPDATE asr_budget_reservations SET actual=amount WHERE project=? AND attempt=?',(project,activity))
            permit=dict(activity_id=activity,kind=kind,project_id=project,research_run_id=run,session_id=session_id,epoch=epoch,remaining_walltime_ms=remaining,created_at=now())
            self._remember(db,project,'activity:'+run,idempotency_key,payload,permit)
            self._event(db,project,run,'runtime_activity_admitted',**permit)
            return permit

    def attach_runtime_process(self, token, project, run, session_id, epoch, owner, identity):
        self._auth(token,project,{'human','supervisor'})
        from integrations.runtimes.process import identify
        if type(identity) is not dict or identify(identity.get('pid'))!=identity:
            raise ControlError('process_identity_mismatch')
        if identity.get('pid')!=identity.get('pgid'): raise ControlError('process_group_required')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session=self._session(db,project,run,session_id,epoch,owner)
            if session['state']!='active': raise ControlError('runtime_not_active')
            if session.get('launch_state')!='launching': raise ControlError('runtime_launch_not_authorized')
            if session.get('process_identity') is not None and session['process_identity']!=identity: raise ControlError('process_identity_immutable')
            session['process_identity']=copy.deepcopy(identity)
            db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(encoded(session),session_id))
            self._event(db,project,run,'runtime_process_attached',session_id=session_id,epoch=epoch,identity=identity)
            return session

    def reconcile_runtime(self, token, project, run, session_id, expected_epoch, owner, *, terminate=False):
        """Fence old ownership before independently checking the registered OS group.

        Unknown/mismatched identity retains its reservation and closes admission.
        Reconciliation grants inspection/termination, never a second launch.
        """
        self._auth(token,project,{'human','supervisor'})
        self._identity(owner)
        if type(expected_epoch) is not int or expected_epoch<1: raise ControlError('stale_runtime_epoch')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT record FROM asr_runtime_sessions WHERE project=? AND run=? AND session_id=?',(project,run,session_id)).fetchone()
            if not row: raise ControlError('runtime_not_found')
            session=json.loads(row[0])
            if session['epoch']!=expected_epoch: raise ControlError('stale_runtime_epoch')
            if session['state']=='exited': return session
            session.update(epoch=expected_epoch+1,owner=owner,state='reconciling')
            db.execute('UPDATE asr_runtime_sessions SET state=?,record=? WHERE session_id=?',('reconciling',encoded(session),session_id))
            running=self._run(db,project,run)
            running.update(health='reconciling',admission_open=False)
            db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(running),project,run))
            self._event(db,project,run,'runtime_reconciliation_started',session_id=session_id,epoch=session['epoch'])
        try:
            from integrations.runtimes.process import verify_process_exit
            if not session.get('process_identity'): raise ControlError('process_identity_required')
            receipt=verify_process_exit(session['process_identity'],terminate=terminate)
        except (ValueError,RuntimeError,OSError) as exc:
            with self._connect() as db:
                db.execute('BEGIN IMMEDIATE')
                current=self._session(db,project,run,session_id,session['epoch'],owner)
                current.update(state='uncertain',reconciliation_error=str(exc))
                db.execute('UPDATE asr_runtime_sessions SET state=?,record=? WHERE session_id=?',('uncertain',encoded(current),session_id))
                self._event(db,project,run,'runtime_reconciliation_uncertain',session_id=session_id,epoch=session['epoch'],reason=str(exc))
            raise
        elapsed=max(0,int((datetime.now(timezone.utc)-datetime.fromisoformat(session['started_at'])).total_seconds()*1000))
        result=self.release_runtime(token,project,run,session_id,session['epoch'],owner,execution_exited=True,actual_walltime_ms=elapsed)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            running=self._run(db,project,run)
            unresolved_numerical=False
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='asr_executions'").fetchone():
                for body, in db.execute('SELECT record FROM asr_executions'):
                    execution=json.loads(body)
                    if execution['project']==project and execution['run']==run and execution.get('report') is None and execution['state'] in ('interrupted','reconciling'):
                        unresolved_numerical=True
            if not unresolved_numerical: running['health']='ok'
            db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(running),project,run))
            result['reconciliation_receipt']=receipt
            db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(encoded(result),session_id))
            self._event(db,project,run,'runtime_reconciled',session_id=session_id,epoch=result['epoch'],receipt=receipt)
        return result

    def ack_guidance(self, token, project, run, command_id, *, session_id, epoch, owner,
                     status, reason, idempotency_key):
        principal=self._auth(token,project,{'human','supervisor','researcher'})
        self._identity(command_id,idempotency_key)
        if status not in ('delivered','adopted','deferred') or type(reason) is not str or (status=='deferred' and not reason.strip()): raise ControlError('invalid_guidance_ack')
        payload=[principal['subject'],command_id,session_id,epoch,owner,status,reason]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session=self._session(db,project,run,session_id,epoch,owner)
            replay=self._replay(db,project,'guidance_ack:'+run,idempotency_key,payload)
            if replay:return replay
            if session['state']!='active': raise ControlError('runtime_not_active')
            row=db.execute('SELECT record FROM asr_commands WHERE project=? AND run=? AND command_id=?',(project,run,command_id)).fetchone()
            if not row: raise ControlError('command_not_found')
            command=json.loads(row[0])
            if command['kind']!='guidance': raise ControlError('not_guidance')
            if status=='delivered' and command.get('delivery_status') in ('adopted','deferred'): raise ControlError('ack_regression')
            ack=dict(acknowledgement_id='ack_'+uuid.uuid4().hex,command_id=command_id,session_id=session_id,epoch=epoch,status=status,reason=reason,author=principal['subject'],created_at=now())
            command.update(delivery_status=status,acknowledgements=command.get('acknowledgements',[])+[ack])
            db.execute('UPDATE asr_commands SET record=? WHERE command_id=?',(encoded(command),command_id))
            for scope,key,body in db.execute('SELECT scope,request_key,record FROM asr_requests WHERE project=? AND scope=?',(project,'command:'+run)).fetchall():
                if json.loads(body).get('command_id')==command_id:
                    db.execute('UPDATE asr_requests SET record=? WHERE project=? AND scope=? AND request_key=?',(encoded(command),project,scope,key))
            self._remember(db,project,'guidance_ack:'+run,idempotency_key,payload,ack)
            self._event(db,project,run,'guidance_acknowledged',**ack)
            return ack

    def begin_runtime_launch(self, token, project, run, session_id, epoch, owner):
        """Persist the sole launch grant immediately before the trusted Popen.

        Once issued, missing process identity is uncertainty, never proof that
        nothing launched. A repeated grant cannot authorize another process.
        """
        self._auth(token,project,{'human','supervisor'})
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session=self._session(db,project,run,session_id,epoch,owner)
            if session['state']!='active': raise ControlError('runtime_not_active')
            if session.get('launch_state')!='prepared': raise ControlError('runtime_launch_already_authorized')
            if not self.owning_gate(db,{'project_id':project,'research_run_id':run}): raise ControlError('admission_closed')
            session.update(launch_state='launching',launch_authorized_at=now())
            db.execute('UPDATE asr_runtime_sessions SET record=? WHERE session_id=?',(encoded(session),session_id))
            self._event(db,project,run,'runtime_launch_authorized',session_id=session_id,epoch=epoch)
            return session

    def abort_runtime_prelaunch(self, token, project, run, session_id, epoch, owner, *, reason):
        """Settle a setup rejection only when no launch grant was ever issued."""
        self._auth(token,project,{'human','supervisor'})
        if type(reason) is not str or not reason.strip(): raise ControlError('reason_required')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session=self._session(db,project,run,session_id,epoch,owner)
            if session['state']=='exited' and session.get('launch_state')=='aborted': return session
            if session['state']!='active' or session.get('launch_state')!='prepared' or session.get('process_identity') is not None: raise ControlError('runtime_launch_already_authorized')
            receipt=dict(kind='no_launch_grant_issued',session_id=session_id,epoch=epoch,observed_at=now(),reason=reason)
            session.update(state='exited',launch_state='aborted',actual_walltime_ms=0,execution_exited=True,exit_receipt=receipt,finished_at=now())
            db.execute('UPDATE asr_budget_reservations SET actual=0 WHERE project=? AND attempt=? AND dimension=?',(project,session_id,'research_walltime_ms'))
            db.execute('UPDATE asr_runtime_sessions SET state=?,record=? WHERE session_id=?',('exited',encoded(session),session_id))
            self._event(db,project,run,'runtime_prelaunch_aborted',session_id=session_id,epoch=epoch,receipt=receipt)
            from asr_supervisor.store import ExecutionStore
            ExecutionStore.finalize_controls_in_transaction(db,project,run)
            return session

    def publish_hypothesis(self, token, project, hypothesis_id, document, *, expected_revision, idempotency_key):
        """Append an immutable author prediction; never publish validation status."""
        principal=self._auth(token,project,{'human','researcher'})
        self._identity(hypothesis_id,idempotency_key);self._revision(expected_revision)
        from .hypotheses import validate_document
        document=validate_document(document)
        payload=[principal['subject'],hypothesis_id,document,expected_revision]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=self._replay(db,project,'hypothesis',idempotency_key,payload)
            if replay:return replay
            latest=db.execute('SELECT COALESCE(MAX(revision),0) FROM asr_hypotheses WHERE project=? AND hypothesis_id=?',(project,hypothesis_id)).fetchone()[0]
            if latest!=expected_revision:raise ControlError('revision_conflict')
            record=dict(schema_version='asr-hypothesis/1',project_id=project,hypothesis_id=hypothesis_id,revision=latest+1,parent_revision=latest or None,document=document,sha256=hashlib.sha256(encoded(document).encode()).hexdigest(),author=principal['subject'],created_at=now())
            db.execute('INSERT INTO asr_hypotheses VALUES (?,?,?,?)',(project,hypothesis_id,latest+1,encoded(record)))
            self._remember(db,project,'hypothesis',idempotency_key,payload,record)
            self._event(db,project,None,'hypothesis_published',hypothesis_id=hypothesis_id,revision=latest+1,parent_revision=record['parent_revision'])
            return record

    def hypotheses(self, token, project, hypothesis_id=None):
        self._auth(token,project)
        if hypothesis_id is not None:self._identity(hypothesis_id)
        with self._connect() as db:
            if hypothesis_id is None:
                rows=db.execute('SELECT record FROM asr_hypotheses WHERE project=? ORDER BY hypothesis_id,revision',(project,))
            else:
                rows=db.execute('SELECT record FROM asr_hypotheses WHERE project=? AND hypothesis_id=? ORDER BY revision',(project,hypothesis_id))
            return [json.loads(row[0]) for row in rows]

    def _hypothesis_ref(self, db, project, reference):
        if type(reference) is not dict or set(reference)!={'project_id','hypothesis_id','revision'}:raise ControlError('invalid_hypothesis_ref')
        if reference['project_id']!=project:raise ControlError('hypothesis_scope_conflict')
        self._identity(reference['hypothesis_id'])
        if type(reference['revision']) is not int or not 1<=reference['revision']<=2**63-1:raise ControlError('invalid_hypothesis_ref')
        row=db.execute('SELECT record FROM asr_hypotheses WHERE project=? AND hypothesis_id=? AND revision=?',(project,reference['hypothesis_id'],reference['revision'])).fetchone()
        if row is None:raise ControlError('hypothesis_not_found')
        record=json.loads(row[0])
        return dict(reference,sha256=record['sha256'])

    def _finding_hypothesis_evidence(self, db, project, relations, trials, evidence, author):
        """Validate author links without deciding experimental/scientific validity."""
        fields={'hypothesis_ref','trial_id','assessment','scope','analysis_timing'}
        if type(relations) is not list or not relations or len(relations)>256:raise ControlError('invalid_hypothesis_evidence')
        records=[];seen=set()
        for relation in relations:
            if type(relation) is not dict or set(relation)!=fields:raise ControlError('invalid_hypothesis_evidence')
            if relation['assessment'] not in ('supports','opposes','uncertain') or relation['analysis_timing'] not in ('prospective','post_hoc') or type(relation['scope']) is not str or not relation['scope'].strip():raise ControlError('invalid_hypothesis_evidence')
            if type(relation['trial_id']) is not str or relation['trial_id'] not in trials:raise ControlError('hypothesis_evidence_trial_conflict')
            reference=self._hypothesis_ref(db,project,relation['hypothesis_ref'])
            key=(reference['hypothesis_id'],reference['revision'],relation['trial_id'])
            if key in seen:raise ControlError('duplicate_hypothesis_evidence')
            seen.add(key)
            hypothesis=json.loads(db.execute('SELECT record FROM asr_hypotheses WHERE project=? AND hypothesis_id=? AND revision=?',(project,reference['hypothesis_id'],reference['revision'])).fetchone()[0])
            if relation['analysis_timing']=='prospective' and (trials[relation['trial_id']].get('hypothesis_ref')!=reference or hypothesis['document']['analysis_timing']=='post_hoc'):raise ControlError('post_hoc_label_required')
            source=next(item for item in evidence if item['trial_id']==relation['trial_id'])
            records.append(dict(relation,hypothesis_ref=reference,execution_attempt_id=source['execution_attempt_id'],manifest_hash=source['manifest_hash'],assessment_kind='author_claim',assessment_author=author))
        return records

    def publish_validation(self, token, project, run, validation_id, document, *, idempotency_key, supersedes=None):
        from .validations import publish_validation
        return publish_validation(self,token,project,run,validation_id,document,idempotency_key=idempotency_key,supersedes=supersedes)

    def validations(self, token, project, run):
        from .validations import validations
        return validations(self,token,project,run)
