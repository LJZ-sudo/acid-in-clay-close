# -*- coding: utf-8 -*-
"""P13 验证:多角色 LLM 证伪市场(Gap3)—— 真实 OpenRouter 调用 + 真实数据结算。

非仿真:Proposer/Falsifier/Auditor 是**真实 LLM 往返**(OpenRouter,gpt-5.4,读 stage1/.env)。
结算用真实 σ(T) replay + 严格适当评分(EpistemicAccount)。验证:
  1. 真实 LLM 调用 >=4(proposer + 每轮 falsifier/auditor);
  2. LLM 产出合法押注合同(claim_model ∈ 候选族, staked_confidence ∈(0,1), 含证伪条件);
  3. 在真实数据上完成多轮结算(z-score / survived / outcome);
  4. 资本/信誉按严格评分更新:过度自信稻草人(押 arrhenius@0.97,真数据含相变→被证伪)
     信誉显著低于 1.0,且不高于(通常低于)更校准的 LLM 提案者。
无 key/断网 → SKIP,不谎报。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

HERE = Path(__file__).resolve()
NDA = next(_p for _p in HERE.parents if _p.name == "research")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
S1 = MAIN / "stage1_optimization"
RUN_DIR = MAIN / "runs" / "run_20260629_112156_9db536"
for p in (str(NDA), str(S1), str(MAIN)):
    if p not in sys.path:
        sys.path.insert(0, p)

from epistemic import falsification_market as FM  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_live_T_sigma():
    T, S = [], []
    f = RUN_DIR / "events.jsonl"
    for l in f.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        t = e.get("type") or e.get("event")
        pl = e.get("payload") or {}
        if t == "MEASUREMENT_COMPLETED" and pl.get("success") and pl.get("conductivity_S_cm"):
            tk = pl.get("temperature_K")
            if tk is None and pl.get("temperature_C") is not None:
                tk = pl["temperature_C"] + 273.15
            sg = pl.get("conductivity_S_cm")
            if tk and sg and sg > 0:
                T.append(float(tk)); S.append(float(sg))
    T = np.array(T); y = np.log(np.array(S))
    o = np.argsort(T)
    return T[o], y[o]


def main():
    print("=" * 72)
    print("P13:多角色 LLM 证伪市场(Gap3)—— 真实 OpenRouter + 真实数据结算")
    print("=" * 72)
    T, y = load_live_T_sigma()
    print(f"真实点 n={len(T)}  T∈[{T.min():.1f},{T.max():.1f}]K")

    client = FM.LLMClient()
    if not client.available:
        print("[SKIP] 无 LLM_API_KEY,跳过真实证伪市场(不谎报)")
        return
    print(f"LLM:model={client.model} base={client.base_url}")

    summary = FM.run_market(T, y, client=client, n_seed=6, n_rounds=4, include_strawman=True)

    out_dir = NDA / "results" / "epistemic_out"; out_dir.mkdir(exist_ok=True)
    (out_dir / "falsification_market.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    n_calls = len(summary["llm_calls"])
    roles = {c["role"] for c in summary["llm_calls"]}
    check("真实 LLM 调用 >=4(proposer+falsifier+auditor 多轮)", n_calls >= 4,
          f"n_calls={n_calls} roles={sorted(roles)}")
    check("多角色齐全:proposer/falsifier/auditor 均真实发起", 
          {"proposer", "falsifier", "auditor"}.issubset(roles),
          f"roles={sorted(roles)}")

    llm_c = next((c for c in summary["contracts"] if c["source"] == "llm"), None)
    check("LLM 产出合法押注合同(claim_model∈候选族, confidence∈(0,1))",
          llm_c is not None and llm_c["claim_model"] in FM.MODEL_FAMILIES
          and 0 < llm_c["staked_confidence"] < 1,
          f"claim={llm_c['claim_model'] if llm_c else None} "
          f"conf={llm_c['staked_confidence'] if llm_c else None}")
    if llm_c:
        print(f"  LLM 合同: claim={llm_c['claim_model']} conf={llm_c['staked_confidence']:.2f}")
        print(f"           证伪条件: {llm_c['falsification_conditions'][:120]}")
        print(f"           rationale: {llm_c['rationale'][:120]}")

    # 多轮真实数据结算存在
    straw_setts = summary["settlements"].get("Strawman_Overconfident", [])
    check("在真实数据上完成多轮结算(z-score/outcome)", len(straw_setts) >= 2,
          f"strawman 结算轮数={len(straw_setts)}")
    if straw_setts:
        print("  稻草人逐轮结算(真实数据):")
        for s in straw_setts:
            print(f"    T={s['test_T_K']:.1f}K pred={s['predicted_y']:.2f} obs={s['observed_y']:.2f} "
                  f"z={s['z_score']:.2f} survived={s['survived']} outcome={s['outcome']}")

    rep = summary["reputation"]
    straw_rep = rep.get("Strawman_Overconfident", 1.0)
    check("严格评分:过度自信稻草人被真实数据证伪→信誉显著下跌(<0.6)",
          straw_rep < 0.6, f"strawman reputation={straw_rep:.4f}")

    if llm_c:
        llm_rep = rep.get("LLM_Proposer", rep.get(llm_c["agent"], 1.0))
        check("严格评分:校准的 LLM 提案者信誉 >= 过度自信稻草人(机制设计核心)",
              llm_rep >= straw_rep,
              f"LLM_rep={llm_rep:.4f} vs strawman={straw_rep:.4f}")

    print("\n  信誉(资本)终值:")
    for a, rv in rep.items():
        print(f"    {a:26s} reputation={rv:.4f} brier={summary['brier'][a]}")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 72)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   产物→ epistemic_out/falsification_market.json")
    print(f"真实 LLM 调用次数={n_calls}")
    print("=" * 72)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
