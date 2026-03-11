# SI Note 1: Multi-Strategy Bulk Resistance (Rb) Fitting Method

> **Source code**: `close/phase1/core/rb_fitting.py`, `specific_conductance/rb_fitting.py`

## 1. Overview

The agent employs a multi-strategy Rb fitting approach that automatically selects the optimal method based on EIS spectrum morphology at each temperature. This is critical because EIS spectra vary dramatically across the 170–300 K range: from incomplete high-impedance semicircles at low-T to Warburg-type responses at high-T.

## 2. Fitting Strategies (Priority Order)

### Strategy 1: X-axis Intercept Method (highest priority)

**Applicable conditions**: Clear semicircle with identifiable Z' intercept, or low-impedance spectra where Z'' crosses zero.

**Algorithm**:
1. Scan Z_imag for sign change or near-zero crossing (|Z''| < 5 Ω)
2. If found: Rb = Z' at the crossing point
3. If not found: perform linear extrapolation on the high-frequency tail to find Z' axis intercept

**Dominance**: 75–95% of low-T (170–210 K) and high-T (270–290 K) measurements (see Fig S4).

### Strategy 2: Progressive Linear Fit

**Applicable conditions**: Partial semicircle where the high-frequency portion is approximately linear.

**Algorithm**:
1. Start with all data points
2. Iteratively remove the lowest-frequency point
3. At each step, compute correlation coefficient r of Z'' vs Z'
4. Accept when |r| > **0.92** (threshold)
5. Rb = x-intercept of the linear fit
6. Maximum removal: **35%** of total points

### Strategy 3: Semicircle Arc Fitting (IRLS)

**Applicable conditions**: Clear semicircular arc in Nyquist plot.

**Algorithm**:
1. Apply Savitzky-Golay preprocessing (window=7, poly=3) for noise reduction
2. Remove outliers using 3σ criterion
3. Fit circle using Iteratively Reweighted Least Squares (IRLS) with Huber weighting (τ=0.1):
   - Minimize: Σ ρ_Huber(|r_i - R|) where r_i = distance from point i to center, R = radius
   - Huber loss: ρ(x) = x²/2 if |x| ≤ τ, else τ|x| - τ²/2
4. Rb = x_center + R (right intercept of semicircle with Z' axis)
5. Convergence: max_iter=50, tol=1e-6

### Strategy 4: Relaxed Linear Fit (fallback)

**Applicable conditions**: When strategies 1–3 fail.

**Algorithm**:
1. Use middle segment of data (20%–80% of frequency range)
2. Apply linear fit with relaxed threshold: |r| > **0.88**
3. If still fails, further relax to **0.85**

### Strategy 5: High-Frequency Average (last resort)

**Applicable conditions**: All above methods fail.

**Algorithm**: Rb = min(Z') from the highest-frequency 20% of data points.

## 3. Quality Control Integration

After Rb fitting, the Critic Agent evaluates the result:
- **R² grading**: A (≥0.98), B (≥0.95), C (≥0.90), D (<0.90)
- Grade C or D triggers re-measurement suggestion
- All fitting parameters and method selection are logged in the Evidence Package

## 4. Key Parameters Summary

| Parameter | Value | Description |
|-----------|-------|-------------|
| linear_threshold | 0.92 | Minimum |r| for progressive linear fit |
| max_remove_ratio | 0.35 | Maximum fraction of points removable |
| relaxed_threshold | 0.88 | Relaxed |r| for fallback |
| very_relaxed_threshold | 0.85 | Final fallback threshold |
| filter_window | 7 | Savitzky-Golay window size |
| filter_poly | 3 | Savitzky-Golay polynomial order |
| outlier_threshold | 3.0σ | Outlier detection |
| huber_tau | 0.1 | IRLS robustness parameter |
| circle_max_iter | 50 | Maximum IRLS iterations |
| circle_tol | 1e-6 | IRLS convergence tolerance |

## 5. Conductivity Calculation

From Rb, the ionic conductivity σ is computed:

$$\sigma = \frac{L}{R_b \cdot S}$$

where L is sample thickness (cm) and S is sample cross-sectional area (cm²).
