# -*- coding: utf-8 -*-
"""M2-4 / G4 测试:LLM 安全修正 vs 确定性基线(真实 SafetyValidator + 冻结 recipe)。"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
if str(MAINLINE) not in sys.path:
    sys.path.insert(0, str(MAINLINE))

from analysis.evaluation import policy_ablation as PA  # noqa: E402


def _by_policy(results, name):
    return next(r for r in results if r["policy"] == name)


def test_raw_low_r_passes_hard_safety_box():
    """关键事实:R=0.0285 在硬边界内 → 安全箱通过(说明硬约束抓不到低 R)。"""
    s = PA.run()
    raw = _by_policy(s["results"], "RAW_MOBO")
    assert raw["recipe"]["R"] == 0.0285
    assert raw["safety_passed"] is True
    assert raw["R_below_observed_floor"] is True


def test_hard_constraint_does_not_fix_low_r():
    s = PA.run()
    hard = _by_policy(s["results"], "HARD_CONSTRAINED_MOBO")
    # 0.0285 已在 [0,1.04] 内 → 裁剪不改 → 仍在观测下限以下
    assert hard["recipe"]["R"] == 0.0285
    assert hard["R_below_observed_floor"] is True
    assert hard["in_observed_R_region"] is False


def test_deterministic_rule_repairs_direction_like_llm():
    s = PA.run()
    proj = _by_policy(s["results"], "DETERMINISTIC_PROJECTION")
    rule = _by_policy(s["results"], "RULE_BASED_RISK_REPAIR")
    llm = _by_policy(s["results"], "LLM_TOPK_SELECTION")
    # 确定性投影/规则把 R 拉回观测域,方向与 LLM 一致
    assert proj["in_observed_R_region"] is True
    assert rule["in_observed_R_region"] is True
    assert llm["in_observed_R_region"] is True


def test_verdict_flags_llm_replaceable():
    s = PA.run()
    kf = s["key_findings"]
    assert kf["hard_constraint_misses_low_R"] is True
    assert kf["deterministic_rule_repairs_direction"] is True
    # 诚实结论:不声称 LLM 独特安全
    assert "可被确定性规则替代" in s["verdict"]
