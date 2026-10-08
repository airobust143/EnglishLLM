# miniVy

A compact, efficient AI speech system designed for high accuracy and low-latency performance. By combining a lightweight, fine-tuned language model with Retrieval-Augmented Generation (RAG), the system delivers precise, context-aware responses grounded in real-time data rather than relying solely on pre-trained knowledge.

## Features

- **Lightweight AI Model**: Fine-tuned language model for efficient local inference
- **RAG Integration**: Dynamic document reference for up-to-date, reliable outputs
- **Multi-format Document Support**: PDF, DOCX, TXT, MD, CSV, JSON
- **Offline Capable**: Runs entirely local with Ollama
- **Local Speech-to-Text**: Browser microphone recordings are transcribed by a cached local Whisper model
- **Automatic Voice Turn Detection**: Recording stops after detected speech and brief silence, with a manual Stop override
- **Lightweight Speech Log**: Stores human transcripts and AI responses locally as JSONL, without audio
- **Web Interface**: Next.js-based voice assistant UI
- **API Endpoint**: FastAPI backend for chat interactions

## Architecture

The system uses a targeted fine-tuning approach that adapts the model to specific domains or speech patterns, while RAG allows it to dynamically reference external documents, ensuring up-to-date and reliable outputs without the need for a massive, resource-heavy infrastructure.

## Project Structure

```
smallAI/
├── main.py              # Local Qwen3 Full Context API (FastAPI)
├── chat.py              # Terminal chat client
├── mainv.py             # Main voice assistant script
├── docs/                # Documentation files
├── data/                # Data files (FAISS index, metadata)
└── voice-assistant-web/ # Next.js web interface
```

## Requirements

- Python 3.10+
- Ollama (with qwen3:0.6b model)
- Node.js 18+ (for web interface)
- FFmpeg available on `PATH` (required by Faster-Whisper for browser audio files)

## Installation

### Backend

```bash
pip install -r requirement.txt
ollama pull qwen3:0.6b
```

The first transcription starts Faster-Whisper's configured model download (by
default `base.en`). After that, transcription runs locally. For a fully
offline setup, download the model in advance and set `WHISPER_MODEL` in `.env`
to its local directory. Voice transcription uses greedy decoding by default
(`WHISPER_BEAM_SIZE=1`) to reduce latency; increase it if recognition quality
is more important than response speed. Ollama voice replies use a 2048-token
context by default; adjust `OLLAMA_NUM_CTX` if your prompts require more
context. Voice chat uses lightweight local RAG: it retrieves the most relevant
lesson chunks instead of sending the whole lesson on every request. Set
`RAG_TOP_K` to control how many chunks are included.

### Frontend

```bash
cd voice-assistant-web
npm install
```

## Usage

### Configure Gemini (server only)

Set the Google AI Studio key in the backend process environment or in the ignored
root `.env` file. The key is never entered in, stored by, or sent from the browser.

PowerShell:

```powershell
$env:GEMINI_API_KEY="your-google-ai-studio-key"
```

Leave this variable unset if you only want to use local Ollama.

Alternatively, copy `.env.example` to `.env`, fill in `GEMINI_API_KEY`, and keep
that file private. Restart the API after changing the key.

### Start the API Server

```bash
python mainv.py
```

The API will be available at `http://127.0.0.1:8000`

### Chat via Terminal

```bash
python chat.py
```

### Start the Web Interface

```bash
cd voice-assistant-web
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## API Endpoints

- `GET /health` - Health check and system status
- `GET /document` - List loaded documents
- `GET /models` - List available providers and local Ollama models
- `POST /transcribe` - Transcribe a browser audio recording with local Whisper
- `POST /logs/speech` - Append a completed human/AI conversation to the local JSONL log
- `POST /chat` - Send chat message and provider (for example, `{"message": "Hello", "provider": "gemini"}`)

Speech logs are written to `speech_logs.jsonl` by default. Set
`SPEECH_LOG_ENABLED=false` to disable logging or change `SPEECH_LOG_FILE` to a
different local filename. Audio recordings are never stored.

## Supported Document Formats

- PDF (.pdf)
- Word (.docx)
- Text (.txt)
- Markdown (.md)
- CSV (.csv)
- JSON (.json)

## License

MIT
