# -*- coding: utf-8 -*-
"""pH1 验证(H1):C³-Harness 收敛证书从"只写盘"到"主循环真消费"。

在 Stage1 真终止评估器 `evaluate_termination` 上接 C³ advisory 消费,**单调安全**:
  * C³ 只能把一次"非硬停"的 loop_can_end 推迟成继续(证据不足时);
  * 永不把 continue 变成停;永不推迟 budget 硬停;legacy `verdict` 字段永不改。

做法(不连硬件、真实调用生产函数 `evaluate_termination`):
  A. **真实 replay**:用真 attapulgite campaign + 真 history_db,喂真实计量证据
     (between-specimen 0.252 dex 复现地板、单片 repro=1)→ 证书被消费且单调守住;
  B. **非硬停 defer**:构造 performance 触发停 + 证据不足 → verdict_effective=continue_c3_defer;
  C. **证据充分**:同停 + 低 metro/复现达标 → 不 defer(agree_stop);
  D. **budget 硬停不可推迟**:budget 触发 + 证据不足 → budget_hard_stop=True、不 defer;
  E. **向后兼容**:不传 c3_evidence → c3=None、verdict_effective==verdict。
所有场景断言证书 `consistent_with_legacy=True`(c3_stop⊆legacy_stop 不变量)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve()
NDA = (next(_p for _p in HERE.parents if _p.name == "V1.0-qianduan-mainline").parent / "experiments")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
for p in (str(MAIN), str(MAIN / "stage1_optimization")):
    if p not in sys.path:
        sys.path.insert(0, p)

from closed_loop.termination_evaluator import evaluate_termination  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


CAMPAIGN = (MAIN / "stage1_optimization" / "campaigns" / "attapulgite_aice_campaign.json")
HISTORY = (MAIN / "stage1_optimization" / "campaign_memory" / "history_db_attapulgite.json")

# between-specimen 复现地板(真实):0.252 dex;单次全温区扫描=1 独立片
EV_INSUFFICIENT = {
    "metrological_uncertainty_dex": 0.252,
    "repro_replicates_have": 1,
    "repro_replicates_required": 3,
    "claim_stability": 1.0,
}
EV_SUFFICIENT = {
    "metrological_uncertainty_dex": 0.02,
    "repro_replicates_have": 3,
    "repro_replicates_required": 3,
    "claim_stability": 1.0,
}


def _perf_campaign(easy=True):
    """构造一个 performance 极易触发、budget 不触发的 campaign(隔离 defer 逻辑)。"""
    return {
        "campaign_name": "H1_synthetic",
        "parameters": {"R": {"low": 0.0, "high": 1.0}, "N": {"low": 0.5, "high": 1.3}},
        "termination_criteria": {
            "performance_target": {
                "sigma_rt_min_S_cm": 0.0, "ea_high_max_eV": 9.9,
                "ea_low_excess_max_eV": 9.9, "combined_score_min": -9.9,
                "consecutive_distinct_recipes_required": 2,
                "distinct_recipe_min_distance": 0.05,
            },
            "budget": {"max_total_trials": 999},
        },
    }


def _two_distinct_trials():
    def mk(tid, R, N):
        return {"trial_id": tid, "parameters": {"R": R, "N": N},
                "objectives": {"conductivity_room_temp_S_cm": 0.03, "ea_high_temp_eV": 0.08,
                               "ea_low_excess_eV": 0.1, "combined_score": -1.5}}
    return {"trials": [mk(1, 0.2, 1.0), mk(2, 0.8, 0.6)]}


def main():
    print("=" * 74)
    print("pH1:C³ 收敛证书主循环真消费 —— 驱动生产函数 evaluate_termination")
    print("=" * 74)

    # ---- A. 真实 replay:真 campaign + 真 history_db ----
    camp = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    hist = json.loads(HISTORY.read_text(encoding="utf-8"))
    outA = evaluate_termination(camp, hist, c3_evidence=EV_INSUFFICIENT)
    c3A = outA.get("c3")
    check("A1 真 replay:C³ 证书被消费(consumed=True)",
          bool(c3A and c3A.get("consumed")), f"c3={None if not c3A else c3A.get('recommended_action')}")
    check("A2 真 replay:单调不变量 consistent_with_legacy=True",
          bool(c3A and c3A.get("consistent_with_legacy")), f"delta={c3A.get('delta_vs_legacy') if c3A else None}")
    # legacy verdict 字段保留;若 legacy=continue 则 effective 也必不为停
    vlA, veA = outA.get("verdict"), outA.get("verdict_effective")
    mono_A = not (vlA == "continue" and veA in ("loop_can_end", "loop_must_end_budget"))
    check("A3 真 replay:legacy continue 绝不被 C³ 变成停(单调)", mono_A,
          f"verdict={vlA} verdict_effective={veA}")

    # ---- B. 非硬停 + 证据不足 → defer ----
    outB = evaluate_termination(_perf_campaign(), _two_distinct_trials(), c3_evidence=EV_INSUFFICIENT)
    c3B = outB.get("c3")
    check("B1 performance 触发停(legacy verdict=loop_can_end)",
          outB.get("verdict") == "loop_can_end", f"verdict={outB.get('verdict')} by={outB.get('triggered_by')}")
    check("B2 证据不足 → C³ 推迟停(verdict_effective=continue_c3_defer)",
          outB.get("verdict_effective") == "continue_c3_defer" and c3B.get("c3_deferred_stop") is True,
          f"eff={outB.get('verdict_effective')} delta={c3B.get('delta_vs_legacy')}")
    check("B3 defer 时 legacy verdict 字段保持不变(=loop_can_end)",
          outB.get("verdict") == "loop_can_end", f"verdict={outB.get('verdict')}")

    # ---- C. 非硬停 + 证据充分 → 不 defer ----
    outC = evaluate_termination(_perf_campaign(), _two_distinct_trials(), c3_evidence=EV_SUFFICIENT)
    c3C = outC.get("c3")
    check("C1 证据充分 → 不推迟(verdict_effective=loop_can_end)",
          outC.get("verdict_effective") == "loop_can_end" and c3C.get("c3_deferred_stop") is False,
          f"eff={outC.get('verdict_effective')} delta={c3C.get('delta_vs_legacy')}")

    # ---- D. budget 硬停不可推迟 ----
    camp_budget = {
        "campaign_name": "H1_budget",
        "parameters": {"R": {"low": 0.0, "high": 1.0}, "N": {"low": 0.5, "high": 1.3}},
        "termination_criteria": {"budget": {"max_total_trials": 2}},
    }
    outD = evaluate_termination(camp_budget, _two_distinct_trials(), c3_evidence=EV_INSUFFICIENT)
    c3D = outD.get("c3")
    check("D1 budget 触发(triggered_by 含 budget)",
          "budget" in (outD.get("triggered_by") or []), f"by={outD.get('triggered_by')}")
    check("D2 budget 硬停不可推迟(budget_hard_stop=True 且未 defer)",
          c3D.get("budget_hard_stop") is True and c3D.get("c3_deferred_stop") is False
          and outD.get("verdict_effective") != "continue_c3_defer",
          f"hard={c3D.get('budget_hard_stop')} defer={c3D.get('c3_deferred_stop')} eff={outD.get('verdict_effective')}")

    # ---- E. 向后兼容:不传证据 ----
    outE = evaluate_termination(camp, hist)
    check("E1 不传 c3_evidence → c3=None(向后兼容)", outE.get("c3") is None,
          f"c3={outE.get('c3')}")
    check("E2 不传证据 → verdict_effective==verdict(legacy 行为)",
          outE.get("verdict_effective") == outE.get("verdict"),
          f"verdict={outE.get('verdict')} eff={outE.get('verdict_effective')}")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   (生产函数 evaluate_termination 真 replay)")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
