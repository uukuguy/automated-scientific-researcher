"""清单流式解析与整份JSON解析的隔离Python分配对比。"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import tracemalloc
import ijson

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from asr_service.manifest_stream import select
from integrations.runtimes.capacity_policy import load_policy


def measure(call):
    tracemalloc.start()
    try:
        result=call();current,peak=tracemalloc.get_traced_memory()
        return result,dict(retained_bytes=current,peak_bytes=peak)
    finally:tracemalloc.stop()


def run(count,chunk):
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'manifest.json'
        with path.open('w') as stream:
            stream.write('{"schema":"asr-workspace-snapshot/1","project_id":"p","research_run_id":"r","files":[')
            for index in range(count):
                if index:stream.write(',')
                json.dump(dict(path=f'file-{index}',sha256='a'*64,size=index),stream)
            stream.write(']}')
        full,before=measure(lambda:json.loads(path.read_bytes()));expected=full['files'][-1];del full
        streamed,after=measure(lambda:select(path,'snapshot',f'file-{count-1}',chunk))
        assert streamed['entry']==expected
        return dict(entries=count,file_bytes=path.stat().st_size,sha256=streamed['sha256'],whole_json=before,streamed=after)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():parser.error('output exists; use a new path')
    policy=load_policy();chunk=policy['limits']['artifact_read_chunk_bytes']['value']
    result=dict(schema='asr-manifest-memory-probe/1',measurement='Python tracemalloc，不含原生解析器分配、RSS、页缓存或并发叠加',
        parser_version=ijson.__version__,parser_backend=ijson.backend,chunk_bytes=chunk,capacity_policy_sha256=policy['sha256'],samples=[run(n,chunk) for n in (1000,60000,120000)])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
