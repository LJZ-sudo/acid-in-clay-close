#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
S8 EIS Feature Extractor - Extract EIS features from raw CHI files
"""

import os
import sys
import json
import numpy as np
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STAGE0_DIR = PROJECT_ROOT / "stage0_measurement"
sys.path.insert(0, str(STAGE0_DIR))

# Import Stage0 modules
try:
    from modules.io_utils.chi_parser import parse_chi_file
    from modules.analysis.data_quality import assess_data_quality
    STAGE0_AVAILABLE = True
except ImportError:
    STAGE0_AVAILABLE = False
    print("Warning: Stage0 modules not available")


def _nyquist_arc_branch(
    freq_1d: np.ndarray,
    neg: np.ndarray,
    zr: np.ndarray,
    *,
    after_frac: float = 0.6,
    rise_thr: float = 0.43,
    fall_thr: float = 0.38,
) -> Optional[Dict[str, Any]]:
    """
    One ordering of points: interior maximum of -Z'', rising/falling heuristics.

    ``after_frac`` of the post-peak segment is used for ``falling_ratio`` (skip lowest-f tail).
    """
    n = len(neg)
    arc_diam = float(zr.max() - zr.min())
    if not np.isfinite(arc_diam) or arc_diam <= 0:
        return None
    lo = max(1, n // 7)
    hi = n - lo
    if hi <= lo + 2:
        return None

    peak_rel = int(np.argmax(neg[lo:hi]))
    peak_idx = lo + peak_rel
    peak_neg = float(neg[peak_idx])
    char_freq = float(freq_1d[peak_idx])
    peak_ratio = peak_neg / (arc_diam + 1e-12)

    before = neg[: peak_idx + 1]
    after = neg[peak_idx:]
    rising_ratio = float(np.mean(np.diff(before) > 0)) if len(before) >= 2 else 0.0

    na = len(after)
    if na >= 4:
        n_desc = max(2, int(np.ceil(na * after_frac)))
        n_desc = min(n_desc, na)
        after_desc = after[:n_desc]
    else:
        after_desc = after
    falling_ratio = (
        float(np.mean(np.diff(after_desc) < 0)) if len(after_desc) >= 2 else 0.0
    )

    ok = bool(
        peak_ratio < 3.0
        and rising_ratio > rise_thr
        and falling_ratio > fall_thr
        and peak_neg > 1e-9
    )
    pr_s = max(0.0, min(1.0, (3.0 - peak_ratio) / 3.0)) if peak_ratio < 3.0 else 0.0
    quality = float(
        np.clip(
            0.35 * pr_s
            + 0.35 * min(rising_ratio / 0.5, 1.0)
            + 0.30 * min(falling_ratio / 0.5, 1.0),
            0.0,
            1.0,
        )
    )
    return {
        "peak_ratio": float(peak_ratio),
        "rising_ratio": rising_ratio,
        "falling_ratio": falling_ratio,
        "ok": ok,
        "quality": quality,
        "char_freq": char_freq,
        "peak_neg": peak_neg,
    }


def compute_nyquist_arc_metrics(
    freq: np.ndarray,
    zreal: np.ndarray,
    zimag: np.ndarray,
    trim_lowfreq: int = 5,
) -> Dict:
    """
    Classify Nyquist arc visibility using -Z'' (i.e. -z_imag).

    Uses three **OR** branches (same physics, different point orderings / thresholds):

    1. **Instrument sweep order** (CHI DTA is typically high f → low f).
    2. **Frequency ascending order** with default rise/fall thresholds.
    3. **Frequency ascending** with slightly relaxed rise/fall and a longer post-peak
       window for ``falling_ratio`` (weak or noisy arcs).

    ``arc_visible`` is True if any branch passes. Exported ``nyquist_*`` columns use the
    first passing branch (sweep → strict f-sorted → relaxed f-sorted), else the
    highest-quality branch.
    """
    nan = float("nan")
    defaults: Dict = {
        "arc_visible": False,
        "semicircle_quality": 0.0,
        "characteristic_frequency_Hz": nan,
        "peak_neg_zimag_ohm": nan,
        "nyquist_peak_ratio": nan,
        "nyquist_rising_ratio": nan,
        "nyquist_falling_ratio": nan,
    }
    n_raw = len(freq)
    if n_raw <= trim_lowfreq + 10:
        return defaults

    freq_c = np.asarray(freq[trim_lowfreq:], dtype=float)
    zr = np.asarray(zreal[trim_lowfreq:], dtype=float)
    zi = np.asarray(zimag[trim_lowfreq:], dtype=float)
    n = len(freq_c)
    if n < 15:
        return defaults

    neg_sweep = (-zi).astype(float)
    br_sw = _nyquist_arc_branch(freq_c, neg_sweep, zr)
    if br_sw is None:
        return defaults

    order = np.argsort(freq_c)
    br_f = _nyquist_arc_branch(
        freq_c[order], neg_sweep[order], zr[order]
    )
    if br_f is None:
        br_f = br_sw

    # Relaxed f-sorted branch: recovers weak / noisy arcs where strict rise/fall fails
    br_fr = _nyquist_arc_branch(
        freq_c[order],
        neg_sweep[order],
        zr[order],
        after_frac=0.65,
        rise_thr=0.38,
        fall_thr=0.32,
    )
    if br_fr is None:
        br_fr = br_f

    arc_visible = bool(br_sw["ok"] or br_f["ok"] or br_fr["ok"])

    if br_sw["ok"]:
        primary = br_sw
    elif br_f["ok"]:
        primary = br_f
    elif br_fr["ok"]:
        primary = br_fr
    else:
        primary = max((br_sw, br_f, br_fr), key=lambda b: b["quality"])

    qmax = max(br_sw["quality"], br_f["quality"], br_fr["quality"])

    return {
        "arc_visible": arc_visible,
        "semicircle_quality": float(qmax),
        "characteristic_frequency_Hz": primary["char_freq"],
        "peak_neg_zimag_ohm": primary["peak_neg"],
        "nyquist_peak_ratio": primary["peak_ratio"],
        "nyquist_rising_ratio": primary["rising_ratio"],
        "nyquist_falling_ratio": primary["falling_ratio"],
    }


def calculate_temperature_from_chi(filepath: str) -> Dict:
    """Calculate temperature from CHI file (reuse stage0_processing logic)"""
    filename = os.path.basename(filepath)
    m = re.search(r'#(\d+)', filename)
    file_seq = int(m.group(1)) if m else 1
    
    # Parse temperature range from filename
    params = {
        'start_temp_K': 300.0,
        'target_end_temp_K': 120.0,
        'temp_rate_K_per_min': 3.0,
        'is_heating': False
    }
    
    m = re.search(r'(\d+)-(\d+)K', filename)
    if m:
        temp1, temp2 = float(m.group(1)), float(m.group(2))
        params['start_temp_K'] = temp1
        params['target_end_temp_K'] = temp2
        params['is_heating'] = temp1 < temp2
    
    m = re.search(r'(\d+(?:\.\d+)?)K-min', filename)
    if m:
        params['temp_rate_K_per_min'] = float(m.group(1))
    
    # Read timestamp from CHI file
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
    
    # Find reference time (file #1)
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
    
    # Calculate temperature
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
        'elapsed_minutes': elapsed_minutes
    }


def extract_eis_features_from_chi_with_temp(chi_filepath: str, T_K: float, T_C: float) -> Dict:
    """
    Extract EIS features from a single CHI file with given temperature
    
    Method: Extract meaningful resistance values from narrow frequency range (0-55 Hz)
    - Remove low-frequency artifacts (first 5 points)
    - Extract R_high_freq (55 Hz, approximates grain resistance)
    - Extract R_low_freq (5-10 Hz, approximates total resistance)
    - Calculate delta_R (interface/grain boundary contribution)
    """
    if not STAGE0_AVAILABLE:
        return {'success': False, 'error': 'Stage0 modules not available'}
    
    # Parse CHI file
    try:
        parse_result = parse_chi_file(chi_filepath)
        if not parse_result['success']:
            return {'success': False, 'error': 'Failed to parse CHI file'}
        
        freq = parse_result['frequencies']
        zreal = parse_result['z_real']
        zimag = parse_result['z_imag']
    except Exception as e:
        return {'success': False, 'error': f'Parse error: {str(e)}'}
    
    # Remove low-frequency artifacts (first 5 points: 0-4 Hz)
    # These points have huge inductive artifacts (e.g., 300,046.9 Ω at 0 Hz)
    if len(freq) > 5:
        freq_clean = freq[5:]
        zreal_clean = zreal[5:]
        zimag_clean = zimag[5:]
    else:
        freq_clean = freq
        zreal_clean = zreal
        zimag_clean = zimag
    
    # Extract meaningful features from cleaned data
    try:
        # In Nyquist plot, Zreal increases with decreasing frequency
        # So zreal_clean[0] is at ~5 Hz (low freq), zreal_clean[-1] is at ~55 Hz (high freq)
        # But we want R_low_freq to be the LARGER value (total resistance)
        
        # R_high_freq: resistance at highest frequency (≈55 Hz)
        # This approximates the grain (bulk) resistance (should be SMALLER)
        R_high_freq = float(min(zreal_clean)) if len(zreal_clean) > 0 else 0.0
        
        # R_low_freq: resistance at lowest cleaned frequency (≈5-10 Hz)
        # This approximates the total resistance (should be LARGER)
        R_low_freq = float(max(zreal_clean)) if len(zreal_clean) > 0 else 0.0
        
        # delta_R: difference between low and high frequency resistance
        # This represents the contribution of grain boundaries and interfaces
        delta_R = R_low_freq - R_high_freq
        
        # R_ratio: ratio of total to grain resistance
        # Higher ratio indicates more significant interface/grain boundary effects
        R_ratio = R_low_freq / R_high_freq if R_high_freq > 0 else 1.0
        
        # Data quality check
        data_valid = (
            len(freq_clean) >= 10 and  # Sufficient data points
            R_high_freq > 0 and         # Positive resistance
            R_low_freq > 0 and          # Positive resistance
            delta_R >= 0 and            # Physical constraint
            R_ratio >= 1.0              # Physical constraint
        )
        
        # Additional metrics for reference (kept for compatibility)
        # Note: These should NOT be interpreted as standard Nyquist semicircle features
        arc_diameter = float(zreal_clean.max() - zreal_clean.min())
        median_zimag = float(np.median(np.abs(zimag_clean)))

        nyq = compute_nyquist_arc_metrics(freq, zreal, zimag, trim_lowfreq=5)

    except Exception as e:
        # If extraction fails, return invalid data
        R_high_freq = 0.0
        R_low_freq = 0.0
        delta_R = 0.0
        R_ratio = 1.0
        data_valid = False
        arc_diameter = 0.0
        median_zimag = 0.0
        nyq = {
            'arc_visible': False,
            'semicircle_quality': 0.0,
            'characteristic_frequency_Hz': float('nan'),
            'peak_neg_zimag_ohm': float('nan'),
            'nyquist_peak_ratio': float('nan'),
            'nyquist_rising_ratio': float('nan'),
            'nyquist_falling_ratio': float('nan'),
        }
    
    return {
        'success': True,
        'temperature_K': float(T_K),
        'temperature_C': float(T_C),
        # New meaningful features
        'data_valid': bool(data_valid),
        'R_high_freq_ohm': R_high_freq,
        'R_low_freq_ohm': R_low_freq,
        'delta_R_ohm': delta_R,
        'R_ratio': R_ratio,
        # Legacy features (for reference only, do NOT interpret as semicircle)
        'arc_diameter_ohm': arc_diameter,
        'median_zimag_ohm': median_zimag,
        # Nyquist -Z'' arc shape (uses corrected parse_chi_file Zreal/Zimag)
        'arc_visible': bool(nyq['arc_visible']),
        'semicircle_visible': bool(nyq['arc_visible']),
        'semicircle_quality': float(nyq['semicircle_quality']),
        'characteristic_frequency': float(nyq['characteristic_frequency_Hz']),
        'peak_neg_zimag_ohm': float(nyq['peak_neg_zimag_ohm']),
        'nyquist_peak_ratio': nyq['nyquist_peak_ratio'],
        'nyquist_rising_ratio': nyq['nyquist_rising_ratio'],
        'nyquist_falling_ratio': nyq['nyquist_falling_ratio'],
    }


def extract_sample_features(
    sample_id: str,
    scan_dir: str,
    raw_eis_base: Path,
    aggregated_results: Dict,
    output_file: Optional[Path] = None
) -> Dict:
    """Extract EIS features using temperatures from aggregated_results"""
    chi_dir = raw_eis_base / sample_id / scan_dir
    
    if not chi_dir.exists():
        print(f"  Error: CHI directory not found: {chi_dir}")
        return None
    
    print(f"  Processing {len(aggregated_results['measurements'])} measurements")
    
    features_by_temp = []
    n_success = 0
    n_failed = 0
    
    # Process each measurement from aggregated_results
    for measurement in aggregated_results['measurements']:
        if not measurement['success']:
            continue
        
        # Get temperature from aggregated_results (already calculated by Stage0)
        T_K = measurement['temperature_K']
        T_C = measurement['temperature_C']
        
        # Find corresponding CHI file
        # The filepath in aggregated_results points to temp_chi_files, but we need the original
        # Extract the sequence number from filename
        filepath = measurement['filepath']
        import re
        seq_match = re.search(r'seq(\d+)', filepath)
        if not seq_match:
            n_failed += 1
            continue
        
        seq_num = int(seq_match.group(1))
        
        # Find the original CHI file with this sequence number
        chi_pattern = f"*_#{seq_num}.DTA"
        chi_files = list(chi_dir.glob(chi_pattern))
        
        if not chi_files:
            n_failed += 1
            continue
        
        chi_file = chi_files[0]
        
        # Extract EIS features (using Stage0's temperature, not recalculating)
        result = extract_eis_features_from_chi_with_temp(str(chi_file), T_K, T_C)
        if result['success']:
            n_success += 1
            features_by_temp.append(result)
        else:
            n_failed += 1
    
    print(f"    Success: {n_success}, Failed: {n_failed}")
    
    # Sort by temperature (high to low)
    features_by_temp.sort(key=lambda x: x['temperature_K'], reverse=True)
    
    # Calculate statistics
    n_valid = sum(1 for f in features_by_temp if f.get('data_valid', False))
    
    # Calculate average R_ratio (indicator of interface effects)
    valid_features = [f for f in features_by_temp if f.get('data_valid', False)]
    avg_R_ratio = np.mean([f['R_ratio'] for f in valid_features]) if valid_features else 1.0
    
    print(f"    Valid data: {n_valid}/{len(features_by_temp)}")
    print(f"    Avg R_ratio: {avg_R_ratio:.3f}")

    # First temperature (ascending T) where Nyquist arc_visible is True -> T_arc_K
    n_arc = sum(1 for f in features_by_temp if f.get('arc_visible'))
    t_arc_k = None
    for f in sorted(features_by_temp, key=lambda x: x['temperature_K']):
        if f.get('arc_visible'):
            t_arc_k = float(f['temperature_K'])
            break
    
    # Build result
    result = {
        'sample_id': sample_id,
        'scan_dir': scan_dir,
        'n_points': len(features_by_temp),
        'n_success': n_success,
        'n_failed': n_failed,
        'features_by_temperature': features_by_temp,
        'data_quality_summary': {
            'n_valid_points': int(n_valid),
            'total_points': len(features_by_temp),
            'valid_ratio': float(n_valid / len(features_by_temp)) if features_by_temp else 0.0,
            'avg_R_ratio': float(avg_R_ratio),
            'note': 'R_ratio > 1 indicates significant interface/grain boundary contribution'
        },
        'morphology_summary': {
            'T_arc_K': t_arc_k,
            'n_arc_visible': int(n_arc),
            'detection': 'nyquist_neg_zimag_interior_peak',
        },
        'extraction_timestamp': datetime.now().isoformat()
    }
    
    # Save
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"    Saved: {output_file}")
    
    return result


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract EIS features from raw CHI files')
    parser.add_argument('sample_id', help='Sample ID (e.g., S8-2-1-1)')
    parser.add_argument('scan_dir', help='Scan directory (e.g., 300-120K 3K-min)')
    parser.add_argument('--raw-eis-base', default='../../data/raw_eis/S8', help='Raw EIS base directory')
    parser.add_argument('--stage0-results', default='../../output/stage0_results', help='Stage0 results directory')
    parser.add_argument('--output', '-o', help='Output file path')
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    raw_eis_base = (script_dir / args.raw_eis_base).resolve()
    stage0_results = (script_dir / args.stage0_results).resolve()
    
    # Load aggregated_results
    agg_file = stage0_results / args.sample_id / args.scan_dir / "aggregated_results.json"
    if not agg_file.exists():
        print(f"Error: aggregated_results.json not found: {agg_file}")
        sys.exit(1)
    
    with open(agg_file, encoding='utf-8') as f:
        agg_data = json.load(f)
    
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = stage0_results / args.sample_id / args.scan_dir / "eis_features.json"
    
    print(f"\nExtracting EIS features:")
    print(f"  Sample: {args.sample_id}")
    print(f"  Scan: {args.scan_dir}")
    print(f"  Raw EIS: {raw_eis_base}")
    
    result = extract_sample_features(
        sample_id=args.sample_id,
        scan_dir=args.scan_dir,
        raw_eis_base=raw_eis_base,
        aggregated_results=agg_data,
        output_file=output_file
    )
    
    if result:
        print(f"\nSuccess!")
        sys.exit(0)
    else:
        print(f"\nFailed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
