# miniVy

A compact, efficient AI speech system designed for high accuracy and low-latency performance. By combining a lightweight, fine-tuned language model with Retrieval-Augmented Generation (RAG), the system delivers precise, context-aware responses grounded in real-time data rather than relying solely on pre-trained knowledge.

## Features

- **Lightweight AI Model**: Fine-tuned language model for efficient local inference
- **RAG Integration**: Dynamic document reference for up-to-date, reliable outputs
- **Multi-format Document Support**: PDF, DOCX, TXT, MD, CSV, JSON
- **Offline Capable**: Runs entirely local with Ollama
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

- Python 3.8+
- Ollama (with qwen3:0.6b model)
- Node.js 18+ (for web interface)

## Installation

### Backend

```bash
pip install fastapi uvicorn requests pypdf python-docx
ollama pull qwen3:0.6b
```

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
- `POST /chat` - Send chat message and provider (for example, `{"message": "Hello", "provider": "gemini"}`)

## Supported Document Formats

- PDF (.pdf)
- Word (.docx)
- Text (.txt)
- Markdown (.md)
- CSV (.csv)
- JSON (.json)

## License

MIT
