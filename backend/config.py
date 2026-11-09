"""Process configuration. Invalid numeric/boolean settings fail at startup."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BASE_DIR / "docs"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise ValueError(f"Expected a positive integer, got {value!r}")
    return number

def _boolean(value: str) -> bool:
    if value.lower() not in {"true", "false"}:
        raise ValueError("Boolean configuration must be true or false")
    return value.lower() == "true"

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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_NUM_CTX = _positive_int(os.getenv("OLLAMA_NUM_CTX", "2048"))
RAG_TOP_K = _positive_int(os.getenv("RAG_TOP_K", "3"))
RAG_CORPUS = BASE_DIR / os.getenv("RAG_CORPUS", "docs/rag_english10_global_success.jsonl")
RAG_MAX_CONTEXT_CHARS = _positive_int(os.getenv("RAG_MAX_CONTEXT_CHARS", "3000"))
RAG_VOICE_CONTEXT_CHARS = _positive_int(os.getenv("RAG_VOICE_CONTEXT_CHARS", "1200"))
OLLAMA_VOICE_MAX_TOKENS = _positive_int(os.getenv("OLLAMA_VOICE_MAX_TOKENS", "72"))
OLLAMA_MODELS = tuple(
    dict.fromkeys(
        model.strip()
        for model in os.getenv(
            "OLLAMA_MODELS",
            f"{OLLAMA_MODEL},qwen3:1.7b,qwen3:0.6b,llama3.2:3b",
        ).split(",")
        if model.strip()
    )
)
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_BEAM_SIZE = _positive_int(os.getenv("WHISPER_BEAM_SIZE", "1"))
WHISPER_VAD_FILTER = _boolean(os.getenv("WHISPER_VAD_FILTER", "false"))
WHISPER_PRELOAD = _boolean(os.getenv("WHISPER_PRELOAD", "true"))
SPEECH_LOG_ENABLED = _boolean(os.getenv("SPEECH_LOG_ENABLED", "true"))
SPEECH_LOG_FILE = BASE_DIR / os.getenv("SPEECH_LOG_FILE", "speech_logs.jsonl")
PORT = _positive_int(os.getenv("PORT", "8000"))

if PORT > 65535:
    raise ValueError("PORT must be between 1 and 65535")
