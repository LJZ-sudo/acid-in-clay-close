# v2-R3 EIS Acquisition Checklist

This checklist intentionally does not claim CHI real-run readiness. Use the established CHI workflow and archive raw exports. The local CHI macro evidence status is recorded in `chi_eis_preflight_gate.json`.

- [ ] Sample ID matches the reserved BO v2 pattern.
- [ ] Preparation record includes R, N, acid mass, added-water mass, clay mass, thickness and area.
- [ ] Raw EIS export folder is append-only and hashable.
- [ ] Temperature sequence follows `measurement_sequence_template.csv` or records deviations explicitly.
- [ ] 273 K and 253 K anchors are collected.
- [ ] 233 K continuity anchor is collected if physically stable.
- [ ] Cold-tail points are marked exploratory unless repeat/QC supports stronger use.
- [ ] Manual Rb review queue is created for all main-window points.
- [ ] No result is imported into v2 history before QC and scoring.
