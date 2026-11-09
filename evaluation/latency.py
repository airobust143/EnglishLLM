"""Measure the current local pipeline without storing learner data.

Run from the repo root: python -m evaluation.latency [--audio sample.wav]
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend import config
from backend.services.transcription import whisper_ready


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, help="Optional short recorded speech sample")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")

    report = {"model": config.OLLAMA_MODEL, "chat": [], "transcription": []}
    with TestClient(app) as client:
        if config.WHISPER_PRELOAD:
            started = time.perf_counter()
            while not whisper_ready() and time.perf_counter() - started < 30:
                time.sleep(0.05)
            report["whisper_preload_ms"] = (time.perf_counter() - started) * 1000
            report["whisper_ready"] = whisper_ready()
        for message, unit in (("What is recycling?", 2),
                              ("What is the difference between will and be going to?", 2)):
            samples = []
            for _ in range(args.repeats):
                started = time.perf_counter()
                response = client.post("/chat", json={"message": message, "unit": unit})
                response.raise_for_status()
                body = response.json()
                samples.append({"wall_ms": (time.perf_counter() - started) * 1000,
                                "retrieval_ms": body["timings_ms"]["retrieval"],
                                "generation_ms": body["timings_ms"]["generation"],
                                "answer_chars": len(body["answer"])})
            report["chat"].append({"query": message, "samples": samples,
                                   "median_wall_ms": statistics.median(s["wall_ms"] for s in samples)})

        if args.audio:
            if not args.audio.is_file():
                parser.error("audio file does not exist")
            data = args.audio.read_bytes()
            for _ in range(args.repeats):
                started = time.perf_counter()
                response = client.post("/transcribe", files={"audio": (args.audio.name, data)})
                response.raise_for_status()
                body = response.json()
                report["transcription"].append({
                    "wall_ms": (time.perf_counter() - started) * 1000,
                    **body["timings_ms"], "text_chars": len(body["text"]),
                })
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
