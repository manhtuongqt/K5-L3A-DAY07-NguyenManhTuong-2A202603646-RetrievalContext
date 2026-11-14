import unittest
from pathlib import Path
from src.evaluation import hit, context_hit, evaluate_retrieval, aggregate_agent, agent_input, verify_benchmark


GOLD = [{'source_id': 'doc', 'page': 'doc:1', 'evidence': 'must keep condition'}]
CHUNK = {'id': 'c1', 'source_id': 'doc', 'page': 'doc:1', 'text': 'You must keep condition.', 'source': 'https://example.org'}
CASES = [{'id': 'D1', 'split': 'dev', 'answerable': True, 'question': 'Q?', 'gold': GOLD, 'expected_answer': 'Secret gold'},
         {'id': 'U1', 'split': 'dev', 'answerable': False, 'question': 'Missing?', 'gold': []}]


class EvaluationTest(unittest.TestCase):
    def test_real_benchmark_lock_and_source_evidence(self):
        root = Path(__file__).resolve().parents[1]
        report = verify_benchmark(root)
        self.assertEqual(report['questions'], 24)
        self.assertGreaterEqual(report['gold_alternatives_checked'], 20)
        self.assertEqual(report['absence_checks'], 4)
        self.assertTrue(report['semantic_human_review_not_inferred'])

    def test_exact_source_page_and_quote(self):
        self.assertTrue(hit(CHUNK, GOLD))
        self.assertFalse(hit({**CHUNK, 'page': 'wrong'}, GOLD))
        self.assertFalse(hit({**CHUNK, 'text': 'must keep'}, GOLD))
        self.assertFalse(hit(CHUNK, []))

    def test_no_gold_projection(self):
        self.assertEqual(set(agent_input(CASES[0])), {'id', 'question', 'filter'})
        self.assertNotIn('gold', agent_input(CASES[0]))

    def test_context_must_be_actual_sent_text(self):
        trace = {'final_context': [CHUNK], 'context_ids': ['c1'], 'final_context_text': 'You must keep'}
        self.assertFalse(context_hit(trace, GOLD))
        trace['final_context_text'] = '[c1] You must keep condition.'
        self.assertTrue(context_hit(trace, GOLD))
        trace['context_ids'] = []
        self.assertFalse(context_hit(trace, GOLD))

    def test_unanswerable_not_retrieval_denominator(self):
        class Service:
            def search(self, query, **kwargs):
                self.assertion = kwargs
                return [CHUNK]
        traces, summary = evaluate_retrieval(Service(), CASES, 'dense')
        self.assertEqual(summary['hit1']['N'], 1)
        self.assertEqual(summary['hit1']['n'], 1)
        self.assertIsNone(traces[1]['hit1'])
        self.assertEqual(traces[0]['actual_returned'], 1)

    def test_errors_stay_in_fixed_retrieval_denominator(self):
        class Broken:
            def search(self, *args, **kwargs):
                raise RuntimeError('store unavailable')
        traces, summary = evaluate_retrieval(Broken(), CASES, 'dense')
        self.assertEqual(summary['errors'], 2)
        self.assertEqual(summary['hit3'], {'n': 0, 'N': 1, 'rate': 0})
        self.assertEqual(traces[0]['error']['message'], 'store unavailable')

    def good_trace(self):
        return {'query_id': 'D1', 'status': 'answered', 'answer': 'Condition [c1]', 'citations': ['c1'],
                'final_context': [CHUNK], 'final_context_text': CHUNK['text'], 'context_ids': ['c1'],
                'events': [{'event': 'search', 'results': [CHUNK]}], 'elapsed_ms': 10}

    def good_review(self):
        return {'query_id': 'D1', 'answer_grade': 2, 'context_grade': 2, 'citation_support': [True],
                'citation_reasons': ['Contains the required condition.'], 'reason': 'Answer states the whole condition.',
                'review_status': 'AI-assisted draft pending human review', 'human_confirmed': False}

    def test_semantic_support_is_not_id_validity(self):
        review = self.good_review()
        review['citation_support'] = [False]
        report = aggregate_agent(CASES[:1], [self.good_trace()], [review])
        self.assertEqual(report['citation_validity']['n'], 0)
        self.assertEqual(report['strict_end_to_end']['n'], 0)
        self.assertEqual(report['context_evidence_rate']['n'], 1)
        self.assertEqual(report['human_confirmed_case_count'], 0)

    def test_id_absent_context_cannot_be_supported(self):
        trace = self.good_trace()
        trace['context_ids'] = []
        with self.assertRaises(ValueError):
            aggregate_agent(CASES[:1], [trace], [self.good_review()])

    def test_failed_case_counts_in_strict_denominator_unknown_cost(self):
        traces = [self.good_trace(), {'query_id': 'U1', 'status': 'error', 'error': {'type': 'timeout'}}]
        report = aggregate_agent(CASES, traces, [self.good_review()])
        self.assertEqual(report['strict_end_to_end'], {'n': 1, 'N': 2, 'rate': .5})
        self.assertEqual(report['errors'], 1)
        self.assertFalse(report['cost']['complete'])
        self.assertIsNone(report['cost']['mean_per_scheduled_case_usd'])

    def test_no_review_remains_pending(self):
        report = aggregate_agent(CASES[:1], [self.good_trace()], [])
        self.assertEqual(report['pending_reviews'], ['D1'])
        self.assertFalse(report['all_semantic_labels_present'])
        self.assertEqual(report['strict_end_to_end']['n'], 0)

    def test_contradictory_abstention_label_rejected(self):
        trace = {**self.good_trace(), 'query_id': 'U1'}
        review = {**self.good_review(), 'query_id': 'U1', 'abstention_correct': True}
        with self.assertRaises(ValueError):
            aggregate_agent(CASES[1:], [trace], [review])


if __name__ == '__main__':
    unittest.main()
