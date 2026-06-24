# Reproducibility floor vs autonomous loop — verification (2026-06-21)

**Hypothesis (falsifiable):** are the differences the Line-B MOBO+LLM loop tries to resolve
between candidates *smaller* than the fabrication reproducibility floor measured on Line-A
independent repeats? If yes, the loop is partly "optimizing noise" near the optimum — which
quantitatively explains the P4 honest null (prospective rounds did not beat the best; the
Pareto front did not expand).

## Inputs (all REAL, no fabrication)
- `V1.0-qianduan-mainline/stage1_optimization/campaign_memory/history_db_attapulgite.json`
  — 10 real attapulgite trials (each with measured `combined_score` and components, real
  per-pellet thickness, and the actual room-T it was measured at).
- `_new_data_analysis/calibration/repro_full_report.json` — Line-A LRS 7-repeat floor
  (`median |Δlog10 σ|`, `std(Ea_high)`, `std(Ea_low)`).

## Method
`combined_score = log10(σ) − 3.0·Ea_high − 0.5·ea_low_excess` (the loop's objective).
Floor on a candidate-vs-candidate `combined_score` difference, propagated from Line-A:
`floor = sqrt( dσ² + (3·dEa_high)² + (0.5·dExc)² )`, `dσ` = Line-A median |Δlog10 σ| between two
independent pellets, `dEa ≈ √2·std`.

## Result
- `combined_score` floor ≈ **0.26** (June standardized proxy) – **0.33** (all-repeats proxy).
- **2 / 9** non-best candidates sit within the loose floor of the campaign best
  (T5 gap 0.22, T7 gap 0.23; T8 gap 0.34 at the floor).
- Pure-σ cross-check: top-3 σ candidates span only **0.256 dex** ≈ tight floor → the loop
  cannot distinguish them by conductivity.
- Line-B internal evidence: pellet thickness 0.070–0.103 cm alone → 0.171 dex σ scatter;
  historical 0.022 cm parse bug once added ~0.6 dex; room-T 17–24 °C → only 0.02–0.04 dex.

## Honesty caveats
- Floor is a **biopolymer (LRS) proxy** for the attapulgite system (flagged); both tight and
  loose floors reported.
- Line-B has **no exact-repeat (R,N) points**, so the floor is not measured directly on
  attapulgite. Closing that needs 1–2 same-recipe attapulgite repeats (fold into the ongoing
  closed-loop extension — a measurement already planned, not new characterization).

## Run
```bash
python _new_data_analysis/repro_floor/floor_vs_loop.py
```
Outputs `floor_vs_loop_report.json` and `floor_vs_loop.png` next to the script.
