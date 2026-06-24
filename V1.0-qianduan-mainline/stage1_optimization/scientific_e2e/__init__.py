"""端到端跨层演示（WP5）。

把 WP1–WP4 三包缝成一条真链并与"无治理"基线对比:
  认证 Skill → SciTX 事务(故障注入)→ C_P/C_M/C_E → 无效不进 BO →
  后发现错误 → Skill 撤销 → E-Mem 失效传播 → BO 训练视图重建 → 下一最优改变。
证明三项创新**共同**阻止了一条真实/设计的错误链,而非三个孤立软件包。
"""
from .demo_end_to_end import (  # noqa: F401
    run, baseline_ablation, ablation_over_scenarios, GovernedResult, BaselineResult,
)
from .ro_crate import build_ro_crate, build_default_crate, DEFAULT_ARTIFACTS  # noqa: F401
