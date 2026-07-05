# Benchmark Condition Audit

Status: `PASS_CONTEXTUAL_ONLY`

External low-Ea entries are useful contextual anchors, but current evidence does not support direct absolute ranking across material classes, humidity, geometry and temperature windows.

## Audited Entries

| entry | comparability | direct rank | verified condition | manuscript use | gap |
| --- | --- | --- | --- | --- | --- |
| `THIS-5.9CS` | direct_internal_main_text_candidate | no | This work; LRS/PVA/attapulgite/H3PO4 thin film; high-segment 243-293 K; 273/253 K anchors; L=0.022 cm by preparation/back-calculation decision. | main this-work low-barrier branch with explicit EIS gate caveats | needs independent repeats, leakage exclusion, and advanced impedance/orthogonal characterization for stronger journal target |
| `THIS-4.29CS` | direct_internal_supporting_main_text_candidate | no | This work; independent LRS/PVA/attapulgite/H3PO4 thin-film repeat; high-segment 241-298 K; 273/253 K anchors. | supporting internal repeat for the LRS low-barrier branch | low-temperature tail remains exploratory |
| `LIT-POP-2020` | external_low_ea_context_only | no | Porous organic polymer / PVDF mixed-matrix membrane; 1S3MP conductivity 2.13e-2 S cm-1 at 80 C and 90% RH; reported Ea 0.039 eV. | use as low-Ea membrane reference under clearly different 80 C / 90% RH conditions | requires full-paper extraction of fitting window, RH protocol and membrane geometry before numeric ranking |
| `LIT-MFM300CR-2022` | external_framework_barrier_anchor_only | no | MFM-300(Cr).SO4(H3O)2 framework conductor; reported Ea 0.04 eV; >1e-2 S cm-1 between 25 and 80 C, with high-RH cycling and mechanism support from diffraction/QENS/MD. | use as framework low-barrier anchor and mechanism/QENS contrast, not direct membrane ranking | different material class, geometry, humidity and mechanism evidence level |
| `LIT-AICE-2022` | closest_mother_system_context | no | Sepiolite-phosphoric acid AiCE thin-film electrolyte; reported 15 mS cm-1 at 25 C and 0.023 mS cm-1 at -82 C; R=0.3 in the preprint/full-text excerpt. | use as mother-system benchmark for acid-in-clay wide-temperature conductivity | different clay, polymer scaffold and battery-electrolyte context; direct superiority claim not allowed |

## Required Before Stronger Claim

- full-condition extraction for each external benchmark
- matched temperature/RH/geometric comparison table
- additional independent LRS repeats
- leakage exclusion and advanced impedance/orthogonal characterization

## Sources

- `THIS-5.9CS`: RETIRED paper/current/qc/eis_submission_gate/eis_submission_gate_report.json
  (replacement evidence: three_pillars/pillar2_descriptor_qc/eis_qc_v2/)
- `THIS-4.29CS`: RETIRED paper/current/qc/eis_submission_gate/eis_submission_gate_report.json
  (replacement evidence: three_pillars/pillar2_descriptor_qc/eis_qc_v2/)
- `LIT-POP-2020`: https://pubs.rsc.org/en/content/articlelanding/2020/ta/c9ta06807d
- `LIT-MFM300CR-2022`: https://pubs.acs.org/doi/10.1021/jacs.2c04900
- `LIT-AICE-2022`: https://pubmed.ncbi.nlm.nih.gov/35443084/
