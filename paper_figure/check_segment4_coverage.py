# -*- coding: utf-8 -*-
"""
检查 Segment 4 绘图覆盖范围
"""
from pathlib import Path
import json
import numpy as np

SAMPLE_ID = "S8-3-9-3"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "output" / "phase1_results"

json_path = RESULTS_DIR / f"{SAMPLE_ID}_analysis_result.json"
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

temperatures_K = np.array(data['temperatures'])
seg4 = data["arrhenius"]["segments"][3]

T_lo, T_hi = seg4["temp_range_K"]
inv_T_lo = 1000.0 / T_hi
inv_T_hi = 1000.0 / T_lo

print(f"Segment 4 temperature range:")
print(f"  T: {T_lo:.2f} - {T_hi:.2f} K")
print(f"  1000/T: {inv_T_lo:.3f} - {inv_T_hi:.3f}")

# 检查实际数据点
mask = (temperatures_K >= T_lo) & (temperatures_K <= T_hi)
T_seg = temperatures_K[mask]
inv_T_seg = 1000.0 / T_seg

print(f"\nActual data points:")
print(f"  Count: {len(T_seg)}")
print(f"  1000/T range: {inv_T_seg.min():.3f} - {inv_T_seg.max():.3f}")

# 检查绘图时的 x_seg
inv_T_all = 1000.0 / temperatures_K
x_plot = np.linspace(inv_T_all.min(), inv_T_all.max(), 200)

print(f"\nx_plot range: {x_plot.min():.3f} - {x_plot.max():.3f}")

x_seg = x_plot[(x_plot >= inv_T_lo) & (x_plot <= inv_T_hi)]
print(f"\nx_seg for Segment 4:")
print(f"  Range: {x_seg.min():.3f} - {x_seg.max():.3f}")
print(f"  Points: {len(x_seg)}")

if x_seg.min() > inv_T_seg.min() or x_seg.max() < inv_T_seg.max():
    print("\n!!! WARNING: x_seg does NOT cover all data points !!!")
    print(f"  Data min: {inv_T_seg.min():.3f}, x_seg min: {x_seg.min():.3f}")
    print(f"  Data max: {inv_T_seg.max():.3f}, x_seg max: {x_seg.max():.3f}")
else:
    print("\nOK: x_seg covers all data points")

# 检查视觉问题：segment 4的拟合线颜色
print(f"\nSegment 4 fit line color: #9C27B0 (purple)")
print("Data points color: #2c3e50 (dark gray, alpha=0.5)")
print("\nPossible visual issue: Low-temperature data points are very scattered,")
print("and the fit line may appear to 'miss' some points visually, even though")
print("it's the correct least-squares fit.")
