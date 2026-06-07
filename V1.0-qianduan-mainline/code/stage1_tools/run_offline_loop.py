#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化离线闭环脚本

自动运行多轮 Stage1优化器 + Virtual Oracle 的闭环迭代。

工作流程：
1. 运行 Stage1 优化器 → 生成 AI 建议
2. 运行 Virtual Oracle → 匹配最近邻样品
3. 重复步骤 1-2，直到达到指定迭代次数，或触发早停（可选）

早停（默认开启，B 与 A 为「或」，先触发先停）：
- [B] Oracle 重复：连续 K 次命中同一 result_folder（离线回放）；可用 --no-oracle-early-stop 关闭
- [A] 分数平台：连续 M 轮全局 combined_score 无提升（--score-plateau-rounds M；M=0 表示关闭）
- 硬上限：始终受 --iterations 限制

Usage:
    python run_offline_loop.py --iterations 10
    python run_offline_loop.py --iterations 20 --cold-start
    python run_offline_loop.py --iterations 100 --no-early-stop
    python run_offline_loop.py --iterations 80 --score-plateau-rounds 10 --no-oracle-early-stop
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

# Fix encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Repo root: .../V1.0-qianduan-mainline (this file lives in code/stage1_tools/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "code"))

from shared.manifest import write_manifest
from _campaign_paths import DEFAULT_REPLAY_CAMPAIGN, load_campaign_storage

STAGE1_DIR = PROJECT_ROOT / "stage1_optimization"
CODE_DIR = PROJECT_ROOT / "code"
HISTORY_DB_PATH = _STORAGE.history_db
# The replay recipe path is resolved from campaign storage.output_dir below.
RECIPE_PATH = STAGE1_DIR / "output" / "next_experiment_recipe.json"
LAST_ORACLE_MATCH_PATH = STAGE1_DIR / "output" / "last_virtual_oracle_match.json"
_STORAGE = load_campaign_storage(DEFAULT_REPLAY_CAMPAIGN)


def configure_campaign_paths(campaign_config: Optional[str]) -> None:
    """Use campaign storage for replay artifacts while keeping this tool offline-only."""
    global _STORAGE, HISTORY_DB_PATH, RECIPE_PATH, LAST_ORACLE_MATCH_PATH
    _STORAGE = load_campaign_storage(campaign_config, default_campaign=DEFAULT_REPLAY_CAMPAIGN)
    HISTORY_DB_PATH = _STORAGE.history_db
    RECIPE_PATH = _STORAGE.next_recipe
    LAST_ORACLE_MATCH_PATH = _STORAGE.output_dir / "last_virtual_oracle_match.json"


configure_campaign_paths(str(DEFAULT_REPLAY_CAMPAIGN))

SCORE_EPS = 1e-9


def _agent_ops_heartbeat(
    stage: str, status: str = "alive", extra: Optional[Dict[str, Any]] = None
) -> None:
    try:
        from agent_ops.heartbeat import write_heartbeat

        write_heartbeat(stage, status=status, extra=extra, project_root=PROJECT_ROOT)
    except Exception:
        pass


def _agent_ops_memory(event_type: str, payload: Dict[str, Any]) -> None:
    try:
        from agent_ops.memory import append_memory_event

        append_memory_event(event_type, payload, project_root=PROJECT_ROOT)
    except Exception:
        pass


def run_command(cmd: list, cwd: Path, description: str, verbose: bool = False):
    """运行命令并捕获输出"""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}")
    
    if verbose:
        print(f"Command: {' '.join(cmd)}")
        print(f"Working directory: {cwd}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if verbose or result.returncode != 0:
            print("\n--- STDOUT ---")
            print(result.stdout)
            if result.stderr:
                print("\n--- STDERR ---")
                print(result.stderr)
        
        if result.returncode != 0:
            print(f"\n[ERROR] Command failed with exit code {result.returncode}")
            return False
        
        print(f"[OK] {description} completed successfully")
        return True
    
    except Exception as e:
        print(f"[ERROR] Failed to run command: {e}")
        return False


def load_history() -> List[Dict[str, Any]]:
    """加载历史数据"""
    if not HISTORY_DB_PATH.exists():
        return []
    
    with open(HISTORY_DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get('trials', [])


def max_combined_score(history: List[Dict[str, Any]]) -> Optional[float]:
    """历史中的全局最优 combined_score；无则 None"""
    scores: List[float] = []
    for t in history:
        o = t.get('objectives') or {}
        v = o.get('combined_score')
        if v is not None:
            scores.append(float(v))
    if not scores:
        return None
    return max(scores)


def load_latest_recipe() -> Optional[Dict[str, Any]]:
    """加载最新的AI建议"""
    if not RECIPE_PATH.exists():
        return None
    
    with open(RECIPE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_last_oracle_match() -> Optional[Dict[str, Any]]:
    """读取 Virtual Oracle 写入的最近一次匹配（用于早停）"""
    if not LAST_ORACLE_MATCH_PATH.exists():
        return None
    try:
        with open(LAST_ORACLE_MATCH_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def print_iteration_summary(iteration: int, recipe: Optional[Dict], history: List[Dict[str, Any]]):
    """打印迭代摘要"""
    print(f"\n{'='*70}")
    print(f"迭代 {iteration} 摘要")
    print(f"{'='*70}")
    
    if recipe and 'optimizer_suggestion' in recipe:
        r = recipe['optimizer_suggestion']['R']
        n = recipe['optimizer_suggestion']['N']
        print(f"AI 建议: R={r:.4f}, N={n:.4f}")
    
    if history:
        latest = history[-1]
        params = latest['parameters']
        objs = latest['objectives']
        print(f"实际使用: R={params['R']:.4f}, N={params['N']:.4f}")
        print(f"性能指标:")
        
        conductivity = objs.get('conductivity_room_temp_S_cm')
        ea_high = objs.get('ea_high_temp_eV')
        score = objs.get('combined_score')
        
        if conductivity is not None:
            print(f"  - 室温电导率: {conductivity:.6e} S/cm")
        else:
            print(f"  - 室温电导率: N/A (数据缺失)")
        
        if ea_high is not None:
            print(f"  - 高温Ea: {ea_high:.4f} eV")
        else:
            print(f"  - 高温Ea: N/A (数据缺失)")
        
        if score is not None:
            print(f"  - Combined Score: {score:.4f}")
        else:
            print(f"  - Combined Score: N/A (数据缺失)")
    
    print(f"{'='*70}")


def main(
    iterations: int = 10,
    cold_start: bool = False,
    verbose: bool = False,
    early_stop: bool = True,
    oracle_early_stop: bool = True,
    oracle_repeat_patience: int = 3,
    score_plateau_rounds: int = 0,
    campaign_config: Optional[str] = None,
) -> int:
    """主函数"""
    configure_campaign_paths(campaign_config)
    print("=" * 70)
    print("自动化离线闭环 - 开始运行")
    print("=" * 70)
    print(f"[MODE] legacy/offline replay; campaign_config={_STORAGE.campaign_config}")
    print(f"[MODE] history={HISTORY_DB_PATH}")
    print(f"[MODE] output_dir={_STORAGE.output_dir}")
    print(f"迭代次数(硬上限): {iterations}")
    print(f"冷启动: {'是' if cold_start else '否'}")
    print(f"早停: {'是' if early_stop else '否'}")
    if early_stop:
        if oracle_early_stop:
            print(f"  - [B] Oracle 连续同库次数 >= {oracle_repeat_patience} -> 停止")
        else:
            print("  - [B] Oracle 重复早停: 关闭 (与在线实验一致时请用 --no-oracle-early-stop + --score-plateau-rounds)")
        if score_plateau_rounds > 0:
            print(f"  - [A] 全局 combined_score 连续 {score_plateau_rounds} 轮无提升 -> 停止")
        else:
            print("  - [A] 分数平台判据: 关闭 (score_plateau_rounds=0；若只要 A 请设置 >0)")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    loop_events: List[Dict[str, Any]] = []
    _agent_ops_heartbeat(
        "stage1_offline_loop",
        status="running",
        extra={"iterations": iterations, "cold_start": cold_start},
    )

    if cold_start:
        print("\n执行冷启动初始化...")
        success = run_command(
            [
                sys.executable,
                "initialize_cold_start.py",
                "--reset",
                "--verbose",
                "--campaign_config",
                str(_STORAGE.campaign_config),
            ],
            CODE_DIR / "stage1_tools",
            "冷启动初始化",
            verbose=verbose
        )
        if not success:
            print("[ERROR] 冷启动失败")
            return 1
        
        time.sleep(2)
    
    # 早停状态
    last_oracle_folder: Optional[str] = None
    oracle_same_streak = 0
    score_plateau_count = 0
    stop_reason: Optional[str] = None
    
    for i in range(1, iterations + 1):
        print(f"\n{'#'*70}")
        print(f"# 迭代 {i}/{iterations}")
        print(f"{'#'*70}")
        
        history_before = load_history()
        len_before = len(history_before)
        best_before = max_combined_score(history_before)
        
        success = run_command(
            [
                sys.executable,
                "run_optimization_loop.py",
                "--campaign_config", str(_STORAGE.campaign_config),
                "--stage0_results_dir", "demo_stage0_results",
                "--output_dir", str(_STORAGE.output_dir),
                "--mode", "replay",
                "--source_tag", _STORAGE.source_tag,
            ],
            STAGE1_DIR,
            f"迭代 {i} - Stage1 优化器",
            verbose=verbose
        )
        
        if not success:
            print(f"[ERROR] 迭代 {i} 的 Stage1 优化器失败")
            break
        
        time.sleep(1)
        
        success = run_command(
            [
                sys.executable,
                "virtual_oracle.py",
                "--verbose",
                "--use-final-recipe",
                "--campaign_config",
                str(_STORAGE.campaign_config),
            ],
            CODE_DIR / "stage1_tools",
            f"迭代 {i} - Virtual Oracle",
            verbose=verbose
        )
        
        if not success:
            print(f"[ERROR] 迭代 {i} 的 Virtual Oracle 失败")
            break
        
        recipe = load_latest_recipe()
        history = load_history()
        loop_events.append({
            "iteration": i,
            "recipe_timestamp": (recipe or {}).get("timestamp"),
            "optimizer_suggestion": (recipe or {}).get("optimizer_suggestion"),
            "recommended_parameters": ((recipe or {}).get("recipe") or {}).get("recommended_parameters"),
            "optimizer_vs_llm_delta": (recipe or {}).get("optimizer_vs_llm_delta"),
            "last_oracle_match": load_last_oracle_match(),
            "history_length": len(history),
        })
        print_iteration_summary(i, recipe, history)
        
        if early_stop:
            # --- [B] Oracle 重复（离线回放专用；在线实验请关闭）---
            if oracle_early_stop:
                om = load_last_oracle_match()
                folder = (om or {}).get("result_folder")
                if folder:
                    if folder == last_oracle_folder:
                        oracle_same_streak += 1
                    else:
                        oracle_same_streak = 1
                        last_oracle_folder = folder
                    if oracle_same_streak >= oracle_repeat_patience:
                        stop_reason = (
                            f"Oracle 连续 {oracle_same_streak} 次命中同一库存文件夹: {folder}"
                        )
                else:
                    print("[WARNING] 未找到 last_virtual_oracle_match.json，跳过 Oracle 重复判据本轮")
            
            # --- [A] 分数平台（全局最优长期无提升；贴近在线实验停机）---
            if stop_reason is None and score_plateau_rounds > 0:
                best_after = max_combined_score(history)
                if best_before is not None and best_after is not None:
                    if best_after <= best_before + SCORE_EPS:
                        score_plateau_count += 1
                    else:
                        score_plateau_count = 0
                    if score_plateau_count >= score_plateau_rounds:
                        stop_reason = (
                            f"全局 combined_score 连续 {score_plateau_count} 轮未提升 "
                            f"(当前最优 {best_after:.6f})"
                        )
                elif best_before is None and best_after is not None:
                    score_plateau_count = 0
        
        # 原 duplicate 警告逻辑（参数完全相同）
        if len(history) > len_before:
            latest = history[-1]
            if len(history) >= 2:
                prev = history[-2]
                if (abs(latest['parameters']['R'] - prev['parameters']['R']) < 1e-6 and
                    abs(latest['parameters']['N'] - prev['parameters']['N']) < 1e-6):
                    print(f"\n[WARNING] 检测到连续两条历史参数完全相同 (R,N)")
        
        if stop_reason:
            print(f"\n{'='*70}")
            print("[EARLY STOP] 早停触发")
            print(f"  原因: {stop_reason}")
            print(f"  结束于迭代: {i}/{iterations}")
            print(f"{'='*70}")
            break
        
        time.sleep(2)
    
    print(f"\n{'='*70}")
    print("离线闭环运行完成")
    if stop_reason:
        print(f"结束原因: 早停 ({stop_reason})")
    else:
        print("结束原因: 达到迭代上限或中途错误")
    print(f"{'='*70}")
    
    history = load_history()
    print(f"总实验次数: {len(history)}")
    
    if history:
        best_trial = max(history, key=lambda x: x['objectives'].get('combined_score', float('-inf')))
        print(f"\n最佳性能:")
        print(f"  Trial ID: {best_trial['trial_id']}")
        print(f"  参数: R={best_trial['parameters']['R']:.4f}, N={best_trial['parameters']['N']:.4f}")
        print(f"  Combined Score: {best_trial['objectives']['combined_score']:.4f}")
        
        conductivity = best_trial['objectives'].get('conductivity_room_temp_S_cm')
        if conductivity is not None:
            print(f"  室温电导率: {conductivity:.6e} S/cm")
        else:
            print(f"  室温电导率: N/A (数据缺失)")
        
        scores = [t['objectives']['combined_score'] for t in history if 'combined_score' in t.get('objectives', {})]
        if scores:
            print(f"\n性能趋势:")
            print(f"  初始 Score: {scores[0]:.4f}")
            print(f"  最终 Score: {scores[-1]:.4f}")
            print(f"  改进: {scores[-1] - scores[0]:.4f}")
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    write_manifest(STAGE1_DIR / "output" / "replay_loop_manifest.json", {
        "iterations_requested": iterations,
        "cold_start": cold_start,
        "early_stop": early_stop,
        "oracle_early_stop": oracle_early_stop,
        "oracle_repeat_patience": oracle_repeat_patience,
        "score_plateau_rounds": score_plateau_rounds,
        "stop_reason": stop_reason,
        "events": loop_events,
    })
    _agent_ops_heartbeat("stage1_offline_loop", status="completed", extra={"stop_reason": stop_reason})
    _agent_ops_memory(
        "stage1_replay_loop",
        {
            "iterations_requested": iterations,
            "stop_reason": stop_reason,
            "events_count": len(loop_events),
        },
    )

    return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="自动化离线闭环脚本")
    parser.add_argument("--iterations", type=int, default=10, help="迭代次数硬上限（默认10）")
    parser.add_argument("--cold-start", action="store_true", help="执行冷启动初始化")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")
    parser.add_argument(
        "--campaign_config",
        default=str(DEFAULT_REPLAY_CAMPAIGN),
        help="Campaign JSON whose storage paths are used for replay artifacts.",
    )
    parser.add_argument(
        "--no-early-stop",
        action="store_true",
        help="关闭早停，仅跑满 --iterations",
    )
    parser.add_argument(
        "--oracle-repeat-patience",
        type=int,
        default=3,
        metavar="K",
        help="连续 K 次 Virtual Oracle 命中同一 result_folder 则早停（默认 3）",
    )
    parser.add_argument(
        "--score-plateau-rounds",
        type=int,
        default=0,
        metavar="M",
        help="连续 M 轮全局 combined_score 无提升则早停；0 表示关闭（默认 0）",
    )
    parser.add_argument(
        "--no-oracle-early-stop",
        action="store_true",
        help="关闭「连续命中同一库存文件夹」早停 (B)，仅保留分数平台 (A) 与硬上限；贴近在线实验时推荐",
    )
    
    args = parser.parse_args()
    early_stop = not args.no_early_stop
    oracle_early_stop = not args.no_oracle_early_stop
    
    try:
        sys.exit(main(
            iterations=args.iterations,
            cold_start=args.cold_start,
            verbose=args.verbose,
            early_stop=early_stop,
            oracle_early_stop=oracle_early_stop,
            oracle_repeat_patience=max(1, args.oracle_repeat_patience),
            score_plateau_rounds=max(0, args.score_plateau_rounds),
            campaign_config=args.campaign_config,
        ))
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] 用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
