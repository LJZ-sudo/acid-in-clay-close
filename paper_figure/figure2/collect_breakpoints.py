# -*- coding: utf-8 -*-
"""
收集 S8 和 S60 样品的 Arrhenius 变化点（breakpoints）
用于 Figure 2: 多样品变化点温度分布
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

CLOSE_ROOT = Path(__file__).resolve().parent.parent.parent
PHASE1_DIR = CLOSE_ROOT / "output" / "phase1_results"
OUT_DIR = Path(__file__).resolve().parent

def collect_breakpoints(material_type):
    """收集指定材料的所有变化点温度（只收集 4 段样品）"""
    breakpoints_data = []
    
    # 查找所有该材料的样品
    pattern = f"{material_type}-*.json"
    files = sorted(PHASE1_DIR.glob(pattern))
    
    print(f"\n{'='*60}")
    print(f"Material: {material_type}")
    print(f"Found {len(files)} samples")
    print(f"{'='*60}")
    
    skipped_count = 0
    
    for file in files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            sample_id = data["sample_id"]
            segments = data["arrhenius"]["segments"]
            n_segments = len(segments)
            
            # ⭐ 只保留 4 段样品 ⭐
            if n_segments != 4:
                skipped_count += 1
                continue
            
            # 提取变化点温度
            # 变化点在相邻段之间：取下一段的高温端
            for i in range(len(segments) - 1):
                next_seg = segments[i + 1]
                temp_range = next_seg.get("temp_range_K") or next_seg.get("T_range")
                if temp_range:
                    breakpoint_T = max(temp_range)  # 下一段的高温端
                    
                    breakpoints_data.append({
                        'material': material_type,
                        'sample_id': sample_id,
                        'breakpoint_index': i + 1,  # 第几个变化点
                        'temperature_K': breakpoint_T,
                        'total_segments': n_segments
                    })
            
            print(f"  {sample_id}: {n_segments} segments, {n_segments-1} breakpoints")
        
        except Exception as e:
            print(f"  Error reading {file.name}: {e}")
    
    print(f"\nKept {len(breakpoints_data)//3} 4-segment samples (skipped {skipped_count} non-4-segment samples)")
    
    return breakpoints_data

def main():
    # 收集 S8 和 S60 的变化点
    all_breakpoints = []
    
    for material in ["S8", "S60"]:
        bp_data = collect_breakpoints(material)
        all_breakpoints.extend(bp_data)
    
    # 转换为 DataFrame
    df = pd.DataFrame(all_breakpoints)
    
    if len(df) == 0:
        print("\nNo breakpoints found!")
        return
    
    print(f"\n{'='*60}")
    print(f"Summary")
    print(f"{'='*60}")
    print(f"Total breakpoints collected: {len(df)}")
    print(f"\nBy material:")
    print(df.groupby('material').size())
    
    print(f"\nTemperature range:")
    print(f"  Min: {df['temperature_K'].min():.2f} K")
    print(f"  Max: {df['temperature_K'].max():.2f} K")
    print(f"  Mean: {df['temperature_K'].mean():.2f} K")
    print(f"  Median: {df['temperature_K'].median():.2f} K")
    
    # 统计 215 K 附近的变化点（±10 K）
    near_215 = df[(df['temperature_K'] >= 205) & (df['temperature_K'] <= 225)]
    print(f"\nBreakpoints near 215 K (205-225 K): {len(near_215)}")
    
    # 保存为 CSV
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "breakpoints_data.csv"
    df.to_csv(csv_path, index=False, encoding='utf-8')
    print(f"\nData saved to: {csv_path}")
    
    return df

if __name__ == "__main__":
    df = main()
