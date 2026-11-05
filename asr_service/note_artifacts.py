"""Resolve typed note citations to existing public study evidence and snapshots.

Returns provenance metadata, not raw data or a scientific validity judgement.
No caller-supplied host paths or evaluation-job assets are accepted.
"""
import codecs
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from asr_context import Material, material_digest
from .contracts import encoded
from .control import ControlError


def _safe_path(root, relative):
    if type(relative) is not str or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('unsafe_artifact_path')
    path=root/relative
    if root.is_symlink() or any(p.is_symlink() for p in [path,*path.parents] if p==root or p.is_relative_to(root)) or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('unsafe_artifact_path')
    return path


@dataclass(frozen=True)
class ArtifactFile:
    root: Path
    relative: str
    chunk_bytes: int
    witness: object
    policy_sha256: str


def _stream_file(root,relative,chunk_bytes,*,page=None):
    path=_safe_path(root,relative)
    if not path.is_file():raise ValueError('artifact_regular_file_required')
    digest=hashlib.sha256();size=0;characters=0;parts=[]
    decoder=codecs.getincrementaldecoder('utf-8')() if page is not None else None
    def collect(text):
        nonlocal characters
        start=characters;characters+=len(text)
        lo=max(0,page[0]-start);hi=min(len(text),page[0]+page[1]-start)
        if hi>lo:parts.append(text[lo:hi])
    with path.open('rb') as stream:
        while block:=stream.read(chunk_bytes):
            digest.update(block);size+=len(block)
            if decoder is not None:collect(decoder.decode(block))
    if decoder is not None:collect(decoder.decode(b'',final=True))
    return dict(sha256=digest.hexdigest(),bytes=size,text=''.join(parts),characters=characters)


def _attachment(root,relative,chunk_bytes,witnesses,policy_sha256):
    from .context_io import verify
    path=_safe_path(root,relative)
    witness=verify(str(path),lambda:_stream_file(root,relative,chunk_bytes))
    if witnesses is not None:witnesses.append(witness)
    return ArtifactFile(root,relative,chunk_bytes,witness,policy_sha256)


def _read_manifest(root,kind,target,chunk_bytes,witnesses):
    from .context_io import verify
    from .manifest_stream import select
    path=_safe_path(root,'manifest.json')
    if not path.is_file():raise ValueError('manifest_regular_file_required')
    result=verify(str(path),lambda:select(path,kind,target,chunk_bytes))
    if witnesses is not None:witnesses.append(result)
    return result.value


class PreparedArtifacts:
    def __init__(self,references,rows,witnesses,bindings):
        self.references=encoded(references);self.rows=rows;self.witnesses=witnesses;self.bindings=bindings

    def check(self,db,references):
        if encoded(references)!=self.references:raise ControlError('note_artifact_unavailable')
        for query,parameters,expected in self.bindings:
            if db.execute(query,parameters).fetchone()!=expected:raise ControlError('note_artifact_unavailable')
        try:
            for witness in self.witnesses:witness.check()
        except (ControlError,OSError):raise ControlError('note_artifact_unavailable') from None
        return self.rows


class _ObservedQueries:
    """Record only this resolver's SELECT/fetchone bindings for commit checks."""
    def __init__(self,db):self.db=db;self.bindings=[]

    def execute(self,query,parameters):
        if not query.lstrip().startswith('SELECT '):raise ValueError('artifact_read_only_required')
        value=self.db.execute(query,parameters).fetchone()
        self.bindings.append((query,parameters,value))
        class Row:
            def fetchone(self):return value
        return Row()


def prepare(db,service,project,run,references):
    tracked=_ObservedQueries(db);witnesses=[]
    rows=_resolve(tracked,service,project,run,references,witnesses=witnesses)
    return PreparedArtifacts(references,rows,witnesses,tracked.bindings)


def _resolve(db, service, project, run, references,*,witnesses=None):
    if type(references) is not list:raise ControlError('invalid_note_artifacts')
    result=[];seen=set()
    chunk_bytes=service.artifact_io_policy['limits']['artifact_read_chunk_bytes']['value']
    for ref in references:
        try:
            if type(ref) is not dict:raise ValueError('invalid_reference')
            identity='artifact:'+encoded(ref)
            if identity in seen:raise ValueError('duplicate_artifact')
            seen.add(identity)
            if ref.get('kind')=='snapshot' and set(ref)=={'kind','snapshot_sha256','path'}:
                digest=ref['snapshot_sha256']
                if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('invalid_snapshot')
                directory=service.path.parent/'snapshots'/digest
                selected=_read_manifest(directory,'snapshot',ref['path'],chunk_bytes,witnesses);manifest=selected['headers']
                if selected['sha256']!=digest or manifest['schema']!='asr-workspace-snapshot/1' or (manifest['project_id'],manifest['research_run_id'])!=(project,run):raise ValueError('snapshot_mismatch')
                entry=selected['entry']
                attachment=_attachment(directory/'files',ref['path'],chunk_bytes,witnesses,service.artifact_io_policy['sha256']);summary=attachment.witness.value
                if summary['sha256']!=entry['sha256'] or summary['bytes']!=entry['size']:raise ValueError('snapshot_file_mismatch')
                provenance=dict(snapshot_sha256=digest)
            elif ref.get('kind')=='trial' and set(ref)=={'kind','trial_id','path'}:
                # Excludes raw input payloads and independent evaluation assets.
                if ref['path'] not in {'study-result.json','study-events.json','validation.json','result.json'}:raise ValueError('unsupported_trial_file')
                row=db.execute('SELECT attempt,state FROM asr_dispatch WHERE project=? AND run=? AND trial=?',(project,run,ref['trial_id'])).fetchone()
                if not row or row[1] not in {'succeeded','failed','timed_out','interrupted'}:raise ValueError('trial_unavailable')
                raw=db.execute('SELECT record FROM asr_executions WHERE attempt=?',(row[0],)).fetchone()
                execution=json.loads(raw[0]) if raw else {}
                if (execution.get('project'),execution.get('run'),execution.get('trial'),execution.get('attempt'))!=(project,run,ref['trial_id'],row[0]):raise ValueError('execution_mismatch')
                report=execution.get('report') or {}
                if report.get('execution_exited') is not True:raise ValueError('execution_unsettled')
                directory=Path(report['evidence_path'])
                selected=_read_manifest(directory,'trial',ref['path'],chunk_bytes,witnesses);manifest=selected['headers']
                if selected['sha256']!=report['manifest_hash'] or (manifest['trial_id'],manifest['execution_attempt_id'],manifest['status'])!=(ref['trial_id'],row[0],row[1]):raise ValueError('manifest_mismatch')
                attachment=_attachment(directory,ref['path'],chunk_bytes,witnesses,service.artifact_io_policy['sha256']);summary=attachment.witness.value;entry=selected['entry']
                if summary['sha256']!=entry['sha256'] or summary['bytes']!=entry['bytes']:raise ValueError('trial_file_mismatch')
                provenance=dict(trial_id=ref['trial_id'],execution_attempt_id=row[0],manifest_sha256=report['manifest_hash'])
            else:raise ValueError('unsupported_artifact_kind')
            metadata=dict(reference=ref,sha256=summary['sha256'],bytes=summary['bytes'],provenance=provenance)
            result.append((Material(identity,metadata['sha256'],encoded(metadata)),attachment))
        except (ValueError,KeyError,TypeError,OSError,StopIteration) as cause:
            error=ControlError('note_artifact_unavailable')
            error.details=dict(category=type(cause).__name__,check=str(cause) if isinstance(cause,ValueError) else 'artifact_lookup_or_read_failed')
            raise error from None
    return result


def resolve(db, service, project, run, references,*,prepared=None):
    rows=prepared.check(db,references) if prepared is not None else _resolve(db,service,project,run,references)
    return [material for material,body in rows]


def read_page(db, service, project, run, reference, *, offset=0, limit=8000,prepared=None):
    """Return a verified UTF-8 text page. Offsets count Unicode characters."""
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=16000:
        error=ControlError('invalid_note_source_page')
        error.details=dict(offset=offset if type(offset) is int else type(offset).__name__,limit=limit if type(limit) is int else type(limit).__name__,max_characters=16000,unit='unicode_characters',
                           purpose='Bound one tool response and prevent refilling context with a large artifact.',
                           recovery='Use limit 1..16000 and follow next_offset; no source was truncated.')
        raise error
    material,attachment=(prepared.check(db,[reference]) if prepared is not None else _resolve(db,service,project,run,[reference]))[0]
    try:
        original=attachment.witness.check()
        page=_stream_file(attachment.root,attachment.relative,attachment.chunk_bytes,page=(offset,limit))
        attachment.witness.check()
        if page['sha256']!=original['sha256'] or page['bytes']!=original['bytes']:raise ControlError('note_artifact_unavailable')
    except UnicodeError:raise ControlError('note_source_not_utf8') from None
    except (ValueError,OSError):raise ControlError('note_artifact_unavailable') from None
    if offset>page['characters']:raise ControlError('note_source_offset_out_of_range')
    end=min(page['characters'],offset+limit)
    return dict(status='source_page',reference=reference,sha256=material.revision,source_material_sha256=material_digest(material),source_bytes=page['bytes'],
                read_chunk_bytes=attachment.chunk_bytes,capacity_policy_sha256=attachment.policy_sha256,
                offset=offset,end_offset=end,total_characters=page['characters'],offset_unit='unicode_characters',
                text=page['text'],has_more=end<page['characters'],next_offset=end if end<page['characters'] else None,
                partial=offset>0 or end<page['characters'])
