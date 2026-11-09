# LocalTutor v2 evaluation summary — 9 November 2026

## Fixed protocol

- 28 distinct typed probes: 6 updates, 4 follow-ups, 5 targeted errors, 4 out-of-list errors, 4 topic turns, 3 negative controls, and 2 greetings.
- Protocol SHA-256: `6ef8498b9b4c774119491b8a00c424c41e5de982a35e13a71d588540e82effe7`.
- The protocol was written before model runs. Each probe contains an expected route and deterministic content/role constraints.
- The v1 condition is a documented reconstruction on the new holdout: ordered history and retrieved context are included, while the v2 learner-fact block and correction hints are absent. It is not the historical Stage-A executable.

## Primary model: Qwen3-1.7B, cap 56

| Condition | Pass | Update | Follow-up | Targeted error | Out-of-list | Negative control | Median words | Median time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Reconstructed v1 | 16/28 | 2/6 | 3/4 | 0/5 | 2/4 | 3/3 | 13 | 4.369 s |
| Full v2 | 22/28 | 5/6 | 4/4 | 2/5 | 2/4 | 3/3 | 9 | 1.466 s |
| Raw student turns | 17/28 | 0/6 | 4/4 | 2/5 | 2/4 | 3/3 | 9 | 1.555 s |
| v2 without fact block | 14/28 | 0/6 | 1/4 | 2/5 | 2/4 | 3/3 | 9 | 1.308 s |
| v2 without hints | 20/28 | 5/6 | 4/4 | 0/5 | 2/4 | 3/3 | 9 | 1.269 s |

- Routing matched the authored expectation for 28/28 test cases. The same deterministic router was used by every condition; this is rule coverage, not a learned-classifier accuracy estimate.
- Full-v2 functional conformance was 22/28 (Wilson 95% CI 60.5–89.8%).
- The no-fact prompt retained the v2 system policy, route, English-only instruction, and current question but omitted both facts and ordinary history on memory routes. The raw-turn condition inserted student turns verbatim and excluded tutor turns, without stale-value removal or pronoun conversion.
- Raw turns preserved 4/4 simple follow-ups but passed 0/6 updates. Student information is therefore necessary in these cases, but this comparison does not isolate extraction, latest-wins selection, and pronoun conversion.
- All five targeted errors triggered the hint rule. Only E01 and E04 passed under full v2; E02, E03, and E05 are model-realization failures after rule coverage. None of the four out-of-list errors triggered a hint, identifying a coverage limit.
- Hints improved the targeted cases from 0/5 to 2/5 and did not improve the four out-of-list cases (2/4 with or without the evaluated hint mechanism).
- Full-v2 word-count IQR was 7.0–13.8; time IQR was 1.183–2.131 s.
- Full v2 produced a question in 4/28 replies, including 2/7 turns for which the response policy selected a follow-up.
- Across all five Stage-B conditions, no response reached the cap, activated the Vietnamese filter, or leaked reasoning markers.

## Qwen3-4B-Instruct-2507, cap 56

The official Ollama `qwen3:4b-instruct-2507-q4_K_M` package was used. Ollama reported 100% CPU and a 2,048-token runtime context.

| Condition | Pass | Median words | Median time | Cap | Vietnamese filter | Reasoning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reconstructed v1 | 18/28 | 15 | 10.189 s | 0/28 | 0/28 | 0/28 |
| Full v2 | 20/28 | 14 | 2.905 s | 0/28 | 0/28 | 0/28 |

No cap-96 follow-up was run because neither local model produced any cap event at 56 tokens.

## Gemini

A same-holdout Gemini-v2 run was attempted but did not return a result within the available run window and was stopped before any complete record was written. The paper therefore restricts cloud claims to the previously recorded Stage-A comparison and does not report a Stage-C Gemini score.

## Reproducibility notes

- Release tag: `localtutor-iccitt-2026-v2-eval` (commit recorded in the tagged README and Git metadata).
- Ollama version: 0.40.15.
- Raw records include the 1.7B five-condition runs and the 4B v1/v2 runs.
