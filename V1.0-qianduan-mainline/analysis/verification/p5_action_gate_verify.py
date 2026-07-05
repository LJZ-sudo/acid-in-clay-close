# -*- coding: utf-8 -*-
"""P5 验证:enforce 关 bypass —— live 逐点自主 Agent 决策改走 ActionGate(唯一受控入口)。

直接驱动**生产同一对象** HardwareAdapter._gate_agent_decision,以规范自主动作集
(CONTINUE / FINE_GRAINED_SCAN / ABORT)在 shadow vs enforce 下核验:
  - shadow:所有自主动作照常下发(行为与 legacy 一致),不降级;
  - enforce:FINE_GRAINED_SCAN(→TRIGGER_FINE_SCAN ∈ allowlist)放行;
            ABORT(→AGENT_ABORT ∉ allowlist)被 BLOCKED → 降级为安全默认 CONTINUE;
  - 两模式下每个自主覆盖动作都过 gate ⇒ bypass_count == 0(audit bypass 归零);
  - 人工 override(source=operator)→ OVERRIDE_DISPATCHED,与自主隔离。
"""
import sys
from pathlib import Path

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN))
sys.path.insert(0, str(MAIN / "stage1_optimization"))

from backend_api.services.hardware_adapter import HardwareAdapter  # noqa: E402
from scientific_harness.action_gate import ActionGate, ActionProposal, OVERRIDE_DISPATCHED  # noqa: E402

ACTIONS = [
    {"action": "CONTINUE"},
    {"action": "FINE_GRAINED_SCAN", "reasoning": "phase transition suspected"},
    {"action": "ABORT", "reasoning": "agent wants to stop"},
]


def run_mode(mode):
    ad = HardwareAdapter()
    ad._harness_mode = mode
    ad._action_gate = None
    ad._action_gate_bypass_count = 0
    ad._action_gate_decisions = []
    out = {}
    for d in ACTIONS:
        res = ad._gate_agent_decision(dict(d), step_idx=1)
        out[d["action"]] = (res or {}).get("action")
    return out, ad._action_gate_bypass_count, ad._action_gate_decisions


def main():
    print("== P5 ActionGate verify (live autonomous decisions → gate) ==")
    sh_out, sh_bypass, sh_dec = run_mode("shadow")
    en_out, en_bypass, en_dec = run_mode("enforce")
    print(f"shadow : results={sh_out} bypass={sh_bypass} gated={len(sh_dec)}")
    print(f"enforce: results={en_out} bypass={en_bypass} gated={len(en_dec)}")

    # 人工 override 隔离
    gate = ActionGate(lambda *a, **k: True, mode="enforce")
    ov = gate.submit(ActionProposal(command="AGENT_ABORT", source="operator", operator="LBM"))
    print(f"operator override decision: {ov.decision} dispatched={ov.dispatched}")

    checks = {
        # shadow:行为不变,均不降级
        "shadow_fine_kept": sh_out["FINE_GRAINED_SCAN"] == "FINE_GRAINED_SCAN",
        "shadow_abort_kept": sh_out["ABORT"] == "ABORT",
        "shadow_continue_kept": sh_out["CONTINUE"] == "CONTINUE",
        "shadow_bypass_zero": sh_bypass == 0,
        # enforce:allowlist 内放行,allowlist 外 ABORT 降级 CONTINUE
        "enforce_fine_allowed": en_out["FINE_GRAINED_SCAN"] == "FINE_GRAINED_SCAN",
        "enforce_abort_blocked_downgraded": en_out["ABORT"] == "CONTINUE",
        "enforce_continue_kept": en_out["CONTINUE"] == "CONTINUE",
        "enforce_bypass_zero": en_bypass == 0,
        # 仅自主覆盖动作过 gate(CONTINUE 不计):每模式 2 条(FINE+ABORT)
        "shadow_gated_two": len(sh_dec) == 2,
        "enforce_gated_two": len(en_dec) == 2,
        "enforce_one_blocked": sum(1 for d in en_dec if not d["dispatched"]) == 1,
        # 人工 override 隔离
        "operator_override_dispatched": ov.decision == OVERRIDE_DISPATCHED and ov.dispatched,
    }
    print("-- checks --")
    all_ok = True
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        all_ok = all_ok and v
    print(f"== {'ALL PASS' if all_ok else 'FAILED'} ==")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
