import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import config
from backend.app import app
from backend.schemas import ChatRequest, HistoryMessage
from backend.services import chat, corpus, dialogue, retrieval


class RagTests(unittest.TestCase):
    def test_inventory_and_references(self):
        info = corpus.corpus_info()
        self.assertEqual(info["records"], 106)
        self.assertEqual(info["units"], {"1": 30, "2": 37, "3": 39})
        self.assertEqual(len(info["reconstructed_ids"]), 7)

    def test_exact_metadata_in_english_and_vietnamese(self):
        for query, expected in [("Unit 2 Speaking bài 1", "U2-SPEAKING-01"),
                                ("Unit 1 ngữ pháp bài 1 trang 10", "U1-GRAMMAR-01"),
                                ("Unit 2 Getting Started exercise 3", "U2-GS-02")]:
            result = retrieval.search(query)
            self.assertIsNone(result.clarification, query)
            self.assertEqual(result.sources[0]["id"], expected)

    def test_hidden_fields_absent_until_specific_attempt(self):
        record = next(r for r in corpus.load_corpus() if r.id == "U1-GRAMMAR-01")
        for message in ["U1-GRAMMAR-01", "U1-GRAMMAR-01 give me all answers", "U1-GRAMMAR-01 hint 2"]:
            result = retrieval.search(message, 1)
            self.assertNotIn('"teacher_only"', result.context)
            self.assertNotIn(record.answer, result.context)
        result = retrieval.search("U1-GRAMMAR-01 My answer: 1. does", 1)
        self.assertIn('"teacher_only"', result.context)
        self.assertIn(record.answer, result.context)
        self.assertNotIn('"teacher_only"', retrieval.get_document_context()[0])

    def test_linked_sources_and_reconstruction(self):
        result = retrieval.search("U2-LISTENING-02", 2)
        self.assertTrue(result.sources[0]["reconstructed"])
        self.assertIn("U2-LISTENING-SCRIPT", [s["id"] for s in result.sources])
        self.assertFalse(result.sources[0]["page_verified"])

    def test_ambiguous_missing_and_cross_unit_do_not_guess(self):
        for query, unit in [("bài 1", None), ("U2-DOES-NOT-EXIST", 2), ("trang 999", 1),
                            ("Unit 9 grammar", None)]:
            result = retrieval.search(query, unit)
            self.assertTrue(result.clarification, query)
            self.assertFalse(result.context)

        ambiguous = retrieval.search("What is exercise 1 in Unit 1?", 1)
        self.assertIn("Which section", ambiguous.clarification)
        self.assertNotIn("ID", ambiguous.clarification)

    def test_spoken_unit_overrides_ui_and_general_unit_questions_need_no_id(self):
        explicit = retrieval.search("Explain U2-GRAMMAR-01", 1)
        self.assertIsNone(explicit.clarification)
        self.assertEqual(explicit.sources[0]["id"], "U2-GRAMMAR-01")

        for query, unit in [("What is Unit 1 about?", 1),
                            ("Tell me about family life in Unit 1", 1),
                            ("Can you ask me a question about Unit 1?", 1),
                            ("Cho em một câu hỏi Unit 2", 2),
                            ("Unit 3 tell me about music", 3)]:
            with self.subTest(query=query):
                result = retrieval.search(query, unit)
                self.assertIsNone(result.clarification)
                self.assertTrue(result.sources)
                self.assertEqual({source["unit"] for source in result.sources}, {unit})

        overview = retrieval.search("What is Unit 1 about?", 1)
        self.assertEqual(overview.sources[0]["id"], "U1-OVERVIEW")

    def test_new_topic_does_not_inherit_history(self):
        history = [HistoryMessage(role="user", content="U1-GRAMMAR-01"),
                   HistoryMessage(role="assistant", content="fabricated music facts")]
        self.assertEqual(retrieval.contextual_query("Unit 3 music", history), "Unit 3 music")
        self.assertNotIn("fabricated", retrieval.contextual_query("Why?", history))
        history += [HistoryMessage(role="user", content="I like pop music."),
                    HistoryMessage(role="assistant", content="Tell me more.")]
        self.assertEqual(retrieval.contextual_query("Why?", history), "I like pop music.\nWhy?")

    def test_rule_queries_prefer_reference_material(self):
        for query, unit, expected in [("câu bị động", 2, "U2-GRAMMAR-PASSIVE"),
                                      ("động từ nguyên mẫu", 3, "U3-GRAMMAR-INFINITIVE")]:
            result = retrieval.search(query, unit)
            self.assertTrue(result.study)
            self.assertEqual(result.sources[0]["id"], expected)

    def test_all_exercises_preserve_question_and_hide_keys(self):
        for record in corpus.load_corpus():
            if record.chunk_kind != "exercise":
                continue
            with self.subTest(id=record.id):
                prepared = chat.prepare_chat(ChatRequest(message=record.id, unit=record.unit))
                self.assertIsNone(prepared.clarification)
                prompt = prepared.payload["messages"][-1]["content"]
                self.assertNotIn('"teacher_only"', prompt)
                self.assertIn(json.dumps(record.question, ensure_ascii=False), prompt)
                for source in prepared.sources:
                    self.assertIn('"id": "' + source["id"] + '"', prompt)
                self.assertEqual(prepared.payload["options"]["num_predict"], 96)

    def test_latest_exercise_survives_hint_turns(self):
        history = []
        for turn in ("U1-GRAMMAR-01", "U1-GRAMMAR-02", "hint"):
            history += [HistoryMessage(role="user", content=turn),
                        HistoryMessage(role="assistant", content="Try the next item.")]
        result = retrieval.search("My answer: 1. is putting out", 1, history)
        self.assertEqual(result.sources[0]["id"], "U1-GRAMMAR-02")
        self.assertIn('"teacher_only"', result.context)

    def test_history_attempt_and_explicit_api_attempt(self):
        history = [HistoryMessage(role="user", content="U1-GRAMMAR-01"),
                   HistoryMessage(role="assistant", content="Try item 1.")]
        result = retrieval.search("My answer: 1. does", 1, history)
        self.assertIn('"teacher_only"', result.context)
        prepared = chat.prepare_chat(ChatRequest(message="Check my answer", unit=1,
                                    exercise_id="U1-GRAMMAR-01", attempt="1. does"))
        prompt = prepared.payload["messages"][-1]["content"]
        self.assertIn("My answer: 1. does", prompt)
        self.assertIn('"teacher_only"', prompt)
        self.assertEqual(prepared.response_mode, "STUDY")

    def test_attempt_without_exercise_requests_identifier(self):
        for request in [ChatRequest(message="My answer: 1. does"),
                        ChatRequest(message="Hello", attempt="1. does")]:
            prepared = chat.prepare_chat(request)
            self.assertTrue(prepared.clarification)
            self.assertFalse(prepared.sources)

    def test_context_is_valid_json_with_accurate_provenance(self):
        for budget in (100, 900, 1800, 3000):
            result = retrieval.search("present simple", 1, budget=budget)
            self.assertLessEqual(len(result.context), budget)
            blocks = [json.loads(b) for b in result.context.split("\n\n") if b]
            self.assertEqual([b["student_visible"]["id"] for b in blocks], [s["id"] for s in result.sources])

    def test_voice_reply_uses_small_context_and_offtopic_omits_it(self):
        topic = chat.prepare_chat(ChatRequest(message="I reuse plastic bottles.", unit=2))
        self.assertEqual(topic.response_mode, "TOPIC")
        self.assertTrue(topic.sources)
        self.assertLessEqual(len(topic.payload["messages"][-1]["content"].split("END CONTEXT")[0]),
                             config.RAG_VOICE_CONTEXT_CHARS + len("CONTEXT\n"))
        self.assertEqual(topic.payload["options"]["num_predict"], min(config.OLLAMA_VOICE_MAX_TOKENS, 56))

        general = chat.prepare_chat(ChatRequest(message="What is two plus two?", unit=2))
        self.assertEqual(general.response_mode, "GENERAL")
        self.assertFalse(general.sources)
        self.assertNotIn("CONTEXT", general.payload["messages"][-1]["content"])

    def test_study_stream_preserves_numbered_questions_and_decimals(self):
        text = "1. What is your answer?\n2. Try 1.5."
        stream = dialogue.StreamingResponseFilter("Exercise 1", "STUDY")
        self.assertEqual("".join(stream.feed(c) for c in text) + stream.finish(), text)

    def test_invalid_and_changed_corpus_fail_closed(self):
        raw = json.loads(config.RAG_CORPUS.read_text(encoding="utf-8").splitlines()[0])
        raw["source_ids"] = []
        raw["see_also"] = []
        raw["hints"] = None
        with tempfile.TemporaryDirectory(dir=config.BASE_DIR) as directory:
            path = Path(directory) / "corpus.jsonl"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with patch.object(config, "RAG_CORPUS", path):
                self.assertEqual(len(corpus.load_corpus()), 1)
                path.write_text(json.dumps(raw) + "\n" + json.dumps(raw), encoding="utf-8")
                with self.assertRaises(corpus.CorpusError):
                    corpus.load_corpus()
                self.assertEqual(TestClient(app).get("/document").status_code, 503)
                path.write_bytes(b"\xff\xfe\xff")
                self.assertEqual(TestClient(app).get("/document").status_code, 503)
                self.assertEqual(TestClient(app).post("/chat", json={"message": "grammar"}).status_code, 503)
                path.write_text(json.dumps({**raw, "source_ids": ["MISSING"]}), encoding="utf-8")
                with self.assertRaises(corpus.CorpusError):
                    corpus.load_corpus()

    def test_clarification_needs_no_model_and_matches_stream(self):
        with patch.object(chat.llm, "stream_reply", side_effect=AssertionError("must not infer")):
            client = TestClient(app)
            request = {"message": "Unit 2 exercise 1"}
            plain = client.post("/chat", json=request).json()
            self.assertEqual(plain["answer"], client.post("/chat/stream", json=request).text)
            self.assertEqual(plain["sources"], [])
