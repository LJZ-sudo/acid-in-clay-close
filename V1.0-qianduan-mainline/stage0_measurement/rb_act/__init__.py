# -*- coding: utf-8 -*-
"""Rb-ACT — Active, Calibrated, Teachable bulk-resistance skill（ESAS-OS 2.0 / PC-Skills v2）。

在 legacy `rb_fitting.fit_all_rb_methods` 之上的决策层:Rb 后验 + 弃权 + 主动测量建议 +
SciTX C_M 准入信号。**legacy 永不覆盖**;接入走五级门(本模块=R0 离线 shadow)。
"""
from .schema import (  # noqa: F401
    RbActResult, RbPosterior, ActiveRequest,
    REPORT, REPORT_CONDITIONAL, ABSTAIN,
    EXTEND_FREQ_HIGH, EXTEND_FREQ_LOW, CHANGE_FIXTURE, REMEASURE, ADD_TEMP_POINT,
)
from .features import extract_features, data_quality_uncertainty_dex  # noqa: F401
from .skill import analyze_spectrum, analyze_series  # noqa: F401
from .shadow import shadow_run, validate_synthetic  # noqa: F401
from .synthetic import (  # noqa: F401
    randles_spectrum, blocking_spectrum, synthetic_suite, make_case,
)
