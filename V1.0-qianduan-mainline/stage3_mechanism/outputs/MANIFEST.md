# Stage3 Outputs Manifest

Current status date: 2026-06-07

This directory is the canonical Stage3 run-output root. After the 2026-06-07
Tier-A/B cleanup, mixed-tier polo publication run, and the OpenRouter v2
re-run, four anchored snapshots are retained:

- **`verification/20260607_openrouter_publication_v2/` (publication-grade, CURRENT AUTHORITATIVE)**:
  full 13-step chain run on 2026-06-07 with `literature_mode=hybrid`,
  `llm_mode=live`, and OpenRouter as the LLM provider. Models:
  `PREMIUM=openai/gpt-5.4` (s04/s06/s06b), `STANDARD=openai/gpt-5.2` (s07),
  `CHEAP=openai/gpt-5.2` (s05_lit/s08_sum). Used the current stage2 seed
  `4edbd136...`. **5 min 37 s wallclock (6.1× faster than V1 polo run), 13/13
  LLM calls succeeded zero-fail, 54,971 total tokens (~$0.35 / ¥2.5)**.
  Top-1 / Top-2 candidates bit-identical to both the V1 polo run and the OLD
  5/26 historical run, proving cross-provider robustness of the core finding.
  **S13/S14 re-audited on 2026-06-07T15:51Z** (post-hoc, no LLM calls) after
  restoring the lost timing anchor (see CHANGELOG `[2026-06-07d]`) and
  promoting `final_audit=True`. Final claim ladder: 4 PASS
  (`closed_loop_source_system`, `mechanism_discovery`,
  `llm_transfer_candidate`, `prospective_validation` with `n_prospective_links=2`)
  + 1 TODO (`retrospective_validation`, expected-empty given all bindings are
  prospective). See `CHANGELOG.md [2026-06-07c]` and `[2026-06-07d]`.

- **`verification/20260607_mixed_tier_publication/` (V1, polo mixed tier, retained as cross-validation evidence)**:
  V1 publication run via polo gateway (`literature_mode=hybrid`,
  `llm_mode=live`). Mixed-tier routing: `PREMIUM=gpt-5.4` (s04/s06/s06b),
  `STANDARD=gpt-5.2` (s07), `CHEAP=deepseek-v4-pro` (s05_lit/s08_sum).
  34 min 11 s wallclock, 79,119 total tokens, 9/23 LLM calls failed at the
  polo `deepseek-v4-pro` CHEAP tier (all recovered by gateway retry).
  Superseded by the V2 OpenRouter run above, retained as cross-validation
  evidence (Top-1 / Top-2 candidates match V2 exactly). See
  `CHANGELOG.md [2026-06-07b]` for full rationale.

- `verification/20260526_final_audit_cacheoff_full/` (historical baseline, all-deepseek):
  full 13-step chain run in `literature_mode=hybrid` with all 3 tiers
  configured as `deepseek-v4-pro`. Recorded stage2 seed hash `fe7f48cc...`
  (prior generation). Retained as the historical reference that the
  publication run was validated against.

- `verification/20260607_post_cleanup_smoke/` (mock-mode regression baseline, 0.48 MB / 37 files):
  generated against the current seed `4edbd136...` with mock LLM + mock
  literature + cache disabled. Top-3 candidates and ranking robustness are
  bit-identical to the prior `stage3_current_real_mock_20260518_215842/`
  baseline (now removed), confirming the Tier-A/B cleanup did not perturb
  pipeline behavior.

Output directory policy:

- `stage3/`: default destination placeholder for a new Stage3 run. Empty
  besides `README.md`. Reproducible runs should prefer an explicit dated
  `--output-dir`.

For new runs:

```powershell
$env:PYTHONPATH='stage3_mechanism/src'
python -m s8_stage3.orchestrator.run_stage3 --mode real --stage2-output-dir stage2_statistics\exports --output-dir stage3_mechanism\outputs\verification\<new-run-name>
```

Use `run_manifest.json` inside each generated output directory to verify the
Stage2 input directory, Stage2 seed hash, selected steps, output directory,
and strict/legacy input mode.
