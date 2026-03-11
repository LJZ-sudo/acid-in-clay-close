# -*- coding: utf-8 -*-
"""
收集所有样品的 Arrhenius 分段数
"""
from pathlib import Path
import json
import pandas as pd

# 路径设置
RESULTS_DIR = Path(__file__).resolve().parents[2] / "output" / "phase1_results"
OUT_DIR = Path(__file__).resolve().parent

def main():
    print("Scanning phase1_results for segment counts...\n")
    
    data_list = []
    
    # 扫描所有JSON文件
    for json_file in sorted(RESULTS_DIR.glob("*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            sample_id = json_file.stem.replace('_analysis_result', '')
            
            # 提取材料类型
            if sample_id.startswith('S8'):
                material = 'S8'
            elif sample_id.startswith('S60'):
                material = 'S60'
            else:
                continue  # 跳过其他材料
            
            # 获取分段数
            if 'arrhenius' in data and 'segments' in data['arrhenius']:
                n_segments = len(data['arrhenius']['segments'])
            else:
                continue
            
            data_list.append({
                'sample_id': sample_id,
                'material': material,
                'n_segments': n_segments
            })
            
        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")
            continue
    
    # 创建DataFrame
    df = pd.DataFrame(data_list)
    
    # 保存原始数据
    csv_path = OUT_DIR / "segment_counts_data.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved raw data to: {csv_path}")
    
    # 统计分析
    print(f"\n{'='*70}")
    print("Segment Count Distribution:")
    print(f"{'='*70}")
    
    for material in ['S8', 'S60']:
        mat_df = df[df['material'] == material]
        print(f"\n{material} (Total: {len(mat_df)} samples):")
        
        segment_counts = mat_df['n_segments'].value_counts().sort_index()
        for n_seg, count in segment_counts.items():
            pct = count / len(mat_df) * 100
            print(f"  {n_seg} segments: {count:3d} samples ({pct:5.1f}%)")
    
    # 生成汇总统计
    summary_data = []
    for material in ['S8', 'S60']:
        mat_df = df[df['material'] == material]
        segment_counts = mat_df['n_segments'].value_counts().sort_index()
        
        for n_seg in range(segment_counts.index.min(), segment_counts.index.max() + 1):
            count = segment_counts.get(n_seg, 0)
            pct = count / len(mat_df) * 100 if len(mat_df) > 0 else 0
            summary_data.append({
                'Material': material,
                'N_Segments': n_seg,
                'N_Samples': count,
                'Percentage': pct
            })
    
    summary_df = pd.DataFrame(summary_data)
    summary_csv = OUT_DIR / "segment_counts_summary.csv"
    summary_df.to_csv(summary_csv, index=False, float_format='%.2f')
    print(f"\nSaved summary to: {summary_csv}")
    
    # 打印整体统计
    print(f"\n{'='*70}")
    print("Overall Statistics:")
    print(f"{'='*70}")
    print(f"S8:  {len(df[df['material']=='S8'])} samples")
    print(f"S60: {len(df[df['material']=='S60'])} samples")
    print(f"Total: {len(df)} samples")
    print(f"\nSegment range: {df['n_segments'].min()} - {df['n_segments'].max()}")

if __name__ == "__main__":
    main()
