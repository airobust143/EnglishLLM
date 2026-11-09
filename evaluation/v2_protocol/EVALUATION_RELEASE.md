# LocalTutor ICCIT 2026 v2 evaluation release

This directory contains the fixed 28-test-case Stage-B/C protocol, benchmark runner, deterministic summarizer, raw model responses, and aggregate results used in the manuscript.

## Release identifier

- Git tag: `localtutor-iccitt-2026-v2-eval`
- Base repository commit before the evaluated additions: `b59b0abc1c8ef6cd604f706900b95e38bdecf0fe`
- Holdout protocol SHA-256: `6ef8498b9b4c774119491b8a00c424c41e5de982a35e13a71d588540e82effe7`

The tag itself identifies the final release commit. Use `git rev-list -n 1 localtutor-iccitt-2026-v2-eval` to recover that commit.

## Recorded configuration

- Ollama 0.40.15
- Primary model: `qwen3:1.7b` Q4_K_M
- Comparator: `qwen3:4b-instruct-2507-q4_K_M`
- Temperature: 0.2
- Output cap: 56 tokens
- Runtime context: 2,048 tokens
- `keep_alive`: 30 minutes
- No fixed seed

## Conditions

The 1.7B run contains reconstructed v1, full v2, v2 without the fact block, and v2 without hints. The separate raw-turn run replaces the fact block with verbatim student turns and excludes tutor turns. The 4B run contains reconstructed v1 and full v2. The incomplete Gemini attempt is retained only as a protocol record and is not scored.

The release does not include the copyrighted textbook PDF.
