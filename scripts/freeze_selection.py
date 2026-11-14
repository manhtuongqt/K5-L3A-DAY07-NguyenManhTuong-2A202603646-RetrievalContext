"""Select using complete dev labels and freeze implementation before opening test."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.lab_common import ROOT,read_json,write_json,sha256,now
from src.evaluation import aggregate_agent,verify_benchmark
from src.model_client import ModelClient
from scripts.run_experiments import code_hashes
from scripts.review_helpers import evaluation_trace,citation_counts
from scripts.human_reviews import confirmed_reviews

def verified_confirmation(root,kind):
    record=read_json(root/f'results/audit/{kind}_human_confirmation.json')
    for name,expected in record['artifact_hashes'].items():
        if sha256(root/name)!=expected:
            raise ValueError(f'{kind}: confirmed artifact changed: {name}')
    return record

def select(root=ROOT,config_ids=('C0','C1','C2','C3')):
    if (root/'results/selection.json').exists():
        raise ValueError('Selection already exists; preserve it. Do not reselect after test.')
    if list((root/'results/agent/test').glob('*/cases/*.json')):
        raise ValueError('Test output already exists; cannot claim a new pre-test selection.')
    verified_confirmation(root,'benchmark')
    dev_confirmation=verified_confirmation(root,'dev')
    verify_benchmark(root)
    cases=read_json(root/'benchmark/dev.json')
    summaries={}
    trace_hashes={}
    review_hashes={}
    for cid in config_ids:
        trace_path=root/f'results/agent/dev/{cid}/traces.json'
        reviews_path=root/f'results/audit/dev/{cid}_reviews.json'
        if reviews_path.relative_to(root).as_posix() not in dev_confirmation['artifact_hashes']:
            raise ValueError(f'{cid}: dev review not in explicit student confirmation')
        raw=read_json(trace_path)
        reviews=confirmed_reviews('dev',cid,root)
        metrics=aggregate_agent(cases,[evaluation_trace(t) for t in raw],reviews)
        metrics['citation_counts']=citation_counts(raw)
        metrics['confirmation_file']='results/audit/dev_human_confirmation.json'
        if metrics['pending_reviews'] or metrics['missing_traces']:
            raise ValueError(f'{cid}: missing dev traces/reviews')
        summaries[cid]=metrics
        trace_hashes[trace_path.relative_to(root).as_posix()]=sha256(trace_path)
        review_hashes[reviews_path.relative_to(root).as_posix()]=sha256(reviews_path)
    remaining=list(config_ids)
    decisions=[]
    criteria=[('strict_end_to_end',lambda c:summaries[c]['strict_end_to_end']['rate'],max),
              ('context_evidence_rate',lambda c:summaries[c]['context_evidence_rate']['rate'],max),
              ('false_abstention_count',lambda c:summaries[c]['false_abstention']['n'],min)]
    for name,key,choose in criteria:
        best=choose(key(c) for c in remaining)
        remaining=[c for c in remaining if key(c)==best]
        decisions.append({'criterion':name,'best':best,'remaining':list(remaining)})
    if len(remaining)>1:
        if all(summaries[c]['cost']['complete'] for c in remaining):
            best=min(summaries[c]['cost']['mean_per_scheduled_case_usd'] for c in remaining)
            remaining=[c for c in remaining if summaries[c]['cost']['mean_per_scheduled_case_usd']==best]
            decisions.append({'criterion':'known_mean_cost_usd','best':best,'remaining':list(remaining)})
        else:
            decisions.append({'criterion':'known_mean_cost_usd','skipped':'Cost unknown for at least one tied configuration; unknown is not zero.','remaining':list(remaining)})
    if len(remaining)>1:
        best=min(summaries[c]['elapsed_ms']['median'] for c in remaining)
        remaining=[c for c in remaining if summaries[c]['elapsed_ms']['median']==best]
        decisions.append({'criterion':'median_end_to_end_ms','best':best,'remaining':list(remaining)})
    winner=sorted(remaining)[0]
    hashes=code_hashes(root)
    for name in ('scripts/review_helpers.py','scripts/human_reviews.py','scripts/freeze_selection.py'):
        hashes[name]=sha256(root/name)
    selected={'selected_at':now(),'selected_config':winner,'baseline_config':'C0','basis':'dev only',
              'benchmark_lock_sha256':sha256(root/'benchmark/lock.json'),
              'config_hashes':{cid:sha256(root/f'configs/{cid}.json') for cid in config_ids},
              'implementation_hashes':hashes,'model_config':ModelClient.from_env(root).public_config(),
              'data_hashes':{p:sha256(root/p) for p in ('data/chunks.jsonl','data/pages.jsonl','configs/embedding_model.json')},
              'dev_trace_hashes':trace_hashes,'dev_review_hashes':review_hashes,
              'selection_rule':read_json(root/'benchmark/protocol.json')['selection_order'],
              'decisions':decisions,'dev_metrics':summaries,
              'limitations':['One real run per configuration; API decoding/latency may vary.','Provider model alias and usage are provider-reported.','Per-answer distinct citation IDs include inline references in abstention reasons.']}
    write_json(root/'results/metrics_dev.json',summaries)
    write_json(root/'results/selection.json',selected)
    return selected

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--configs',nargs='+',default=['C0','C1','C2','C3'])
    args=p.parse_args()
    out=select(ROOT,args.configs)
    print('Frozen selected configuration:',out['selected_config'])
if __name__=='__main__':main()
