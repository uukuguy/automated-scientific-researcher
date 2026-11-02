"""Actual pinned AAR ORM organization behind the existing ASR control writer.

Upstream source is loaded from a validated private checkout, never vendored.
Actual Experiment/Finding mapped classes define the stored rows and perform reads.
Writes use their mapped column definitions inside the *same* SQLite transaction
as ASR admission, avoiding a second writer/scheduler or a two-database saga.
"""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime

from asr_service.contracts import encoded
from asr_service.control import ControlError

_MODELS={}


def _load_models(checkout):
    checkout=Path(checkout).resolve()
    pin=json.loads(Path(__file__).with_name('upstream.json').read_text())
    revision=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
    if revision!=pin['revision']: raise ValueError('upstream_revision_mismatch')
    relative='w2s_research/web_ui/backend/models.py';source=checkout/relative
    if hashlib.sha256(source.read_bytes()).hexdigest()!=pin['files'][relative]: raise ValueError('upstream_models_modified')
    key=str(checkout)
    if key in _MODELS:return _MODELS[key]
    sys.path.insert(0,key)
    # Package paths may outlive a temporary test checkout. Keep actual source
    # imports on the explicitly selected pinned tree; no stub modules are used.
    for name in ('w2s_research','w2s_research.web_ui','w2s_research.web_ui.backend'):
        module=importlib.import_module(name)
        module.__path__=[str(checkout/Path(*name.split('.')))]
    name='asr_aar_models_'+hashlib.sha256(key.encode()).hexdigest()[:16]
    spec=importlib.util.spec_from_file_location(name,source)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    db=module.db
    for cls in (module.Experiment,module.Finding):
        cls.asr_project_id=db.Column(db.String(256),nullable=True,index=True)
        cls.asr_research_run_id=db.Column(db.String(256),nullable=True,index=True)
    module.Finding.asr_finding_id=db.Column(db.String(256),nullable=True)
    module.Finding.asr_revision=db.Column(db.Integer,nullable=True)
    module.Finding.asr_evidence=db.Column(db.Text,nullable=True)
    module.Finding.asr_snapshot_path=db.Column(db.Text,nullable=True)
    _MODELS[key]=module
    return module


class UpstreamAdapter:
    def __init__(self, service, *, checkout):
        from flask import Flask
        self.service=service;self.checkout=Path(checkout).resolve()
        from .prepare_upstream import verify_worker_patch
        from .source_integrity import verify_source_tree
        verify_worker_patch(self.checkout)
        allowed={'w2s_research/web_ui/backend/worker.py'}
        if (self.checkout/'.asr-loop-patch.json').exists():
            from .loop_patch import verify_loop_patch
            verify_loop_patch(self.checkout)
            allowed.update({'w2s_research/research_loop/agent.py','w2s_research/research_loop/tools/findings_sync.py'})
        verify_source_tree(self.checkout,allowed_changes=allowed)
        self.models=_load_models(self.checkout)
        self.app=Flask('asr-aar-'+str(id(self)))
        self.app.config.update(ASR_MODE=True,SQLALCHEMY_DATABASE_URI='sqlite:///'+str(service.path.resolve()),SQLALCHEMY_TRACK_MODIFICATIONS=False)
        self.models.db.init_app(self.app)
        with self.app.app_context():
            self.models.db.create_all()
        # Migrate existing upstream tables additively; legacy rows remain legacy.
        with service._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for table,columns in {'experiments':{'asr_project_id':'TEXT','asr_research_run_id':'TEXT'},'findings':{'asr_project_id':'TEXT','asr_research_run_id':'TEXT','asr_finding_id':'TEXT','asr_revision':'INTEGER','asr_evidence':'TEXT','asr_snapshot_path':'TEXT'}}.items():
                present={row[1] for row in db.execute('PRAGMA table_info('+table+')')}
                for name,kind in columns.items():
                    if name not in present:db.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+kind)
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS asr_experiment_mapping ON experiments(asr_project_id,asr_research_run_id) WHERE asr_project_id IS NOT NULL')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS asr_finding_revision ON findings(asr_project_id,asr_research_run_id,asr_finding_id,asr_revision) WHERE asr_project_id IS NOT NULL')

    @staticmethod
    def _insert(db,model,values):
        """Use actual upstream mapped columns/defaults; owner controls commit."""
        instance=model(**values)
        supplied=dict(values)
        for column in model.__table__.columns:
            if column.name not in supplied and column.default is not None:
                default=column.default.arg
                supplied[column.name]=default(None) if callable(default) else default
        for name,value in supplied.items():
            if name not in model.__table__.columns: raise ValueError('unmapped_upstream_field')
            if isinstance(value,datetime): supplied[name]=value.isoformat(' ')
        names=list(supplied)
        cursor=db.execute('INSERT INTO '+model.__table__.name+' ('+','.join(names)+') VALUES ('+','.join('?' for _ in names)+')',[supplied[name] for name in names])
        return cursor.lastrowid

    def create_run(self, token, project, run, contract_id, contract_revision, *, idempotency_key):
        service=self.service;principal=service._auth(token,project,{'human'})
        service._identity(run,contract_id,idempotency_key);service._revision(contract_revision)
        payload=[principal['subject'],run,contract_id,contract_revision]
        with service._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=service._replay(db,project,'aar_create_run',idempotency_key,payload)
            if replay:return replay
            contract=service._contract(db,project,contract_id,contract_revision)
            if db.execute('SELECT 1 FROM experiments WHERE asr_project_id=? AND asr_research_run_id=?',(project,run)).fetchone():raise ControlError('run_mapping_conflict')
            idea=db.execute('SELECT id FROM ideas WHERE name=?',(project,)).fetchone()
            if not idea:self._insert(db,self.models.Idea,dict(name=project,uid=hashlib.sha256(project.encode()).hexdigest(),idea_json=encoded(contract['document']['objective']),description=contract['document']['objective']['question'],source='asr'))
            rowid=self._insert(db,self.models.Experiment,dict(idea_name=project,idea_title=contract['document']['objective']['question'],idea_description=contract['document']['objective']['scope'],dataset='asr-powerflow',weak_model='',strong_model='',status='running',execution_mode='asr',run_id=run,idea_uid=project,asr_project_id=project,asr_research_run_id=run))
            record=service.create_run_in_transaction(db,token,project,run,'aar-experiment:'+str(rowid),contract_id,contract_revision,idempotency_key='aar:'+idempotency_key)
            service._remember(db,project,'aar_create_run',idempotency_key,payload,record)
            service._event(db,project,run,'aar_experiment_bound',upstream_experiment_id=rowid)
            return record

    def experiment(self, token, project, run):
        service=self.service;service._auth(token,project)
        binding=service.get_run(token,project,run)
        with self.app.app_context():
            actual=self.models.Experiment.query.filter_by(asr_project_id=project,asr_research_run_id=run).one_or_none()
            if actual is None or binding['experiment_id']!='aar-experiment:'+str(actual.id) or actual.execution_mode!='asr':raise ControlError('actual_experiment_binding_required')
            return dict(actual.to_dict(),asr_project_id=actual.asr_project_id,asr_research_run_id=actual.asr_research_run_id)

    def legacy_worker(self):
        """Actual guarded upstream class; ASR app cannot start its scheduler."""
        from .prepare_upstream import verify_worker_patch
        verify_worker_patch(self.checkout)
        source=self.checkout/'w2s_research/web_ui/backend/worker.py'
        # Bind its absolute models import to the same actual mapped classes.
        sys.modules['w2s_research.web_ui.backend.models']=self.models
        spec=importlib.util.spec_from_file_location('asr_guarded_legacy_worker_'+str(id(self)),source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.ExperimentWorker(self.app)

    def sync_findings(self, token, project, run):
        service=self.service;service._auth(token,project,{'human','supervisor'})
        self.experiment(token,project,run)
        with service._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for body, in db.execute('SELECT record FROM asr_findings WHERE project=? AND run=? ORDER BY finding_id,revision',(project,run)).fetchall():
                finding=json.loads(body)
                config=dict(status='candidate',limitations=finding['limitations'],asr_author=finding['author'])
                if 'hypothesis_evidence' in finding:config['hypothesis_evidence']=finding['hypothesis_evidence']
                prior=db.execute('SELECT content,asr_evidence,config FROM findings WHERE asr_project_id=? AND asr_research_run_id=? AND asr_finding_id=? AND asr_revision=?',(project,run,finding['finding_id'],finding['revision'])).fetchone()
                if prior:
                    if prior!=(finding['statement'],encoded(finding['evidence']),encoded(config)):raise ValueError('upstream_finding_projection_corrupt')
                    continue
                post=hashlib.sha256(encoded([project,run,finding['finding_id'],finding['revision']]).encode()).hexdigest()
                self._insert(db,self.models.Finding,dict(post_id=post,title=finding['finding_id'],content=finding['statement'],finding_type='result',idea_uid=project,idea_name=project,run_id=run,dataset='asr-powerflow',config=encoded(config),asr_project_id=project,asr_research_run_id=run,asr_finding_id=finding['finding_id'],asr_revision=finding['revision'],asr_evidence=encoded(finding['evidence'])))
                service._event(db,project,run,'aar_finding_projected',finding_id=finding['finding_id'],revision=finding['revision'],post_id=post)
        return [row for row in self.forum(token,project) if row['asr_research_run_id']==run and row['finding_type']!='snapshot']

    @staticmethod
    def _finding(row):
        return dict(row.to_dict(),asr_project_id=row.asr_project_id,asr_research_run_id=row.asr_research_run_id,asr_finding_id=row.asr_finding_id,asr_revision=row.asr_revision,asr_evidence=json.loads(row.asr_evidence or '[]'),asr_snapshot_path=row.asr_snapshot_path)

    def forum(self, token, project):
        self.service._auth(token,project)
        with self.app.app_context():
            return [self._finding(row) for row in self.models.Finding.query.filter_by(asr_project_id=project).order_by(self.models.Finding.id).all()]

    @staticmethod
    def _snapshot(path,project,run,digest):
        path=Path(path)
        if path.is_symlink():raise ValueError('snapshot_corrupt')
        raw=(path/'manifest.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('snapshot_corrupt')
        manifest=json.loads(raw)
        if manifest.get('project_id')!=project or manifest.get('research_run_id')!=run:raise ValueError('snapshot_scope_conflict')
        for entry in manifest['files']:
            name=Path(entry['path'])
            source=path/'files'/name
            if name.is_absolute() or '..' in name.parts or source.is_symlink() or not source.resolve().is_relative_to((path/'files').resolve()) or hashlib.sha256(source.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('snapshot_corrupt')
        return manifest

    def register_snapshot(self, token, project, run, *, snapshot_root, digest):
        service=self.service;service._auth(token,project,{'human','supervisor'})
        self.experiment(token,project,run)
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('invalid_snapshot_digest')
        path=Path(snapshot_root).resolve()/digest
        manifest=self._snapshot(path,project,run,digest)
        with service._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT id FROM findings WHERE commit_id=?',(digest,)).fetchone()
            if not prior:
                self._insert(db,self.models.Finding,dict(post_id='snapshot-'+digest,title='Snapshot '+digest[:12],content='Frozen local research workspace; not a numerical result',finding_type='snapshot',idea_uid=project,idea_name=project,run_id=run,commit_id=digest,files_snapshot=encoded(manifest['files']),asr_project_id=project,asr_research_run_id=run,asr_finding_id='snapshot:'+digest,asr_revision=1,asr_evidence='[]',asr_snapshot_path=str(path)))
                service._event(db,project,run,'aar_snapshot_projected',snapshot_sha256=digest)
        return next(row for row in self.snapshots(token,project,run) if row['commit_id']==digest)

    def snapshots(self, token, project, run):
        self.service._auth(token,project)
        return [row for row in self.forum(token,project) if row['asr_research_run_id']==run and row['commit_id'] is not None]

    def restore_snapshot(self, token, project, run, digest, destination):
        self.service._auth(token,project,{'human','supervisor'})
        row=next((row for row in self.snapshots(token,project,run) if row['commit_id']==digest),None)
        if row is None:raise ValueError('snapshot_not_found')
        source=Path(row['asr_snapshot_path']);manifest=self._snapshot(source,project,run,digest)
        destination=Path(destination)
        if destination.exists():raise ValueError('destination_exists')
        destination.mkdir(parents=True)
        for entry in manifest['files']:
            target=destination/entry['path'];target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((source/'files'/entry['path']).read_bytes())
        return dict(snapshot_sha256=digest,destination=str(destination.resolve()))
