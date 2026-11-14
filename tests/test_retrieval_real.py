"""Synthetic ranking tests and real local index checks; no benchmark questions."""
from pathlib import Path
import tempfile
import unittest

from src.retrieval import ROOT, BM25, RetrievalService, reciprocal_rank_fusion, validate_filters, read_lines, _validate_source_chunks


def chunk(cid, text, kind="tutorial"):
    return {"id": cid, "text": text, "metadata": {"document_type": kind}}


class RankingTests(unittest.TestCase):
    def test_bm25_ranks_distinctive_terms_and_zero_matches(self):
        index = BM25([chunk("a", "apple apple banana"), chunk("b", "banana pear"), chunk("c", "orange")])
        self.assertEqual(index.search("APPLE")[0]["id"], "a")
        self.assertEqual(index.search("nothing_in_the_corpus"), [])

    def test_filters_are_applied_in_bm25_and_gold_filters_forbidden(self):
        index = BM25([chunk("a", "apple apple", "tutorial"), chunk("b", "apple", "library")])
        self.assertEqual([c["id"] for c in index.search("apple", {"document_type": "library"})], ["b"])
        for bad in ({"page": "gold"}, {"source_id": "gold"}, {"document_type": ["library"]}):
            with self.assertRaises(ValueError):
                validate_filters(bad)

    def test_rrf_merges_ranks_not_incommensurate_scores(self):
        a = {**chunk("a", "a"), "score": .99}
        b = {**chunk("b", "b"), "score": .98}
        lexical_a = {**a, "score": 300}
        lexical_b = {**b, "score": 200}
        merged = reciprocal_rank_fusion([a, b], [lexical_b, lexical_a], top_k=3)
        self.assertEqual([c["id"] for c in merged], ["a", "b"])
        self.assertAlmostEqual(merged[0]["score"], 1 / 61 + 1 / 62)
        self.assertEqual(merged[0]["branch_ranks"], {"dense": 1, "bm25": 2})
        self.assertEqual(len({c["id"] for c in merged}), len(merged))

    def test_rrf_duplicate_branch_ids_do_not_double_count(self):
        a = {**chunk("a", "a"), "score": .5}
        merged = reciprocal_rank_fusion([a, a], [])
        self.assertAlmostEqual(merged[0]["score"], 1 / 61)


@unittest.skipUnless((ROOT / "data/day6_manifest.json").exists(), "Run scripts/prepare_data.py for real local store checks")
class RealIndexTests(unittest.TestCase):
    def test_01_preserved_offsets_and_ids_for_all_312_chunks(self):
        chunks = read_lines(ROOT / "data/chunks.jsonl")
        pages = read_lines(ROOT / "data/pages.jsonl")
        _validate_source_chunks(chunks, pages)
        self.assertTrue(all(c["id"] == c["chunk_id"] and c["source_id"] == c["document_id"] for c in chunks))

    def test_02_real_methods_filters_persistence_and_error_states(self):
        # Construct a query from arbitrary source text, not any dev/test benchmark.
        text = read_lines(ROOT / "data/chunks.jsonl")[0]["text"][:96]
        with RetrievalService(ROOT) as service:
            first = service.search(text, method="dense")
            for method in ("dense", "bm25", "hybrid"):
                results = service.search(text, method=method)
                self.assertTrue(results)
                self.assertLessEqual(len(results), 3)
                self.assertEqual([c["rank"] for c in results], list(range(1, len(results) + 1)))
                self.assertTrue(all(set(("id", "source_id", "source", "page", "text", "metadata", "score")) <= c.keys() for c in results))
                filtered = service.search(text, filters={"document_type": "library"}, method=method)
                self.assertTrue(all(c["metadata"]["document_type"] == "library" for c in filtered))
                if method == "hybrid":
                    self.assertTrue(all(c["branch_ranks"] for c in results))
                self.assertEqual(service.search(text, filters={"version": "absent_version"}, method=method), [])
            with self.assertRaises(ValueError):
                service.search(text, filters={"page": "gold_page"})
            with self.assertRaises(ValueError):
                service.search(text, top_k=0)
            with self.assertRaises(ValueError):
                service.search(text, method="wrong")
            with self.assertRaises(ValueError):
                service.search("")
        with self.assertRaises(RuntimeError):
            service.search(text)
        with RetrievalService(ROOT) as reopened:
            second = reopened.search(text, method="dense")
        self.assertEqual([c["id"] for c in first], [c["id"] for c in second])
        self.assertEqual([c["score"] for c in first], [c["score"] for c in second])


if __name__ == "__main__":
    unittest.main()
