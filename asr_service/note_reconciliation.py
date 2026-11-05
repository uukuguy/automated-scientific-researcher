"""Explicit host inspection of immutable note files and existing Control receipts.

Never repairs a save receipt, adopts a note, deletes a file or infers a crash cause.
"""
import hashlib
import json
import re
import stat

from asr_context.notes import NoteStore
from .contracts import encoded
from .control import ControlError
from .organization import member


def _ledger(db,project,run,subject):
    scope='research-note:'+encoded([project,run,subject])
    receipts=db.execute('SELECT request_key,record FROM asr_requests WHERE project=? AND scope=? ORDER BY request_key',(project,scope)).fetchall()
    head=db.execute('SELECT revision FROM asr_note_heads WHERE project=? AND run=? AND owner=?',(project,run,subject)).fetchone()
    return receipts,head[0] if head else None


def _metadata(path):
    try:value=path.lstat()
    except FileNotFoundError:return None
    return (str(path.parent.resolve()/path.name),value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns,value.st_mode)


def _scan(service,project,run,subject,ledger):
    scope=encoded([project,run,subject]);root=service.path.parent/'research-notes'/hashlib.sha256(scope.encode()).hexdigest()
    directory=root/'revisions';guards={root:_metadata(root),directory:_metadata(directory)}
    if any(value and not stat.S_ISDIR(value[-1]) for value in guards.values()):raise ControlError('unsafe_note_directory')
    receipts,head=ledger;known={}
    for key,raw in receipts:
        record=json.loads(raw)
        if record.get('status') not in ('saved','adopted'):continue
        revision=record['revision']
        item=known.setdefault(revision,dict(saved=[],adopted=[]));item[record['status']].append(key)
    if head is not None:known.setdefault(head,dict(saved=[],adopted=[]))
    entries=[];present=set()
    if guards[directory] is not None:
        store=NoteStore(root,scope=scope,create=False)
        for path in sorted(directory.iterdir()):
            metadata=_metadata(path);guards[path]=metadata
            match=re.fullmatch(r'([0-9a-f]{64})\.json',path.name)
            if not match:
                entries.append(dict(file=path.name,integrity='unpublished_temporary' if path.name.startswith('.note-') else 'unrecognized',registration='unknown',current_accepted=False))
                continue
            revision=match[1];present.add(revision);binding=known.get(revision,dict(saved=[],adopted=[]))
            row=dict(file=path.name,revision=revision,registration='registered' if binding['saved'] or binding['adopted'] else ('head_only' if revision==head else 'unregistered'),
                     saved_request_keys=binding['saved'],adopted_request_keys=binding['adopted'],current_accepted=revision==head)
            if metadata is None:row['integrity']='missing'
            elif not stat.S_ISREG(metadata[-1]):row['integrity']='unsafe_file'
            else:
                try:
                    note=store.read(revision)
                    row.update(integrity='verified',parent=note['parent'],source_count=len(note['sources']))
                except ValueError as error:row.update(integrity='invalid',reason=str(error))
            if _metadata(path)!=metadata:raise ControlError('note_audit_sources_changed')
            entries.append(row)
    for revision in sorted(set(known)-present):
        binding=known[revision]
        entries.append(dict(file=revision+'.json',revision=revision,integrity='missing',registration='registered' if binding['saved'] or binding['adopted'] else 'head_only',
                            saved_request_keys=binding['saved'],adopted_request_keys=binding['adopted'],current_accepted=revision==head))
    return dict(entries=entries,guards=guards)


def _commit(service,token,project,run,subject,key,ledger,scan,error):
    service._auth(token,project,{'human','supervisor'})
    scope='context-note-audit:'+encoded([run,subject]);payload=[subject]
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE');service._run(db,project,run);member(db,project,run,subject)
        replay=service._replay(db,project,scope,key,payload)
        if replay:return replay
        try:
            if error is not None:raise error
            if _ledger(db,project,run,subject)!=ledger:raise ControlError('note_audit_ledger_changed')
            if any(_metadata(path)!=value for path,value in scan['guards'].items()):raise ControlError('note_audit_sources_changed')
            result=dict(status='inspected',entries=scan['entries'],accepted_revision=ledger[1],snapshot_stable=True)
        except (ValueError,OSError) as failure:
            result=dict(status='deferred',reason=getattr(failure,'code','note_audit_unavailable'),snapshot_stable=False,
                        entries=scan['entries'] if scan else [],accepted_revision_at_scan=ledger[1])
        result.update(audit_id=key,subject=subject,historical_receipt=True,sources_current_verified=False,adoption_changed=False,save_receipts_repaired=False,current_context_authorized=False,
                      recovery='保留全部文件。可用本人history_read核查完整草稿；是否修订或采纳须重新走原有校验。未登记不证明崩溃原因；损坏、临时文件和变化中的快照不自动修复。')
        service._remember(db,project,scope,key,payload,result)
        service._event(db,project,run,'research_note_audit',subject=subject,audit_id=key,status=result['status'],reason=result.get('reason'))
        return result


def audit(service,token,project,run,*,subject,idempotency_key):
    service._auth(token,project,{'human','supervisor'});service._identity(run,subject,idempotency_key)
    scope='context-note-audit:'+encoded([run,subject])
    with service._connect() as db:
        service._run(db,project,run);member(db,project,run,subject)
        replay=service._replay(db,project,scope,idempotency_key,[subject])
        if replay:return replay  # Historical inspection, never a current-use grant.
        ledger=_ledger(db,project,run,subject)
    scan=None;error=None
    try:scan=_scan(service,project,run,subject,ledger)
    except (ValueError,OSError) as failure:error=failure
    return _commit(service,token,project,run,subject,idempotency_key,ledger,scan,error)
