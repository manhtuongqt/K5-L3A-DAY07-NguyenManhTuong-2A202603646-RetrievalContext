"""Offline trace-integrity audit, independent of semantic grading and API/store.

Does not read benchmark gold or open Qdrant. Passing proves internal trace and
source consistency, not correctness of answers/citation support or human audit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agent_runtime import parse_action
from src.context import pack_context, rank_candidates
from src.lab_common import ROOT, read_json, read_jsonl, write_json, now


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def forbidden_keys(value):
    banned = {"gold", "expected_answer", "answerable", "expected_evidence", "gold_evidence"}
    if isinstance(value, dict):
        return sorted(set(value).intersection(banned)) + [key for child in value.values() for key in forbidden_keys(child)]
    if isinstance(value, list):
        return [key for child in value for key in forbidden_keys(child)]
    return []


def verify_trace(trace, chunks, pages=None):
    """Return errors with stable codes; never mutate trace or infer human labels."""
    errors, checks = [], 0
    def check(condition, code, detail=""):
        nonlocal checks
        checks += 1
        if not condition:
            errors.append({"code": code, "detail": detail})
    try:
        chunk_map = chunks if isinstance(chunks, dict) else {c["id"]: c for c in chunks}
        page_map = None if pages is None else (pages if isinstance(pages, dict) else {p["page"]: p for p in pages})
        config = trace["config"]
        top_k, max_searches = int(config.get("top_k", 3)), int(config.get("max_searches", 1))
        max_repairs = int(config.get("max_action_repairs", 1))
        budget = int(config.get("budget_chars", config.get("context_budget_chars", 4000)))
        max_chunks = int(config.get("context_top_k", top_k))
        searches = [e for e in trace["events"] if e.get("event") == "search"]
        search_errors = [e for e in trace["events"] if e.get("event") == "search_error"]
        calls = trace["model_calls"]
        check(trace["status"] in ("answered", "abstain", "error"), "status")
        check(len(searches) <= max_searches, "search_limit")
        check(trace["tool_calls"] == len(searches) + len(search_errors), "tool_call_count")
        check(len(calls) <= max_searches + max_repairs + 2, "model_call_limit")
        check(trace.get("total_calls") == len(calls), "total_call_count")
        check(trace.get("total_errors") == len(trace.get("errors", [])), "error_count")
        check(trace.get("retries") == sum(max(0, len(c.get("attempts", [])) - 1) for c in calls), "retry_count")
        for location, chunk in [(f"search:{i}:{j}", c) for i, event in enumerate(searches) for j, c in enumerate(event["results"])] + [
                (f"final:{i}", c) for i, c in enumerate(trace["final_context"])]:
            canonical = chunk_map.get(chunk.get("id"))
            check(canonical is not None, "unknown_chunk", location)
            if canonical is None:
                continue
            for key in ("text", "source_id", "source", "page", "metadata", "start", "end", "source_start", "source_end"):
                if key in canonical:
                    check(chunk.get(key) == canonical[key], "chunk_source_mismatch", f"{location}:{key}")
            if page_map is not None:
                page = page_map.get(chunk.get("page"))
                check(page is not None, "unknown_page", location)
                if page is not None:
                    check(chunk["text"] == page["text"][chunk["start"]:chunk["end"]], "page_offset_text", location)
                    check(chunk["source_start"] == page["start"] + chunk["start"] and
                          chunk["source_end"] == page["start"] + chunk["end"], "document_offset", location)

        batches, snapshots = [], [pack_context([], budget_chars=budget, max_chunks=max_chunks)]
        for i, event in enumerate(searches):
            check(event.get("top_k") == top_k, "event_top_k", str(i))
            check(len(event["results"]) <= top_k, "actual_result_limit", str(i))
            check(event.get("actual_results") == len(event["results"]), "actual_result_count", str(i))
            check(len({c["id"] for c in event["results"]}) == len(event["results"]), "duplicate_result_ids", str(i))
            check(event.get("filter") == trace.get("filter"), "filter_overridden", str(i))
            for chunk in event["results"]:
                for key, value in (trace.get("filter") or {}).items():
                    check(chunk.get("metadata", {}).get(key) == value, "filter_result_violation", f"{i}:{key}")
            batches.append(event["results"])
            snapshot = pack_context(rank_candidates(batches), budget_chars=budget, max_chunks=max_chunks)
            snapshots.append(snapshot)
            check(event.get("context") == snapshot["text"], "event_context_text", str(i))
            check(event.get("context_ids") == snapshot["ids"], "event_context_ids", str(i))

        previous_search_count = 0
        previous_action = None
        observed_successful_searches = 0
        native_costs, unknown_usage_attempts = [], 0
        allowed_state_keys = {"question", "scope_filters", "remaining_search_calls", "previous_queries", "DOCUMENT_CONTEXT", "context_ids", "runtime_feedback"}
        for i, call in enumerate(calls):
            messages = call.get("request_messages", [])
            check(len(messages) == 2 and [m.get("role") for m in messages] == ["system", "user"], "request_roles", str(i))
            if len(messages) != 2:
                continue
            check(call.get("system_prompt_sha256") == digest(messages[0]["content"]), "system_prompt_hash", str(i))
            check(call.get("input_chars") == sum(len(m["content"]) for m in messages), "input_chars", str(i))
            state = json.loads(messages[1]["content"])
            check(set(state) == allowed_state_keys, "request_state_keys", str(i))
            check(not forbidden_keys(state), "benchmark_leakage_key", str(i))
            check(state.get("question") == trace["question"], "request_question", str(i))
            check(state.get("scope_filters") == trace.get("filter"), "request_filter", str(i))
            queries = state.get("previous_queries", [])
            n = len(queries)
            check(0 <= n <= len(searches), "request_search_count", str(i))
            if not 0 <= n <= len(searches):
                continue
            check(queries == [e["query"] for e in searches[:n]], "request_query_history", str(i))
            check(state.get("remaining_search_calls") == max_searches - n, "remaining_search_budget", str(i))
            check(n in (previous_search_count, previous_search_count + 1), "search_progression", str(i))
            if i == 0:
                check(n == 0, "initial_search_history")
            if n == previous_search_count + 1:
                check(previous_action is not None and previous_action.get("action") == "search" and
                      previous_action.get("query", "").strip() == searches[n - 1]["query"], "model_search_event_link", str(i))
                observed_successful_searches += 1
            previous_search_count = n
            expected = snapshots[n]
            check(state.get("DOCUMENT_CONTEXT") == expected["text"], "request_context_text", str(i))
            check(state.get("context_ids") == expected["ids"], "request_context_ids", str(i))
            check(call.get("context_ids_sent") == expected["ids"], "call_context_ids", str(i))
            check(call.get("context_chars_sent") == expected["chars"], "call_context_chars", str(i))
            check(call.get("context_text_sha256") == digest(expected["text"]), "call_context_hash", str(i))
            check(len(state.get("DOCUMENT_CONTEXT", "")) <= budget, "context_budget", str(i))
            if config.get("action_protocol", "json") == "native_tools":
                tools = call.get("request_tools", [])
                names = [t.get("function", {}).get("name") for t in tools]
                expected_names = (["search"] if n < max_searches else []) + (["answer", "abstain"] if n else [])
                check(names == expected_names, "native_schema_state", str(i))
                for tool in tools:
                    check(tool.get("type") == "function", "native_tool_type", str(i))
                    schema = tool["function"].get("parameters", {})
                    check(schema.get("type") == "object" and set(schema.get("required", [])) == set(schema.get("properties", {}))
                          and schema.get("additionalProperties") is False, "native_schema_required", str(i))
                if call.get("status") == "success" and not call.get("tool_calls"):
                    check(any(e.get("turn") == i + 1 and e.get("type") == "invalid_model_action" for e in trace.get("errors", [])),
                          "missing_native_call_unreported", str(i))
            previous_action = None
            if call.get("status") == "success":
                try:
                    previous_action = parse_action(call)
                except (ValueError, KeyError, TypeError):
                    check(any(e.get("turn") == i + 1 and e.get("type") == "invalid_model_action" for e in trace.get("errors", [])),
                          "invalid_action_unreported", str(i))
            usage = call.get("usage")
            if usage is not None:
                raw = usage.get("raw", {})
                for normalized, rawkey in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens")):
                    if rawkey in raw:
                        check(usage.get(normalized) == raw[rawkey], "provider_usage_changed", f"{i}:{rawkey}")
                x_ckey = raw.get("x_ckey", {})
                if "cost" in x_ckey:
                    native_costs.append(x_ckey["cost"])
                    check("cost_usd" not in usage, "native_cost_mislabeled_usd", str(i))
            unknown_usage_attempts += sum(a.get("usage") is None for a in call.get("attempts", []))

        final = snapshots[-1]
        check(trace.get("final_context_text") == final["text"], "final_context_text")
        check(trace.get("context_ids") == final["ids"], "final_context_ids")
        check(trace.get("context_chars") == final["chars"], "final_context_chars")
        check(trace.get("final_context") == final["chunks"], "final_context_chunks")
        if trace["status"] in ("answered", "abstain"):
            check(bool(searches), "successful_without_retrieval")
            check(observed_successful_searches == len(searches), "searches_not_sent_to_model")
            check(bool(calls) and calls[-1].get("status") == "success", "final_model_not_successful")
            if calls and calls[-1].get("request_messages"):
                last = json.loads(calls[-1]["request_messages"][1]["content"])
                check(last.get("DOCUMENT_CONTEXT") == trace.get("final_context_text"), "final_not_actually_sent")
            check(previous_action is not None and previous_action.get("action") == ("answer" if trace["status"] == "answered" else "abstain"),
                  "final_status_action")
        if trace["status"] == "answered":
            check(bool(trace.get("citations")), "missing_answer_citations")
            for cid in trace.get("citations", []):
                check(cid in final["ids"] and f"[{cid}]" in trace.get("answer", ""), "invalid_final_citation", cid)
            if previous_action:
                check(trace["answer"] == previous_action.get("answer"), "answer_differs_from_model")
        elif trace["status"] == "abstain":
            check(not trace.get("citations"), "abstain_has_citations")
        else:
            check(bool(trace.get("errors")), "error_without_error_record")
        inline = list(dict.fromkeys(re.findall(r"\[([a-fA-F0-9]{32})\]", trace.get("answer", ""))))
        undeclared = [cid for cid in inline if cid not in trace.get("citations", [])]
        warnings = ([{"code": "undeclared_inline_citations", "ids": undeclared,
                      "detail": "Raw trace preserved; semantic/citation audit must account for inline references, including abstention reasons."}]
                    if undeclared else [])
        return {"query_id": trace.get("query_id"), "config_id": trace.get("config_id"), "passed": not errors,
                "checks": checks, "errors": errors, "native_cost_amounts": native_costs,
                "warnings": warnings, "inline_citation_ids": inline, "undeclared_inline_citation_count": len(undeclared),
                "native_cost_units": "provider_native_unspecified; not inferred as USD",
                "unknown_usage_attempts": unknown_usage_attempts,
                "semantic_and_human_audit_verified": False}
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        errors.append({"code": "malformed_trace", "detail": f"{type(exc).__name__}: {exc}"})
        return {"query_id": trace.get("query_id"), "passed": False, "checks": checks, "errors": errors,
                "semantic_and_human_audit_verified": False}


def verify_traces(traces, chunks, pages=None):
    rows = [verify_trace(t, chunks, pages) for t in traces]
    return {"passed": all(r["passed"] for r in rows) and bool(rows), "traces": len(rows),
            "checks": sum(r["checks"] for r in rows), "errors": [dict(query_id=r.get("query_id"), **e) for r in rows for e in r["errors"]],
            "warnings": [dict(query_id=r.get("query_id"), **w) for r in rows for w in r.get("warnings", [])],
            "results": rows, "semantic_and_human_audit_verified": False,
            "scope": "Offline source/context/native-action trace consistency only; not a complete lab gate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, nargs="+", required=True, help="Trace JSON object/array or a directory containing cases/*.json")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/chunks.jsonl")
    parser.add_argument("--pages", type=Path, default=ROOT / "data/pages.jsonl")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    traces = []
    for path in args.traces:
        files = sorted(path.glob("cases/*.json")) if path.is_dir() else [path]
        for file in files:
            value = read_json(file)
            traces.extend(value if isinstance(value, list) else [value])
    report = verify_traces(traces, read_jsonl(args.chunks), read_jsonl(args.pages))
    report["verified_at"] = now()
    if args.output:
        write_json(args.output, report)
    print(json.dumps({k: report[k] for k in ("passed", "traces", "checks", "errors")}, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
