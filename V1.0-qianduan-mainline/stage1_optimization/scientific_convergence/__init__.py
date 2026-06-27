# -*- coding: utf-8 -*-
"""C³-Harness — Physical/Metrological/Epistemic Convergence Harness（ESAS-OS 2.0 / §10.5）。

shadow 于 `closed_loop.termination_evaluator.evaluate_termination` 之上,**不改写它**:
把"收敛=几条阈值"升级为"收敛状态(五类不确定度)+ 信息价值驱动的动作组合 + 可审计收敛证书"。
不变量:**C³ 的"停"单调 ⊆ legacy 的"停"**(只推迟、绝不更早停),默认 shadow 只记录不夺权。
"""
from .models import (  # noqa: F401
    Action, ConvergenceState, ActionUtility, ConvergenceCertificate,
)
from .policy import UtilityWeights, score_actions, recommend  # noqa: F401
from .harness import build_state_from_termination, certify, shadow_convergence  # noqa: F401
from . import bench  # noqa: F401
