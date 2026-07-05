# -*- coding: utf-8 -*-
"""P13b 验证(P13-B):多角色 LLM 证伪市场**接进 live 收尾**——驱动生产方法本身。

与 p13 的区别:p13 直接调离线 `falsification_market.run_market`;本脚本验证
**`hardware_adapter._run_falsification_market`(真正接进 finalize 的生产代码)**
在真机 σ(T) 上端到端跑通、真实 OpenRouter 调用、落 `epistemic/falsification_market.json`、
发 `MARKET_SETTLED`。真 LLM(非仿真):Proposer/Falsifier/Auditor 真实往返 OpenRouter。

做法(不连硬件、不改 legacy):
  1. 从真机 genuine-live run 的 evidence/EP-*.json 读真实 T_K / σ(与生产 `_measurements` 同构);
  2. `HardwareAdapter.__new__` 绕过 __init__(不连硬件),注入本方法读取的属性
     (_enable_falsification_market / _measurements / _run_id / _emit_event 捕获器);
  3. 调用**生产方法** `_run_falsification_market("completed")`(真 OpenRouter 调用);
  4. 断言:MARKET_SETTLED 真发、>=4 次真 LLM 调用、三角色齐全、产物落盘、
     过度自信稻草人被真实数据证伪→信誉下跌且不高于校准的 LLM 提案者。
无 key/断网 → SKIP,不谎报。

用法: python p13b_market_live_verify.py [run_id]
默认 run = run_20260630_135646_f33d5e。
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

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "run_20260630_135646_f33d5e"
HERE = Path(__file__).resolve()
NDA = (next(_p for _p in HERE.parents if _p.name == "V1.0-qianduan-mainline").parent / "experiments")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
EVID = MAIN / "runs" / RUN_ID / "evidence"

for p in (str(MAIN), str(MAIN / "stage1_optimization"), str(MAIN / "analysis")):
    if p not in sys.path:
        sys.path.insert(0, p)

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_measurements(run_id):
    out = []
    if not EVID.exists():
        return out
    for fp in sorted(EVID.glob("EP-*.json")):
        d = json.loads(fp.read_text(encoding="utf-8")).get("payload", {})
        out.append({
            "success": bool(d.get("success")),
            "temperature_C": d.get("temperature_C"),
            "temperature_K": d.get("temperature_K"),
            "conductivity_S_cm": d.get("conductivity_S_cm"),
            "rb_ohm": d.get("rb_ohm"),
        })
    return out


def main():
    print("=" * 74)
    print("P13b:证伪市场接 live 收尾 —— 驱动生产方法 _run_falsification_market(真 OpenRouter)")
    print("=" * 74)

    meas = load_measurements(RUN_ID)
    real = [m for m in meas if m["success"] and m.get("conductivity_S_cm")]
    if len(real) < 8:
        print(f"[SKIP] 真实 σ(T) 点不足({len(real)}),跳过(不谎报)")
        return 0

    # 先探测 key(无 key 诚实 SKIP,不算失败)
    from epistemic import falsification_market as FM  # noqa: E402
    if not FM.LLMClient().available:
        print("[SKIP] 无 LLM_API_KEY(.env),跳过真实证伪市场(不谎报)")
        return 0

    print(f"run={RUN_ID}  真机 σ(T) 点 n={len(real)}  "
          f"T∈[{min(m['temperature_C'] for m in real):.1f},"
          f"{max(m['temperature_C'] for m in real):.1f}]°C")

    # --- 导入生产模块 + 用 __new__ 绕过 __init__(不连硬件)---
    from backend_api.services import hardware_adapter as HA  # noqa: E402
    adapter = HA.HardwareAdapter.__new__(HA.HardwareAdapter)
    adapter._enable_falsification_market = True
    adapter._measurements = meas
    adapter._run_id = None   # → 写 outputs/epistemic_live_tmp(不污染真实 run 目录)

    captured = []
    adapter._emit_event = lambda etype, payload=None: captured.append((etype, payload or {}))

    print("… 发起真实 OpenRouter 多角色调用(Proposer/Falsifier/Auditor),请稍候 …")
    adapter._run_falsification_market("completed")   # 生产方法本身

    ev = {t: p for (t, p) in captured}
    check("生产方法发出 MARKET_SETTLED 事件(未 UNAVAILABLE/SKIPPED/ERROR)",
          "MARKET_SETTLED" in ev, f"events={sorted(ev.keys())}")
    if "MARKET_SETTLED" not in ev:
        for t, p in captured:
            print(f"    emitted {t}: {p}")
        n_fail = 1
    else:
        summ = ev["MARKET_SETTLED"]
        out_json = Path(summ.get("output_dir", "")) / "falsification_market.json"
        check("生产产物 falsification_market.json 真实落盘", out_json.exists(), str(out_json))
        market = json.loads(out_json.read_text(encoding="utf-8")) if out_json.exists() else {}

        n_calls = summ.get("n_real_llm_calls", 0)
        roles = set(summ.get("real_call_roles", []))
        check("真实 LLM 调用 >=4(proposer+falsifier+auditor 多轮)",
              n_calls >= 4, f"n_calls={n_calls} roles={sorted(roles)}")
        check("多角色齐全:proposer/falsifier/auditor 均真实发起",
              {"proposer", "falsifier", "auditor"}.issubset(roles),
              f"roles={sorted(roles)}")

        llm_c = next((c for c in market.get("contracts", []) if c.get("source") == "llm"), None)
        check("LLM 产出合法押注合同(claim_model∈候选族, confidence∈(0,1))",
              llm_c is not None and llm_c.get("claim_model") in FM.MODEL_FAMILIES
              and 0 < llm_c.get("staked_confidence", 0) < 1,
              f"claim={llm_c.get('claim_model') if llm_c else None} "
              f"conf={llm_c.get('staked_confidence') if llm_c else None}")
        if llm_c:
            print(f"  LLM 合同: claim={llm_c['claim_model']} conf={llm_c['staked_confidence']:.2f}")
            print(f"           证伪条件: {str(llm_c.get('falsification_conditions'))[:120]}")

        straw_setts = market.get("settlements", {}).get("Strawman_Overconfident", [])
        check("在真实数据上完成多轮结算(z-score/outcome)",
              len(straw_setts) >= 2, f"strawman 结算轮数={len(straw_setts)}")
        if straw_setts:
            print("  稻草人逐轮结算(真实数据):")
            for s in straw_setts:
                print(f"    T={s['test_T_K']:.1f}K pred={s['predicted_y']:.2f} "
                      f"obs={s['observed_y']:.2f} z={s['z_score']:.2f} "
                      f"survived={s['survived']} outcome={s['outcome']}")

        rep = summ.get("reputation", {})
        straw_rep = rep.get("Strawman_Overconfident", 1.0)
        check("严格评分:过度自信稻草人被真实数据证伪→信誉显著下跌(<0.6)",
              straw_rep < 0.6, f"strawman reputation={straw_rep:.4f}")
        check("严格评分:校准的 LLM 提案者信誉 >= 过度自信稻草人(机制设计核心)",
              summ.get("overconfident_strawman_beaten") is True,
              f"beaten={summ.get('overconfident_strawman_beaten')} rep={rep}")

        print("\n  信誉(资本)终值:")
        for a, rv in rep.items():
            print(f"    {a:26s} reputation={rv:.4f}")
        n_fail = sum(1 for _, s, _ in results if s == FAIL)

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   "
          f"(生产方法 hardware_adapter._run_falsification_market 真机 σ(T) + 真 OpenRouter)")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
