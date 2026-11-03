"""Derive role wakeups from Control records, not hard-coded research topics.

This is a serial delivery adapter around actual AAR role sessions. Scientific
choices are authored organization records; Control still owns task/runtime facts.
"""
import hashlib
import json
from asr_service.organization import current, latest, member, require
from asr_service.contracts import encoded


def pending(service, token, project, run):
    service._auth(token, project, {'human','supervisor'})
    with service._connect() as db:
        service._run(db, project, run)
        members={r['entity_id']:r['document'] for r in current(db,project,run,'member')}
        organizers=[name for name,doc in members.items() if doc==dict(role='organizer',enabled=True)]
        require(len(organizers)==1,'organization_organizer_required')
        rows=db.execute('SELECT record FROM asr_organization WHERE project=? AND run=? ORDER BY seq',(project,run)).fetchall()
        result=[]
        for row in rows:
            record=json.loads(row[0]);doc=record['document'];targets=[];kind=record['kind']
            if kind=='policy' and record['revision']==1:targets=organizers
            elif kind=='message':targets=doc['recipients']
            elif kind=='direction' and doc['status']=='active':targets=[doc['owner']]
            elif kind=='task' and doc['status']=='assigned':targets=[doc['assignee']]
            elif kind=='task' and doc['status'] in ('completed','cancelled'):
                direction=latest(db,project,run,'direction',doc['direction_id'])
                targets=[direction['document']['owner']]
            for target in targets:
                identity=hashlib.sha256(encoded([project,run,record['seq'],target]).encode()).hexdigest()
                if db.execute('SELECT 1 FROM asr_requests WHERE project=? AND scope=? AND request_key=?',
                              (project,'organization-delivery:'+run,identity)).fetchone():continue
                # Retain source even if newer state supersedes its instruction;
                # recipient must inspect authoritative latest state before action.
                require(target in members and members[target]['enabled'],'organization_recipient_disabled')
                result.append(dict(delivery_id=identity,recipient=target,source_seq=record['seq'],
                    kind=kind,entity_id=record['entity_id'],revision=record['revision']))
        return result


def acknowledge(service, token, project, run, deliveries, session_id):
    principal=service._auth(token,project,{'human','supervisor'})
    require(type(deliveries) is list and bool(deliveries),'organization_deliveries_required')
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT record FROM asr_runtime_sessions WHERE project=? AND run=? AND session_id=?',
                       (project,run,session_id)).fetchone()
        require(row is not None,'runtime_not_found')
        session=json.loads(row[0]);binding=session.get('organization_binding') or {}
        require(session['state']=='exited' and session.get('execution_exited') is True and bool(session.get('process_identity')),'execution_not_reconciled')
        receipts=[]
        for delivery in deliveries:
            require(set(delivery)=={'delivery_id','recipient','source_seq','kind','entity_id','revision'},'invalid_organization_delivery')
            require(binding.get('subject')==delivery['recipient'],'organization_delivery_actor_mismatch')
            source=db.execute('SELECT record FROM asr_organization WHERE project=? AND run=? AND seq=?',
                              (project,run,delivery['source_seq'])).fetchone()
            require(source is not None,'organization_delivery_source_missing')
            source=json.loads(source[0])
            require(all(source[k]==delivery[k] for k in ('kind','entity_id','revision')),'organization_delivery_source_mismatch')
            identity=hashlib.sha256(encoded([project,run,source['seq'],delivery['recipient']]).encode()).hexdigest()
            require(identity==delivery['delivery_id'],'invalid_organization_delivery')
            payload=[principal['subject'],delivery,session_id]
            replay=service._replay(db,project,'organization-delivery:'+run,identity,payload)
            if replay:receipts.append(replay);continue
            receipt=dict(delivery,session_id=session_id,author=principal['subject'],
                status='exited_session_host_reported_settled',boundary='Delivery acknowledgement, not scientific approval or proof that every requested task completed.')
            service._remember(db,project,'organization-delivery:'+run,identity,payload,receipt)
            service._event(db,project,run,'organization_delivery_acknowledged',**receipt)
            receipts.append(receipt)
        return receipts
