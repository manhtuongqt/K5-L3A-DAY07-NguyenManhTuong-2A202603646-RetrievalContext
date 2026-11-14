"""Post-selection TEST audit only; no model/retrieval call or tuning.

The script never assigns a semantic grade. Explicit assessments are entered
after reading raw output, citations, actual context and source evidence, and
must bind to the exact trace SHA256. Human approval remains separate.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation import aggregate_agent, context_hit
from scripts.review_helpers import evaluation_trace, citation_counts


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_test(config):
    if not (ROOT / 'results/selection.json').exists():
        raise ValueError('Selection must exist before reading test outputs')
    cases = read(ROOT / 'benchmark/test.json')
    paths, traces = {}, []
    for case in cases:
        path = ROOT / f'results/agent/test/{config}/cases/{case["id"]}.json'
        if path.exists():
            trace = read(path)
            if trace['query_id'] != case['id'] or trace['split'] != 'test':
                raise ValueError('Test trace ID/split mismatch')
            paths[case['id']] = path
            traces.append(evaluation_trace(trace))
    return cases, traces, paths


def apply(config, assessment_path):
    cases, traces, paths = load_test(config)
    by_id = {t['query_id']: t for t in traces}
    rows = read(assessment_path)
    seen = set()
    for row in rows:
        cid = row['query_id']
        if cid in seen or cid not in by_id or by_id[cid]['status'] == 'error':
            raise ValueError(f'{cid}: missing/duplicate/failed trace cannot receive a successful-output grade')
        seen.add(cid)
        if row['trace_sha256'] != hashlib.sha256(paths[cid].read_bytes()).hexdigest():
            raise ValueError(f'{cid}: assessment bound to stale trace')
        row.update(reviewer='Codex (AI-assisted semantic draft)', review_status='AI-assisted draft; student review pending',
                   human_confirmed=False, trace=paths[cid].relative_to(ROOT).as_posix())
    metrics = aggregate_agent(cases, traces, rows)
    metrics['citation_accounting'] = citation_counts(traces)
    folder = ROOT / 'results/audit/test'
    write(folder / f'{config}_reviews.json', rows)
    write(folder / f'{config}_metrics_draft.json', metrics)
    print(json.dumps({'config': config, 'labels': len(rows), 'pending': metrics['pending_reviews'],
                      'missing_traces': metrics['missing_traces'], 'strict': metrics['strict_end_to_end']}))


def packet(config):
    cases, traces, paths = load_test(config)
    by_id = {t['query_id']: t for t in traces}
    folder = ROOT / 'results/audit/test'
    review_file = folder / f'{config}_reviews.json'
    labels = {r['query_id']: r for r in read(review_file)} if review_file.exists() else {}
    lines = [f'# Đối chiếu TEST {config}', '',
             '**Bản nháp AI hỗ trợ, chờ người học đối chiếu. Đây là audit sau khi đã cố định lựa chọn, không dùng kết quả để sửa pipeline.**', '',
             f'Trace hiện có: {len(traces)}/{len(cases)}.', '']
    for case in cases:
        cid = case['id']
        lines += [f'## {cid}', '', case['question'], '', f"Đáp án kỳ vọng: {case['expected_answer']}", '']
        if cid not in by_id:
            lines += ['Chưa có trace; không tự điền kết quả hoặc nhãn.', '']
            continue
        trace = by_id[cid]
        lines += [f"Trạng thái: {trace['status']} · [{paths[cid].relative_to(ROOT).as_posix()}](../../agent/test/{config}/cases/{cid}.json)",
                  f"SHA256 trace: `{hashlib.sha256(paths[cid].read_bytes()).hexdigest()}`", '', '### Nhãn và lý do', '']
        if cid in labels:
            row = labels[cid]
            lines += [f"Context={row.get('context_grade')} · Answer={row.get('answer_grade')} · Từ chối đúng={row.get('abstention_correct')}", row['reason'], '']
            lines += [f"- `{c}` · hỗ trợ={s} · {r}" for c, s, r in zip(trace['citations'], row['citation_support'], row['citation_reasons'])]
            lines += ['']
        else:
            lines += ['Chưa có nhãn output. Lỗi được lưu riêng, không loại khỏi mẫu số strict pass.', json.dumps(trace.get('errors', []), ensure_ascii=False), '']
        lines += ['### Câu trả lời thật', '', trace.get('answer', ''), '', '### Nội dung thực sự được trích dẫn', '']
        chunks = {c['id']: c for c in trace.get('final_context', [])}
        for citation in trace['citations']:
            lines += [f'#### {citation}']
            if citation not in chunks:
                lines += ['Không có trong context cuối.', '']
            else:
                c = chunks[citation]
                lines += [f"{c['source']} · {c['page']}", '```text', c['text'], '```', '']
        lines += ['### Toàn bộ context cuối thực sự gửi model', '```text', trace.get('final_context_text', ''), '```', '']
        if case['answerable']:
            lines += ['### Gold nguồn để chấm (không gửi vào agent)', '']
            for g in case['gold']:
                lines += [f"{g['source']} · {g['page']} · [{g['page_start']},{g['page_end']})", '```text', g['evidence'], '```', '']
            lines += [f"Exact-evidence trong context: {context_hit(trace, case['gold'])}. Chỉ số này không tự quyết định điểm answer/citation.", '']
        else:
            checks = read(ROOT / 'benchmark/absence_checks.json')
            check = next(c for c in checks if c['query_id'] == cid)
            lines += ['### Căn cứ thiếu bằng chứng', check['semantic_reason'],
                      f"Đã quét đầy đủ {check['scanned_source_units']} source units trước thực nghiệm; xem benchmark/absence_checks.json.", '']
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{config}_REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')


def overview():
    folder = ROOT / 'results/audit/test'
    lines = ['# Đối chiếu TEST: baseline C0 và cấu hình đã chọn C2', '',
             '**Bản nháp AI hỗ trợ; cần người học đọc và xác nhận nhãn hiện tại. Không coi xác nhận DEV hoặc benchmark là xác nhận TEST.**', '',
             '## Tiêu chí', '',
             '- Đọc đủ 5 câu có đáp án và 2 câu thiếu evidence của từng cấu hình.',
             '- Chấm context 0/1/2, câu trả lời 0/1/2; ghi lý do dựa trên nội dung và điều kiện thực tế.',
             '- Chấm mọi citation ID xuất hiện, kể cả trong câu từ chối; có ID đúng chưa đủ chứng minh nội dung được hỗ trợ.',
             '- Câu thiếu evidence chỉ đạt nếu thực sự từ chối mà không đoán số liệu hoặc thông tin triển khai riêng.',
             '- Lỗi được báo riêng và vẫn là không đạt trong strict pass trên toàn bộ 7 câu.',
             '- Không điều chỉnh cấu hình/gold/nhãn để nâng điểm sau khi đã nhìn test.', '',
             '| Cấu hình | Nhãn output | Lỗi | Strict pass | Gói nguồn chi tiết |', '|---|---:|---:|---:|---|']
    for config in ('C0', 'C2'):
        path = folder / f'{config}_metrics_draft.json'
        if path.exists():
            m = read(path)
            n = m['strict_end_to_end']
            lines += [f"| {config} | {m['reviewed_case_count']} | {m['errors']} | {n['n']}/{n['N']} | [{config}_REVIEW.md]({config}_REVIEW.md) |"]
    for config in ('C0', 'C2'):
        path = folder / f'{config}_reviews.json'
        if not path.exists():
            continue
        lines += ['', f'## {config}', '', '| Câu | Context | Answer | Từ chối đúng | Citation hỗ trợ | Lý do |', '|---|---:|---:|---|---|---|']
        for r in read(path):
            support = ', '.join(str(v) for v in r['citation_support']) or 'N/A'
            reason = r['reason'].replace('|', '\\|').replace('\n', ' ')
            lines += [f"| {r['query_id']} | {r['context_grade']} | {r['answer_grade']} | {r['abstention_correct']} | {support} | {reason} |"]
    (folder / 'REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', choices=('C0', 'C2'), required=True)
    p.add_argument('--assessments', type=Path)
    args = p.parse_args()
    if args.assessments:
        apply(args.config, args.assessments)
    packet(args.config)
    overview()
