# v2 Engine Tools — First Batch Implementation Report

- **Date:** 2026-06-01 (relocated to `three_pillars/` on 2026-06-05)
- **Scope:** v2 first batch of integrity/validation tools.
  Original plan documents (`codex/v2_submission_and_upgrade_plan_20260601/V2_MASTER_PLAN.md`
  and `v2_minimal_implementation_plan.md`) have been retired with the rest of `codex/`.
- **Location (only place touched):** `three_pillars/pillar3_eis_in_the_loop/v2_engine_tools/`
- **Verdict context (unchanged):** current small paper **GO**; v2 claims **HOLD**;
  EIS is **bounded QC / supporting evidence only**, never mechanism proof.

These tools are integrity/validation/reporting helpers. They are **default
read-only**, **default-safe** (HOLD / DISABLED), and **emit no scientific result
or claim**. They do not, and cannot by design, upgrade any v2 claim or enable
real CHI automation.

---

## 1. Files delivered

### Tools (10 requested + 1 shared helper)
| # | File | Purpose | Default posture |
|---|------|---------|-----------------|
| 1 | `build_round_hash_manifest.py` | SHA-256 + roll-up manifest over the 9 required round artifacts; completeness verdict | read-only (writes only with `--write`, into `out/`) |
| 2 | `verify_round_hash_manifest.py` | Recompute & compare vs manifest; detect TAMPERED / MISSING / INCOMPLETE | read-only |
| 3 | `verify_approval_binding.py` | Recompute roll-up over the 4 bound inputs, compare to `bound_input_sha256` in `human_approval.md` (MATCH/MISMATCH/…). Signing stays a human action | read-only |
| 4 | `verify_append_only_chain.py` | Verify raw-EIS intake hash chain: OK / BROKEN_CHAIN / OVERWRITE_DETECTED / MISSING_PARENT / EMPTY | read-only, never writes raw EIS |
| 5 | `validate_manual_rb_qc.py` | Validate manual Rb QC CSV vs schema (columns, units, ranges, enums, main-text conditional rule) | read-only |
| 6 | `manual_rb_qc_schema.json` | Schema for a manual Rb QC row (units encoded in column names) | static schema |
| 7 | `validate_score_layers.py` | Enforce 4-layer separation; **reject forbidden overclaim wording** and publication fields | read-only |
| 8 | `v2_claim_unlock_check.py` | 8-condition unlock chain; **HOLD by default and on any missing/non-true input** | default **HOLD** |
| 9 | `summarize_kk_residuals.py` | Per-point KK residual vs threshold; flags bounded-caveat; states EIS is not mechanism proof | read-only |
| 10 | `check_chi_automation_preconditions.py` | CHI readiness check; **DISABLED by default**; never enables automation | default **DISABLED** |
| – | `v2tools_common.py` | Shared hashing, forbidden-wording list, `out/`-only write guard, protected-tree guard | helper |

### Tests & fixtures
- `tests/test_v2_engine_tools.py` — 27 tests covering every tool (happy path + failure modes).
- `tests/conftest.py` — puts the tools dir on `sys.path`; exposes `FIXTURES`.
- `tests/fixtures/` — all `synthetic_not_real_evidence` (see §4).
- `tests/fixtures/make_hashed_fixtures.py` — regenerates hash-dependent fixtures.
- `out/.gitkeep` — the **only** writable output location.

---

## 2. Test results

Command (run from `three_pillars/pillar3_eis_in_the_loop/v2_engine_tools/`):

```
python -m pytest tests/ -v
```

Result: **27 passed in 0.12s** (Python 3.12.7, pytest 8.4.1).

Coverage highlights:
- Round manifest: complete / incomplete / OK / **TAMPERED** / **MISSING**.
- Approval binding: **MATCH** / **MISMATCH** (input mutated post-sign) / **MISSING_APPROVAL**.
- Append-only chain: **OK** / **BROKEN_CHAIN** / **OVERWRITE_DETECTED** / **MISSING_PARENT**.
- Rb QC: valid pass / invalid (bad temperature, negative Rb, zero thickness, bad enum, empty reviewer, missing KK on main-text tier).
- Score validator: clean pass / **rejects** `claim` field + forbidden wording / missing-field failure.
- Claim unlock: **HOLD** with no input, **HOLD** on partial, **HOLD** on non-boolean values, ALLOW only when all 8 explicitly `true` (synthetic).
- KK summary: numeric (1 above-threshold flagged) / legacy (no numeric KK → bounded caveat).
- CHI: **DISABLED** with no dir, **DISABLED** on `NEEDS_REFERENCE_MACRO`, `PRECONDITIONS_MET_SYNTHETIC` only on full synthetic set — and even then `enables_chi_automation = false`.
- Boundary guarantee test asserts protected prefixes are declared.

Linter: **no errors** (`ReadLints` over the tool directory).

---

## 3. Did this touch frozen / protected directories?

**No.**
- `three_pillars/` round templates and evidence — **not touched** (read or write).
- `V1.0-qianduan-mainline/` — **not touched** (read or write).
- All code, tests, fixtures, and the one runtime output (`out/`) live exclusively under
  `three_pillars/pillar3_eis_in_the_loop/v2_engine_tools/`.
- `v2tools_common.py` hard-codes `PROTECTED_PREFIXES = ("three_pillars", "V1.0-qianduan-mainline")`
  and refuses any write that resolves outside `out/` or into a protected tree.
- CLI smoke test confirmed `--write` output landed **only** in `out/` (`unlock_smoke.json`,
  `chi_smoke.json`); these were removed after verification.

---

## 4. Were any result-like artifacts generated?

**No real result-like artifacts.**
- Every tool's JSON output carries `"result_like_artifact": false`.
- No real measurement, approval, raw EIS, QC record, score, or claim was produced.
- All fixtures are explicitly **synthetic** — marked `synthetic_not_real_evidence`
  in **both filename and content** — and live in `tests/fixtures/`:
  - `round_valid_synthetic_not_real_evidence/` (9 required files; approval correctly hash-bound)
  - `append_only_{clean,broken,overwrite}_synthetic_not_real_evidence/`
  - `manual_rb_qc_{valid,invalid}_synthetic_not_real_evidence.csv`
  - `score_{clean,forbidden}_synthetic_not_real_evidence.json`
  - `kk_bundle_{numeric,legacy}_synthetic_not_real_evidence.json`
  - `unlock_{all_true,partial}_synthetic_not_real_evidence.json`
  - `chi_full_evidence_synthetic_not_real_evidence/`, `chi_needs_macro_synthetic_not_real_evidence/`
- `check_chi_automation_preconditions.py`'s best case is `PRECONDITIONS_MET_SYNTHETIC`,
  which explicitly does **not** enable real CHI automation; manual EIS remains the only allowed route.

---

## 5. Forbidden-wording enforcement (score validator)

`validate_score_layers.py` (via `v2tools_common.FORBIDDEN_WORDING`) rejects, among others:
`global optimum`, `world record`, `lowest ever`, `global best`,
`v2 pareto achieved` / `pareto front achieved`, `bo+llm discovered lrs` / `llm discovered`,
`eis proves mechanism`, `equivalent circuit established`, `optimization completed`,
`mobo completed`, `openalex validated`. It also rejects any `claim` / `publication` /
`conclusion` field embedded in a score record. Verified by `test_score_forbidden`.

---

## 6. How to run

```
cd three_pillars/pillar3_eis_in_the_loop/v2_engine_tools
python -m pytest tests/ -v                 # 27 tests
python tests/fixtures/make_hashed_fixtures.py   # regenerate hashed fixtures (idempotent)

# example read-only invocations
python build_round_hash_manifest.py tests/fixtures/round_valid_synthetic_not_real_evidence
python v2_claim_unlock_check.py             # -> HOLD (no input)
python check_chi_automation_preconditions.py  # -> DISABLED (no dir)
```

---

## 7. Boundaries reaffirmed

- These tools **do not** unlock v2 claims, **do not** enable CHI automation, and **do not**
  assert any mechanism or performance result.
- v2 remains **HOLD** until real signed/hash-bound approvals, real append-only raw EIS,
  Stage0 gate pass, accepted manual Rb QC, score gate, reviewed history import, Stage3 rerun
  claim gate, and a new frozen manifest + pre-submission pass are all satisfied with real data.
- Current small paper status is unchanged: **GO**.
