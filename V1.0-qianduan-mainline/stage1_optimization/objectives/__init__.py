"""目标函数注册表(M1-6 / G7):隔离"训练目标"与"审计目标",各带冻结哈希。"""
from .registry import (  # noqa: F401
    ObjectiveDefinition,
    load_registry,
    get_objective,
    objective_for_role,
    stamp_metadata,
    get_best_trial_by_definition,
    assert_trial_objective_consistency,
)
