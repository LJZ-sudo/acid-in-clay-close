# -*- coding: utf-8 -*-
"""查看 S8-3-2-1 的分段信息"""
import json
from pathlib import Path

PHASE1_DIR = Path(__file__).resolve().parent.parent / "output" / "phase1_results"
data_file = PHASE1_DIR / "S8-3-2-1_analysis_result.json"

with open(data_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

segs = data['arrhenius']['segments']
print(f"Total segments: {len(segs)}\n")

for i, s in enumerate(segs):
    T_range = s.get("temp_range_K", [])
    print(f"Segment {i+1}:")
    print(f"  T range: {T_range[0]:.2f} - {T_range[1]:.2f} K")
    print(f"  Ea: {s['Ea_eV']:.4f} eV")
    print(f"  ln_sigma0: {s['ln_sigma0']:.4f}")
    print(f"  R2: {s['r_squared']:.4f}")
    print()
