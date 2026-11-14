"""Evaluator-only gold access; retrieval and agent never import benchmark labels.

Exact evidence metrics are mechanical. Semantic answer/citation/abstention grades
must be supplied with reasons by an identified reviewer; ID membership is not
used as a substitute for semantic support.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import time


def fraction(n, total):
    return {'n': n, 'N': total, 'rate': n / total if total else None}


def hit(chunk, gold):
    """One complete evidence alternative in one same-source/page chunk."""
    source_id = chunk.get('source_id', chunk.get('document_id'))
    return any(source_id == g['source_id'] and chunk.get('page') == g['page']
               and g.get('evidence', g.get('evidence_quote', ''))
               and g.get('evidence', g.get('evidence_quote')) in chunk.get('text', '')
               for g in gold)


def agent_input(case):
    """The only benchmark fields allowed to cross into runtime execution."""
    return {'id': case['id'], 'question': case['question'], 'filter': dict(case.get('filter', {}))}


def validate_cases(cases):
    seen = set()
    for case in cases:
        if case['id'] in seen:
            raise ValueError('Duplicate case ID')
        seen.add(case['id'])
        if type(case.get('answerable')) is not bool:
            raise ValueError(f"{case['id']}: answerable must be boolean")
        if case['answerable'] and not case.get('gold'):
            raise ValueError(f"{case['id']}: missing evaluator gold")


def verify_benchmark(root):
    """Verify the frozen benchmark, exact evidence and no Day06-test reuse.

    This is an artifact check, not semantic student approval of the gold.
    """
    root = Path(root)
    folder = root / 'benchmark'
    load = lambda path: json.loads(path.read_text(encoding='utf-8'))
    lock = load(folder / 'lock.json')
    for relative, expected in lock['files'].items():
        if hashlib.sha256((folder / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen benchmark file changed: {relative}')
    cases = load(folder / 'questions.json')
    validate_cases(cases)
    for split, minimum_a, minimum_u in [('dev', 15, 2), ('test', 5, 2)]:
        subset = [c for c in cases if c['split'] == split]
        if subset != load(folder / f'{split}.json'):
            raise ValueError(f'{split}: combined and separate question files differ')
        if sum(c['answerable'] for c in subset) < minimum_a or sum(not c['answerable'] for c in subset) < minimum_u:
            raise ValueError(f'{split}: insufficient benchmark cases')
    checks = {r['query_id']: r for r in load(folder / 'absence_checks.json')}
    chunks_file = root / 'data/chunks.jsonl'
    pages_file = root / 'data/pages.jsonl'
    if not chunks_file.exists() or not pages_file.exists():
        raise ValueError('Prepare the source-linked Day06 chunks and pages first')
    chunks = [json.loads(s) for s in chunks_file.read_text(encoding='utf-8').splitlines() if s.strip()]
    pages = {p['page']: p for p in [json.loads(s) for s in pages_file.read_text(encoding='utf-8').splitlines() if s.strip()]}
    checked_gold = 0
    for case in cases:
        if not case['answerable']:
            check = checks[case['absence_check_id']]
            if check['scanned_source_units'] != len(pages) or not check.get('semantic_reason'):
                raise ValueError(f"{case['id']}: missing full-corpus absence review")
            for term, expected_rows in check['terms_and_matches'].items():
                actual = [{'page': p['page'], 'count': p['text'].casefold().count(term.casefold())}
                          for p in pages.values() if term.casefold() in p['text'].casefold()]
                if actual != expected_rows:
                    raise ValueError(f"{case['id']}: absence literal-scan mismatch")
            continue
        for gold in case['gold']:
            page = pages[gold['page']]
            if page['text'][gold['page_start']:gold['page_end']] != gold['evidence']:
                raise ValueError(f"{case['id']}: source evidence offsets invalid")
            if not any(hit(c, [gold]) for c in chunks):
                raise ValueError(f"{case['id']}: no whole evidence chunk")
            checked_gold += 1
    return {'frozen_files_checked': len(lock['files']), 'questions': len(cases),
            'gold_alternatives_checked': checked_gold, 'absence_checks': len(checks),
            'human_review_status': lock.get('human_review_status', 'pending'),
            'semantic_human_review_not_inferred': True}


def evaluate_retrieval(service, cases, method, config=None):
    """Comparable original-query top-3, including explicit failed traces.

    Return (traces, summary). Unanswerables remain in runtime/error counts, but
    are never included in retrieval quality denominators.
    """
    validate_cases(cases)
    config = config or {}
    traces = []
    for case in cases:
        started = time.perf_counter()
        row = {'query_id': case['id'], 'split': case['split'], 'question': case['question'],
               'filter': case.get('filter', {}), 'filter_origin': case.get('filter_origin', 'none'),
               'method': method, 'query_kind': 'original', 'top_k': 3, 'answerable': case['answerable']}
        try:
            results = service.search(case['question'], filters=case.get('filter', {}), top_k=3, method=method)
            if not isinstance(results, list) or len(results) > 3:
                raise ValueError('Retriever must return a list with at most 3 results')
            ids = [c.get('id', c.get('chunk_id')) for c in results]
            if any(not v for v in ids) or len(set(ids)) != len(ids):
                raise ValueError('Missing or duplicate result ID')
            marked = [{**c, 'evidence_hit': bool(hit(c, case.get('gold', [])))} for c in results]
            row.update(status='ok', results=marked, actual_returned=len(marked),
                       hit1=bool(marked and marked[0]['evidence_hit']) if case['answerable'] else None,
                       hit3=any(c['evidence_hit'] for c in marked) if case['answerable'] else None)
        except Exception as exc:
            row.update(status='error', error={'type': type(exc).__name__, 'message': str(exc)},
                       results=[], actual_returned=0, hit1=False if case['answerable'] else None,
                       hit3=False if case['answerable'] else None)
        row['elapsed_ms'] = (time.perf_counter() - started) * 1000
        traces.append(row)
    answerable = [t for t in traces if t['answerable']]
    summary = {'method': method, 'query_kind': 'original', 'top_k': 3, 'config': config,
               'cases': len(traces), 'errors': sum(t['status'] == 'error' for t in traces),
               'hit1': fraction(sum(bool(t['hit1']) for t in answerable), len(answerable)),
               'hit3': fraction(sum(bool(t['hit3']) for t in answerable), len(answerable)),
               'actual_returned_distribution': dict(sorted(Counter(t['actual_returned'] for t in traces).items())),
               'elapsed_ms': {'total': sum(t['elapsed_ms'] for t in traces),
                              'median': statistics.median(t['elapsed_ms'] for t in traces) if traces else None},
               'api_cost_usd': 0, 'cost_scope': 'Local embedding/vector/lexical retrieval only; hardware/electricity excluded.'}
    return traces, summary


def final_context(trace):
    """Extract only the actual final context, never all retrieved candidates."""
    searches = [e for e in trace.get('events', []) if e.get('event') == 'search']
    supplied_context = trace.get('final_context')
    text = trace.get('final_context_text', supplied_context if isinstance(supplied_context, str) else trace.get('context'))
    ids = trace.get('context_ids')
    if text is None and searches:
        text = searches[-1].get('context', '')
    if ids is None and searches:
        ids = searches[-1].get('context_ids', [])
    text = text or ''
    ids = ids or []
    chunks = supplied_context if isinstance(supplied_context, list) else trace.get('context_chunks')
    if chunks is None:
        by_id = {}
        for event in searches:
            for chunk in event.get('results', []):
                cid = chunk.get('id', chunk.get('chunk_id'))
                by_id[cid] = chunk
        chunks = [by_id[cid] for cid in ids if cid in by_id]
    # A retrieved full chunk is not evidence in context if a selector truncated
    # it away. Require both provenance and literal evidence in the sent string.
    return text, ids, chunks


def context_hit(trace, gold):
    text, ids, chunks = final_context(trace)
    for chunk in chunks:
        if chunk.get('id', chunk.get('chunk_id')) not in ids:
            continue
        for g in gold:
            evidence = g.get('evidence', g.get('evidence_quote', ''))
            if evidence and evidence in text and hit(chunk, [g]):
                return True
    return False


def _index(rows, key, name):
    result = {}
    for row in rows:
        cid = row[key]
        if cid in result:
            raise ValueError(f'Duplicate {name}: {cid}')
        result[cid] = row
    return result


def _grade(value, cid, name):
    if type(value) is not int or value not in (0, 1, 2):
        raise ValueError(f'{cid}: {name} must be integer 0, 1 or 2')
    return value


def aggregate_agent(cases, traces, reviews):
    """Aggregate supplied semantic labels; preserve failures and review status.

    Missing reviews are reported as pending, never promoted to correct. An
    error is excluded from successful-output metrics but included as a failure
    in strict end-to-end/all-scheduled quality metrics.
    """
    validate_cases(cases)
    by_trace = _index(traces, 'query_id', 'trace')
    by_review = _index(reviews, 'query_id', 'review')
    total_answerable = sum(c['answerable'] for c in cases)
    total_unanswerable = len(cases) - total_answerable
    out = {'cases': len(cases), 'successes': 0, 'errors': 0, 'missing_traces': [], 'pending_reviews': [],
           'error_types': {}, 'tool_use': fraction(0, 0), 'tool_call_distribution': {},
           'grounded_answer': {'0': 0, '1': 0, '2': 0, 'N': 0, 'mean': None},
           'context_grades': {'0': 0, '1': 0, '2': 0, 'N': 0},
           'citation_validity': fraction(0, 0), 'answer_citation_coverage': fraction(0, 0),
           'abstention': fraction(0, 0), 'false_abstention': fraction(0, 0),
           'strict_end_to_end': fraction(0, len(cases)), 'context_evidence_rate': fraction(0, total_answerable),
           'answerable_scheduled': total_answerable, 'unanswerable_scheduled': total_unanswerable,
           'review_provenance': dict(Counter(str(r.get('review_status', 'unspecified')) for r in reviews)),
           'reviewed_case_count': 0, 'human_confirmed_case_count': 0}
    call_counts, errors, latencies, known_costs = [], Counter(), [], []
    costs_complete, token_totals = True, Counter()
    for case in cases:
        cid = case['id']
        if cid not in by_trace:
            out['missing_traces'].append(cid)
            costs_complete = False
            continue
        trace = by_trace[cid]
        elapsed = trace.get('elapsed_ms', trace.get('latency_ms'))
        if elapsed is not None:
            latencies.append(float(elapsed))
        cost = trace.get('cost_usd', trace.get('usage', {}).get('cost_usd'))
        if cost is None:
            costs_complete = False
        else:
            if not math.isfinite(float(cost)) or float(cost) < 0:
                raise ValueError(f'{cid}: invalid cost')
            known_costs.append(float(cost))
        usage = trace.get('usage', {})
        for key in ('input_tokens', 'output_tokens', 'total_tokens'):
            if isinstance(usage.get(key), (int, float)):
                token_totals[key] += usage[key]
        # CER measures the evidence actually sent, independently of whether
        # the model's final action passed runtime validation. A failed answer
        # can still have received sufficient context; keep its case in N.
        if case['answerable']:
            out['context_evidence_rate']['n'] += context_hit(trace, case['gold'])
        if trace.get('status') == 'error':
            out['errors'] += 1
            error = trace.get('error', {})
            errors[str(error.get('type', 'unknown') if isinstance(error, dict) else error)] += 1
            continue
        if trace.get('status') not in ('answered', 'abstain'):
            raise ValueError(f'{cid}: invalid trace status')
        out['successes'] += 1
        events = trace.get('events', [])
        calls = sum(e.get('event') == 'search' for e in events)
        call_counts.append(calls)
        out['tool_use']['N'] += 1
        out['tool_use']['n'] += calls > 0
        if case['answerable']:
            out['false_abstention']['N'] += 1
            out['false_abstention']['n'] += trace['status'] == 'abstain'
        if cid not in by_review:
            out['pending_reviews'].append(cid)
            continue
        review = by_review[cid]
        if not isinstance(review.get('reason'), str) or not review['reason'].strip():
            raise ValueError(f'{cid}: review requires a concrete reason')
        citations = trace.get('citations', [])
        support = review.get('citation_support')
        reasons = review.get('citation_reasons')
        if not isinstance(support, list) or len(support) != len(citations) or any(type(v) is not bool for v in support):
            raise ValueError(f'{cid}: one semantic boolean label per citation is required')
        if not isinstance(reasons, list) or len(reasons) != len(citations) or any(not isinstance(s, str) or not s.strip() for s in reasons):
            raise ValueError(f'{cid}: one substantive reason per citation is required')
        _, context_ids, _ = final_context(trace)
        for citation, supported in zip(citations, support):
            if supported and citation not in context_ids:
                raise ValueError(f'{cid}: supported citation absent from final context')
        out['reviewed_case_count'] += 1
        out['human_confirmed_case_count'] += review.get('human_confirmed') is True
        out['citation_validity']['n'] += sum(support)
        out['citation_validity']['N'] += len(citations)
        if trace['status'] == 'answered':
            out['answer_citation_coverage']['N'] += 1
            out['answer_citation_coverage']['n'] += bool(citations)
        if case['answerable']:
            grade = _grade(review.get('answer_grade'), cid, 'answer_grade')
            context_grade = _grade(review.get('context_grade'), cid, 'context_grade')
            if trace['status'] == 'abstain' and grade != 0:
                raise ValueError(f'{cid}: false abstention must receive answer_grade=0')
            out['grounded_answer'][str(grade)] += 1
            out['grounded_answer']['N'] += 1
            out['context_grades'][str(context_grade)] += 1
            out['context_grades']['N'] += 1
            passed = grade == 2 and bool(citations) and all(support) and trace['status'] == 'answered'
        else:
            correct = review.get('abstention_correct')
            if type(correct) is not bool:
                raise ValueError(f'{cid}: abstention_correct must be a semantic boolean label')
            if correct and trace['status'] != 'abstain':
                raise ValueError(f'{cid}: correct abstention label contradicts actual status')
            out['abstention']['N'] += 1
            out['abstention']['n'] += correct
            passed = correct
        out['strict_end_to_end']['n'] += passed
    for key in ('tool_use', 'citation_validity', 'answer_citation_coverage', 'abstention', 'false_abstention', 'strict_end_to_end', 'context_evidence_rate'):
        out[key] = fraction(out[key]['n'], out[key]['N'])
    g = out['grounded_answer']
    if g['N']:
        g['mean'] = (g['1'] + 2*g['2']) / g['N']
    out['completion'] = fraction(out['successes'], len(cases))
    out['tool_call_distribution'] = dict(sorted(Counter(call_counts).items()))
    out['error_types'] = dict(errors)
    out['elapsed_ms'] = {'N': len(latencies), 'median': statistics.median(latencies) if latencies else None,
                         'total': sum(latencies), 'mean': statistics.mean(latencies) if latencies else None}
    out['cost'] = {'known_total_usd': sum(known_costs), 'known_case_count': len(known_costs),
                   'complete': costs_complete and len(known_costs) == len(cases),
                   'mean_per_scheduled_case_usd': sum(known_costs) / len(cases) if costs_complete and cases else None,
                   'unknown_is_not_zero': True}
    out['tokens'] = dict(token_totals)
    out['all_semantic_labels_present'] = not out['pending_reviews'] and not out['missing_traces']
    return out


def audit_template(cases, traces):
    """Create ungraded review rows without falsely asserting human approval."""
    by_trace = _index(traces, 'query_id', 'trace')
    result = []
    for case in cases:
        trace = by_trace.get(case['id'])
        if not trace or trace.get('status') == 'error':
            continue
        citations = trace.get('citations', [])
        result.append({'query_id': case['id'], 'answer_grade': None if case['answerable'] else None,
                       'context_grade': None, 'citation_support': [None] * len(citations),
                       'citation_reasons': [''] * len(citations), 'abstention_correct': None,
                       'reason': '', 'reviewer': '', 'review_status': 'pending', 'human_confirmed': False})
    return result
