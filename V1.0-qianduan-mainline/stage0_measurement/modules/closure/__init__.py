"""Sample-level Closure Agent (researcher-facing only).

This module produces a *researcher-facing* short narrative report for one
finished sample.  Its output is intentionally NOT consumed by Stage1 BO,
Stage2 statistics, or Stage3 reasoning — it exists solely to give the human
researcher a quick, grounded read on the sample they just measured.

Public surface:
    - generate_sample_closure_report(...)
    - SampleClosureReport (Pydantic model)
    - build_deterministic_features(...)
"""

from .closure_schema import (
    ClosureAgentInput,
    SampleClosureReport,
    PerformanceCard,
    QualityCard,
    PhaseTransitionInterp,
    MechanismNote,
    CampaignComparisonLite,
    RiskFlag,
    ReportMeta,
    SampleIdentity,
)
from .closure_features import build_deterministic_features
from .closure_agent import generate_sample_closure_report

__all__ = [
    "ClosureAgentInput",
    "SampleClosureReport",
    "PerformanceCard",
    "QualityCard",
    "PhaseTransitionInterp",
    "MechanismNote",
    "CampaignComparisonLite",
    "RiskFlag",
    "ReportMeta",
    "SampleIdentity",
    "build_deterministic_features",
    "generate_sample_closure_report",
]
