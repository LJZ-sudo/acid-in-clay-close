"""敏感性分析：评估排名对评分权重变化的稳健性。"""
from __future__ import annotations

from s8_stage3.contracts.ranking import RankedCandidate, RankingCriterion


def rank_sensitivity_summary(candidates: list[RankedCandidate]) -> dict:
    """
    简单敏感性摘要：
    - 统计 Top-1 与 Top-2 的得分差
    - 若差距 < 0.05，标注为"不稳健排名"
    """
    if len(candidates) < 2:
        return {"status": "insufficient_candidates"}

    top1 = candidates[0]
    top2 = candidates[1]
    score_gap = round(top1.total_score - top2.total_score, 4)
    robust = score_gap >= 0.05

    return {
        "top1": top1.instance_name,
        "top1_score": top1.total_score,
        "top2": top2.instance_name,
        "top2_score": top2.total_score,
        "score_gap": score_gap,
        "ranking_robust": robust,
        "warning": None if robust else (
            f"Top-1 vs Top-2 gap is only {score_gap:.3f}; "
            "ranking may change with small weight perturbations."
        ),
    }
