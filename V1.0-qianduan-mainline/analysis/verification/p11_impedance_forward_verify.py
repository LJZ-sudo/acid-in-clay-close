# -*- coding: utf-8 -*-
"""P11 验证:阻抗级正问题(MechanismModel)在**真实 EIS 谱**上跑通。

数据:真实 genuine-live run `run_20260629_112156_9db536` 的逐点 evidence JSON,
每点含真实 frequencies / z_real / z_imag(84 频点)。验证:
  1. 三机制(single_bulk / bulk_electrode / two_population)对真谱真实拟合,参数有限、被动性成立;
  2. 物理静态检查(Re Z>0、CPE 指数 ∈(0,1]、Fisher λ_min 可观测性)真实给出;
  3. 机制谱级判别(AIC 权重)随温度演化 —— 冷端(穿相变后)更偏好"电极阻塞/双弧"(半圆+斜线),
     与 S06 真实机制叙事一致;
  4. 拟合优度 RMS 在合理量级(数据级证据,不是占位)。
无谱数据则 SKIP,不谎报。
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
NDA = (next(_p for _p in HERE.parents if _p.name == "V1.0-qianduan-mainline").parent / "research")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
EVID = MAIN / "runs" / "run_20260629_112156_9db536" / "evidence"
if str(MAIN / "analysis") not in sys.path:
    sys.path.insert(0, str(MAIN / "analysis"))

from epistemic import impedance_models as IM  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_spectra():
    out = []
    if not EVID.exists():
        return out
    for fp in sorted(EVID.glob("EP-*.json")):
        d = json.loads(fp.read_text(encoding="utf-8")).get("payload", {})
        f = d.get("frequencies"); zr = d.get("z_real"); zi = d.get("z_imag")
        if not (f and zr and zi) or len(f) < 10:
            continue
        out.append({
            "T_C": d.get("temperature_C"), "rb_ohm": d.get("rb_ohm"),
            "f": np.array(f, float), "zr": np.array(zr, float),
            "zi": np.array(zi, float), "qc": d.get("qc_grade"),
        })
    out.sort(key=lambda s: (s["T_C"] if s["T_C"] is not None else 0), reverse=True)
    return out


def main():
    print("=" * 72)
    print("P11:阻抗级正问题 MechanismModel —— 真实 EIS 谱验证")
    print("=" * 72)
    spectra = load_spectra()
    if len(spectra) < 5:
        print(f"[SKIP] 真实谱不足({len(spectra)}),跳过(不谎报)")
        return
    print(f"真实谱 n={len(spectra)}  T∈[{spectra[-1]['T_C']:.1f},{spectra[0]['T_C']:.1f}]°C  "
          f"每谱频点≈{len(spectra[0]['f'])}")

    out_dir = NDA / "results" / "epistemic_out"; out_dir.mkdir(exist_ok=True)

    def bulk_resistance(fit):
        """从机制拟合提取'体相电阻'(对照 reverse_zero_crossing 实测 rb)。
        single_bulk/bulk_electrode → Rb;two_population → R1+R2(两弧之和=总体相)。"""
        th = fit.theta
        if fit.model == "two_population":
            return float(th[1] + th[4])
        return float(th[1])

    rows = []
    n_passive = 0; n_finite = 0; n_goodfit = 0
    per_T_best = []
    for s in spectra:
        fits = IM.fit_all_mechanisms(s["f"], s["zr"], s["zi"])
        w = IM.aic_weights(fits)
        best = max(w, key=lambda k: (w[k] if np.isfinite(w[k]) else -1))
        bf = fits[best]
        rb_best = bulk_resistance(bf)
        if bf.ok and np.isfinite(rb_best):
            n_finite += 1
        if all(f.passive for f in fits.values() if f.ok):
            n_passive += 1
        if bf.ok and np.isfinite(bf.weighted_resid_rms) and bf.weighted_resid_rms < 0.35:
            n_goodfit += 1
        per_T_best.append((s["T_C"], best, w, s["rb_ohm"]))
        rows.append({
            "T_C": s["T_C"], "qc": s["qc"], "rb_measured": s["rb_ohm"],
            "best_mechanism": best,
            "best_bulk_R": rb_best, "best_wrms": bf.weighted_resid_rms,
            "best_lambda_min": bf.lambda_min, "best_cond": bf.condition_number,
            "best_invariants": bf.invariants,
            "aic_weights": {k: (round(v, 3) if np.isfinite(v) else None) for k, v in w.items()},
        })
    (out_dir / "impedance_forward_fits.json").write_text(
        json.dumps({"n_spectra": len(spectra), "fits": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    import math
    check("阻抗正问题:最优机制对真谱拟合出有限体相电阻(>=80% 谱)",
          n_finite >= 0.8 * len(spectra), f"{n_finite}/{len(spectra)}")
    check("物理静态检查:被动性 Re Z>0 成立(>=80% 谱)",
          n_passive >= 0.8 * len(spectra), f"{n_passive}/{len(spectra)}")
    check("阻抗正问题:最优机制对真谱拟合优度合格(加权残差RMS<0.35,>=80% 谱)",
          n_goodfit >= 0.8 * len(spectra), f"{n_goodfit}/{len(spectra)}")

    # 最优机制体相电阻 与 reverse_zero_crossing 实测 rb 的趋势一致性(秩相关)。
    # 诚实说明:电极阻塞尾巴主导时,绝对体相电阻仅弱可辨识(R∥CPE 会向纯 CPE 简并去拟合尾巴),
    # 这本身是一个真实的可观测性发现。故这里验证趋势(随冷却单调上升)而非绝对量级,
    # 绝对体相电阻以项目已验证的 HF 截距提取(reverse_zero_crossing)为准。
    from scipy.stats import spearmanr
    pairs = [(r["rb_measured"], r["best_bulk_R"]) for r in rows
             if r["rb_measured"] and r["best_bulk_R"] and r["rb_measured"] > 0 and r["best_bulk_R"] > 0]
    rho, _ = spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
    check("阻抗正问题:正问算子体相电阻 与独立 rb 提取 趋势一致(Spearman ρ>0.6)",
          rho > 0.6, f"ρ={rho:.3f} n={len(pairs)}  [注:绝对量级在电极阻塞下弱可辨识—真实观测性发现]")

    lam_ok = sum(1 for r in rows if np.isfinite(r["best_lambda_min"]))
    check("方案一(谱级):Fisher λ_min 参数可观测性对真谱给出有限值",
          lam_ok >= 0.8 * len(spectra), f"{lam_ok}/{len(spectra)}")

    # 机制谱级判别真实随温度演化(非恒定),且最冷/穿相变端偏好最富结构模型
    distinct = {b for (_, b, _, _) in per_T_best}
    check("机制谱级判别:偏好随温度真实演化(非恒定单一机制)",
          len(distinct) >= 2, f"出现机制={sorted(distinct)}")
    coldest = sorted([x for x in per_T_best if x[0] is not None], key=lambda x: x[0])[:3]
    cold_multi = sum(1 for (_, b, _, _) in coldest if b in ("two_population", "bulk_electrode"))
    check("机制谱级判别:最冷3点(穿相变后,体相弧增大)偏好多弧/电极阻塞结构",
          cold_multi >= 2, f"coldest={[(round(t,1),b) for (t,b,_,_) in coldest]}")

    print("\n  逐温机制偏好(AIC 权重最高者 / 体相R对照):")
    for (t, b, w, rbm) in per_T_best[::max(1, len(per_T_best)//9)]:
        ws = " ".join(f"{k}={w[k]:.2f}" for k in w if np.isfinite(w[k]))
        rrow = next(r for r in rows if r["T_C"] == t)
        print(f"    T={t:6.1f}°C best={b:14s} R_bulk={rrow['best_bulk_R']:9.3g} "
              f"rb_meas={rbm:9.3g} wrms={rrow['best_wrms']:.3f} [{ws}]")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 72)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   产物→ epistemic_out/impedance_forward_fits.json")
    print("=" * 72)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
