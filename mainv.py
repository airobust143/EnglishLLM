#!/usr/bin/env python3
"""
Local Voice Assistant API
FastAPI + Ollama + Qwen3

Features
- Reads documents from docs/
- Supports PDF DOCX TXT MD CSV JSON
- Full-context prompting
- Streaming Ollama responses
- Short English voice-conversation responses
"""

from __future__ import annotations
from fastapi.middleware.cors import CORSMiddleware
import json
import httpx
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import requests
from docx import Document
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(exist_ok=True)


def load_local_environment(path: Path) -> None:
    """Load simple KEY=VALUE entries without exposing them to the web client."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"").strip("'")

        if name and name not in os.environ:
            os.environ[name] = value


load_local_environment(BASE_DIR / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
OLLAMA_MODELS = tuple(
    dict.fromkeys(
        model.strip()
        for model in os.getenv(
            "OLLAMA_MODELS",
            f"{OLLAMA_MODEL},qwen3:0.6b,qwen3:1.7b,llama3.2:3b",
        ).split(",")
        if model.strip()
    )
)
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
SPEECH_LOG_ENABLED = os.getenv("SPEECH_LOG_ENABLED", "true").lower() == "true"
SPEECH_LOG_FILE = BASE_DIR / os.getenv("SPEECH_LOG_FILE", "speech_logs.jsonl")
PORT = int(os.getenv("PORT", "8000"))
_whisper_model = None

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".json",
}


app = FastAPI(
    title="Local Qwen Voice Assistant API",
    version="3.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    provider: Literal["ollama", "gemini"] = "ollama"
    unit: Literal[1, 2, 3] | None = None
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 2048


class SpeechLogRequest(BaseModel):
    human: str = Field(min_length=1, max_length=4000)
    assistant: str = Field(min_length=1, max_length=8000)
    provider: Literal["ollama", "gemini"] = "ollama"
    model: str | None = Field(default=None, max_length=200)
    unit: Literal[1, 2, 3] | None = None


@app.post("/logs/speech")
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


def resolve_model(requested_model: str | None) -> str:
    model = (requested_model or OLLAMA_MODEL).strip()

    if not model:
        raise HTTPException(status_code=400, detail="An Ollama model name is required.")

    return model


def resolve_gemini_key() -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini is not configured on the server. "
                "Set the GEMINI_API_KEY environment variable and restart the API."
            ),
        )

    return GEMINI_API_KEY


def get_whisper_model():
    """Load the local Whisper model once, on the first transcription request."""
    global _whisper_model

    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Local speech-to-text is not installed. "
                    "Install the backend requirements, including faster-whisper."
                ),
            ) from exc

        try:
            _whisper_model = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
            )
        except (OSError, RuntimeError) as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Could not load the local Whisper model '{WHISPER_MODEL}'. "
                    "Set WHISPER_MODEL to a downloaded model directory if offline."
                ),
            ) from exc

    return _whisper_model


@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribe a browser recording locally with Whisper."""
    if not audio.filename:
        raise HTTPException(status_code=400, detail="An audio recording is required.")

    audio_data = await audio.read()

    if not audio_data:
        raise HTTPException(status_code=400, detail="The audio recording is empty.")

    if len(audio_data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="The audio recording is too large.")

    suffix = Path(audio.filename).suffix.lower() or ".webm"
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
            dir=BASE_DIR,
        ) as temporary_file:
            temporary_file.write(audio_data)
            temporary_path = Path(temporary_file.name)

        model = get_whisper_model()
        segments, _ = model.transcribe(
            str(temporary_path),
            language="en",
            vad_filter=True,
            beam_size=WHISPER_BEAM_SIZE,
            condition_on_previous_text=False,
        )
        transcript = " ".join(segment.text.strip() for segment in segments).strip()

        return {"text": transcript}
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not transcribe the audio recording: {exc}",
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def gemini_chat(
    message: str,
    context: str,
    unit: int | None,
    api_key: str,
    temperature: float,
    max_tokens: int,
) -> str:
    response = None

    for attempt in range(3):
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": api_key},
            json={
                "systemInstruction": {
                    "parts": [{"text": VOICE_SYSTEM_PROMPT}],
                },
                "contents": [{
                    "role": "user",
                    "parts": [{
                        "text": build_user_prompt(message, context, unit),
                    }],
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            },
            timeout=300,
        )

        if response.ok or response.status_code not in {429, 503}:
            break

        if attempt < 2:
            time.sleep(2 ** attempt)

    if not response.ok:
        try:
            upstream_error = response.json().get("error", {})
            upstream_message = upstream_error.get(
                "message",
                "Google AI Studio request failed.",
            )
        except ValueError:
            upstream_message = "Google AI Studio request failed."

        raise HTTPException(
            status_code=response.status_code,
            detail=upstream_message,
        )

    data = response.json()
    return (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""

            if text.strip():
                pages.append(
                    f"[PAGE {page_number}]\n{text}"
                )

        except Exception as exc:
            print(
                f"[PDF] Failed page {page_number} "
                f"in {path}: {exc}"
            )

    return "\n\n".join(pages)


def read_docx(path: Path) -> str:
    doc = Document(str(path))
    parts = []

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()

        if text:
            parts.append(text)

    for table_index, table in enumerate(
        doc.tables,
        start=1,
    ):
        parts.append(f"[TABLE {table_index}]")

        for row in table.rows:
            cells = [
                cell.text.strip()
                for cell in row.cells
            ]

            if any(cells):
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return read_pdf(path)

    if suffix == ".docx":
        return read_docx(path)

    if suffix in {
        ".txt",
        ".md",
        ".csv",
    }:
        return read_text_file(path)

    if suffix == ".json":
        raw = read_text_file(path)

        try:
            data = json.loads(raw)

            return json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )

        except json.JSONDecodeError:
            return raw

    return ""


def load_all_documents(paths: list[Path] | None = None):
    documents = []
    file_names = []

    document_paths = paths if paths is not None else sorted(DOCS_DIR.rglob("*"))

    for path in document_paths:

        if not path.is_file():
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            text = read_document(path).strip()

            if not text:
                continue

            relative_path = str(
                path.relative_to(BASE_DIR)
            )

            documents.append(
                f"===== DOCUMENT: {relative_path} =====\n"
                f"{text}"
            )

            file_names.append(relative_path)

        except Exception as exc:
            print(
                f"[DOCS] Failed to read "
                f"{path}: {exc}"
            )

    return "\n\n".join(documents), file_names


_document_cache = {}

UNIT_CONTENT_FILES = {
    1: "unit-1-family-life.md",
    2: "unit-2-humans-environment.md",
    3: "unit-3-music.md",
}

UNIT_TOPIC_KEYWORDS = {
    1: {
        "family", "parent", "parents", "mother", "father", "mom", "dad",
        "sister", "brother", "sibling", "siblings", "child", "children",
        "chore", "chores", "housework", "laundry", "dishes", "cooking",
        "cook", "clean", "cleaning", "rubbish", "trash", "groceries",
        "breadwinner", "homemaker", "routine", "responsibility",
    },
    2: {
        "environment", "environmental", "green", "pollution", "recycle",
        "recycling", "reuse", "plastic", "waste", "litter", "energy",
        "water", "carbon", "eco", "climate", "tree", "trees", "cleanup",
        "resources", "nature", "protect",
    },
    3: {
        "music", "song", "songs", "singer", "musician", "artist", "band",
        "instrument", "instruments", "guitar", "piano", "drums", "concert",
        "festival", "performance", "perform", "album", "single", "lyrics",
        "rhythm", "melody", "playlist", "listen", "listening", "audience",
    },
}

GREETINGS = {
    "hello", "hi", "hey", "hello there", "hi there", "good morning",
    "good afternoon", "good evening",
}


def get_document_context(unit: int | None = None):
    if unit is not None:
        unit_path = DOCS_DIR / UNIT_CONTENT_FILES[unit]
        paths = [unit_path] if unit_path.is_file() else []
    else:
        paths = [
            path
            for path in sorted(DOCS_DIR.rglob("*"))
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

    signature = tuple(
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        for path in paths
    )
    cache_key = unit or "all"
    cached = _document_cache.get(cache_key)

    if cached is None or cached[0] != signature:
        cached = (signature, load_all_documents(paths))
        _document_cache[cache_key] = cached

    return cached[1]


_rag_cache = {}


def _split_retrieval_chunks(text: str, source: str):
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]
    chunks = []
    for index in range(0, len(paragraphs), 2):
        paragraph_group = paragraphs[index:index + 2]
        chunk_text = "\n\n".join(paragraph_group)
        chunks.append({
            "source": source,
            "text": chunk_text,
            "terms": set(re.findall(r"[a-z]+", chunk_text.lower())),
        })
    return chunks


def _get_retrieval_chunks(unit: int | None):
    if unit is not None:
        unit_path = DOCS_DIR / UNIT_CONTENT_FILES[unit]
        paths = [unit_path] if unit_path.is_file() else []
    else:
        paths = [
            path
            for path in sorted(DOCS_DIR.rglob("*"))
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

    signature = tuple(
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        for path in paths
    )
    cache_key = unit or "all"
    cached = _rag_cache.get(cache_key)

    if cached is None or cached[0] != signature:
        chunks = []
        for path in paths:
            try:
                chunks.extend(
                    _split_retrieval_chunks(
                        read_document(path),
                        str(path.relative_to(BASE_DIR)),
                    )
                )
            except (OSError, ValueError):
                continue
        cached = (signature, chunks)
        _rag_cache[cache_key] = cached

    return cached[1]


def retrieve_context(message: str, unit: int | None):
    """Retrieve a few relevant lesson chunks without an embedding dependency."""
    query_terms = {
        term
        for term in re.findall(r"[a-z]+", message.lower())
        if term not in {
            "a", "an", "and", "are", "at", "can", "do", "for", "how",
            "i", "in", "is", "it", "me", "my", "of", "on", "or", "the",
            "to", "unrelated", "what", "when", "where", "which", "who",
            "why", "you",
        }
    }
    if not query_terms:
        return "", []

    scored_chunks = []
    for chunk in _get_retrieval_chunks(unit):
        overlap = query_terms & chunk["terms"]
        if not overlap:
            continue

        score = len(overlap) / max(len(query_terms), 1)
        scored_chunks.append((score, len(overlap), chunk))

    scored_chunks.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [item[2] for item in scored_chunks[:max(RAG_TOP_K, 1)]]

    context = "\n\n".join(
        f"[SOURCE: {chunk['source']}]\n{chunk['text']}"
        for chunk in selected
    )
    files = list(dict.fromkeys(chunk["source"] for chunk in selected))
    return context, files


def get_chat_context(message: str, unit: int | None):
    """Use lightweight RAG to keep only relevant lesson context in the prompt."""
    return retrieve_context(message, unit)


VOICE_SYSTEM_PROMPT = """
You are a concise English conversation partner
Answer only the users latest request
Treat lesson context as optional guidance rather than a restriction
Never repeat quote or paraphrase the users question
Answer questions with new relevant information
Never begin the answer with the same question phrase as the user
Use lesson context only when it directly answers the request
Follow the RESPONSE MODE instruction exactly
For GREETING use one brief greeting and do not ask how you can help
For TOPIC give two or three useful natural sentences and sometimes end with one relevant question
For GENERAL answer normally in one or two short sentences without redirecting to the lesson
Do not reuse a stock phrase from an earlier reply
When explicitly asked to review an answer give one strength one correction and one improved answer
Do not mix lesson units or invent facts
Use simple spoken English normal punctuation and plain text
Stop when the answer is complete
"""


def get_response_mode(message: str, unit: int | None):
    normalized = " ".join(re.findall(r"[a-z]+", message.lower()))

    if normalized in GREETINGS:
        return "GREETING"

    words = set(normalized.split())
    if unit is not None and words & UNIT_TOPIC_KEYWORDS[unit]:
        return "TOPIC"

    return "GENERAL"


def sentence_repeats_message(sentence: str, message: str):
    message_words = set(re.findall(r"[a-z]+", message.lower()))
    sentence_words = set(re.findall(r"[a-z]+", sentence.lower()))

    if not message_words or not sentence_words:
        return False

    shared_ratio = len(message_words & sentence_words) / min(
        len(message_words),
        len(sentence_words),
    )
    return shared_ratio >= 0.75


def clean_response(answer: str, message: str, mode: str):
    """Remove small-model echoing and enforce the selected response mode."""
    if mode == "GREETING":
        return "Hi."

    sentences = [
        sentence.strip()
        for sentence in re.findall(r"[^.!?]+[.!?]?", answer.strip())
        if sentence.strip()
    ]

    if sentences and sentence_repeats_message(sentences[0], message):
        sentences.pop(0)

    if mode == "GENERAL":
        statements = [
            sentence for sentence in sentences
            if not sentence.endswith("?")
        ]
        if statements:
            sentences = statements[:2]
    else:
        if not should_ask_follow_up(message):
            statements = [
                sentence for sentence in sentences
                if not sentence.endswith("?")
            ]
            if statements:
                sentences = statements
        sentences = sentences[:3]

    cleaned = " ".join(sentences).strip()
    return cleaned or answer.strip()


class StreamingResponseFilter:
    """Release complete sentences while enforcing response-mode rules."""

    def __init__(self, message: str, mode: str):
        self.message = message
        self.mode = mode
        self.buffer = ""
        self.checked_opening = False
        self.emitted_sentences = 0

    def _accept(self, sentence: str):
        sentence = sentence.strip()
        if not sentence:
            return ""

        if not self.checked_opening:
            self.checked_opening = True
            if sentence_repeats_message(sentence, self.message):
                return ""

        if sentence.endswith("?") and (
            self.mode == "GENERAL"
            or not should_ask_follow_up(self.message)
        ):
            return ""

        sentence_limit = 2 if self.mode == "GENERAL" else 3
        if self.emitted_sentences >= sentence_limit:
            return ""

        self.emitted_sentences += 1
        return sentence + " "

    def feed(self, chunk: str):
        self.buffer += chunk
        output = []

        while True:
            match = re.search(r"[.!?\n]", self.buffer)
            if match is None:
                break

            end = match.end()
            output.append(self._accept(self.buffer[:end]))
            self.buffer = self.buffer[end:]

        return "".join(output)

    def finish(self):
        tail = self._accept(self.buffer)
        self.buffer = ""
        return tail.rstrip()


def should_ask_follow_up(message: str):
    normalized = " ".join(re.findall(r"[a-z]+", message.lower()))
    personal_openings = (
        "i ", "i'm ", "im ", "my ", "we ", "our ", "do you ",
        "what do you ", "which do you ", "which one do you ",
    )
    preference_words = {"favorite", "favourite", "prefer", "opinion"}
    words = set(normalized.split())
    return normalized.startswith(personal_openings) or bool(words & preference_words)


def build_user_prompt(message: str, context: str, unit: int | None = None):
    if not context:
        return message

    response_mode = get_response_mode(message, unit)
    follow_up_instruction = (
        "Sentence three should be one short relevant question for continued "
        "speaking practice."
        if should_ask_follow_up(message)
        else "Do not add a follow-up question."
    )

    mode_instruction = {
        "GREETING": (
            "Reply with one brief natural greeting only. "
            "Do not ask how you can help."
        ),
        "TOPIC": (
            "Write two or three natural sentences using relevant lesson context. "
            "Sentence one must add a new fact reaction or idea without copying "
            "the learner. Sentence two must add useful detail. Sentence three "
            f"may be used only as instructed next. {follow_up_instruction}"
        ),
        "GENERAL": (
            "Answer normally in one or two short sentences using general "
            "knowledge. Do not mention or redirect to the lesson topic."
        ),
    }[response_mode]

    return f"""
CONTEXT

{context}

END CONTEXT

RESPONSE MODE {response_mode}

{mode_instruction}
Start immediately with the answer or a new relevant idea.
Never repeat restate quote or paraphrase the users question.
Never use the users wording as the opening sentence.

USER

{message}
"""


def build_messages(message: str, context: str, unit: int | None = None):
    return [
        {
            "role": "system",
            "content": VOICE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": build_user_prompt(message, context, unit),
        },
    ]


def ollama_stream(
    messages,
    model=OLLAMA_MODEL,
    temperature=0.2,
    max_tokens=2048,
):
    payload = {
        "model": model,
        "think": False,
        "messages": messages,
        "stream": True,
        "keep_alive": "30m",
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=300,
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ollama is not reachable. "
                f"Expected {OLLAMA_URL}. "
                f"Error: {exc}"
            ),
        )

    for line in response.iter_lines():

        if not line:
            continue

        try:
            data = json.loads(line)

            content = (
                data
                .get("message", {})
                .get("content", "")
            )

            if content:
                yield content

            if data.get("done"):
                break

        except json.JSONDecodeError:
            continue


@app.get("/health")
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
        "available_models": OLLAMA_MODELS,
        "providers": ["ollama", "gemini"],
        "gemini_configured": bool(GEMINI_API_KEY),
    }


@app.get("/models")
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

@app.post("/chat/stream/legacy")
async def chat_stream(req: ChatRequest):
    selected_model = resolve_model(req.model)
    # Đọc toàn bộ documents mỗi request
    # để luôn lấy nội dung mới nhất trong docs/
    context, files = get_chat_context(req.message, req.unit)

    messages = build_messages(
        req.message,
        context,
        req.unit,
    )

    async def generate():
        payload = {
            "model": selected_model,

            # Qwen3:
            # Chỉ stream câu trả lời, không stream thinking
            "think": False,

            "messages": messages,

            "stream": True,

            "keep_alive": "30m",

            "options": {
                "temperature": req.temperature,
                "num_predict": min(req.max_tokens, 256),
                "num_ctx": OLLAMA_NUM_CTX,
            },
        }

        print("=" * 60, flush=True)
        print("[STREAM] Request:", req.message, flush=True)
        print("[STREAM] Documents:", files, flush=True)
        print(
            "[STREAM] Context characters:",
            len(context),
            flush=True,
        )
        print(
            "[STREAM] Temperature:",
            req.temperature,
            flush=True,
        )
        print(
            "[STREAM] Max tokens:",
            req.max_tokens,
            flush=True,
        )
        print("=" * 60, flush=True)

        try:
            async with httpx.AsyncClient(
                timeout=None
            ) as client:

                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                ) as response:

                    print(
                        "[STREAM] Ollama status:",
                        response.status_code,
                        flush=True,
                    )

                    response.raise_for_status()

                    async for line in response.aiter_lines():

                        if not line:
                            continue

                        try:
                            data = json.loads(line)

                        except json.JSONDecodeError:
                            print(
                                "[STREAM] Invalid JSON:",
                                line,
                                flush=True,
                            )
                            continue

                        # Chỉ lấy content
                        # Không lấy thinking
                        content = (
                            data
                            .get("message", {})
                            .get("content", "")
                        )

                        if content:
                            print(
                                "[STREAM] TOKEN:",
                                repr(content),
                                flush=True,
                            )

                            yield content

                        if data.get("done"):
                            print(
                                "[STREAM] DONE:",
                                data.get("done_reason"),
                                flush=True,
                            )
                            break

        except httpx.HTTPError as exc:
            print(
                "[STREAM] HTTP ERROR:",
                exc,
                flush=True,
            )

        except Exception as exc:
            print(
                "[STREAM] ERROR:",
                exc,
                flush=True,
            )

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

@app.post("/chat/stream")
async def chat_stream_fast(req: ChatRequest):
    context, _ = get_chat_context(req.message, req.unit)
    max_tokens = min(req.max_tokens, 96)
    response_mode = get_response_mode(req.message, req.unit)

    if response_mode == "GREETING":
        async def generate_greeting():
            yield "Hi."

        return StreamingResponse(
            generate_greeting(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    if req.provider == "gemini":
        api_key = resolve_gemini_key()

        async def generate():
            stream_filter = StreamingResponseFilter(
                req.message,
                response_mode,
            )
            payload = {
                "systemInstruction": {
                    "parts": [{"text": VOICE_SYSTEM_PROMPT}],
                },
                "contents": [{
                    "role": "user",
                    "parts": [{
                        "text": build_user_prompt(req.message, context, req.unit),
                    }],
                }],
                "generationConfig": {
                    "temperature": req.temperature,
                    "maxOutputTokens": max_tokens,
                },
            }

            try:
                async with httpx.AsyncClient(timeout=300) as client:
                    async with client.stream(
                        "POST",
                        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:streamGenerateContent",
                        params={"alt": "sse"},
                        headers={"x-goog-api-key": api_key},
                        json=payload,
                    ) as response:
                        if not response.is_success:
                            body = await response.aread()

                            try:
                                detail = json.loads(body).get("error", {}).get(
                                    "message",
                                    "Google AI Studio request failed.",
                                )
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                detail = "Google AI Studio request failed."

                            yield detail
                            return

                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue

                            try:
                                data = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue

                            parts = (
                                data.get("candidates", [{}])[0]
                                .get("content", {})
                                .get("parts", [])
                            )

                            for part in parts:
                                if part.get("text") and not part.get("thought"):
                                    output = stream_filter.feed(part["text"])
                                    if output:
                                        yield output

                    tail = stream_filter.finish()
                    if tail:
                        yield tail
            except httpx.HTTPError:
                yield "The Gemini service is temporarily unavailable."

    else:
        selected_model = resolve_model(req.model)
        messages = build_messages(req.message, context, req.unit)

        async def generate():
            stream_filter = StreamingResponseFilter(
                req.message,
                response_mode,
            )
            payload = {
                "model": selected_model,
                "think": False,
                "messages": messages,
                "stream": True,
                "keep_alive": "30m",
                "options": {
                    "temperature": req.temperature,
                    "num_predict": max_tokens,
                    "num_ctx": OLLAMA_NUM_CTX,
                },
            }

            try:
                async with httpx.AsyncClient(timeout=300) as client:
                    async with client.stream(
                        "POST",
                        f"{OLLAMA_URL}/api/chat",
                        json=payload,
                    ) as response:
                        response.raise_for_status()

                        async for line in response.aiter_lines():
                            if not line:
                                continue

                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            content = data.get("message", {}).get("content", "")

                            if content:
                                output = stream_filter.feed(content)
                                if output:
                                    yield output

                            if data.get("done"):
                                break

                    tail = stream_filter.finish()
                    if tail:
                        yield tail
            except httpx.HTTPError:
                yield "The local Ollama service is unavailable."

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat")
def chat(req: ChatRequest):
    context, files = get_chat_context(req.message, req.unit)
    response_mode = get_response_mode(req.message, req.unit)

    if response_mode == "GREETING":
        return {
            "answer": "Hi.",
            "provider": req.provider,
            "model": GEMINI_MODEL if req.provider == "gemini" else resolve_model(req.model),
            "documents": files,
            "mode": "voice",
        }

    if req.provider == "gemini":
        answer = gemini_chat(
            req.message,
            context,
            req.unit,
            resolve_gemini_key(),
            req.temperature,
            min(req.max_tokens, 2048),
        )
        answer = clean_response(answer, req.message, response_mode)

        return {
            "answer": answer,
            "provider": "gemini",
            "model": GEMINI_MODEL,
            "documents": files,
            "mode": "voice",
        }

    selected_model = resolve_model(req.model)

    messages = build_messages(
        req.message,
        context,
        req.unit,
    )

    answer = "".join(
        ollama_stream(
            messages,
            model=selected_model,
            temperature=req.temperature,
            max_tokens=min(req.max_tokens, 96),
        )
    )
    answer = clean_response(answer, req.message, response_mode)

    return {
        "answer": answer,
        "model": selected_model,
        "documents": files,
        "mode": "voice",
    }


@app.get("/document")
def document():

    context, files = get_document_context()

    return {
        "files": files,
        "characters": len(context),
        "context": context,
    }


@app.on_event("startup")
def startup():

    print("=" * 60)
    print("Local Qwen Voice Assistant API")
    print("=" * 60)
    print(f"Ollama: {OLLAMA_URL}")
    print(f"Model:  {OLLAMA_MODEL}")
    print(f"Docs:   {DOCS_DIR}")
    print(f"API:    http://127.0.0.1:{PORT}")
    print("=" * 60)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=PORT,
    )
