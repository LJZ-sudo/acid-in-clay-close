"""
Stage 2 Evidence Agent Package
"""

from .main_agent import Stage2Agent
from .core.schema import EvidenceUnit, EvidenceAtlas, ClaimLevel, EvidenceTheme

__version__ = "2.0.0"

__all__ = [
    "Stage2Agent",
    "EvidenceUnit",
    "EvidenceAtlas",
    "ClaimLevel",
    "EvidenceTheme",
]
