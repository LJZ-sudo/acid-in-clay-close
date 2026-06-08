# Data Manifest

Current status date: 2026-06-08

## Live (active runtime consumers)

- `ao/`: current AiCE AO input folders used by Stage0 offline processing. Treat as raw/imported experiment input; do not delete.
- `ao.zip`: historical packaged copy of AO data. Keep for traceability.
- `新材料/`: transfer-validation material data. Source for the 7 prospective LRS / Chitosan / Starch experiments measured on 2026-05-09 (Pillar 1 evidence).
- `literature/`: human-curated initial reference library (22 PDFs, 2026-03-24). Live drop target for `backend_api/routers/evidence_jobs.py` `/literature/upload` endpoint. PDFs themselves are gitignored (see V1.0-qianduan-mainline/.gitignore line 25).
- `raw_eis/`: historical raw EIS CHI files. `raw_eis/S8/` is referenced by `code/shared/paths.py:RAW_EIS_S8` and the legacy S8 reprocessing scripts under `code/stage*_processing/`; remaining S-series (S6, S13–S16, S60, S95–S97) are 2020–2021 measurements kept for cross-system traceability but have no current code consumers.
- `材料数据说明.xlsx`: original material description spreadsheet; treat as raw reference.

## Archived (no current code consumers, kept for provenance)

- `archive/legacy_phase1_s60_20260608/`: snapshot of the older `front_half_v2` Phase 1 pipeline outputs. Contains:
  - `phase1_results/` (58 files): `<sample_id>_analysis_result.json` for S60-* and S8-3-* samples produced by the historical Phase 1 KK+Arrhenius pipeline.
  - `canonical_inputs/` (58 files): `<sample_id>_canonical_input.json` for the same samples.
  - `knowledge_base/phase1_material_lexicon.json`: R/N/L/S material lexicon used by the older Phase 1 pipeline.
  See the archive's own `README.md` for the full rationale and recovery instructions.

## Runtime path

Current executable Stage0 processing reads from `data/ao/<folder>` and writes to `output/ao_stage0_results/<folder>` plus the sample bus under `output/stage0_results/<sample_id>`. `backend_api/routers/data.py` reads experiment results from `output/phase1_results/` (note: separate path from the archived `data/archive/legacy_phase1_s60_20260608/phase1_results/`).

The older `data/README.md` describes historical `front_half_v2` data conventions. Use this MANIFEST for the current mainline directory classification.
