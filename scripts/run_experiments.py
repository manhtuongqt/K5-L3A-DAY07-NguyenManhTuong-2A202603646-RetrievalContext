"""Run a complete scheduled real-model split, preserving every original case result."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.lab_common import ROOT,read_json,write_json,sha256,now
from src.model_client import ModelClient
from src.agent_runtime import run_agent,SYSTEM_PROMPT
from src.retrieval import RetrievalService

def verify_benchmark(root):
    lock=read_json(root/'benchmark/lock.json')
    for relative,expected in lock['files'].items():
        path=root/'benchmark'/relative
        if sha256(path)!=expected:
            raise ValueError(f'Frozen benchmark changed: {relative}')
    return sha256(root/'benchmark/lock.json')

def code_hashes(root):
    files=list((root/'src').glob('*.py'))+[root/'scripts/run_experiments.py']
    return {p.relative_to(root).as_posix():sha256(p) for p in sorted(files)}

class ConfiguredRetriever:
    def __init__(self,service,method,lock):
        self.service,self.method,self.lock=service,method,lock
    def search(self,query,*,filters=None,top_k=3):
        # One Qdrant/ONNX owner; model requests can overlap safely outside this lock.
        with self.lock:
            return self.service.search(query,filters=filters,top_k=top_k,method=self.method)

def run_batch(root,config_ids,split,workers=2):
    benchmark_hash=verify_benchmark(root)
    cases=read_json(root/f'benchmark/{split}.json')
    modelspec=ModelClient.from_env(root).public_config()
    configurations={cid:read_json(root/f'configs/{cid}.json') for cid in config_ids}
    hashes=code_hashes(root)
    if split=='test':
        selection=read_json(root/'results/selection.json')
        allowed={'C0',selection['selected_config']}
        if set(config_ids)!=allowed:
            raise ValueError('Test must evaluate baseline and frozen winner, or one C0 if it won.')
        if selection['benchmark_lock_sha256']!=benchmark_hash:
            raise ValueError('Selection benchmark mismatch')
        for relative,expected in selection['implementation_hashes'].items():
            if sha256(root/relative)!=expected:
                raise ValueError(f'Implementation changed after selection: {relative}')
        for cid in allowed:
            if sha256(root/f'configs/{cid}.json')!=selection['config_hashes'][cid]:
                raise ValueError('Config changed after selection')
        if modelspec!=selection['model_config']:
            raise ValueError('Model configuration changed after selection')
    service=RetrievalService(root=root)
    retrieval_lock=threading.Lock()
    outputs=[]
    try:
        for cid in config_ids:
            config=configurations[cid]
            output=root/f'results/agent/{split}/{cid}'
            manifest_path=output/'run.json'
            signature={'config_hash':sha256(root/f'configs/{cid}.json'),
                       'benchmark_lock_sha256':benchmark_hash,'implementation_hashes':hashes,'model_config':modelspec}
            if manifest_path.exists():
                existing=read_json(manifest_path)
                if existing['signature']!=signature:
                    raise ValueError(f'{cid}: existing run has a different signature; preserve it and use a new config/run.')
                manifest=existing
            else:
                manifest={'config_id':cid,'split':split,'started_at':now(),'signature':signature,
                          'scheduled_ids':[c['id'] for c in cases],'workers':workers,
                          'resume_policy':'Only missing cases are resumed; original error outputs remain.'}
                write_json(manifest_path,manifest)
            adapter=ConfiguredRetriever(service,config['method'],retrieval_lock)
            pending=[c for c in cases if not (output/'cases'/f"{c['id']}.json").exists()]
            def one(case):
                # Project input explicitly. The model receives no gold or answerable label.
                projection={k:case[k] for k in ('id','question','filter') if k in case}
                trace=run_agent(projection,ModelClient.from_env(root),adapter,config)
                trace.update(split=split,benchmark_lock_sha256=benchmark_hash,
                             run_config_sha256=signature['config_hash'],recorded_at=now())
                write_json(output/'cases'/f"{case['id']}.json",trace)
                return trace
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures={pool.submit(one,c):c['id'] for c in pending}
                for future in as_completed(futures):
                    trace=future.result()
                    print(json.dumps({'config':cid,'split':split,'query_id':trace['query_id'],
                                      'status':trace['status'],'tool_calls':trace['tool_calls'],
                                      'model_calls':len(trace['model_calls'])}),flush=True)
            traces=[read_json(output/'cases'/f"{c['id']}.json") for c in cases]
            write_json(output/'traces.json',traces)
            manifest.update(completed_at=now(),cases=len(traces),
                            statuses={s:sum(t['status']==s for t in traces) for s in ('answered','abstain','error')},
                            model_calls=sum(len(t['model_calls']) for t in traces),
                            tool_calls=sum(t['tool_calls'] for t in traces))
            write_json(manifest_path,manifest)
            outputs.append(manifest)
    finally:
        service.close()
    return outputs

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split',choices=['dev','test'],required=True)
    parser.add_argument('--configs',nargs='+',required=True)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    if not 1<=args.workers<=4:
        parser.error('workers must be 1..4')
    run_batch(args.root,args.configs,args.split,args.workers)

if __name__=='__main__':
    main()
