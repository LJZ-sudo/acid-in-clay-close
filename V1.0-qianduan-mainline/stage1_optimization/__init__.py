"""
Stage 1 Optimization Module
自驱动实验室 (SDL) - 优化闭环模块

核心组件:
- CampaignConfig: 战役配置管理
- MemoryManager: 实验历史记忆
- BayesianOptimizer: 贝叶斯优化器（左脑）
- StrategyPlanner: 策略规划器（右脑）
- OptimizationOrchestrator: 优化编排器
"""

__version__ = "1.0.0"
__author__ = "SDL Team"

# 导出核心类
from .canonical_input.campaign_parser import CampaignConfig
from .canonical_input.design_space import ParameterSpace
from .canonical_input.state0_parser import State0Parser
from .campaign_memory.memory_manager import MemoryManager
from .optimizers.bayesian_opt import BayesianOptimizer
from .agents.llm_client import LLMClient
from .agents.strategy_planner import StrategyPlanner
from .contracts.next_experiment_schema import NextExperimentRecipe

__all__ = [
    "CampaignConfig",
    "ParameterSpace",
    "State0Parser",
    "MemoryManager",
    "BayesianOptimizer",
    "LLMClient",
    "StrategyPlanner",
    "NextExperimentRecipe",
]
