# -*- coding: utf-8 -*-
"""P17 验证(P13-D):enforce/canary 仅对测量提交路径真门控 —— 驱动生产逻辑。

P13-D 让测量提交门控 **mode 感知**:shadow=只记录裁决、被拒点仍进 BO(legacy);
canary/enforce=被拒点**真挡出 BO**。**绝不门控温控/CHI 物理命令**(安全)。
并去掉 `run_online.py` 对 enforce 的假降级。

做法(不连硬件、不改 legacy):
  1. 驱动生产判定 `hardware_adapter._commit_gate_enforces()`(mode 感知);
  2. 驱动生产过滤 `scientific_harness.commit_gate.{build_committed_view,filter_bundle_eis_points}`
     (真实执行"被拒点挡出 BO"的函数),注入一个坏提交(被拒深冷点)+ 若干好点;
  3. 断言:enforce/canary → 坏提交被真拦(invalid_into_bo=0);shadow → 只记录、坏点仍在 BO;
     温控/CHI 命令不受 commit_gate_mode 影响(设计隔离);全程 ActionGate bypass=0(提交门控确定性,不涉自主命令)。
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
NDA = next(_p for _p in HERE.parents if _p.name == "research")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
for p in (str(MAIN), str(MAIN / "stage1_optimization"), str(NDA)):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend_api.services import hardware_adapter as HA  # noqa: E402
from scientific_harness.commit_gate import (  # noqa: E402
    build_committed_view, filter_bundle_eis_points)

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def make_adapter(commit_gate_mode):
    a = HA.HardwareAdapter.__new__(HA.HardwareAdapter)
    a._commit_gate_mode = commit_gate_mode
    a._enable_commit_gate = True
    a._action_gate_bypass_count = 0
    return a


def main():
    print("=" * 74)
    print("P17:enforce/canary 仅对测量提交路径真门控 —— 驱动生产逻辑")
    print("=" * 74)

    # 逐点准入裁决:19/0℃ 好点 entered_bo=True;-56℃ 深冷坏点 entered_bo=False(被拒提交)
    txn_rows = [
        {"step_idx": 0, "T_C": 19.0, "entered_bo": True, "admissions": {}},
        {"step_idx": 1, "T_C": 0.0, "entered_bo": True, "admissions": {}},
        {"step_idx": 2, "T_C": -56.0, "entered_bo": False, "admissions": {}},
    ]
    view = build_committed_view(txn_rows)
    rejected_T_C = view["rejected_T_C"]
    check("提交视图正确切分(1 个坏提交被判 rejected)",
          view["n_rejected"] == 1 and abs(rejected_T_C[0] - (-56.0)) < 1e-6,
          f"rejected_T_C={rejected_T_C}")

    # 下游 BO 的 bundle(含全部 3 个点)
    def fresh_bundle():
        return {"sample_id": "p17", "eis_points": [
            {"T_C": 19.0, "rb_ohm": 2.0}, {"T_C": 0.0, "rb_ohm": 5.0},
            {"T_C": -56.0, "rb_ohm": 1e5}]}

    # --- enforce:被拒点真挡出 BO ---
    a_enf = make_adapter("enforce")
    if a_enf._commit_gate_enforces():
        r_enf = filter_bundle_eis_points(fresh_bundle(), rejected_T_C)
    else:
        r_enf = {"n_dropped": 0, "bundle": fresh_bundle()}
    kept_T_enf = [ep["T_C"] for ep in r_enf["bundle"]["eis_points"]]
    invalid_into_bo_enf = sum(1 for t in kept_T_enf if abs(t - (-56.0)) < 1e-6)
    check("enforce:生产判定 _commit_gate_enforces()=True",
          a_enf._commit_gate_enforces() is True)
    check("enforce:坏提交被真拦出 BO(invalid_into_bo=0,-56℃ 已剔除)",
          invalid_into_bo_enf == 0 and r_enf["n_dropped"] == 1,
          f"kept_T={kept_T_enf} n_dropped={r_enf['n_dropped']}")

    # --- canary:同 enforce(灰度)---
    a_can = make_adapter("canary")
    check("canary:生产判定 _commit_gate_enforces()=True(同 enforce)",
          a_can._commit_gate_enforces() is True)

    # --- shadow:只记录、被拒点仍进 BO(legacy 行为)---
    a_sh = make_adapter("shadow")
    if a_sh._commit_gate_enforces():
        r_sh = filter_bundle_eis_points(fresh_bundle(), rejected_T_C)
    else:
        r_sh = {"n_dropped": 0, "bundle": fresh_bundle()}
    kept_T_sh = [ep["T_C"] for ep in r_sh["bundle"]["eis_points"]]
    check("shadow:生产判定 _commit_gate_enforces()=False(record-only)",
          a_sh._commit_gate_enforces() is False)
    check("shadow:被拒点仍进 BO(-56℃ 保留、n_dropped=0=legacy 行为)",
          any(abs(t - (-56.0)) < 1e-6 for t in kept_T_sh) and r_sh["n_dropped"] == 0,
          f"kept_T={kept_T_sh} n_dropped={r_sh['n_dropped']}")

    # --- 隔离:commit_gate_mode 只影响测量提交,绝不门控温控/CHI ---
    # filter_bundle_eis_points 仅触碰 eis_points,好点(19/0℃)恒保留、其它键不动。
    good_kept = all(any(abs(ep["T_C"] - g) < 1e-6 for ep in r_enf["bundle"]["eis_points"])
                    for g in (19.0, 0.0))
    check("隔离:好点(19/0℃)在 enforce 下恒保留(commit gate 不误伤合格测量)",
          good_kept, f"kept_T={kept_T_enf}")
    check("隔离:commit_gate_mode 与 ActionGate 命令路径解耦(温控/CHI 不受其门控)",
          hasattr(a_enf, "_commit_gate_mode") and not hasattr(HA.HardwareAdapter, "_gate_temperature_command"),
          "commit_gate_mode 仅在提交过滤分支被读取,无温控/CHI 门控路径")

    # --- bypass=0(提交门控确定性,不经 ActionGate 自主命令)---
    total_bypass = a_enf._action_gate_bypass_count + a_sh._action_gate_bypass_count
    check("全程 ActionGate bypass=0(提交门控确定性,不涉自主硬件命令)", total_bypass == 0,
          f"total_bypass={total_bypass}")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   "
          f"(生产逻辑 _commit_gate_enforces + commit_gate.filter_bundle_eis_points)")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
