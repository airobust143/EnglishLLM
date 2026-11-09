"""System information, lesson inventory and optional speech logs."""
import json
from datetime import datetime, timezone
import requests
from fastapi import APIRouter, HTTPException
from backend.config import (OLLAMA_URL, OLLAMA_MODEL, OLLAMA_MODELS, OLLAMA_NUM_CTX,
    GEMINI_MODEL, GEMINI_API_KEY, SPEECH_LOG_ENABLED, SPEECH_LOG_FILE,
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_BEAM_SIZE, WHISPER_VAD_FILTER, WHISPER_PRELOAD,
    RAG_TOP_K, RAG_VOICE_CONTEXT_CHARS, OLLAMA_VOICE_MAX_TOKENS)
from backend.schemas import SpeechLogRequest
from backend.services.retrieval import get_document_context
from backend.services.corpus import corpus_info
from backend.services.transcription import whisper_ready

router = APIRouter()

@router.post("/logs/speech")
def log_speech(entry: SpeechLogRequest):
    """Append one completed conversation to the local JSONL log."""
    if not SPEECH_LOG_ENABLED:
        return {"logged": False}

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "human": entry.human.strip(),
        "assistant": entry.assistant.strip(),
        "provider": entry.provider,
        "model": entry.model,
        "unit": entry.unit,
    }

    if not record["human"] or not record["assistant"]:
        raise HTTPException(
            status_code=400,
            detail="Both human speech and assistant response are required.",
        )

    try:
        with SPEECH_LOG_FILE.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not write the local speech log.",
        ) from exc

    return {"logged": True}

@router.get("/health")
def health():

    ollama_ok = False

    try:
        response = requests.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=3,
        )

        ollama_ok = response.ok

    except requests.RequestException:
        pass

    context, files = get_document_context()

    return {
        "status": "ok",
        "ollama": ollama_ok,
        "ollama_url": OLLAMA_URL,
        "ollama_model": OLLAMA_MODEL,
        "documents": files,
        "context_characters": len(context),
        "mode": "voice-stream",
        "speech_logging_enabled": SPEECH_LOG_ENABLED,
        "whisper": {"model": WHISPER_MODEL, "device": WHISPER_DEVICE, "compute_type": WHISPER_COMPUTE_TYPE, "beam_size": WHISPER_BEAM_SIZE, "vad_filter": WHISPER_VAD_FILTER,
                    "preload": WHISPER_PRELOAD, "ready": whisper_ready()},
        "generation": {"num_ctx": OLLAMA_NUM_CTX, "voice_max_tokens": OLLAMA_VOICE_MAX_TOKENS, "study_max_tokens": 96, "think": False},
        "retrieval": {"top_k": RAG_TOP_K, "voice_context_chars": RAG_VOICE_CONTEXT_CHARS, "method": "metadata+bm25", **corpus_info()},
        "available_models": OLLAMA_MODELS,
        "providers": ["ollama", "gemini"],
        "gemini_configured": bool(GEMINI_API_KEY),
    }


@router.get("/models")
def models():
    installed_models = list(OLLAMA_MODELS)

    try:
        response = requests.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=3,
        )
        response.raise_for_status()
        installed_models = [
            item["name"]
            for item in response.json().get("models", [])
            if item.get("name")
        ]
    except (requests.RequestException, ValueError):
        pass

    return {
        "models": installed_models,
        "default": OLLAMA_MODEL,
        "providers": [
            {
                "id": "ollama",
                "label": "Local Ollama",
                "models": installed_models,
            },
            {
                "id": "gemini",
                "label": "Google AI Studio",
                "models": [GEMINI_MODEL],
                "configured": bool(GEMINI_API_KEY),
            },
        ],
        "gemini_configured": bool(GEMINI_API_KEY),
    }

@router.get("/document")
def document():

    context, files = get_document_context()

    return {
        "files": files,
        "characters": len(context),
        "context": context,
        "corpus": corpus_info(),
    }
