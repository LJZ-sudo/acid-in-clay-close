#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
S8 Batch Processing Script (Final Version)

Batch processes all 41 S8 samples with DTA temperature extraction
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import shutil
import subprocess

# Fix encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Repo root: .../V1.0-qianduan-mainline (this file lives in code/stage0_processing/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STAGE0_DIR = PROJECT_ROOT / "stage0_measurement"
sys.path.insert(0, str(STAGE0_DIR))

from modules.io_utils import dta_parser
import re
from datetime import datetime

# Config
DATA_BASE_DIR = PROJECT_ROOT / "data" / "raw_eis" / "S8"
OUTPUT_BASE_DIR = PROJECT_ROOT / "output" / "stage0_results"
SAMPLE_THICKNESS_CM = 0.12
SAMPLE_AREA_CM2 = 3.919348


def _calculate_temperature_from_dta_fixed(filepath):
    """Fixed temperature calculation - uses actual calculated temperature"""
    filename = os.path.basename(filepath)
    m = re.search(r'#(\d+)', filename)
    file_seq = int(m.group(1)) if m else 1
    
    params = {'start_temp_K': 300.0, 'target_end_temp_K': 120.0, 'temp_rate_K_per_min': 3.0, 'is_heating': False}
    m = re.search(r'(\d+)-(\d+)K', filename)
    if m:
        temp1, temp2 = float(m.group(1)), float(m.group(2))
        params['start_temp_K'] = temp1
        params['target_end_temp_K'] = temp2
        params['is_heating'] = temp1 < temp2
    m = re.search(r'(\d+(?:\.\d+)?)K-min', filename)
    if m:
        params['temp_rate_K_per_min'] = float(m.group(1))
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        date_match = re.search(r'DATE\s+LABEL\s+(\d{1,2}/\d{1,2}/\d{4})', content)
        time_match = re.search(r'TIME\s+LABEL\s+(\d{1,2}:\d{2}:\d{2})', content)
        if not (date_match and time_match):
            return {'success': False, 'error': 'No timestamp found'}
        timestamp = datetime.strptime(f"{date_match.group(1)} {time_match.group(1)}", "%m/%d/%Y %H:%M:%S")
    except Exception as e:
        return {'success': False, 'error': f'Failed to read timestamp: {str(e)}'}
    
    folder_path = os.path.dirname(filepath)
    first_filename = re.sub(r'#\d+', '#1', filename)
    first_file_path = os.path.join(folder_path, first_filename)
    
    try:
        if os.path.exists(first_file_path):
            with open(first_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            date_match = re.search(r'DATE\s+LABEL\s+(\d{1,2}/\d{1,2}/\d{4})', content)
            time_match = re.search(r'TIME\s+LABEL\s+(\d{1,2}:\d{2}:\d{2})', content)
            if date_match and time_match:
                reference_time = datetime.strptime(f"{date_match.group(1)} {time_match.group(1)}", "%m/%d/%Y %H:%M:%S")
            else:
                reference_time = timestamp
        else:
            reference_time = timestamp
    except:
        reference_time = timestamp
    
    elapsed_minutes = (timestamp - reference_time).total_seconds() / 60.0
    start_temp_K = params['start_temp_K']
    rate = params['temp_rate_K_per_min']
    is_heating = params['is_heating']
    
    if is_heating:
        calculated_temp_K = start_temp_K + rate * elapsed_minutes
    else:
        calculated_temp_K = start_temp_K - rate * elapsed_minutes
    
    temp_C = calculated_temp_K - 273.15
    
    return {
        'success': True,
        'temperature_K': calculated_temp_K,
        'temperature_C': temp_C,
        'file_sequence': file_seq,
        'error': None
    }


def convert_dta_to_chi_with_temp(dta_file, output_dir):
    """Convert DTA to CHI format with temperature in filename"""
    try:
        temp_result = _calculate_temperature_from_dta_fixed(str(dta_file))
        
        if not temp_result['success']:
            return {'success': False, 'temperature_C': None, 'error': 'Temperature extraction failed'}
        
        temp_C = temp_result['temperature_C']
        file_seq = temp_result['file_sequence']
        
        # Parse DTA for EIS data
        with open(dta_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        data_lines = []
        in_table = False
        for line in lines:
            if 'ZCURVE' in line and 'TABLE' in line:
                in_table = True
                continue
            if in_table:
                if line.strip() and not line.startswith('#') and not line.startswith('Pt'):
                    parts = line.strip().split('\t')
                    if len(parts) >= 5:
                        try:
                            freq = float(parts[2])
                            zreal = float(parts[3])
                            zimag = float(parts[4])
                            data_lines.append(f"{freq}\t{zreal}\t{zimag}\n")
                        except (ValueError, IndexError):
                            continue
        
        if not data_lines:
            return {'success': False, 'temperature_C': temp_C, 'error': 'No EIS data'}
        
        sample_name = dta_file.parent.parent.name
        output_filename = f"{sample_name}_T{temp_C:.1f}C_seq{file_seq:02d}.txt"
        output_file = output_dir / output_filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Frequency\tZreal\tZimag\n")
            f.writelines(data_lines)
        
        return {'success': True, 'output_file': str(output_file), 'temperature_C': temp_C, 'error': None}
    
    except Exception as e:
        return {'success': False, 'temperature_C': None, 'error': str(e)}


def process_sample_scan(sample_name, scan_name, data_dir, output_base_dir, verbose=False):
    """Process one sample scan"""
    if verbose:
        print(f"\n{'='*70}")
        print(f"Sample: {sample_name} / Scan: {scan_name}")
        print('='*70)
    
    temp_dir = output_base_dir / sample_name / scan_name / "temp_chi_files"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    dta_files = sorted(data_dir.glob("*.DTA"))
    if not dta_files:
        return {'success': False, 'sample': sample_name, 'scan': scan_name, 'error': 'No DTA files'}
    
    if verbose:
        print(f"Found {len(dta_files)} DTA files, converting...")
    
    converted = 0
    for dta_file in dta_files:
        result = convert_dta_to_chi_with_temp(dta_file, temp_dir)
        if result['success']:
            converted += 1
    
    if verbose:
        print(f"Converted: {converted}/{len(dta_files)} files")
    
    if converted == 0:
        return {'success': False, 'sample': sample_name, 'scan': scan_name, 'error': 'No files converted'}
    
    if verbose:
        print("Running EIS analysis...")
    
    output_dir = output_base_dir / sample_name / scan_name
    wrapper_script = Path(__file__).parent / "run_stage0_wrapper.py"
    
    cmd = [
        sys.executable,
        str(wrapper_script),
        "--data_dir", str(temp_dir),
        "--output_dir", str(output_dir),
        "--material", sample_name,
        "--chi_pattern", "*.txt",
        "--thickness", str(SAMPLE_THICKNESS_CM),
        "--area", str(SAMPLE_AREA_CM2),
    ]
    
    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False
        )
        
        if process.returncode == 0:
            # Sort results by temperature
            _sort_results_by_temperature(output_dir)
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        if process.returncode == 0:
            if verbose:
                print("[SUCCESS]")
            return {'success': True, 'sample': sample_name, 'scan': scan_name, 'error': None}
        else:
            if verbose:
                print(f"[ERROR] Analysis failed")
            return {'success': False, 'sample': sample_name, 'scan': scan_name, 'error': f'Analysis failed'}
    
    except Exception as e:
        return {'success': False, 'sample': sample_name, 'scan': scan_name, 'error': str(e)}


def _sort_results_by_temperature(output_dir):
    """Sort aggregated results by temperature"""
    aggregated_file = output_dir / "aggregated_results.json"
    if not aggregated_file.exists():
        return
    
    try:
        with open(aggregated_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Sort measurements by temperature_C (ascending)
        if 'measurements' in data and data['measurements']:
            data['measurements'].sort(key=lambda x: x.get('temperature_C', 0))
        
        # Rebuild arrays in sorted order
        if 'measurements' in data:
            data['temperatures_K'] = [m['temperature_K'] for m in data['measurements'] 
                                      if m.get('success') and m.get('rb_ohm') is not None]
            data['conductivities'] = [m['conductivity_S_per_cm'] for m in data['measurements'] 
                                      if m.get('success') and m.get('rb_ohm') is not None]
            data['rb_values'] = [m['rb_ohm'] for m in data['measurements'] 
                                 if m.get('success') and m.get('rb_ohm') is not None]
        
        # Save sorted results
        with open(aggregated_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    except Exception as e:
        print(f"Warning: Failed to sort results: {e}")


def scan_samples():
    """Scan all sample directories"""
    samples = []
    
    if not DATA_BASE_DIR.exists():
        return samples
    
    for sample_dir in sorted(DATA_BASE_DIR.iterdir()):
        if not sample_dir.is_dir():
            continue
        
        sample_name = sample_dir.name
        scan_dirs = []
        
        for scan_dir in sorted(sample_dir.iterdir()):
            if not scan_dir.is_dir():
                continue
            
            dta_files = list(scan_dir.glob("*.DTA"))
            if dta_files:
                scan_dirs.append(scan_dir.name)
        
        if scan_dirs:
            samples.append((sample_name, scan_dirs))
    
    return samples


def main():
    parser = argparse.ArgumentParser(description="S8 Batch Processing")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop on first error")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()
    
    print("=" * 70)
    print("S8 Batch Processing")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data dir: {DATA_BASE_DIR}")
    print(f"Output dir: {OUTPUT_BASE_DIR}")
    print(f"Sample params: L={SAMPLE_THICKNESS_CM} cm, S={SAMPLE_AREA_CM2} cm^2")
    print("=" * 70)
    
    print("\nScanning samples...")
    samples = scan_samples()
    
    if not samples:
        print("[ERROR] No samples found")
        return 1
    
    total_samples = len(samples)
    total_scans = sum(len(scans) for _, scans in samples)
    
    print(f"[OK] Found {total_samples} samples, {total_scans} scans total")
    
    if not args.verbose:
        print("\nSample list:")
        for i, (sample_name, scan_dirs) in enumerate(samples, 1):
            print(f"  {i:2d}. {sample_name} ({len(scan_dirs)} scans)")
    
    if args.dry_run:
        print("\n[DRY-RUN] Would process all samples")
        return 0
    
    print("\nStarting batch processing...")
    print("=" * 70)
    
    results = []
    scan_counter = 0
    start_time = datetime.now()
    
    for sample_idx, (sample_name, scan_dirs) in enumerate(samples, 1):
        if not args.verbose:
            print(f"\n[{sample_idx}/{total_samples}] {sample_name}")
        
        for scan_idx, scan_name in enumerate(scan_dirs, 1):
            scan_counter += 1
            
            if not args.verbose:
                print(f"  [{scan_idx}/{len(scan_dirs)}] {scan_name} [{scan_counter}/{total_scans}]...", end=' ')
            
            data_dir = DATA_BASE_DIR / sample_name / scan_name
            
            result = process_sample_scan(
                sample_name, scan_name, data_dir, OUTPUT_BASE_DIR, verbose=args.verbose
            )
            
            results.append(result)
            
            if result['success']:
                if not args.verbose:
                    print("[OK]")
            else:
                if not args.verbose:
                    print(f"[ERROR] {result['error']}")
                
                if args.stop_on_error:
                    print("\n[STOP] Error encountered")
                    break
        
        if args.stop_on_error and not results[-1]['success']:
            break
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Save summary
    summary_file = OUTPUT_BASE_DIR / "batch_processing_summary.json"
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_scans': len(results),
        'successful': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'thickness_cm': SAMPLE_THICKNESS_CM,
        'area_cm2': SAMPLE_AREA_CM2,
        'duration_seconds': duration,
        'results': results
    }
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "=" * 70)
    print("Batch Processing Complete")
    print("=" * 70)
    
    successful = summary['successful']
    failed = summary['failed']
    
    print(f"Total scans: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Duration: {duration:.2f} sec ({duration/60:.2f} min)")
    
    if failed > 0:
        print(f"\nFailed scans:")
        for r in results:
            if not r['success']:
                print(f"  [ERROR] {r['sample']} / {r['scan']}: {r['error']}")
    
    print(f"\nOutput: {OUTPUT_BASE_DIR}")
    print(f"Summary: {summary_file}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED]")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
