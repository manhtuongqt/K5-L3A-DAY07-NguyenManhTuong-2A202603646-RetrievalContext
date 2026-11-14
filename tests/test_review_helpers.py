import unittest
from scripts.review_helpers import evaluation_trace, citation_counts


class CitationProjectionTest(unittest.TestCase):
    def test_abstention_inline_is_audited_without_mutating_raw(self):
        cid = 'a' * 32
        raw = {'status': 'abstain', 'answer': f'No guarantee is provided. See [{cid}].', 'citations': []}
        view = evaluation_trace(raw)
        self.assertEqual(raw['citations'], [])
        self.assertEqual(view['citations'], [cid])
        self.assertEqual(view['extra_inline_citations'], [cid])
        self.assertEqual(view['declared_citations'], [])

    def test_distinct_ids_and_occurrences_are_separate_and_idempotent(self):
        cid = 'b' * 32
        raw = {'answer': f'One [{cid}], two [{cid}].', 'citations': []}
        once = evaluation_trace(raw)
        self.assertEqual(len(once['citations']), 1)
        self.assertEqual(len(once['citation_occurrences']), 2)
        self.assertEqual(evaluation_trace(once), once)
        self.assertEqual(citation_counts([raw]), citation_counts([once]))

    def test_uuid_and_unknown_citation_still_require_review(self):
        uid = '12345678-1234-1234-1234-123456789abc'
        raw = {'answer': f'Claim [{uid}] [not-a-chunk]', 'citations': []}
        self.assertEqual(evaluation_trace(raw)['citations'], [uid])


if __name__ == '__main__':
    unittest.main()
