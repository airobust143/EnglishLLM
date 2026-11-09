"""Validated local corpus. Teacher fields never enter the public projection."""
import json
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from backend import config


class CorpusError(ValueError):
    pass


class Hint(BaseModel):
    model_config = ConfigDict(strict=True)
    level: int
    text: str
    ref_ids: list[str] = Field(default_factory=list)


class Record(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str = Field(min_length=1, pattern=r"^U[123]-[A-Z0-9-]+$")
    unit: Literal[1, 2, 3]
    section: str | None
    exercise: str | None
    page: int | None
    chunk_kind: Literal["exercise", "text", "reference", "overview"]
    embed_text: str = Field(min_length=1)
    source_file: str
    source_ids: list[str]
    see_also: list[str]
    search_aliases_vi: list[str]
    reconstructed: bool
    reconstruction_note: str | None
    answer_hidden: bool
    question: str | None
    content: str | None
    answer: str | None
    explanation: str | None
    teacher_notes: str | None
    hints: list[Hint] | None

    def provenance(self):
        return {"id": self.id, "unit": self.unit, "section": self.section,
                "exercise": self.exercise, "page": self.page, "page_verified": False,
                "reconstructed": self.reconstructed, "source_file": self.source_file}

    def public(self):
        # Exercise content can duplicate a key; explicitly select only the question.
        return {**self.provenance(), "text": self.question if self.chunk_kind == "exercise" else self.content,
                "reconstruction_note": self.reconstruction_note,
                "required_source_ids": self.source_ids}


@lru_cache(maxsize=2)
def _load(path: str, mtime: int, size: int) -> tuple[Record, ...]:
    records = []
    try:
        with open(path, encoding="utf-8-sig") as source:
            for line_number, line in enumerate(source, 1):
                if line.strip():
                    try:
                        record = Record.model_validate(json.loads(line))
                    except ValueError as exc:
                        raise CorpusError(f"Invalid corpus record at line {line_number}") from exc
                    if not record.id.startswith(f"U{record.unit}-"):
                        raise CorpusError(f"ID/unit mismatch: {record.id}")
                    if record.chunk_kind == "exercise" and not (
                        record.question and record.answer and record.answer_hidden
                    ):
                        raise CorpusError(f"Missing question/hidden answer: {record.id}")
                    if "ANSWER:" in record.embed_text.upper():
                        raise CorpusError(f"Answer marker in index: {record.id}")
                    records.append(record)
    except (OSError, UnicodeError) as exc:
        raise CorpusError("Cannot read RAG corpus") from exc
    indexed = {r.id: r for r in records}
    if not records or len(indexed) != len(records):
        raise CorpusError("Empty corpus or duplicate record IDs")
    for record in records:
        refs = record.source_ids + record.see_also + [ref for h in record.hints or [] for ref in h.ref_ids]
        for ref in refs:
            if ref not in indexed or indexed[ref].unit != record.unit:
                raise CorpusError(f"Missing or cross-unit reference: {record.id} -> {ref}")
    return tuple(records)


def load_corpus() -> tuple[Record, ...]:
    try:
        path = config.RAG_CORPUS.resolve()
        stat = path.stat()
        return _load(str(path), stat.st_mtime_ns, stat.st_size)
    except OSError as exc:
        raise CorpusError("RAG corpus is missing or unreadable") from exc


def corpus_info():
    records = load_corpus()
    return {"records": len(records), "units": {str(u): sum(r.unit == u for r in records) for u in (1, 2, 3)},
            "kinds": {kind: sum(r.chunk_kind == kind for r in records) for kind in ("exercise", "text", "reference", "overview")},
            "reconstructed_ids": [r.id for r in records if r.reconstructed],
            "missing_source_files": sorted({r.source_file for r in records if not (config.DOCS_DIR / r.source_file).is_file()})}
