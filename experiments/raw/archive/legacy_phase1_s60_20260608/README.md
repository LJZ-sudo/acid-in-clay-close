# Legacy Phase1 / S60+S8 archive (snapshot 2026-06-08)

This directory contains three subfolders that were live in an earlier
`front_half_v2` / Phase 1 research cycle but have **zero current code
consumers** as of 2026-06-08. They are archived here, NOT deleted, so the
provenance chain of the older S60-series and the early S8 R/N/L/S parameter
work remains auditable.

## Contents

### `phase1_results/` (58 files, 12.4 MB, dated 2026-03-23)

`<sample_id>_analysis_result.json` files for S60-* (15 samples) and S8-3-*
(43 samples). These were produced by the historical Phase 1 KK+Arrhenius
pipeline (`front_half_v2.tools.enrich_phase1_metadata` plus the older S8 batch
processors under `code/stage*_processing/`).

The current `backend_api/routers/data.py` `/api/data/experiments` endpoint
reads from `output/phase1_results/` (a different runtime path that is not
populated in the current mainline), so this directory has been orphaned since
the V1.0 reorganization in May 2026. None of stage0/1/2/3_* nor the current
backend imports this path.

### `canonical_inputs/` (58 files, 1.91 MB, dated 2026-03-29)

`<sample_id>_canonical_input.json` files for the same S60-* and S8-3-* samples,
produced by `extract_canonical_phase1_input` from the corresponding
`phase1_results/` JSONs (the v1.1 export, without `kk_validation` /
`drt_analysis`). Each canonical input cross-references
`front_half_v2/data/phase1_material_lexicon.json` (see `knowledge_base/`
below). Zero runtime consumers in the current mainline.

### `knowledge_base/phase1_material_lexicon.json` (2 KB, dated 2026-03-23)

Material lexicon defining R/N/L/S parameters used by the older Phase 1
pipeline. Referenced as a string by every `canonical_inputs/*.json` file in
this archive, but no longer imported by any Python module in the current
mainline.

## Why archived rather than deleted

- These three folders document the **previous research cycle** (S60 system,
  early S8 R/N/L/S preprocessing). Although the current paper focuses on the
  attapulgite-AiCE mother system and the LRS/Chitosan/Starch transfer family,
  the S60 + early-S8 work is part of the project's chain of evidence and
  should remain retrievable for reviewer questions about provenance.

- All three folders together are only ~14 MB / 117 files. The repo size cost
  of keeping them archived is negligible.

## Recovery

If a future analysis needs to consume these as live inputs, move the desired
subfolder back to `data/<name>/` and verify that the consumer code still
matches the schema (the Phase 1 schema is unchanged since 2026-03-29 but the
runtime pipelines have since moved to `stage0_measurement/` + `stage2_statistics/`).

## Related references

- `V1.0-qianduan-mainline/data/MANIFEST.md` — top-level data manifest
- `V1.0-qianduan-mainline/data/README.md` — historical `front_half_v2`
  conventions doc
- `V1.0-qianduan-mainline/data/raw_eis/S60/` and `data/raw_eis/S8/` —
  source CHI files (2020-2021) that this archive's `phase1_results/` was
  derived from
