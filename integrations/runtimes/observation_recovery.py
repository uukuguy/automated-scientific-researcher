"""Host-only reconciliation of frozen, persisted observation prefixes.

This does not replay scientific work, restore a live cursor or recover volatile
memory. Control remains the only authority for the original session/epoch/key.
"""
import hashlib
from itertools import islice
import sqlite3
import json
import os
from pathlib import Path
import re
import stat

from asr_service.control import ControlError
from .capacity_policy import load_policy


class InvalidPrefix(ValueError):
    def __init__(self, reason, **details):
        self.reason=reason;self.details=details


def _records(path, limits):
    cap=limits['observation_recovery_record_bytes']['value']
    count=limits['observation_recovery_records']['value']
    with path.open('rb') as stream:
        number=0
        while True:
            offset=stream.tell();line=stream.readline(cap+1)
            if not line:return
            number+=1
            if len(line)>cap:raise InvalidPrefix('record_capacity',line=number,offset=offset,limit=cap,observed_at_least=len(line),unit='bytes')
            if number>count:raise InvalidPrefix('record_count_capacity',line=number,limit=count,observed=number,unit='records')
            if not line.endswith(b'\n'):raise InvalidPrefix('incomplete_tail',line=number,offset=offset,bytes=len(line),sha256=hashlib.sha256(line).hexdigest())
            try:record=json.loads(line)
            except (ValueError,UnicodeError):raise InvalidPrefix('invalid_record',line=number,offset=offset) from None
            if (type(record) is not dict or record.get('schema')!='asr-recorded-runtime-event/1' or
                    type(record.get('sequence')) is not int or record['sequence']!=number or type(record.get('event')) is not dict):
                raise InvalidPrefix('invalid_record',line=number,offset=offset)
            yield number,offset,record


def _cursor(event):
    if event.get('type')=='asr_context_cursor':return event
    prefix='ASR_CONTEXT_EVENT '
    if (event.get('type')=='extension_ui_request' and event.get('method')=='notify' and
            type(event.get('message')) is str and event['message'].startswith(prefix)):
        try:value=json.loads(event['message'][len(prefix):])
        except ValueError:raise InvalidPrefix('invalid_observation_metadata') from None
        if type(value) is not dict:raise InvalidPrefix('invalid_observation_metadata')
        if value.get('type')=='asr_context_cursor':return value
    return None


def recover(service, token, project, run, source, *, identity, expected_sha256, destination, capacity_policy_path=None):
    service._auth(token,project,{'human','supervisor'})
    if type(identity) is not dict or set(identity)!={'session_id','epoch','owner'}:raise ValueError('original_runtime_identity_required')
    if type(expected_sha256) is not str or not re.fullmatch('[0-9a-f]{64}',expected_sha256):raise ValueError('source_hash_required')
    policy=load_policy(capacity_policy_path);limits=policy['limits']
    destination=Path(destination);destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    result=dict(schema='asr-observation-recovery/1',status='deferred',project_id=project,research_run_id=run,
        identity=dict(identity),historical_only=True,installation_authorized=False,active_cursor_verified=False,
        scientific_work_replayed=False,budget_changes=False,persisted_prefix_only=True,volatile_records_recovered=False,observations=0,outcomes={},capacity_policy_sha256=policy['sha256'])

    def finish(reason=None, **details):
        if reason:result.update(reason=reason,details=details)
        with (destination/'recovery.json').open('x') as stream:
            json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        return result

    try:
        with service._connect() as db:
            session=service._session(db,project,run,**identity)
        if session['state']!='exited':return finish('execution_reconciliation_required')
    except ControlError as error:return finish(error.code)

    source=Path(source)
    if not source.is_absolute() or source.resolve()!=source:return finish('unsafe_source_path')
    snapshot=destination/'source.jsonl'
    try:
        descriptor=os.open(source,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(descriptor,'rb') as reader:
            info=os.fstat(reader.fileno())
            if not stat.S_ISREG(info.st_mode):return finish('source_not_regular')
            cap=limits['observation_recovery_snapshot_bytes']['value']
            if info.st_size>cap:return finish('snapshot_capacity',limit=cap,observed=info.st_size,unit='bytes')
            remaining=info.st_size;digest=hashlib.sha256()
            with snapshot.open('xb') as writer:
                while remaining:
                    body=reader.read(min(262144,remaining))
                    if not body:return finish('source_changed_during_freeze')
                    digest.update(body);writer.write(body);remaining-=len(body)
                writer.flush();os.fsync(writer.fileno())
        snapshot.chmod(0o400)
        result['source']=dict(path=str(source),snapshot='source.jsonl',prefix_bytes=info.st_size,sha256=digest.hexdigest(),expected_sha256=expected_sha256)
        if digest.hexdigest()!=expected_sha256:return finish('source_hash_mismatch')
    except OSError:return finish('source_freeze_failed')

    # Validate the entire sealed prefix before any Control mutation. The second
    # pass consumes that same private snapshot with record-bounded parsing memory.
    validated=0
    try:
        for number,offset,record in _records(snapshot,limits):
            _cursor(record['event']);validated=number
    except InvalidPrefix as error:
        if error.reason!='incomplete_tail':return finish(error.reason,**error.details)
        result['gap']=dict(reason=error.reason,**error.details)
    result['validated_records']=validated
    with (destination/'receipts.jsonl').open('x') as receipts:
        for number,offset,record in islice(_records(snapshot,limits),validated):
            event=_cursor(record['event'])
            if event is None:continue
            try:
                receipt=service.observe_context_cursor(token,project,run,**identity,observation=event)
            except ControlError as error:receipt=dict(status='deferred',reason=error.code)
            except (OSError,sqlite3.Error):receipt=dict(status='deferred',reason='observation_record_io_failed')
            status=receipt.get('status','unknown')
            result['observations']+=1
            result['outcomes'][status]=result['outcomes'].get(status,0)+1
            proof=dict(source_line=number,source_offset=offset,observation_id=event.get('observation_id'),historical_only=True,installation_authorized=False,receipt=receipt)
            receipts.write(json.dumps(proof,ensure_ascii=False,allow_nan=False)+'\n')
        receipts.flush();os.fsync(receipts.fileno())
    result['status']='partial' if 'gap' in result else 'reconciled'
    return finish()


def recover_steps(service, token, project, run, steps, *, destination, capacity_policy_path=None):
    """Explicit organization resume hook; never changes old step results."""
    service._auth(token,project,{'human','supervisor'})
    destination=Path(destination);destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    report=dict(schema='asr-step-observation-recovery/1',historical_only=True,
                installation_authorized=False,budget_changes=False,steps=[])
    for step in sorted(Path(steps).glob('*')):
        result_path=step/'result.json'
        if not step.is_dir() or not result_path.is_file():continue
        old=json.loads(result_path.read_text())
        if old.get('context_observation_drain',{}).get('drained') is not False:continue
        identity=old.get('runtime_claim',{})
        original={key:identity[key] for key in ('session_id','epoch','owner') if key in identity}
        source=step/'events.jsonl'
        if len(original)!=3 or not source.is_file() or source.is_symlink():
            outcome=dict(status='deferred',reason='original_observation_source_or_identity_missing')
        else:
            with source.open('rb') as stream:expected=hashlib.file_digest(stream,'sha256').hexdigest()
            outcome=recover(service,token,project,run,source,identity=original,expected_sha256=expected,
                            destination=destination/step.name,capacity_policy_path=capacity_policy_path)
        report['steps'].append(dict(step=step.name,recovery=outcome))
    with (destination/'index.json').open('x') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return report
