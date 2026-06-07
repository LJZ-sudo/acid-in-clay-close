"""
Stage 2 Core Module
提供证据结构的类型定义和数据协议
"""

from .schema import (
    ClaimLevel,
    EvidenceTheme,
    EvidenceUnit,
    EvidenceAtlas,
)
from .base_specialist import BaseSpecialist

__all__ = [
    "ClaimLevel",
    "EvidenceTheme",
    "EvidenceUnit",
    "EvidenceAtlas",
    "BaseSpecialist",
]
