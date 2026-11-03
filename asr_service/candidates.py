"""Single UTF-8 Octave source artifacts; registration grants no execution rights."""
import hashlib
import json
import os
from pathlib import Path
import re
from .contracts import encoded
from .budgets import BudgetError
from .references import ReferenceStore

PROFILE='octave-candidate/1'
IMAGE='sha256:d40dc592523126c64abb42a730c4cc9652083efa5593d01e56238202200d9831'


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS asr_candidates(project TEXT,digest TEXT,record TEXT,PRIMARY KEY(project,digest))')


def register(service,token,project,*,request_key,source,entrypoint='candidate.m',profile=PROFILE,snapshot_ref=None,run=None):
    principal=service._auth(token,project,{'human','researcher'})
    service._identity(request_key)
    if type(source) is not str or not source or '\0' in source or len(source.encode('utf-8'))>65536:raise ValueError('invalid_candidate_source')
    if entrypoint!='candidate.m' or profile!=PROFILE:raise ValueError('capability_unavailable')
    if snapshot_ref is not None and (not isinstance(snapshot_ref,str) or re.fullmatch('[a-f0-9]{64}',snapshot_ref) is None):raise ValueError('invalid_snapshot_ref')
    body=source.encode('utf-8');sha=hashlib.sha256(body).hexdigest()
    payload=[principal['subject'],source,entrypoint,profile,snapshot_ref]
    if run is not None:service._identity(run);payload.append(run)
    with service._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        replay=service._replay(db,project,'candidate',request_key,payload)
        if replay:return replay
        if run is not None:service._run(db,project,run)
        root=service.path.parent/'asr-artifacts'/'candidates'/hashlib.sha256(project.encode()).hexdigest()/sha
        for parent in (root.parent.parent.parent,root.parent.parent,root.parent,root):
            if parent.is_symlink():raise ValueError('candidate_artifact_corrupt')
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=root/'candidate.m'
        if path.is_symlink():raise ValueError('candidate_artifact_corrupt')
        if path.exists():
            if path.read_bytes()!=body or path.stat().st_nlink!=1:raise ValueError('candidate_artifact_corrupt')
        else:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o444)
            with os.fdopen(fd,'wb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
        path.chmod(0o444)
        document=dict(profile=PROFILE,image_id=IMAGE,source_sha256=sha,size=len(body),entrypoint='candidate.m')
        digest=ReferenceStore._digest('candidate',document)
        db.execute('INSERT OR IGNORE INTO asr_references VALUES (?,?,?,?)',(project,'candidate',digest,encoded(document)))
        record=dict(digest=digest,**document,path=str(path.resolve()),snapshot_ref=snapshot_ref,author=principal['subject'])
        prior=db.execute('SELECT record FROM asr_candidates WHERE project=? AND digest=?',(project,digest)).fetchone()
        if prior:
            saved=json.loads(prior[0])
            if saved['source_sha256']!=sha or saved['path']!=record['path']:raise ValueError('candidate_artifact_corrupt')
        else:db.execute('INSERT INTO asr_candidates VALUES (?,?,?)',(project,digest,encoded(record)))
        service._remember(db,project,'candidate',request_key,payload,record)
        service._event(db,project,None,'candidate_registered',digest=digest,source_sha256=sha,snapshot_ref=snapshot_ref)
        return record


def resolve(db,project,digest):
    document=ReferenceStore.get_in_transaction(db,project,'candidate',digest)
    row=db.execute('SELECT record FROM asr_candidates WHERE project=? AND digest=?',(project,digest)).fetchone()
    if row is None:raise ValueError('candidate_not_registered')
    record=json.loads(row[0]);path=Path(record['path'])
    expected={k:record[k] for k in ('profile','image_id','source_sha256','size','entrypoint')}
    if document!=expected or path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_size!=record['size'] or hashlib.sha256(path.read_bytes()).hexdigest()!=record['source_sha256']:raise ValueError('candidate_artifact_corrupt')
    return record


def check_admission(db,project,run,digest,policy):
    """Count methods actually admitted in this run, including failed/cancelled work."""
    maximum=policy.get('max_candidate_revisions')
    if maximum is None:return
    admitted={}
    for body, in db.execute('SELECT record FROM asr_dispatch WHERE project=? AND run=?',(project,run)):
        trial=json.loads(body)
        if trial['execution_request'].get('profile')==PROFILE:
            admitted[trial['references']['candidate']]=True
    if digest not in admitted and len(admitted)>=maximum:
        raise BudgetError('candidate_revision_limit',details=dict(dimension='candidate_revisions',limit=maximum,spent=len(admitted),reserved=0,available=maximum-len(admitted),requested=1,scope='research_run'))
