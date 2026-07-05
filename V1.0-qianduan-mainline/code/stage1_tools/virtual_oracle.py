#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Virtual Oracle - Offline Closed-Loop Replay Tool

Simulates experimental closed-loop by:
1. Reading AI-recommended R/N from next_experiment_recipe.json
2. Finding nearest-neighbor sample from s8_sample_rn.json
3. Copying real experimental data to stage1_optimization input directory
4. Generating experiment_metadata.json for traceability

Usage:
    python virtual_oracle.py
    python virtual_oracle.py --verbose
    python virtual_oracle.py --dry-run

Author: Auto-generated
Date: 2026-04-10
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import math

# Fix encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================
# Path Configuration (relative to project root)
# ============================================================

# Repo root: .../V1.0-qianduan-mainline (this file lives in code/stage1_tools/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from shared.manifest import write_manifest
from _campaign_paths import DEFAULT_REPLAY_CAMPAIGN, load_campaign_storage

LAST_ORACLE_MATCH_PATH = PROJECT_ROOT / "stage1_optimization" / "output" / "last_virtual_oracle_match.json"
INVENTORY_PATH = PROJECT_ROOT.parent / "experiments" / "output" / "stage0_results" / "s8_sample_rn.json"
REAL_DATA_ROOT = PROJECT_ROOT.parent / "experiments" / "output" / "stage0_results"
STAGE1_INPUT_DIR = PROJECT_ROOT / "stage1_optimization" / "demo_stage0_results"

_STORAGE = load_campaign_storage(DEFAULT_REPLAY_CAMPAIGN)
AI_RECIPE_PATH = _STORAGE.next_recipe
LAST_ORACLE_MATCH_PATH = _STORAGE.output_dir / "last_virtual_oracle_match.json"
HISTORY_DB_PATH = _STORAGE.history_db


def configure_campaign_paths(campaign_config: Optional[str], *, allow_real_campaign: bool = False) -> None:
    """Point the replay helper at campaign storage without silently using real AiCE history."""
    global _STORAGE, AI_RECIPE_PATH, LAST_ORACLE_MATCH_PATH, HISTORY_DB_PATH
    _STORAGE = load_campaign_storage(campaign_config, default_campaign=DEFAULT_REPLAY_CAMPAIGN)
    if _STORAGE.is_attapulgite_real and not allow_real_campaign:
        raise RuntimeError(
            "Virtual Oracle is an offline S8 replay tool. Refusing to use "
            "attapulgite real campaign storage without --allow-real-campaign."
        )
    AI_RECIPE_PATH = _STORAGE.next_recipe
    LAST_ORACLE_MATCH_PATH = _STORAGE.output_dir / "last_virtual_oracle_match.json"
    HISTORY_DB_PATH = _STORAGE.history_db

# ============================================================
# Core Functions
# ============================================================

def load_ai_recommendation(selection_source: str = "final_recipe") -> Optional[Dict]:
    """Load AI-recommended R/N from recipe JSON"""
    if not AI_RECIPE_PATH.exists():
        return None
    
    try:
        with open(AI_RECIPE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        optimizer_params = data.get('optimizer_suggestion') or {}
        recipe_params = (data.get('recipe') or {}).get('recommended_parameters') or {}

        selected_params = recipe_params if selection_source == "final_recipe" else optimizer_params
        r_val = selected_params.get('R')
        n_val = selected_params.get('N')

        if r_val is None or n_val is None:
            return None

        return {
            'R': r_val,
            'N': n_val,
            'selection_source': selection_source,
            'selected_parameters': selected_params,
            'optimizer_suggestion': optimizer_params,
            'recommended_parameters': recipe_params,
            'optimizer_vs_llm_delta': data.get('optimizer_vs_llm_delta', {}),
            'full_recipe': data
        }
    
    except Exception as e:
        print(f"[ERROR] Failed to load AI recipe: {e}")
        return None


def load_inventory() -> Optional[Dict]:
    """Load sample inventory with R/N values"""
    if not INVENTORY_PATH.exists():
        return None
    
    try:
        with open(INVENTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load inventory: {e}")
        return None


def calculate_euclidean_distance(r1: float, n1: float, r2: float, n2: float) -> float:
    """
    Calculate normalized Euclidean distance between two (R, N) points
    
    使用标准化距离防止量纲灾难：
    - R range: [0.0, 1.041], span = 1.041
    - N range: [1.182, 7.006], span = 5.824
    - N 的跨度是 R 的 5.6 倍，如果不归一化，N 会主导距离计算
    
    归一化后，R 和 N 的权重相等
    """
    # 实际参数范围（从 s8_sample_rn.json 统计）
    R_MIN, R_MAX = 0.0, 1.041
    N_MIN, N_MAX = 1.182, 7.006
    
    # 归一化到 [0, 1]
    r1_norm = (r1 - R_MIN) / (R_MAX - R_MIN) if R_MAX > R_MIN else 0.0
    r2_norm = (r2 - R_MIN) / (R_MAX - R_MIN) if R_MAX > R_MIN else 0.0
    n1_norm = (n1 - N_MIN) / (N_MAX - N_MIN) if N_MAX > N_MIN else 0.0
    n2_norm = (n2 - N_MIN) / (N_MAX - N_MIN) if N_MAX > N_MIN else 0.0
    
    # 计算标准化欧几里得距离
    return math.sqrt((r1_norm - r2_norm)**2 + (n1_norm - n2_norm)**2)


def calculate_combined_score(sample_folder: Path, scan_subfolder: str) -> float:
    """
    计算样品的 combined_score = log10(conductivity) - 5.0 * Ea_high
    
    Args:
        sample_folder: 样品文件夹路径
        scan_subfolder: 扫描子文件夹名称
    
    Returns:
        combined_score (越大越好)，如果计算失败返回 -999.0
    """
    agg_file = sample_folder / scan_subfolder / "aggregated_results.json"
    arr_file = sample_folder / scan_subfolder / "arrhenius_analysis.json"
    
    try:
        # 读取室温电导率（24-26°C，即 297-299K）
        if not agg_file.exists():
            return -999.0
        
        with open(agg_file, 'r', encoding='utf-8') as f:
            agg_data = json.load(f)
        
        # aggregated_results.json 的结构是 measurements 数组
        conductivity = None
        for measurement in agg_data.get('measurements', []):
            temp_K = measurement.get('temperature_K', 0)
            if 297 <= temp_K <= 299:  # 24-26°C
                conductivity = measurement.get('conductivity_S_per_cm')
                break
        
        if conductivity is None or conductivity <= 0:
            return -999.0
        
        # 读取 Ea_high（使用智能提取策略，与 state0_parser 一致）
        if not arr_file.exists():
            return -999.0
        
        with open(arr_file, 'r', encoding='utf-8') as f:
            arr_data = json.load(f)
        
        if not arr_data.get('success'):
            return -999.0
        
        segments = arr_data.get('segments', [])
        if not segments:
            return -999.0
        
        # 智能提取主导段的 Ea（选择数据点最多的段）
        max_points = max(s.get('n_points', 0) for s in segments)
        candidates = [s for s in segments if s.get('n_points', 0) == max_points]
        
        if len(candidates) > 1:
            # 多个段数据点相同，选择温度最高的
            main_seg = max(candidates, key=lambda s: s.get('temp_range_K', [0, 0])[1])
        else:
            main_seg = candidates[0]
        
        ea_high = main_seg.get('Ea_eV', 0.0)
        
        # 计算 combined_score
        combined_score = math.log10(conductivity) - 5.0 * ea_high
        
        return combined_score
    
    except Exception as e:
        # 静默失败，返回最低分
        return -999.0


def get_used_samples_from_history() -> Tuple[set, Dict]:
    """
    从历史数据库中获取已使用的样品列表及使用次数
    
    Returns:
        tuple: (used_samples_set, sample_use_count_dict)
            - used_samples_set: 已使用样品的 (R, N) 集合
            - sample_use_count_dict: {(R, N): count} 使用次数字典
    """
    history_path = HISTORY_DB_PATH
    
    if not history_path.exists():
        return set(), {}
    
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        used_samples = set()
        sample_use_count = {}
        
        for trial in history.get('trials', []):
            params = trial.get('parameters', {})
            r = params.get('R')
            n = params.get('N')
            if r is not None and n is not None:
                # 使用 (R, N) 元组作为唯一标识
                key = (round(r, 6), round(n, 6))
                used_samples.add(key)
                sample_use_count[key] = sample_use_count.get(key, 0) + 1
        
        return used_samples, sample_use_count
    except Exception as e:
        print(f"[WARNING] Failed to load history: {e}")
        return set(), {}


def find_nearest_sample(target_r: float, target_n: float, inventory: Dict, 
                       avoid_duplicates: bool = True, duplicate_penalty: float = 2.0,
                       max_reuse_count: int = 3) -> Optional[Dict]:
    """
    Find nearest sample in inventory by Euclidean distance
    
    Args:
        target_r: 目标R值
        target_n: 目标N值
        inventory: 样品库
        avoid_duplicates: 是否避免重复样品
        duplicate_penalty: 重复样品的距离惩罚倍数
        max_reuse_count: 单个样品最大重复使用次数（超过则强制排除）
    
    Returns:
        dict: {
            'result_folder': str,
            'excel_sample_id': str,
            'R': float,
            'N': float,
            'distance': float,
            'scan_subfolders': list,
            'is_duplicate': bool,
            'use_count': int
        }
    """
    samples = inventory.get('samples', [])
    if not samples:
        return None
    
    # 获取已使用的样品及使用次数
    used_samples, sample_use_count = get_used_samples_from_history() if avoid_duplicates else (set(), {})
    
    best_match = None
    min_distance = float('inf')
    all_candidates = []
    
    for sample in samples:
        r = sample.get('R')
        n = sample.get('N')
        
        if r is None or n is None:
            continue
        
        sample_key = (round(r, 6), round(n, 6))
        use_count = sample_use_count.get(sample_key, 0)
        
        # 强制排除已达到最大使用次数的样品
        if use_count >= max_reuse_count:
            continue
        
        distance = calculate_euclidean_distance(target_r, target_n, r, n)
        
        # 检查是否是重复样品
        is_duplicate = sample_key in used_samples
        
        # 对重复样品施加距离惩罚（惩罚力度随使用次数增加）
        penalty_multiplier = 1.0 + (duplicate_penalty - 1.0) * use_count
        effective_distance = distance * penalty_multiplier if is_duplicate else distance
        
        candidate = {
            'result_folder': sample['result_folder'],
            'excel_sample_id': sample['excel_sample_id'],
            'R': r,
            'N': n,
            'L_cm': sample.get('L_cm'),
            'S_cm2': sample.get('S_cm2'),
            'distance': distance,
            'effective_distance': effective_distance,
            'is_duplicate': is_duplicate,
            'use_count': use_count,
            'scan_subfolders': sample.get('scan_subfolders', [])
        }
        
        all_candidates.append(candidate)
        
        if effective_distance < min_distance:
            min_distance = effective_distance
            best_match = candidate
    
    # === 方案 1：基于性能的智能选择 ===
    # 对于 R/N 相同的样品（距离 < 1e-6），选择性能最优的
    if best_match:
        distance_threshold = 1e-6
        same_rn_group = [
            c for c in all_candidates 
            if c['distance'] <= best_match['distance'] + distance_threshold
        ]
        
        if len(same_rn_group) > 1:
            print(f"[Virtual Oracle] 发现 {len(same_rn_group)} 个 R/N 相同的样品，正在选择性能最优的样品...")
            
            best_sample = None
            best_score = -999.0
            
            for candidate in same_rn_group:
                sample_folder = REAL_DATA_ROOT / candidate['result_folder']
                scan_subfolder = candidate['scan_subfolders'][0] if candidate['scan_subfolders'] else None
                
                if not scan_subfolder:
                    continue
                
                score = calculate_combined_score(sample_folder, scan_subfolder)
                
                if score > best_score:
                    best_score = score
                    best_sample = candidate
                    print(f"  ✓ {candidate['result_folder']:25s} | score={score:7.4f} | {scan_subfolder:20s} (当前最优)")
                else:
                    print(f"    {candidate['result_folder']:25s} | score={score:7.4f} | {scan_subfolder:20s}")
            
            if best_sample:
                print(f"[Virtual Oracle] 选择最优样品: {best_sample['result_folder']} (combined_score={best_score:.4f})")
                best_match = best_sample
    
    # 打印匹配信息
    if best_match and avoid_duplicates:
        total_unique_used = len(used_samples)
        total_trials = sum(sample_use_count.values())
        
        if best_match['is_duplicate']:
            use_count = best_match['use_count']
            print(f"[WARNING] 最近样品是重复样品 (使用次数: {use_count}, 总试验: {total_trials}, 独立样品: {total_unique_used})")
            # 找到最近的未使用样品
            unused_candidates = [c for c in all_candidates if not c['is_duplicate']]
            if unused_candidates:
                nearest_unused = min(unused_candidates, key=lambda x: x['distance'])
                print(f"  最近的未使用样品: {nearest_unused['result_folder']}")
                print(f"    距离: {nearest_unused['distance']:.6f} (vs 重复样品: {best_match['distance']:.6f})")
    
    return best_match


def copy_experimental_data(
    source_folder: Path,
    scan_subfolder: str,
    target_dir: Path,
    verbose: bool = False
) -> Dict:
    """
    Copy aggregated_results.json and arrhenius_analysis.json to target directory
    
    Returns:
        dict: {success, copied_files, error}
    """
    source_scan_dir = source_folder / scan_subfolder
    
    if not source_scan_dir.exists():
        return {
            'success': False,
            'copied_files': [],
            'error': f'Source scan directory not found: {source_scan_dir}'
        }
    
    # Files to copy (aggregated_results.json is required, others are optional)
    required_files = ['aggregated_results.json']
    optional_files = ['arrhenius_analysis.json']
    
    # Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)
    
    copied = []
    errors = []
    
    # Copy required files
    for filename in required_files:
        source_file = source_scan_dir / filename
        target_file = target_dir / filename
        
        if not source_file.exists():
            errors.append(f'{filename} (required) not found in source')
            continue
        
        try:
            shutil.copy2(source_file, target_file)
            copied.append(filename)
            if verbose:
                print(f"  [OK] Copied {filename}")
        except Exception as e:
            errors.append(f'{filename}: {str(e)}')
    
    # Copy optional files (don't fail if missing)
    for filename in optional_files:
        source_file = source_scan_dir / filename
        target_file = target_dir / filename
        
        if not source_file.exists():
            if verbose:
                print(f"  [SKIP] {filename} not found (optional)")
            continue
        
        try:
            shutil.copy2(source_file, target_file)
            copied.append(filename)
            if verbose:
                print(f"  [OK] Copied {filename}")
        except Exception as e:
            if verbose:
                print(f"  [WARNING] Failed to copy {filename}: {e}")
    
    # Only fail if required files are missing
    if any('required' in err for err in errors):
        return {
            'success': False,
            'copied_files': copied,
            'error': '; '.join(errors)
        }
    
    return {
        'success': True,
        'copied_files': copied,
        'error': None
    }


def generate_metadata(
    ai_recommendation: Dict,
    matched_sample: Dict,
    target_dir: Path
) -> Dict:
    """
    Generate experiment_metadata.json for traceability
    
    Returns:
        dict: {success, metadata_path, error}
    """
    metadata = {
        'virtual_oracle_version': '1.0',
        'selection_source': ai_recommendation.get('selection_source', 'final_recipe'),
        'parameters': {
            'R': matched_sample['R'],
            'N': matched_sample['N']
        },
        'ai_recommendation': {
            'R': ai_recommendation['R'],
            'N': ai_recommendation['N']
        },
        'optimizer_suggestion': ai_recommendation.get('optimizer_suggestion', {}),
        'recommended_parameters': ai_recommendation.get('recommended_parameters', {}),
        'optimizer_vs_llm_delta': ai_recommendation.get('optimizer_vs_llm_delta', {}),
        'matched_real_sample': {
            'result_folder': matched_sample['result_folder'],
            'excel_sample_id': matched_sample['excel_sample_id'],
            'R': matched_sample['R'],
            'N': matched_sample['N'],
            'L_cm': matched_sample.get('L_cm'),
            'S_cm2': matched_sample.get('S_cm2'),
            'euclidean_distance': matched_sample['distance']
        },
        'data_source': {
            'scan_subfolder': matched_sample.get('selected_scan'),
            'source_path': str(REAL_DATA_ROOT / matched_sample['result_folder'] / matched_sample.get('selected_scan', ''))
        }
    }
    
    metadata_path = target_dir / 'experiment_metadata.json'
    
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        return {
            'success': True,
            'metadata_path': str(metadata_path),
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'metadata_path': None,
            'error': str(e)
        }


def write_last_oracle_match_record(
    ai_recommendation: Dict,
    matched_sample: Dict,
) -> None:
    """
    Write a small JSON for run_offline_loop early-stop (Oracle repeat detection).
    """
    LAST_ORACLE_MATCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "selection_source": ai_recommendation.get("selection_source", "final_recipe"),
        "result_folder": matched_sample["result_folder"],
        "excel_sample_id": matched_sample.get("excel_sample_id"),
        "euclidean_distance": float(matched_sample.get("distance", 0.0)),
        "ai_R": float(ai_recommendation["R"]),
        "ai_N": float(ai_recommendation["N"]),
        "optimizer_suggestion": ai_recommendation.get("optimizer_suggestion", {}),
        "recommended_parameters": ai_recommendation.get("recommended_parameters", {}),
        "optimizer_vs_llm_delta": ai_recommendation.get("optimizer_vs_llm_delta", {}),
        "matched_R": float(matched_sample["R"]),
        "matched_N": float(matched_sample["N"]),
        "selected_scan": matched_sample.get("selected_scan"),
    }
    with open(LAST_ORACLE_MATCH_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ============================================================
# Main Function
# ============================================================

def main(
    dry_run: bool = False,
    verbose: bool = False,
    selection_source: str = "final_recipe",
    campaign_config: Optional[str] = None,
    allow_real_campaign: bool = False,
) -> int:
    """Main function"""
    configure_campaign_paths(campaign_config, allow_real_campaign=allow_real_campaign)
    print("=" * 70)
    print("Virtual Oracle - Offline Closed-Loop Replay")
    print("=" * 70)
    print(f"[MODE] legacy/offline replay; campaign_config={_STORAGE.campaign_config}")
    print(f"[MODE] recipe={AI_RECIPE_PATH}")
    print(f"[MODE] history={HISTORY_DB_PATH}")
    
    # Step 1: Load AI recommendation
    print("\nStep 1/5: Loading AI recommendation...")
    ai_rec = load_ai_recommendation(selection_source=selection_source)
    
    if ai_rec is None:
        print("[ERROR] AI recipe not found or invalid")
        print(f"  Expected path: {AI_RECIPE_PATH}")
        print("\n  Hint: Run Stage 1 optimization first to generate initial recipe.")
        return 1
    
    print(f"  [OK] Selection source: {ai_rec['selection_source']}")
    print(f"  [OK] AI recommends: R = {ai_rec['R']:.4f}, N = {ai_rec['N']:.4f}")
    
    # Step 2: Load inventory
    print("\nStep 2/5: Loading sample inventory...")
    inventory = load_inventory()
    
    if inventory is None:
        print("[ERROR] Sample inventory not found")
        print(f"  Expected path: {INVENTORY_PATH}")
        print("\n  Hint: Run extract_s8_rn_from_excel.py first.")
        return 1
    
    n_samples = len(inventory.get('samples', []))
    print(f"  [OK] Loaded {n_samples} samples from inventory")
    
    # Step 3: Find nearest neighbor
    print("\nStep 3/5: Finding nearest sample...")
    matched = find_nearest_sample(ai_rec['R'], ai_rec['N'], inventory, 
                                  avoid_duplicates=True, duplicate_penalty=2.0)
    
    if matched is None:
        print("[ERROR] No valid samples found in inventory")
        return 1
    
    print(f"  [OK] Best match: {matched['result_folder']}")
    print(f"      Excel ID: {matched['excel_sample_id']}")
    print(f"      R = {matched['R']:.4f}, N = {matched['N']:.4f}")
    print(f"      Euclidean distance: {matched['distance']:.6f}")
    if matched.get('is_duplicate'):
        print(f"      [DUPLICATE] This sample has been used before")
    print(f"      Available scans: {matched['scan_subfolders']}")
    
    # Select first scan subfolder
    if not matched['scan_subfolders']:
        print("[ERROR] No scan subfolders found for matched sample")
        return 1
    
    selected_scan = matched['scan_subfolders'][0]
    matched['selected_scan'] = selected_scan
    print(f"      Selected scan: {selected_scan}")
    
    if dry_run:
        print("\n[DRY-RUN] Would copy data from:")
        print(f"  Source: {REAL_DATA_ROOT / matched['result_folder'] / selected_scan}")
        print(f"  Target: {STAGE1_INPUT_DIR}")
        return 0
    
    # Step 4: Copy experimental data
    print("\nStep 4/5: Copying experimental data...")
    source_folder = REAL_DATA_ROOT / matched['result_folder']
    
    copy_result = copy_experimental_data(
        source_folder,
        selected_scan,
        STAGE1_INPUT_DIR,
        verbose=verbose
    )
    
    if not copy_result['success']:
        print(f"[ERROR] Data copy failed: {copy_result['error']}")
        return 1
    
    print(f"  [OK] Copied {len(copy_result['copied_files'])} files")
    if verbose:
        for f in copy_result['copied_files']:
            print(f"      - {f}")
    
    # Step 5: Generate metadata
    print("\nStep 5/5: Generating metadata...")
    metadata_result = generate_metadata(ai_rec, matched, STAGE1_INPUT_DIR)
    
    if not metadata_result['success']:
        print(f"[ERROR] Metadata generation failed: {metadata_result['error']}")
        return 1
    
    print(f"  [OK] Metadata: {metadata_result['metadata_path']}")
    
    try:
        write_last_oracle_match_record(ai_rec, matched)
        print(f"  [OK] Oracle match record: {LAST_ORACLE_MATCH_PATH.name}")
    except Exception as e:
        print(f"  [WARNING] Could not write {LAST_ORACLE_MATCH_PATH.name}: {e}")
    
    write_manifest(LAST_ORACLE_MATCH_PATH.parent / "virtual_oracle_manifest.json", {
        "selection_source": ai_rec.get("selection_source"),
        "selected_parameters": ai_rec.get("selected_parameters"),
        "optimizer_suggestion": ai_rec.get("optimizer_suggestion"),
        "recommended_parameters": ai_rec.get("recommended_parameters"),
        "matched_sample": matched,
        "dry_run": dry_run,
    })

    # Summary
    print("\n" + "=" * 70)
    print("Virtual Oracle Execution Complete")
    print("=" * 70)
    print(f"AI recommendation: R={ai_rec['R']:.4f}, N={ai_rec['N']:.4f}")
    print(f"Matched sample: {matched['result_folder']} (distance={matched['distance']:.6f})")
    print(f"Data copied to: {STAGE1_INPUT_DIR}")
    print("\nNext step: Run Stage 1 optimization loop to process this data.")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Virtual Oracle - Offline Closed-Loop Replay")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without copying")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument(
        "--campaign_config",
        default=str(DEFAULT_REPLAY_CAMPAIGN),
        help="Campaign JSON whose storage.output_dir/history_db are used for replay artifacts.",
    )
    parser.add_argument(
        "--allow-real-campaign",
        action="store_true",
        help="Explicitly allow attapulgite real campaign storage. Normally blocked for replay safety.",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--use-final-recipe",
        action="store_true",
        help="Use recipe.recommended_parameters (default)",
    )
    source_group.add_argument(
        "--use-optimizer-suggestion",
        action="store_true",
        help="Use optimizer_suggestion instead of final LLM recipe",
    )
    
    args = parser.parse_args()
    selection_source = "optimizer_suggestion" if args.use_optimizer_suggestion else "final_recipe"
    
    try:
        sys.exit(main(
            dry_run=args.dry_run,
            verbose=args.verbose,
            selection_source=selection_source,
            campaign_config=args.campaign_config,
            allow_real_campaign=args.allow_real_campaign,
        ))
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED]")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
