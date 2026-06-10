# Deprecated samples (figure_data consistency note)

This note records samples that were intentionally removed from the
figure-data tables in this folder, so that the figure-data layer stays
consistent with `../tables/final_benchmark_table.csv` (which already
excludes them). Kept here for provenance; do NOT silently re-add.

## 2026.4.25CS  (removed 2026-06-08)

- Original role in `wide_temperature_performance_summary.csv`:
  `LRS main validation` (thick film, thickness = 0.10 cm, Ea_high = 0.163 eV).
- Reason for deprecation: the author cross-checked the raw measurement
  records and found the workbook/raw data did not correspond reliably
  ("对应不上"); the sample was therefore discarded as an LRS validation
  data point.
- Action taken: row removed from `wide_temperature_performance_summary.csv`
  to eliminate the inconsistency where this sample appeared as an "LRS main
  validation" row in the performance summary while being absent from the
  curated benchmark table (`../tables/final_benchmark_table.csv`,
  `ea_benchmark_table.csv`).
- Manuscript handling: 2026.4.25CS is NOT used for any LRS performance or
  Ea claim. It is also excluded from the Ea-vs-thickness confounding figure
  to avoid relying on data flagged as unreliable. The thickness-confounding
  argument is made with the remaining valid samples (LRS thin films at
  0.02/0.022 cm vs starch/chitosan controls at 0.05/0.06 cm).
- Raw data: the raw EIS spectra under `data/新材料/2026.4.25CS/` are left
  untouched; only the curated figure-data row is removed.

Single canonical figure-data file is maintained (no parallel versions).
