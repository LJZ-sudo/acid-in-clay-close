#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Run full Stage0 to Stage2 preprocessing pipeline
"""

import sys
import time
from pathlib import Path
from datetime import datetime

from batch_extract_eis_features import batch_extract_all
from convert_stage0_to_stage2 import Stage0ToStage2Converter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "code"))

from shared.manifest import sha256_file, write_manifest


def run_pipeline(
    stage0_dir: str,
    raw_eis_base: str,
    rn_mapping: str,
    output_csv: str,
    skip_eis: bool = False,
    force_eis: bool = False
):
    """Run full pipeline"""
    start_time = time.time()
    
    print("=" * 60)
    print("Stage0 to Stage2 Full Pipeline")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Skip EIS: {skip_eis}")
    print("=" * 60)
    
    script_dir = Path(__file__).parent
    stage0_path = (script_dir / stage0_dir).resolve()
    raw_eis_path = (script_dir / raw_eis_base).resolve()
    rn_mapping_path = (script_dir / rn_mapping).resolve()
    output_csv_path = (script_dir / output_csv).resolve()
    
    # Check paths
    if not stage0_path.exists():
        print(f"Error: Stage0 directory not found: {stage0_path}")
        return False
    
    if not rn_mapping_path.exists():
        print(f"Error: R/N mapping not found: {rn_mapping_path}")
        return False
    
    # Step 1: Extract EIS features
    if not skip_eis:
        print("\n[Step 1/2] Extracting EIS features...")
        print("-" * 60)
        
        try:
            eis_results = batch_extract_all(stage0_path, raw_eis_path, force_eis)
            
            if eis_results['successful_samples'] == 0:
                print("\nWarning: EIS extraction failed, skipping EIS features")
                skip_eis = True
            else:
                print(f"\nEIS extraction complete: {eis_results['successful_samples']}/{eis_results['total_samples']}")
        
        except Exception as e:
            print(f"\nError in EIS extraction: {e}")
            print("Continuing without EIS features...")
            skip_eis = True
    else:
        print("\n[Step 1/2] Skipping EIS extraction")
    
    # Step 2: Convert to Stage2 input
    print("\n[Step 2/2] Converting to Stage2 input...")
    print("-" * 60)
    
    try:
        converter = Stage0ToStage2Converter(
            stage0_results_dir=str(stage0_path),
            rn_mapping_file=str(rn_mapping_path),
            output_csv=str(output_csv_path),
            include_eis_features=not skip_eis
        )
        
        df = converter.convert_all_samples()
        
        if df.empty:
            print("\nError: No valid data")
            return False
        
        print(f"\nConversion complete!")
    
    except Exception as e:
        print(f"\nError in conversion: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("Pipeline complete")
    print("=" * 60)
    print(f"Total time: {elapsed:.1f}s")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nOutput: {output_csv_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Samples: {df['sample_id'].nunique()}")
    write_manifest(Path(output_csv_path).with_suffix('.full_pipeline_manifest.json'), {
        'stage': 'stage2_preprocessing_full_pipeline',
        'stage0_dir': str(stage0_path),
        'raw_eis_base': str(raw_eis_path),
        'rn_mapping': str(rn_mapping_path),
        'output_csv': str(output_csv_path),
        'output_sha256': sha256_file(output_csv_path),
        'skip_eis': skip_eis,
        'force_eis': force_eis,
        'eis_results': locals().get('eis_results'),
        'rows': len(df),
        'samples': int(df['sample_id'].nunique()),
        'duration_seconds': elapsed,
    })
    
    return True


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run full Stage0 to Stage2 pipeline')
    parser.add_argument('--stage0-dir', default='../../output/stage0_results')
    parser.add_argument('--raw-eis-base', default='../../data/raw_eis/S8')
    parser.add_argument('--rn-mapping', default='../../output/stage0_results/s8_sample_rn.json')
    parser.add_argument('--output', default='../../stage2_statistics/data/s8_input.csv')
    parser.add_argument('--skip-eis', action='store_true', help='Skip EIS extraction')
    parser.add_argument('--force-eis', action='store_true', help='Force re-extract EIS')
    
    args = parser.parse_args()
    
    success = run_pipeline(
        stage0_dir=args.stage0_dir,
        raw_eis_base=args.raw_eis_base,
        rn_mapping=args.rn_mapping,
        output_csv=args.output,
        skip_eis=args.skip_eis,
        force_eis=args.force_eis
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
