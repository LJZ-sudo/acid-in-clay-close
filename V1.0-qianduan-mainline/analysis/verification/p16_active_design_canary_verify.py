# -*- coding: utf-8 -*-
"""P16 验证(P13-C):active_design canary 可选夺权 —— 驱动生产方法本身。

把 active_design 从纯 advisory 升级为 canary:canary 模式下,据 active_design 最新建议
**经 ActionGate 在用户固定阶梯的相邻候选间微调下一 setpoint**,受硬护栏约束
(单步邻域 / 阶梯包络 / 回温≤15K),越界或被拦即回退固定阶梯。advisory 模式行为完全不变。

做法(不连硬件、不改 legacy):`HardwareAdapter.__new__` 绕过 __init__,注入所需属性,
直接调用**生产方法** `_apply_agent_decision`(集成路径)与 `_active_design_canary_nudge`
(硬护栏单元)。断言:
  1. canary + 相邻建议 → 真改选点(next_t 变、canary_applied、ActionGate DISPATCHED);
  2. canary + 非邻域建议 → 回退固定阶梯(EPISTEMIC_CANARY_SKIPPED:not_adjacent);
  3. canary + 越阶梯包络 → 回退(reason: out_of_envelope);
  4. canary + 回温>15K → 回退(reason: reheat>15K);
  5. advisory 模式 + 同一相邻建议 → 行为不变(next_t=固定阶梯、无 canary 事件);
  6. 全程 ActionGate bypass=0(自主动作都经 gate)。
"""
from __future__ import annotations

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
for p in (str(MAIN), str(MAIN / "stage1_optimization"), str(MAIN / "analysis")):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend_api.services import hardware_adapter as HA  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def new_adapter(mode, advisory, *, harness_mode="canary",
                t_start=20.0, t_end=-85.0, step=5.0):
    a = HA.HardwareAdapter.__new__(HA.HardwareAdapter)
    a._active_design_mode = mode
    a._last_epistemic_advisory = advisory
    a._step_size = step
    a._t_start_C = t_start
    a._t_end_C = t_end
    a._harness_mode = harness_mode
    a._action_gate = None
    a._action_gate_decisions = []
    a._action_gate_bypass_count = 0
    a._fine_step = 1.0
    a._events = []
    a._emit_event = lambda etype, payload=None: a._events.append((etype, payload or {}))
    return a


def main():
    print("=" * 74)
    print("P16:active_design canary 可选夺权 —— 驱动生产方法 _apply_agent_decision / _canary_nudge")
    print("=" * 74)

    CONTINUE = {"action": "CONTINUE"}
    total_bypass = 0

    # --- 场景 1:canary + 相邻建议(anchor=0,step=5 → 固定下一点 -5;建议 -10 邻域内)→ 真改选点 ---
    a1 = new_adapter("canary", {"recommended_next_temp_C": -10.0, "value_per_cost": 0.05})
    out1 = a1._apply_agent_decision(CONTINUE, current_t=0.2, step_idx=5, planned_t=0.0)
    ev1 = {t for t, _ in a1._events}
    gate_disp = any(d["command"] == "EPISTEMIC_CANARY_SETPOINT" and d["dispatched"]
                    for d in a1._action_gate_decisions)
    check("canary+相邻建议:真改选点(next_t 由固定 -5 → 建议 -10)",
          abs(out1["next_t"] - (-10.0)) < 1e-6 and out1.get("canary_applied") is True,
          f"next_t={out1['next_t']} fixed={out1.get('fixed_ladder_next_C')} applied={out1.get('canary_applied')}")
    check("canary+相邻建议:经 ActionGate DISPATCHED 且发 EPISTEMIC_CANARY_SETPOINT",
          gate_disp and "EPISTEMIC_CANARY_SETPOINT" in ev1,
          f"gate_dispatched={gate_disp} events={sorted(ev1)}")
    total_bypass += a1._action_gate_bypass_count

    # --- 场景 2:canary + 非邻域建议(-30,距固定 -5 达 25 > step 5)→ 回退固定阶梯 ---
    a2 = new_adapter("canary", {"recommended_next_temp_C": -30.0})
    out2 = a2._apply_agent_decision(CONTINUE, current_t=0.2, step_idx=6, planned_t=0.0)
    skip2 = next((p for t, p in a2._events if t == "EPISTEMIC_CANARY_SKIPPED"), None)
    check("canary+非邻域建议:回退固定阶梯(next_t=-5,未 applied)",
          abs(out2["next_t"] - (-5.0)) < 1e-6 and out2.get("canary_applied") is False,
          f"next_t={out2['next_t']} applied={out2.get('canary_applied')}")
    check("canary+非邻域:EPISTEMIC_CANARY_SKIPPED 理由含 not_adjacent",
          skip2 is not None and any("not_adjacent" in r for r in skip2.get("reasons", [])),
          f"reasons={skip2.get('reasons') if skip2 else None}")
    total_bypass += a2._action_gate_bypass_count

    # --- 场景 3:canary + 越阶梯包络(anchor=-82,step=5 → 固定 -87;建议 -88 邻域内但 < t_end=-85)→ 回退 ---
    a3 = new_adapter("canary", {"recommended_next_temp_C": -88.0}, t_start=20.0, t_end=-85.0, step=5.0)
    out3 = a3._apply_agent_decision(CONTINUE, current_t=-81.8, step_idx=30, planned_t=-82.0)
    skip3 = next((p for t, p in a3._events if t == "EPISTEMIC_CANARY_SKIPPED"), None)
    check("canary+越阶梯包络:回退固定阶梯且理由含 out_of_envelope",
          out3.get("canary_applied") is False and skip3 is not None
          and any("out_of_envelope" in r for r in skip3.get("reasons", [])),
          f"applied={out3.get('canary_applied')} reasons={skip3.get('reasons') if skip3 else None}")
    total_bypass += a3._action_gate_bypass_count

    # --- 场景 4:canary + 回温>15K(直接调硬护栏方法:fixed=0,step=20 邻域宽,建议 +16 → 回温 16>15)→ 拦 ---
    a4 = new_adapter("canary", {"recommended_next_temp_C": 16.0}, t_start=20.0, t_end=-85.0, step=20.0)
    nudge4 = a4._active_design_canary_nudge(fixed_next_t=0.0, anchor_t=0.0, step_idx=1)
    skip4 = next((p for t, p in a4._events if t == "EPISTEMIC_CANARY_SKIPPED"), None)
    check("canary+回温>15K:硬护栏拦下(返回 None)且理由含 reheat>15K",
          nudge4 is None and skip4 is not None
          and any("reheat>15K" in r for r in skip4.get("reasons", [])),
          f"nudge={nudge4} reasons={skip4.get('reasons') if skip4 else None}")
    total_bypass += a4._action_gate_bypass_count

    # --- 场景 5:advisory 模式 + 同一相邻建议 → 行为完全不变(固定阶梯、无 canary 事件)---
    a5 = new_adapter("advisory", {"recommended_next_temp_C": -10.0})
    out5 = a5._apply_agent_decision(CONTINUE, current_t=0.2, step_idx=5, planned_t=0.0)
    ev5 = {t for t, _ in a5._events}
    check("advisory 模式:行为不变(next_t=固定 -5、canary_applied=False、无 canary 事件)",
          abs(out5["next_t"] - (-5.0)) < 1e-6 and out5.get("canary_applied") is False
          and "EPISTEMIC_CANARY_SETPOINT" not in ev5,
          f"next_t={out5['next_t']} applied={out5.get('canary_applied')} events={sorted(ev5)}")
    total_bypass += a5._action_gate_bypass_count

    # --- 场景 6:全程 bypass=0 ---
    check("全程 ActionGate bypass=0(自主动作都经 gate)", total_bypass == 0,
          f"total_bypass={total_bypass}")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   "
          f"(生产方法 _apply_agent_decision / _active_design_canary_nudge 干跑)")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
