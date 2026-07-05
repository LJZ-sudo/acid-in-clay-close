# -*- coding: utf-8 -*-
"""P10 验证:GPT 三大原创方向的**真实可计算对象**在真实 live 数据上跑通 + 可证伪验证。

数据:真实 genuine-live run `run_20260629_112156_9db536`(19 真机点,全温区,2 相变)。
对象:
  方案一 observability_certificate  —— Fisher λ_min + JS 机制等价类 + 不可辨识性证书(+反事实"需要何种新能力")
  方案三 min_discriminating_set     —— 最小成本判别实验集(精确集合覆盖)+ 编译失败→等价类(独立复核覆盖正确性)
  方案二 eprocess_falsification     —— anytime-valid e-process(蒙特卡洛实测 H0 越界率 ≤ α = Ville)+ 单位成本证伪价值 + 严格评分信誉

全部纯 numpy/scipy 真实运算,无仿真占位、不调 LLM。无数据则 SKIP,不谎报。
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
NDA = HERE.parent
MAIN = NDA.parent / "V1.0-qianduan-mainline"
RUN_DIR = MAIN / "runs" / "run_20260629_112156_9db536"
for p in (str(NDA),):
    if p not in sys.path:
        sys.path.insert(0, p)

from epistemic import models as M  # noqa: E402
from epistemic import observability_certificate as OC  # noqa: E402
from epistemic import min_discriminating_set as MDS  # noqa: E402
from epistemic import eprocess_falsification as EF  # noqa: E402

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
    if len(T) < 6:
        return None, None
    T = np.array(T); y = np.log(np.array(S))
    o = np.argsort(T)
    return T[o], y[o]


def main():
    print("=" * 72)
    print("P10:Epistemic OS 三大原创可计算对象 —— 真实 live 数据验证")
    print("=" * 72)
    T, y = load_live_T_sigma()
    if T is None:
        print("[SKIP] 未找到真实 live 数据,跳过(不谎报)")
        return
    print(f"真实 live:n={len(T)}  T∈[{T.min()-273.15:.1f},{T.max()-273.15:.1f}]°C  "
          f"lnσ∈[{y.min():.2f},{y.max():.2f}]")

    out_dir = NDA / "epistemic_out"
    out_dir.mkdir(exist_ok=True)

    # --- 公共:拟合检查 ---
    specs = M.fit_all(T, y)
    ok_models = [n for n, s in specs.items() if s.ok]
    sigma = M.measurement_noise_sd(specs)
    check("models:4 竞争模型至少 3 个拟合成功", len(ok_models) >= 3,
          f"ok={ok_models} sigma_ln={sigma:.3f}")
    check("models:测量噪声 sd 为正且有限", np.isfinite(sigma) and sigma > 0, f"{sigma:.4f}")

    # ============ 方案一:不可辨识性证书 ============
    print("\n>>> 方案一 UnidentifiabilityCertificate")
    cert = OC.build_certificate(T, y, delta=0.05, label="live_run")
    OC.write_certificate(cert, out_dir / "observability_certificate.json")
    fobs = cert["fisher_observability"]
    lam_ok = all(v.get("ok") and np.isfinite(v["lambda_min"]) for v in fobs.values())
    check("方案一:Fisher 可观测性对每个模型给出有限 λ_min", lam_ok,
          "; ".join(f"{k}:λmin={v['lambda_min']:.2e},cond={v['condition_number']:.1e}"
                    for k, v in fobs.items()))
    check("方案一:产出机制等价类(连通分量)", isinstance(cert["equivalence_classes"], list)
          and len(cert["equivalence_classes"]) >= 1, f"{cert['equivalence_classes']}")
    check("方案一:逐对 sup_JS + 最佳判别动作齐全",
          all("sup_JS" in p and "best_action_T_C" in p for p in cert["pairwise"]),
          f"n_pairs={len(cert['pairwise'])}")
    check("方案一:verdict 合法", cert["verdict"] in (
        "all_pairs_distinguishable_under_current_design",
        "design_conditional_unidentifiability"), cert["verdict"])
    # 若有不可分对,必须给"需要的新能力"且为真实反事实(achieved_sup_JS 数值)
    unident = [p for p in cert["pairwise"] if not p["distinguishable"]]
    if unident:
        good = all("required_new_capability" in p and
                   all("achieved_sup_JS" in o for o in p["required_new_capability"]["options"])
                   for p in unident)
        check("方案一:不可分对给出真实反事实'需要的新能力'", good,
              f"n_unident={len(unident)}")
        for p in unident:
            rc = p["required_new_capability"]
            print(f"    不可分 {p['pair']}: sup_JS={p['sup_JS']:.3f}<δ; "
                  f"cheapest_feasible={rc['cheapest_feasible']}")
    else:
        print("    本数据下全部模型对在当前设计下可区分(无不可分对)")
    print(f"    AIC 最优模型={cert['aic_best_model']}; "
          f"可分/不可分对={cert['n_distinguishable_pairs']}/{cert['n_unidentifiable_pairs']}")

    # ============ 方案三:最小判别实验集 ============
    print("\n>>> 方案三 MinimalDiscriminatingExperimentSet")
    mds = MDS.build_min_discriminating_set(T, y, delta=0.05, label="live_run")
    MDS.write_result(mds, out_dir / "min_discriminating_set.json")
    ms = mds["minimal_set"]["exact_optimal"]
    check("方案三:对真实可执行温度锚点求出精确最小集",
          ms["n_actions"] >= 0 and np.isfinite(ms["total_cost"]) if mds["n_separable_pairs"] else True,
          f"n_actions={ms['n_actions']} cost={ms['total_cost']} "
          f"T_C={ms['action_T_C']}")
    # 独立复核:所选动作确实把所有"可分对"都以 JS>=δ 分开
    chosen_T = np.array(ms["action_T_K"])
    delta = mds["js_delta_threshold"]
    names = mds["models"]
    from itertools import combinations
    sep_ok = True; covered_pairs = 0; total_separable = mds["n_separable_pairs"]
    for ni, nj in combinations(names, 2):
        # 该对是否可分(全动作)
        A_all = np.unique(T)
        sup_all = max(M.js_divergence_gaussian(
            float(specs[ni].predict(np.array([a]))[0]),
            float(specs[nj].predict(np.array([a]))[0]), sigma) for a in A_all)
        if sup_all < delta:
            continue  # 不可分对,不要求被覆盖
        # 在所选集合里是否被分开
        sep_here = max((M.js_divergence_gaussian(
            float(specs[ni].predict(np.array([a]))[0]),
            float(specs[nj].predict(np.array([a]))[0]), sigma) for a in chosen_T),
            default=0.0) if len(chosen_T) else 0.0
        if sep_here >= delta:
            covered_pairs += 1
        else:
            sep_ok = False
    check("方案三:独立复核 —— 最小集覆盖所有可分对(JS>=δ)", sep_ok,
          f"covered {covered_pairs}/{total_separable} separable pairs")
    gr = mds["minimal_set"]["greedy"]
    check("方案三:贪心近似比 >= 1(精确不劣于贪心)",
          (gr["approx_ratio_vs_exact"] is None) or (gr["approx_ratio_vs_exact"] >= 0.999),
          f"ratio={gr['approx_ratio_vs_exact']}")
    check("方案三:编译状态合法", mds["compilation"]["status"] in ("ok", "compilation_failed"),
          mds["compilation"]["status"])
    if mds["compilation"]["status"] == "compilation_failed":
        for up in mds["compilation"]["unidentifiable_pairs"]:
            print(f"    编译失败 {up['pair']}: cheapest_feasible="
                  f"{up['required_new_capability']['cheapest_feasible']}")

    # ============ 方案二:anytime-valid e-process ============
    print("\n>>> 方案二 FalsificationEProcess (anytime-valid)")
    ef = EF.run_falsification_on_sigmaT(T, y, alpha=0.05, holdout_frac=0.45,
                                        label="live_run", n_type_i_sims=20000)
    EF.write_result(ef, out_dir / "eprocess_falsification.json")
    if ef.get("status") == "insufficient_test_points":
        check("方案二:测试点充足", False, "cold 测试点不足")
    else:
        ti = ef["type_i_control"]; ep = ef["eprocess"]
        # 关键:anytime-valid 的硬证明 —— H0 下经验越界率 ≤ α(Ville)
        check("方案二:【anytime-valid】H0 下经验越界率 ≤ α(Ville 不等式成立)",
              ti["anytime_valid_ok"],
              f"false_alarm={ti['empirical_false_alarm_rate']:.4f} <= α+tol={ef['alpha']}+0.01")
        check("方案二:e-process 轨迹长度 = cold 测试点数",
              len(ep["log_E_trajectory"]) == ef["n_test_cold"],
              f"len={len(ep['log_E_trajectory'])} n_test={ef['n_test_cold']}")
        check("方案二:E_t 越界与停时自洽(log 空间,无 inf)",
              (ep["crossed"] == (ep["stopping_time"] is not None)) and np.isfinite(ep["log_E_max"]),
              f"crossed={ep['crossed']} stop={ep['stopping_time']} log_E_max={ep['log_E_max']:.2f}")
        print(f"    H0={ef['H0']} H1={ef['H1']} cold 测试 T_C={ef['test_T_C']}")
        print(f"    log_E_final={ep['log_E_final']:.2f} log_E_max={ep['log_E_max']:.2f} "
              f"crossed={ep['crossed']} 可升级主张={ef['claim_escalation_allowed']}")

    # 单位成本证伪价值
    fvpc = EF.falsification_value_per_cost(T, y, rho=0.5, label="live_run")
    EF.write_result(fvpc, out_dir / "falsification_value_per_cost.json")
    check("方案二:单位成本证伪价值选出下一个最优实验",
          fvpc["best_next_experiment_T_C"] is not None
          and len(fvpc["ranked_actions"]) >= 1,
          f"best_next_T_C={fvpc['best_next_experiment_T_C']} sel={fvpc['selected_model']}")
    check("方案二:FVPC 排序单调递减",
          all(fvpc["ranked_actions"][i]["falsification_value_per_cost"]
              >= fvpc["ranked_actions"][i+1]["falsification_value_per_cost"] - 1e-12
              for i in range(len(fvpc["ranked_actions"]) - 1)))

    # 信誉:严格适当评分(过度自信被惩罚)
    preds = (
        [{"agent": "overconfident", "p": 0.97, "outcome": 0} for _ in range(5)] +
        [{"agent": "overconfident", "p": 0.97, "outcome": 1} for _ in range(5)] +
        [{"agent": "calibrated", "p": 0.55, "outcome": 1} for _ in range(6)] +
        [{"agent": "calibrated", "p": 0.45, "outcome": 0} for _ in range(4)]
    )
    rep = EF.reputation_demo(preds)
    EF.write_result(rep, out_dir / "reputation_proper_scoring.json")
    ra = rep["agents"]
    check("方案二:严格评分惩罚过度自信(信誉 over<calibrated)",
          ra["overconfident"]["reputation"] < ra["calibrated"]["reputation"],
          f"over={ra['overconfident']['reputation']:.3e} cal={ra['calibrated']['reputation']:.3e}")
    check("方案二:执行权不读自报置信度(双账户分离)",
          rep["execution_authority_ignores_self_confidence"] is True)

    # ============ 受限设计场景:证明"不可辨识/编译失败"分支真会触发 ============
    # GPT 核心论点:设计受限(窄温窗)时机制不可辨识,系统应诚实输出"看不清"而非硬选。
    # 取暖端窄窗子集(1/T 跨度小)→ Arrhenius/VTF/Mott/Segmented 实践不可辨识。
    print("\n>>> 受限设计场景(暖端窄窗,演示不可辨识性证书 + 编译失败真分支)")
    warm = T >= (np.median(T))            # 取较暖一半(窄 1/T 跨度)
    Tw, yw = T[warm], y[warm]
    if len(Tw) >= 5:
        cert_w = OC.build_certificate(Tw, yw, delta=0.05, label="restricted_warm_window")
        OC.write_certificate(cert_w, out_dir / "observability_certificate_restricted.json")
        mds_w = MDS.build_min_discriminating_set(Tw, yw, delta=0.05,
                                                 label="restricted_warm_window")
        MDS.write_result(mds_w, out_dir / "min_discriminating_set_restricted.json")
        print(f"    窄窗 n={len(Tw)} T∈[{Tw.min()-273.15:.1f},{Tw.max()-273.15:.1f}]°C "
              f"等价类={cert_w['equivalence_classes']}")
        # 该场景应当出现至少一个不可分对(非平凡等价类)或编译失败,否则跳过不强断言
        has_unident = cert_w["n_unidentifiable_pairs"] >= 1
        check("受限设计:窄窗下出现不可辨识对(机制等价类合并)",
              has_unident, f"n_unident={cert_w['n_unidentifiable_pairs']} "
              f"verdict={cert_w['verdict']}")
        if has_unident:
            # 不可分对必须带真实反事实"需要的新能力",且其中"扩温窗"应能打破(可证伪闭环)
            up = [p for p in cert_w["pairwise"] if not p["distinguishable"]][0]
            rc = up["required_new_capability"]
            check("受限设计:不可分对给出可打破等价的新能力(真实反事实)",
                  rc["any_feasible"] is True,
                  f"{up['pair']} cheapest={rc['cheapest_feasible']}")
            check("受限设计:min_set 对不可分对输出 compilation_failed",
                  mds_w["compilation"]["status"] == "compilation_failed",
                  mds_w["compilation"]["status"])
    else:
        print("    暖端点不足,跳过受限场景(不谎报)")

    # ============ 生产 live-loop 接线验证:HardwareAdapter._run_epistemic ============
    # 证明三对象**已接进 live 回路**(收尾真算),而非只在旁路脚本能跑。
    print("\n>>> 生产 live-loop 接线 HardwareAdapter._run_epistemic")
    try:
        if str(MAIN) not in sys.path:
            sys.path.insert(0, str(MAIN))
        from backend_api.services.hardware_adapter import HardwareAdapter  # noqa: E402
        ad = HardwareAdapter()
        ad._measurements = [{
            "success": True, "temperature_K": float(tk),
            "temperature_C": float(tk - 273.15), "conductivity_S_cm": float(np.exp(yy)),
        } for tk, yy in zip(T, y)]
        ad._sample_id = "ATP-R0.186-N1.029-epistemic-verify"
        ad._run_id = None
        ad._enable_epistemic = True
        events = []
        ad._emit_event = lambda et, pl=None, *a, **k: events.append((et, pl or {}))
        ad._run_epistemic("completed")
        done = [pl for et, pl in events if et == "EPISTEMIC_CERTIFICATE_COMPLETED"]
        errs = [pl for et, pl in events if et in ("EPISTEMIC_ERROR", "EPISTEMIC_UNAVAILABLE", "EPISTEMIC_SKIPPED")]
        check("接线:生产方法发 EPISTEMIC_CERTIFICATE_COMPLETED(无 error)",
              len(done) == 1 and not errs, f"done={len(done)} errs={errs}")
        if done:
            s = done[0]
            check("接线:summary 含三对象关键产出",
                  ("equivalence_classes" in s and "min_set_status" in s
                   and "anytime_valid_ok" in s),
                  f"aic_best={s.get('aic_best_model')} min_set={s.get('min_set_status')} "
                  f"anytime_valid={s.get('anytime_valid_ok')} crossed={s.get('eprocess_crossed')}")
    except Exception as exc:
        check("接线:生产方法可调用", False, f"exc={exc}")

    # ---- 汇总 ----
    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 72)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   产物→ _new_data_analysis/epistemic_out/")
    print("=" * 72)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
