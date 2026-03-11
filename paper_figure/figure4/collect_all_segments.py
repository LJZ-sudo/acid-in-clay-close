# -*- coding: utf-8 -*-
"""
收集所有segment的数据：R, N, T, Ea
用于3D可视化 (R, N, T) + 颜色编码Ea
"""
from pathlib import Path
import json
import pandas as pd
import numpy as np

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "phase1_results"
OUT_DIR = Path(__file__).resolve().parent

# 获取所有JSON文件
json_files = list(RESULTS_DIR.glob("*_analysis_result.json"))

print(f"Found {len(json_files)} JSON files\n")

# 收集数据
data_rows = []

for json_file in json_files:
    sample_id = json_file.stem.replace("_analysis_result", "")
    
    # 只处理S8和S60样品
    if not (sample_id.startswith('S8-') or sample_id.startswith('S60-')):
        continue
    
    # 读取JSON
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 解析样品ID
        parts = sample_id.split("-")
        material = parts[0]
        n_value = int(parts[1]) if len(parts) > 1 else None
        r_value = int(parts[2]) if len(parts) > 2 else None
        
        # 获取Arrhenius segments
        segments = data.get("arrhenius", {}).get("segments", [])
        
        if len(segments) == 0:
            continue
        
        # 遍历每个segment，提取中点温度和Ea
        for seg_idx, seg in enumerate(segments, 1):
            T_low, T_high = seg["temp_range_K"]
            T_mid = (T_low + T_high) / 2.0  # 温度范围的中点
            Ea = seg["Ea_eV"]
            
            data_rows.append({
                'sample_id': sample_id,
                'material': material,
                'N': n_value,
                'R': r_value,
                'segment': seg_idx,
                'T_low_K': T_low,
                'T_high_K': T_high,
                'T_mid_K': T_mid,
                'Ea_eV': Ea,
                'r_squared': seg["r_squared"]
            })
    
    except Exception as e:
        print(f"Error processing {sample_id}: {e}")
        continue

df = pd.DataFrame(data_rows)

print(f"\nCollected {len(df)} segment data points (S8 + S60)\n")

# 分材料统计
print("="*70)
print("S8 segments:")
s8_df = df[df['material'] == 'S8']
print(f"Total segments: {len(s8_df)}")
print(f"From {s8_df['sample_id'].nunique()} samples")
print(f"Temperature range: {s8_df['T_mid_K'].min():.1f} - {s8_df['T_mid_K'].max():.1f} K")
print(f"Ea range: {s8_df['Ea_eV'].min():.3f} - {s8_df['Ea_eV'].max():.3f} eV")

print("\n" + "="*70)
print("S60 segments:")
s60_df = df[df['material'] == 'S60']
print(f"Total segments: {len(s60_df)}")
print(f"From {s60_df['sample_id'].nunique()} samples")
print(f"Temperature range: {s60_df['T_mid_K'].min():.1f} - {s60_df['T_mid_K'].max():.1f} K")
print(f"Ea range: {s60_df['Ea_eV'].min():.3f} - {s60_df['Ea_eV'].max():.3f} eV")

# 保存CSV
csv_path = OUT_DIR / "all_segments_data.csv"
df.to_csv(csv_path, index=False)

print(f"\n{'='*70}")
print(f"Data saved to: {csv_path}")
print(f"{'='*70}")

# 显示示例数据
print("\nSample data (first 10):")
print(df[['sample_id', 'N', 'R', 'segment', 'T_mid_K', 'Ea_eV']].head(10))
