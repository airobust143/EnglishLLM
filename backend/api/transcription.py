"""Audio upload endpoint."""
from fastapi import APIRouter, File, Response, UploadFile
from backend.services import transcription

router = APIRouter()


@router.post("/transcribe")
async def transcribe_audio(response: Response, audio: UploadFile = File(...)):
    result = await transcription.transcribe_audio(audio)
    timings = result["timings_ms"]
    response.headers["Server-Timing"] = (
        f"whisper_load;dur={timings['model_load']:.3f}, "
        f"whisper_decode;dur={timings['decode']:.3f}"
    )
    return result
