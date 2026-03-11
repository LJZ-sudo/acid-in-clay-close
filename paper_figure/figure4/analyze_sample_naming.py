# -*- coding: utf-8 -*-
"""
分析样品命名规则，提取N和R值
"""
from pathlib import Path
import json
import re
import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "phase1_results"

# 获取所有JSON文件
json_files = list(RESULTS_DIR.glob("*_analysis_result.json"))

print(f"Found {len(json_files)} JSON files\n")

# 分析样品命名
sample_data = []

for json_file in json_files[:20]:  # 先看前20个
    sample_id = json_file.stem.replace("_analysis_result", "")
    
    # 解析样品ID: S8-N-R-L 或 S60-N-R-L
    parts = sample_id.split("-")
    
    if len(parts) >= 3:
        material = parts[0]  # S8 or S60
        n_value = parts[1] if len(parts) > 1 else None
        r_value = parts[2] if len(parts) > 2 else None
        l_value = parts[3] if len(parts) > 3 else None
        
        sample_data.append({
            'sample_id': sample_id,
            'material': material,
            'N': n_value,
            'R': r_value,
            'L': l_value,
            'parts_count': len(parts)
        })

df = pd.DataFrame(sample_data)

print("Sample naming structure:")
print(df.head(20))

print("\n\nN values distribution:")
print(df.groupby(['material', 'N']).size())

print("\n\nR values distribution:")
print(df.groupby(['material', 'R']).size())

print("\n\nSample ID format examples:")
print("S8 samples:")
print(df[df['material'] == 'S8']['sample_id'].head(10).tolist())
print("\nS60 samples:")
print(df[df['material'] == 'S60']['sample_id'].head(10).tolist())
