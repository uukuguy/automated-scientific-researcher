"""Immutable indexed export of recorded research communications, with coverage gaps.

Native originals stay in the restricted run directory. This export preserves
visible messages/tool records, never substitutes summaries for missing originals,
and explicitly records credential/private-reasoning redactions. Raw provider
stderr and developer-chat history are not reconstructed by this utility.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3


def sha(body):
    return hashlib.sha256(body).hexdigest()


class EventRecorder:
    """Append the complete native event with collector order/time, then sync it."""
    def __init__(self, stream):
        self.stream = stream
        self.sequence = 0

    def __call__(self, event):
        self.sequence += 1
        record = dict(schema='asr-recorded-runtime-event/1', sequence=self.sequence,
                      recorded_at=datetime.now(timezone.utc).isoformat(), event=event)
        self.stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+'\n')
        self.stream.flush()
        os.fsync(self.stream.fileno())


def archive(root, destination):
    root = root.resolve()
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    sources = []; gaps = []; redactions = []; sessions = []
    secret_keys = {'accesstoken','refreshtoken','apikey','authorization','cookie','bridgetoken','password'}
    private_keys = {'thinkingsignature','thoughtsignature','encryptedcontent'}

    def clean(value, location):
        if isinstance(value, dict):
            kind = value.get('type')
            if type(kind) is str and (kind == 'thinking' or kind.startswith('thinking_')):
                redactions.append(dict(location=location, reason='private_reasoning'))
                return dict(type=kind, omitted='private_reasoning')
            output = {}
            for key, item in value.items():
                normalized = key.lower().replace('_','').replace('-','')
                if normalized in secret_keys | private_keys:
                    redactions.append(dict(location=location+'/'+key, reason='credential_or_private_signature'))
                    output[key] = '[REDACTED]'
                else:
                    output[key] = clean(item, location+'/'+key)
            return output
        if isinstance(value, list):
            return [clean(item, location+'/'+str(i)) for i,item in enumerate(value)]
        if isinstance(value, str):
            result = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]', value)
            result = re.sub(r'(?i)([?&](?:access_token|refresh_token|api_key)=)[^&\s]+', r'\1[REDACTED]', result)
            if result != value:
                redactions.append(dict(location=location, reason='credential_pattern'))
            return result
        return value

    def write(relative, value):
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n')

    def capture(path, relative, jsonl=False):
        if not path.is_file() or path.is_symlink():
            gaps.append(dict(code='missing_or_unsafe_source', source=str(path)))
            return
        body = path.read_bytes()
        source = dict(path=str(path.resolve().relative_to(root)), sha256=sha(body), bytes=len(body), export=relative)
        sources.append(source)
        if jsonl:
            records = []
            for number, line in enumerate(body.splitlines(), 1):
                try:
                    value = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    gaps.append(dict(code='incomplete_or_invalid_jsonl', source=source['path'], line=number,
                                     bytes=len(line), sha256=sha(line), retained='original source; not guessed or silently omitted'))
                    continue
                records.append(clean(value, relative+':'+str(number)))
            path_out = destination / relative
            path_out.parent.mkdir(parents=True, exist_ok=True)
            path_out.write_text(''.join(json.dumps(v,ensure_ascii=False,allow_nan=False)+'\n' for v in records))
            source['records'] = len(records)
        else:
            write(relative, clean(json.loads(body), relative))

    native = set()
    for step in sorted((root/'steps').glob('*')):
        if not step.is_dir():
            continue
        request = step/'request.json'; result = step/'result.json'
        capture(request, 'steps/'+step.name+'/request.json')
        capture(step/'events.jsonl', 'steps/'+step.name+'/events.jsonl', True)
        session = dict(step=step.name, finalized=result.is_file())
        if not result.is_file():
            gaps.append(dict(code='step_not_finalized', step=step.name))
        else:
            capture(result, 'steps/'+step.name+'/result.json')
            record = json.loads(result.read_text()); session['status'] = record.get('status')
            name = record.get('recovery',{}).get('native_session_file')
            if not name or not Path(name).is_file():
                gaps.append(dict(code='missing_native_journal', step=step.name))
            else:
                path = Path(name)
                if path.is_symlink() or not path.resolve().is_relative_to(root) or path.suffix != '.jsonl':
                    gaps.append(dict(code='unsafe_native_journal_path', step=step.name))
                else:
                    relative = 'native/'+sha(str(path.resolve()).encode())+'.jsonl'
                    session['native_journal'] = relative
                    if path not in native:
                        capture(path, relative, True); native.add(path)
            if (step/'delivery-receipt.json').is_file():
                capture(step/'delivery-receipt.json', 'steps/'+step.name+'/delivery-receipt.json')
        sessions.append(session)
    with closing(sqlite3.connect((root/'control.db').as_uri()+'?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        for table in ('asr_organization','asr_events','asr_runtime_sessions','asr_commands','asr_contracts','asr_hypotheses','asr_findings'):
            rows = [json.loads(row[0]) for row in db.execute('SELECT record FROM '+table+' ORDER BY rowid')]
            write('control/'+table+'.json', clean(rows, table))
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='asr_note_heads'").fetchone():
            heads=[dict(zip(('project','run','owner','revision'),row)) for row in db.execute('SELECT project,run,owner,revision FROM asr_note_heads ORDER BY project,run,owner')]
            write('control/asr_note_heads.json',clean(heads,'asr_note_heads'))
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='asr_requests'").fetchone() and (root/'identity.json').is_file():
            identity=json.loads((root/'identity.json').read_text())
            project=identity.get('project_id');run=identity.get('research_run_id')
            if type(project) is str and type(run) is str:
                requests=[]
                for scope,key,payload,record in db.execute('SELECT scope,request_key,payload,record FROM asr_requests WHERE project=? ORDER BY scope,request_key',(project,)):
                    if not scope.startswith(('context-prepare:','context-admission:','context-source:')):continue
                    try:
                        binding=json.loads(scope.split(':',1)[1])
                        if type(binding) is not list or len(binding)!=2 or any(type(v) is not str for v in binding):raise ValueError('invalid_context_scope')
                    except ValueError:
                        gaps.append(dict(code='invalid_context_scope',request_key=key));continue
                    if binding[0]==run:requests.append(dict(scope=scope,request_key=key,payload=json.loads(payload),record=json.loads(record)))
                write('control/context_requests.json',clean(requests,'context_requests'))
    for path in sorted((root/'research-notes').glob('*/revisions/*.json')):
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent!=root and parent.is_relative_to(root)):
            gaps.append(dict(code='unsafe_note_path',path=str(path.relative_to(root))))
            continue
        capture(path,str(path.relative_to(root)))
    for name in ('identity.json','resource-policy.json','human-instructions.jsonl'):
        if (root/name).is_file():
            capture(root/name, name, name.endswith('.jsonl'))
    for path in sorted(root.glob('recovery-*.json')):
        capture(path, 'lifecycle/'+path.name)
    for path in sorted((root/'workspaces').glob('*/CLIENT-BRIEF.md')):
        body=path.read_bytes()
        relative='briefs/'+path.parent.name+'.json'
        sources.append(dict(path=str(path.relative_to(root)),sha256=sha(body),bytes=len(body),export=relative))
        write(relative, clean(dict(content=body.decode('utf-8'), captured_at='archive time; historical delivery is evidenced separately in native journals'), relative))
    manifest = dict(schema='asr-communication-archive/1', recorded_at=datetime.now(timezone.utc).isoformat(),
        source_root=str(root), scope='Recorded visible role communication, tool events and Control history; not developer-chat export or private model reasoning.',
        limitations=['Raw provider stderr is not retained by the runtime because it may contain credentials.',
                     'Historical human instructions without a recorded original are not reconstructed.',
                     'Streaming event timestamps are only available where native events recorded them; no timestamps invented.'],
        sessions=sessions, sources=sources, gaps=gaps, redactions=redactions)
    write('manifest.json', manifest)
    write('inventory.json', [dict(path=str(p.relative_to(destination)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
                             for p in sorted(destination.rglob('*')) if p.is_file()])
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = archive(args.root, args.output)
    print(json.dumps(dict(sessions=len(result['sessions']), sources=len(result['sources']),
                          gaps=result['gaps'], redactions=len(result['redactions']))))


if __name__ == '__main__':
    main()
