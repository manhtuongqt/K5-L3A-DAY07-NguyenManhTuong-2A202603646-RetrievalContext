"""Offline mutation tests for trace audit; no model/API/store/heldout data."""
import copy
import hashlib
import json
import unittest

from scripts.verify_runtime_traces import verify_trace, verify_traces
from src.agent_runtime import run_agent

CHUNK = {"id": "c1", "text": "Document evidence", "source_id": "doc", "source": "doc.html", "page": "doc:u001",
         "metadata": {"document_type": "tutorial"}, "start": 0, "end": 17, "source_start": 10, "source_end": 27}
PAGE = {"page": "doc:u001", "start": 10, "text": "Document evidence and more."}


def fixture():
    class Model:
        count = 0
        def complete(self, messages, **kwargs):
            self.count += 1
            name, args = ("search", {"query": "documentation"}) if self.count == 1 else ("answer", {"answer": "Evidence [c1]", "citations": ["c1"]})
            raw = {"prompt_tokens": 12, "completion_tokens": 6, "x_ckey": {"cost": 2, "cost_is_estimate": False}}
            usage = {"input_tokens": 12, "output_tokens": 6, "raw": raw}
            return {"text": "", "tool_calls": [{"name": name, "arguments": args}], "usage": usage,
                    "attempts": [{"status": "success", "usage": usage}]}
    class Retriever:
        def search(self, query, **kwargs):
            return [dict(CHUNK)]
    return run_agent({"id": "fixture", "question": "What evidence?", "filter": {"document_type": "tutorial"}}, Model(), Retriever(),
                     {"id": "offline-test", "action_protocol": "native_tools", "max_searches": 1})


class TraceVerificationTests(unittest.TestCase):
    def check_mutation(self, mutate, expected):
        trace = fixture()
        mutate(trace)
        report = verify_trace(trace, [CHUNK], [PAGE])
        self.assertFalse(report["passed"])
        self.assertIn(expected, [e["code"] for e in report["errors"]])

    def test_genuine_fixture_passes_without_claiming_semantic_or_human_audit(self):
        out = verify_traces([fixture()], [CHUNK], [PAGE])
        self.assertTrue(out["passed"], out["errors"])
        self.assertFalse(out["semantic_and_human_audit_verified"])
        self.assertEqual(out["results"][0]["native_cost_amounts"], [2, 2])
        self.assertIn("not inferred as USD", out["results"][0]["native_cost_units"])

    def test_changed_source_text_is_detected(self):
        self.check_mutation(lambda t: t["events"][0]["results"][0].update(text="Tampered"), "chunk_source_mismatch")

    def test_changed_offsets_are_detected(self):
        self.check_mutation(lambda t: t["final_context"][0].update(source_start=11), "document_offset")

    def test_gold_in_user_payload_is_detected(self):
        def mutate(t):
            message = t["model_calls"][1]["request_messages"][1]
            payload = json.loads(message["content"])
            payload["gold"] = [{"evidence": "leaked"}]
            message["content"] = json.dumps(payload)
        self.check_mutation(mutate, "benchmark_leakage_key")

    def test_context_that_was_not_sent_is_detected(self):
        self.check_mutation(lambda t: t.update(final_context_text="different"), "final_not_actually_sent")

    def test_changed_prompt_and_native_schema_are_detected(self):
        self.check_mutation(lambda t: t["model_calls"][0]["request_messages"][0].update(content="different"), "system_prompt_hash")
        self.check_mutation(lambda t: t["model_calls"][1].update(request_tools=[]), "native_schema_state")

    def test_fake_actual_result_count_is_detected(self):
        self.check_mutation(lambda t: t["events"][0].update(actual_results=3), "actual_result_count")

    def test_native_cost_cannot_be_renamed_usd_without_conversion_evidence(self):
        self.check_mutation(lambda t: t["model_calls"][0]["usage"].update(cost_usd=2), "native_cost_mislabeled_usd")

    def test_empty_or_malformed_is_not_a_pass(self):
        self.assertFalse(verify_traces([], [CHUNK])["passed"])
        self.assertFalse(verify_trace({}, [CHUNK])["passed"])

    def test_undeclared_inline_abstention_refs_are_warning_not_false_integrity_failure(self):
        trace = fixture()
        ref = "a" * 32
        trace["status"] = "abstain"
        trace["answer"] = f"Insufficient evidence [{ref}]"
        trace["citations"] = []
        trace["model_calls"][-1]["tool_calls"] = [{"name": "abstain", "arguments": {"reason": f"Missing [{ref}]"}}]
        report = verify_trace(trace, [CHUNK], [PAGE])
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["undeclared_inline_citation_count"], 1)
        self.assertEqual(report["warnings"][0]["code"], "undeclared_inline_citations")


if __name__ == "__main__":
    unittest.main()
