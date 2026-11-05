"""Member-owned research-note adoption in the existing Control transaction ledger."""
from dataclasses import asdict
import json

from asr_context import Material
from asr_context.notes import restore
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


def _prepare_operation(service,token,project,run,*,operation,idempotency_key,text=None,
                       source_sequences=None,revision=None,expected_note=None,artifact_references=None,
                       artifact_reference=None,offset=0,limit=8000):
    principal=service._auth(token,project,{'researcher'});service._identity(run,idempotency_key)
    if operation not in ('save','adopt','read','source_read','history_read'):raise ControlError('invalid_note_operation')
    owner=principal['subject'];scope=encoded([project,run,owner])
    payload=[operation,text,source_sequences,revision,expected_note,artifact_references]
    with service._connect() as db:
        state=service._run(db,project,run);principal_role(db,project,run,principal)
        if operation not in ('read','source_read','history_read') and state['state'] not in ('running','paused'):raise ControlError('note_run_closed')
        if operation in ('save','adopt'):
            replay=service._replay(db,project,'research-note:'+scope,idempotency_key,payload)
            if replay:return dict(replay=replay)
        row=db.execute('SELECT revision FROM asr_note_heads WHERE project=? AND run=? AND owner=?',(project,run,owner)).fetchone()
        head=row[0] if row else None
        from .note_io import PreparedStore
        from .note_artifacts import prepare,resolve,read_page
        store=PreparedStore(service,project,run,owner)
        selected=revision if revision is not None else head
        item=dict(head=head,store=store,payload=payload,scope=scope,owner=owner,selected=selected,
                  sources=None,artifacts=None,references=[],sequences=[],saved_revision=None)
        if operation=='save':
            if head is not None:store.load(head)
            sequences=[] if source_sequences is None else source_sequences
            references=[] if artifact_references is None else artifact_references
            artifacts=prepare(db,service,project,run,references)
            sources=_materials(db,service,project,run,sequences,saving=True)+resolve(db,service,project,run,references,prepared=artifacts)
            new=store.store.save(text,sources=sources,parent=head)
            try:store.load(new)
            except (ValueError,OSError) as cause:
                error=cause if isinstance(cause,ControlError) else ControlError('note_unavailable_or_invalid')
                error.details=dict(getattr(error,'details',{}),retained_draft_revision=new,adopted=False)
                raise error from None
            item.update(saved_revision=new,result=dict(status='saved',revision=new,accepted_revision=head),
                        sources=sources,sequences=sequences,references=references,artifacts=artifacts)
        elif selected is None:
            if operation in ('adopt','source_read'):raise ControlError('note_revision_required')
            item['result']=dict(status='empty',accepted_revision=head)
        else:
            note=store.load(selected)
            if operation=='history_read':
                item['result']=dict(status='historical_note',revision=selected,note=note,eligible_for_current_context=False)
            else:
                sequences=[int(ref['id'].split(':',1)[1]) for ref in note['sources'] if ref['id'].startswith('organization:')]
                refs=[json.loads(ref['id'][len('artifact:'):]) for ref in note['sources'] if ref['id'].startswith('artifact:')]
                if operation=='source_read':
                    if artifact_reference not in refs:raise ControlError('note_source_not_referenced')
                    artifacts=prepare(db,service,project,run,[artifact_reference])
                    page=read_page(db,service,project,run,artifact_reference,offset=offset,limit=limit,prepared=artifacts)
                    binding=next(ref for ref in note['sources'] if ref['id']=='artifact:'+encoded(artifact_reference))
                    if binding['sha256']!=page['source_material_sha256']:raise ControlError('note_sources_changed')
                    item.update(result=page,artifacts=artifacts,references=[artifact_reference])
                else:
                    artifacts=prepare(db,service,project,run,refs)
                    sources=_materials(db,service,project,run,sequences)+resolve(db,service,project,run,refs,prepared=artifacts)
                    restored=restore(store,accepted_revision=selected,materials=sources,role=owner)
                    if operation=='adopt':
                        if head!=expected_note or note['parent']!=head:raise ControlError('revision_conflict')
                        if restored['status']!='ready':raise ControlError('note_sources_changed')
                        result=dict(status='adopted',revision=selected,accepted_revision=selected)
                    else:
                        if 'material' in restored:restored['material']=asdict(restored['material'])
                        result=dict(status='read',accepted_revision=head,requested_revision=selected,restoration=restored)
                    item.update(result=result,sources=sources,sequences=sequences,references=refs,artifacts=artifacts)
    return item


def _commit_operation(service,token,project,run,item,*,operation,idempotency_key,**arguments):
    principal=service._auth(token,project,{'researcher'});owner=principal['subject']
    if owner!=item['owner']:raise ControlError('forbidden')
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        state=service._run(db,project,run);principal_role(db,project,run,principal)
        if operation in ('save','adopt') and state['state'] not in ('running','paused'):raise ControlError('note_run_closed')
        scope='research-note:'+item['scope']
        if operation in ('save','adopt'):
            replay=service._replay(db,project,scope,idempotency_key,item['payload'])
            if replay:return replay
        row=db.execute('SELECT revision FROM asr_note_heads WHERE project=? AND run=? AND owner=?',(project,run,owner)).fetchone()
        head=row[0] if row else None
        if head!=item['head']:raise ControlError('revision_conflict')
        item['store'].check()
        if item['artifacts'] is not None:item['artifacts'].check(db,item['references'])
        if item['sources'] is not None:
            from .note_artifacts import resolve
            current=_materials(db,service,project,run,item['sequences'],saving=operation=='save')+resolve(db,service,project,run,item['references'],prepared=item['artifacts'])
            if current!=item['sources']:raise ControlError('note_sources_changed')
        result=item['result']
        if operation=='adopt':
            db.execute('INSERT INTO asr_note_heads VALUES (?,?,?,?) ON CONFLICT(project,run,owner) DO UPDATE SET revision=excluded.revision',(project,run,owner,item['selected']))
        if operation in ('save','adopt'):
            service._remember(db,project,scope,idempotency_key,item['payload'],result)
            service._event(db,project,run,'research_note_'+operation,owner=owner,revision=result['revision'],accepted_revision=result['accepted_revision'])
        elif operation=='history_read' and item['selected'] is not None:
            service._event(db,project,run,'research_note_history_read',owner=owner,revision=item['selected'])
        elif operation=='source_read':
            service._event(db,project,run,'research_note_source_read',owner=owner,note_revision=item['selected'],
                reference=arguments.get('artifact_reference'),sha256=result['sha256'],offset=result['offset'],end_offset=result['end_offset'],
                read_chunk_bytes=result['read_chunk_bytes'],capacity_policy_sha256=result['capacity_policy_sha256'])
        return result


def _operation(service,token,project,run,**arguments):
    item=None
    try:
        item=_prepare_operation(service,token,project,run,**arguments)
        if 'replay' in item:return item['replay']
        return _commit_operation(service,token,project,run,item,**arguments)
    except (ValueError,OSError) as error:
        if not isinstance(error,ControlError):error=ControlError('note_unavailable_or_invalid')
        if item and item.get('saved_revision'):
            error.details=dict(getattr(error,'details',{}),retained_draft_revision=item['saved_revision'],adopted=False)
        raise error


def operation(service, token, project, run, **arguments):
    try:return _operation(service,token,project,run,**arguments)
    except ControlError as error:
        if getattr(error,'details',{}).get('retained_draft_revision') or error.code in ('note_sources_changed','note_source_not_current','note_source_unavailable','note_artifact_unavailable','invalid_note_source_page','note_source_not_referenced','revision_conflict','note_unavailable_or_invalid','context_source_changed','organization_member_unavailable'):
            principal=service._auth(token,project,{'researcher'})
            with service._connect() as db:
                service._event(db,project,run,'research_note_deferred',owner=principal['subject'],
                               reason=error.code,operation=arguments.get('operation'),request_key=arguments.get('idempotency_key'),details=getattr(error,'details',None))
            error.details=dict(getattr(error,'details',{}),reason=error.code,action='not_applied',recovery='Read current sources and accepted note. Preserve old notes; revise explicitly without repeating experiments.')
        raise
