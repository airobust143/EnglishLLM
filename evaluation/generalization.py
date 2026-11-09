"""Frozen paper probes and a separate generalization evaluation suite.

The twelve paper probes define the reported ablation and must remain stable.
The expanded suite is prospective: its presence does not imply measured results.
"""
from __future__ import annotations


PAPER_12_ITEMS = [
    ("T01", 1, [], "I help my mother cook dinner on weekdays. What else could I do at home?"),
    ("T05", 2, [], "What can our class do to reduce plastic waste?"),
    ("T09", 3, [], "I enjoy pop music when I study. What other music might help me focus?"),
    ("E01", 1, [], "My father cook dinner every evening."),
    ("E05", 2, [], "We should use less plastic bags."),
    ("E07", 3, [], "I like listen to music after school."),
    ("F01", 1, ["I usually wash the dishes after dinner."], "Why is that helpful?"),
    ("F03", 2, ["I carry a reusable bottle to school."], "How does that help?"),
    ("F05", 3, ["I like folk music because my grandparents play it at home."], "Why did I say I like it?"),
    ("O05", 1, ["I wash the dishes every evening.", "Actually, I wash them only on weekends."], "When did I say I wash the dishes?"),
    ("O06", 2, ["I take the bus to school.", "I meant that I cycle to school."], "How do I travel to school?"),
    ("O07", 3, ["I play the piano.", "Sorry, I play the guitar, not the piano."], "Which instrument do I play?"),
]


def _spec(family, unit, setup, probe, expected_all, *, stale_any=(),
          second_person=False, error_family=None, control=None):
    return {
        "family": family,
        "unit": unit,
        "setup": setup,
        "probe": probe,
        "expected_all": [list(group) for group in expected_all],
        "stale_any": list(stale_any),
        "second_person": second_person,
        "error_family": error_family,
        "control": control,
    }


GENERALIZATION_SPECS = {
    # Ten update probes: an earlier value is explicitly replaced.
    "O-GEN-01": _spec("update", 1,
        ["I vacuum the living room on Tuesday.", "Correction: I vacuum it on Saturday."],
        "When do I vacuum the living room?", [["saturday"]], stale_any=["tuesday"], second_person=True),
    "O-GEN-02": _spec("update", 2,
        ["I walk to the library.", "Correction: I ride my scooter to the library."],
        "How do I travel to the library?", [["scooter"]], stale_any=["walk"], second_person=True),
    "O-GEN-03": _spec("update", 3,
        ["I practise the piano after school.", "Correction: I practise the violin, not the piano."],
        "Which instrument do I practise?", [["violin"]], stale_any=["piano"], second_person=True,
        control="unseen_value_violin"),
    "O-GEN-04": _spec("update", 1,
        ["My sister cooks dinner at home.", "Correction: my brother cooks dinner at home."],
        "Who cooks dinner at my home?", [["brother"]], stale_any=["sister"], second_person=True),
    "O-GEN-05": _spec("update", 3,
        ["My favourite music is pop.", "Correction: my favourite music is jazz."],
        "What is my favourite kind of music?", [["jazz"]], stale_any=["pop"], second_person=True),
    "O-GEN-06": _spec("update", 2,
        ["Our class collects paper for recycling.", "Correction: our class collects glass for recycling."],
        "What does our class collect for recycling?", [["glass"]], stale_any=["paper"], second_person=True),
    "O-GEN-07": _spec("update", 3,
        ["I practise singing on Monday.", "Correction: I practise singing on Friday."],
        "When do I practise singing?", [["friday"]], stale_any=["monday"], second_person=True),
    "O-GEN-08": _spec("update", 1,
        ["I study English in my bedroom.", "Correction: I study English in the kitchen."],
        "Where do I study English?", [["kitchen"]], stale_any=["bedroom"], second_person=True),
    "O-GEN-09": _spec("update", 3,
        ["I sing twice a week.", "Correction: I sing every day."],
        "How often do I sing?", [["every day", "daily"]], stale_any=["twice a week"], second_person=True),
    "O-GEN-10": _spec("update", 2,
        ["I save water by taking long showers.", "Correction: I save water by taking short showers."],
        "How do I save water?", [["short"], ["shower", "showers"]], stale_any=["long shower"], second_person=True),

    # Ten single-history follow-ups with directly scorable facts.
    "F-GEN-01": _spec("followup", 1, ["I fold the clean clothes before breakfast."],
        "What do I do before breakfast?", [["fold"], ["clothes"]], second_person=True),
    "F-GEN-02": _spec("followup", 2, ["I carry a metal lunch box to school."],
        "What do I carry to school?", [["metal"], ["lunch box"]], second_person=True),
    "F-GEN-03": _spec("followup", 3, ["I listen to classical music while I read."],
        "Which kind of music did I say I listen to?", [["classical"]], second_person=True),
    "F-GEN-04": _spec("followup", 3, ["I practise the violin on Sundays."],
        "Which instrument did I say I practise?", [["violin"]], second_person=True,
        control="unseen_value_violin"),
    "F-GEN-05": _spec("followup", 1, ["My cousin waters the plants in the evening."],
        "Who waters the plants?", [["cousin"]], second_person=True),
    "F-GEN-06": _spec("followup", 2, ["We planted trees in the community park."],
        "Where did we plant trees?", [["community"], ["park"]], second_person=True),
    "F-GEN-07": _spec("followup", 1, ["I clean my room on Saturdays."],
        "When do I clean my room?", [["saturday", "saturdays"]], second_person=True),
    "F-GEN-08": _spec("followup", 2, ["I walk to football practice."],
        "How do I travel to football practice?", [["walk", "on foot"]], second_person=True),
    "F-GEN-09": _spec("followup", 2, ["I turn off the tap to save water."],
        "What do I turn off to save water?", [["tap", "faucet"]], second_person=True),
    "F-GEN-10": _spec("followup", 3, ["I listen to music before breakfast."],
        "When do I listen to music?", [["before breakfast"]], second_person=True),

    # Three examples in each priority error family.
    "E-SVA-01": _spec("error", 1, [], "My uncle drive to work every morning.",
        [["uncle drives"]], stale_any=["uncle drive "], error_family="subject_verb_agreement"),
    "E-SVA-02": _spec("error", 1, [], "My sister wash the dishes after dinner.",
        [["sister washes"]], stale_any=["sister wash "], error_family="subject_verb_agreement"),
    "E-SVA-03": _spec("error", 1, [], "He do the laundry on Sundays.",
        [["he does"]], stale_any=["he do "], error_family="subject_verb_agreement"),
    "E-COUNT-01": _spec("error", 2, [], "Our event should use less paper cups.",
        [["fewer paper cups", "fewer cups"]], stale_any=["less paper cups"], error_family="count_noun_quantifier"),
    "E-COUNT-02": _spec("error", 2, [], "Our school needs less recycling bins.",
        [["fewer recycling bins", "fewer bins"]], stale_any=["less recycling bins"], error_family="count_noun_quantifier"),
    "E-COUNT-03": _spec("error", 2, [], "We throw away less bottles now.",
        [["fewer bottles"]], stale_any=["less bottles"], error_family="count_noun_quantifier"),
    "E-COMP-01": _spec("error", 3, [], "I enjoy listen to music after school.",
        [["enjoy listening"]], stale_any=["enjoy listen "], error_family="verb_complementation"),
    "E-COMP-02": _spec("error", 3, [], "I like read mystery stories.",
        [["like reading", "like to read"]], stale_any=["like read "], error_family="verb_complementation"),
    "E-COMP-03": _spec("error", 3, [], "She enjoys sing in the school club.",
        [["enjoys singing"]], stale_any=["enjoys sing "], error_family="verb_complementation"),
}


# Frozen only after the dialogue changes were complete. Do not tune prompts or
# scorers against these cases; report failures as observed.
HOLDOUT_SPECS = {
    "H-O-01": _spec("update", 1,
        ["I study mathematics at night.", "Correction: I study it before school."],
        "When do I study mathematics?", [["before school"]], stale_any=["at night"], second_person=True),
    "H-O-02": _spec("update", 1,
        ["My backpack is red.", "Correction: my backpack is blue."],
        "What colour is my backpack?", [["blue"]], stale_any=["red"], second_person=True),
    "H-O-03": _spec("update", 1,
        ["My mother walks the dog with me.", "Correction: my father walks the dog with me."],
        "Who walks the dog with me?", [["father"]], stale_any=["mother"], second_person=True),
    "H-O-04": _spec("update", 2,
        ["Our club meets in Room 201.", "Correction: our club meets in the library."],
        "Where does our club meet?", [["library"]], stale_any=["room 201"], second_person=True),
    "H-O-05": _spec("update", 3,
        ["I practise the flute after class.", "Correction: I practise the drums after class."],
        "What do I practise after class?", [["drums"]], stale_any=["flute"], second_person=True),
    "H-F-01": _spec("followup", 1, ["My aunt bakes bread on Sundays."],
        "Who bakes bread on Sundays?", [["aunt"]], second_person=True),
    "H-F-02": _spec("followup", 2, ["I turn off the lights before bed."],
        "What do I turn off before bed?", [["lights"]], second_person=True),
    "H-F-03": _spec("followup", 1, ["I read science magazines during lunch."],
        "What do I read during lunch?", [["science"], ["magazine", "magazines"]], second_person=True),
    "H-F-04": _spec("followup", 2, ["I take the train to visit my grandparents."],
        "How do I travel to visit my grandparents?", [["train"]], second_person=True),
    "H-F-05": _spec("followup", 3, ["I rehearse with my band on Thursday."],
        "When do I rehearse with my band?", [["thursday"]], second_person=True),
    "H-E-SVA-01": _spec("error", 1, [], "My aunt teach English at school.",
        [["aunt teaches"]], stale_any=["aunt teach "], error_family="subject_verb_agreement"),
    "H-E-SVA-02": _spec("error", 1, [], "My friend go jogging every morning.",
        [["friend goes"]], stale_any=["friend go "], error_family="subject_verb_agreement"),
    "H-E-COUNT-01": _spec("error", 2, [], "We need less notebooks for this activity.",
        [["fewer notebooks"]], stale_any=["less notebooks"], error_family="count_noun_quantifier"),
    "H-E-COUNT-02": _spec("error", 2, [], "The classroom should have less chairs.",
        [["fewer chairs"]], stale_any=["less chairs"], error_family="count_noun_quantifier"),
    "H-E-COMP-01": _spec("error", 3, [], "I enjoy dance after school.",
        [["enjoy dancing"]], stale_any=["enjoy dance "], error_family="verb_complementation"),
    "H-E-COMP-02": _spec("error", 3, [], "My friend likes draw cartoons.",
        [["likes drawing", "likes to draw"]], stale_any=["likes draw "], error_family="verb_complementation"),
}


def paper12_cases():
    """Return the frozen twelve probes in the local runner's scenario format."""
    category = {"T": "typical", "E": "learner_error", "F": "followup", "O": "update"}
    return [{
        "id": item_id,
        "category": category[item_id[0]],
        "unit": unit,
        "message": message,
        "setup": list(setup),
        "expected": "Frozen paper probe; use the original pre-specified scoring protocol.",
        "correction_eligible": item_id.startswith("E"),
    } for item_id, unit, setup, message in PAPER_12_ITEMS]


def generalization_cases():
    """Return prospective probes without implying that they have been run."""
    result = []
    for item_id, spec in GENERALIZATION_SPECS.items():
        result.append({
            "id": item_id,
            "category": spec["family"],
            "unit": spec["unit"],
            "message": spec["probe"],
            "setup": list(spec["setup"]),
            "expected": "Deterministic criteria are defined in evaluation/scoring.py.",
            "correction_eligible": spec["family"] == "error",
            "error_family": spec["error_family"],
            "control": spec["control"],
        })
    return result


def holdout_cases():
    """Return the post-development holdout without implying learner outcomes."""
    return [{
        "id": item_id,
        "category": spec["family"],
        "unit": spec["unit"],
        "message": spec["probe"],
        "setup": list(spec["setup"]),
        "expected": "Frozen deterministic criteria are defined in evaluation/scoring.py.",
        "correction_eligible": spec["family"] == "error",
        "error_family": spec["error_family"],
        "control": "post_development_holdout",
    } for item_id, spec in HOLDOUT_SPECS.items()]
