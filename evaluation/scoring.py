"""Deterministic scorers for the prospective generalization suite.

These checks are intentionally narrow. They assess explicit value recall,
speaker role, stale-value suppression, and target-form production. They are not
substitutes for human judgments of relevance or pedagogical quality.
"""
from __future__ import annotations

import re

try:
    from .generalization import GENERALIZATION_SPECS, HOLDOUT_SPECS
except ImportError:  # Supports `python evaluation/score_generalization.py`.
    from generalization import GENERALIZATION_SPECS, HOLDOUT_SPECS

SCORING_SPECS = {**GENERALIZATION_SPECS, **HOLDOUT_SPECS}


FIRST_PERSON = re.compile(r"\b(?:i|i'm|i've|i'd|i'll|me|my|mine)\b", re.IGNORECASE)


def normalize(text):
    return " ".join(re.findall(r"[a-z0-9']+", (text or "").lower()))


def contains_phrase(text, phrase):
    """Match a normalized word sequence without substring false positives."""
    normalized_text = normalize(text)
    normalized_phrase = normalize(phrase)
    if not normalized_phrase:
        return False
    pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, normalized_phrase.split())) + r"(?!\w)"
    return re.search(pattern, normalized_text) is not None


def matches_all_groups(text, expected_all):
    return all(any(contains_phrase(text, alias) for alias in group) for group in expected_all)


def score_response(item_id, response, status="ok"):
    """Score one response using the frozen criteria for its probe.

    Speaker-role scoring is strict: a response to a learner-memory question
    fails if it uses a first-person pronoun, even when the expected value is
    present. Elliptical answers such as "On weekends" remain acceptable.
    """
    if item_id not in SCORING_SPECS:
        raise KeyError(f"No generalization scoring specification for {item_id}")
    spec = SCORING_SPECS[item_id]
    request_success = status == "ok" and bool((response or "").strip())
    value_correct = request_success and matches_all_groups(response, spec["expected_all"])
    no_stale_value = request_success and not any(
        contains_phrase(response, phrase) for phrase in spec["stale_any"]
    )
    role_correct = request_success and (
        not spec["second_person"] or FIRST_PERSON.search(response or "") is None
    )
    criterion = {
        "update": "latest_value_correct",
        "followup": "followup_fact_correct",
        "error": "target_form_correct",
    }[spec["family"]]
    return {
        "item_id": item_id,
        "family": spec["family"],
        "error_family": spec["error_family"],
        "control": spec["control"],
        "request_success": request_success,
        "value_criterion": criterion,
        "value_correct": value_correct,
        "second_person_role_correct": role_correct,
        "no_stale_value": no_stale_value,
        "overall_pass": request_success and value_correct and role_correct and no_stale_value,
    }
