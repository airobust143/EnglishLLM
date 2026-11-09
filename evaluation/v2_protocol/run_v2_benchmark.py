"""Run the frozen LocalTutor v2 holdout against local Ollama or Gemini.

The runner imports the evaluated application code without modifying it.  The
"v1" condition is an explicit reconstruction: ordered dialogue history and
retrieved lesson context are supplied, while the v2 fact block and correction
hint are absent.  It is not represented as the historical Stage-A binary.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import statistics
import sys
import time
from pathlib import Path

import httpx

CODE_ROOT = Path(r"C:\Users\admin\Documents\ChatGPT\EnglishLLM")
HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "holdout_v2_28.json"
sys.path.insert(0, str(CODE_ROOT))

from backend import config  # noqa: E402
from backend.schemas import ChatRequest, HistoryMessage  # noqa: E402
from backend.services import chat, dialogue, llm, retrieval  # noqa: E402


def history_objects(case):
    entries = []
    for user, assistant in case["history"]:
        entries.extend([HistoryMessage(role="user", content=user),
                        HistoryMessage(role="assistant", content=assistant)])
    return entries


def strip_block(text, start, end):
    return re.sub(re.escape(start) + r".*?" + re.escape(end) + r"\n?", "", text, flags=re.S)


def v1_messages(req):
    """Reconstruct the pre-v2 context policy for a same-holdout comparison."""
    found = retrieval.search(req.message, req.unit, req.history)
    recent = dialogue.bounded_history(req.history)
    legacy_mode = "TOPIC" if found.context else "GENERAL"
    user = dialogue.build_user_prompt(req.message, found.context, req.unit, legacy_mode, facts="")
    user = strip_block(user, "LANGUAGE COACHING HINT\n", "END HINT")
    return [{"role": "system", "content": dialogue.VOICE_SYSTEM_PROMPT}, *recent,
            {"role": "user", "content": user}]


def prepare(case, model, cap, variant, provider):
    req = ChatRequest(message=case["message"], unit=case["unit"], history=history_objects(case),
                      provider=provider, model=model, max_tokens=cap, temperature=0.2)
    actual_route = dialogue.get_response_mode(req.message, req.unit, req.history)
    if variant == "v1":
        messages = v1_messages(req)
        resolved = config.GEMINI_MODEL if provider == "gemini" else model
        payload = llm.build_payload(req, messages, resolved, output_cap=cap)
    else:
        prepared = chat.prepare_chat(req)
        payload = prepared.payload
        user_text = payload["contents"][-1]["parts"][0]["text"] if provider == "gemini" else payload["messages"][-1]["content"]
        if variant == "v2_no_fact":
            user_text = strip_block(user_text, "LEARNER FACTS (learner-authored; role-normalized; latest wins)\n", "END LEARNER FACTS")
        elif variant == "v2_raw_turns":
            raw_turns = "\n".join(
                f"Student said: {entry.content}" for entry in req.history if entry.role == "user"
            )
            user_text = re.sub(
                re.escape("LEARNER FACTS (learner-authored; role-normalized; latest wins)\n")
                + r".*?" + re.escape("END LEARNER FACTS"),
                "LEARNER FACTS (raw learner turns; oldest to newest; no normalization)\n"
                + raw_turns + "\nEND LEARNER FACTS",
                user_text,
                flags=re.S,
            )
        elif variant == "v2_no_hint":
            user_text = strip_block(user_text, "LANGUAGE COACHING HINT\n", "END HINT")
        if provider == "gemini":
            payload["contents"][-1]["parts"][0]["text"] = user_text
        else:
            payload["messages"][-1]["content"] = user_text
    if provider == "ollama":
        payload["stream"] = False
        payload["options"]["num_predict"] = cap
    return req, actual_route, payload


def text_match(output, patterns):
    low = output.lower()
    return all(any(option.strip().lower() in low for option in pattern.split("|")) for pattern in patterns)


def score(case, output):
    required = text_match(output, case["required"])
    forbidden = not any(option.strip().lower() in output.lower()
                        for item in case["forbidden"] for option in item.split("|"))
    role_ok = True
    if case.get("role_check"):
        role_ok = not re.search(r"\b(?:i|my|me|mine)\b", output, re.I)
    return required and forbidden and role_ok, required, forbidden, role_ok


async def ollama_call(payload):
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
        response.raise_for_status()
    return response.json(), (time.perf_counter() - started) * 1000


async def gemini_call(payload):
    started = time.perf_counter()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(url, headers={"x-goog-api-key": llm.resolve_gemini_key()}, json=payload)
        response.raise_for_status()
    data = response.json()
    text = "".join(part.get("text", "") for candidate in data.get("candidates", [])
                   for part in candidate.get("content", {}).get("parts", []) if not part.get("thought"))
    reason = (data.get("candidates") or [{}])[0].get("finishReason")
    return {"message": {"content": text}, "done_reason": reason,
            "eval_count": None}, (time.perf_counter() - started) * 1000


async def run(args):
    protocol_bytes = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_bytes)
    output_dir = HERE / args.output
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "protocol.json").write_bytes(protocol_bytes)
    records = []
    for variant in args.variants.split(","):
        for case in protocol["cases"]:
            req, actual_route, payload = prepare(case, args.model, args.cap, variant, args.provider)
            try:
                raw, elapsed_ms = await (ollama_call(payload) if args.provider == "ollama" else gemini_call(payload))
                unfiltered = raw.get("message", {}).get("content", "")
                filter_activated = bool(dialogue.VIETNAMESE_OUTPUT.search(unfiltered))
                response_filter = dialogue.StreamingResponseFilter(req.message, actual_route)
                output = response_filter.feed(unfiltered) + response_filter.finish()
                passed, required_ok, forbidden_ok, role_ok = score(case, output)
                eval_count = raw.get("eval_count")
                done_reason = raw.get("done_reason") or raw.get("doneReason")
                truncated = str(done_reason).lower() in {"length", "max_tokens"} or (
                    isinstance(eval_count, int) and eval_count >= args.cap)
                reasoning = bool(re.search(r"</?think>|\b(?:we need to|let's reason|analysis:)\b", unfiltered, re.I))
                error = None
            except Exception as exc:
                output = unfiltered = ""
                elapsed_ms = None
                filter_activated = truncated = reasoning = False
                eval_count = done_reason = None
                passed = required_ok = forbidden_ok = role_ok = False
                error = f"{type(exc).__name__}: {exc}"
            records.append({
                "id": case["id"], "family": case["family"], "variant": variant,
                "provider": args.provider, "model": args.model, "cap": args.cap,
                "expected_route": case["expected_route"], "actual_route": actual_route,
                "route_correct": actual_route == case["expected_route"],
                "response": output, "unfiltered_response": unfiltered,
                "pass": passed, "required_ok": required_ok, "forbidden_ok": forbidden_ok,
                "role_ok": role_ok, "word_count": len(re.findall(r"\b\w+(?:['-]\w+)?\b", output)),
                "elapsed_ms": elapsed_ms, "eval_count": eval_count, "done_reason": done_reason,
                "truncated": truncated, "filter_activated": filter_activated,
                "reasoning_leakage": reasoning, "error": error,
            })
            print(args.provider, args.model, variant, case["id"], "PASS" if passed else "FAIL", flush=True)
    with (output_dir / "records.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {"protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
               "provider": args.provider, "model": args.model, "cap": args.cap, "variants": {}}
    for variant in args.variants.split(","):
        rows = [r for r in records if r["variant"] == variant]
        words = [r["word_count"] for r in rows if not r["error"]]
        times = [r["elapsed_ms"] for r in rows if r["elapsed_ms"] is not None]
        summary["variants"][variant] = {
            "n": len(rows), "requests_ok": sum(not r["error"] for r in rows),
            "route_correct": sum(r["route_correct"] for r in rows),
            "functional_pass": sum(r["pass"] for r in rows),
            "median_words": statistics.median(words) if words else None,
            "median_ms": statistics.median(times) if times else None,
            "truncated": sum(r["truncated"] for r in rows),
            "filter_activated": sum(r["filter_activated"] for r in rows),
            "reasoning_leakage": sum(r["reasoning_leakage"] for r in rows),
        }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["ollama", "gemini"], default="ollama")
    parser.add_argument("--model", default="qwen3:1.7b")
    parser.add_argument("--cap", type=int, default=56)
    parser.add_argument("--variants", default="v1,v2,v2_no_fact,v2_no_hint")
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))
