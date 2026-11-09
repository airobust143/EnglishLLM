"""Metadata routing and cached BM25; no embedding model or vector service."""
import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

from backend import config
from backend.services.corpus import load_corpus

STOP = set("a an and are at can do for how i in is it me my of on or the to what when where which who why you please unit bai trang exercise page".split())
ALIASES = {"viec nha": "housework chores", "moi truong": "environment green", "tai che": "recycle recycling",
           "am nhac": "music", "cau bi dong": "passive voice", "hien tai don": "present simple",
           "hien tai tiep dien": "present continuous", "tuong lai": "future will going",
           "tiet kiem nang luong": "save energy", "gia dinh": "family", "cau ghep": "compound sentences",
           "dong tu nguyen mau": "infinitive", "nguoi tru cot": "breadwinner"}
SECTIONS = {"grammar": "grammar", "ngu phap": "grammar", "speaking": "speaking", "luyen noi": "speaking",
            "reading": "reading", "bai doc": "reading", "listening": "listening", "bai nghe": "listening",
            "writing": "writing", "bai viet": "writing", "vocabulary": "vocabulary", "tu vung": "vocabulary",
            "pronunciation": "pronunciation", "phat am": "pronunciation", "getting started": "getting started",
            "looking back": "looking back", "culture": "culture", "clil": "clil", "communication": "communication"}


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower().replace("đ", "d")) if not unicodedata.combining(c))


def tokens(text):
    normalized = normalize(text)
    for phrase, translation in ALIASES.items():
        if phrase in normalized:
            normalized += " " + translation
    return [t for t in re.findall(r"[a-z0-9]+", normalized) if t not in STOP]


@lru_cache(maxsize=8)
def _index(signature):
    counters = [Counter(tokens(text)) for text in signature]
    frequencies = Counter(t for counts in counters for t in counts)
    average = sum(sum(c.values()) for c in counters) / max(len(counters), 1)
    return counters, frequencies, average


def rank(records, query):
    signature = tuple(r.embed_text + " " + " ".join(r.search_aliases_vi) for r in records)
    counters, frequencies, average = _index(signature)
    terms = set(tokens(query))
    scores = []
    for record, counts in zip(records, counters):
        length = sum(counts.values())
        score = sum(math.log(1 + (len(records) - frequencies[t] + .5) / (frequencies[t] + .5))
                    * counts[t] * 2.2 / (counts[t] + 1.2 * (.25 + .75 * length / max(average, 1)))
                    for t in terms if counts[t])
        if score > 0:
            scores.append((score, record))
    return [r for _, r in sorted(scores, key=lambda pair: (-pair[0], pair[1].id))]


def contextual_query(message, history=None):
    normalized = normalize(message).strip(" .?!")
    short_turns = {"why", "how", "why not", "tai sao", "vi sao", "goi y", "hint", "another hint", "hint 2", "goi y 2"}
    attempt_pattern = r"^(my answer|my attempt|cau tra loi cua em|dap an cua em)\s*:"
    followup = normalized in short_turns or bool(re.match(attempt_pattern, normalized))
    prior = []
    if followup:
        turns = [e.content for e in history or [] if e.role == "user"]
        for turn in reversed(turns):
            text = normalize(turn).strip(" .?!")
            if text not in short_turns and not re.match(attempt_pattern, text):
                prior = [turn]
                break
        if not prior:
            prior = turns[-1:]
    return "\n".join([*prior, message])


@dataclass
class RetrievalResult:
    context: str = ""
    sources: list[dict] = field(default_factory=list)
    study: bool = False
    clarification: str | None = None

    @property
    def files(self):
        return [str(config.RAG_CORPUS.relative_to(config.BASE_DIR)) if config.RAG_CORPUS.is_relative_to(config.BASE_DIR)
                else config.RAG_CORPUS.name] if self.sources else []


def _excerpt(text, query, limit=900):
    if len(text) <= limit:
        return text
    # Preserve complete lines where possible (including glossary rows).
    pieces = []
    for line in text.splitlines():
        if len(line) > limit:
            pieces.extend(line[i:i + limit - 30] for i in range(0, len(line), limit - 30))
        elif line.strip():
            pieces.append(line)
    terms = set(tokens(query))
    best = max(range(len(pieces)), key=lambda i: len(terms & set(tokens(pieces[i]))))
    excerpt = pieces[best]
    for line in pieces[best + 1:]:
        if len(excerpt) + len(line) + 1 > limit - 30:
            break
        excerpt += "\n" + line
    return excerpt + "\n[Partial excerpt]"


def _section_choices(records):
    """Return short human-facing section names for an ambiguous exercise number."""
    names = []
    for record in records:
        name = (record.section or "Other").split(">")[-1].strip()
        if name not in names:
            names.append(name)
    return names


def search(message, unit=None, history=None, *, exercise_id=None, attempt=None, budget=None):
    records = load_corpus()
    query = contextual_query(message, history)
    q = normalize(query)
    current_ids = re.findall(r"\bU\d+-[A-Z0-9-]+\b", message.upper())
    ids = [exercise_id.upper()] if exercise_id else current_ids or re.findall(r"\bU\d+-[A-Z0-9-]+\b", query.upper())
    requested_units = {int(n) for n in re.findall(r"\bunit\s*(\d+)\b", q)}
    requested_units.update(int(re.match(r"U(\d+)", id_)[1]) for id_ in ids)
    result = RetrievalResult()
    if len(requested_units) > 1 or not requested_units <= {1, 2, 3}:
        result.clarification = "Please ask about one Unit at a time."
        return result
    # A Unit or record explicitly named by the learner overrides the current UI tab.
    selected_unit = next(iter(requested_units), unit)
    candidates = [r for r in records if selected_unit is None or r.unit == selected_unit]
    pages = re.findall(r"\b(?:page|trang)\s*(\d+)\b", q)
    exercises = re.findall(r"\b(?:exercise|bai(?: tap)?)\s*(\d+)\b", q)
    sections = {target for phrase, target in SECTIONS.items() if re.search(r"\b" + phrase + r"\b", q)}
    exact = bool(ids or exercises or pages)
    explicit_attempt = attempt or re.search(r"(?:my answer|my attempt|cau tra loi cua em|dap an cua em)\s*:\s*(.+)", normalize(message))
    knowledge = any(
        term in q for term in ("passive voice", "present simple", "present continuous", "infinitive",
                               "compound sentence", "cau bi dong", "hien tai don", "hien tai tiep dien", "cau ghep",
                               "dong tu nguyen mau", "will and be going to"))
    practice = bool(re.search(
        r"\b(?:exercise|practice|quiz|bai tap|luyen tap|ask me (?:a )?question|"
        r"give me (?:a )?question|hoi em|cho em (?:mot )?cau hoi)\b", q
    ))
    overview = bool(requested_units) and bool(re.search(
        r"\b(?:what is unit|what.*unit.*about|tell me about (?:the )?unit|"
        r"unit.*overview|noi dung unit|chu de unit|hoc gi)\b", q
    ))
    result.study = exact or bool(sections) or bool(requested_units) or knowledge or practice
    if ids:
        candidates = [r for r in candidates if r.id in ids]
        if len(set(ids)) != 1:
            candidates = []
    else:
        if pages:
            candidates = [r for r in candidates if r.page == int(pages[-1])]
        if exercises:
            candidates = [r for r in candidates if r.exercise == exercises[-1] and r.chunk_kind == "exercise"]
        if sections:
            candidates = [r for r in candidates if all(s in normalize(r.section or "") for s in sections)]
    if exact and exercises and len(candidates) > 1:
        sections = ", ".join(_section_choices(candidates))
        result.clarification = f"Exercise {exercises[-1]} appears in several sections. Which section do you mean: {sections}?"
        return result
    if exact and not candidates:
        location = f"Unit {selected_unit}" if selected_unit else "the lesson data"
        result.clarification = f"I could not find that exercise or page in {location}. Please check the number or section."
        return result
    if explicit_attempt and (not exact or len(candidates) != 1 or candidates[0].chunk_kind != "exercise"):
        result.clarification = "Please give the exercise ID with your answer so I can check the correct exercise."
        return result
    selected = candidates if exact else rank(candidates, query)
    if not exact and overview:
        selected = [r for r in candidates if r.chunk_kind == "overview"]
    elif not exact and knowledge and not practice:
        # For rule questions, prefer relevant reference material among the shortlist.
        selected = sorted(selected[:6], key=lambda r: r.chunk_kind != "reference") + selected[6:]
    elif not exact and practice:
        selected = [r for r in selected if r.chunk_kind == "exercise"]
        if not selected and selected_unit:
            selected = [r for r in candidates if r.chunk_kind == "exercise"]
    selected = selected[:config.RAG_TOP_K]
    if not selected and selected_unit:
        selected = [r for r in candidates if r.chunk_kind == "overview"]
    if not selected:
        if result.study:
            result.clarification = "I could not find supporting lesson material for that question. Please check the Unit or section."
        return result
    primary = selected[0]
    exercise_selected = exact and len(candidates) == 1 and primary.chunk_kind == "exercise"
    can_grade = exercise_selected and bool(explicit_attempt)
    if exercise_selected:
        by_id = {r.id: r for r in records}
        level_two = bool(re.search(r"(?:hint|goi y)\s*2", normalize(message)))
        hint_refs = [ref for h in primary.hints or [] if level_two and h.level == 2 for ref in h.ref_ids]
        related = primary.source_ids + hint_refs + primary.see_also
        selected = [primary] + [by_id[id_] for id_ in dict.fromkeys(related)][:config.RAG_TOP_K]
    blocks = []
    budget = min(config.RAG_MAX_CONTEXT_CHARS, budget if budget is not None else config.RAG_MAX_CONTEXT_CHARS)
    for record in selected:
        source = record.public()
        public = {key: source[key] for key in ("id", "unit", "reconstructed", "text")}
        if source["reconstruction_note"]:
            public["reconstruction_note"] = source["reconstruction_note"]
        if source["required_source_ids"]:
            public["required_source_ids"] = source["required_source_ids"]
        if record == primary and record.page is not None and pages:
            public["page"] = record.page
        if record.chunk_kind != "exercise":
            public["text"] = _excerpt(public["text"] or "", query, 1300 if record == primary else 800)
        block = {"student_visible": public}
        if record == primary and record.chunk_kind == "exercise":
            block["stage"] = "feedback" if can_grade else "attempt_first"
            level = 2 if re.search(r"(?:hint|goi y)\s*2", normalize(message)) else 1
            block["hint"] = next((h.text for h in record.hints or [] if h.level == level), None)
            if can_grade:
                block["teacher_only"] = {"answer": record.answer, "explanation": record.explanation,
                                         "teacher_notes": record.teacher_notes}
        encoded = json.dumps(block, ensure_ascii=False)
        if len(encoded) + sum(len(b) + 2 for b in blocks) > budget:
            if record == primary:
                if result.study:
                    result.clarification = "This exercise needs more context space. Please start a new conversation or increase OLLAMA_NUM_CTX and RAG_MAX_CONTEXT_CHARS."
                return result
            continue
        blocks.append(encoded)
        result.sources.append(record.provenance())
    result.context = "\n\n".join(blocks)
    return result


def retrieve_context(message, unit):
    result = search(message, unit)
    return result.context, result.files


def get_chat_context(message, unit, history=None):
    return retrieve_context(contextual_query(message, history), unit)


def get_document_context(unit=None):
    records = [r for r in load_corpus() if unit is None or r.unit == unit]
    context = "\n".join(json.dumps(r.public(), ensure_ascii=False) for r in records)
    return context, RetrievalResult(sources=[r.provenance() for r in records]).files
