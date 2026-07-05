# Phase B Minor-Fix Acceptance Note

- **Date:** 2026-06-02
- **Scope:** two confirmed minor fixes from the Phase B cleanup audit. No scope expansion.
- **Banner:** dry-run only, no scientific claim, **v2 remains HOLD**, Phase C **not unlocked**.

## Verdict: PASS

## Issue 1 - misleading S09 evidence-based instance metadata (FIXED)
In `s09_candidate_family_generator.py::run_s09`, instances from the deterministic
evidence-based branch were still labelled `origin="llm_selected_from_broad_pool"` and
`source_mode="broad_literature_pool_selection"`, even though `generation_mode` was
`evidence_based_descriptor_match`.

Fix: when `generation_mode == "evidence_based_descriptor_match"`, instances now get
truthful, non-LLM deterministic labels:
- `source_mode = "evidence_based_descriptor_match"`
- `origin = "deterministic_evidence_based_descriptor_match"`

The frozen `deterministic_from_d4` and `llm` paths are **unchanged** (default behaviour
when `s09_evidence_based_generation` is False is untouched). `material.py` was NOT
edited; `origin` is assigned post-construction (no `validate_assignment`), so the
`CandidateOrigin` Literal contract is not modified.

## Issue 2 - stale test count in the report (FIXED)
`PHASE_B_INTELLIGENCE_DRYRUN_REPORT.md` said Stage3 tests were `159 passed`. Updated to
the current `162 passed, 3 warnings` (the +1 over the cleanup note's 161 is the new
truthful-metadata test added for Issue 1), preserving the 3 pre-existing
`datetime.utcnow` deprecation-warning note.

## Tests
- `V1.0-qianduan-mainline/stage3_mechanism > python -m pytest tests -q` -> **162 passed, 3 warnings**.
- `codex/v2_engine_tools_20260601 > python -m pytest tests -q` -> **34 passed**.

New/updated tests in `test_s09_evidence_based_tier3.py`:
- default OFF -> `generation_mode == "deterministic_from_d4"` (existing, retained);
- explicit ON -> `generation_mode == "evidence_based_descriptor_match"` (existing, retained);
- explicit ON -> instances NOT `origin="llm_selected_from_broad_pool"` and NOT
  `source_mode="broad_literature_pool_selection"`;
- explicit ON -> `source_mode == "evidence_based_descriptor_match"` and
  `origin == "deterministic_evidence_based_descriptor_match"`.

## Boundaries
- Files changed: `s09_candidate_family_generator.py`, `test_s09_evidence_based_tier3.py`,
  `PHASE_B_INTELLIGENCE_DRYRUN_REPORT.md`, and this note.
- No `paper/current/**`, no frozen evidence, no raw data, no manifests/figures/builds touched.
- v2 remains **HOLD**; Phase C **not unlocked**; CHI automation not enabled.

## Addendum 2026-06-02 - schema contract regression repair

Issue 1 above was correct at the run-time level (the JSON serialized fine because
`MaterialInstance` does not use `validate_assignment`), but it introduced a regression
at the schema-validation level: round-tripping the written `material_instances.json`
through `MaterialInstanceSet.model_validate(data)` raised a `ValidationError` because
`"deterministic_evidence_based_descriptor_match"` was not in the `CandidateOrigin`
Literal.

Repair:
- `src/s8_stage3/contracts/material.py` — added
  `"deterministic_evidence_based_descriptor_match"` to the `CandidateOrigin` Literal
  and updated the `origin` field description to truthfully include this non-LLM
  deterministic evidence-based origin.
- `tests/test_s09_evidence_based_tier3.py` — extended
  `test_run_s09_evidence_based_metadata_is_truthful_not_llm` to round-trip the
  written `material_instances.json` through `MaterialInstanceSet.model_validate(...)`,
  and to assert
  `origin_values == ["deterministic_evidence_based_descriptor_match"]` and
  `source_mode_values == ["evidence_based_descriptor_match"]`.

Re-verified:
- `V1.0-qianduan-mainline/stage3_mechanism > python -m pytest tests -q` -> **162 passed, 3 warnings** (unchanged count; the new assertions were added to the existing test).
- `codex/v2_engine_tools_20260601 > python -m pytest tests -q` -> **34 passed**.
- Manual round-trip: `MaterialInstanceSet.model_validate(data)` passes;
  `n_instances=3`; `origin_values=['deterministic_evidence_based_descriptor_match']`;
  `source_mode_values=['evidence_based_descriptor_match']`.

Boundaries: no `paper/current/**`, no frozen evidence, no raw data, no
manifests/figures/builds, no dry-run result JSONs touched. v2 remains **HOLD**;
Phase C **not unlocked**.
