# Stage3 Logs Manifest

Current status date: 2026-06-07

This directory holds Stage3 runtime logs. Historical mock/diagnostic logs from
the 2026-04-19 / 2026-05-18 / 2026-06-02 runs have been cleared (see CHANGELOG
[2026-06-07] entry) — their scientific content was either superseded by
CHANGELOG narrative or was mock-execution evidence with no archival value.

Conventions:

- New Stage3 runs may create a fresh `llm_calls.jsonl` here. It is execution
  evidence, not scientific evidence, and may be cleared between runs.
- `archive/` is reserved for log files that need to be retained across runs
  but moved out of the active path. The directory is currently empty (see
  `archive/README.md`); future archived logs should include a dated filename
  prefix (e.g. `archive/20260907_*.jsonl`).
- Live LLM runs that need long-term traceability should write their logs into
  a deliberate, run-specific `--output-dir` rather than this shared `logs/`
  root.
