"""Whole-chunk source-preserving context, bounded by rendered characters."""
from __future__ import annotations

import hashlib


def render_chunk(chunk):
    return f"[{chunk['id']}] source={chunk['source']} | page={chunk['page']}\n{chunk['text']}"


def rank_candidates(search_batches):
    """Latest search ranks first; prior unique candidates remain as a fallback.

    Query-local dense/BM25 scores are deliberately never compared across calls.
    The newest rank for a repeated ID refreshes it instead of preserving stale
    first-call order. Selection is deterministic, independent of benchmark gold.
    """
    seen_ids, seen_texts, ranked = set(), set(), []
    for batch in reversed(search_batches):
        for rank, chunk in enumerate(batch, 1):
            ident = chunk["id"]
            fingerprint = hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest()
            if ident in seen_ids or fingerprint in seen_texts:
                continue
            seen_ids.add(ident)
            seen_texts.add(fingerprint)
            ranked.append(dict(chunk, context_rank=len(ranked) + 1, retrieval_rank=rank))
    return ranked


def pack_context(candidates, *, budget_chars=4000, max_chunks=3):
    if budget_chars < 1 or max_chunks < 1:
        raise ValueError("context budget and max_chunks must be positive")
    selected, blocks, skipped = [], [], []
    for chunk in candidates:
        block = render_chunk(chunk)
        if len(selected) >= max_chunks:
            skipped.append({"id": chunk["id"], "reason": "max_chunks"})
            continue
        if len("\n\n".join(blocks + [block])) > budget_chars:
            skipped.append({"id": chunk["id"], "reason": "budget_full_chunk"})
            continue
        selected.append(chunk)
        blocks.append(block)
    return {"text": "\n\n".join(blocks), "chunks": selected, "ids": [c["id"] for c in selected],
            "chars": len("\n\n".join(blocks)), "budget_chars": budget_chars, "skipped": skipped,
            "policy": "latest_search_rank_then_prior_unique;whole_chunks;exact_text_dedup"}
