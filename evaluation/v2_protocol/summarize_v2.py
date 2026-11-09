"""Create a compact cross-condition summary from frozen v2 benchmark records."""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CODE_ROOT = Path(r"C:\Users\admin\Documents\ChatGPT\EnglishLLM")
sys.path.insert(0, str(CODE_ROOT))
from backend.services import dialogue  # noqa: E402

RUNS = [
    ROOT / "run_qwen3_1_7b_cap56" / "records.jsonl",
    ROOT / "run_qwen3_1_7b_raw_turns_cap56" / "records.jsonl",
    ROOT / "run_qwen3_4b_instruct_2507_cap56" / "records.jsonl",
]
CASES = {case["id"]: case for case in json.loads((ROOT / "holdout_v2_28.json").read_text(encoding="utf-8"))["cases"]}


def wilson(x, n, z=1.959963984540054):
    if not n:
        return [None, None]
    p = x / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [centre - half, centre + half]


def quartiles(values):
    values = sorted(values)
    if not values:
        return [None, None, None]
    q = statistics.quantiles(values, n=4, method="inclusive")
    return [q[0], statistics.median(values), q[2]]


records = []
for path in RUNS:
    records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())

groups = defaultdict(list)
for row in records:
    groups[(row["model"], row["variant"])].append(row)

summary = {}
for (model, variant), rows in groups.items():
    key = f"{model}|{variant}"
    family = {}
    for name in sorted({row["family"] for row in rows}):
        subset = [row for row in rows if row["family"] == name]
        family[name] = {"pass": sum(row["pass"] for row in subset), "n": len(subset)}
    passed = sum(row["pass"] for row in rows)
    routes = sum(row["route_correct"] for row in rows)
    summary[key] = {
        "n": len(rows),
        "functional_pass": passed,
        "functional_wilson_95": wilson(passed, len(rows)),
        "route_correct": routes,
        "route_wilson_95": wilson(routes, len(rows)),
        "words_q1_median_q3": quartiles([row["word_count"] for row in rows]),
        "latency_ms_q1_median_q3": quartiles([row["elapsed_ms"] for row in rows if row["elapsed_ms"] is not None]),
        "truncated": sum(row["truncated"] for row in rows),
        "filter_activated": sum(row["filter_activated"] for row in rows),
        "reasoning_leakage": sum(row["reasoning_leakage"] for row in rows),
        "question_responses": sum("?" in row["response"] for row in rows),
        "followup_eligible": sum(dialogue.should_ask_follow_up(CASES[row["id"]]["message"]) for row in rows),
        "question_when_eligible": sum(
            "?" in row["response"] and dialogue.should_ask_follow_up(CASES[row["id"]]["message"])
            for row in rows
        ),
        "family": family,
    }

(ROOT / "cross_condition_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(json.dumps(summary, indent=2, ensure_ascii=False))
