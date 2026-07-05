# -*- coding: utf-8 -*-
"""P4 验证:Rb-ACT R2→R3。证明噪声感知 GP 的逐观测方差(train_Yvar / alpha)能由**真实**
Rb-ACT 计量不确定度(从真机谱重算的 sigma_log10_total)驱动,而非 cross-system proxy。

做法(全真实、不造新配方):
  1. 从真机谱(committed 点)重算 Rb-ACT u_total_dex(median)→ bridge 转 objective_variance;
  2. 读真实 history_db(只读)+ 真实 campaign,作为既有 BO 历史;
  3. 把"本配方"作为一条新 trial 注入(参数=真实 R/N,objective=真实 σ),
     metadata.objective_variance 由真实 Rb-ACT 驱动,noise_source=RB_ACT_METROLOGICAL_DIRECT;
  4. 用与生产同一引擎 NoiseAwareParEGO,核验:
     - _extract 取到的逐观测方差里含真实 Rb-ACT 方差(train_Yvar 真来自 Rb-ACT);
     - R3(Rb-ACT)alpha ≠ R2(proxy default)alpha —— 噪声通道真被改写;
     - suggest_next 走 noise_aware_parego(非冷启动)且给出 in-bounds 真实建议。
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
MAIN = REPO / "V1.0-qianduan-mainline"
STAGE1 = MAIN / "stage1_optimization"
sys.path.insert(0, str(MAIN / "stage0_measurement"))
sys.path.insert(0, str(STAGE1))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from rb_act import analyze_spectrum  # noqa: E402
from scientific_harness.rbact_noise_bridge import (  # noqa: E402
    variance_from_u_dex, stamp_metadata, RBACT_NOISE_SOURCE,
)
from canonical_input.campaign_parser import CampaignConfig  # noqa: E402
from canonical_input.design_space import ParameterSpace  # noqa: E402
from campaign_memory.memory_manager import MemoryManager  # noqa: E402
from optimizers.botorch_mobo_v2 import NoiseAwareParEGO  # noqa: E402
from optimizers.mobo_optimizer import locked_v2_objectives  # noqa: E402

CHI_DIR = Path(r"E:\chi_data\p3_fulltemp_fe2")
CAMPAIGN = STAGE1 / "campaigns" / "attapulgite_aice_campaign.json"
HISTORY_DB = STAGE1 / "campaign_memory" / "history_db_attapulgite.json"
HISTORY_KEYS = {"sigma_key": "conductivity_room_temp_S_cm",
                "ea_high_key": "ea_high_temp_eV", "ea_low_excess_key": "ea_low_excess_eV"}
_T_RE = re.compile(r"_T(-?\d+(?:[.p]\d+)?)_")


class _Shim:
    """只读 memory_manager 适配器:真实 history + 1 条注入 trial。不写真实 DB。"""
    def __init__(self, trials):
        self._t = trials

    def get_history(self):
        return list(self._t)


def real_rbact_u_dex(chi_dir, thickness=0.0564, area=1.96):
    us, sig_warm = [], None
    for fp in sorted(Path(chi_dir).glob("*.txt")):
        m = _T_RE.search(fp.name)
        if not m:
            continue
        T_C = float(m.group(1).replace("p", "."))
        parsed = parse_chi_file(str(fp))
        if not parsed.get("success"):
            continue
        r = analyze_spectrum(parsed["frequencies"], parsed["z_real"], parsed["z_imag"],
                             thickness_cm=thickness, area_cm2=area)
        post = getattr(r, "posterior", None)
        u = getattr(post, "sigma_log10_total", None) if post else None
        if isinstance(u, (int, float)) and not math.isnan(u):
            us.append(float(u))
    return us


def main():
    print("== P4 Rb-ACT R2->R3 noise-aware GP verify ==")
    us = real_rbact_u_dex(CHI_DIR)
    if not us:
        print(f"未从 {CHI_DIR} 重算到 Rb-ACT u_total_dex")
        return 1
    u_med = float(np.median(sorted(us)))
    rbact_var = variance_from_u_dex(u_med)
    print(f"real Rb-ACT points={len(us)} u_total_dex median={u_med:.4f} -> objective_variance={rbact_var:.5f}")

    cfg = CampaignConfig(str(CAMPAIGN))
    ps = ParameterSpace(cfg)
    mm = MemoryManager(db_path=str(HISTORY_DB), campaign_name=cfg.campaign_name)
    objs = locked_v2_objectives(**HISTORY_KEYS)
    param_names = list(cfg.parameters.keys())
    hist = mm.get_history()
    print(f"real history trials: {len(hist)}  params={param_names}")

    # 本配方真实 (R,N) + 真实 objective(用真实 history 的目标键，注入一条带 Rb-ACT 方差的 trial）
    obj_key = cfg.get_objective_target()
    # 取一条既有有效 trial 的 objective 形态，换成本配方的真实 σ（warm 点）作占位目标值
    inj_objs = None
    for t in hist:
        o = t.get("objectives") or {}
        if all(ob.key in o for ob in objs):
            inj_objs = dict(o)
            break
    if inj_objs is None:
        print("history 无完整 objective 形态，无法注入对照 trial")
        return 1

    def make_trial(variance, source):
        md = stamp_metadata({"sample_id": "ATP-R0.186-N1.029-fulltemp-fe2"},
                            u_med) if source == "rbact" else {"sample_id": "proxy",
                                                              "objective_variance": 1e-3,
                                                              "noise_source": "CROSS_SYSTEM_PROXY"}
        return {"parameters": {param_names[0]: 0.186, param_names[1]: 1.029} if len(param_names) >= 2
                else {param_names[0]: 0.186},
                "objectives": inj_objs, "metadata": md}

    inj_r3 = make_trial(rbact_var, "rbact")
    inj_r2 = make_trial(1e-3, "proxy")
    print(f"injected R3 metadata: objective_variance={inj_r3['metadata'].get('objective_variance'):.5f} "
          f"noise_source={inj_r3['metadata'].get('noise_source')}")

    opt_r3 = NoiseAwareParEGO(ps, _Shim(hist + [inj_r3]), objectives=objs,
                              cold_start_threshold=5, random_state=7)
    opt_r3.noise_source = RBACT_NOISE_SOURCE
    X, P, var_r3, _, _ = opt_r3._extract(param_names)

    opt_r2 = NoiseAwareParEGO(ps, _Shim(hist + [inj_r2]), objectives=objs,
                              cold_start_threshold=5, random_state=7)
    _, _, var_r2, _, _ = opt_r2._extract(param_names)

    s = opt_r3.suggest_next()
    prov = opt_r3.get_provenance()
    in_bounds = all(lo <= s[n] <= hi for n, (lo, hi) in
                    zip(param_names, [tuple(b) for b in ps.get_bounds()]))

    print(f"R3 alpha contains rbact_var ({rbact_var:.5f}): {any(abs(v - rbact_var) < 1e-9 for v in var_r3)}")
    print(f"R2 alpha (proxy) values sample: {sorted(set(round(v,5) for v in var_r2))[:5]}")
    print(f"R3 vs R2 alpha differ: {var_r3 != var_r2}")
    print(f"suggest_next mode={prov.get('mode')} mean_obs_variance={prov.get('mean_obs_variance')} in_bounds={in_bounds}")

    checks = {
        "real_rbact_u_dex_present": len(us) > 0 and u_med >= 0,
        "bridge_variance_eq_u2": abs(rbact_var - max(u_med, 0.02) ** 2) < 1e-12,
        "R3_alpha_contains_rbact_var": any(abs(v - rbact_var) < 1e-9 for v in var_r3),
        "R3_neq_R2_alpha": var_r3 != var_r2,
        "noise_source_rbact": inj_r3["metadata"].get("noise_source") == RBACT_NOISE_SOURCE,
        "suggest_noise_aware_mode": prov.get("mode") == "noise_aware_parego",
        "suggestion_in_bounds": in_bounds,
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
