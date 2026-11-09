"""Lazy local Whisper inference and temporary audio lifecycle."""
import tempfile
import time
from threading import Lock
from pathlib import Path
from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from backend.config import BASE_DIR, WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_BEAM_SIZE, WHISPER_VAD_FILTER

_whisper_model = None
_model_lock = Lock()

def get_whisper_model():
    """Load the local Whisper model once, on the first transcription request."""
    global _whisper_model

    if _whisper_model is None:
        with _model_lock:
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


def whisper_ready() -> bool:
    return _whisper_model is not None


async def transcribe_audio(audio: UploadFile):
    """Transcribe a browser recording locally with Whisper."""
    if not audio.filename:
        raise HTTPException(status_code=400, detail="An audio recording is required.")

    audio_data = await audio.read(25 * 1024 * 1024 + 1)

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

        def decode():
            started = time.perf_counter()
            model = get_whisper_model()
            model_ms = (time.perf_counter() - started) * 1000
            segments, _ = model.transcribe(
                str(temporary_path), language="en", vad_filter=WHISPER_VAD_FILTER,
                beam_size=WHISPER_BEAM_SIZE, condition_on_previous_text=False,
            )
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            decode_ms = (time.perf_counter() - started) * 1000 - model_ms
            return transcript, model_ms, decode_ms

        transcript, model_ms, decode_ms = await run_in_threadpool(decode)

        return {"text": transcript, "timings_ms": {"model_load": model_ms, "decode": decode_ms}}
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not transcribe the audio recording: {exc}",
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
