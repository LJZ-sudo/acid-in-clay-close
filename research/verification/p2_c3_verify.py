# -*- coding: utf-8 -*-
"""P2 验证:C³-Harness shadow 在 legacy "扫完即停" 之上,喂**真实** Rb-ACT 计量不确定度
(逐点 sigma_log10_total,从真机谱重算)+ 复现地板(单片 → required 3 未满)→ 出收敛证书。

核验不变量与价值:
  - consistent_with_legacy == True(C³ 的"停" ⊆ legacy 的"停",绝不更早停);
  - legacy 想停(loop_can_end)而复现地板未满 → delta == "c3_defers_stop"(C³ 推迟,真有价值);
  - recommended_action != STOP(因复现/计量未解决);
  - 证书携带真实 metrological_uncertainty_dex(median/max)与主动测量请求。

用法: python p2_c3_verify.py [--chi_data_dir DIR] [--thickness T] [--area A]
默认谱目录 = E:\\chi_data\\p3_fulltemp_fe2(前端驱动全温区 genuine live 谱)。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN / "stage0_measurement"))
sys.path.insert(0, str(MAIN / "stage1_optimization"))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from rb_act import analyze_spectrum, ABSTAIN  # noqa: E402
from scientific_convergence import shadow_convergence  # noqa: E402

import re  # noqa: E402
_T_RE = re.compile(r"_T(-?\d+(?:[.p]\d+)?)_")


def _temp_from_name(name):
    m = _T_RE.search(name)
    return float(m.group(1).replace("p", ".")) if m else None


def collect_metro(chi_dir, thickness, area):
    """逐谱重算 Rb-ACT 后验,取真实 sigma_log10_total(dex)+ 主动测量请求。"""
    metro, acts, n = [], [], 0
    for fp in sorted(Path(chi_dir).glob("*.txt")):
        if _temp_from_name(fp.name) is None:
            continue
        parsed = parse_chi_file(str(fp))
        if not parsed.get("success"):
            continue
        r = analyze_spectrum(parsed["frequencies"], parsed["z_real"], parsed["z_imag"],
                             thickness_cm=thickness, area_cm2=area)
        post = getattr(r, "posterior", None)
        u = getattr(post, "sigma_log10_total", None) if post else None
        if isinstance(u, (int, float)) and not math.isnan(u):
            metro.append(float(u))
        for a in (getattr(r, "active_requests", None) or []):
            act = str(getattr(a, "action", a))
            if act not in acts:
                acts.append(act)
        n += 1
    return metro, acts, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi_data_dir", default=r"E:\chi_data\p3_fulltemp_fe2")
    ap.add_argument("--thickness", type=float, default=0.0564)
    ap.add_argument("--area", type=float, default=1.96)
    args = ap.parse_args()

    print(f"== P2 C3-Harness shadow verify  dir={args.chi_data_dir} ==")
    metro, acts, n = collect_metro(args.chi_data_dir, args.thickness, args.area)
    if not metro:
        print(f"未从 {args.chi_data_dir} 重算到任何 Rb-ACT 计量不确定度;先确认谱目录。")
        return 1
    metro_sorted = sorted(metro)
    metro_med = float(np.median(metro_sorted))
    metro_max = float(metro_sorted[-1])
    print(f"recomputed Rb-ACT points: {n}  metro_dex median={metro_med:.4f} max={metro_max:.4f}")
    print(f"active_requests(union): {acts}")

    # legacy:全温区扫描完成 → loop_can_end(legacy 想停)
    termination = {"verdict": "loop_can_end", "triggered_by": ["stage0_sweep_complete"],
                   "convergence": {}, "progress": {}, "budget": {}}
    cert = shadow_convergence(
        termination,
        metrological_uncertainty_dex=metro_med,
        repro_replicates_have=1,
        repro_replicates_required=3,
        claim_stability=1.0,
        rb_act_active_requests=acts,
    )
    d = cert.to_dict()
    print(f"legacy_stop={d['legacy_stop']}  c3_stop={d['c3_stop']}  "
          f"delta={d['delta_vs_legacy']}  recommended={d['recommended_action']}")
    print(f"reasons: {d['reasons']}")
    print(f"state: repro_unmet={d['state']['reproducibility_unmet']:.3f} "
          f"metro={d['state']['metrological_uncertainty']:.3f} unresolved={d['state']['unresolved']:.3f}")
    print(f"top3 actions: {[u['action'] for u in d['portfolio'][:3]]}")

    checks = {
        "consistent_with_legacy": d["consistent_with_legacy"] is True,
        "legacy_wanted_stop": d["legacy_stop"] is True,
        "c3_defers_stop": d["delta_vs_legacy"] == "c3_defers_stop",
        "recommended_not_STOP": d["recommended_action"] != "STOP",
        "repro_floor_unmet": d["state"]["reproducibility_unmet"] > 0.0,
        "real_metro_present": metro_med >= 0.0 and n > 0,
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
