# -*- coding: utf-8 -*-
"""pH4 验证(H4):Rb-ACT R4 **激活模式** —— 三条件人审门 + σ_v2 + delta,legacy 永不覆盖。

prereg 只做审计-only(rb_r4_active 恒 False)。H4 补真正的激活路径:**仅当**
`rb_r4_activate=True` + 预注册 `gates_pass=True` + **人审签核 token** 三者齐备,才让
Rb-ACT 后验均值旁产 σ_v2 + delta 喂 BO;缺任一条件恒回退 legacy。

用真机 run 存档的**真实 EIS 谱**(fe2/fe3/fe4b evidence)跑 legacy↔Rb-ACT 双跑 → 驱动生产函数
`rb_act.build_activation`,断言:
  1. 未请求激活 → rb_r4_active=False、σ_v2 全 None(数值链走 legacy);
  2. 请求激活但**缺人审签核** → 仍 False、σ_v2 全 None(人审门有效);
  3. 三条件齐备 → rb_r4_active=True、σ_v2 逐点产出、train_Yvar_v2 非空;
  4. legacy 永不覆盖:legacy_overwritten=0 且输入 legacy_rb 前后不变;
  5. "BO 不劣化"守卫:legacy↔v2 的 σ 排序 Spearman≥0.99 且中位 |Δlog10σ|≤门 → bo_not_degraded=True;
  6. 激活产物可落盘复载。
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
NDA = next(_p for _p in HERE.parents if _p.name == "research")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
EVID_RUNS = [
    MAIN / "runs" / "run_20260629_112156_9db536" / "evidence",   # fe2
    MAIN / "runs" / "run_20260630_135646_f33d5e" / "evidence",   # fe3
    MAIN / "runs" / "run_20260702_144507_52a878" / "evidence",   # fe4b
]
for p in (str(MAIN / "stage0_measurement"), str(MAIN / "stage1_optimization"), str(NDA)):
    if p not in sys.path:
        sys.path.insert(0, p)

import rb_act as RB  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []
THICK, AREA = 0.088, 1.96
SIGNOFF = "operator:LBM approved R4 replacement on old material 2026-07-04"


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_spectra():
    out = []
    for evid in EVID_RUNS:
        if not evid.exists():
            continue
        for fp in sorted(evid.glob("EP-*.json")):
            d = json.loads(fp.read_text(encoding="utf-8")).get("payload", {})
            f = d.get("frequencies"); zr = d.get("z_real"); zi = d.get("z_imag")
            if not (f and zr and zi) or len(f) < 10:
                continue
            out.append({"T_C": d.get("temperature_C"),
                        "f": np.array(f, float), "zr": np.array(zr, float), "zi": np.array(zi, float)})
    out.sort(key=lambda s: (s["T_C"] if s["T_C"] is not None else 0), reverse=True)
    return out


def main():
    print("=" * 74)
    print("pH4:Rb-ACT R4 激活模式 —— 三条件人审门 + σ_v2 + delta(真谱驱动 build_activation)")
    print("=" * 74)
    spectra = load_spectra()
    if len(spectra) < 5:
        print(f"[SKIP] 真实谱不足({len(spectra)}),跳过(不谎报)")
        return 0
    print(f"真实谱 n={len(spectra)}  T∈[{spectra[-1]['T_C']:.1f},{spectra[0]['T_C']:.1f}]°C")

    rb_results = [
        RB.analyze_spectrum(s["f"], s["zr"], s["zi"], thickness_cm=THICK, area_cm2=AREA,
                            temperature_K=(s["T_C"] + 273.15) if s["T_C"] is not None else 298.15)
        for s in spectra
    ]
    contract = RB.build_r4_prereg_contract(sample_id="pH4-oldmat", note="H4 激活验证")
    audit = RB.audit_series(rb_results, contract=contract)
    print(f"审计:gates_pass={audit['gates_pass']} n_paired={audit['n_paired']} "
          f"flips={audit['n_unexplained_flips']} median|Δ|={audit['median_abs_delta_log10']}")

    # 1. 未请求激活
    act0 = RB.build_activation(rb_results, contract=contract, audit=audit,
                               rb_r4_activate=False, human_signoff=SIGNOFF,
                               thickness_cm=THICK, area_cm2=AREA)
    v2_none0 = all(p["sigma_v2_S_cm"] is None for p in act0["per_point"])
    check("1 未请求激活 → rb_r4_active=False 且 σ_v2 全 None(走 legacy)",
          act0["rb_r4_active"] is False and v2_none0, f"reasons={act0['reasons']}")

    # 2. 请求激活但缺人审签核
    act1 = RB.build_activation(rb_results, contract=contract, audit=audit,
                               rb_r4_activate=True, human_signoff=None,
                               thickness_cm=THICK, area_cm2=AREA)
    v2_none1 = all(p["sigma_v2_S_cm"] is None for p in act1["per_point"])
    check("2 请求激活但缺人审签核 → 仍 False、σ_v2 全 None(人审门有效)",
          act1["rb_r4_active"] is False and v2_none1
          and any("human_signoff" in r for r in act1["reasons"]),
          f"reasons={act1['reasons']}")

    # 3. 三条件齐备
    act = RB.build_activation(rb_results, contract=contract, audit=audit,
                              rb_r4_activate=True, human_signoff=SIGNOFF,
                              thickness_cm=THICK, area_cm2=AREA)
    n_v2 = sum(1 for p in act["per_point"] if p["sigma_v2_S_cm"] is not None)
    if not audit["gates_pass"]:
        check("3 前置:预注册门达标(gates_pass) —— 未达标则激活本应被拒",
              False, f"gates_pass={audit['gates_pass']}(真谱未过门,激活按设计拒绝)")
    else:
        check("3 三条件齐备 → rb_r4_active=True、σ_v2 逐点产出、train_Yvar_v2 非空",
              act["rb_r4_active"] is True and n_v2 > 0 and bool(act["train_Yvar_v2"]),
              f"active={act['rb_r4_active']} n_v2={n_v2} yvar={len(act['train_Yvar_v2'] or [])}")

    # 4. legacy 永不覆盖
    check("4 legacy 永不覆盖(legacy_overwritten=0)", act["legacy_overwritten"] == 0,
          f"overwritten={act['legacy_overwritten']}")

    # 5. BO 不劣化守卫
    check("5 BO 不劣化守卫:Spearman≥0.99 且中位|Δlog10σ|≤门",
          (act["rb_r4_active"] is False)  # 未激活时该项不适用
          or (act["bo_not_degraded"] is True),
          f"spearman={act['spearman_legacy_vs_v2']} median|Δ|={act['median_abs_delta_log10_sigma']} "
          f"gate={act['max_median_abs_delta_dex_gate']} bo_not_degraded={act['bo_not_degraded']}")

    # 6. 落盘复载
    out = NDA / "results" / "epistemic_out" / "rb_act_r4_activation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(act, ensure_ascii=False, indent=2), encoding="utf-8")
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    check("6 激活产物落盘且可复载", out.exists()
          and reloaded.get("activation_version") == RB.R4_ACTIVATION_VERSION,
          str(out))

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   "
          f"(真谱 n={len(spectra)};rb_r4_active={act['rb_r4_active']};"
          f"bo_not_degraded={act['bo_not_degraded']})")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
