# -*- coding: utf-8 -*-
"""C³-Harness 收敛场景 benchmark（ESAS-OS 2.0 / §10.5 验收）。

注入"已收敛但仍探索 / 真收敛 / 未收敛"三类场景,带 oracle `truly_done`,
对比 legacy(任一象限触发即停)与 C³ shadow 的"错误提前停止"次数。
验收:**C³ 错误提前停止 ≤ legacy 且严格更少一次**(对应 §10.6 C³ 行)。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .harness import shadow_convergence


def _scenarios() -> List[Dict[str, Any]]:
    return [
        {   # A 收敛阈值触发,但 Rb-ACT 计量不确定度高 + 只测了 1 片 → 其实没完成
            "name": "converged_but_unreliable",
            "truly_done": False,
            "termination": {"verdict": "loop_can_end", "triggered_by": ["convergence"],
                            "convergence": {"triggered": True}, "anomaly": {"triggered": False},
                            "budget": {"triggered": False}, "progress": {}},
            "evidence": {"metrological_uncertainty_dex": 0.28, "repro_replicates_have": 1,
                         "repro_replicates_required": 3, "claim_stability": 0.7,
                         "rb_act_active_requests": ["EXTEND_FREQ_HIGH"]},
        },
        {   # B 收敛 + 测量可靠 + 3 片 + 主张稳 → 真收敛
            "name": "genuinely_converged",
            "truly_done": True,
            "termination": {"verdict": "loop_can_end", "triggered_by": ["convergence", "performance_target"],
                            "convergence": {"triggered": True}, "anomaly": {"triggered": False},
                            "budget": {"triggered": False}, "progress": {}},
            "evidence": {"metrological_uncertainty_dex": 0.04, "repro_replicates_have": 3,
                         "repro_replicates_required": 3, "claim_stability": 1.0},
        },
        {   # C 未触发 + 性能差距大 + std 高 → 该继续探索
            "name": "not_converged_explore",
            "truly_done": False,
            "termination": {"verdict": "continue", "triggered_by": [],
                            "convergence": {"triggered": False, "rules": [
                                {"id": "predicted_std", "value": {"max_std": 0.09}}]},
                            "anomaly": {"triggered": False}, "budget": {"triggered": False},
                            "progress": {"performance_gap_to_threshold": {"combined_score": 0.6}}},
            "evidence": {"metrological_uncertainty_dex": 0.05, "repro_replicates_have": 2,
                         "repro_replicates_required": 3, "claim_stability": 0.95,
                         "score_min": 1.0},
        },
        {   # D 预算耗尽 → 必须停(C³ 不得推迟硬预算门)
            "name": "budget_exhausted",
            "truly_done": True,
            "termination": {"verdict": "loop_must_end_budget", "triggered_by": ["budget"],
                            "convergence": {"triggered": False}, "anomaly": {"triggered": False},
                            "budget": {"triggered": True, "status": "exhausted"}, "progress": {}},
            "evidence": {"metrological_uncertainty_dex": 0.2, "repro_replicates_have": 1,
                         "repro_replicates_required": 3, "claim_stability": 0.8},
        },
    ]


def run() -> Dict[str, Any]:
    legacy_wrong_stops = 0
    c3_wrong_stops = 0
    rows: List[Dict[str, Any]] = []
    consistent_all = True
    for sc in _scenarios():
        cert = shadow_convergence(sc["termination"], **sc["evidence"])
        legacy_stop = cert.legacy_stop
        c3_stop = cert.c3_stop
        truly_done = sc["truly_done"]
        legacy_wrong = legacy_stop and not truly_done
        c3_wrong = c3_stop and not truly_done
        legacy_wrong_stops += int(legacy_wrong)
        c3_wrong_stops += int(c3_wrong)
        consistent_all = consistent_all and cert.consistent_with_legacy
        rows.append({"name": sc["name"], "truly_done": truly_done,
                     "legacy_stop": legacy_stop, "c3_stop": c3_stop,
                     "recommended": cert.recommended_action, "delta": cert.delta_vs_legacy,
                     "legacy_wrong": legacy_wrong, "c3_wrong": c3_wrong,
                     "top3": cert.top_actions(3)})
    ok = (c3_wrong_stops < legacy_wrong_stops) and consistent_all
    return {"ok": ok, "legacy_wrong_stops": legacy_wrong_stops,
            "c3_wrong_stops": c3_wrong_stops, "consistent_all": consistent_all,
            "scenarios": rows}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=2))
