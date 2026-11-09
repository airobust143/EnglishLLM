"""One dialogue pipeline for JSON and streamed HTTP responses."""
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from backend import config
from backend.schemas import ChatRequest
from backend.services import dialogue, llm, retrieval


@dataclass(frozen=True)
class PreparedChat:
    request: ChatRequest
    model: str
    response_mode: str
    documents: list[str]
    retrieval_ms: float
    payload: dict
    sources: list[dict]
    clarification: str | None = None


def prepare_chat(req: ChatRequest) -> PreparedChat:
    started = time.perf_counter()
    mode = dialogue.get_response_mode(req.message, req.unit, req.history)
    message = req.message + ("\nMy answer: " + req.attempt if req.attempt else "")
    skip_retrieval = mode in {"GREETING", "MEMORY", "CORRECTION"} and not req.exercise_id and not req.attempt
    result = retrieval.RetrievalResult() if skip_retrieval else retrieval.search(
        req.message, req.unit, req.history, exercise_id=req.exercise_id, attempt=req.attempt)
    if result.study or result.clarification:
        mode = "STUDY"
    if mode == "GENERAL":
        result.context = ""
        result.sources.clear()
    _, budget = dialogue.prompt_budget(message, req.unit, req.history, mode)
    budget = min(budget, config.RAG_VOICE_CONTEXT_CHARS) if mode == "TOPIC" else budget
    if len(result.context) > budget:
        result = retrieval.search(req.message, req.unit, req.history, exercise_id=req.exercise_id,
                                  attempt=req.attempt, budget=budget)
    retrieval_ms = (time.perf_counter() - started) * 1000
    model = config.GEMINI_MODEL if req.provider == "gemini" else llm.resolve_model(req.model)
    if req.provider == "gemini" and mode != "GREETING" and not result.clarification:
        llm.resolve_gemini_key()
    messages = dialogue.build_messages(message, result.context, req.unit, req.history, mode)
    output_cap = 96 if mode == "STUDY" else min(config.OLLAMA_VOICE_MAX_TOKENS, 56)
    return PreparedChat(req, model, mode, result.files, retrieval_ms,
                        llm.build_payload(req, messages, model, output_cap=output_cap),
                        result.sources, result.clarification)


async def generate_reply(prepared: PreparedChat) -> AsyncIterator[str]:
    if prepared.clarification:
        yield prepared.clarification
        return
    if prepared.response_mode == "GREETING":
        yield "Hi."
        return
    response_filter = dialogue.StreamingResponseFilter(prepared.request.message, prepared.response_mode)
    emitted = False
    async for chunk in llm.stream_reply(prepared.request.provider, prepared.payload):
        text = response_filter.feed(chunk)
        if text:
            emitted = True
            yield text
    tail = response_filter.finish()
    if tail:
        emitted = True
        yield tail
    if not emitted:
        raise llm.GenerationError("The assistant returned an empty response.")
