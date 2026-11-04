"""Resolve typed note citations to existing public study evidence and snapshots.

Returns provenance metadata, not raw data or a scientific validity judgement.
No caller-supplied host paths or evaluation-job assets are accepted.
"""
import hashlib
import json
from pathlib import Path
import re

from asr_context import Material
from .contracts import encoded
from .control import ControlError


def _hash(body):return hashlib.sha256(body).hexdigest()


def _safe_file(root, relative):
    if type(relative) is not str or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('unsafe_artifact_path')
    path=root/relative
    if root.is_symlink() or any(p.is_symlink() for p in [path,*path.parents] if p==root or p.is_relative_to(root)) or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('unsafe_artifact_path')
    return path.read_bytes()


def resolve(db, service, project, run, references):
    if type(references) is not list:raise ControlError('invalid_note_artifacts')
    result=[];seen=set()
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
                body=_safe_file(directory,'manifest.json');manifest=json.loads(body)
                if _hash(body)!=digest or manifest['schema']!='asr-workspace-snapshot/1' or (manifest['project_id'],manifest['research_run_id'])!=(project,run):raise ValueError('snapshot_mismatch')
                entry=next(x for x in manifest['files'] if x['path']==ref['path'])
                body=_safe_file(directory/'files',ref['path'])
                if _hash(body)!=entry['sha256'] or len(body)!=entry['size']:raise ValueError('snapshot_file_mismatch')
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
                manifest_body=_safe_file(directory,'manifest.json');manifest=json.loads(manifest_body)
                if _hash(manifest_body)!=report['manifest_hash'] or (manifest['trial_id'],manifest['execution_attempt_id'],manifest['status'])!=(ref['trial_id'],row[0],row[1]):raise ValueError('manifest_mismatch')
                body=_safe_file(directory,ref['path']);entry=manifest['artifacts'][ref['path']]
                if _hash(body)!=entry['sha256'] or len(body)!=entry['bytes']:raise ValueError('trial_file_mismatch')
                provenance=dict(trial_id=ref['trial_id'],execution_attempt_id=row[0],manifest_sha256=report['manifest_hash'])
            else:raise ValueError('unsupported_artifact_kind')
            metadata=dict(reference=ref,sha256=_hash(body),bytes=len(body),provenance=provenance)
            result.append(Material(identity,metadata['sha256'],encoded(metadata)))
        except (ValueError,KeyError,TypeError,OSError,StopIteration) as cause:
            error=ControlError('note_artifact_unavailable')
            error.details=dict(category=type(cause).__name__,check=str(cause) if isinstance(cause,ValueError) else 'artifact_lookup_or_read_failed')
            raise error from None
    return result
