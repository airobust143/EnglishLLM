import json
import runpy
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import main
import mainv
from backend import config
from backend.app import app, create_app
from backend.api import system
from backend.services import dialogue, llm, retrieval, transcription


@contextmanager
def model_transport(provider, text, captured):
    def handler(request):
        captured.append((request.url.path, json.loads(request.content)))
        if provider == "gemini":
            data = {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}
            return httpx.Response(200, text="data: " + json.dumps(data) + "\n\n")
        return httpx.Response(200, text=json.dumps({"message": {"content": text}, "done": True}) + "\n")
    real_client = httpx.AsyncClient
    with patch.object(config, "GEMINI_API_KEY", "test-key"), patch.object(
        llm.httpx, "AsyncClient",
        side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    ):
        yield


class BackendStructureTests(unittest.TestCase):
    def test_launchers_expose_same_app(self):
        self.assertIs(main.app, app)
        self.assertIs(mainv.app, app)
        with patch("uvicorn.run") as run:
            main.main()
            self.assertIs(run.call_args.args[0], app)
        with patch("uvicorn.run") as run:
            runpy.run_path("mainv.py", run_name="__main__")
            self.assertIs(run.call_args.args[0], app)

    def test_public_routes_survive_factory(self):
        application = create_app()
        routes = {(method.upper(), path) for path, operations in application.openapi()["paths"].items()
                  for method in operations}
        expected = {("POST", "/chat"), ("POST", "/chat/stream"), ("POST", "/transcribe"),
                    ("POST", "/logs/speech"), ("GET", "/health"), ("GET", "/models"), ("GET", "/document")}
        self.assertTrue(expected <= routes)
        model_response = SimpleNamespace(ok=True, raise_for_status=lambda: None, json=lambda: {"models": []})
        with patch.object(system.requests, "get", return_value=model_response), \
             patch.object(system, "SPEECH_LOG_ENABLED", False), \
             patch.object(config, "WHISPER_PRELOAD", False), TestClient(application) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/models").status_code, 200)
            self.assertEqual(len(client.get("/document").json()["files"]), 1)
            self.assertEqual(client.post("/logs/speech", json={"human": "Hi", "assistant": "Hello"}).json(), {"logged": False})

    def test_json_and_stream_share_payload_and_filtering(self):
        for provider in ["ollama", "gemini"]:
            for message, unit, raw, expected in [
                ("We should use less plastic bags.", 2,
                 "Use fewer plastic bags. What can you reuse?", "Use fewer plastic bags. What can you reuse?"),
                ("What is two plus two?", 1, "Four. Anything else?", "Four. Anything else?"),
                ("Why?", 2, "Because reusing bottles reduces waste.", "Because reusing bottles reduces waste."),
            ]:
                with self.subTest(provider=provider, message=message):
                    captured = []
                    request = {"message": message, "unit": unit, "provider": provider, "max_tokens": 200,
                               "history": [{"role": "user", "content": "I reuse plastic bottles."},
                                           {"role": "assistant", "content": "That can reduce waste."}]}
                    with model_transport(provider, raw, captured):
                        client = TestClient(app)
                        plain = client.post("/chat", json=request)
                        stream = client.post("/chat/stream", json=request)
                    self.assertEqual(plain.status_code, 200)
                    self.assertEqual(stream.status_code, 200)
                    self.assertEqual(plain.json()["answer"], expected)
                    self.assertEqual(plain.json()["answer"], stream.text.strip())
                    self.assertEqual(captured[0], captured[1])
                    payload = captured[0][1]
                    if provider == "ollama":
                        self.assertEqual(payload["options"]["num_predict"], config.OLLAMA_VOICE_MAX_TOKENS)
                        self.assertEqual(payload["messages"][0]["content"], dialogue.VOICE_SYSTEM_PROMPT)
                    else:
                        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 96)
                        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], dialogue.VOICE_SYSTEM_PROMPT)
                        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "I reuse plastic bottles.")

    def test_greetings_use_same_fast_path_without_inference(self):
        with patch.object(llm, "stream_reply", side_effect=AssertionError("Greeting must not invoke inference")):
            for provider in ["ollama", "gemini"]:
                client = TestClient(app)
                request = {"message": "Hello", "provider": provider}
                self.assertEqual(client.post("/chat", json=request).json()["answer"], "Hi.")
                self.assertEqual(client.post("/chat/stream", json=request).text, "Hi.")

    def test_missing_gemini_configuration_fails_both_endpoints(self):
        with patch.object(config, "GEMINI_API_KEY", ""):
            for path in ["/chat", "/chat/stream"]:
                self.assertEqual(TestClient(app).post(path, json={"message": "Why?", "provider": "gemini"}).status_code, 503)

    def test_generation_failure_returns_json_error(self):
        real_client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda request: httpx.Response(503))
        with patch.object(llm.httpx, "AsyncClient", side_effect=lambda **kw: real_client(transport=transport, **kw)):
            response = TestClient(app).post("/chat", json={"message": "Why?"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("answer", response.json())

    def test_catalogue_excludes_instructions_with_or_without_unit(self):
        for unit in [None, 1]:
            context, files = retrieval.get_document_context(unit)
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].endswith("rag_english10_global_success.jsonl"))
            self.assertNotIn('"teacher_notes":', context)
            self.assertNotIn('"answer":', context)

    def test_selected_unit_remains_isolated(self):
        for unit in (1, 2, 3):
            context, _ = retrieval.get_document_context(unit)
            self.assertEqual({json.loads(line)["unit"] for line in context.splitlines()}, {unit})
        self.assertEqual(len(retrieval.get_document_context()[1]), 1)

    def test_audio_cleanup_survives_inference_error(self):
        paths = []
        def decode(path, **kwargs):
            paths.append(Path(path))
            raise RuntimeError("Test inference failure")
        with patch.object(transcription, "get_whisper_model", return_value=SimpleNamespace(transcribe=decode)):
            response = TestClient(app).post("/transcribe", files={"audio": ("test.webm", b"fake", "audio/webm")})
        self.assertEqual(response.status_code, 422)
        self.assertFalse(paths[0].exists())

    def test_invalid_configuration_is_rejected(self):
        for value in ["0", "-1", "abc"]:
            with self.assertRaises(ValueError):
                config._positive_int(value)
        with self.assertRaises(ValueError):
            config._boolean("sometimes")


if __name__ == "__main__":
    unittest.main()
