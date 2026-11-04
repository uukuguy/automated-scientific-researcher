"""Member-owned research-note adoption in the existing Control transaction ledger."""
from dataclasses import asdict
import hashlib
import json

from asr_context import Material
from asr_context.notes import NoteStore, restore
from .contracts import encoded
from .control import ControlError
from .organization import principal_role, latest


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS asr_note_heads(project TEXT, run TEXT, owner TEXT, revision TEXT, PRIMARY KEY(project,run,owner))')


def _materials(db, service, project, run, sequences, *, saving=False):
    if type(sequences) is not list or any(type(n) is not int or n<1 for n in sequences) or len(set(sequences))!=len(sequences):
        raise ControlError('invalid_note_sources')
    state=service._run(db,project,run)
    rows=[Material('control','current',encoded({k:state[k] for k in ('contract_revision','control_revision')}))]
    for sequence in sequences:
        raw=db.execute('SELECT record FROM asr_organization WHERE project=? AND run=? AND seq=?',(project,run,sequence)).fetchone()
        if not raw:raise ControlError('note_source_unavailable')
        source=json.loads(raw[0]);current=latest(db,project,run,source['kind'],source['entity_id'])
        if saving and current['seq']!=sequence:raise ControlError('note_source_not_current')
        # Stable logical ID makes a newer version visible as a changed source.
        rows.append(Material('organization:'+str(sequence),str(current['revision']),encoded(current)))
    return rows


def _operation(service, token, project, run, *, operation, idempotency_key, text=None,
              source_sequences=None, revision=None, expected_note=None, artifact_references=None):
    principal=service._auth(token,project,{'researcher'})
    service._identity(run,idempotency_key)
    if operation not in ('save','adopt','read'):raise ControlError('invalid_note_operation')
    owner=principal['subject'];scope=encoded([project,run,owner])
    payload=[operation,text,source_sequences,revision,expected_note,artifact_references]
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        state=service._run(db,project,run);principal_role(db,project,run,principal)
        if operation!='read' and state['state'] not in ('running','paused'):raise ControlError('note_run_closed')
        request_scope='research-note:'+scope
        if operation!='read':
            replay=service._replay(db,project,request_scope,idempotency_key,payload)
            if replay:return replay
        row=db.execute('SELECT revision FROM asr_note_heads WHERE project=? AND run=? AND owner=?',(project,run,owner)).fetchone()
        head=row[0] if row else None
        store=NoteStore(service.path.parent/'research-notes'/hashlib.sha256(scope.encode()).hexdigest(),scope=scope)
        try:
            if operation=='save':
                sources=_materials(db,service,project,run,[] if source_sequences is None else source_sequences,saving=True)
                from .note_artifacts import resolve
                sources+=resolve(db,service,project,run,[] if artifact_references is None else artifact_references)
                new=store.save(text,sources=sources,parent=head)
                result=dict(status='saved',revision=new,accepted_revision=head)
            else:
                selected=revision if revision is not None else head
                if selected is None:
                    if operation=='adopt':raise ControlError('note_revision_required')
                    return dict(status='empty',accepted_revision=head)
                note=store.read(selected)
                sequences=[int(ref['id'].split(':',1)[1]) for ref in note['sources'] if ref['id'].startswith('organization:')]
                from .note_artifacts import resolve
                refs=[json.loads(ref['id'][len('artifact:'):]) for ref in note['sources'] if ref['id'].startswith('artifact:')]
                sources=_materials(db,service,project,run,sequences)+resolve(db,service,project,run,refs)
                restored=restore(store,accepted_revision=selected,materials=sources,role=owner)
                if operation=='adopt':
                    if head!=expected_note or note['parent']!=head:raise ControlError('revision_conflict')
                    if restored['status']!='ready':raise ControlError('note_sources_changed')
                    db.execute('INSERT INTO asr_note_heads VALUES (?,?,?,?) ON CONFLICT(project,run,owner) DO UPDATE SET revision=excluded.revision',(project,run,owner,selected))
                    result=dict(status='adopted',revision=selected,accepted_revision=selected)
                else:
                    if 'material' in restored:restored['material']=asdict(restored['material'])
                    return dict(status='read',accepted_revision=head,requested_revision=selected,restoration=restored)
        except ValueError as error:
            if isinstance(error,ControlError):raise
            raise ControlError('note_unavailable_or_invalid') from None
        service._remember(db,project,request_scope,idempotency_key,payload,result)
        service._event(db,project,run,'research_note_'+operation,owner=owner,revision=result['revision'],accepted_revision=result['accepted_revision'])
        return result


def operation(service, token, project, run, **arguments):
    try:return _operation(service,token,project,run,**arguments)
    except ControlError as error:
        if error.code in ('note_sources_changed','note_source_not_current','note_source_unavailable','note_artifact_unavailable','revision_conflict'):
            principal=service._auth(token,project,{'researcher'})
            with service._connect() as db:
                principal_role(db,project,run,principal)
                service._event(db,project,run,'research_note_deferred',owner=principal['subject'],
                               reason=error.code,operation=arguments.get('operation'),request_key=arguments.get('idempotency_key'),details=getattr(error,'details',None))
            error.details=dict(getattr(error,'details',{}),reason=error.code,action='not_applied',recovery='Read current sources and accepted note. Preserve old notes; revise explicitly without repeating experiments.')
        raise
