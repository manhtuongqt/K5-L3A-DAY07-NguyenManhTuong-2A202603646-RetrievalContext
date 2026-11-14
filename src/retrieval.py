"""Pinned Day06 adapter and real dense/BM25/RRF retrieval. No gold or model API."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re
import shutil
import time
import unicodedata
import uuid

ROOT = Path(__file__).resolve().parents[1]
DAY06_REPO = "manhtuongqt/K5-L3A-DAY06-NguyenManhTuong-2A202603646-DataIngestion"
DAY06_COMMIT = "64c4ab778f81ba5608d4b2b57315f6369aedd0fd"
SOURCE_HASHES = {
    "results/chunks_B.jsonl": "bcc757f290099109a9361d8f5e7f2812c3ea57901b5048854c93269ccbd808e1",
    "data/pages.jsonl": "16c33ff8363b1d5b1833a77ec3cf2891a7ead1eea202a51bba092d981cdbf92f",
    "data/manifest.json": "2db095b271b1eef6ef2bb127366be0a8ab1740af636842a511a7f768cbcc6d4a",
    "benchmark/model.json": "13ffcb7f358c70015512dfb70e115f8ab86a9b728dd6453e156623ec6c640190",
    "results/index.json": "3ee3df76100eeabcd9c6da5d15390ff8b5d715bab04d8d6d7b9df22a6d19343f",
    "THIRD_PARTY_NOTICES.md": "01841c03db7cd26b26fbf5516f3c922c9781ae3fde36dbea2d377db793ba86ca",
    "data/raw/python_license.html": "ced1a5587f118ad9454a151b721292abe08379b6ce390c5f8b7c165720412ca0",
}
ALLOWED_FILTERS = {"document_type", "language", "version"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_filters(filters: dict | None) -> dict:
    if filters is None:
        return {}
    if not isinstance(filters, dict) or set(filters) - ALLOWED_FILTERS:
        raise ValueError("Filters only support user-supplied document_type, language, version")
    if any(not isinstance(v, str) or not v.strip() for v in filters.values()):
        raise ValueError("Filter values must be non-empty strings")
    return dict(filters)


def tokenize(text: str) -> list[str]:
    """Unicode words, lowercase, underscores kept; no stemming or gold expansion."""
    return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())


class BM25:
    """Okapi BM25, positive Robertson IDF; corpus-level statistics before filter."""
    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.counts = [Counter(tokenize(c["text"])) for c in chunks]
        self.lengths = [sum(row.values()) for row in self.counts]
        self.average_length = sum(self.lengths) / len(chunks) if chunks else 0
        df = Counter(term for row in self.counts for term in row)
        self.idf = {term: math.log(1 + (len(chunks) - n + .5) / (n + .5)) for term, n in df.items()}

    def search(self, query: str, filters: dict | None = None, top_k: int = 3) -> list[dict]:
        filters = validate_filters(filters)
        terms = set(tokenize(query))  # repeated query words do not artificially boost a term
        scored = []
        for chunk, counts, length in zip(self.chunks, self.counts, self.lengths):
            if any(chunk["metadata"].get(k) != v for k, v in filters.items()):
                continue
            normalizer = self.k1 * (1 - self.b + self.b * length / (self.average_length or 1))
            score = sum(self.idf.get(t, 0) * counts[t] * (self.k1 + 1) / (counts[t] + normalizer)
                        for t in terms if counts[t])
            if score > 0:
                scored.append({**chunk, "score": score})
        scored.sort(key=lambda c: (-c["score"], c["id"]))
        return [{**c, "rank": i + 1, "method": "bm25"} for i, c in enumerate(scored[:top_k])]


def reciprocal_rank_fusion(dense: list[dict], lexical: list[dict], top_k: int = 3, k: int = 60) -> list[dict]:
    """Ranks are one-based; missing branches contribute zero, never raw score sums."""
    merged = {}
    for branch, results in (("dense", dense), ("bm25", lexical)):
        seen = set()
        for rank, result in enumerate(results, 1):
            if result["id"] in seen:
                continue
            seen.add(result["id"])
            item = merged.setdefault(result["id"], {**result, "score": 0.0, "branch_ranks": {}, "branch_scores": {}})
            item["score"] += 1 / (k + rank)
            item["branch_ranks"][branch] = rank
            item["branch_scores"][branch] = result["score"]
    ordered = sorted(merged.values(), key=lambda c: (-c["score"], c["id"]))[:top_k]
    return [{**c, "rank": rank, "method": "hybrid", "rrf_k": k} for rank, c in enumerate(ordered, 1)]


def prepare_model(root: Path, lock: dict, day6_root: Path | None = None) -> Path:
    import requests
    directory = root / ".local/model"
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in lock["files_sha256"].items():
        path = directory / name
        original = day6_root / ".local/model" / name if day6_root else None
        if not path.exists():
            if original and original.exists():
                shutil.copyfile(original, path)
            else:
                url = f"https://huggingface.co/{lock['onnx_repository']}/resolve/{lock['revision']}/{name}"
                response = requests.get(url, stream=True, timeout=(30, 180))
                response.raise_for_status()
                temporary = path.with_suffix(path.suffix + ".part")
                with temporary.open("wb") as output:
                    for block in response.iter_content(1024 * 1024):
                        output.write(block)
                temporary.replace(path)
        if sha(path) != expected:
            raise ValueError(f"Pinned model hash mismatch: {name}; refusing incompatible query/index")
    return directory


class Embedder:
    def __init__(self, root: Path = ROOT):
        import numpy as np
        from fastembed import TextEmbedding
        self.np = np
        self.lock = read(root / "configs/embedding_model.json")
        if self.lock["dimensions"] != 384 or self.lock["document_prefix"] != "":
            raise ValueError("Unsupported Day06 embedding lock")
        model_dir = prepare_model(root, self.lock)
        self.model = TextEmbedding(self.lock["model"], specific_model_path=str(model_dir),
                                   threads=self.lock["threads"], providers=["CPUExecutionProvider"])

    def validate(self, vectors):
        if vectors.ndim != 2 or vectors.shape[1] != self.lock["dimensions"] or not self.np.isfinite(vectors).all():
            raise ValueError("Embedding shape or finite-value validation failed")
        if not self.np.allclose(self.np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
            raise ValueError("Expected L2 normalized Day06 embeddings")

    def documents(self, texts):
        vectors = self.np.asarray(list(self.model.passage_embed(texts, batch_size=32)), dtype=self.np.float32)
        self.validate(vectors)
        return vectors

    def query(self, text):
        # Identical to Day06: FastEmbed BGE does not inject an instruction itself.
        if text.startswith(self.lock["query_prefix"]):
            raise ValueError("Pass raw query; the locked BGE prefix is added exactly once")
        vectors = self.np.asarray(list(self.model.query_embed([self.lock["query_prefix"] + text], batch_size=16)), dtype=self.np.float32)
        self.validate(vectors)
        return vectors[0]


def _validate_source_chunks(chunks: list[dict], pages: list[dict]):
    page_map = {page["page"]: page for page in pages}
    if len(chunks) != 312 or len({c["chunk_id"] for c in chunks}) != 312:
        raise ValueError("Expected frozen Day06 B: 312 unique chunks")
    for c in chunks:
        page = page_map[c["page"]]
        if c["text"] != page["text"][c["start"]:c["end"]]:
            raise ValueError(f"Page-relative offsets do not reproduce {c['chunk_id']}")
        if c["source_start"] != page["start"] + c["start"] or c["source_end"] != page["start"] + c["end"]:
            raise ValueError("Normalized-document offsets changed")


def prepare_day6(day6_root: Path | None, root: Path = ROOT) -> dict:
    """Import immutable Day06 bytes locally or download from its pinned Git commit.

    No Day06 benchmark/results scores are imported, except index provenance.
    Model/vector/store paths are independent: Day06 is never mutated or opened.
    """
    from qdrant_client import QdrantClient
    root = Path(root).resolve()
    (root / ".local").mkdir(parents=True, exist_ok=True)
    # Acquire the actual Qdrant owner before replacing any prepared artifact.
    # A concurrent run fails immediately without leaving chunks/manifest divergent.
    owner = QdrantClient(path=str(root / ".local/qdrant_day07"))
    try:
        return _prepare_day6(day6_root, root, owner)
    finally:
        owner.close()


def _prepare_day6(day6_root: Path | None, root: Path, owner) -> dict:
    import numpy as np
    import requests
    root = Path(root).resolve()
    day6_root = Path(day6_root).resolve() if day6_root else None
    snapshot = root / ".local/day06_snapshot"
    started = time.perf_counter()
    for relative, expected in SOURCE_HASHES.items():
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if day6_root:
            payload = (day6_root / relative).read_bytes()
        elif destination.exists() and sha(destination) == expected:
            payload = destination.read_bytes()
        else:
            response = requests.get(f"https://raw.githubusercontent.com/{DAY06_REPO}/{DAY06_COMMIT}/{relative}", timeout=(30, 120))
            response.raise_for_status()
            payload = response.content
        # This small metadata JSON is tracked as text in Day06 (autocrlf on
        # Windows); unlike frozen corpus/model bytes its pinned Git blob is LF.
        if relative == "results/index.json":
            payload = payload.replace(b"\r\n", b"\n")
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"Day06 snapshot changed: {relative}; use pinned commit {DAY06_COMMIT}")
        destination.write_bytes(payload)
    original = read_lines(snapshot / "results/chunks_B.jsonl")
    pages = read_lines(snapshot / "data/pages.jsonl")
    _validate_source_chunks(original, pages)
    chunks = [{"id": c["chunk_id"], "source_id": c["document_id"], **c} for c in original]
    target_chunks = root / "data/chunks.jsonl"
    target_chunks.parent.mkdir(parents=True, exist_ok=True)
    target_chunks.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8", newline="\n")
    for relative, target in (("data/pages.jsonl", "data/pages.jsonl"), ("data/manifest.json", "data/source_manifest.json"),
                             ("benchmark/model.json", "configs/embedding_model.json"),
                             ("data/raw/python_license.html", "data/python_license.html"),
                             ("THIRD_PARTY_NOTICES.md", "data/DAY06_THIRD_PARTY_NOTICES.md")):
        output = root / target
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(snapshot / relative, output)
    lock = read(root / "configs/embedding_model.json")
    prepare_model(root, lock, day6_root)
    vector_path = root / ".local/vectors_B.npy"
    expected_vector_sha = read(snapshot / "results/index.json")["strategies"]["B"]["vectors_sha256"]
    candidate = day6_root / ".local/vectors_B.npy" if day6_root else None
    reused = False
    if candidate and candidate.exists():
        if sha(candidate) != expected_vector_sha:
            raise ValueError("Day06 cached vectors differ from its recorded B index")
        shutil.copyfile(candidate, vector_path)
        reused = True
    elif vector_path.exists() and sha(vector_path) == expected_vector_sha:
        reused = True
    else:
        embedder = Embedder(root)
        np.save(vector_path, embedder.documents([c["text"] for c in chunks]))
    vectors = np.load(vector_path, allow_pickle=False)
    if vectors.shape != (312, 384) or not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
        raise ValueError("Invalid real Day06 B vectors")
    # Verify the actual persisted payload and vector snapshot through Qdrant API.
    store_result = _create_store(root, chunks, vectors, owner)
    manifest = {
        "prepared_at": datetime.now(timezone.utc).isoformat(), "day06_repository": f"https://github.com/{DAY06_REPO}",
        "day06_commit": DAY06_COMMIT, "source_file_sha256": SOURCE_HASHES,
        "chunks": len(chunks), "content_units": len(pages), "chunk_strategy": "B paragraph max1000; no rechunking",
        "chunks_sha256": sha(target_chunks), "pages_sha256": sha(root / "data/pages.jsonl"),
        "model_lock_sha256": sha(root / "configs/embedding_model.json"),
        "vectors": {"shape": list(vectors.shape), "sha256": sha(vector_path), "day06_sha256": expected_vector_sha,
                    "reused_day06_cache": reused, "byte_identical_day06": sha(vector_path) == expected_vector_sha,
                    "regeneration_limit": "Same pinned quantized model/pooling/prefix; floating point kernels may differ across platforms. New hash is always recorded."},
        "store": store_result, "embedding_api_calls": 0, "embedding_api_cost_usd": 0,
        "elapsed_seconds": time.perf_counter() - started,
        "source_unit_note": "69 contiguous normalized HTML units, not physical PDF pages; original Day06 offsets unchanged.",
        "retrieval": {"dense": "Qdrant exact cosine", "bm25": {"k1": 1.5, "b": .75, "tokenizer": "Unicode NFC casefold words; keep underscores; no stemming"},
                      "hybrid": {"fusion": "RRF", "candidate_per_branch": 10, "k": 60, "tie_break": "chunk ID ascending"}},
    }
    write(root / "data/day6_manifest.json", manifest)
    return manifest


def _create_store(root, chunks, vectors, client=None):
    from qdrant_client import QdrantClient, models
    owns_client = client is None
    if owns_client:
        client = QdrantClient(path=str(root / ".local/qdrant_day07"))
    name = "day07_B"
    try:
        if not client.collection_exists(name):
            client.create_collection(name, vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE))
        params = client.get_collection(name).config.params.vectors
        if params.size != 384 or params.distance != models.Distance.COSINE:
            raise ValueError("Existing collection is incompatible with Day06 B")
        current_ids = {str(uuid.UUID(c["id"])) for c in chunks}
        previous, offset = set(), None
        while True:
            old, offset = client.scroll(name, limit=256, offset=offset, with_payload=False)
            previous.update(str(point.id) for point in old)
            if offset is None:
                break
        for start in range(0, len(chunks), 128):
            client.upsert(name, [models.PointStruct(id=str(uuid.UUID(c["id"])), vector=v.tolist(),
                          payload={**c, **c["metadata"]}) for c, v in zip(chunks[start:start + 128], vectors[start:start + 128])], wait=True)
        obsolete = sorted(previous - current_ids)
        if obsolete:
            client.delete(name, points_selector=models.PointIdsList(points=obsolete), wait=True)
        count = client.count(name, exact=True).count
        if count != len(chunks):
            raise ValueError("Persisted Qdrant count mismatch")
        first = client.retrieve(name, [str(uuid.UUID(chunks[0]["id"]))], with_vectors=True)[0]
        import numpy as np
        if first.payload["text"] != chunks[0]["text"] or not np.allclose(first.vector, vectors[0], atol=1e-6):
            raise ValueError("Qdrant persisted data differs from imported data")
        return {"engine": "QdrantClient local persistent", "path": ".local/qdrant_day07", "collection": name,
                "count": count, "distance": "Cosine", "exact_search": True, "obsolete_removed": len(obsolete),
                "sample_payload_and_vector_verified": True}
    finally:
        if owns_client:
            client.close()


class RetrievalService:
    def __init__(self, root: Path = ROOT):
        from qdrant_client import QdrantClient
        self.root = Path(root).resolve()
        self.manifest = read(self.root / "data/day6_manifest.json")
        if sha(self.root / "data/chunks.jsonl") != self.manifest["chunks_sha256"]:
            raise ValueError("Chunks changed after index preparation; rebuild data")
        if sha(self.root / "configs/embedding_model.json") != self.manifest["model_lock_sha256"]:
            raise ValueError("Query embedding model lock changed; rebuild index")
        self.chunks = read_lines(self.root / "data/chunks.jsonl")
        self.bm25 = BM25(self.chunks)
        self.embedder = Embedder(self.root)
        self.client = QdrantClient(path=str(self.root / ".local/qdrant_day07"))
        self.closed = False
        try:
            collection = self.client.get_collection("day07_B")
            vectors = collection.config.params.vectors
            if collection.points_count != len(self.chunks) or vectors.size != 384 or str(vectors.distance).lower() != "cosine":
                raise ValueError("Stored collection count/model dimension/distance mismatch")
        except Exception:
            self.close()
            raise

    def close(self):
        if not self.closed:
            self.client.close()
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _dense(self, query, filters, top_k):
        from qdrant_client import models
        vector = self.embedder.query(query)
        qfilter = models.Filter(must=[models.FieldCondition(key=k, match=models.MatchValue(value=v)) for k, v in filters.items()]) if filters else None
        points = self.client.query_points("day07_B", query=vector.tolist(), query_filter=qfilter,
                                        limit=top_k, search_params=models.SearchParams(exact=True), with_payload=True).points
        # Qdrant resolves cosine ties internally; preserve returned vector ranking.
        return [{**p.payload, "rank": i + 1, "score": p.score, "method": "dense"} for i, p in enumerate(points)]

    def search(self, query: str, *, filters: dict | None = None, top_k: int = 3, method: str = "dense") -> list[dict]:
        if self.closed:
            raise RuntimeError("RetrievalService is closed")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 10:
            raise ValueError("top_k must be an integer between 1 and 10")
        if method not in {"dense", "bm25", "hybrid"}:
            raise ValueError("method must be dense, bm25, or hybrid")
        filters = validate_filters(filters)
        if method == "dense":
            return self._dense(query, filters, top_k)
        if method == "bm25":
            return self.bm25.search(query, filters, top_k)
        return reciprocal_rank_fusion(self._dense(query, filters, 10), self.bm25.search(query, filters, 10), top_k, 60)
