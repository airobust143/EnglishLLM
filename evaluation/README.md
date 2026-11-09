# Evaluation suites

The evaluation code keeps three suites separate so that system changes do not silently rewrite the reported benchmark.

- `core36`: the original functional test sheet.
- `paper12`: the twelve frozen probes used in the paper ablation.
- `generalization`: 29 prospective probes: ten latest-value updates, ten history follow-ups, and nine grammar errors (three cases in each priority family).
- `holdout`: 16 post-development probes frozen after prompt/routing changes; do not tune the system against their outcomes.

The generalization suite includes violin controls whose latest value is not a lesson-topic answer. This distinguishes session recall from curriculum retrieval that merely returns a plausible topic-associated value.

## Run locally

Start the API, then run each model into a different output directory:

```powershell
python evaluation/run.py --suite generalization --model qwen3:1.7b --output evaluation/runs/qwen3_1_7b_generalization
python evaluation/run.py --suite generalization --model llama3.2:3b --output evaluation/runs/llama3_2_3b_generalization
python evaluation/run.py --suite holdout --model qwen3:1.7b --output evaluation/runs/qwen3_1_7b_holdout
```

Score a completed transcript without making any provider call:

```powershell
python evaluation/score_generalization.py --input evaluation/runs/qwen3_1_7b_generalization/transcripts.jsonl --output evaluation/runs/qwen3_1_7b_generalization/deterministic_scores.csv
```

For update and follow-up probes, a pass requires the expected latest value, correct speaker role, and absence of the stale value. Grammar probes require the target form and absence of the known erroneous form. These are narrow conformance checks; human ratings are still needed for relevance, naturalness, and pedagogical quality.

Do not merge prospective generalization results into the paper's original 180 observations. Report them as a new evaluation or a post-revision experiment with the exact model and code revision.

Freeze the code before creating/running a holdout and do not revise prompts or scorers after viewing its outputs. Model-size comparisons also require a package whose serving template honors the requested no-think mode; otherwise report the configuration incompatibility rather than ranking model capability from truncated reasoning text.
