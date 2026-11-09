"""Summarize completed human ratings and observed browser timings."""
import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def summarize_ratings(rows):
    result = {}
    for category in ["overall", *dict.fromkeys(row["category"] for row in rows)]:
        selected = rows if category == "overall" else [r for r in rows if r["category"] == category]
        result[category] = {}
        for criterion in ["relevant", "grammatical", "level_appropriate", "correction_accurate"]:
            eligible = [r for r in selected if criterion != "correction_accurate" or r["correction_eligible"].lower() == "true"]
            scores = [r[criterion].strip().lower() for r in eligible]
            if any(s not in {"", "yes", "no"} for s in scores):
                raise ValueError("Ratings must be yes, no, or blank (unrated).")
            rated = [s for s in scores if s]
            passed = rated.count("yes")
            result[category][criterion] = {"passes": passed, "rated_n": len(rated), "eligible_n": len(eligible),
                "percent_of_rated": 100 * passed / len(rated) if rated else None}
    return result


def summarize_sessions(sessions):
    result = {}
    for stage in ["transcription_ms", "retrieval_ms", "generation_ms", "speech_onset_ms", "end_to_end_ms"]:
        values = sorted(turn["timing"][stage] / 1000 for session in sessions for turn in session["turns"]
                        if turn["timing"].get(stage) is not None)
        result[stage] = {"n": len(values), "mean_s": statistics.mean(values) if values else None,
                         "min_s": min(values) if values else None, "max_s": max(values) if values else None,
                         "p95_s": values[math.ceil(len(values) * .95) - 1] if values else None}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", type=Path)
    parser.add_argument("--session", type=Path, action="append", default=[])
    args = parser.parse_args()
    report = {}
    if args.ratings:
        with args.ratings.open(encoding="utf-8", newline="") as handle:
            report["quality"] = summarize_ratings(list(csv.DictReader(handle)))
    if args.session:
        report["browser_timing_estimates"] = summarize_sessions([json.loads(p.read_text(encoding="utf-8")) for p in args.session])
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
