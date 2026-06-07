# Data Manifest

Current status date: 2026-05-18

Data directory policy:

- `ao/`: current AiCE AO input folders used by Stage0 offline processing. Treat as raw/imported experiment input; do not delete.
- `ao.zip`: historical packaged copy of AO data. Keep for traceability.
- `raw_eis/`: historical/raw EIS data.
- `新材料/`: transfer-validation material data.
- `canonical_inputs/`, `knowledge_base/`, `literature/`, `phase1_results/`: legacy or support data retained for traceability and older analysis paths.
- `材料数据说明.xlsx`: original material description spreadsheet; treat as raw reference.

Current executable Stage0 processing reads from `data/ao/<folder>` and writes to `output/ao_stage0_results/<folder>` plus the sample bus under `output/stage0_results/<sample_id>`.

The older `data/README.md` describes historical `front_half_v2` data conventions. Use this MANIFEST for the current mainline directory classification.
