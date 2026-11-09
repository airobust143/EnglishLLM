"""Author-constructed scenarios, not observed learner data or ideal transcripts."""


def cases():
    result = []
    def add(category, unit, message, expected, setup=None, correction=False):
        result.append({"id": f"{category}-{sum(c['category'] == category for c in result) + 1:02}",
                       "category": category, "unit": unit, "message": message,
                       "setup": setup or [], "expected": expected,
                       "correction_eligible": correction})

    typical = [
        (1, "I help my mother cook dinner.", "React to sharing chores and invite speaking."),
        (1, "What does a homemaker do?", "Explain in simple English."),
        (1, "My brother does the laundry.", "Discuss family responsibilities."),
        (1, "How can we share housework fairly?", "Give relevant practical advice."),
        (2, "I carry a reusable bottle to school.", "Discuss reduced waste and invite speaking."),
        (2, "How can I save water at home?", "Give simple relevant suggestions."),
        (2, "Our class plants trees every spring.", "React to environmental action."),
        (2, "Why is recycling useful?", "Explain recycling without page claims."),
        (3, "I enjoy listening to pop music.", "React to musical preference and invite speaking."),
        (3, "What is a musical instrument?", "Explain with a simple example."),
        (3, "My favourite singer is very creative.", "Invite speaking about musical preferences."),
        (3, "How can I practise singing?", "Give short relevant advice."),
    ]
    for unit, message, expected in typical:
        add("typical", unit, message, expected)
    errors = [
        (1, "He do the washing every day.", "Correct do to does."),
        (1, "My sister cook dinner every night.", "Correct cook to cooks."),
        (1, "Yesterday I clean my room.", "Correct clean to cleaned."),
        (2, "We should use less plastic bags.", "Correct less to fewer."),
        (2, "There is many trees in our school.", "Correct is to are."),
        (2, "We must to save water.", "Remove to after must."),
        (3, "She can sings very well.", "Correct sings to sing."),
        (3, "I enjoy listen to music.", "Correct listen to listening."),
    ]
    for unit, message, expected in errors:
        add("learner_error", unit, message, expected + " Preserve meaning and correct at most one issue.", correction=True)
    followups = [
        (2, ["I carry a reusable bottle to school."], "Why?", "Resolve the bottle topic from history."),
        (1, ["I wash the dishes on weekends."], "When do I wash them?", "Say on weekends; do not invent frequency."),
        (3, ["My favourite instrument is the piano."], "What about you?", "Continue the instrument topic without claiming real personal experience."),
        (2, ["I want to reduce plastic waste."], "How?", "Give an action about reducing plastic waste."),
        (1, ["I clean my room on Saturdays."], "What did I tell you about my weekends?", "Recall cleaning the room on Saturdays, not an invented activity."),
        (3, ["I listen to jazz after school."], "When?", "Recall after school."),
        (1, ["My brother cooks and I wash dishes."], "Who cooks?", "Recall the learner's brother."),
        (2, ["We planted trees in the school garden."], "Where?", "Recall the school garden."),
    ]
    for unit, setup, message, expected in followups:
        add("followup", unit, message, expected, setup)
    for unit, message in [(1, "What is two plus two?"), (2, "What colour is a ripe banana?"),
                          (3, "What is the capital of France?"), (1, "Tell me one fact about the moon.")]:
        add("offtopic_correction", unit, message, "Answer briefly without forcing the selected lesson.")
    add("offtopic_correction", 1, "When do I wash them?",
        "Use weekends, replacing the earlier frequency; do not correct valid English.",
        ["I wash the dishes every evening.", "Actually, only on weekends."], True)
    add("offtopic_correction", 3, "Please correct: She play the piano.", "Correct play to plays.", correction=True)
    add("offtopic_correction", 2, "Please correct: We should use less plastic bags.", "Correct less to fewer.", correction=True)
    add("offtopic_correction", 1, "Please check: I wash the dishes every evening.", "Recognize the valid sentence; do not invent an error.", correction=True)
    return result
