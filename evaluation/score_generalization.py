"""Score a completed generalization CSV or JSONL without calling any model."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

try:
    from .scoring import score_response
except ImportError:
    from scoring import score_response


def read_rows(path):
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            rows.append({
                "item_id": record.get("item_id") or record.get("id"),
                "status": "error" if "error" in record else "ok",
                "response": record.get("verbatim_reply") or record.get("result", {}).get("answer", ""),
            })
        return rows
    with path.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    return [{
        "item_id": row.get("item_id") or row.get("id"),
        "status": row.get("status", "ok"),
        "response": row.get("verbatim_reply") or row.get("answer") or "",
    } for row in source]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="Destination CSV; a summary JSON is written beside it")
    args = parser.parse_args()
    rows = read_rows(args.input)
    if not rows:
        raise SystemExit("Input contains no observations")
    scored = []
    for row in rows:
        result = score_response(row["item_id"], row["response"], row["status"])
        scored.append({**row, **result})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(scored[0]))
        writer.writeheader(); writer.writerows(scored)

    groups = defaultdict(list)
    for row in scored:
        groups[row["family"]].append(row)
    summary = {
        "input": str(args.input.resolve()),
        "rows": len(scored),
        "note": "Deterministic conformance checks; not human quality ratings.",
        "families": {
            family: {
                "attempts": len(group),
                "request_successes": sum(row["request_success"] for row in group),
                "value_correct": sum(row["value_correct"] for row in group),
                "role_correct": sum(row["second_person_role_correct"] for row in group),
                "no_stale_value": sum(row["no_stale_value"] for row in group),
                "overall_passes": sum(row["overall_pass"] for row in group),
            }
            for family, group in groups.items()
        },
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
