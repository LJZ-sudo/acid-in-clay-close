#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
冷启动初始化脚本

为离线闭环选择一个合适的初始样品，避免从稀疏区域开始。

策略：
1. 从样品库中心区域选择（中位数附近）
2. 或从已知性能较好的样品开始
3. 清空历史数据（可选）
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Fix encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Repo root: .../V1.0-qianduan-mainline (this file lives in code/stage1_tools/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
from _campaign_paths import (
    DEFAULT_REPLAY_CAMPAIGN,
    load_campaign_storage,
    require_not_real_history_reset,
)

INVENTORY_PATH = PROJECT_ROOT.parent / "experiments" / "output" / "stage0_results" / "s8_sample_rn.json"
REAL_DATA_ROOT = PROJECT_ROOT.parent / "experiments" / "output" / "stage0_results"
STAGE1_INPUT_DIR = PROJECT_ROOT / "stage1_optimization" / "demo_stage0_results"
_STORAGE = load_campaign_storage(DEFAULT_REPLAY_CAMPAIGN)
HISTORY_DB_PATH = _STORAGE.history_db


def configure_campaign_paths(campaign_config: str | None) -> None:
    global _STORAGE, HISTORY_DB_PATH
    _STORAGE = load_campaign_storage(campaign_config, default_campaign=DEFAULT_REPLAY_CAMPAIGN)
    HISTORY_DB_PATH = _STORAGE.history_db

def load_inventory():
    """加载样品库"""
    with open(INVENTORY_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_median_sample(samples: List[Dict]) -> Dict:
    """找到接近中位数的样品"""
    r_vals = sorted([s['R'] for s in samples if s.get('R') is not None])
    n_vals = sorted([s['N'] for s in samples if s.get('N') is not None])
    
    r_median = r_vals[len(r_vals) // 2]
    n_median = n_vals[len(n_vals) // 2]
    
    # 找到最接近中位数的样品
    import math
    best_sample = None
    min_dist = float('inf')
    
    for sample in samples:
        r = sample.get('R')
        n = sample.get('N')
        if r is None or n is None:
            continue
        
        dist = math.sqrt((r - r_median)**2 + (n - n_median)**2)
        if dist < min_dist:
            min_dist = dist
            best_sample = sample
    
    return best_sample, r_median, n_median

def copy_sample_data(sample: Dict, verbose: bool = False):
    """复制样品数据到demo_stage0_results"""
    source_folder = REAL_DATA_ROOT / sample['result_folder']
    scan_subfolder = sample['scan_subfolders'][0]
    source_scan_dir = source_folder / scan_subfolder
    
    # 清空目标目录
    if STAGE1_INPUT_DIR.exists():
        shutil.rmtree(STAGE1_INPUT_DIR)
    STAGE1_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 复制文件
    files_to_copy = ['aggregated_results.json', 'arrhenius_analysis.json']
    
    for filename in files_to_copy:
        source_file = source_scan_dir / filename
        target_file = STAGE1_INPUT_DIR / filename
        shutil.copy2(source_file, target_file)
        if verbose:
            print(f"  [OK] Copied {filename}")
    
    # 生成元数据
    metadata = {
        'cold_start': True,
        'strategy': 'median_sample',
        'parameters': {
            'R': sample['R'],
            'N': sample['N']
        },
        'selected_sample': {
            'result_folder': sample['result_folder'],
            'excel_sample_id': sample['excel_sample_id'],
            'R': sample['R'],
            'N': sample['N'],
            'L_cm': sample.get('L_cm'),
            'S_cm2': sample.get('S_cm2')
        },
        'scan_subfolder': scan_subfolder
    }
    
    metadata_path = STAGE1_INPUT_DIR / 'experiment_metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

def reset_history(backup: bool = True, *, allow_real_history_reset: bool = False):
    """重置历史数据库"""
    require_not_real_history_reset(_STORAGE, allowed=allow_real_history_reset)
    if backup and HISTORY_DB_PATH.exists():
        backup_path = HISTORY_DB_PATH.with_suffix('.json.backup')
        shutil.copy2(HISTORY_DB_PATH, backup_path)
        print(f"  [OK] Backed up history to {backup_path}")
    
    # 创建空历史
    empty_history = {
        "campaign_name": "S8_Sepiolite_Wide_Temp_Optimization",
        "trials": []
    }
    
    with open(HISTORY_DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(empty_history, f, indent=2, ensure_ascii=False)
    
    print(f"  [OK] Reset history database")

def main(
    reset: bool = False,
    verbose: bool = False,
    campaign_config: str | None = None,
    allow_real_history_reset: bool = False,
):
    """主函数"""
    configure_campaign_paths(campaign_config)
    print("=" * 70)
    print("冷启动初始化 - 选择初始样品")
    print("=" * 70)
    print(f"[MODE] legacy/offline cold start; campaign_config={_STORAGE.campaign_config}")
    print(f"[MODE] history={HISTORY_DB_PATH}")
    
    # 加载样品库
    print("\nStep 1/4: 加载样品库...")
    inventory = load_inventory()
    samples = inventory['samples']
    print(f"  [OK] 加载了 {len(samples)} 个样品")
    
    # 找到中位数样品
    print("\nStep 2/4: 选择初始样品（中位数策略）...")
    best_sample, r_median, n_median = find_median_sample(samples)
    
    print(f"  [OK] 样品库中位数: R={r_median:.4f}, N={n_median:.4f}")
    print(f"  [OK] 选择样品: {best_sample['result_folder']}")
    print(f"      Excel ID: {best_sample['excel_sample_id']}")
    print(f"      R = {best_sample['R']:.4f}")
    print(f"      N = {best_sample['N']:.4f}")
    print(f"      扫描: {best_sample['scan_subfolders']}")
    
    # 复制数据
    print("\nStep 3/4: 复制样品数据...")
    copy_sample_data(best_sample, verbose=verbose)
    print(f"  [OK] 数据已复制到 {STAGE1_INPUT_DIR}")
    
    # 重置历史（可选）
    if reset:
        print("\nStep 4/4: 重置历史数据库...")
        reset_history(backup=True, allow_real_history_reset=allow_real_history_reset)
    else:
        print("\nStep 4/4: 保留现有历史数据")
        print("  提示: 使用 --reset 参数可清空历史数据")
    
    # 总结
    print("\n" + "=" * 70)
    print("冷启动初始化完成")
    print("=" * 70)
    print(f"初始样品: {best_sample['result_folder']}")
    print(f"参数: R={best_sample['R']:.4f}, N={best_sample['N']:.4f}")
    print(f"\n下一步:")
    print("  cd stage1_optimization")
    print("  python run_optimization_loop.py \\")
    print("    --campaign campaigns/attapulgite_aice_campaign.json \\")
    print("    --stage0-dir demo_stage0_results \\")
    print("    --output-dir output")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="冷启动初始化脚本")
    parser.add_argument("--reset", action="store_true", help="重置历史数据库")
    parser.add_argument("--verbose", action="store_true", help="显示详细输出")
    parser.add_argument(
        "--campaign_config",
        default=str(DEFAULT_REPLAY_CAMPAIGN),
        help="Campaign JSON whose storage.history_db is reset when --reset is used.",
    )
    parser.add_argument(
        "--allow-real-history-reset",
        action="store_true",
        help="Explicitly allow reset of attapulgite real campaign history.",
    )
    
    args = parser.parse_args()
    
    try:
        sys.exit(main(
            reset=args.reset,
            verbose=args.verbose,
            campaign_config=args.campaign_config,
            allow_real_history_reset=args.allow_real_history_reset,
        ))
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED]")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
