"""Provider payloads and streaming transport, shared by both chat endpoints."""
import json
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException

from backend import config
from backend.schemas import ChatRequest


class GenerationError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def resolve_model(requested_model: str | None) -> str:
    model = (requested_model or config.OLLAMA_MODEL).strip()
    if not model:
        raise HTTPException(status_code=400, detail="An Ollama model name is required.")
    return model


def resolve_gemini_key() -> str:
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail=(
            "Gemini is not configured on the server. "
            "Set the GEMINI_API_KEY environment variable and restart the API."
        ))
    return config.GEMINI_API_KEY


def build_payload(req: ChatRequest, messages: list[dict], model: str, *, output_cap: int = 96) -> dict:
    max_tokens = min(req.max_tokens, output_cap)
    if req.provider == "gemini":
        return {
            "systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
            "contents": [
                {"role": "model" if entry["role"] == "assistant" else "user",
                 "parts": [{"text": entry["content"]}]}
                for entry in messages[1:]
            ],
            "generationConfig": {"temperature": req.temperature, "maxOutputTokens": max_tokens},
        }
    return {
        "model": model, "think": False, "messages": messages, "stream": True,
        "keep_alive": "30m",
        "options": {"temperature": req.temperature, "num_predict": max_tokens,
                    "num_ctx": config.OLLAMA_NUM_CTX},
    }


async def stream_reply(provider: str, payload: dict) -> AsyncIterator[str]:
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:streamGenerateContent"
        options = {"params": {"alt": "sse"}, "headers": {"x-goog-api-key": resolve_gemini_key()}}
    else:
        url = f"{config.OLLAMA_URL}/api/chat"
        options = {}

    completed = False
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", url, json=payload, **options) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if provider == "gemini":
                        if not line.startswith("data:"):
                            continue
                        line = line[5:].strip()
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise GenerationError(f"Invalid {provider} stream") from exc
                    if data.get("error"):
                        raise GenerationError(f"{provider} generation failed")
                    if provider == "gemini":
                        candidates = data.get("candidates") or []
                        if not candidates:
                            continue
                        candidate = candidates[0]
                        for part in candidate.get("content", {}).get("parts", []):
                            if part.get("text") and not part.get("thought"):
                                yield part["text"]
                        reason = candidate.get("finishReason")
                        if reason:
                            if reason not in {"STOP", "MAX_TOKENS"}:
                                raise GenerationError(f"Gemini generation stopped: {reason}")
                            completed = True
                            break
                    else:
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            completed = True
                            break
                if not completed:
                    raise GenerationError(f"{provider} stream ended before completion")
    except httpx.HTTPStatusError as exc:
        status = 503 if exc.response.status_code in {429, 503} else 502
        raise GenerationError(f"{provider} service request failed ({exc.response.status_code})", status) from exc
    except httpx.HTTPError as exc:
        raise GenerationError(f"{provider} service is unavailable", 503) from exc
