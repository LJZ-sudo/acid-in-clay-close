"""材料评分：对 RankedCandidate 进行加权综合评分（可用于后处理验证）。"""
from __future__ import annotations

from s8_stage3.contracts.ranking import RankedCandidate


def compute_weighted_score(candidate: RankedCandidate) -> float:
    """重新计算加权分（用于验证 S10 LLM 输出是否合理）。"""
    total_weight = sum(c.weight for c in candidate.criteria_scores)
    if total_weight == 0:
        return 0.0
    weighted_sum = sum(c.score * c.weight for c in candidate.criteria_scores)
    return round(weighted_sum / total_weight, 4)


def validate_ranking_consistency(candidates: list[RankedCandidate]) -> list[str]:
    """检查排名顺序与得分是否一致，返回警告列表。"""
    warnings = []
    for i in range(1, len(candidates)):
        prev = candidates[i - 1]
        curr = candidates[i]
        if curr.total_score > prev.total_score + 0.02:
            warnings.append(
                f"Ranking inconsistency: rank {curr.rank} (score={curr.total_score}) "
                f"> rank {prev.rank} (score={prev.total_score})"
            )
    return warnings
