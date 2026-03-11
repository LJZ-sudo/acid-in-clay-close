# SI Note 2: Arrhenius Segmentation Algorithm

> **Source code**: `close/phase1/core/arrhenius_analyzer.py`

## 1. Overview

The agent performs automated segmented Arrhenius analysis to identify distinct proton conduction mechanism regimes. The algorithm iteratively detects breakpoints in the ln(σ) vs 1000/T relationship using statistical model selection.

## 2. Physical Model

The Arrhenius equation for ionic conductivity:

$$\sigma(T) = \sigma_0 \exp\left(-\frac{E_a}{k_B T}\right)$$

Linearized form (used for fitting):

$$\ln(\sigma) = \ln(\sigma_0) - \frac{E_a}{k_B T}$$

where k_B = 8.617333 × 10⁻⁵ eV/K is the Boltzmann constant.

Each segment yields:
- **Ea** (activation energy, eV): slope × (-k_B) of ln(σ) vs 1/T
- **σ₀** (pre-exponential factor, S/cm): exp(intercept)
- **R²**: coefficient of determination

## 3. Segmentation Algorithm

### Step 1: Breakpoint Candidate Detection

**Sliding window approach** (window_size = 5):
1. For each possible breakpoint position i (from min_points to n-min_points):
   - Compute slope_left = linear regression slope on points [0:i]
   - Compute slope_right = linear regression slope on points [i:n]
   - Compute slope_difference = |slope_left - slope_right|
2. Normalize slope differences by their standard deviation
3. Candidates: positions where normalized slope_difference > **0.5**

### Step 2: Breakpoint Validation (F-test)

For each candidate breakpoint:

$$F = \frac{(RSS_1 - RSS_2) / (df_1 - df_2)}{RSS_2 / df_2}$$

where:
- RSS₁ = residual sum of squares of single-segment model
- RSS₂ = residual sum of squares of two-segment model
- df₁, df₂ = degrees of freedom

Accept breakpoint if F-test p-value < **0.05**.

### Step 3: Optimal Breakpoint Selection (AIC)

Among validated candidates, select the one that minimizes AIC:

$$AIC = n \ln(RSS/n) + 2k$$

where n = number of data points, k = number of parameters.

### Step 4: Iterative Multi-Segment Extension

Repeat Steps 1–3 on each resulting segment until:
- max_segments reached (default: **3** breakpoints → **4** segments), or
- No further breakpoints pass F-test, or
- Any segment would have fewer than min_points (**5**) data points

## 4. Physical Constraints

- Ea must be in **[0, 2.0] eV** (physically reasonable range)
- Each segment must contain ≥ **5** data points
- Segments are ordered by temperature (high-T first in Arrhenius space)

## 5. Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| min_points | 5 | Minimum points per segment |
| max_segments | 3 | Maximum number of breakpoints (→ max 4 segments) |
| window_size | 5 | Sliding window for slope change detection |
| slope_threshold | 0.5 | Normalized slope difference for candidate detection |
| f_test_alpha | 0.05 | Significance level for F-test |
| Ea_bounds | [0, 2.0] eV | Physical constraint on activation energy |

## 6. Output Structure

For each sample, the algorithm outputs:
```json
{
  "segments": [
    {
      "segment_id": 1,
      "T_range_K": [286, 300],
      "Ea_eV": 0.08,
      "ln_sigma0": 1.23,
      "R_squared": 0.989,
      "n_points": 8
    },
    ...
  ],
  "breakpoints_K": [283, 258, 227],
  "n_segments": 4,
  "method": "iterative_f_test_aic"
}
```

## 7. Comparison: Agent (4 segments) vs Baseline (2 segments)

The agent's denser sampling (especially fine-scan near phase transitions) provides more data points in critical temperature regions, enabling the algorithm to detect breakpoints that sparse data would miss:

| Feature | Agent Measurement | Baseline Measurement |
|---------|------------------|---------------------|
| Typical data points | ~47 | ~20-25 |
| Detected segments | 3–4 | 1–2 |
| Key advantage | Fine-scan in transition zone | Fixed 3K step throughout |
| Ea resolution | Detects 0.08/0.16/0.35/0.90 | Merges into 0.31/0.91 |
