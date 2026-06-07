"""
Strategy Planner
智能体核心逻辑：整合 LLM 和提示词构建器，做出最终决策
"""
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import ValidationError

from .llm_client import LLMClient
from .prompts.planner_prompts import PromptBuilder
from contracts.next_experiment_schema import NextExperimentRecipe
from canonical_input.campaign_parser import CampaignConfig
from campaign_memory.memory_manager import MemoryManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StrategyPlanner:
    """
    策略规划器（右脑 - 智能体核心）
    
    职责：
    1. 整合 LLM 客户端和提示词构建器
    2. 调用 LLM 分析实验数据和优化器建议
    3. 严格验证 LLM 输出的参数合法性
    4. 返回符合契约的实验方案
    """
    
    def __init__(
        self,
        campaign_config: CampaignConfig,
        memory_manager: MemoryManager,
        llm_client: Optional[LLMClient] = None,
        enable_validation: bool = True
    ):
        """
        初始化策略规划器
        
        Args:
            campaign_config: 实验战役配置
            memory_manager: 记忆管理器
            llm_client: LLM 客户端，如果为 None 则自动创建
            enable_validation: 是否启用严格参数验证
        """
        self.campaign_config = campaign_config
        self.memory_manager = memory_manager
        self.enable_validation = enable_validation
        
        # 初始化 LLM 客户端
        if llm_client is None:
            logger.info("未提供 LLM 客户端，使用默认配置创建")
            self.llm_client = LLMClient()
        else:
            self.llm_client = llm_client
        
        # 初始化提示词构建器
        self.prompt_builder = PromptBuilder(campaign_config)
        
        logger.info(
            f"策略规划器初始化完成 | "
            f"战役: {campaign_config.campaign_name} | "
            f"验证模式: {'开启' if enable_validation else '关闭'}"
        )
    
    def decide_next_step(
        self,
        current_metrics: Dict[str, float],
        optimizer_suggestion: Dict[str, Any],
        include_historical_context: bool = True,
        physical_features: Optional[Dict[str, Any]] = None
    ) -> NextExperimentRecipe:
        """
        决策下一步实验参数（核心方法）
        
        Args:
            current_metrics: 当前样品的测试指标
            optimizer_suggestion: 贝叶斯优化器推荐的参数
            include_historical_context: 是否包含历史实验上下文
            physical_features: 物理特征（包含 Arrhenius 分析）
            
        Returns:
            NextExperimentRecipe: 经过验证的实验方案
            
        Raises:
            ValidationError: LLM 输出不符合 Schema
            ValueError: 参数验证失败
        """
        logger.info("=" * 80)
        logger.info("🧠 策略规划器开始决策...")
        logger.info("=" * 80)
        
        # 1. 获取历史最优数据
        best_trial = None
        historical_trials = None
        
        if include_historical_context:
            objective_name = self.campaign_config.get_objective_target()
            goal = self.campaign_config.get_objective_goal()
            
            best_trial = self.memory_manager.get_best_trial(objective_name, goal)
            historical_trials = self.memory_manager.get_history()
            
            if best_trial:
                logger.info(
                    f"📊 历史最优: {objective_name} = "
                    f"{best_trial['objectives'][objective_name]:.2e}"
                )
            else:
                logger.info("📊 暂无历史数据（冷启动阶段）")
        
        # 2. 构建提示词
        logger.info("📝 构建 LLM 提示词...")
        
        best_metrics = None
        if best_trial:
            best_metrics = best_trial.get("objectives", {})
        
        system_prompt, user_prompt = self.prompt_builder.build_complete_prompt(
            current_metrics=current_metrics,
            best_historical_metrics=best_metrics,
            optimizer_suggestion=optimizer_suggestion,
            historical_trials=historical_trials,
            physical_features=physical_features
        )
        
        logger.debug(f"系统提示词长度: {len(system_prompt)} 字符")
        logger.debug(f"用户提示词长度: {len(user_prompt)} 字符")
        
        # 3. 调用 LLM
        logger.info("🤖 调用 LLM 进行机理分析...")
        
        try:
            # 规划提示词较长；max_tokens 过小会导致 ```json``` 在 recommended_parameters 处被截断，解析失败。
            _mt = max(int(getattr(self.llm_client, "max_tokens", 2000) or 2000), 4096)
            json_response = self.llm_client.generate_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
                retry_count=3,
                completion_max_tokens=_mt,
            )
        except Exception as e:
            logger.error(f"❌ LLM 调用失败: {e}")
            raise ValueError(f"LLM 调用失败，无法生成实验方案: {e}") from e
        
        # 4. 解析和验证 JSON
        logger.info("🔍 验证 LLM 输出...")
        
        try:
            recipe = NextExperimentRecipe.model_validate_json(json_response)
            logger.info("✅ JSON Schema 验证通过")
        except ValidationError as e:
            logger.error(f"❌ JSON Schema 验证失败:\n{e}")
            logger.error(f"LLM 原始输出:\n{json_response}")
            raise ValueError(
                f"LLM 输出不符合 NextExperimentRecipe Schema: {e}"
            ) from e
        
        # 5. 硬校验：检查参数键是否合法
        if self.enable_validation:
            self._validate_parameter_keys(recipe.recommended_parameters)
        
        # 6. 验证参数值是否在合法范围内
        if self.enable_validation:
            try:
                self.campaign_config.validate_parameters(recipe.recommended_parameters)
                logger.info("✅ 参数范围验证通过")
            except ValueError as e:
                logger.error(f"❌ 参数范围验证失败: {e}")
                logger.error(f"LLM 推荐参数: {recipe.recommended_parameters}")
                raise ValueError(
                    f"LLM 推荐的参数超出合法范围: {e}"
                ) from e
        
        # 7. 输出决策结果
        logger.info("=" * 80)
        logger.info("✅ 策略规划完成")
        logger.info("=" * 80)
        logger.info(f"推荐参数: {recipe.recommended_parameters}")
        logger.info(f"置信度: {recipe.confidence_score:.2f}")
        logger.info(f"预期结果: {recipe.expected_outcome[:100]}...")
        
        if recipe.warnings:
            logger.warning(f"⚠️ 风险警告 ({len(recipe.warnings)} 项):")
            for i, warning in enumerate(recipe.warnings, 1):
                logger.warning(f"  {i}. {warning}")
        
        return recipe
    
    def _validate_parameter_keys(self, parameters: Dict[str, Any]) -> None:
        """
        硬校验：检查参数键是否合法
        
        Args:
            parameters: LLM 推荐的参数字典
            
        Raises:
            ValueError: 存在非法参数键
        """
        valid_keys = set(self.campaign_config.get_parameter_names())
        actual_keys = set(parameters.keys())
        
        # 检查是否有多余的键
        extra_keys = actual_keys - valid_keys
        if extra_keys:
            error_msg = (
                f"LLM 输出包含非法参数键: {extra_keys}\n"
                f"合法参数键: {valid_keys}"
            )
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        # 检查是否缺少必需的键
        missing_keys = valid_keys - actual_keys
        if missing_keys:
            error_msg = (
                f"LLM 输出缺少必需参数键: {missing_keys}\n"
                f"合法参数键: {valid_keys}"
            )
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"✅ 参数键验证通过: {actual_keys}")
    
    def decide_with_fallback(
        self,
        current_metrics: Dict[str, float],
        optimizer_suggestion: Dict[str, Any],
        fallback_to_optimizer: bool = True,
        physical_features: Optional[Dict[str, Any]] = None,
    ) -> NextExperimentRecipe:
        """
        带降级策略的决策方法
        
        先调用 LLM；若失败且 fallback_to_optimizer=True，**直接**返回优化器建议，
        不再重复调用 LLM（避免 suggest_next / run_optimization 失败后二次打满超时）。
        
        Args:
            current_metrics: 当前样品的测试指标
            optimizer_suggestion: 贝叶斯优化器推荐的参数
            fallback_to_optimizer: 是否在失败时降级到优化器建议
            physical_features: 与 decide_next_step 相同的物理特征（Arrhenius 等）
            
        Returns:
            NextExperimentRecipe: 实验方案
        """
        try:
            return self.decide_next_step(
                current_metrics=current_metrics,
                optimizer_suggestion=optimizer_suggestion,
                include_historical_context=True,
                physical_features=physical_features,
            )
        except Exception as e:
            logger.error(f"❌ 策略规划失败: {e}")
            
            if fallback_to_optimizer:
                logger.warning("⚠️ 降级策略：直接采用优化器建议（不再重复调用 LLM）")
                
                # 创建一个简单的 Recipe
                return NextExperimentRecipe(
                    reasoning=(
                        "由于 LLM 调用失败，直接采用贝叶斯优化器的数学建议。"
                        "该参数组合基于高斯过程回归，预期能够在探索-利用权衡中找到最优解。"
                    ),
                    expected_outcome=(
                        "预期该参数组合能够改善目标指标。"
                        "具体性能需要实验验证。"
                    ),
                    recommended_parameters=optimizer_suggestion,
                    confidence_score=0.5,
                    warnings=["LLM 调用失败，未进行物理机制分析"],
                    physical_constraints_checked=False
                )
            else:
                raise
    
    def batch_evaluate_candidates(
        self,
        current_metrics: Dict[str, float],
        candidate_suggestions: List[Dict[str, Any]]
    ) -> List[NextExperimentRecipe]:
        """
        批量评估多个候选参数（用于并行实验）
        
        Args:
            current_metrics: 当前样品的测试指标
            candidate_suggestions: 多个候选参数列表
            
        Returns:
            实验方案列表
        """
        logger.info(f"🔄 批量评估 {len(candidate_suggestions)} 个候选参数...")
        
        recipes = []
        for i, suggestion in enumerate(candidate_suggestions, 1):
            logger.info(f"评估候选 {i}/{len(candidate_suggestions)}...")
            
            try:
                recipe = self.decide_next_step(
                    current_metrics=current_metrics,
                    optimizer_suggestion=suggestion,
                    include_historical_context=(i == 1)  # 只在第一个包含历史
                )
                recipes.append(recipe)
            except Exception as e:
                logger.error(f"候选 {i} 评估失败: {e}")
                continue
        
        logger.info(f"✅ 批量评估完成，成功 {len(recipes)}/{len(candidate_suggestions)} 个")
        
        return recipes
