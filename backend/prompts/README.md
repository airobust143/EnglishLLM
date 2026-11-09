# Prompt ownership

`tutor.txt` is the active system policy, loaded by `services/dialogue.py` when the
backend starts. Restart the API after editing it. Response-mode instructions,
history budgeting and output filtering live in that same dialogue module.

The policy uses brief replies with a 72-token voice cap and 96-token study cap. Exercise
stages (`attempt_first` / `feedback`) control hints and grading; rule questions
receive a direct explanation. English is the default, with short Vietnamese
explanations on request. Prompt behavior still needs evaluation with the real model.

`reference/` contains three tutor playbooks for human review. They are not
loaded into model requests or indexed as lesson evidence. Keep the active
policy in `tutor.txt` rather than concatenating additional policies into it.
These playbooks are optional documentation: removing them does not affect
runtime behavior, prompt size or inference latency.

Lesson evidence comes from `docs/rag_english10_global_success.jsonl`, or the
file configured by `RAG_CORPUS`. Metadata routing and BM25 retrieval live in
`services/retrieval.py`; schema validation and teacher-field separation live in
`services/corpus.py`. Arbitrary files in `docs/` are not indexed automatically.
See [RAG implementation](../../docs/RAG_IMPLEMENTATION.md) for the current flow.
