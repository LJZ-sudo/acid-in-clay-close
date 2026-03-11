# -*- coding: utf-8 -*-
"""
检查实际绘图的坐标
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
segments = data["arrhenius"]["segments"]

# 计算inv_T
inv_T = 1000.0 / temperatures_K

print(f"Sample: {SAMPLE_ID}")
print(f"Total data points: {len(temperatures_K)}")
print(f"\nData point coordinates (1000/T):")
print(f"  Min inv_T: {inv_T.min():.3f} (T={temperatures_K.max():.2f} K)")
print(f"  Max inv_T: {inv_T.max():.3f} (T={temperatures_K.min():.2f} K)")

print(f"\nSegment ranges (1000/T):")
for i, seg in enumerate(segments, 1):
    T_lo, T_hi = seg["temp_range_K"]
    inv_T_lo = 1000.0 / T_hi
    inv_T_hi = 1000.0 / T_lo
    print(f"  Segment {i}: inv_T = {inv_T_lo:.3f} - {inv_T_hi:.3f}")
    
    # 这段拟合线在X轴上的范围
    mask = (temperatures_K >= T_lo) & (temperatures_K <= T_hi)
    if mask.sum() > 0:
        seg_inv_T = inv_T[mask]
        print(f"    Data points: inv_T = {seg_inv_T.min():.3f} - {seg_inv_T.max():.3f} ({mask.sum()} points)")

# 检查是否有gap
print(f"\nChecking coverage:")
sorted_inv_T = np.sort(inv_T)
print(f"Sorted data inv_T range: {sorted_inv_T[0]:.3f} - {sorted_inv_T[-1]:.3f}")

# 检查segment 1和最左边数据点的gap
seg1_inv_T_min = 1000.0 / segments[0]["temp_range_K"][1]
leftmost_data = sorted_inv_T[0]
if seg1_inv_T_min > leftmost_data:
    gap = seg1_inv_T_min - leftmost_data
    print(f"GAP FOUND: Segment 1 starts at {seg1_inv_T_min:.3f}, but data starts at {leftmost_data:.3f}")
    print(f"  Gap size: {gap:.3f}")
else:
    print(f"No gap: Segment 1 covers from {seg1_inv_T_min:.3f}, data starts at {leftmost_data:.3f}")
