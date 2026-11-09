"""HTTP adapters over the shared dialogue service."""
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from backend.schemas import ChatRequest
from backend.services import chat as conversation
from backend.services.llm import GenerationError

router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest):
    prepared = await run_in_threadpool(conversation.prepare_chat, req)
    started = time.perf_counter()
    try:
        answer = "".join([text async for text in conversation.generate_reply(prepared)]).strip()
    except GenerationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "answer": answer, "provider": req.provider, "model": prepared.model,
        "documents": prepared.documents, "mode": "voice",
        "sources": prepared.sources, "response_mode": prepared.response_mode,
        "timings_ms": {"retrieval": prepared.retrieval_ms,
                       "generation": (time.perf_counter() - started) * 1000},
    }


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    prepared = await run_in_threadpool(conversation.prepare_chat, req)
    return StreamingResponse(
        conversation.generate_reply(prepared),
        media_type="text/plain; charset=utf-8",
        headers={"Server-Timing": f"retrieval;dur={prepared.retrieval_ms:.3f}",
                 "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
