"""Author and freeze the basic Day07 benchmark before retrieval experiments.

No model/retrieval call is made here. Gold is evaluator-only and is mechanically
checked against the immutable normalized Day06 corpus and B chunks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAY06 = ROOT.parent / 'K5-L3-Day06-DataIngestionEngineering'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build():
    out = ROOT / 'benchmark'
    if (out / 'lock.json').exists():
        raise RuntimeError('Benchmark is frozen. Do not overwrite after experiments; version a new benchmark explicitly.')
    pages = [json.loads(s) for s in (DAY06 / 'data/pages.jsonl').read_text(encoding='utf-8').splitlines()]
    chunks = [json.loads(s) for s in (DAY06 / 'results/chunks_B.jsonl').read_text(encoding='utf-8').splitlines()]
    page_by_id = {p['page']: p for p in pages}
    old = json.loads((DAY06 / 'benchmark/questions.json').read_text(encoding='utf-8'))
    cases = []

    def enrich(case):
        for g in case['gold']:
            page = page_by_id[g['page']]
            assert page['document_id'] == g['source_id']
            pos = page['text'].index(g['evidence'])
            g.update(source=page['source'], page_start=pos, page_end=pos + len(g['evidence']),
                     source_start=page['start'] + pos, source_end=page['start'] + pos + len(g['evidence']))
            g['valid_chunk_ids'] = [c['chunk_id'] for c in chunks if c['page'] == g['page'] and g['evidence'] in c['text']]
            assert g['valid_chunk_ids'], f"{case['id']}: no complete evidence in B"
        case['gold_validation'] = 'Exact substring, source/page/offset and complete B chunk mechanically validated; AI-assisted authoring, human semantic review pending.'
        cases.append(case)

    for q in old:
        if q['split'] != 'dev':
            continue
        enrich({'id': q['id'], 'split': 'dev', 'question': q['question'], 'answerable': True,
                'expected_answer': q['expected_answer'], 'filter': q['filter'], 'filter_origin': q['filter_origin'],
                'gold': [{'source_id': g['source_id'], 'page': g['page'], 'evidence': g['evidence_quote']}
                         for g in q['gold_alternatives']],
                'origin': 'Day06 development question, revalidated against the reused B chunks; no Day06 test reused.'})

    fresh = [
        ('T01', 'In the library reference, with json ensure_ascii=False, which characters still have to be escaped?',
         'Quotation mark, reverse solidus (backslash), and control characters U+0000 through U+001F still must be escaped.',
         'library_json:u002', 'If False , all characters will be outputted as-is, except for\nthe characters that must be escaped: quotation mark, reverse solidus,\nand the control characters U+0000 through U+001F.'),
        ('T02', 'What does json.load pass to a supplied parse_float callback, and what happens when the callback is None?',
         'It passes the string of every JSON float; None is equivalent to float(num_str).',
         'library_json:u003', 'parse_float ( callable | None) – If set, a function that is called with\nthe string of every JSON float to be decoded.\nIf None (the default), it is equivalent to float(num_str) .'),
        ('T03', 'In the library reference, how does csv.DictReader handle rows with more or fewer fields than fieldnames, including the defaults?',
         'Extra fields go in a list under restkey (default None); missing fields are filled with restval (default None).',
         'library_csv:u002', 'If a row has more fields than fieldnames, the remaining data is put in a\nlist and stored with the fieldname specified by restkey (which defaults\nto None ).  If a non-blank row has fewer fields than fieldnames, the\nmissing values are filled-in with the value of restval (which defaults\nto None ).'),
        ('T04', 'Why can csvreader.line_num differ from the number of records returned?',
         'It counts lines read from the source iterator, while a record can span multiple lines.',
         'library_csv:u005', 'The number of lines read from the source iterator. This is not the same as the\nnumber of records returned, as records can span multiple lines.'),
        ('T05', 'In the library reference, how does Path.resolve behave for a nonexistent path or a symlink loop when strict is True versus False?',
         'With strict=True it raises OSError. With strict=False it resolves as far as possible and appends the remainder without checking existence.',
         'library_pathlib:u007', 'If a path doesn’t exist or a symlink loop is encountered, and strict is True , OSError is raised.  If strict is False , the path is\nresolved as far as possible and any remainder is appended without checking\nwhether it exists.'),
    ]
    for cid, question, answer, page, evidence in fresh:
        scoped = question.startswith('In the library reference,')
        enrich({'id': cid, 'split': 'test', 'question': question, 'answerable': True,
                'expected_answer': answer, 'filter': {'document_type': 'library_reference'} if scoped else {},
                'filter_origin': 'Explicit library-reference scope in question, supplied before retrieval.' if scoped else 'none',
                'gold': [{'source_id': page.split(':')[0], 'page': page, 'evidence': evidence}],
                'origin': 'New Day07 held-out topic; not a paraphrase of the five Day06 test questions.'})

    missing = [
        ('DU01', 'dev', 'What measured throughput in MB/s does json.dumps achieve on a Ryzen 7 7800X3D in the benchmark supplied with this corpus?',
         ['7800X3D', 'Ryzen', 'MB/s'], 'library_json',
         'The snapshot documents JSON API behavior and examples, not a hardware throughput experiment. No CPU/workload measurement or MB/s table is supplied.'),
        ('DU02', 'dev', 'What exact maximum recursion depth is guaranteed for pathlib.Path.walk on the Acme network filesystem used by our deployment?',
         ['Acme', 'network filesystem', 'maximum recursion depth'], 'library_pathlib',
         'The snapshot documents traversal options, not the private Acme filesystem/deployment. It provides no deployment-specific guaranteed recursion-depth number.'),
        ('TU01', 'test', 'What p95 latency in milliseconds is guaranteed for csv.DictReader when processing our 1 GB upload workload on Windows?',
         ['p95', '1 GB', 'latency'], 'library_csv',
         'CSV documentation specifies parsing semantics, not the private upload workload, hardware or a latency SLA. No p95 timing guarantee is stated.'),
        ('TU02', 'test', 'Which backup bucket and retention period does our production project use to restore files deleted with Path.unlink?',
         ['backup bucket', 'retention period', 'production project'], 'library_pathlib',
         'Path.unlink documents removal and missing_ok, not the production project backup configuration. Neither a bucket identity nor a retention period is given.'),
    ]
    checks = []
    for cid, split, question, terms, subject, reason in missing:
        hits = {term: [{'page': p['page'], 'count': p['text'].casefold().count(term.casefold())}
                       for p in pages if term.casefold() in p['text'].casefold()] for term in terms}
        related = [{'page': p['page'], 'source': p['source'], 'sha256': hashlib.sha256(p['text'].encode()).hexdigest()}
                   for p in pages if p['document_id'] == subject]
        checks.append({'query_id': cid, 'scan_method': 'Case-insensitive literal scan of every normalized source unit, plus semantic inspection of all relevant source units; absence is not inferred from top-k.',
                       'scanned_source_units': len(pages), 'scanned_documents': len({p['document_id'] for p in pages}),
                       'terms_and_matches': hits, 'relevant_units_inspected': related, 'semantic_reason': reason,
                       'conclusion': 'Insufficient evidence in this fixed corpus; do not supply a fabricated measurement or private configuration.',
                       'review_status': 'AI-assisted corpus inspection; human review pending'})
        cases.append({'id': cid, 'split': split, 'question': question, 'answerable': False,
                      'expected_answer': 'State that the supplied corpus does not provide the requested deployment/measurement facts; do not invent them.',
                      'filter': {}, 'filter_origin': 'none', 'gold': [], 'absence_check_id': cid,
                      'gold_validation': 'AI-assisted absence review; human semantic review pending.'})

    cases.sort(key=lambda c: (c['split'] == 'test', not c['answerable'], c['id']))
    dev = [c for c in cases if c['split'] == 'dev']
    test = [c for c in cases if c['split'] == 'test']
    assert len(dev) == 17 and len(test) == 7
    protocol = {
        'version': 'day07-basic-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'Basic 85-point lab only. Bonus deferred by the student.',
        'corpus': {'source_day06_commit': '64c4ab778f81ba5608d4b2b57315f6369aedd0fd', 'pages_sha256': digest(DAY06 / 'data/pages.jsonl'),
                   'chunks_B_sha256': digest(DAY06 / 'results/chunks_B.jsonl'), 'source_units': len(pages), 'chunks': len(chunks)},
        'split': {'dev': {'answerable': 15, 'unanswerable': 2}, 'test': {'answerable': 5, 'unanswerable': 2}},
        'test_independence': 'Five new library-reference topics, not the previously inspected Day06 held-out questions. No test output will be used to modify configurations or labels.',
        'agent_input_projection': ['id', 'question', 'filter'],
        'retrieval_hit': 'One returned chunk must contain one complete exact evidence alternative, matching source_id and page. Multiple alternatives are OR. Unanswerable cases excluded from denominator.',
        'original_query_ranking': 'Run original user question with provided filter and fixed top_k=3 for dense, bm25 and hybrid. Rewritten-query pipeline traces reported separately.',
        'context_evidence_rate': 'Check exact gold evidence with source/page against actual final context chunks/text sent to the last model call; never infer from retrieved ranking or unused candidates.',
        'context_grade': {'0': 'No relevant evidence in final context', '1': 'Relevant but incomplete condition or source', '2': 'All required evidence and source present'},
        'answer_grade': {'0': 'Incorrect, unsupported, or false abstention', '1': 'Partially correct/complete with evidence', '2': 'Correct and complete, grounded in final context'},
        'citation_support': 'Manual semantic label and reason for every cited occurrence/ID: must appear in actual final context and support the associated answer conditions. ID validity alone never suffices.',
        'abstention': 'Unanswerable accepted only if the response actually declines the requested unsupported facts without adding invented assertions. False abstention on answerable is reported separately.',
        'selection_order': ['maximize strict_end_to_end_pass_n_over_all_dev_including_errors', 'maximize context_evidence_rate', 'minimize false_abstention_count',
                            'minimize mean_cost_usd_if_complete_known', 'minimize median_end_to_end_latency_ms', 'lexicographic_config_id'],
        'selection_missing_cost_rule': 'If any tied configuration has unknown cost, skip cost comparison for the entire tie group; do not replace unknown costs with zero.',
        'errors': 'Save model/store errors, retries and any known usage separately. Strict end-to-end n/N keeps all scheduled cases. Quality metrics on successful outputs also report missing labels and failed-case counts.',
        'audit': 'AI-assisted drafts remain identified until the student explicitly reviews the current benchmark/answers/citations. Day06 audit approval is not transferable.',
        'freeze': 'Benchmark and protocol are locked before any Day07 dev retrieval run; selected config/prompt/code/model/reviews locked before test.'
    }
    save(out / 'dev.json', dev)
    save(out / 'test.json', test)
    save(out / 'questions.json', cases)
    save(out / 'absence_checks.json', checks)
    save(out / 'protocol.json', protocol)
    review = ['# Day07 benchmark source review', '', '**Status: AI-assisted authoring; student review pending.**', '',
              'Review source meaning, required conditions and absence reasoning. This file is a review packet, not an assertion that a human approved the labels.', '']
    for c in cases:
        review += [f"## {c['id']} · {c['split']} · {'answerable' if c['answerable'] else 'insufficient evidence'}", c['question'], '', f"Expected: {c['expected_answer']}", '']
        for g in c['gold']:
            review += [f"Source: {g['source']} · {g['page']} · page offsets [{g['page_start']},{g['page_end']})", '', '```text', g['evidence'], '```', '']
        if not c['answerable']:
            check = next(x for x in checks if x['query_id'] == c['id'])
            review += [check['semantic_reason'], f"Full corpus scan: {check['scanned_source_units']} units; see absence_checks.json.", '']
    (out / 'REVIEW.md').write_text('\n'.join(review), encoding='utf-8')
    paths = ['dev.json', 'test.json', 'questions.json', 'absence_checks.json', 'protocol.json', 'REVIEW.md']
    save(out / 'lock.json', {'version': 'day07-basic-v1', 'locked_at': datetime.now(timezone.utc).isoformat(),
                            'files': {p: digest(out / p) for p in paths}, 'human_review_status': 'pending'})
    print(json.dumps({'locked': True, 'dev': len(dev), 'test': len(test), 'review': 'benchmark/REVIEW.md'}))


if __name__ == '__main__':
    build()
