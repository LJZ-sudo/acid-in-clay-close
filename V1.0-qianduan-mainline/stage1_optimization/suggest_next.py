"""suggest_next.py — Stage1 BO+LLM 「单次推荐」入口

与 ``run_optimization_loop.py`` 的区别：
* run_optimization_loop:  解析 stage0 bundle → **写入 history_db** → BO → LLM → recipe
* suggest_next (本脚本): 直接读取 **现有 history_db** → BO → LLM → recipe（不写库、不重复 ingest）

适用场景：
* 冷启动已完成（history_db 已积累 ≥ cold_start_threshold 个去重配方），想立即拿到 GP+EI + LLM 的下一组 R/N
* 已经手工/批处理把若干 Stage0 bundle 灌入了 history_db，只想 "纯推荐" 而不二次写库
* 前端 /optimization 页面定期刷新 next_experiment_recipe.json

用法::

    python stage1_optimization/suggest_next.py \\
        --campaign_config stage1_optimization/campaigns/attapulgite_aice_campaign.json

输出: <campaign.storage.output_dir>/next_experiment_recipe.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm_client import LLMClient
from agents.strategy_planner import StrategyPlanner
from campaign_memory.memory_manager import MemoryManager
from canonical_input.campaign_parser import CampaignConfig
from canonical_input.design_space import ParameterSpace
from optimizers.bayesian_opt import BayesianOptimizer
from safety.safety_validator import SafetyValidator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("suggest_next")


def _resolve_paths(campaign_config: CampaignConfig) -> Dict[str, Path]:
    storage = campaign_config.config.get("storage") or {}
    db_rel = storage.get("history_db") or "campaign_memory/history_db_attapulgite.json"
    out_rel = storage.get("output_dir") or "output"
    return {
        "history_db": (ROOT / db_rel).resolve(),
        "output_dir": (ROOT / out_rel).resolve(),
    }


def _derive_current_state(memory: MemoryManager) -> tuple[Dict[str, float], Dict[str, Any]]:
    """把 history_db 的最近一个 trial 当作 "current state"（仅用作 LLM context）。"""
    history = memory.get_history()
    if not history:
        return {}, {}
    latest = history[-1]
    objectives = latest.get("objectives") or {}
    metrics = {k: v for k, v in objectives.items() if isinstance(v, (int, float))}
    physical = {
        k: v
        for k, v in objectives.items()
        if k in {
            "ea_high_temp_eV",
            "ea_low_temp_eV",
            "ea_low_excess_eV",
            "n_segments",
            "transition_temps_K",
        }
    }
    return metrics, physical


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--campaign_config", type=str, required=True)
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="覆盖输出目录（缺省时取 campaign storage.output_dir）",
    )
    parser.add_argument(
        "--db_path",
        type=str,
        default=None,
        help="覆盖 history_db 路径（缺省时取 campaign storage.history_db）",
    )
    parser.add_argument(
        "--cold_start_threshold",
        type=int,
        default=5,
        help="去重配方数 < 此值时仍走冷启动随机采样（默认 5）",
    )
    parser.add_argument(
        "--source_tag",
        type=str,
        default=None,
        help="数据来源标签（缺省时取 campaign.source_tag → campaign_name）",
    )
    args = parser.parse_args()

    cfg_path = Path(args.campaign_config)
    if not cfg_path.exists():
        logger.error(f"Campaign config not found: {cfg_path}")
        return 2

    logger.info("=" * 80)
    logger.info("🚀 Stage1 「单次推荐」 (suggest_next, no ingest)")
    logger.info("=" * 80)

    campaign = CampaignConfig(str(cfg_path))
    paths = _resolve_paths(campaign)
    db_path = Path(args.db_path).resolve() if args.db_path else paths["history_db"]
    output_dir = Path(args.output_dir).resolve() if args.output_dir else paths["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    source_tag = args.source_tag or campaign.config.get("source_tag") or campaign.campaign_name

    logger.info(f"📋 Campaign : {campaign.campaign_name}")
    logger.info(f"🗄️ DB path  : {db_path}")
    logger.info(f"📁 Output   : {output_dir}")
    logger.info(f"🏷️ source_tag: {source_tag}")

    if not db_path.exists():
        logger.error(f"history_db 不存在: {db_path}")
        return 3

    memory = MemoryManager(str(db_path), campaign_name=campaign.campaign_name)
    history = memory.get_history()
    if not history:
        logger.error("history_db 为空 — suggest_next 至少需要 1 个历史 trial")
        return 4

    parameter_space = ParameterSpace(campaign)
    optimizer = BayesianOptimizer(
        parameter_space=parameter_space,
        memory_manager=memory,
        cold_start_threshold=args.cold_start_threshold,
        acq_func="EI",
    )

    try:
        llm = LLMClient(temperature=0.2, max_tokens=2000)
        # test_connection 用极短 prompt 跑一次，R1 模型偶发会先吐 reasoning 导致正文为空被判失败；
        # 这里只作"信息位"提示，不据此关闭 LLM —— 真实失败会在 decide_with_fallback 里被 fallback 兜底。
        if not llm.test_connection():
            logger.warning("⚠️ LLM 连接 ping 失败，但仍尝试进入 planner（最终由 decide_with_fallback 兜底）")
    except Exception as e:  # pragma: no cover - network/optional
        logger.warning(f"⚠️ LLM 初始化失败: {e}")
        llm = None

    planner = StrategyPlanner(campaign_config=campaign, memory_manager=memory, llm_client=llm)
    safety = SafetyValidator(campaign)

    current_metrics, physical_features = _derive_current_state(memory)
    logger.info(f"📊 current_metrics (latest trial): {current_metrics}")

    logger.info("🧮 BayesianOptimizer.suggest_next()")
    optimizer_suggestion = optimizer.suggest_next()
    logger.info(f"   → {optimizer_suggestion}")
    prediction = optimizer.get_model_prediction(optimizer_suggestion)
    bo_prediction: Dict[str, Any] | None = None
    if prediction:
        mean, std = prediction
        logger.info(f"   predicted {campaign.get_objective_target()} = {mean:+.4f} ± {std:.4f}")
        bo_prediction = {
            "objective_target": campaign.get_objective_target(),
            "predicted_mean": mean,
            "predicted_std": std,
            "acquisition_function": optimizer.acq_func,
            "acquisition_value": optimizer.get_expected_improvement(optimizer_suggestion),
            "parameters": optimizer_suggestion,
        }

    logger.info("🤖 StrategyPlanner.decide_with_fallback() — LLM + BO 降级")
    recipe = planner.decide_with_fallback(
        current_metrics=current_metrics,
        optimizer_suggestion=optimizer_suggestion,
        fallback_to_optimizer=True,
        physical_features=physical_features,
    )
    safety_result = safety.validate(
        recipe.recommended_parameters,
        physical_features=physical_features or {},
    )

    # Mirror the structured BO ↔ LLM delta that run_optimization_loop.py emits,
    # so the front-end BORecipeCard component renders the same evidence table.
    delta_params: Dict[str, Any] = {}
    for k, llm_v in (recipe.recommended_parameters or {}).items():
        opt_v = optimizer_suggestion.get(k)
        numeric_delta: Optional[float] = None
        if isinstance(opt_v, (int, float)) and isinstance(llm_v, (int, float)):
            numeric_delta = llm_v - opt_v
        delta_params[k] = {
            "optimizer": opt_v,
            "llm": llm_v,
            "delta": numeric_delta,
            "status": "ok" if opt_v == llm_v else "adjusted",
        }
    optimizer_vs_llm_delta: Dict[str, Any] = {
        "parameters": delta_params,
        "adjusted": any(v["status"] == "adjusted" for v in delta_params.values()),
        "adjustment_reason": getattr(recipe, "reasoning", None),
        "warnings": getattr(recipe, "warnings", None) or [],
    }

    try:
        prompt_metadata = planner.prompt_builder.get_prompt_metadata()
    except Exception:
        prompt_metadata = {}

    _keys = tuple(campaign.parameters.keys())
    now = datetime.now().isoformat()
    payload: Dict[str, Any] = {
        "schema_version": "0.2.0",
        "artifact_type": "stage1_next_experiment_recipe",
        "created_at": now,
        "timestamp": now,
        "campaign_name": campaign.campaign_name,
        "campaign_config": str(cfg_path.resolve()),
        "source_mode": "history_only",
        "source_tag": source_tag,
        "history_db": str(db_path),
        "input_bundle_hash": None,
        "recipe": recipe.model_dump(),
        "optimizer_suggestion": optimizer_suggestion,
        "optimizer_vs_llm_delta": optimizer_vs_llm_delta,
        "safety_box": safety_result.to_dict(),
        "metadata": {
            "mode": "suggest_next_no_ingest",
            "history_db": str(db_path),
            "input_bundle_hash": None,
            "total_trials": len(history),
            "n_distinct_param_sets": memory.count_distinct_parameter_sets(_keys),
            "optimization_mode": (
                "cold_start"
                if memory.is_cold_start(args.cold_start_threshold, _keys)
                else "bayesian"
            ),
            "source_tag": source_tag,
            "objective_target": campaign.get_objective_target(),
            "objective_goal": campaign.get_objective_goal(),
            "objective_formula": campaign.get_objective_formula(),
            "bo_prediction": bo_prediction,
            "bo_provenance": optimizer.get_provenance(),
            "prompt_metadata": prompt_metadata,
            "llm_model_info": llm.get_model_info() if llm is not None else {"available": False},
        },
    }
    output_file = output_dir / "next_experiment_recipe.json"
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("=" * 80)
    logger.info(f"✅ 下一步推荐已写入: {output_file}")
    logger.info(f"   R = {recipe.recommended_parameters.get('R')}")
    logger.info(f"   N = {recipe.recommended_parameters.get('N')}")
    logger.info(f"   confidence_level = {getattr(recipe, 'confidence_level', None)}")
    logger.info("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
