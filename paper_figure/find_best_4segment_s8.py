# -*- coding: utf-8 -*-
"""
Find best 4-segment S8 sample for Figure 1
"""
from pathlib import Path
import json

RESULTS_DIR = Path(__file__).resolve().parent.parent / "output" / "phase1_results"

def main():
    print("Searching for 4-segment S8 samples...\n")
    
    four_seg_samples = []
    
    for json_file in sorted(RESULTS_DIR.glob("S8*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            sample_id = json_file.stem.replace('_analysis_result', '')
            
            if 'arrhenius' not in data or 'segments' not in data['arrhenius']:
                continue
            
            segments = data['arrhenius']['segments']
            
            if len(segments) != 4:
                continue
            
            # Get data points
            n_points = len(data.get('temperatures', []))
            
            # Calculate average R2
            r2_values = [seg.get('r_squared', 0) for seg in segments]
            avg_r2 = sum(r2_values) / len(r2_values)
            min_r2 = min(r2_values)
            
            # Temperature range
            temps = data.get('temperatures', [])
            if len(temps) > 0:
                temp_range = max(temps) - min(temps)
            else:
                temp_range = 0
            
            four_seg_samples.append({
                'sample_id': sample_id,
                'n_points': n_points,
                'avg_r2': avg_r2,
                'min_r2': min_r2,
                'temp_range': temp_range,
                'r2_values': r2_values,
                'segments': segments
            })
            
        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")
            continue
    
    if not four_seg_samples:
        print("No 4-segment S8 samples found!")
        return
    
    # Sort by: 1) min_r2 > 0.9, 2) n_points, 3) avg_r2
    four_seg_samples.sort(key=lambda x: (x['min_r2'] > 0.9, x['n_points'], x['avg_r2']), reverse=True)
    
    print(f"Found {len(four_seg_samples)} 4-segment S8 samples\n")
    print("="*80)
    print("Top 10 candidates (sorted by quality):")
    print("="*80)
    
    for i, sample in enumerate(four_seg_samples[:10], 1):
        print(f"\n{i}. {sample['sample_id']}")
        print(f"   Data points: {sample['n_points']}")
        print(f"   Avg R2: {sample['avg_r2']:.4f}")
        print(f"   Min R2: {sample['min_r2']:.4f}")
        print(f"   Temp range: {sample['temp_range']:.1f} K")
        print(f"   R2 by segment: {[f'{r2:.3f}' for r2 in sample['r2_values']]}")
        
        # Print Ea values
        ea_values = [seg.get('Ea_eV', 0) for seg in sample['segments']]
        print(f"   Ea values: {[f'{ea:.3f}' for ea in ea_values]} eV")
    
    print(f"\n{'='*80}")
    print(f"RECOMMENDED: {four_seg_samples[0]['sample_id']}")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
