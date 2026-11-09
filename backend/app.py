"""Application factory and router registration."""
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.services.corpus import CorpusError

from backend import config
from backend.services import transcription as transcription_service
from backend.api import chat, system, transcription


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Local English Tutor | model={config.OLLAMA_MODEL} | docs={config.DOCS_DIR}")
    print(f"API: http://127.0.0.1:{config.PORT}")
    if config.WHISPER_PRELOAD:
        def preload():
            try:
                transcription_service.get_whisper_model()
            except Exception as exc:
                print(f"[WHISPER] Preload failed: {exc}")
        Thread(target=preload, daemon=True, name="whisper-preload").start()
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="Local Qwen Voice Assistant API", version="3.0.0", lifespan=lifespan)
    @application.exception_handler(CorpusError)
    async def corpus_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    application.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"], expose_headers=["Server-Timing"],
    )
    for router in (chat.router, transcription.router, system.router):
        application.include_router(router)
    return application


app = create_app()
