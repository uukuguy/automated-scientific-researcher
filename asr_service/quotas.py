"""Append-only bounded observations; provider state never resets local usage."""
from datetime import datetime,timedelta,timezone
import json
from .contracts import encoded


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS asr_quota_observations(seq INTEGER PRIMARY KEY AUTOINCREMENT,project TEXT,run TEXT,record TEXT)')


def _instant(value):
    try:
        instant=datetime.fromisoformat(value)
        if instant.tzinfo is None or instant>datetime.now(timezone.utc)+timedelta(seconds=60):raise ValueError('invalid_time')
        return instant
    except (ValueError,TypeError):raise ValueError('invalid_quota_observation')


def apply_observation(service,db,project,run,running,*,provider,state,source,observed_at,author,bump_revision=True):
    instant=_instant(observed_at)
    if state not in ('unknown','available','rate_limited','exhausted') or source not in ('operator_observation','provider_response','runtime_rate_limit'):raise ValueError('invalid_quota_observation')
    rows=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_quota_observations WHERE project=? AND run=?',(project,run))]
    latest=max((datetime.fromisoformat(row['observed_at']) for row in rows if row['provider']==provider),default=None)
    applied=latest is None or instant>latest
    previous=running.get('quota_state','unknown')
    if applied:
        if state!='unknown' or previous not in ('rate_limited','exhausted'):running['quota_state']=state
        if state in ('rate_limited','exhausted'):
            running['admission_open']=False
            if running['state'] not in ('stopping','finishing','stopped','completed'):running['state']='paused'
        if bump_revision and (running.get('quota_state')!=previous or state in ('rate_limited','exhausted')):running['control_revision']+=1
    record=dict(provider=provider,state=state,source=source,observed_at=instant.astimezone(timezone.utc).isoformat(),recorded_at=datetime.now(timezone.utc).isoformat(),author=author,applied=applied,effective_state=running.get('quota_state','unknown'))
    db.execute('INSERT INTO asr_quota_observations(project,run,record) VALUES (?,?,?)',(project,run,encoded(record)))
    service._event(db,project,run,'quota_observed',**record)
    return record


def contract_state(db,project,run,provider,requested,previous,previous_provider):
    if requested in ('rate_limited','exhausted'):return requested
    if provider==previous_provider and previous in ('rate_limited','exhausted'):return previous
    observations=[json.loads(row[0]) for row in db.execute('SELECT record FROM asr_quota_observations WHERE project=? AND run=?',(project,run))]
    known=[row for row in observations if row['provider']==provider and row['applied'] and row['state']!='unknown']
    if known:
        latest=max(known,key=lambda row:datetime.fromisoformat(row['observed_at']))
        if latest['state'] in ('rate_limited','exhausted'):return latest['state']
    return requested


def observe(service,token,project,run,*,request_key,provider,state,source,observed_at):
    principal=service._auth(token,project,{'human','supervisor'});service._identity(request_key)
    _instant(observed_at)
    payload=[principal['subject'],provider,state,source,observed_at]
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        replay=service._replay(db,project,'quota_observation:'+run,request_key,payload)
        if replay:return replay
        running=service._run(db,project,run)
        policy=service._contract(db,project,running['contract_id'],running['contract_revision'])['document']['runtime_policy']
        if provider!=policy['provider']:raise ValueError('quota_provider_conflict')
        record=apply_observation(service,db,project,run,running,provider=provider,state=state,source=source,observed_at=observed_at,author=principal['subject'])
        db.execute('UPDATE asr_runs SET record=? WHERE project=? AND run=?',(encoded(running),project,run))
        service._remember(db,project,'quota_observation:'+run,request_key,payload,record)
        return record
