# Cooling-Resilient Pathway Continuity Descriptor — Definition

> Paper-facing mathematical specification of Pillar 2's central descriptor.
> Implementation lives in
> `V1.0-qianduan-mainline/stage0_measurement/modules/closure/closure_features.py`
> and `closure_schema.py`. The values reported in
> `pillar2_descriptor_qc/eis_qc_v2/*.csv` are exactly those produced by this code.

## 1. Why this descriptor exists

Standard proton-conductor benchmarking reports σ(25 °C) and a single
activation energy Eₐ. That collapses **two distinct physical regimes** that
are central to wide-temperature operation:

- a **high-temperature segment** (above any glass / freezing transition of
  the H₃PO₄ / water phase) where Grotthuss-like proton hopping dominates,
- a **cold-tail segment** (below the transition) where vehicular transport
  is suppressed and the conductivity often drops by 2 – 4 orders of
  magnitude.

A material that has a *low* high-segment Eₐ but a *collapsed* cold tail is
**not** cooling-resilient. The descriptor below is designed so that a
single scalar conclusion ("cooling-resilient" or not) cannot be claimed
without simultaneously controlling both segments and the geometry / QC
chain that produced them.

## 2. Per-sample feature vector

For every sample bundle (one biopolymer–clay membrane processed by
`closure_features.build_performance_card`) the descriptor records:

| field | symbol | unit | source code |
|---|---|---|---|
| room-temperature conductivity | σ_RT | S · cm⁻¹ | `PerformanceCard.sigma_RT_S_per_cm` (point nearest 25 °C) |
| peak conductivity + its temperature | σ_max, T_at_max | S · cm⁻¹, °C | `sigma_max_S_per_cm`, `T_at_sigma_max_C` |
| coldest measured temperature + σ there | T_min, σ(T_min) | °C, S · cm⁻¹ | `T_min_measured_C`, `sigma_at_T_min_S_per_cm` |
| number of Arrhenius segments | n_seg | int | `n_segments` (AICc-selected, capped at 3) |
| segment transition temperatures | {T_k} | °C | `transition_temps_C` |
| per-segment activation energies | Eₐ⁽ᵢ⁾ | eV | `segments[i].Ea_eV` |
| per-segment T-range and point count | [T_low⁽ᵢ⁾, T_high⁽ᵢ⁾], n⁽ᵢ⁾ | °C, count | `segments[i]` |
| Arrhenius fit confidence flag | conf | str | `arrhenius_confidence` |
| transport-model label | model | str | `transport_model` (e.g. `multi_segment_arrhenius`) |

The segmented Arrhenius fit itself follows

    σ(T) · T = A_i · exp( -Eₐ⁽ᵢ⁾ / k_B T )   for T ∈ [T_low⁽ᵢ⁾, T_high⁽ᵢ⁾]

with the segment cuts {T_k} chosen by AICc on the joint ln(σT)-vs-1/T plot
and a hard cap n_seg ≤ 3 (see `modules/analysis/algorithms/arrhenius.py`).

## 3. QC gate (what makes a sample "report-able")

A sample's descriptor only enters Main Text / Supplement / Exploratory
sections after passing the three-level QC implemented in
`pillar2_descriptor_qc/eis_qc_v2/*`:

1. **Geometry QC** (`geometry_audit_v2.csv`)
   - thickness, area, and geometric σ_factor are all measured;
   - any disagreement between workbook-header values and Stage0-recorded
     values is flagged (`geometry_conflict = True` → sample retained only
     with explicit caveat; cf. `2026.5.9CS`).

2. **Temperature-sequence QC** (`temperature_sequence_audit_v2.csv`)
   - cooling/heating loops are checked for monotonicity, hysteresis, and
     filename-vs-timestamp ordering (`sequence` flag).

3. **R_b QC** (`selected_rb_qc_v2.csv`, 62 KB)
   - For every (sample, temperature) point we keep BOTH the auto Rb
     (KK-RB software fit) AND a manual Rb (human-annotated semi-circle
     intersection on the Nyquist plot), then accept the point only when
     |Rb_auto − Rb_manual| / Rb_manual ≤ tolerance, separately tracked
     for the **main window** (the temperature span used for the
     high-segment Eₐ) and the **cold tail** (≤ 233 K).

`eis_qc_v2_summary.md` records the gate verdicts per sample and per claim
band (Main / Supplement / Exploratory).

## 4. The descriptor's claim bands

The descriptor is partitioned into **three claim bands** with explicit
publication consequences (see `eis_qc_v2_summary.md::Claim Gate`):

| band | temperature window | QC requirement | manuscript use |
|---|---|---|---|
| **Main text** | high segment + σ(273 K) + σ(253 K) anchors | manual Rb agreement on every point | quantitative Eₐ + σ values |
| **Supplement** | 233 K continuity anchor + representative Nyquist | manual Rb agreement; explicit annotation | qualitative continuity claim |
| **Exploratory** | cold-tail points (T < 233 K) where auto / manual Rb disagree or segment instability appears | retained but flagged | discussion only; never as Main quantitative claim |

This is the operational definition of **"cooling-resilient"**: a sample's
descriptor is allowed to enter the Main-text band only if the high-segment
Eₐ remains low **and** the 273 K + 253 K conductivity anchors retain
their manual-Rb-validated value through the cooling cycle. Failure at
either anchor demotes the claim to Supplement (continuity-qualified) or
Exploratory (no quantitative claim).

## 5. LRS = positive validation, CHITO = boundary validation

The descriptor was designed and tuned against acid-in-clay sepiolite
(S8 mother system, Pillar 1 evidence). Its transfer to the
biopolymer-clay family is validated in two complementary modes,
intentionally:

- **LRS (PVA / attapulgite / H₃PO₄ thin-film)** — positive band.
  - `THIS-5.9CS`: Eₐ_high = 0.037 eV (243–293 K), σ(273 K) = 1.85 × 10⁻² S/cm,
    σ(253 K) = 1.56 × 10⁻² S/cm; passes Main + Supplement QC; lands
    record-level / comparable-to-lowest-Eₐ benchmark band (no "world
    record" wording; see `final_benchmark_table.csv` claim_boundary
    column).
  - `THIS-4.29CS`: Eₐ_high = 0.042 eV (241–298 K), σ(273 K) ≈ 1.84 × 10⁻²
    S/cm; passes Main + Supplement; supports the LRS replicate claim.

- **CHITO (chitosan / attapulgite / H₃PO₄)** — boundary band.
  - The descriptor's QC gate is **expected to lose** Main-text eligibility
    on at least one anchor (typically cold-tail σ collapse and/or
    manual-Rb disagreement). This is the *intended* role of CHITO in the
    paper: it demonstrates that the descriptor is not vacuous — it can
    distinguish a cooling-resilient member of the biopolymer–clay
    family (LRS) from a non-resilient one (CHITO) under identical
    geometry / QC treatment.

This pair (LRS positive + CHITO boundary) is what makes the descriptor a
**descriptor** rather than a metric: it has discriminative power, not just
descriptive power.

## 6. What this descriptor does NOT claim

The descriptor is descriptive, not mechanistic:

- It does **not** assert a specific proton-transport mechanism (Grotthuss
  vs vehicular vs frozen-water hydronium). Mechanism inference is Stage 3's
  job (see `stage3_mechanism/`) and goes through a separate claim-audit
  pipeline (`s14_claim_auditor`).
- It does **not** claim "discovery of LRS as a new material class". LRS is
  validated within the biopolymer–clay family as a cooling-resilient
  member; the family itself was identified by Pillar 1's transfer agent.
- It does **not** assert "world-record" performance. The `final_benchmark_
  table.csv::claim_boundary` column hard-codes the allowed wording:
  *"record-level / comparable to lowest reported barriers"* with
  explicit caveat that conditions (humidity, geometry, electrode) must
  match before any superiority claim.

## 7. Reproducing the descriptor from scratch

Given a fresh batch of CHI-format EIS files for a new sample
`<sample_id>`:

```bash
cd V1.0-qianduan-mainline
python -m code.stage0_processing.process_new_materials_stage0 \
       --sample <sample_id> --input data/新材料/<sample_id>/
python -m stage0_measurement.run_closure_offline --sample <sample_id>
# then re-export the pillar2 QC sidecars (eis_qc_v2_*) as documented in
# three_pillars/pillar2_descriptor_qc/eis_qc_v2/eis_qc_v2_summary.md
```

The descriptor is fully deterministic given the same bundle + the same
algorithm versions (KK / R_b / Arrhenius). LLM is never consulted in the
descriptor calculation; LLM only sees the trimmed
`build_prompt_context(...)` summary downstream.
