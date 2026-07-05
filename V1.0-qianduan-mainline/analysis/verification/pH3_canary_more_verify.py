# -*- coding: utf-8 -*-
"""pH3 验证(H3):canary 让 active_design 真正**多驱动几点** —— 驱动生产方法。

原实现 canary 只在固定阶梯点 ±1 step 邻域微调 → fe4b 仅成 2 次。H3 把可执行邻域放宽到
±`canary_max_steps`(默认 2)step,让更多步产生实质微调;**仍守阶梯包络 + 回温≤15K +
ActionGate**。advisory 行为完全不变。

驱动生产方法 `_active_design_canary_nudge` / `_apply_agent_decision`(__new__ 注入,不连硬件):
  1. ±2 step 建议(默认 max_steps=2)→ 真改选点 DISPATCHED(原 ±1 会被拒);
  2. 同一 ±2 建议但 max_steps=1 → not_adjacent 被拒(证明"放宽邻域"就是多驱动的杠杆);
  3. ±3 step 建议(超 max_steps=2)→ 仍 not_adjacent 被拒(护栏未失守);
  4. 越阶梯包络 → 仍回退(out_of_envelope);
  5. 回温>15K → 仍拦(reheat>15K);
  6. advisory 模式 → 行为不变;
  7. 全程 ActionGate bypass=0。
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


def new_adapter(mode, advisory, *, max_steps=2, harness_mode="canary",
                t_start=20.0, t_end=-85.0, step=5.0):
    a = HA.HardwareAdapter.__new__(HA.HardwareAdapter)
    a._active_design_mode = mode
    a._canary_max_steps = max_steps
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
    print("pH3:canary 多驱动(±2 step 邻域)—— 驱动生产方法 _active_design_canary_nudge")
    print("=" * 74)
    CONTINUE = {"action": "CONTINUE"}
    total_bypass = 0

    # 1. ±2 step 建议(anchor=0,step=5 → 固定下一点 -5;建议 -15,距 10=2*step)→ DISPATCHED
    a1 = new_adapter("canary", {"recommended_next_temp_C": -15.0, "value_per_cost": 0.05}, max_steps=2)
    out1 = a1._apply_agent_decision(CONTINUE, current_t=0.2, step_idx=5, planned_t=0.0)
    disp1 = any(d["command"] == "EPISTEMIC_CANARY_SETPOINT" and d["dispatched"]
                for d in a1._action_gate_decisions)
    check("1 ±2 step 建议(max_steps=2):真改选点 DISPATCHED(-5 → -15)",
          abs(out1["next_t"] - (-15.0)) < 1e-6 and out1.get("canary_applied") is True and disp1,
          f"next_t={out1['next_t']} applied={out1.get('canary_applied')} dispatched={disp1}")
    total_bypass += a1._action_gate_bypass_count

    # 2. 同一 ±2 建议但 max_steps=1 → not_adjacent 被拒(证明放宽邻域是杠杆)
    a2 = new_adapter("canary", {"recommended_next_temp_C": -15.0}, max_steps=1)
    out2 = a2._apply_agent_decision(CONTINUE, current_t=0.2, step_idx=6, planned_t=0.0)
    skip2 = next((p for t, p in a2._events if t == "EPISTEMIC_CANARY_SKIPPED"), None)
    check("2 同建议 max_steps=1 → not_adjacent 被拒(邻域宽度就是多驱动杠杆)",
          out2.get("canary_applied") is False and skip2 is not None
          and any("not_adjacent" in r for r in skip2.get("reasons", [])),
          f"applied={out2.get('canary_applied')} reasons={skip2.get('reasons') if skip2 else None}")
    total_bypass += a2._action_gate_bypass_count

    # 3. ±3 step 建议(-20,距 15 > 2*5=10)→ 仍 not_adjacent 被拒(护栏未失守)
    a3 = new_adapter("canary", {"recommended_next_temp_C": -20.0}, max_steps=2)
    out3 = a3._apply_agent_decision(CONTINUE, current_t=0.2, step_idx=7, planned_t=0.0)
    skip3 = next((p for t, p in a3._events if t == "EPISTEMIC_CANARY_SKIPPED"), None)
    check("3 ±3 step 建议超邻域 → 仍 not_adjacent 被拒",
          out3.get("canary_applied") is False and skip3 is not None
          and any("not_adjacent" in r for r in skip3.get("reasons", [])),
          f"applied={out3.get('canary_applied')} reasons={skip3.get('reasons') if skip3 else None}")
    total_bypass += a3._action_gate_bypass_count

    # 4. 越阶梯包络(anchor=-82,step=5 → 固定 -87;建议 -86 在 ±2 邻域内但 < t_end=-85)→ 回退
    a4 = new_adapter("canary", {"recommended_next_temp_C": -86.0}, max_steps=2,
                     t_start=20.0, t_end=-85.0, step=5.0)
    out4 = a4._apply_agent_decision(CONTINUE, current_t=-81.8, step_idx=30, planned_t=-82.0)
    skip4 = next((p for t, p in a4._events if t == "EPISTEMIC_CANARY_SKIPPED"), None)
    check("4 越阶梯包络 → 回退(out_of_envelope)",
          out4.get("canary_applied") is False and skip4 is not None
          and any("out_of_envelope" in r for r in skip4.get("reasons", [])),
          f"applied={out4.get('canary_applied')} reasons={skip4.get('reasons') if skip4 else None}")
    total_bypass += a4._action_gate_bypass_count

    # 5. 回温>15K(fixed=0,step=8,max_steps=2 邻域 16;建议 +16 → 回温 16>15)→ 拦
    a5 = new_adapter("canary", {"recommended_next_temp_C": 16.0}, max_steps=2,
                     t_start=20.0, t_end=-85.0, step=8.0)
    nudge5 = a5._active_design_canary_nudge(fixed_next_t=0.0, anchor_t=0.0, step_idx=1)
    skip5 = next((p for t, p in a5._events if t == "EPISTEMIC_CANARY_SKIPPED"), None)
    check("5 回温>15K → 硬护栏拦下(返回 None,reheat>15K)",
          nudge5 is None and skip5 is not None
          and any("reheat>15K" in r for r in skip5.get("reasons", [])),
          f"nudge={nudge5} reasons={skip5.get('reasons') if skip5 else None}")
    total_bypass += a5._action_gate_bypass_count

    # 6. advisory 模式 + 同 ±2 建议 → 行为不变
    a6 = new_adapter("advisory", {"recommended_next_temp_C": -15.0}, max_steps=2)
    out6 = a6._apply_agent_decision(CONTINUE, current_t=0.2, step_idx=5, planned_t=0.0)
    ev6 = {t for t, _ in a6._events}
    check("6 advisory 模式:行为不变(next_t=固定 -5、无 canary 事件)",
          abs(out6["next_t"] - (-5.0)) < 1e-6 and out6.get("canary_applied") is False
          and "EPISTEMIC_CANARY_SETPOINT" not in ev6,
          f"next_t={out6['next_t']} applied={out6.get('canary_applied')}")
    total_bypass += a6._action_gate_bypass_count

    # 7. bypass=0
    check("7 全程 ActionGate bypass=0", total_bypass == 0, f"total_bypass={total_bypass}")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   (生产方法 _active_design_canary_nudge 干跑)")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
