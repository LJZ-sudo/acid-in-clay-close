# -*- coding: utf-8 -*-
"""P12 验证:可知性驱动内层自主选温(Gap2)在**真实 σ(T)**上的闭环价值。

不造任何数据:用真实 live run 的 (T, σ) 池做 replay 闭环。
对比两种"下一个测温点"策略,从同一初始种子(最暖 N 点)出发,每步只能从
**真实剩余点**里取一个并揭示其真实 lnσ:
  - uniform   : 按温度顺序逐点(项目当前的均匀阶梯)
  - adaptive  : epistemic.active_design.select_next_temperature(单位成本期望机制判别价值)

度量:识别"正确机制"(=全数据 AIC 最优,本数据为含相变的 segmented)所需点数。
预期:自适应用更少点把竞争机制分开(更早 posterior 收敛到真模型)。
另验证:hardware_adapter 接线(enable_active_design)真能产出 EPISTEMIC_NEXT_ACTION 建议。
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
NDA = (next(_p for _p in HERE.parents if _p.name == "V1.0-qianduan-mainline").parent / "experiments")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
RUN_DIR = MAIN.parent / "experiments" / "runs" / "run_20260629_112156_9db536"
for p in (str(MAIN / "analysis"), str(MAIN)):
    if p not in sys.path:
        sys.path.insert(0, p)

from epistemic import models as M          # noqa: E402
from epistemic import active_design as AD   # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_live_T_sigma():
    T, S = [], []
    f = RUN_DIR / "events.jsonl"
    if not f.exists():
        return None, None
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
    if len(T) < 8:
        return None, None
    T = np.array(T); y = np.log(np.array(S))
    o = np.argsort(T)
    return T[o], y[o]


def best_model(T, y):
    specs = M.fit_all(T, y)
    post = AD.aic_posterior(specs)
    valid = {n: p for n, p in post.items() if np.isfinite(p)}
    if not valid:
        return None, post
    b = max(valid, key=valid.get)
    return b, post


def run_strategy(T_all, y_all, seed_idx, strategy, truth, post_thresh=0.6):
    """返回 (points_to_identify, history)。识别 = AIC 最优==truth 且后验>post_thresh。"""
    obs = list(seed_idx)
    remaining = [i for i in range(len(T_all)) if i not in obs]
    hist = []
    n_to_id = None
    while remaining:
        To = T_all[obs]; yo = y_all[obs]
        b, post = best_model(To, yo)
        idok = (b == truth and np.isfinite(post.get(truth, 0)) and post[truth] >= post_thresh)
        hist.append({"n": len(obs), "best": b, "post_truth": round(float(post.get(truth, float('nan'))), 3)})
        if idok and n_to_id is None:
            n_to_id = len(obs)
            break
        # 选下一点
        if strategy == "uniform":
            # 温度降序补点(项目当前阶梯)
            nxt = min(remaining, key=lambda i: T_all[i])  # 取更冷的(顺着扫)
            # uniform 按降温顺序:实际剩余里温度最高的先(逼近真实扫序),这里反向
            nxt = max(remaining, key=lambda i: T_all[i])
        else:  # adaptive
            cand_T = [float(T_all[i]) for i in remaining]
            choice = AD.select_next_temperature(list(To), list(yo), cand_T)
            if choice is None:
                nxt = max(remaining, key=lambda i: T_all[i])
            else:
                nxt = min(remaining, key=lambda i: abs(T_all[i] - choice.next_T_K))
        obs.append(nxt); remaining.remove(nxt)
    if n_to_id is None:
        To = T_all[obs]; yo = y_all[obs]
        b, post = best_model(To, yo)
        if b == truth and post.get(truth, 0) >= post_thresh:
            n_to_id = len(obs)
    return n_to_id, hist


def main():
    print("=" * 72)
    print("P12:可知性驱动内层自主选温(Gap2)—— 真实 σ(T) replay 闭环")
    print("=" * 72)
    T, y = load_live_T_sigma()
    if T is None:
        print("[SKIP] 真实 σ(T) 不足,跳过(不谎报)")
        return
    print(f"真实点 n={len(T)}  T∈[{T.min():.1f},{T.max():.1f}]K")

    truth, post_full = best_model(T, y)
    check("全数据可定真模型(竞争机制可辨识)", truth is not None,
          f"truth={truth} 全数据后验={ {k: round(v,2) for k,v in post_full.items() if np.isfinite(v)} }")
    if truth is None:
        return

    # 初始种子:最暖 4 点(线性段,不含相变信息)
    seed = list(np.argsort(-T)[:4])
    n_uni, h_uni = run_strategy(T, y, seed, "uniform", truth)
    n_ada, h_ada = run_strategy(T, y, seed, "adaptive", truth)
    print(f"\n  truth='{truth}'  种子=最暖4点")
    print(f"  uniform  识别所需点数 = {n_uni}")
    print(f"  adaptive 识别所需点数 = {n_ada}")
    print(f"  adaptive 选点后验轨迹: {[ (h['n'], h['post_truth']) for h in h_ada ]}")

    check("adaptive 真实产出选点决策(选择器在闭环里被调用)", len(h_ada) >= 1,
          f"adaptive 步数={len(h_ada)}")
    check("adaptive 识别正确机制不慢于 uniform(真实数据上自适应≥均匀)",
          (n_ada is not None) and (n_uni is None or n_ada <= n_uni),
          f"adaptive={n_ada} vs uniform={n_uni}")

    # 选择器价值面真实非平凡:不同候选的单位成本判别价值有区分度
    seedT = list(T[seed]); seedY = list(y[seed])
    cand = [float(t) for i, t in enumerate(T) if i not in seed]
    ch = AD.select_next_temperature(seedT, seedY, cand)
    check("选择器给出非平凡价值排序(候选间 value_per_cost 有区分)",
          ch is not None and len(ch.ranking) >= 2 and ch.ranking[0][1] > 0,
          f"top3={ch.ranking[:3] if ch else None}")
    if ch:
        print(f"  选择器推荐下一温度 = {ch.next_T_K:.1f}K ({ch.next_T_K-273.15:.1f}°C)  "
              f"value/cost={ch.value_per_cost:.4g}  {ch.n_competing} 机制竞争")

    # 生产路径接线:hardware_adapter enable_active_design 真产出建议
    try:
        from backend_api.services.hardware_adapter import HardwareAdapter  # noqa
        ha = HardwareAdapter()
        ha._enable_active_design = True
        ha._step_size = 10.0
        ha._measurements = [
            {"success": True, "temperature_K": float(tk),
             "conductivity_S_cm": float(np.exp(yy))}
            for tk, yy in zip(T, y)
        ]
        emitted = {}
        ha._emit_event = lambda k, p: emitted.setdefault(k, p)  # type: ignore
        adv = ha._epistemic_next_action(step_idx=len(T))
        ok = (adv is not None and "recommended_next_temp_K" in adv
              and "EPISTEMIC_NEXT_ACTION" in emitted)
        check("生产路径:hardware_adapter._epistemic_next_action 产出建议并发事件",
              ok, f"rec_next_C={adv.get('recommended_next_temp_C') if adv else None} "
                  f"gate={adv.get('gate_status') if adv else None}")
    except Exception as exc:
        check("生产路径:hardware_adapter._epistemic_next_action 产出建议并发事件",
              False, f"异常:{exc}")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 72)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL")
    print("=" * 72)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
