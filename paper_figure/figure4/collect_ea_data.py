# -*- coding: utf-8 -*-
"""
收集S8和S60样品的Ea数据，用于热力图
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
        
        # 获取高温段和低温段的Ea
        # 假设：第1段=高温，最后1段=低温
        ea_high = segments[0]["Ea_eV"] if len(segments) > 0 else None
        ea_low = segments[-1]["Ea_eV"] if len(segments) > 0 else None
        
        # 获取所有segment的Ea（用于后续分析）
        all_ea = [seg["Ea_eV"] for seg in segments]
        
        data_rows.append({
            'sample_id': sample_id,
            'material': material,
            'N': n_value,
            'R': r_value,
            'n_segments': len(segments),
            'Ea_high_temp': ea_high,
            'Ea_low_temp': ea_low,
            'Ea_mean': np.mean(all_ea),
            'Ea_all': all_ea
        })
    
    except Exception as e:
        print(f"Error processing {sample_id}: {e}")
        continue

df = pd.DataFrame(data_rows)

print(f"\nCollected {len(df)} samples (S8 + S60)\n")

# 分材料统计
print("="*70)
print("S8 samples:")
s8_df = df[df['material'] == 'S8']
print(f"Total: {len(s8_df)} samples")
print(f"N values: {sorted(s8_df['N'].unique())}")
print(f"R values: {sorted(s8_df['R'].unique())}")
print(f"\nN-R distribution:")
print(s8_df.groupby(['N', 'R']).size().unstack(fill_value=0))

print("\n" + "="*70)
print("S60 samples:")
s60_df = df[df['material'] == 'S60']
print(f"Total: {len(s60_df)} samples")
print(f"N values: {sorted(s60_df['N'].unique())}")
print(f"R values: {sorted(s60_df['R'].unique())}")
print(f"\nN-R distribution:")
print(s60_df.groupby(['N', 'R']).size().unstack(fill_value=0))

# 保存CSV
csv_path = OUT_DIR / "ea_heatmap_data.csv"
df_export = df[['sample_id', 'material', 'N', 'R', 'n_segments', 
                'Ea_high_temp', 'Ea_low_temp', 'Ea_mean']]
df_export.to_csv(csv_path, index=False)

print(f"\n{'='*70}")
print(f"Data saved to: {csv_path}")
print(f"{'='*70}")

# 显示示例数据
print("\nSample data (first 10):")
print(df_export.head(10))
