# Stage2 Preprocessing

Convert Stage0 results to Stage2 input CSV with physically meaningful EIS features.

## Quick Start

```bash
# Run full pipeline (extract EIS + convert)
python run_full_pipeline.py

# Output: ../../stage2_statistics/data/s8_input.csv (current S8: 1081 rows × 34 columns)
```

## Key Improvement (2026-04-12)

**Problem**: Raw EIS data has narrow frequency range (0-55 Hz), cannot form standard Nyquist semicircles.

**Solution**: Extract meaningful resistance features instead of misleading "semicircle" metrics:
- `R_high_freq_ohm`: High-frequency resistance (≈55 Hz, grain resistance)
- `R_low_freq_ohm`: Low-frequency resistance (≈5-10 Hz, total resistance)
- `delta_R_ohm`: Interface/grain boundary contribution (R_low - R_high)
- `R_ratio`: Resistance ratio (R_low / R_high), indicates interface effect strength

## Files

- `extract_s8_eis_features.py` - Extract resistance features from raw CHI files
- `batch_extract_eis_features.py` - Batch extract all samples
- `convert_stage0_to_stage2.py` - Convert Stage0 to Stage2 CSV
- `run_full_pipeline.py` - One-click full pipeline

## Data Flow

```
Stage0 Results (output/stage0_results/)
├── s8_sample_rn.json           → R, N
├── aggregated_results.json     → T, sigma, R²
├── arrhenius_analysis.json     → Ea, sigma0, T_break
└── eis_features.json (new)     → R_high, R_low, delta_R, R_ratio

↓

Stage2 Input (stage2_statistics/data/s8_input.csv)
- current S8 baseline: 1081 rows, 40 samples, 34 columns
- All points have valid EIS data (100%)
- R_ratio avg 6.22 (significant interface effects)
```

## Output Columns

**Sample**: sample_id, scan_dir, excel_id, R, N, L_cm, S_cm2

**Temperature**: T, T_C, inv_T_1000

**Conductivity**: sigma, ln_sigma, R2, rb_ohm

**Arrhenius**: Ea, sigma0, ln_sigma0, T_break

**EIS (new)**:
- `data_valid`: Data quality flag
- `R_high_freq_ohm`: High-freq resistance (grain)
- `R_low_freq_ohm`: Low-freq resistance (total)
- `delta_R_ohm`: Interface contribution
- `R_ratio`: Interface effect strength (avg 6.2)
- `arc_diameter_ohm`: Zreal range (reference)
- `median_zimag_ohm`: Zimag median (reference)
- `arc_visible`: heuristic Nyquist arc flag
- `semicircle_visible`: alias for arc visibility
- `semicircle_quality`: heuristic shape score
- `characteristic_frequency`: -Zimag peak frequency
- `peak_neg_zimag_ohm`, `nyquist_*`: morphology helper metrics
- `T_arc`: sample-level heuristic arc emergence temperature

**Manifests**:
- `s8_input.manifest.json`: direct conversion manifest
- `s8_input.full_pipeline_manifest.json`: one-click pipeline manifest

## Data Quality

- 1081/1081 valid points (100%)
- R_ratio range: 2.46 - 8.05 (mean 6.22)
- 80.8% points have R_ratio > 5 (significant interface effects)
- delta_R decreases with temperature (physically expected)

`SOLUTION_PROPOSAL.md` and `EIS_MORPHOLOGY_FINAL_REPORT.md` are historical technical reports. Use this README and the generated manifests as the current run guide.
