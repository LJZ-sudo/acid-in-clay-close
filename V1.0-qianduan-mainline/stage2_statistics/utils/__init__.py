"""
Utils Module
基础设施模块
"""

from .statistics_lib import (
    bootstrap_ci,
    calculate_aic,
    calculate_aicc,
    calculate_bic,
    detect_outliers_iqr,
)
from .viz_engine import VizEngine, ACADEMIC_COLORS

__all__ = [
    "bootstrap_ci",
    "calculate_aic",
    "calculate_aicc",
    "calculate_bic",
    "detect_outliers_iqr",
    "VizEngine",
    "ACADEMIC_COLORS",
]
