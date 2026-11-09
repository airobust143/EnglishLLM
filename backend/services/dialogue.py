"""Tutor policy, prompt construction, history budgets and output filtering."""
import re
from backend.catalog import GREETINGS, UNIT_TOPIC_KEYWORDS
from backend.config import OLLAMA_NUM_CTX, PROMPTS_DIR

VOICE_SYSTEM_PROMPT = (PROMPTS_DIR / "tutor.txt").read_text(encoding="utf-8")

MEMORY_QUESTION_PATTERNS = (
    r"\bwhat did i (?:say|tell|mention)\b",
    r"\bwhen did i (?:say|tell|mention)\b",
    r"\bwhy did i say\b",
    r"\bwhich (?:one |instrument |activity |task |place )?do i\b",
    r"\bhow do i (?:travel|go|get|usually)\b",
    r"\bwhat (?:instrument|activity|task|place|day|time) do i\b",
    r"\bwhy is that\b",
    r"\bhow does that\b",
    r"\b(?:what|when|where|which|who|how)\b.*\b(?:do i|did i|my|we|our)\b",
    r"^(?:who|when|where|which)\b",
)

VIETNAMESE_OUTPUT = re.compile(
    r"(?:\bVietnamese\s*:|\bDịch\s*:|[ăâđêôơưĂÂĐÊÔƠƯ]|"
    r"[áàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ])",
    re.IGNORECASE,
)


def get_response_mode(message: str, unit: int | None, history=None):
    normalized = " ".join(re.findall(r"[a-z]+", message.lower()))

    if normalized in GREETINGS:
        return "GREETING"

    if history and any(re.search(pattern, normalized) for pattern in MEMORY_QUESTION_PATTERNS):
        return "MEMORY"

    if priority_correction_hint(message):
        return "CORRECTION"

    words = set(normalized.split())
    if unit is not None and words & UNIT_TOPIC_KEYWORDS[unit]:
        return "TOPIC"

    return "GENERAL"


class StreamingResponseFilter:
    """Stream English text while suppressing an unsolicited Vietnamese tail."""

    def __init__(self, message: str, mode: str):
        self.message = message
        self.mode = mode
        self.suppressing_vietnamese = False

    def feed(self, chunk: str):
        if not chunk:
            return ""
        if self.suppressing_vietnamese:
            boundary = re.search(r"[.!?\n]", chunk)
            if not boundary:
                return ""
            self.suppressing_vietnamese = False
            return self.feed(chunk[boundary.end():])
        match = VIETNAMESE_OUTPUT.search(chunk)
        if not match:
            return chunk
        # Translations commonly begin after a newline or inside parentheses. Remove
        # that whole segment instead of emitting a partially translated sentence.
        start = max(chunk.rfind("\n", 0, match.start()), chunk.rfind("(", 0, match.start()))
        safe = chunk[:start if start >= 0 else match.start()]
        self.suppressing_vietnamese = True
        boundary = re.search(r"[.!?\n]", chunk[match.end():])
        if boundary:
            end = match.end() + boundary.end()
            self.suppressing_vietnamese = False
            safe += self.feed(chunk[end:])
        return safe

    def finish(self):
        return ""


def should_ask_follow_up(message: str):
    normalized = " ".join(re.findall(r"[a-z]+", message.lower()))
    personal_openings = (
        "i ", "i'm ", "im ", "my ", "we ", "our ", "do you ",
        "what do you ", "which do you ", "which one do you ",
    )
    preference_words = {"favorite", "favourite", "prefer", "opinion"}
    words = set(normalized.split())
    return normalized.startswith(personal_openings) or bool(words & preference_words)


def priority_correction_hint(message: str) -> str:
    """Return a narrow, explainable grammar hint for high-priority error families."""
    normalized = " ".join(message.strip().split())
    lower = normalized.lower()
    count_match = re.search(r"\bless\s+(?:(?:[a-z]+)\s+){0,2}([a-z]+s)\b", lower)
    if count_match:
        return f"Priority grammar hint: '{count_match.group(1)}' is a plural count noun; use 'fewer', not 'less'."
    like_match = re.search(r"\blike\s+([a-z]+)\b", lower)
    if like_match and like_match.group(1) not in {"to", "a", "an", "the"} and (
        like_match.group(1) in {"sing", "bring"} or not like_match.group(1).endswith("ing")
    ):
        return "Priority grammar hint: after 'like', use either 'to + base verb' or a verb ending in '-ing'."
    enjoy_match = re.search(r"\benjoys?\s+([a-z]+)\b", lower)
    if enjoy_match and (enjoy_match.group(1) in {"sing", "bring"} or not enjoy_match.group(1).endswith("ing")):
        return "Priority grammar hint: after 'enjoy', use a verb ending in '-ing'."
    third_person = re.search(
        r"(?:^|[.!?]\s+)(?:he|she|my\s+(?:father|mother|brother|sister|uncle|aunt|cousin|friend|teacher))\s+"
        r"(cook|wash|clean|play|listen|help|go|do|make|take|have|study|work|live|drive|ride|sing)\b",
        lower,
    )
    if third_person:
        return "Priority grammar hint: check the third-person singular verb ending in the present simple."
    return ""


def normalize_learner_fact(turn: str) -> str:
    """Express a learner statement from the tutor's point of view."""
    text = turn.strip()
    text = re.sub(r"^(?:actually\s*,?\s*|correction\s*:\s*|sorry\s*,?\s*)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^i meant that\s+", "", text, flags=re.IGNORECASE)
    # The latest positive value is enough for recall; a trailing contrast would
    # reintroduce the stale value that latest-wins is meant to remove.
    text = re.sub(r"\s*,?\s+not\s+(?:the\s+)?[^,.!?]+(?=[.!?]?$)", "", text, flags=re.IGNORECASE)
    for pattern, replacement in ((r"\bi\b", "you"), (r"\bmy\b", "your"),
                                 (r"\bwe\b", "you"), (r"\bour\b", "your")):
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    if text:
        text = text[0].upper() + text[1:]
    return text


def learner_facts(history, budget=1600):
    """Keep learner-authored facts, normalize speaker role and apply latest-wins."""
    turns = [entry.content.strip() for entry in history or [] if entry.role == "user" and entry.content.strip()]
    if len(turns) >= 2 and re.search(
        r"^(?:actually\b|correction\s*:|i meant\b|sorry\b|no\s*,|rather\b)",
        turns[-1],
        re.IGNORECASE,
    ):
        # An explicit learner correction supersedes the immediately preceding
        # claim. Do not expose the stale value to the small model.
        turns.pop(-2)
    selected = []
    remaining = budget
    for turn in reversed(turns):
        cost = len(turn) + 24
        if cost > remaining:
            break
        selected.insert(0, turn)
        remaining -= cost
    lines = []
    for index, turn in enumerate(selected, 1):
        label = "latest turn" if index == len(selected) else f"turn {index}"
        lines.append(f"Learner fact ({label}; tutor perspective): {normalize_learner_fact(turn)}")
    return "\n".join(lines)


def build_user_prompt(message: str, context: str, unit: int | None = None, mode=None, facts=""):
    response_mode = mode or get_response_mode(message, unit)
    follow_up_instruction = (
        "Sentence three should be one short relevant question for continued "
        "speaking practice."
        if should_ask_follow_up(message)
        else "Do not add a follow-up question."
    )

    mode_instruction = {
        "STUDY": (
            "Use supplied lesson evidence. For an exercise, follow its stage. "
            "For a rule or word, explain with one example."
        ),
        "GREETING": (
            "Reply with one brief natural greeting only. "
            "Do not ask how you can help."
        ),
        "TOPIC": (
            "Reply in two short sentences using relevant lesson context. "
            f"{follow_up_instruction}"
        ),
        "MEMORY": (
            "Answer from LEARNER FACTS only. Conflicting statements are ordered oldest to newest, "
            "so the latest learner statement wins. Change learner self-reference from 'I/my' to "
            "'you/your', but preserve any named third person: 'my brother' becomes 'your brother', "
            "not 'you'. Copy the grammatical subject of the latest fact exactly; if it starts with "
            "'Your cousin', the answer must also start with 'Your cousin'. Never answer as if the "
            "tutor owns the learner's fact. "
            "State the remembered action or value explicitly before explaining it. Present it as a "
            "fact, not advice or a list of alternatives. Answer directly in one or two short sentences "
            "and do not retrieve a textbook topic."
        ),
        "CORRECTION": (
            "Correct the single priority grammar issue identified below. Preserve the learner's "
            "original subject, meaning, time expression, and point of view. Begin with the corrected "
            "sentence, add at most one brief explanation, and do not replace 'my father', 'my sister', "
            "or another named subject with 'you' or 'I'."
        ),
        "GENERAL": (
            "Answer in one or two short sentences using general knowledge."
        ),
    }[response_mode]

    context_block = f"CONTEXT\n{context}\nEND CONTEXT\n" if context else ""
    facts_block = (
        "LEARNER FACTS (learner-authored; role-normalized; latest wins)\n"
        f"{facts}\nEND LEARNER FACTS\n"
        if facts else ""
    )
    correction = priority_correction_hint(message)
    correction_block = f"LANGUAGE COACHING HINT\n{correction}\nEND HINT\n" if correction else ""
    return (
        f"{context_block}MODE {response_mode}: {mode_instruction}\n"
        "Reply in English only. Do not add a translation.\n"
        f"{facts_block}{correction_block}CURRENT STUDENT MESSAGE: {message}"
    )


def bounded_history(history, budget=2400):
    """Keep newest complete pairs within a conservative character budget."""
    selected = []
    remaining = budget
    entries = history or []
    for index in range(len(entries) - 2, -1, -2):
        pair = entries[index:index + 2]
        cost = sum(len(entry.content) for entry in pair)
        if cost > remaining:
            break
        selected[0:0] = [entry.model_dump() for entry in pair]
        remaining -= cost
    return selected


def prompt_budget(message, unit=None, history=None, mode=None):
    # Conservative English character estimate; reserve output and template overhead.
    # Preserve the current utterance and newest complete pairs before lesson excerpts.
    facts = learner_facts(history) if mode == "MEMORY" else ""
    available = max(0, OLLAMA_NUM_CTX * 3 - 96 * 3 - 768
                    - len(VOICE_SYSTEM_PROMPT) - len(build_user_prompt(message, "", unit, mode, facts)))
    recent = [] if mode == "MEMORY" else bounded_history(
        history, min(600 if mode == "STUDY" else 2400, available)
    )
    context_budget = max(0, available - sum(len(entry["content"]) for entry in recent))
    return recent, context_budget


def build_messages(message: str, context: str, unit: int | None = None, history=None, mode=None):
    mode = mode or get_response_mode(message, unit, history)
    if mode == "MEMORY":
        context = ""
    recent, context_budget = prompt_budget(message, unit, history, mode)
    # Never cut through a JSON evidence block or separate a key from its question.
    blocks = []
    for block in context.split("\n\n"):
        if len("\n\n".join([*blocks, block])) <= context_budget:
            blocks.append(block)
    return [
        {
            "role": "system",
            "content": VOICE_SYSTEM_PROMPT,
        },
        *recent,
        {
            "role": "user",
            "content": build_user_prompt(
                message,
                "\n\n".join(blocks),
                unit,
                mode,
                learner_facts(history) if mode == "MEMORY" else "",
            ),
        },
    ]
