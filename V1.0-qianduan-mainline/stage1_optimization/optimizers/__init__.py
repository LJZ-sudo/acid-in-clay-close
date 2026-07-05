"""
Optimizers Module
优化器模块：封装各种优化算法（贝叶斯优化、遗传算法等）

- ``BayesianOptimizer``: 冻结主线使用的单目标 GP+EI 优化器。
- ``MOBOOptimizer`` 与 Pareto 工具（Tier 3 / v2 能力）: 多目标 ParEGO 优化器，
  独立于冻结闭环，按
  ``experiments/three_pillars/pillar3_eis_in_the_loop/bo_v2_objective_spec_20260527.md``
  定义目标。
"""
from .bayesian_opt import BayesianOptimizer
from .mobo_optimizer import (
    MOBOOptimizer,
    Objective,
    annotate_pareto,
    dominated_hypervolume,
    dominates,
    locked_v2_objectives,
    parego_scalarize,
    pareto_front_indices,
    score_v3,
)

__all__ = [
    "BayesianOptimizer",
    "MOBOOptimizer",
    "Objective",
    "locked_v2_objectives",
    "dominates",
    "pareto_front_indices",
    "annotate_pareto",
    "score_v3",
    "dominated_hypervolume",
    "parego_scalarize",
]
