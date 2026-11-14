"""Prepare and record DEV-only semantic review drafts from real saved traces.

This script never invents grades or uses Hit@k to infer semantic support. The
reviewer reads the packet and supplies an explicit assessment JSON. Labels are
identified as AI-assisted drafts until separately confirmed by the student.
"""
from __future__ import annotations
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


def load_dev(config_id):
    if config_id not in ('C0', 'C1', 'C2', 'C3', 'C4'):
        raise ValueError('Unknown configuration')
    cases = read(ROOT / 'benchmark/dev.json')
    folder = ROOT / 'results/agent/dev' / config_id
    traces, paths = [], {}
    for case in cases:
        path = folder / 'cases' / (case['id'] + '.json')
        if path.exists():
            trace = read(path)
            if trace['query_id'] != case['id']:
                raise ValueError('Trace ID mismatch')
            traces.append(evaluation_trace(trace))
            paths[case['id']] = path
    return cases, traces, paths


def packet(config_id):
    cases, traces, paths = load_dev(config_id)
    by_id = {t['query_id']: t for t in traces}
    review_path = ROOT / 'results/audit/dev' / f'{config_id}_reviews.json'
    labels = {r['query_id']: r for r in read(review_path)} if review_path.exists() else {}
    lines = [f'# Đối chiếu DEV {config_id}: câu trả lời, context và citation', '',
             '**Bản nháp chấm ngữ nghĩa do AI hỗ trợ; chưa phải xác nhận của người học.**', '',
             f'Đã có {len(traces)}/{len(cases)} trace thật. Trace chưa có vẫn để chờ, không tự điền kết quả.', '']
    for case in cases:
        lines += [f"## {case['id']}", '', case['question'], '', f"Expected: {case['expected_answer']}", '']
        if case['id'] not in by_id:
            lines += ['Trace missing; no draft grade.', '']
            continue
        trace = by_id[case['id']]
        lines += [f"Trạng thái: {trace['status']} · trace `{paths[case['id']].relative_to(ROOT).as_posix()}`",
                  f"Trace SHA256: `{hashlib.sha256(paths[case['id']].read_bytes()).hexdigest()}`", '',
                  '### Nhãn nháp và lý do', '']
        if case['id'] in labels:
            label = labels[case['id']]
            lines += [f"Context: {label.get('context_grade')} · Answer: {label.get('answer_grade')} · Từ chối đúng: {label.get('abstention_correct')}",
                      label['reason'], '']
            for cite_id, supported, reason in zip(trace['citations'], label['citation_support'], label['citation_reasons']):
                lines += [f"- Citation `{cite_id}` · hỗ trợ: {supported} · {reason}"]
            lines += ['']
        else:
            lines += ['Chưa có nhãn cho output này; lỗi hệ thống được tính là không đạt trong tỷ lệ toàn bộ case.',
                      json.dumps(trace.get('errors', []), ensure_ascii=False), '']
        lines += ['### Câu trả lời thực tế', trace.get('answer', ''), '',
                  '### Đoạn được trích dẫn trong context cuối', '']
        context = trace.get('final_context', [])
        by_chunk = {c['id']: c for c in context} if isinstance(context, list) else {}
        for cid in trace.get('citations', []):
            chunk = by_chunk.get(cid)
            lines += [f'#### {cid}']
            if not chunk:
                lines += ['Absent from final context.']
            else:
                lines += [f"{chunk['source']} · {chunk['page']}", '', '```text', chunk['text'], '```', '']
        lines += ['### Toàn bộ context cuối thực sự gửi model', '', '```text', trace.get('final_context_text', ''), '```', '']
        if case['answerable']:
            lines += ['### Evidence để chấm (không đưa vào agent)', '']
            for gold in case['gold']:
                lines += [f"{gold['source']} · {gold['page']}", '```text', gold['evidence'], '```', '']
            lines += [f"Mechanical exact-evidence presence: {context_hit(trace, case['gold'])}. This is not an answer or citation grade.", '']
    path = ROOT / 'results/audit/dev' / f'{config_id}_REVIEW.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')
    overview()
    print(json.dumps({'packet': str(path.relative_to(ROOT)), 'available': len(traces), 'scheduled': len(cases)}))


def apply(config_id, assessment_file):
    cases, traces, paths = load_dev(config_id)
    assessments = read(assessment_file)
    by_trace = {t['query_id']: t for t in traces}
    ids = set()
    for row in assessments:
        cid = row['query_id']
        if cid in ids or cid not in by_trace or by_trace[cid]['status'] == 'error':
            raise ValueError(f'{cid}: duplicated, missing or failed trace cannot receive a successful-output grade')
        ids.add(cid)
        actual_sha = hashlib.sha256(paths[cid].read_bytes()).hexdigest()
        if row.get('trace_sha256') != actual_sha:
            raise ValueError(f'{cid}: explicit assessment must bind to current source trace SHA256')
        row.update(reviewer='Codex (AI-assisted semantic draft)',
                   review_status='AI-assisted draft; student review pending', human_confirmed=False,
                   trace=str(paths[cid].relative_to(ROOT).as_posix()))
    metrics = aggregate_agent(cases, traces, assessments)
    metrics['citation_accounting'] = citation_counts(traces)
    folder = ROOT / 'results/audit/dev'
    write(folder / f'{config_id}_reviews.json', assessments)
    write(folder / f'{config_id}_metrics_draft.json', metrics)
    print(json.dumps({'config_id': config_id, 'graded': len(assessments), 'pending': metrics['pending_reviews'],
                      'missing_traces': metrics['missing_traces'], 'strict': metrics['strict_end_to_end']}))


def overview():
    folder = ROOT / 'results/audit/dev'
    lines = ['# Đối chiếu kết quả DEV Day07', '',
             '**Đây là bản nháp AI hỗ trợ. Người học cần đọc và xác nhận đúng các file/nhãn đã xem; xác nhận benchmark không tự chuyển thành xác nhận output agent.**', '',
             '## Cách đọc', '',
             '- Context 0/1/2: không có / thiếu điều kiện hoặc nguồn / đủ bằng chứng và nguồn.',
             '- Answer 0/1/2: sai hoặc từ chối nhầm / đúng một phần / đúng và đủ theo context.',
             '- Citation phải hỗ trợ nội dung gắn với nó, không chỉ tồn tại đúng ID. Bao gồm citation trong lý do từ chối.',
             '- Strict pass: câu có đáp án đạt answer=2 và có citation được hỗ trợ; câu thiếu evidence phải từ chối đúng. Lỗi vẫn nằm trong mẫu số 17.',
             '- CER là metric exact-evidence đã khóa, có thể thấp hơn nhãn context ngữ nghĩa khi agent dùng bằng chứng thay thế hợp lệ. Không sửa gold sau khi thấy kết quả.', '',
             '| Cấu hình | Nhãn output | Lỗi | Strict pass | Gói đọc nguồn |', '|---|---:|---:|---:|---|']
    for config_id in ('C0', 'C1', 'C2', 'C3', 'C4'):
        metrics = folder / f'{config_id}_metrics_draft.json'
        if not metrics.exists():
            continue
        m = read(metrics)
        s = m['strict_end_to_end']
        lines += [f"| {config_id} | {m['reviewed_case_count']} | {m['errors']} | {s['n']}/{s['N']} | [{config_id}_REVIEW.md]({config_id}_REVIEW.md) |"]
    lines += ['', '## Các nhãn và lý do theo cấu hình', '']
    for config_id in ('C0', 'C1', 'C2', 'C3', 'C4'):
        path = folder / f'{config_id}_reviews.json'
        if not path.exists():
            continue
        lines += [f'### {config_id}', '', '| Câu | Context | Answer | Từ chối đúng | Citation hỗ trợ | Lý do |', '|---|---:|---:|---|---|---|']
        for r in read(path):
            citations = ', '.join(str(v) for v in r['citation_support']) or 'N/A'
            reason = r['reason'].replace('|', '\\|').replace('\n', ' ')
            lines += [f"| {r['query_id']} | {r['context_grade']} | {r['answer_grade']} | {r['abstention_correct']} | {citations} | {reason} |"]
        lines += ['']
    (folder / 'REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True, choices=('C0', 'C1', 'C2', 'C3', 'C4'))
    p.add_argument('--assessments', type=Path)
    args = p.parse_args()
    if args.assessments:
        apply(args.config, args.assessments)
    else:
        packet(args.config)
