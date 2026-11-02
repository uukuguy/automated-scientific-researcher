"""Variable policy validation and immutable revision storage.

This is one component of a future research contract. A policy passing these
checks is NOT execution authorization. References, budgets, capability admission
and authenticated principals belong to the service layer still to be built.
"""
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from jsonschema import Draft202012Validator

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / 'contracts/variable-policy.schema.json').read_text())
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)


class PolicyError(ValueError):
    def __init__(self, code, path='', message=''):
        self.code, self.path = code, path
        super().__init__(message or f'{code}: {path}')


def encoded(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise PolicyError('invalid_json') from exc


def _typed(value, kind):
    return {'string': lambda: type(value) is str,
            'boolean': lambda: type(value) is bool,
            'integer': lambda: type(value) is int,
            'number': lambda: type(value) in (int, float)}[kind]()


def _value(var, value, path):
    if not _typed(value, var['type']):
        raise PolicyError('invalid_type', path)
    allowed = var.get('allowed')
    if allowed:
        if 'choices' in allowed:
            if value not in allowed['choices']:
                raise PolicyError('outside_allowed', path)
        elif not allowed['minimum'] <= value <= allowed['maximum']:
            raise PolicyError('outside_allowed', path)


def resolve_policy(template, overrides=None):
    """Resolve declared user overrides; never mutate the input or infer units."""
    encoded(template)
    policy = copy.deepcopy(template)
    errors = list(VALIDATOR.iter_errors(policy))
    if errors:
        error = errors[0]
        raise PolicyError('invalid_schema', '/'.join(map(str,error.absolute_path)), error.message)
    if overrides is not None and type(overrides) is not dict:
        raise PolicyError('invalid_overrides')
    for key, changes in (overrides or {}).items():
        if key not in policy['variables'] or type(changes) is not dict:
            raise PolicyError('unknown_variable', key)
        if set(changes) - {'value','mode','allowed','modifiable_by','implementation'}:
            raise PolicyError('undeclared_override', key)
        policy['variables'][key].update(copy.deepcopy(changes))
    encoded(policy)
    errors = list(VALIDATOR.iter_errors(policy))
    if errors:
        error = errors[0]
        raise PolicyError('invalid_schema','/'.join(map(str,error.absolute_path)),error.message)
    for key, var in policy['variables'].items():
        if not _typed(var['default'],var['type']):
            raise PolicyError('invalid_default',key)
        allowed=var.get('allowed')
        if allowed and 'minimum' in allowed:
            if var['type'] not in ('integer','number') or allowed['minimum'] > allowed['maximum']:
                raise PolicyError('invalid_range',key)
        if allowed and 'choices' in allowed and any(not _typed(v,var['type']) for v in allowed['choices']):
            raise PolicyError('invalid_choices',key)
        if var['mode']=='fixed' and 'researcher' in var['modifiable_by']:
            raise PolicyError('fixed_researcher_permission',key)
        var.setdefault('value',copy.deepcopy(var['default']))
        _value(var,var['value'],key)
    return policy


def check_change(policy, variable, value, actor, *, scope="trial"):
    """Validate a candidate trial value without modifying the published policy."""
    policy=resolve_policy(policy)
    encoded(value)
    if variable not in policy['variables']:
        raise PolicyError('unknown_variable',variable)
    var=policy['variables'][variable]
    if scope != var['scope']:
        raise PolicyError('scope_mismatch',variable)
    if actor not in var['modifiable_by']:
        raise PolicyError('forbidden',variable)
    _value(var,value,variable)
    if var['mode']=='fixed' and value != var['value']:
        raise PolicyError('requires_new_revision',variable)
    return copy.deepcopy(value)


class PolicyStore:
    """Trusted in-process repository. actor is NOT an authentication mechanism.

    Pass the owning application's database path. No autonomous runs are created.
    Bindings attach an external run ID to a policy; they do not dispatch work.
    """
    def __init__(self, path):
        self.path=Path(path)
        with self._connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS asr_policy_revisions (
              project TEXT NOT NULL, policy_id TEXT NOT NULL, revision INTEGER NOT NULL,
              record TEXT NOT NULL, PRIMARY KEY(project,policy_id,revision));
            CREATE TABLE IF NOT EXISTS asr_policy_requests (
              project TEXT NOT NULL, request_key TEXT NOT NULL, payload TEXT NOT NULL,
              record TEXT NOT NULL, PRIMARY KEY(project,request_key));
            CREATE TABLE IF NOT EXISTS asr_policy_bindings (
              project TEXT NOT NULL, run_id TEXT NOT NULL, record TEXT NOT NULL,
              PRIMARY KEY(project,run_id));
            CREATE TABLE IF NOT EXISTS asr_policy_events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL, record TEXT NOT NULL);
            ''')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path,timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _authorize(actor):
        if actor!='human': raise PolicyError('forbidden')

    @staticmethod
    def _identity(*values):
        if any(type(v) is not str or not v or len(v)>256 for v in values):
            raise PolicyError('invalid_identity')

    @staticmethod
    def _revision(value):
        if type(value) is not int or value<0: raise PolicyError('invalid_revision')

    def publish(self, project, policy_id, policy, *, expected_revision, idempotency_key, actor):
        self._authorize(actor);self._identity(project,policy_id,idempotency_key);self._revision(expected_revision)
        policy=resolve_policy(policy)
        payload=encoded([policy_id,policy,expected_revision,actor])
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT payload,record FROM asr_policy_requests WHERE project=? AND request_key=?',(project,idempotency_key)).fetchone()
            if prior:
                if prior[0]!=payload: raise PolicyError('idempotency_conflict')
                return json.loads(prior[1])
            latest=db.execute('SELECT COALESCE(MAX(revision),0) FROM asr_policy_revisions WHERE project=? AND policy_id=?',(project,policy_id)).fetchone()[0]
            if latest!=expected_revision: raise PolicyError('revision_conflict')
            record=dict(project_id=project,policy_id=policy_id,revision=latest+1,policy=policy,
                        sha256=hashlib.sha256(encoded(policy).encode()).hexdigest(),
                        created_at=datetime.now(timezone.utc).isoformat(),author=actor)
            body=encoded(record)
            db.execute('INSERT INTO asr_policy_revisions VALUES (?,?,?,?)',(project,policy_id,latest+1,body))
            db.execute('INSERT INTO asr_policy_requests VALUES (?,?,?,?)',(project,idempotency_key,payload,body))
            db.execute('INSERT INTO asr_policy_events(project,record) VALUES (?,?)',(project,encoded({'type':'policy_published','policy_id':policy_id,'revision':latest+1})))
            return record

    def get(self, project, policy_id, revision):
        with self._connect() as db:
            row=db.execute('SELECT record FROM asr_policy_revisions WHERE project=? AND policy_id=? AND revision=?',(project,policy_id,revision)).fetchone()
        if not row: raise PolicyError('not_found')
        return json.loads(row[0])

    def apply(self, project, run_id, policy_id, policy_revision, *, expected_revision, actor):
        self._authorize(actor);self._identity(project,run_id,policy_id);self._revision(expected_revision);self._revision(policy_revision)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM asr_policy_revisions WHERE project=? AND policy_id=? AND revision=?',(project,policy_id,policy_revision)).fetchone():
                raise PolicyError('not_found')
            prior=db.execute('SELECT record FROM asr_policy_bindings WHERE project=? AND run_id=?',(project,run_id)).fetchone()
            current=json.loads(prior[0])['control_revision'] if prior else 0
            if current!=expected_revision: raise PolicyError('revision_conflict')
            record=dict(project_id=project,run_id=run_id,policy_id=policy_id,
                        policy_revision=policy_revision,control_revision=current+1)
            db.execute('INSERT INTO asr_policy_bindings VALUES (?,?,?) ON CONFLICT(project,run_id) DO UPDATE SET record=excluded.record',(project,run_id,encoded(record)))
            db.execute('INSERT INTO asr_policy_events(project,record) VALUES (?,?)',(project,encoded({'type':'policy_applied',**record})))
            return record

    def binding(self, project, run_id):
        with self._connect() as db:
            row=db.execute('SELECT record FROM asr_policy_bindings WHERE project=? AND run_id=?',(project,run_id)).fetchone()
        if not row: raise PolicyError('not_found')
        return json.loads(row[0])

    def events(self, project):
        with self._connect() as db:
            return [{'seq':seq,**json.loads(body)} for seq,body in db.execute('SELECT seq,record FROM asr_policy_events WHERE project=? ORDER BY seq',(project,))]
