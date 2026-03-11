# -*- coding: utf-8 -*-
"""
检查 Segment 4 的数据和拟合
"""
from pathlib import Path
import json
import numpy as np
from scipy.stats import linregress

SAMPLE_ID = "S8-3-9-3"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "output" / "phase1_results"

json_path = RESULTS_DIR / f"{SAMPLE_ID}_analysis_result.json"
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

temperatures_K = np.array(data['temperatures'])
conductivity_S_cm = np.array(data['conductivity_values'])
seg4 = data["arrhenius"]["segments"][3]  # 第4段

T_lo, T_hi = seg4["temp_range_K"]
Ea_json = seg4["Ea_eV"]
ln_sigma0_json = seg4["ln_sigma0"]
r2_json = seg4["r_squared"]

print(f"Segment 4 from JSON:")
print(f"  Range: {T_lo:.2f} - {T_hi:.2f} K")
print(f"  Ea: {Ea_json:.4f} eV")
print(f"  ln_sigma0: {ln_sigma0_json:.4f}")
print(f"  R2: {r2_json:.4f}")

# 提取该段的数据点
mask = (temperatures_K >= T_lo) & (temperatures_K <= T_hi)
T_seg = temperatures_K[mask]
sigma_seg = conductivity_S_cm[mask]

print(f"\nData points in Segment 4: {len(T_seg)}")

# 重新拟合
inv_T_seg = 1000.0 / T_seg
ln_sigma_seg = np.log(sigma_seg)

slope, intercept, r_value, p_value, std_err = linregress(inv_T_seg, ln_sigma_seg)

kB_eV = 8.617333e-5
Ea_refit = -slope * kB_eV * 1000.0
ln_sigma0_refit = intercept
r2_refit = r_value ** 2

print(f"\nRe-fit from data:")
print(f"  Ea: {Ea_refit:.4f} eV")
print(f"  ln_sigma0: {ln_sigma0_refit:.4f}")
print(f"  R2: {r2_refit:.4f}")

print(f"\nDifference:")
print(f"  Delta Ea: {abs(Ea_json - Ea_refit):.4f} eV")
print(f"  Delta ln_sigma0: {abs(ln_sigma0_json - ln_sigma0_refit):.4f}")

if abs(Ea_json - Ea_refit) > 0.01:
    print("\n!!! WARNING: JSON parameters do NOT match data fit !!!")
    print("The JSON file may contain incorrect fitting parameters for Segment 4.")
else:
    print("\nJSON parameters match data fit well.")
