#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reset Optimization History

清理重复的历史数据，为新一轮优化做准备
"""
import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse

# Repo root: .../V1.0-qianduan-mainline (this file lives in code/stage1_tools/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
from _campaign_paths import (
    DEFAULT_REPLAY_CAMPAIGN,
    load_campaign_storage,
    require_not_real_history_reset,
)

_STORAGE = load_campaign_storage(DEFAULT_REPLAY_CAMPAIGN)
HISTORY_PATH = _STORAGE.history_db
BACKUP_DIR = HISTORY_PATH.parent / "backups"


def configure_campaign_paths(campaign_config: str | None) -> None:
    global _STORAGE, HISTORY_PATH, BACKUP_DIR
    _STORAGE = load_campaign_storage(campaign_config, default_campaign=DEFAULT_REPLAY_CAMPAIGN)
    HISTORY_PATH = _STORAGE.history_db
    BACKUP_DIR = HISTORY_PATH.parent / "backups"


def main(campaign_config: str | None = None, *, allow_real_history_reset: bool = False):
    configure_campaign_paths(campaign_config)
    require_not_real_history_reset(_STORAGE, allowed=allow_real_history_reset)
    print("=" * 70)
    print("Reset Optimization History")
    print("=" * 70)
    print(f"[MODE] campaign_config={_STORAGE.campaign_config}")
    print(f"[MODE] history={HISTORY_PATH}")
    
    if not HISTORY_PATH.exists():
        print("[INFO] No history file found. Nothing to reset.")
        return
    
    # 读取当前历史
    with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    total_trials = len(history.get('trials', []))
    
    if total_trials == 0:
        print("[INFO] History is already empty.")
        return
    
    print(f"\n[INFO] Current history: {total_trials} trials")
    
    # 统计重复样品
    param_counts = {}
    for trial in history.get('trials', []):
        params = trial.get('parameters', {})
        r = params.get('R')
        n = params.get('N')
        if r is not None and n is not None:
            key = (round(r, 6), round(n, 6))
            param_counts[key] = param_counts.get(key, 0) + 1
    
    unique_samples = len(param_counts)
    duplicates = sum(1 for count in param_counts.values() if count > 1)
    
    print(f"[INFO] Unique samples: {unique_samples}")
    print(f"[INFO] Samples with duplicates: {duplicates}")
    
    if duplicates > 0:
        print("\n[INFO] Duplicate samples:")
        for (r, n), count in sorted(param_counts.items(), key=lambda x: -x[1]):
            if count > 1:
                print(f"  R={r:.3f}, N={n:.3f}: {count} times")
    
    # 备份
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"history_db_{timestamp}.json"
    
    shutil.copy2(HISTORY_PATH, backup_path)
    print(f"\n[BACKUP] Saved to: {backup_path}")
    
    # 询问确认
    print("\n" + "=" * 70)
    print("This will DELETE the current history and start fresh.")
    print("=" * 70)
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("[CANCELLED] No changes made.")
        return
    
    # 删除历史文件
    HISTORY_PATH.unlink()
    print(f"\n[SUCCESS] History reset complete!")
    print(f"[INFO] Backup saved at: {backup_path}")
    print("\nNext steps:")
    print("  1. Run: python initialize_cold_start.py --reset")
    print("  2. Run: python run_offline_loop.py --iterations 15")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset Stage1 optimization history")
    parser.add_argument(
        "--campaign_config",
        default=str(DEFAULT_REPLAY_CAMPAIGN),
        help="Campaign JSON whose storage.history_db will be reset.",
    )
    parser.add_argument(
        "--allow-real-history-reset",
        action="store_true",
        help="Explicitly allow reset of attapulgite real campaign history.",
    )
    args = parser.parse_args()
    main(
        campaign_config=args.campaign_config,
        allow_real_history_reset=args.allow_real_history_reset,
    )
