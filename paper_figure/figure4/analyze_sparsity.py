# -*- coding: utf-8 -*-
"""
分析热力图数据稀疏度
"""
import pandas as pd
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

df = pd.read_csv(OUT_DIR / "ea_heatmap_data.csv")

print("="*70)
print("S8 samples:")
s8 = df[df['material'] == 'S8']
print(f"  Total samples: {len(s8)}")
print(f"  N range: {s8['N'].min()}-{s8['N'].max()}, unique values: {s8['N'].nunique()}")
print(f"  R range: {s8['R'].min()}-{s8['R'].max()}, unique values: {s8['R'].nunique()}")
total_cells = s8['N'].nunique() * s8['R'].nunique()
print(f"  Grid size: {s8['N'].nunique()} x {s8['R'].nunique()} = {total_cells} cells")
print(f"  Data coverage: {len(s8)}/{total_cells} = {len(s8)/total_cells*100:.1f}%")
print(f"  Empty cells: {total_cells - len(s8)}")

print("\n" + "="*70)
print("S60 samples:")
s60 = df[df['material'] == 'S60']
print(f"  Total samples: {len(s60)}")
print(f"  N range: {s60['N'].min()}-{s60['N'].max()}, unique values: {s60['N'].nunique()}")
print(f"  R range: {s60['R'].min()}-{s60['R'].max()}, unique values: {s60['R'].nunique()}")
total_cells = s60['N'].nunique() * s60['R'].nunique()
print(f"  Grid size: {s60['N'].nunique()} x {s60['R'].nunique()} = {total_cells} cells")
print(f"  Data coverage: {len(s60)}/{total_cells} = {len(s60)/total_cells*100:.1f}%")
print(f"  Empty cells: {total_cells - len(s60)}")

print("\n" + "="*70)
print("Conclusion:")
print("The heatmap is VERY SPARSE (78% and 38% empty for S8 and S60)")
print("Better visualization options:")
print("  1. 3D Scatter Plot (recommended) - show actual data points in 3D")
print("  2. 3D Bar Chart - bars for each N-R combination")
print("  3. 2D Scatter Plot with bubble size - simpler alternative")
