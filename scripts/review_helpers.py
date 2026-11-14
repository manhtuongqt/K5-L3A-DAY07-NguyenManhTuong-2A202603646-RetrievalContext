"""Evaluation-only view of raw traces; never modify model inputs or run files.

Audit every distinct cited ID, including citations inside abstention reasons.
Occurrence counts remain separate from the per-distinct-ID support metric.
"""
from copy import deepcopy
import re

INLINE = re.compile(r'\[((?:[a-fA-F0-9]{32})|(?:[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}))\]')


def evaluation_trace(trace):
    view = deepcopy(trace)
    declared = list(trace.get('declared_citations', trace.get('citations', [])))
    answer = trace.get('answer', '')
    occurrences = [{'id': match.group(1), 'start': match.start(), 'end': match.end(), 'field': 'answer'}
                   for match in INLINE.finditer(answer)]
    unique = list(dict.fromkeys(declared + [m['id'] for m in occurrences]))
    view.update(declared_citations=declared, citations=unique,
                citation_occurrences=occurrences,
                extra_inline_citations=[cid for cid in unique if cid not in declared],
                citation_evaluation_policy='distinct union of declared and inline answer IDs, including abstention; occurrences counted separately; original raw trace preserved')
    if trace.get('status') == 'error' and not trace.get('error'):
        raw_errors = trace.get('errors', [])
        last = raw_errors[-1] if raw_errors else {}
        view['error'] = {'type': trace.get('reason') or last.get('type', 'unknown'),
                         'details': deepcopy(raw_errors),
                         'source': 'Runtime reason/errors fields, projected for evaluator compatibility; raw trace preserved.'}
    return view


def citation_counts(traces):
    views = [evaluation_trace(t) for t in traces]
    return {'distinct_cited_ids_per_answer_total': sum(len(t['citations']) for t in views),
            'inline_occurrences_total': sum(len(t['citation_occurrences']) for t in views),
            'declared_cited_ids_total': sum(len(t['declared_citations']) for t in views),
            'extra_inline_ids_total': sum(len(t['extra_inline_citations']) for t in views),
            'policy': 'Support labels per distinct citation ID within each answer, not per repeated printed occurrence; both denominators are disclosed.'}
