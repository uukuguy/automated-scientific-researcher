"""Lossless public-data pages for the native reader's bounded output.

This projection never reads private client data and never replaces source files.
"""
import argparse
import hashlib
import json
from pathlib import Path

MAX_PAGE_BYTES=40000  # Below pi read's observed 50-KB output boundary.
SPLITS=('train','id_dev','diagnostic')


def prepare_views(public,destination):
    public=Path(public);destination=Path(destination)
    manifest=json.loads((public/'manifest.json').read_text())
    sources={}
    for split in SPLITS:
        path=public/(split+'.json')
        if path.is_symlink():raise ValueError('source symlink forbidden')
        body=path.read_bytes()
        if hashlib.sha256(body).hexdigest()!=manifest['files'][path.name]:raise ValueError('source hash mismatch')
        rows=json.loads(body)
        if not isinstance(rows,list):raise ValueError('source array required')
        lines=[(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n').encode() for r in rows]
        if any(len(line)>MAX_PAGE_BYTES for line in lines):raise ValueError('one row exceeds reader page limit; source retained, explicit alternative projection required')
        sources[split]=(path.name,lines)
    destination.mkdir(parents=True,exist_ok=False)
    report=dict(schema='asr-public-data-pages/1',source_manifest_sha256=hashlib.sha256((public/'manifest.json').read_bytes()).hexdigest(),max_page_bytes=MAX_PAGE_BYTES,splits={})
    for split,(name,lines) in sources.items():
        pages=[];pending=[];size=0
        def flush():
            if not pending:return
            filename=f'{split}-{len(pages):03d}.jsonl';body=b''.join(pending)
            (destination/filename).write_bytes(body)
            pages.append(dict(file=filename,rows=len(pending),bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
        for line in lines:
            if size+len(line)>MAX_PAGE_BYTES:flush();pending=[];size=0
            pending.append(line);size+=len(line)
        flush()
        report['splits'][split]=dict(source_file=name,source_sha256=manifest['files'][name],rows=len(lines),pages=pages)
    (destination/'index.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public',required=True,type=Path);parser.add_argument('--destination',required=True,type=Path)
    args=parser.parse_args();result=prepare_views(args.public,args.destination)
    print(json.dumps({k:dict(rows=v['rows'],pages=len(v['pages'])) for k,v in result['splits'].items()}))
