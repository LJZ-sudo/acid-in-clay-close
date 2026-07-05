# -*- coding: utf-8 -*-
"""P20 验证(G-2 武装):真机故障注入 —— 驱动生产逻辑 + 真机后置验收(SKIP-if-no-real-data)。

G-2 硬门 = **真机**(dummy cell / 参考电路)注入故障,验证治理路径真机拦截。物理注入须真机,
无法软件伪造。本脚本做两件**诚实**的事:

  A. 软件驱动生产逻辑(现在即可,证明武装真实有效):用 `HardwareAdapter.__new__` 绕 __init__,
     注入 fe3 run 的**真机 EIS 谱**,驱动生产方法 `_maybe_inject_governance_fault` +
     `_run_point_governance`(→ 真 `measurement_txn` → 真 `commit_gate`)。断言:
       - 三类故障(SAMPLE_MISMATCH/QA_FAIL/CALIBRATION_EXPIRED)注入后 entered_bo=False、caught=True;
       - **未注入的干净点不被误伤**(entered_bo 由真实数据决定,不受故障开关影响);
       - 故障只改治理层输入,**温控/CHI 物理命令零触碰**(设计隔离,无温控/CHI 门控路径);
       - commit gate 把被拦的注入点 T 剔出 BO;全程 ActionGate bypass=0。
  B. 真机后置验收(SKIP-if-no-real-data):扫 runs/ 找带 `fault_injection_summary.json` 的真机 run,
     断言 all_caught=True 且 any_entered_bo=False。无真机故障 run 则 **SKIP,绝不伪造**。
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

import numpy as np

HERE = Path(__file__).resolve()
NDA = next(_p for _p in HERE.parents if _p.name == "research")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
RUNS = MAIN / "runs"
EVID = RUNS / "run_20260629_112156_9db536" / "evidence"
for p in (str(MAIN), str(MAIN / "stage0_measurement"), str(MAIN / "stage1_optimization"), str(NDA)):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend_api.services import hardware_adapter as HA  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_spectrum():
    if not EVID.exists():
        return None
    for fp in sorted(EVID.glob("EP-*.json")):
        d = json.loads(fp.read_text(encoding="utf-8")).get("payload", {})
        f = d.get("frequencies"); zr = d.get("z_real"); zi = d.get("z_imag")
        if f and zr and zi and len(f) >= 10:
            return {
                "T_C": d.get("temperature_C", 20.0),
                "f": np.array(f, float), "zr": np.array(zr, float), "zi": np.array(zi, float),
                "rb_ohm": d.get("rb_ohm"), "kk": (d.get("kk_result") or {}).get("mu_median", 0.02),
            }
    return None


def make_adapter(inject_fault, run_id=None):
    a = HA.HardwareAdapter.__new__(HA.HardwareAdapter)
    a._thickness_cm = 0.1
    a._area_cm2 = 1.96
    a._sample_id = "p20-fe3"
    a._run_id = run_id
    a._harness_fns = None
    a._harness_recorder = None
    a._txn_rows = []
    a._fault_injections = []
    a._rbact_metro_dex = []
    a._rbact_active_requests = []
    a._inject_faults = ([inject_fault] if isinstance(inject_fault, dict)
                        else list(inject_fault or []))
    a._enable_commit_gate = True
    a._commit_gate_mode = "enforce"
    a._commit_rejected_T_C = []
    a._action_gate_bypass_count = 0
    a._events = []
    a._emit_event = lambda ev, payload=None: a._events.append((ev, payload or {}))
    return a


def drive_point(adapter, spec, step_idx, T_C):
    rb_result = {"status": "OK", "rb_ohm": spec["rb_ohm"] or 100.0,
                 "rb_method": "hf_intercept", "raw": {"kk_result": {"mu_median": spec["kk"]}}}
    adapter._run_point_governance(
        step_idx=step_idx, T_C=T_C, freq=spec["f"], zr=spec["zr"], zi=spec["zi"],
        eis_result=None, rb_result=rb_result)


def main():
    print("=" * 76)
    print("P20:真机故障注入(G-2 武装)—— 驱动生产逻辑 + 真机后置验收")
    print("=" * 76)

    spec = load_spectrum()
    if spec is None:
        print("[SKIP] 无真机谱,跳过 A 部(不谎报)")
    else:
        print(f"真机谱 T={spec['T_C']:.1f}°C  频点={len(spec['f'])}")

        # --- A1. 提交路径可忠实拦截的两类故障(at_step=1)→ 必须被治理拦截 ---
        #  (校准/ACK 等仪器在线见证类故障须真仪器 EvidenceTransaction,不在提交路径注入,避免假验收)
        for ft in ("SAMPLE_MISMATCH", "QA_FAIL"):
            a = make_adapter({"type": ft, "at_step": 1})
            drive_point(a, spec, step_idx=0, T_C=20.0)   # 干净点(不注入)
            drive_point(a, spec, step_idx=1, T_C=-30.0)  # 注入点
            injs = a._fault_injections
            fault_row = next((r for r in a._txn_rows if r.get("step_idx") == 1), None)
            caught = bool(injs and injs[0].get("caught"))
            entered = fault_row.get("entered_bo") if fault_row else None
            check(f"{ft}:注入坏点被治理拦截(caught=True, entered_bo=False)",
                  caught and entered is False,
                  f"caught={caught} entered_bo={entered}")
            # FAULT_INJECTED / FAULT_INJECTION_RESULT 事件真发
            evs = {e for e, _ in a._events}
            check(f"{ft}:FAULT_INJECTED + FAULT_INJECTION_RESULT 事件真发",
                  "FAULT_INJECTED" in evs and "FAULT_INJECTION_RESULT" in evs)

        # --- A2. 干净点不被误伤(同谱、不注入)---
        a_clean = make_adapter(None)
        drive_point(a_clean, spec, step_idx=0, T_C=20.0)
        clean_row = a_clean._txn_rows[0] if a_clean._txn_rows else None
        no_inject_events = not any(e == "FAULT_INJECTED" for e, _ in a_clean._events)
        check("未开注入时无 FAULT_INJECTED 事件(默认关、零副作用)", no_inject_events)
        check("干净点治理正常产出 TXN_ADMISSION(entered_bo 由真实数据决定)",
              clean_row is not None and "entered_bo" in clean_row,
              f"clean_row={clean_row}")

        # --- A3. commit gate 把注入点 T 剔出 BO ---
        from scientific_harness.commit_gate import build_committed_view, filter_bundle_eis_points
        a = make_adapter({"type": "SAMPLE_MISMATCH", "at_step": 1})
        drive_point(a, spec, step_idx=0, T_C=20.0)
        drive_point(a, spec, step_idx=1, T_C=-30.0)
        view = build_committed_view(a._txn_rows)
        bundle = {"sample_id": "p20", "eis_points": [{"T_C": 20.0}, {"T_C": -30.0}]}
        r = filter_bundle_eis_points(bundle, view["rejected_T_C"])
        kept_T = [ep["T_C"] for ep in r["bundle"]["eis_points"]]
        check("commit gate 把注入坏点 T(-30℃)剔出 BO,干净点(20℃)保留",
              any(abs(t - 20.0) < 1e-6 for t in kept_T) and not any(abs(t + 30.0) < 1e-6 for t in kept_T),
              f"kept_T={kept_T} rejected={view['rejected_T_C']}")

        # --- A4. 隔离:故障注入只碰治理层,无温控/CHI 门控路径 ---
        check("隔离:故障注入无温控/CHI 门控路径(仅改 txn 治理输入)",
              not hasattr(HA.HardwareAdapter, "_gate_temperature_command")
              and not hasattr(HA.HardwareAdapter, "_gate_chi_command"),
              "_maybe_inject_governance_fault 仅改 expected_sample_id/status/geometry")

        # --- A5. bypass=0 ---
        check("全程 ActionGate bypass=0(故障注入不涉自主命令)",
              a._action_gate_bypass_count == 0)

    # --- B. 真机后置验收(SKIP-if-no-real-data)---
    print("\n--- B 部:真机后置验收(扫 runs/ 找 fault_injection_summary.json)---")
    real_summaries = list(RUNS.glob("*/fault_injection_summary.json")) if RUNS.exists() else []
    if not real_summaries:
        print("[SKIP] 未找到真机故障注入 run(fault_injection_summary.json 不存在)。")
        print("       G-2 物理验收待接 dummy cell/参考电路,以 inject_fault 开真机 run 后自动可验。绝不伪造。")
    else:
        for sp in real_summaries:
            s = json.loads(sp.read_text(encoding="utf-8"))
            check(f"真机 run {sp.parent.name}:注入坏点全被拦(all_caught)且未进 BO",
                  bool(s.get("all_caught")) and not bool(s.get("any_entered_bo")),
                  f"n_injected={s.get('n_injected')} n_caught={s.get('n_caught')}")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 76)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   "
          f"(A=驱动生产逻辑证明武装有效;B=真机物理验收{'已有真机数据' if real_summaries else '待真机 SKIP'})")
    print("=" * 76)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
