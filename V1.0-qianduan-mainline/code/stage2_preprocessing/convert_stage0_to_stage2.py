#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Convert Stage0 results to Stage2 input CSV
"""

import json
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "code"))

from shared.manifest import sha256_file, write_manifest


class Stage0ToStage2Converter:
    """Convert Stage0 results to Stage2 input"""
    
    def __init__(
        self,
        stage0_results_dir: str,
        rn_mapping_file: str,
        output_csv: str,
        include_eis_features: bool = True
    ):
        self.stage0_dir = Path(stage0_results_dir)
        self.rn_mapping_file = Path(rn_mapping_file)
        self.output_csv = Path(output_csv)
        self.include_eis = include_eis_features
        
        # Load R, N mapping
        self.rn_mapping = self._load_rn_mapping()
        
        print("=" * 60)
        print("Stage0 to Stage2 Converter")
        print("=" * 60)
        print(f"Stage0 dir: {self.stage0_dir}")
        print(f"R/N mapping: {self.rn_mapping_file}")
        print(f"Output CSV: {self.output_csv}")
        print(f"Include EIS: {self.include_eis}")
        print(f"Loaded {len(self.rn_mapping)} samples")
        print("=" * 60)
    
    def _load_rn_mapping(self) -> dict:
        """Load R, N mapping from JSON"""
        with open(self.rn_mapping_file, encoding='utf-8') as f:
            data = json.load(f)
        
        mapping = {}
        for sample in data['samples']:
            folder = sample['result_folder']
            mapping[folder] = {
                'R': sample['R'],
                'N': sample['N'],
                'L_cm': sample.get('L_cm', 0.12),
                'S_cm2': sample.get('S_cm2', 3.919348),
                'excel_id': sample['excel_sample_id']
            }
        
        return mapping
    
    def convert_all_samples(self) -> pd.DataFrame:
        """Convert all samples"""
        print("\nConverting samples...\n")
        
        all_rows = []
        n_samples = 0
        n_success = 0
        n_failed = 0
        
        for sample_dir in sorted(self.stage0_dir.glob("S8-*")):
            if not sample_dir.is_dir():
                continue
            
            sample_id = sample_dir.name
            n_samples += 1
            
            print(f"[{n_samples}] {sample_id}")
            
            # Get R, N
            rn_info = self.rn_mapping.get(sample_id)
            if not rn_info:
                print(f"  Error: No R/N info")
                n_failed += 1
                continue
            
            print(f"  R={rn_info['R']:.4f}, N={rn_info['N']:.4f}")
            
            try:
                sample_rows = self._convert_sample(sample_dir, sample_id, rn_info)
                
                if sample_rows:
                    all_rows.extend(sample_rows)
                    n_success += 1
                    print(f"  Success: {len(sample_rows)} points")
                else:
                    n_failed += 1
                    print(f"  Error: No valid data")
            
            except Exception as e:
                n_failed += 1
                print(f"  Error: {e}")
        
        print(f"\n" + "=" * 60)
        print(f"Conversion complete")
        print("=" * 60)
        print(f"Total samples: {n_samples}")
        print(f"Success: {n_success}")
        print(f"Failed: {n_failed}")
        print(f"Total points: {len(all_rows)}")
        
        if not all_rows:
            print("\nWarning: No valid data!")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_rows)
        
        # Add derived columns
        df['inv_T_1000'] = 1000.0 / df['T']
        df['ln_sigma'] = np.log(df['sigma'])
        
        # Save
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.output_csv, index=False, encoding='utf-8')
        write_manifest(self.output_csv.with_suffix('.manifest.json'), {
            'stage': 'stage0_to_stage2_conversion',
            'stage0_results_dir': str(self.stage0_dir),
            'rn_mapping_file': str(self.rn_mapping_file),
            'include_eis_features': self.include_eis,
            'output_csv': str(self.output_csv),
            'output_sha256': sha256_file(self.output_csv),
            'rows': len(df),
            'samples': int(df['sample_id'].nunique()) if 'sample_id' in df.columns else None,
            'columns': list(df.columns),
        })
        
        print(f"\nOutput: {self.output_csv}")
        print(f"  Rows: {len(df)}")
        print(f"  Samples: {df['sample_id'].nunique()}")
        print(f"  Columns: {len(df.columns)}")
        
        return df
    
    def _convert_sample(self, sample_dir: Path, sample_id: str, rn_info: dict) -> list:
        """Convert a single sample"""
        rows = []
        
        for scan_dir in sample_dir.glob("*K*"):
            # Load aggregated_results.json
            agg_file = scan_dir / "aggregated_results.json"
            if not agg_file.exists():
                continue
            
            with open(agg_file, encoding='utf-8') as f:
                agg_data = json.load(f)
            
            # Load arrhenius_analysis.json
            arr_file = scan_dir / "arrhenius_analysis.json"
            arr_data = None
            if arr_file.exists():
                with open(arr_file, encoding='utf-8') as f:
                    arr_data = json.load(f)
            
            # Load eis_features.json
            eis_file = scan_dir / "eis_features.json"
            eis_data = None
            if self.include_eis and eis_file.exists():
                with open(eis_file, encoding='utf-8') as f:
                    eis_data = json.load(f)
            
            # Get T_break
            t_break = None
            if arr_data and arr_data.get('success') and arr_data.get('transition_temps_K'):
                t_break = arr_data['transition_temps_K'][0]
            
            # Process each measurement
            for measurement in agg_data['measurements']:
                if not measurement['success'] or measurement['status'] != 'OK':
                    continue
                
                T_K = measurement['temperature_K']
                
                row = {
                    'sample_id': sample_id,
                    'scan_dir': scan_dir.name,
                    'excel_id': rn_info['excel_id'],
                    'R': rn_info['R'],
                    'N': rn_info['N'],
                    'L_cm': rn_info['L_cm'],
                    'S_cm2': rn_info['S_cm2'],
                    'T': T_K,
                    'T_C': measurement['temperature_C'],
                    'sigma': measurement['conductivity_S_per_cm'],
                    'R2': measurement['fit_quality'],
                    'rb_ohm': measurement['rb_ohm']
                }
                
                # Add Ea
                if arr_data and arr_data.get('success'):
                    ea_info = self._assign_ea(T_K, arr_data)
                    row.update(ea_info)
                    row['T_break'] = t_break
                
                # Add EIS features (per-temperature + sample-level T_arc from morphology_summary)
                if eis_data:
                    morph = eis_data.get('morphology_summary') or {}
                    t_arc_v = morph.get('T_arc_K')
                    row['T_arc'] = float(t_arc_v) if t_arc_v is not None else np.nan
                    eis_features = self._find_eis_features(T_K, eis_data)
                    row.update(eis_features)
                else:
                    row['T_arc'] = np.nan
                
                rows.append(row)
        
        return rows
    
    def _assign_ea(self, T: float, arr_data: dict) -> dict:
        """Assign Ea to temperature point"""
        segments = arr_data.get('segments', [])
        
        for seg in segments:
            T_min, T_max = seg['temp_range_K']
            if T_min <= T <= T_max:
                return {
                    'Ea': seg['Ea_eV'],
                    'sigma0': np.exp(seg['intercept']),
                    'ln_sigma0': seg['intercept']
                }
        
        # Use nearest segment
        if segments:
            nearest = min(segments, key=lambda s: abs(T - (s['temp_range_K'][0] + s['temp_range_K'][1]) / 2))
            return {
                'Ea': nearest['Ea_eV'],
                'sigma0': np.exp(nearest['intercept']),
                'ln_sigma0': nearest['intercept']
            }
        
        return {}
    
    def _find_eis_features(self, T: float, eis_data: dict) -> dict:
        """Find EIS features for a given temperature"""
        if not eis_data or 'features_by_temperature' not in eis_data:
            return {}
        
        # Find matching temperature (within 0.1 K)
        for feature in eis_data['features_by_temperature']:
            if abs(feature['temperature_K'] - T) < 0.1:
                char_f = feature.get('characteristic_frequency')
                if char_f is not None and not (isinstance(char_f, float) and np.isnan(char_f)):
                    char_f = float(char_f)
                else:
                    char_f = np.nan
                return {
                    # New meaningful features
                    'data_valid': feature.get('data_valid', False),
                    'R_high_freq_ohm': feature.get('R_high_freq_ohm'),
                    'R_low_freq_ohm': feature.get('R_low_freq_ohm'),
                    'delta_R_ohm': feature.get('delta_R_ohm'),
                    'R_ratio': feature.get('R_ratio'),
                    # Legacy features (for reference)
                    'arc_diameter_ohm': feature.get('arc_diameter_ohm'),
                    'median_zimag_ohm': feature.get('median_zimag_ohm'),
                    # Nyquist morphology (Stage2 MorphologyExpert)
                    'arc_visible': bool(feature.get('arc_visible', False)),
                    'semicircle_visible': bool(feature.get('semicircle_visible', feature.get('arc_visible', False))),
                    'semicircle_quality': feature.get('semicircle_quality'),
                    'characteristic_frequency': char_f,
                    'peak_neg_zimag_ohm': feature.get('peak_neg_zimag_ohm'),
                    'nyquist_peak_ratio': feature.get('nyquist_peak_ratio'),
                    'nyquist_rising_ratio': feature.get('nyquist_rising_ratio'),
                    'nyquist_falling_ratio': feature.get('nyquist_falling_ratio'),
                }
        
        return {}


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert Stage0 to Stage2 input')
    parser.add_argument('--stage0-dir', default='../../output/stage0_results')
    parser.add_argument('--rn-mapping', default='../../output/stage0_results/s8_sample_rn.json')
    parser.add_argument('--output', '-o', default='../../stage2_statistics/data/s8_input.csv')
    parser.add_argument('--no-eis', action='store_true', help='Skip EIS features')
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    stage0_dir = (script_dir / args.stage0_dir).resolve()
    rn_mapping = (script_dir / args.rn_mapping).resolve()
    output_csv = (script_dir / args.output).resolve()
    
    if not stage0_dir.exists():
        print(f"Error: Stage0 directory not found: {stage0_dir}")
        sys.exit(1)
    
    if not rn_mapping.exists():
        print(f"Error: R/N mapping not found: {rn_mapping}")
        sys.exit(1)
    
    converter = Stage0ToStage2Converter(
        stage0_results_dir=str(stage0_dir),
        rn_mapping_file=str(rn_mapping),
        output_csv=str(output_csv),
        include_eis_features=not args.no_eis
    )
    
    df = converter.convert_all_samples()
    
    if not df.empty:
        print(f"\nSuccess!")
        sys.exit(0)
    else:
        print(f"\nFailed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
