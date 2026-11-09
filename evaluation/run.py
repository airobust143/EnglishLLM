"""Run from repo root: python evaluation/run.py --model qwen3:1.7b.

Writes actual output and leaves human ratings empty. No LLM-as-judge scores.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

try:
    from .cases import cases
    from .generalization import generalization_cases, holdout_cases, paper12_cases
except ImportError:  # Supports `python evaluation/run.py` from the repo root.
    from cases import cases
    from generalization import generalization_cases, holdout_cases, paper12_cases


def request(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=300) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3:1.7b")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--suite", choices=("core36", "paper12", "generalization", "holdout"), default="core36",
                        help="Select the frozen functional suite or prospective generalization probes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    scenarios = {
        "core36": cases,
        "paper12": paper12_cases,
        "generalization": generalization_cases,
        "holdout": holdout_cases,
    }[args.suite]()
    if args.dry_run:
        print(json.dumps(scenarios, indent=2))
        return
    health = request(args.url + "/health")
    if not health["ollama"]:
        raise SystemExit("Ollama is unavailable; no benchmark results generated.")
    output = args.output or Path("evaluation/runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    files = [Path("main.py"), *sorted(Path("evaluation").glob("*.py")),
             *sorted(Path("backend").rglob("*.py")),
             *sorted(Path("backend/prompts").rglob("*.txt")),
             *sorted(Path("docs").glob("*"))]
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    versions = {}
    for name in ["fastapi", "faster-whisper", "ctranslate2", "httpx", "pydantic"]:
        try: versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name] = None
    config = {"timestamp": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "processor": platform.processor(), "python": platform.python_version(),
              "revision": revision, "health": health, "requested_model": args.model,
              "packages": versions, "ollama_version": request(health["ollama_url"] + "/api/version"),
              "ollama_models": request(health["ollama_url"] + "/api/tags"),
              "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()},
              "suite": args.suite,
              "protocol": (f"3 warmups; {len(scenarios)} typed probes; first "
                           f"{min(30, len(scenarios))} probes timed; setup turns excluded")}
    (output / "configuration.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    def chat(message, unit, history):
        return request(args.url + "/chat", {"message": message, "unit": unit, "history": history,
                       "provider": "ollama", "model": args.model, "temperature": 0.2, "max_tokens": 96})

    for prompt in ["I help with housework.", "I recycle plastic bottles.", "I like pop music."]:
        chat(prompt, None, [])
    records = []
    with (output / "transcripts.jsonl").open("w", encoding="utf-8") as transcript:
        for index, scenario in enumerate(scenarios):
            history = []
            try:
                for setup in scenario["setup"]:
                    reply = chat(setup, scenario["unit"], history)
                    history.extend([{"role": "user", "content": setup}, {"role": "assistant", "content": reply["answer"]}])
                started = time.perf_counter()
                result = chat(scenario["message"], scenario["unit"], history)
                record = {**scenario, "history": history, "result": result,
                          "http_duration_ms": (time.perf_counter() - started) * 1000,
                          "timing_eligible": index < min(30, len(scenarios))}
            except Exception as exc:
                record = {**scenario, "history": history, "error": str(exc), "timing_eligible": False}
            records.append(record)
            transcript.write(json.dumps(record, ensure_ascii=False) + "\n")
            transcript.flush()
            print(scenario["id"], "ERROR" if "error" in record else "saved", flush=True)
    with (output / "ratings.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "category", "correction_eligible", "relevant", "grammatical", "level_appropriate", "correction_accurate", "coder", "notes"])
        writer.writeheader()
        writer.writerows({k: record[k] for k in ["id", "category", "correction_eligible"]} for record in records)
    summary = {}
    eligible = [r for r in records if r["timing_eligible"] and "result" in r]
    for stage in ["retrieval", "generation"]:
        values = [r["result"]["timings_ms"][stage] / 1000 for r in eligible]
        summary[stage] = {"n": len(values), "mean_s": statistics.mean(values) if values else None,
                          "min_s": min(values) if values else None, "max_s": max(values) if values else None}
    summary["failed_items"] = sum("error" in r for r in records)
    summary["note"] = "No microphone, physical speech-onset, end-to-end audio, quality scores, or robot measurements are inferred."
    (output / "latency.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
