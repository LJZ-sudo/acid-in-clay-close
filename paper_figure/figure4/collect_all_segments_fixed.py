# -*- coding: utf-8 -*-
"""
收集所有segment的数据：R, N, T, Ea
使用JSON中的真实N和R值，不是从样品ID解析
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
        
        # 从JSON中读取真实的N和R值
        material = data.get("material_type", sample_id.split("-")[0])
        n_value = data.get("N", None)  # 真实N值
        r_value = data.get("R", None)  # 真实R值
        
        if n_value is None or r_value is None:
            print(f"Warning: {sample_id} missing N or R value, skipping")
            continue
        
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
                'N': n_value,       # 真实N值
                'R': r_value,       # 真实R值
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
print(f"N range: {s8_df['N'].min():.3f} - {s8_df['N'].max():.3f}")
print(f"R range: {s8_df['R'].min():.3f} - {s8_df['R'].max():.3f}")
print(f"Temperature range: {s8_df['T_mid_K'].min():.1f} - {s8_df['T_mid_K'].max():.1f} K")
print(f"Ea range: {s8_df['Ea_eV'].min():.3f} - {s8_df['Ea_eV'].max():.3f} eV")

print("\n" + "="*70)
print("S60 segments:")
s60_df = df[df['material'] == 'S60']
print(f"Total segments: {len(s60_df)}")
print(f"From {s60_df['sample_id'].nunique()} samples")
print(f"N range: {s60_df['N'].min():.3f} - {s60_df['N'].max():.3f}")
print(f"R range: {s60_df['R'].min():.3f} - {s60_df['R'].max():.3f}")
print(f"Temperature range: {s60_df['T_mid_K'].min():.1f} - {s60_df['T_mid_K'].max():.1f} K")
print(f"Ea range: {s60_df['Ea_eV'].min():.3f} - {s60_df['Ea_eV'].max():.3f} eV")

# 保存CSV
csv_path = OUT_DIR / "all_segments_data_fixed.csv"
df.to_csv(csv_path, index=False)

print(f"\n{'='*70}")
print(f"Data saved to: {csv_path}")
print(f"{'='*70}")

# 显示示例数据
print("\nSample data (first 10 rows):")
print(df[['sample_id', 'N', 'R', 'segment', 'T_mid_K', 'Ea_eV']].head(10).to_string())

print("\n\nN and R value distribution:")
print(f"S8 N values (unique): {sorted(s8_df['N'].unique())}")
print(f"S8 R values (unique count): {s8_df['R'].nunique()}")
print(f"S60 N values (unique): {sorted(s60_df['N'].unique())}")
print(f"S60 R values (unique count): {s60_df['R'].nunique()}")
