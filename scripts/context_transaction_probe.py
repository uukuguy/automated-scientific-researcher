"""本地隔离的上下文准备占锁测量；不连接模型，不修改历史研究库。"""
import argparse
import cProfile
import json
from pathlib import Path
import pstats
import statistics
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_context_sources import ContextSourcesTests


class MeasuredConnection:
    def __init__(self,connection,samples):self.manager=connection;self.samples=samples;self.started=None
    def __getattr__(self,name):return getattr(self.db,name)
    def __enter__(self):self.db=self.manager.__enter__();return self
    def execute(self,query,*args):
        result=self.db.execute(query,*args)
        if query=='BEGIN IMMEDIATE':self.started=time.perf_counter()
        return result
    def __exit__(self,*args):
        try:return self.manager.__exit__(*args)
        finally:
            if self.started is not None:self.samples.append((time.perf_counter()-self.started)*1000)


def run(size,repeats):
    case=ContextSourcesTests();case.setUp()
    try:
        rows=[json.loads(line) for line in case.path.read_text().splitlines()]
        rows[-1]['message']['content'][0]['text']='x'*size
        case.path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
        # This is an isolated workload size, not an operational limit change.
        case.s.register_context_source('human-secret','p','r',subject='lead',idempotency_key='source',path=str(case.path),native_session_id='native',leaf_id='a',keep_recent_groups=1,max_journal_bytes=case.path.stat().st_size+1)
        original=case.s._connect;samples=[];elapsed=[]
        with patch.object(case.s,'_connect',side_effect=lambda:MeasuredConnection(original(),samples)):
            for index in range(repeats):
                start=time.perf_counter()
                case.s.prepare_context('human-secret','p','r',subject='lead',reviewer_subject='lead2',idempotency_key='measure-'+str(index),source_registration='source')
                elapsed.append((time.perf_counter()-start)*1000)
        # Profile only the write-transaction implementation, not SDK startup.
        import asr_service.context_admission as admission
        profile=cProfile.Profile();implementation=admission._prepare
        def profiled(*args,**kwargs):return profile.runcall(implementation,*args,**kwargs)
        with patch.object(admission,'_prepare',side_effect=profiled):
            case.s.prepare_context('human-secret','p','r',subject='lead',reviewer_subject='lead2',idempotency_key='profile',source_registration='source')
        stats=pstats.Stats(profile)
        top=sorted(stats.stats.items(),key=lambda row:row[1][3],reverse=True)[:18]
        return dict(message_bytes=size,journal_bytes=case.path.stat().st_size,repeats=repeats,write_transaction_ms=samples,
            median_write_transaction_ms=statistics.median(samples),request_ms=elapsed,
            profile_top=[dict(file=Path(k[0]).name,line=k[1],function=k[2],calls=v[1],self_ms=v[2]*1000,cumulative_ms=v[3]*1000) for k,v in top])
    finally:case.doCleanups()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if args.repeats<1:parser.error('repeats must be positive')
    if args.output.exists():parser.error('output already exists; use a new path')
    result=dict(schema='asr-context-transaction-probe/1',scope='合成消息、临时Control数据库、固定pi SDK，无模型/科研调用',
        timing='BEGIN IMMEDIATE取得锁后至事务退出完成；不含等待锁时间。性能剖析单独执行，不计入耗时样本。',
        workloads=[run(n,args.repeats) for n in (1024,262144,1048576)])
    args.output.parent.mkdir(parents=True,exist_ok=True);
    with args.output.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([dict(bytes=r['message_bytes'],lock_ms=r['median_write_transaction_ms']) for r in result['workloads']]))
