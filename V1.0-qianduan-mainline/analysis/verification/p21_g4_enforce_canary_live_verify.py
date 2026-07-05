# -*- coding: utf-8 -*-
"""P21 验证(G-4):enforce/canary 真机全温区长跑 —— 跑后可复核验收。

只读取真实 run 产物(events.jsonl / committed_measurements.json / bundle / recipe),
不驱动任何模拟。验收两条真实作用路径:
  A. 测量提交路径 enforce:被拒点真实被 measurement_txn 判 entered_bo=False、
     真实被 commit gate 挡出 BO(bundle 过滤 + recipe 只见通过点);
  B. 命令路径 canary:主动设计 canary setpoint 真实派发且被物理执行
     (下一实测点温度 ≈ canary_next_t),全程 ActionGate 留痕 bypass=0。
无真机数据则 SKIP,不谎报。
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
MAIN = next(_p for _p in HERE.parents if _p.name == "V1.0-qianduan-mainline")
RUN = MAIN / "runs" / "run_20260702_144507_52a878"   # fe4b:G-4 enforce+canary 全温区长跑

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_events():
    evs = []
    with open(RUN / "events.jsonl", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                evs.append(json.loads(line))
            except Exception:
                continue
    return evs


def main():
    print("=" * 74)
    print("P21:G-4 enforce/canary 真机全温区长跑 —— 跑后验收(只读真实产物)")
    print("=" * 74)
    if not (RUN / "events.jsonl").exists():
        print(f"[SKIP] 无真机 run 产物({RUN}),跳过(不谎报)")
        return 0

    evs = load_events()
    by_type = {}
    for e in evs:
        by_type.setdefault(e.get("type", ""), []).append(e)

    done = (by_type.get("EXPERIMENT_COMPLETED") or [{}])[-1].get("payload", {})
    print(f"run={RUN.name}  status={done.get('status')}  n={done.get('total_measurements')}")
    check("全温区长跑真实完成(status=completed,n≥30)",
          done.get("status") == "completed" and (done.get("total_measurements") or 0) >= 30,
          f"n={done.get('total_measurements')}")

    # ---- A. 测量提交路径 enforce ----
    gate = (by_type.get("COMMIT_GATE") or [{}])[-1].get("payload", {})
    check("COMMIT_GATE 事件为 enforce 且真实拒点(n_rejected>0)",
          gate.get("commit_gate_mode") == "enforce" and (gate.get("n_rejected") or 0) > 0,
          f"mode={gate.get('commit_gate_mode')} n_rejected={gate.get('n_rejected')}")

    cm = json.loads((RUN / "committed_measurements.json").read_text(encoding="utf-8"))
    rej_T = set(round(t, 1) for t in cm.get("rejected_T_C", []))
    rej_rows = cm.get("rejected", [])
    check("被拒点均为真实治理裁决(entered_bo=False,非注入)",
          rej_rows and all(r.get("entered_bo") is False for r in rej_rows)
          and all(not r.get("injected_fault") for r in rej_rows),
          f"rejected_T={sorted(rej_T)}")

    # bundle 真被过滤:门控后 bundle 不含被拒温度;.full 备份含全部
    pp = json.loads((RUN / "post_processing.json").read_text(encoding="utf-8"))
    s0dir = (pp.get("stage0") or {}).get("results_dir")
    bp = Path(s0dir) / "stage0_result_bundle.json" if s0dir else None
    if not (bp and bp.exists()):
        check("找到 fe4b 门控后 bundle", False, f"stage0_result_bundle.json 未找到({s0dir})")
    else:
        b = json.loads(bp.read_text(encoding="utf-8"))
        eis_T = [round(float(p.get("T_K", 0)) - 273.15, 1) for p in b.get("eis_points", [])]
        overlap = rej_T & set(eis_T)
        check("门控后 bundle 不含任何被拒温度(真过滤进 Stage1/BO)",
              not overlap, f"bundle_n={len(eis_T)} overlap={sorted(overlap)}")
        full = bp.parent / "stage0_result_bundle.full.json"
        if full.exists():
            fb = json.loads(full.read_text(encoding="utf-8"))
            check("过滤前 .full 备份保留全部点(可审计)",
                  len(fb.get("eis_points", [])) >= len(eis_T) + len(rej_T),
                  f"full={len(fb.get('eis_points', []))} gated={len(eis_T)} rej={len(rej_T)}")
        else:
            check("过滤前 .full 备份保留全部点(可审计)", False, "无 .full 备份")

    # recipe 真实生成且来源可溯
    recipe = (pp.get("recipe") or {}).get("payload") or {}
    check("Stage1 recipe 真实生成(source_mode=real,带 input_bundle_hash)",
          recipe.get("source_mode") == "real" and bool(recipe.get("input_bundle_hash")),
          f"mode={recipe.get('source_mode')} hash={str(recipe.get('input_bundle_hash'))[:12]}…")

    # ---- B. 命令路径 canary ----
    setpoints = [e.get("payload", {}) for e in by_type.get("EPISTEMIC_CANARY_SETPOINT", [])]
    check("canary setpoint 真实派发(≥1 次,经 ActionGate)",
          len(setpoints) >= 1, f"n={len(setpoints)}")

    # canary 设定点被物理执行:下一实测点温度 ≈ canary_next_t(±1.0°C 腔体容差)
    txn = [e.get("payload", {}) for e in by_type.get("TXN_ADMISSION", [])]
    T_by_step = {int(p["step_idx"]): float(p["temperature_C"]) for p in txn
                 if p.get("step_idx") is not None and p.get("temperature_C") is not None}
    executed = []
    for sp in setpoints:
        nxt = T_by_step.get(int(sp.get("step_idx", -99)) + 1)
        tgt = sp.get("canary_next_t")
        if nxt is not None and tgt is not None:
            executed.append((sp["step_idx"], tgt, nxt, abs(nxt - float(tgt)) <= 1.0))
    check("canary 设定点被物理执行(下一实测点 ≈ canary_next_t ±1.0°C)",
          executed and all(ok for *_, ok in executed),
          "; ".join(f"step{si}: target={t} measured={m}" for si, t, m, _ in executed))

    ag = json.loads((RUN / "action_gate_summary.json").read_text(encoding="utf-8"))
    check("全程 ActionGate 留痕且 bypass=0(自主命令全部过门)",
          ag.get("bypass_count") == 0 and ag.get("n_gated_autonomous_actions", 0) >= len(setpoints),
          f"gated={ag.get('n_gated_autonomous_actions')} bypass={ag.get('bypass_count')}")

    # canary 只小步偏移(受控干预,不夺权):|delta_C| <= 3.0
    check("canary 干预受控(|delta_C|≤3.0,固定阶梯仍是主导)",
          setpoints and all(abs(float(sp.get("delta_C", 99))) <= 3.0 for sp in setpoints),
          "; ".join(f"step{sp['step_idx']}: Δ={sp.get('delta_C')}" for sp in setpoints))

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   (run={RUN.name})")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
