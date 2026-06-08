"""
Optimization Loop Orchestrator
自驱动实验室 (SDL) Stage 1 优化闭环的核心入口

执行流程：
1. 解析 Stage 0 测试结果（当前样品性能）
2. 将结果写入全局记忆库
3. 调用贝叶斯优化器（左脑）获取数学建议
4. 调用智能体（右脑）进行物理机制分析
5. 输出下一步实验方案
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Fix Windows encoding without breaking pytest capture
if sys.platform == 'win32' and "pytest" not in sys.modules:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from canonical_input.campaign_parser import CampaignConfig
from canonical_input.design_space import ParameterSpace
from canonical_input.state0_parser import State0Parser
from campaign_memory.memory_manager import MemoryManager
from optimizers.bayesian_opt import BayesianOptimizer
from optimizers.mobo_optimizer import MOBOOptimizer, locked_v2_objectives

# v2 capability: keys as actually persisted in the attapulgite history DB
# (Stage0 metric names), mapped onto the locked v2 objective contract
# (three_pillars/pillar3_eis_in_the_loop/bo_v2_objective_spec_20260527.md).
MOBO_HISTORY_OBJECTIVE_KEYS = {
    "sigma_key": "conductivity_room_temp_S_cm",  # sigma_RT, maximize
    "ea_high_key": "ea_high_temp_eV",            # Ea_high, minimize
    "ea_low_excess_key": "ea_low_excess_eV",     # ea_low_excess, minimize
}


def build_stage1_optimizer(
    optimizer_kind: str,
    parameter_space,
    memory_manager,
    cold_start_threshold: int = 5,
    optimizer_seed: Optional[int] = None,
):
    """Factory for the Stage1 optimizer (unit-testable, no orchestrator needed).

    ``bo``   -> frozen single-objective :class:`BayesianOptimizer` (default;
                preserves the frozen small-paper closed loop unchanged).
    ``mobo`` -> :class:`MOBOOptimizer` (ParEGO) over the locked 3 objectives,
                with history keys mapped to the attapulgite metric names. This
                is the Line-B v2 capability and must be explicitly opted into.
    """
    kind = (optimizer_kind or "bo").lower()
    if kind == "bo":
        return BayesianOptimizer(
            parameter_space=parameter_space,
            memory_manager=memory_manager,
            cold_start_threshold=cold_start_threshold,
            acq_func="EI",
            random_state=optimizer_seed,
        )
    if kind == "mobo":
        return MOBOOptimizer(
            parameter_space=parameter_space,
            memory_manager=memory_manager,
            objectives=locked_v2_objectives(**MOBO_HISTORY_OBJECTIVE_KEYS),
            cold_start_threshold=cold_start_threshold,
            random_state=optimizer_seed,
        )
    raise ValueError(f"optimizer_kind must be 'bo' or 'mobo', got {optimizer_kind!r}")
from agents.llm_client import LLMClient
from agents.strategy_planner import StrategyPlanner
from contracts.next_experiment_schema import NextExperimentRecipe
from safety.safety_validator import SafetyValidator
from closed_loop import RoundLogger, build_closed_loop_metrics

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class OptimizationOrchestrator:
    """
    优化编排器：协调左脑（优化器）和右脑（智能体）的双脑协同
    
    核心职责：
    1. 数据流管理：Stage 0 → Memory → Optimizer → Agent → Output
    2. 错误处理：确保任何环节失败都能优雅降级
    3. 日志记录：完整追踪决策过程
    """
    
    def __init__(
        self,
        campaign_config_path: str,
        stage0_results_dir: str,
        output_dir: Optional[str] = None,
        db_path: Optional[str] = None,
        source_mode: str = "replay",
        source_tag: Optional[str] = None,
        optimizer_kind: str = "bo",
        optimizer_seed: Optional[int] = None,
    ):
        """
        初始化优化编排器
        
        Args:
            campaign_config_path: 战役配置文件路径
            stage0_results_dir: Stage 0 测试结果目录
            output_dir: 输出目录（None → 优先取 campaign storage.output_dir，回退 ./output）
            db_path:  数据库文件路径（None → 优先取 campaign storage.history_db，回退 history_db_attapulgite.json）
            source_tag: 数据来源标签（None → 优先取 campaign source_tag，回退 campaign_name）
        """
        self.source_mode = source_mode
        self.stage0_real_device = source_mode == "real"
        self.optimizer_kind = (optimizer_kind or "bo").lower()
        self.optimizer_seed = optimizer_seed

        logger.info("=" * 100)
        logger.info("🚀 自驱动实验室 (SDL) - Stage 1 优化闭环启动")
        logger.info("=" * 100)

        # 1. 加载战役配置
        logger.info(f"📋 加载战役配置: {campaign_config_path}")
        try:
            self.campaign_config_path = str(Path(campaign_config_path).resolve())
            self.campaign_config = CampaignConfig(campaign_config_path)
            logger.info(f"✅ 战役名称: {self.campaign_config.campaign_name}")
            logger.info(f"✅ 优化目标: {self.campaign_config.get_objective_target()} ({self.campaign_config.get_objective_goal()})")
        except Exception as e:
            logger.error(f"❌ 加载战役配置失败: {e}")
            raise

        # 1.5 解析 storage / source_tag 默认值（CLI 显式传入时优先）
        stage1_root = Path(__file__).parent
        storage_cfg = (self.campaign_config.config.get("storage") or {})
        campaign_db = storage_cfg.get("history_db")
        campaign_out = storage_cfg.get("output_dir")
        campaign_source_tag = self.campaign_config.config.get("source_tag")

        if output_dir is None:
            output_dir = str((stage1_root / campaign_out).resolve()) if campaign_out else str(stage1_root / "output")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 输出目录: {self.output_dir}")

        if source_tag is None:
            source_tag = campaign_source_tag or self.campaign_config.campaign_name
        self.source_tag = source_tag
        logger.info(f"🏷️ source_tag: {self.source_tag}")

        # 2. 初始化记忆管理器
        if db_path is None:
            if campaign_db:
                db_path = str((stage1_root / campaign_db).resolve())
                logger.info(f"🗄️ 从 campaign storage 解析 db_path: {db_path}")
            else:
                db_path = str(stage1_root / "campaign_memory" / "history_db_attapulgite.json")
        
        logger.info(f"🗄️ 初始化记忆管理器: {db_path}")
        try:
            self.history_db_path = str(Path(db_path).resolve())
            self.memory_manager = MemoryManager(
                db_path=db_path,
                campaign_name=self.campaign_config.campaign_name
            )
            history_count = len(self.memory_manager.get_history())
            logger.info(f"✅ 历史实验数量: {history_count}")
        except Exception as e:
            logger.error(f"❌ 初始化记忆管理器失败: {e}")
            raise
        
        # 3. 初始化 Stage 0 解析器（传入 campaign_config 以支持公式计算）
        logger.info(f"📂 初始化 Stage 0 解析器: {stage0_results_dir}")
        try:
            self.state0_parser = State0Parser(
                stage0_results_dir,
                campaign_config=self.campaign_config
            )
            # 验证数据完整性
            self.state0_parser.validate_data_completeness()
        except Exception as e:
            logger.error(f"❌ 初始化 Stage 0 解析器失败: {e}")
            raise
        
        # 4. 初始化参数空间
        logger.info("🔧 初始化参数空间")
        self.parameter_space = ParameterSpace(self.campaign_config)
        
        # 5. 初始化优化器（左脑）
        # 默认 bo = 冻结的单目标 BayesianOptimizer（不改动冻结闭环）；
        # mobo = Line-B v2 能力：ParEGO 多目标，需显式 --optimizer mobo 开启。
        logger.info(f"🧮 初始化优化器（左脑）: optimizer_kind={self.optimizer_kind}")
        self.optimizer = build_stage1_optimizer(
            optimizer_kind=self.optimizer_kind,
            parameter_space=self.parameter_space,
            memory_manager=self.memory_manager,
            # 2D (R,N)：冷启动按「去重配方数」判断，阈值 5 与 GP 常用初始设计规模一致
            cold_start_threshold=5,
            optimizer_seed=self.optimizer_seed,
        )
        
        # 6. 初始化智能体（右脑）
        logger.info("🤖 初始化策略规划器（右脑）")
        try:
            # Line-B guardrail：temperature=0.0 求确定性（prereg 要求）；
            # gpt-5.4 推理占 token，max_tokens 给足。其余配置走 .env（OpenRouter）。
            self.llm_client = LLMClient(temperature=0.0, max_tokens=8000)
            # 测试 LLM 连接
            if not self.llm_client.test_connection():
                logger.warning("⚠️ LLM 连接测试失败，将在需要时重试")
        except Exception as e:
            logger.warning(f"⚠️ LLM 客户端初始化失败: {e}")
            self.llm_client = None
        
        self.strategy_planner = StrategyPlanner(
            campaign_config=self.campaign_config,
            memory_manager=self.memory_manager,
            llm_client=self.llm_client
        )
        self.safety_validator = SafetyValidator(self.campaign_config)
        
        logger.info("✅ 所有组件初始化完成")
        logger.info("=" * 100)
    
    def run_optimization_loop(self) -> NextExperimentRecipe:
        """
        执行完整的优化闭环
        
        Returns:
            NextExperimentRecipe: 下一步实验方案
            
        Raises:
            Exception: 任何环节失败都会抛出异常
        """
        logger.info("🔄 开始优化闭环...")
        logger.info("")
        
        # Step 1: 解析 Stage 0 测试结果
        logger.info("=" * 100)
        logger.info("Step 1/6: 解析 Stage 0 测试结果")
        logger.info("=" * 100)
        
        try:
            current_metrics = self.state0_parser.extract_objective_metrics()
            current_parameters = self.state0_parser.extract_experiment_parameters()
            sample_id = self.state0_parser.get_latest_sample_id()
            physical_features = self.state0_parser.get_physical_features()
            
            logger.info(f"✅ 样品 ID: {sample_id}")
            logger.info(f"✅ 当前性能指标: {current_metrics}")
            if physical_features:
                logger.info(f"✅ 物理特征: {physical_features}")
            logger.info(f"✅ 实验参数: {current_parameters}")
        except Exception as e:
            logger.error(f"❌ 解析 Stage 0 结果失败: {e}")
            logger.error("请检查 Stage 0 输出格式是否正确")
            raise

        objective_name = self.campaign_config.get_objective_target()
        objective_invalid_reasons = list(current_metrics.get("objective_invalid_reasons") or [])
        objective_valid = bool(current_metrics.get("objective_valid", True))
        persisted_objectives = {
            key: value
            for key, value in current_metrics.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        if objective_name not in persisted_objectives:
            objective_valid = False
            if "objective_target_missing" not in objective_invalid_reasons:
                objective_invalid_reasons.append("objective_target_missing")
        if self.stage0_real_device:
            if not current_parameters:
                raise ValueError(
                    "Real mode requires valid Stage0 parameters; refusing to write history_db"
                )
            if not objective_valid:
                raise ValueError(
                    "Real mode requires a valid Stage0 objective; refusing to write history_db "
                    f"and generate a new recipe. reasons={objective_invalid_reasons}"
                )
        
        logger.info("")
        
        # Step 2: 将结果写入记忆库
        logger.info("=" * 100)
        logger.info("Step 2/6: 记忆固化（写入全局数据库）")
        logger.info("=" * 100)
        
        try:
            # 只有当参数非空时才写入
            if current_parameters:
                trial_id = self.memory_manager.add_trial(
                    parameters=current_parameters,
                    objectives=persisted_objectives,
                    metadata={
                        "sample_id": sample_id,
                        "source": "stage0_measurement",
                        "source_mode": self.source_mode,
                        "source_tag": self.source_tag,
                        "input_bundle_hash": self.state0_parser.get_input_bundle_hash(),
                        "objective_valid": objective_valid,
                        "invalid_reasons": objective_invalid_reasons,
                        "parser_mode": self.state0_parser.get_parser_mode(),
                        "stage0_bundle_path": self.state0_parser.get_bundle_path(),
                        "timestamp": datetime.now().isoformat()
                    }
                )
                logger.info(f"✅ 实验记录已保存 | Trial ID: {trial_id}")
            else:
                logger.warning("⚠️ 实验参数为空，跳过记忆写入")
        except Exception as e:
            logger.error(f"❌ 写入记忆库失败: {e}")
            if self.stage0_real_device:
                raise
            logger.warning("⚠️ 继续执行，但历史数据可能不完整")
        
        logger.info("")
        
        # Step 3: 获取历史最优结果
        logger.info("=" * 100)
        logger.info("Step 3/6: 查询历史最优结果")
        logger.info("=" * 100)
        
        objective_name = self.campaign_config.get_objective_target()
        goal = self.campaign_config.get_objective_goal()
        
        best_trial = self.memory_manager.get_best_trial(objective_name, goal)
        
        if best_trial:
            best_value = best_trial["objectives"][objective_name]
            best_params = best_trial["parameters"]
            logger.info(f"✅ 历史最优: {objective_name} = {best_value:.2e}")
            logger.info(f"✅ 最优参数: {best_params}")
            
            # 计算当前性能相对于最优的表现
            if objective_name in current_metrics:
                current_value = current_metrics[objective_name]
                if goal == "maximize":
                    improvement = ((current_value - best_value) / best_value) * 100
                else:
                    improvement = ((best_value - current_value) / best_value) * 100
                
                status = "📈 提升" if improvement > 0 else "📉 下降"
                logger.info(f"{status} {abs(improvement):.2f}%")
        else:
            logger.info("ℹ️ 暂无历史数据（冷启动阶段）")
        
        # 显示统计信息
        stats = self.memory_manager.get_statistics(objective_name)
        if stats["count"] > 0:
            logger.info(f"📊 历史统计: 均值={stats['mean']:.2e}, 标准差={stats['std']:.2e}, 范围=[{stats['min']:.2e}, {stats['max']:.2e}]")
        
        logger.info("")
        
        # Step 4: 调用优化器（左脑）
        logger.info("=" * 100)
        logger.info("Step 4/6: 左脑决策（贝叶斯优化器）")
        logger.info("=" * 100)
        
        try:
            optimizer_suggestion = self.optimizer.suggest_next()
            logger.info(f"✅ 优化器建议: {optimizer_suggestion}")
            
            # 如果优化器有模型预测，显示预测值
            prediction = self.optimizer.get_model_prediction(optimizer_suggestion)
            if prediction:
                mean, std = prediction
                logger.info(f"📈 模型预测: {objective_name} = {mean:.2e} ± {std:.2e}")
        except Exception as e:
            logger.error(f"❌ 优化器调用失败: {e}")
            raise
        
        logger.info("")
        
        # Step 5: 调用智能体（右脑）
        logger.info("=" * 100)
        logger.info("Step 5/6: 右脑决策（智能体物理分析）")
        logger.info("=" * 100)
        
        recipe = self.strategy_planner.decide_with_fallback(
            current_metrics=current_metrics,
            optimizer_suggestion=optimizer_suggestion,
            fallback_to_optimizer=True,
            physical_features=physical_features,
        )
        if any("LLM 调用失败" in str(w) for w in (recipe.warnings or [])):
            logger.warning("⚠️ 智能体降级：仅使用优化器建议（LLM 不可用或输出无效）")
        else:
            logger.info("✅ 智能体决策完成")
        
        logger.info("")
        
        # Step 6: 输出结果
        logger.info("=" * 100)
        logger.info("Step 6/6: 输出实验方案")
        logger.info("=" * 100)
        
        self._save_and_display_results(recipe, optimizer_suggestion, physical_features)
        
        logger.info("")
        logger.info("=" * 100)
        logger.info("✅ 优化闭环执行完成")
        logger.info("=" * 100)
        
        return recipe
    
    def _save_and_display_results(
        self,
        recipe: NextExperimentRecipe,
        optimizer_suggestion: Dict[str, Any],
        physical_features: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        保存并展示结果
        
        Args:
            recipe: 实验方案
            optimizer_suggestion: 优化器建议（用于对比）
        """
        # 保存为 JSON
        output_file = self.output_dir / "next_experiment_recipe.json"
        
        safety_result = self.safety_validator.validate(
            recipe.recommended_parameters,
            physical_features=physical_features or {}
        )
        optimizer_vs_llm_delta = self._build_optimizer_vs_llm_delta(
            optimizer_suggestion,
            recipe
        )

        _param_keys = tuple(self.campaign_config.parameters.keys())
        now = datetime.now().isoformat()
        input_bundle_hash = self.state0_parser.get_input_bundle_hash()
        output_data = {
            "schema_version": "0.2.0",
            "artifact_type": "stage1_next_experiment_recipe",
            "created_at": now,
            "timestamp": now,
            "campaign_name": self.campaign_config.campaign_name,
            "campaign_config": self.campaign_config_path,
            "source_mode": self.source_mode,
            "source_tag": self.source_tag,
            "history_db": self.history_db_path,
            "input_bundle_hash": input_bundle_hash,
            "recipe": recipe.model_dump(),
            "optimizer_suggestion": optimizer_suggestion,
            "optimizer_vs_llm_delta": optimizer_vs_llm_delta,
            "safety_box": safety_result.to_dict(),
            "metadata": {
                "total_trials": len(self.memory_manager.get_history()),
                "n_distinct_param_sets": self.memory_manager.count_distinct_parameter_sets(_param_keys),
                "optimization_mode": (
                    "cold_start"
                    if self.memory_manager.is_cold_start(self.optimizer.threshold, _param_keys)
                    else "bayesian"
                ),
                "source_mode": self.source_mode,
                "source_tag": self.source_tag,
                "history_db": self.history_db_path,
                "input_bundle_hash": input_bundle_hash,
                "stage0_real_device": self.stage0_real_device,
                "objective_target": self.campaign_config.get_objective_target(),
                "objective_goal": self.campaign_config.get_objective_goal(),
                "objective_formula": self.campaign_config.get_objective_formula(),
                "bo_provenance": self.optimizer.get_provenance(),
                "prompt_metadata": self.strategy_planner.prompt_builder.get_prompt_metadata(),
                "llm_model_info": (
                    self.llm_client.get_model_info()
                    if self.llm_client is not None
                    else {"available": False}
                )
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 实验方案已保存: {output_file}")
        logger.info("")

        # P-Stage1-A/B: 写入 closed-loop round 三件套 + 聚合 metrics
        try:
            self._emit_closed_loop_artifacts(
                recipe=recipe,
                optimizer_suggestion=optimizer_suggestion,
                optimizer_vs_llm_delta=optimizer_vs_llm_delta,
                safety_box=safety_result.to_dict(),
                physical_features=physical_features,
            )
        except Exception as e:
            logger.warning(f"⚠️ closed-loop artifacts 写入失败: {e}")

        # 漂亮的终端输出
        self._print_beautiful_summary(recipe, optimizer_suggestion)

    def _emit_closed_loop_artifacts(
        self,
        recipe: NextExperimentRecipe,
        optimizer_suggestion: Dict[str, Any],
        optimizer_vs_llm_delta: Dict[str, Any],
        safety_box: Dict[str, Any],
        physical_features: Optional[Dict[str, Any]],
    ) -> None:
        """P-Stage1-A/B: round_NNN_{suggestion,stage0_result,decision_trace}.json + closed_loop_metrics.json."""
        round_logger = RoundLogger(self.output_dir)

        # 复用 Step 1/2 已经解析过的 Stage0 数据（避免再读一次）
        try:
            stage0_metrics = self.state0_parser.extract_objective_metrics()
        except Exception:
            stage0_metrics = {}
        try:
            stage0_parameters = self.state0_parser.extract_experiment_parameters()
        except Exception:
            stage0_parameters = {}
        try:
            sample_id = self.state0_parser.get_latest_sample_id()
        except Exception:
            sample_id = None

        parser_mode = (
            self.state0_parser.get_parser_mode()
            if hasattr(self.state0_parser, "get_parser_mode")
            else "legacy"
        )
        bundle_path = (
            self.state0_parser.get_bundle_path()
            if hasattr(self.state0_parser, "get_bundle_path")
            else None
        )
        validity_flags = (
            self.state0_parser.get_validity_flags()
            if hasattr(self.state0_parser, "get_validity_flags")
            else []
        )

        round_id, sug_p, st_p, tr_p = round_logger.write_all(
            campaign_name=self.campaign_config.campaign_name,
            source_mode=self.source_mode,
            source_tag=self.source_tag,
            optimizer_suggestion=optimizer_suggestion,
            recipe_dict=recipe.model_dump(),
            optimizer_vs_llm_delta=optimizer_vs_llm_delta,
            safety_box=safety_box,
            objective_target=self.campaign_config.get_objective_target(),
            objective_goal=self.campaign_config.get_objective_goal(),
            objective_formula=self.campaign_config.get_objective_formula(),
            bo_provenance=self.optimizer.get_provenance(),
            prompt_metadata=self.strategy_planner.prompt_builder.get_prompt_metadata(),
            llm_model_info=(self.llm_client.get_model_info() if self.llm_client else {"available": False}),
            sample_id=sample_id,
            parser_mode=parser_mode,
            stage0_bundle_path=bundle_path,
            stage0_parameters=stage0_parameters,
            stage0_metrics=stage0_metrics,
            stage0_physical_features=physical_features or {},
            stage0_validity_flags=validity_flags,
        )
        logger.info(f"🌀 closed-loop round {round_id:03d} → {sug_p.name}, {st_p.name}, {tr_p.name}")

        metrics = build_closed_loop_metrics(
            output_dir=self.output_dir,
            n_initial_points=3,
            objective_target=self.campaign_config.get_objective_target(),
            objective_goal=self.campaign_config.get_objective_goal(),
            campaign_name=self.campaign_config.campaign_name,
            campaign_config=self.campaign_config.config,
        )
        logger.info(
            f"📊 closed_loop_metrics: rounds={metrics.get('n_closed_loop_rounds')}, "
            f"validity={metrics.get('closed_loop_validity')}, "
            f"best_final_score={metrics.get('best_final_score')}"
        )

    def _build_optimizer_vs_llm_delta(
        self,
        optimizer_suggestion: Dict[str, Any],
        recipe: NextExperimentRecipe
    ) -> Dict[str, Any]:
        """生成 BO 建议与 LLM 最终参数的结构化差异。"""
        delta = {}
        for param, llm_value in recipe.recommended_parameters.items():
            opt_value = optimizer_suggestion.get(param)
            numeric_delta = None
            if isinstance(opt_value, (int, float)) and isinstance(llm_value, (int, float)):
                numeric_delta = llm_value - opt_value
            delta[param] = {
                "optimizer": opt_value,
                "llm": llm_value,
                "delta": numeric_delta,
                "status": "ok" if opt_value == llm_value else "adjusted"
            }

        return {
            "parameters": delta,
            "adjusted": any(item["status"] == "adjusted" for item in delta.values()),
            "adjustment_reason": recipe.reasoning,
            "warnings": recipe.warnings,
        }
    
    def _print_beautiful_summary(
        self,
        recipe: NextExperimentRecipe,
        optimizer_suggestion: Dict[str, Any]
    ) -> None:
        """
        打印漂亮的摘要信息
        
        Args:
            recipe: 实验方案
            optimizer_suggestion: 优化器建议
        """
        print("\n" + "=" * 100)
        print("Next Experiment Recipe")
        print("=" * 100)
        
        # 推荐参数
        print("\nRecommended Parameters:")
        print("-" * 100)
        for param, value in recipe.recommended_parameters.items():
            # 检查是否与优化器建议一致
            optimizer_value = optimizer_suggestion.get(param)
            match_status = "OK" if value == optimizer_value else "ADJUSTED"
            
            print(f"  - {param:30s} = {value:15} {match_status}")
        
        # 置信度
        print("\n" + "-" * 100)
        confidence_bar = "#" * int(recipe.confidence_score * 20)
        print(f"Confidence: {recipe.confidence_score:.2f} [{confidence_bar:20s}]")
        
        # 物理推理
        print("\n" + "-" * 100)
        print("Physical Reasoning:")
        print("-" * 100)
        # 自动换行显示
        reasoning_lines = self._wrap_text(recipe.reasoning, width=96)
        for line in reasoning_lines:
            print(f"  {line}")
        
        # 预期结果
        print("\n" + "-" * 100)
        print("Expected Outcome:")
        print("-" * 100)
        outcome_lines = self._wrap_text(recipe.expected_outcome, width=96)
        for line in outcome_lines:
            print(f"  {line}")
        
        # 风险警告
        if recipe.warnings:
            print("\n" + "-" * 100)
            print(f"Warnings ({len(recipe.warnings)}):")
            print("-" * 100)
            for i, warning in enumerate(recipe.warnings, 1):
                print(f"  {i}. {warning}")
        
        # 物理约束检查状态
        print("\n" + "-" * 100)
        constraint_status = "checked" if recipe.physical_constraints_checked else "not checked"
        print(f"Physical constraints: {constraint_status}")
        
        print("=" * 100 + "\n")
    
    @staticmethod
    def _wrap_text(text: str, width: int = 80) -> list:
        """
        文本自动换行
        
        Args:
            text: 原始文本
            width: 每行宽度
            
        Returns:
            换行后的文本列表
        """
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            if current_length + word_length + len(current_line) <= width:
                current_line.append(word)
                current_length += word_length
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines


def main():
    """主函数：解析命令行参数并执行优化闭环"""
    parser = argparse.ArgumentParser(
        description="SDL Stage 1 优化闭环 - 双脑协同决策系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_optimization_loop.py \\
    --campaign_config campaigns/example_campaign.json \\
    --stage0_results_dir ../stage0_measurement/results/sample_001 \\
    --output_dir ./output

环境变量:
  LLM_API_KEY: LLM API 密钥（必需）
  LLM_BASE_URL: OpenAI 兼容 API 地址
  LLM_MODEL: 模型名称
        """
    )
    
    parser.add_argument(
        "--campaign_config",
        type=str,
        required=True,
        help="战役配置文件路径 (JSON)"
    )
    
    parser.add_argument(
        "--stage0_results_dir",
        type=str,
        required=True,
        help="Stage 0 测试结果目录路径"
    )
    
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="输出目录路径（缺省时取 campaign storage.output_dir，再回退 ./output）"
    )

    parser.add_argument(
        "--db_path",
        type=str,
        default=None,
        help="数据库文件路径（缺省时取 campaign storage.history_db，再回退 history_db_attapulgite.json）"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="启用详细日志输出"
    )

    parser.add_argument(
        "--mode",
        choices=["replay", "virtual_oracle", "real"],
        default="replay",
        help="数据来源模式：replay/virtual_oracle/real（默认: replay）"
    )

    parser.add_argument(
        "--source_tag",
        type=str,
        default=None,
        help="数据来源标签（缺省时优先取 campaign JSON 里的 source_tag，再回退 campaign_name）"
    )

    parser.add_argument(
        "--optimizer",
        choices=["bo", "mobo"],
        default="bo",
        help="优化器：bo=冻结单目标贝叶斯优化（默认）；mobo=Line-B 多目标 ParEGO 闭环"
    )

    parser.add_argument(
        "--optimizer_seed",
        type=int,
        default=None,
        help="优化器随机种子（用于可复现的前瞻 MOBO 轮次；缺省=动态种子）"
    )

    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 执行优化闭环
    try:
        orchestrator = OptimizationOrchestrator(
            campaign_config_path=args.campaign_config,
            stage0_results_dir=args.stage0_results_dir,
            output_dir=args.output_dir,
            db_path=args.db_path,
            source_mode=args.mode,
            source_tag=args.source_tag,
            optimizer_kind=args.optimizer,
            optimizer_seed=args.optimizer_seed,
        )
        
        recipe = orchestrator.run_optimization_loop()
        
        # 返回成功状态码
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断执行")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"\n❌ 执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
