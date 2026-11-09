"""Offline retrieval probes: no model calls, downloads, or learner data."""
import json
import statistics
import time

from backend.schemas import ChatRequest
from backend.services import chat, corpus, retrieval

PROBES = [
    ("Unit 1 grammar exercise 1 page 10", 1, "U1-GRAMMAR-01"),
    ("Unit 2 Speaking bài 1", 2, "U2-SPEAKING-01"),
    ("Unit 2 Getting Started exercise 3", 2, "U2-GS-02"),
    ("U3-READING-01", 3, "U3-READING-01"),
    ("present simple present continuous", 1, "U1-GRAMMAR-RULES"),
    ("câu bị động", 2, "U2-GRAMMAR-PASSIVE"),
    ("will and be going to", 2, "U2-GRAMMAR-FUTURE"),
    ("compound sentences conjunctions", 3, "U3-GRAMMAR-COMPOUND"),
    ("động từ nguyên mẫu", 3, "U3-GRAMMAR-INFINITIVE"),
    ("breadwinner homemaker groceries", 1, "U1-VOCAB-GLOSSARY"),
    ("trang 999", 2, None),
    ("Unit 2 exercise 1", 2, None),
    ("U2-GRAMMAR-01", 1, "U2-GRAMMAR-01"),
    ("What is Unit 1 about?", 1, "U1-OVERVIEW"),
    ("Can you ask me a question about Unit 3?", 3, "U3-READING-01"),
]


def main():
    start = time.perf_counter()
    info = corpus.corpus_info()
    cold_ms = (time.perf_counter() - start) * 1000
    rows, times = [], []
    for query, unit, expected in PROBES:
        result = retrieval.search(query, unit)
        for _ in range(10):
            start = time.perf_counter()
            retrieval.search(query, unit)
            times.append((time.perf_counter() - start) * 1000)
        ids = [s["id"] for s in result.sources]
        passed = expected in ids if expected else bool(result.clarification) and not ids
        rows.append({"query": query, "expected": expected, "retrieved": ids, "passed": passed})
    coverage = {}
    for stage in ("question", "feedback"):
        blocked = []
        for record in corpus.load_corpus():
            if record.chunk_kind != "exercise":
                continue
            prepared = chat.prepare_chat(ChatRequest(message="Help me with this exercise", unit=record.unit,
                exercise_id=record.id, attempt="1. My answer" if stage == "feedback" else None))
            if prepared.clarification:
                blocked.append(record.id)
        coverage[stage + "_budget_blocked"] = blocked
    print(json.dumps({"corpus": info, "probes_passed": sum(r["passed"] for r in rows),
        "probes_total": len(rows), "probes": rows, "cold_load_ms": round(cold_ms, 3),
        "warm_retrieval_median_ms": round(statistics.median(times), 3),
        "warm_retrieval_p95_ms": round(sorted(times)[int(len(times) * .95) - 1], 3),
        "default_prompt_coverage": coverage,
        "scope": "Offline curated probes, not held-out quality or end-to-end model latency."}, indent=2))


if __name__ == "__main__":
    main()
