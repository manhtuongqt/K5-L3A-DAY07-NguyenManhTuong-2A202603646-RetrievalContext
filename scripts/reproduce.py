"""Create an isolated public-source workspace, rebuild retrieval, optionally run new API dev.

Original model outputs and review approvals are never overwritten or copied as
approvals for new outputs. The default command does not call a paid model API.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from pathlib import Path
import shutil
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.lab_common import ROOT,read_json,write_json,now
from src.retrieval import prepare_day6,RetrievalService
from src.evaluation import verify_benchmark,evaluate_retrieval

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--api-dev',action='store_true',help='Additionally make new real model calls on dev; new outputs need fresh semantic reviews.')
    p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target=ROOT/'.local'/f'reproduction_{stamp}'
    if target.exists():raise ValueError('Reproduction target already exists')
    target.mkdir(parents=True)
    for directory in ('src','scripts','configs','benchmark'):
        shutil.copytree(ROOT/directory,target/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    started=time.perf_counter()
    manifest=prepare_day6(None,target)
    benchmark=verify_benchmark(target)
    service=RetrievalService(target)
    comparisons=[]
    try:
        for method in ('dense','bm25','hybrid'):
            traces,summary=evaluate_retrieval(service,read_json(target/'benchmark/dev.json'),method)
            original=read_json(ROOT/f'results/retrieval/dev/{method}/traces.json')
            expected=read_json(ROOT/f'results/retrieval/dev/{method}/summary.json')
            comparisons.append({'method':method,'hit1_equal':summary['hit1']==expected['hit1'],
                                'hit3_equal':summary['hit3']==expected['hit3'],
                                'all_ranked_ids_equal':[[c['id'] for c in t['results']] for t in traces]==[[c['id'] for c in t['results']] for t in original],
                                'errors':summary['errors']})
            write_json(target/f'results/retrieval/dev/{method}/traces.json',traces)
            write_json(target/f'results/retrieval/dev/{method}/summary.json',summary)
    finally:service.close()
    report={'recorded_at':now(),'command':'python -X utf8 scripts/reproduce.py'+(' --api-dev' if args.api_dev else ''),
            'isolated_workspace':target.relative_to(ROOT).as_posix(),'source_mode':'remote pinned downloads; freshly generated vectors/store',
            'benchmark_checks':benchmark,'retrieval_comparisons':comparisons,
            'elapsed_seconds':time.perf_counter()-started,'new_model_api_run':False,
            'passed':all(all(c[k] for k in ('hit1_equal','hit3_equal','all_ranked_ids_equal')) and c['errors']==0 for c in comparisons),
            'scope':'Retrieval/index and frozen benchmark reproduction on this environment; no assertion of independent or byte-identical new model answers.'}
    if args.api_dev:
        from src.model_client import ModelClient
        from scripts.run_experiments import run_batch
        ModelClient.from_env(ROOT)  # Load private settings into memory, never copy .env.
        run_batch(target,['C0','C1','C2','C3'],'dev',args.workers)
        report['new_model_api_run']=True
        report['new_review_required']='Review the newly generated outputs; original labels/approvals are not transferable.'
    write_json('results/reproduction_cli.json',report)
    print(report)
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
