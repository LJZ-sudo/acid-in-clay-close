# SI Note 4: Phase Transition Detection & Adaptive Sampling Algorithm

> **Source code**: `auto_control/integrated_temp_chi_controller.py`, `auto_control/integrated_workflow.py`

## 1. Overview

The measurement agent employs real-time phase transition detection to automatically switch between coarse (3 K) and fine (1 K) sampling modes. This ensures dense data collection in scientifically critical temperature regions while maintaining efficiency elsewhere.

## 2. Phase Jump Score Calculation

For each EIS measurement at temperature T, the agent computes a Phase Jump Score ∈ [0, 1]:

### Step 1: Phase Angle Computation
$$\phi_i = \arctan\left(\frac{Z''_i}{Z'_i}\right) \quad \text{for each frequency point } i$$

### Step 2: Maximum Adjacent Phase Difference
$$\Delta\phi_{\max} = \max_i |\phi_{i+1} - \phi_i|$$

### Step 3: Score Mapping (piecewise linear)

| Condition | Phase Jump Score |
|-----------|-----------------|
| Δφ_max ≥ 2 × threshold | 1.0 |
| Δφ_max ≥ threshold | 0.5 + 0.5 × (Δφ_max − threshold) / threshold |
| Δφ_max ≥ 0.5 × threshold | 0.2 + 0.3 × (Δφ_max − 0.5×threshold) / (0.5×threshold) |
| Δφ_max < 0.5 × threshold | 0.2 × Δφ_max / (0.5×threshold) |

Default threshold: **30 degrees**.

### Step 4: Additional Indicators
- **Fitting method transition**: If Rb fitting switches from linear to arc fit → score bonus +0.2
- **Conductivity change**: If |Δlog₁₀(σ)| > 0.1 between consecutive measurements → score bonus +0.2
- **Boolean phase jump detector**: If triggered, ensure score ≥ 0.6

## 3. Adaptive Sampling Decision

```
IF Phase_Jump_Score > 0.2 (threshold from Fig S1):
    → TRIGGER phase transition mode
    → Switch from Coarse Step (3K) to Fine Step (1K)
    → Optional: BACKTRACK to re-measure transition onset

IF Phase_Jump_Score drops below 0.1 for 3 consecutive measurements:
    → RESUME Coarse Step (3K)
```

## 4. Conductivity-Based Change Detection

As a secondary indicator:

$$
\mathrm{change\_rate} = \frac{\left| \log_{10}(\sigma_c) - \overline{\log_{10}(\sigma_b)} \right|}{\Delta T}
$$

where σ_c = conductivity at current measurement, σ_b = baseline (average of last 4 valid measurements).

Trigger condition: change_rate > **0.25 /°C** OR change_rate > 5σ of baseline variability.

## 5. Observed Behavior (from Fig S1 and S2)

In the representative measurement shown in the uploaded figures:
- **3 phase transitions detected** at measurement indices ~30, ~35, ~42
- Corresponding to temperature region **~200-220 K**
- Automatic switching from Course Step (3K, blue bars) to Fine Step (1K, pink bars) visible in Fig S2
- Phase Jump Score peaks reaching **~0.6** (well above 0.2 threshold)

## 6. Key Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Phase Jump Score threshold | 0.2 | Fig S1 (dashed red line) |
| Phase angle threshold | 30° | Code default |
| Coarse step size | 3 K | Fig S2 |
| Fine step size | 1 K | Fig S2 |
| Conductivity change threshold | 0.25 /°C | Code default |
| Resume threshold | < 0.1 for 3 consecutive | Code logic |
