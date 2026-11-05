"""隔离测量附件核验/分页的Python分配峰值；不是进程RSS上限。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tracemalloc

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_note_artifact_sources import NoteArtifactTests
from asr_service.note_artifacts import prepare,read_page


def run(size):
    case=NoteArtifactTests();case.setUp()
    try:
        service=case.service;body=case.work/'large.txt';digest=hashlib.sha256();block=b'x'*1048576
        with body.open('wb') as stream:
            for _ in range(size//len(block)):stream.write(block);digest.update(block)
        manifest=json.dumps(dict(schema='asr-workspace-snapshot/1',project_id='p',research_run_id='r',files=[dict(path='large.txt',size=size,sha256=digest.hexdigest())])).encode()
        key=hashlib.sha256(manifest).hexdigest();directory=service.path.parent/'snapshots'/key
        (directory/'files').mkdir(parents=True);body.rename(directory/'files/large.txt');(directory/'manifest.json').write_bytes(manifest)
        ref=dict(kind='snapshot',snapshot_sha256=key,path='large.txt');measured={}
        with service._connect() as db:
            tracemalloc.start()
            try:
                prepared=prepare(db,service,'p','r',[ref]);current,peak=tracemalloc.get_traced_memory()
                measured['verification']=dict(retained_bytes=current,peak_bytes=peak)
            finally:tracemalloc.stop()
            tracemalloc.start()
            try:
                page=read_page(db,service,'p','r',ref,offset=size-100,limit=13,prepared=prepared)
                current,peak=tracemalloc.get_traced_memory();measured['page']=dict(retained_bytes=current,peak_bytes=peak)
            finally:tracemalloc.stop()
        assert page['text']=='x'*13 and page['total_characters']==size and page['sha256']==digest.hexdigest()
        return dict(artifact_bytes=size,read_chunk_bytes=page['read_chunk_bytes'],capacity_policy_sha256=page['capacity_policy_sha256'],**measured)
    finally:case.doCleanups()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    if args.output.exists():parser.error('output exists; use a new path')
    result=dict(schema='asr-note-artifact-memory-probe/1',measurement='tracemalloc Python分配；不含OS页缓存、进程RSS、清单规模与并发叠加',
        samples=[run(n*1048576) for n in (1,12,48)])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
