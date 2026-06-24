# -*- coding: utf-8 -*-
"""三重提交状态定义（M5-A）。"""
from __future__ import annotations


class PhysicalCommit:
    """C_P:物理动作是否发生。"""
    NOT_STARTED = "NOT_STARTED"
    DISPATCHED = "DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EFFECT_OBSERVED = "EFFECT_OBSERVED"     # 已确认发生
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"
    RECONSTRUCTED = "RECONSTRUCTED"         # 超时后经核对重建为"已发生"

    COMMITTED = frozenset({EFFECT_OBSERVED, RECONSTRUCTED})

    @classmethod
    def is_committed(cls, status: str) -> bool:
        return status in cls.COMMITTED


class MetrologicalCommit:
    """C_M:测量是否满足计量资格。"""
    VALID = "VALID"
    CONDITIONAL = "CONDITIONAL"
    INVALID = "INVALID"

    COMMITTED = frozenset({VALID})

    @classmethod
    def is_committed(cls, status: str) -> bool:
        return status in cls.COMMITTED


class EpistemicCommit:
    """C_E:是否允许进入 BO/主张/长期记忆。"""
    PRIMARY_EVIDENCE = "PRIMARY_EVIDENCE"
    SENSITIVITY_ONLY = "SENSITIVITY_ONLY"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    REJECTED = "REJECTED"

    COMMITTED = frozenset({PRIMARY_EVIDENCE})

    @classmethod
    def is_committed(cls, status: str) -> bool:
        return status in cls.COMMITTED
