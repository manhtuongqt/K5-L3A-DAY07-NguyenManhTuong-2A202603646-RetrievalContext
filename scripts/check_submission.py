"""Read current source/artifacts and verify the basic Day07 submission requirements.

This checks evidence and approvals, not the instructor's awarded points. No API
requests, label generation, or automatic human confirmation occur here.
"""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.lab_common import ROOT,read_json,read_jsonl,write_json,sha256,now
from src.evaluation import verify_benchmark,aggregate_agent,hit
from scripts.freeze_selection import verified_confirmation
from scripts.human_reviews import confirmed_reviews
from scripts.review_helpers import evaluation_trace,citation_counts
from scripts.verify_runtime_traces import verify_traces

def check(root=ROOT):
    checks=[]
    def require(name,condition,evidence):
        checks.append({'name':name,'passed':bool(condition),'evidence':evidence})
    benchmark=verify_benchmark(root)
    require('benchmark_24_with_frozen_sources',benchmark['questions']>=24 and benchmark['gold_alternatives_checked']>=20 and benchmark['absence_checks']>=4,benchmark)
    chunks=read_jsonl(root/'data/chunks.jsonl');pages=read_jsonl(root/'data/pages.jsonl')
    require('source_and_chunk_sizes',len(chunks)==312 and len(pages)==69,{'chunks':len(chunks),'units':len(pages)})
    manifest=read_json(root/'data/day6_manifest.json')
    require('source_model_data_hashes',sha256(root/'data/chunks.jsonl')==manifest['chunks_sha256'] and sha256(root/'data/pages.jsonl')==manifest['pages_sha256'] and sha256(root/'configs/embedding_model.json')==manifest['model_lock_sha256'],'data/day6_manifest.json')
    selection=read_json(root/'results/selection.json');winner=selection['selected_config']
    require('frozen_implementation',all(sha256(root/p)==h for p,h in selection['implementation_hashes'].items()),selection['implementation_hashes'])
    require('frozen_configs',all(sha256(root/f'configs/{c}.json')==h for c,h in selection['config_hashes'].items()),'results/selection.json config_hashes')
    require('frozen_dev_trace_and_label_files',all(sha256(root/p)==h for p,h in {**selection['dev_trace_hashes'],**selection['dev_review_hashes']}.items()),'results/selection.json dev_trace_hashes/dev_review_hashes')
    require('selection_before_test',all(read_json(root/f'results/agent/test/{c}/run.json')['started_at']>selection['selected_at'] for c in {'C0',winner}),{'selected_at':selection['selected_at'],'winner':winner})
    approvals={k:verified_confirmation(root,k) for k in ('benchmark','dev','test')}
    require('human_benchmark_confirmation',approvals['benchmark']['count']==24,'results/audit/benchmark_human_confirmation.json')
    alltraces=[];labels=0;metric_checks=[]
    for split,ids in [('dev',['C0','C1','C2','C3']),('test',list(dict.fromkeys(['C0',winner])))]:
        cases=read_json(root/f'benchmark/{split}.json');expected={c['id'] for c in cases}
        recorded=read_json(root/f'results/metrics_{split}.json')
        for cid in ids:
            raw=read_json(root/f'results/agent/{split}/{cid}/traces.json')
            require(f'{split}_{cid}_complete_scheduled_cases',len(raw)==len(cases) and {t['query_id'] for t in raw}==expected,{'count':len(raw),'expected':len(cases)})
            reviews=confirmed_reviews(split,cid,root);labels+=len(reviews)
            recomputed=aggregate_agent(cases,[evaluation_trace(t) for t in raw],reviews)
            recomputed['citation_counts']=citation_counts(raw)
            recomputed['confirmation_file']=f'results/audit/{split}_human_confirmation.json'
            equal=json.loads(json.dumps(recomputed))==recorded[cid]
            metric_checks.append({'split':split,'config':cid,'equal':equal})
            require(f'{split}_{cid}_semantic_reviews',not recomputed['pending_reviews'] and recomputed['human_confirmed_case_count']==recomputed['reviewed_case_count'],{'reviewed':len(reviews),'errors':recomputed['errors']})
            alltraces.extend(raw)
    require('all_metrics_recompute',all(r['equal'] for r in metric_checks),metric_checks)
    integrity=verify_traces(alltraces,chunks,pages)
    require('all_real_runtime_trace_integrity',integrity['passed'],{'traces':integrity['traces'],'checks':integrity['checks'],'errors':integrity['errors'],'warnings':len(integrity.get('warnings',[]))})
    require('model_native_tools_used',all(t['config']['action_protocol']=='native_tools' and t['tool_calls']>=1 and t['model_calls'] for t in alltraces),'82 actual model-controlled traces; request schemas/messages retained')
    for method in ('dense','bm25','hybrid'):
        traces=read_json(root/f'results/retrieval/dev/{method}/traces.json');cases=read_json(root/'benchmark/dev.json')
        summary=read_json(root/f'results/retrieval/dev/{method}/summary.json');by={c['id']:c for c in cases}
        a=[t for t in traces if by[t['query_id']]['answerable']]
        hit1=sum(bool(t['results']) and hit(t['results'][0],by[t['query_id']]['gold']) for t in a)
        hit3=sum(any(hit(c,by[t['query_id']]['gold']) for c in t['results']) for t in a)
        require(f'retrieval_{method}_top3_comparable',len(a)==15 and hit1==summary['hit1']['n'] and hit3==summary['hit3']['n'] and all(len(t['results'])==t['actual_returned']<=3 for t in traces),{'cases':len(traces),'answerable':len(a),'hit1':hit1,'hit3':hit3})
    configs=[read_json(root/f'configs/{c}.json') for c in ('C0','C1','C2','C3')]
    require('two_real_improvement_configurations',configs[2]['method']!=configs[0]['method'] and configs[3]['budget_chars']!=configs[2]['budget_chars'] and configs[3]['top_k']!=configs[2]['top_k'],'C2 rank fusion; C3 larger context policy; all have separate dev runs')
    tests=read_json(root/'results/tests.json')
    require('required_code_tests',tests['passed'] and tests['failures']==0 and tests['errors']==0 and tests['skipped']==0,tests)
    reproduction=read_json(root/'results/retrieval_reproduction.json')
    require('remote_retrieval_reproduction',reproduction['passed'] and all(reproduction['checks'].values()),'results/retrieval_reproduction.json')
    cli=read_json(root/'results/reproduction_cli.json')
    require('documented_reproduction_cli_executed',cli['passed'] and not cli['new_model_api_run'],'results/reproduction_cli.json')
    from src.retrieval import RetrievalService
    service=RetrievalService(root)
    try:point_count=service.client.count('day07_B',exact=True).count
    finally:service.close()
    require('persistent_Qdrant_real_collection',point_count==312,{'collection':'day07_B','points':point_count})
    report=root/'report/individual/2A202603646_NguyenManhTuong.md'
    documents=[report,root/'README.md',root/'THIRD_PARTY_NOTICES.md',root/'docs/DEMO.md',root/'docs/REPRODUCTION.md',root/'docs/RETRIEVAL.md']
    missing=[str(p.relative_to(root)) for p in documents if not p.exists()]
    broken=[]
    for path in documents:
        if not path.exists():continue
        for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8-sig')):
            if link.startswith(('https://','http://','#')):continue
            target=link.split('#')[0]
            if target and not (path.parent/target).exists():broken.append({'file':path.relative_to(root).as_posix(),'target':link})
    require('submission_documents_and_links',not missing and not broken,{'missing':missing,'broken':broken})
    content=report.read_text(encoding='utf-8') if report.exists() else ''
    require('two_dev_errors_and_measured_limits','C0/D01' in content and 'C0/D10' in content and 'C1/D03' in content and 'mẫu nhỏ' in content and 'không quy thành USD' in content,'report sections 4–6')
    public_files=[]
    for base in ('src','scripts','configs','benchmark','data','results','docs','report'):
        public_files.extend(p for p in (root/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    private={}
    for line in (root/'.env').read_text(encoding='utf-8-sig').splitlines() if (root/'.env').exists() else []:
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            if any(x in key.upper() for x in ('API_KEY','TOKEN','SECRET')) and len(value.strip())>12:private[key.strip()]=value.strip().strip('"\'')
    exposures=[]
    for path in public_files:
        raw=path.read_bytes()
        for key,value in private.items():
            if value.encode() in raw:exposures.append({'file':path.relative_to(root).as_posix(),'variable':key})
    ignored=subprocess.run(['git','check-ignore','.env','.local/model'],cwd=root,capture_output=True,text=True)
    require('known_secret_values_absent_and_private_paths_ignored',not exposures and '.env' in ignored.stdout and '.local/model' in ignored.stdout,{'exposures':exposures,'limit':'Checks known configured secrets and ignored paths, not a proof against every possible secret.'})
    report_data={'checked_at':now(),'scope':'Basic Day07 only; bonus deferred','full_basic_submission_ready':all(c['passed'] for c in checks),
                 'checks':checks,'passed_checks':sum(c['passed'] for c in checks),'total_checks':len(checks),
                 'semantic_output_rows_confirmed':labels,'pending_required_human_reviews':0,
                 'runtime_traces':len(alltraces),'selected_config':winner,'test_results':read_json(root/'results/metrics_test.json'),
                 'lms':'Student submits; agent has not submitted to LMS.',
                 'grading_limit':'Evidence verification, not a guarantee of instructor points; no optional bonus claim.'}
    write_json(root/'results/submission_check.json',report_data)
    lines=['# Đối chiếu gate phần cơ bản Day07','',f"Kiểm tra: `{report_data['checked_at']}` UTC. Bonus để sau, không tính vào trạng thái phần cơ bản.",'',
           '| Mục | Trạng thái | Bằng chứng |','|---|---|---|']
    for c in checks:lines.append(f"| {c['name']} | {'ĐẠT' if c['passed'] else 'CHƯA ĐẠT'} | `{str(c['evidence']).replace('|',' / ')[:200]}` |")
    lines+=['',f"Kết quả: **{report_data['passed_checks']}/{len(checks)} kiểm tra**, **{labels} hàng audit output đã xác nhận**, {len(alltraces)} trace agent thật.",'',
             'Đây là kiểm tra yêu cầu và bằng chứng, không phải điểm giảng viên. Nhãn được người học đối chiếu/xác nhận, nguồn nháp hỗ trợ được giữ đúng lịch sử. Không còn yêu cầu review của phần cơ bản nếu mọi hash xác nhận vẫn khớp. Người học tự nộp link LMS.']
    (root/'docs/GATE_CHECKLIST.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    return report_data

if __name__=='__main__':
    result=check()
    print(json.dumps({k:result[k] for k in ('full_basic_submission_ready','passed_checks','total_checks','semantic_output_rows_confirmed','pending_required_human_reviews','runtime_traces','selected_config')},ensure_ascii=True,indent=2))
    if not result['full_basic_submission_ready']:
        print(json.dumps([c for c in result['checks'] if not c['passed']],ensure_ascii=True,indent=2))
        raise SystemExit(1)
