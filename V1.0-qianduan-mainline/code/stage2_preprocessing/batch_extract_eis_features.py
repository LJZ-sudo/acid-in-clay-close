#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch Extract EIS Features for all S8 samples
"""

import json
import sys
from pathlib import Path
from datetime import datetime

from extract_s8_eis_features import extract_sample_features


def batch_extract_all(
    stage0_results_dir: Path,
    raw_eis_base: Path,
    force_reextract: bool = False
) -> dict:
    """Batch extract EIS features for all samples"""
    print("=" * 60)
    print("Batch EIS Feature Extraction")
    print("=" * 60)
    print(f"Stage0 results: {stage0_results_dir}")
    print(f"Raw EIS base: {raw_eis_base}")
    print(f"Force re-extract: {force_reextract}")
    print("=" * 60)
    
    results = {
        'total_samples': 0,
        'successful_samples': 0,
        'failed_samples': 0,
        'skipped_samples': 0,
        'samples': [],
        'extraction_timestamp': datetime.now().isoformat()
    }
    
    # Find all sample directories
    sample_dirs = []
    for sample_dir in sorted(stage0_results_dir.glob("S8-*")):
        if not sample_dir.is_dir():
            continue
        
        sample_id = sample_dir.name
        
        # Find scan subdirectories
        for scan_dir in sample_dir.glob("*K*"):
            if not scan_dir.is_dir():
                continue
            
            sample_dirs.append((sample_id, scan_dir.name))
    
    print(f"\nFound {len(sample_dirs)} sample scan directories\n")
    
    # Process each sample
    for idx, (sample_id, scan_dir) in enumerate(sample_dirs, 1):
        results['total_samples'] += 1
        
        print(f"[{idx}/{len(sample_dirs)}] {sample_id}/{scan_dir}")
        
        # Check if already exists
        eis_file = stage0_results_dir / sample_id / scan_dir / "eis_features.json"
        if eis_file.exists() and not force_reextract:
            print(f"  Skipped (already exists)")
            results['skipped_samples'] += 1
            continue
        
        try:
            # Load aggregated_results
            agg_file = stage0_results_dir / sample_id / scan_dir / "aggregated_results.json"
            if not agg_file.exists():
                print(f"  Error: aggregated_results.json not found")
                results['failed_samples'] += 1
                continue
            
            with open(agg_file, encoding='utf-8') as f:
                agg_data = json.load(f)
            
            features = extract_sample_features(
                sample_id=sample_id,
                scan_dir=scan_dir,
                raw_eis_base=raw_eis_base,
                aggregated_results=agg_data,
                output_file=eis_file
            )
            
            if features:
                results['successful_samples'] += 1
                results['samples'].append({
                    'sample_id': sample_id,
                    'scan_dir': scan_dir,
                    'n_points': features['n_points'],
                    'n_valid': features['data_quality_summary']['n_valid_points'],
                    'avg_R_ratio': features['data_quality_summary']['avg_R_ratio']
                })
            else:
                results['failed_samples'] += 1
        
        except Exception as e:
            print(f"  Error: {e}")
            results['failed_samples'] += 1
    
    # Save summary
    summary_file = stage0_results_dir / "eis_features_extraction_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("Batch extraction complete")
    print("=" * 60)
    print(f"Total: {results['total_samples']}")
    print(f"Success: {results['successful_samples']}")
    print(f"Failed: {results['failed_samples']}")
    print(f"Skipped: {results['skipped_samples']}")
    print(f"\nSummary: {summary_file}")
    
    return results


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch extract EIS features for all S8 samples')
    parser.add_argument('--stage0-dir', default='../../output/stage0_results', help='Stage0 results directory')
    parser.add_argument('--raw-eis-base', default='../../data/raw_eis/S8', help='Raw EIS base directory')
    parser.add_argument('--force', '-f', action='store_true', help='Force re-extraction')
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    stage0_dir = (script_dir / args.stage0_dir).resolve()
    raw_eis_base = (script_dir / args.raw_eis_base).resolve()
    
    if not stage0_dir.exists():
        print(f"Error: Stage0 directory not found: {stage0_dir}")
        sys.exit(1)
    
    if not raw_eis_base.exists():
        print(f"Error: Raw EIS directory not found: {raw_eis_base}")
        sys.exit(1)
    
    results = batch_extract_all(stage0_dir, raw_eis_base, args.force)
    
    success_rate = results['successful_samples'] / results['total_samples'] if results['total_samples'] > 0 else 0
    
    if success_rate >= 0.9:
        print(f"\nSuccess: {results['successful_samples']}/{results['total_samples']} ({success_rate*100:.1f}%)")
        sys.exit(0)
    else:
        print(f"\nPartial success: {results['successful_samples']}/{results['total_samples']} ({success_rate*100:.1f}%)")
        sys.exit(1)


if __name__ == '__main__':
    main()
