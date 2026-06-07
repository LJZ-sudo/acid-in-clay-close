# Stage0/EIS QC v2

Status: `PASS_STAGE0_EIS_QC_V2_SUBMISSION_READY_WITH_BOUNDED_CAVEATS`

This is a manuscript-upgrade QC sidecar. It does not overwrite raw EIS files, Stage0 outputs, or the frozen manuscript figures.

## Outputs

- `selected_rb_qc_v2`: `three_pillars/pillar2_descriptor_qc/eis_qc_v2/selected_rb_qc_v2.csv`
- `geometry_audit_v2`: `three_pillars/pillar2_descriptor_qc/eis_qc_v2/geometry_audit_v2.csv`
- `temperature_sequence_audit_v2`: `three_pillars/pillar2_descriptor_qc/eis_qc_v2/temperature_sequence_audit_v2.csv`
- `representative_nyquist_index_v2`: `three_pillars/pillar2_descriptor_qc/eis_qc_v2/representative_nyquist_index_v2.csv`
- `sample_qc_summary_v2`: `three_pillars/pillar2_descriptor_qc/eis_qc_v2/sample_qc_summary_v2.csv`
- `stage0_eis_qc_diagnostics_v2`: `three_pillars/pillar2_descriptor_qc/eis_qc_v2/stage0_eis_qc_diagnostics_v2.csv`
- `stage0_eis_qc_diagnostics_v2_json`: `three_pillars/pillar2_descriptor_qc/eis_qc_v2/stage0_eis_qc_diagnostics_v2.json`

## Sample Summary

| sample | points | manual points | main-window points | main-window median | cold-tail max | sequence | geometry conflict |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `2026.4.25CS` | 37 | 35 | 0 |  |  | nonmonotonic_or_filename_sorted | False |
| `2026.4.27CS` | 33 | 33 | 0 |  |  | nonmonotonic_or_filename_sorted | False |
| `2026.4.28CS` | 34 | 34 | 0 |  |  | nonmonotonic_or_filename_sorted | False |
| `2026.4.29CS` | 34 | 34 | 17 | 13.12 | 49.6 | nonmonotonic_or_filename_sorted | False |
| `2026.4.30CS` | 27 | 27 | 0 |  |  | nonmonotonic_or_filename_sorted | False |
| `2026.5.1CS` | 27 | 27 | 0 |  |  | nonmonotonic_or_filename_sorted | False |
| `2026.5.9CS` | 35 | 34 | 18 | 10.77 | 96.65 | nonmonotonic_or_filename_sorted | True |

## Submission Diagnostics

- Hard failures: `[]`
- Readiness checks: `{'stage0_samples_present': True, 'temperature_points_present': True, 'lrs_main_samples_present': True, 'lrs_main_samples_have_manual_main_window_points': True, 'main_window_conductivity_available': True, 'representative_nyquist_exports_present': True}`
- Warning counts: `{'sequence_warning_count': 7, 'geometry_conflict_count': 1, 'main_window_auto_selected_point_count': 1, 'representative_nyquist_missing_export_count': 0}`

## Claim Gate

- Main text: LRS high-segment window and 273/253 K conductivity anchors.
- Supplement: 233 K continuity anchors and representative Nyquist/Rb annotation.
- Exploratory: cold-tail points where auto/manual Rb disagreement and segment instability increase.
- `2026.5.9CS` retains an explicit geometry-conflict flag for the workbook-header inconsistency.
