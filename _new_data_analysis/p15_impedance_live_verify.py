# -*- coding: utf-8 -*-
"""P15 验证(P13-A):阻抗级正问题**接进 live 收尾**——驱动生产方法本身。

与 p11 的区别:p11 只验证 `epistemic.impedance_models` 离线模块;本脚本验证
**`hardware_adapter._run_epistemic_impedance`(真正接进 finalize 的生产代码)**在
真机 EIS 谱上端到端跑通、落 `epistemic/impedance_summary.json`、发 `EPISTEMIC_IMPEDANCE`。

做法(不连硬件、不改 legacy):
  1. 从真机 genuine-live run 的 evidence/EP-*.json 读真实谱(freq/z_real/z_imag,84 频点),
     其结构与生产内存 `_measurements` 逐字段一致;
  2. `HardwareAdapter.__new__` 绕过 __init__(不连硬件),只注入本方法读取的 4 个属性
     (_enable_epistemic / _measurements / _run_id / _emit_event 捕获器);
  3. 调用**生产方法** `_run_epistemic_impedance("completed")`;
  4. 断言:事件真发、产物真落盘、被动性/拟合优度/λ_min 在真谱上成立、
     最冷端偏好多弧/电极阻塞、体相 R 与独立 rb 提取趋势一致(诚实弱可辨识)。
无谱数据则 SKIP,不谎报。

用法: python p15_impedance_live_verify.py [run_id]
默认 run = run_20260630_135646_f33d5e(带 LLM 创新点全温区真机长跑)。
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
NDA = HERE.parent
MAIN = NDA.parent / "V1.0-qianduan-mainline"
EVID = MAIN / "runs" / RUN_ID / "evidence"

# 让生产模块可导入(backend_api 包)+ epistemic 可解析。
if str(MAIN) not in sys.path:
    sys.path.insert(0, str(MAIN))
if str(NDA) not in sys.path:
    sys.path.insert(0, str(NDA))

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_measurements(run_id):
    """从 evidence/EP-*.json 读真机谱,构造与生产 `_measurements` 同构的 dict 列表。"""
    out = []
    if not EVID.exists():
        return out
    for fp in sorted(EVID.glob("EP-*.json")):
        d = json.loads(fp.read_text(encoding="utf-8")).get("payload", {})
        f = d.get("frequencies"); zr = d.get("z_real"); zi = d.get("z_imag")
        if not (f and zr and zi) or len(f) < 10:
            continue
        out.append({
            "success": bool(d.get("success")),
            "temperature_C": d.get("temperature_C"),
            "temperature_K": d.get("temperature_K"),
            "rb_ohm": d.get("rb_ohm"),
            "conductivity_S_cm": d.get("conductivity_S_cm"),
            "qc_grade": d.get("qc_grade"),
            "frequencies": f, "z_real": zr, "z_imag": zi,
        })
    return out


def main():
    print("=" * 74)
    print("P15:阻抗级正问题接 live 收尾 —— 驱动生产方法 _run_epistemic_impedance")
    print("=" * 74)

    meas = load_measurements(RUN_ID)
    real = [m for m in meas if m["success"]]
    if len(real) < 5:
        print(f"[SKIP] 真实谱不足({len(real)}),跳过(不谎报)")
        return 0
    print(f"run={RUN_ID}  真机谱 n={len(real)}  "
          f"T∈[{min(m['temperature_C'] for m in real):.1f},"
          f"{max(m['temperature_C'] for m in real):.1f}]°C  每谱频点≈{len(real[0]['frequencies'])}")

    # --- 导入生产模块 + 用 __new__ 绕过 __init__(不连硬件)---
    from backend_api.services import hardware_adapter as HA  # noqa: E402
    adapter = HA.HardwareAdapter.__new__(HA.HardwareAdapter)
    adapter._enable_epistemic = True
    adapter._measurements = meas
    adapter._run_id = None   # → 写 outputs/epistemic_live_tmp(不污染真实 run 目录)

    captured = []
    adapter._emit_event = lambda etype, payload=None: captured.append((etype, payload or {}))

    # --- 调用生产方法本身 ---
    adapter._run_epistemic_impedance("completed")

    ev = {t: p for (t, p) in captured}
    check("生产方法发出 EPISTEMIC_IMPEDANCE 事件(未 UNAVAILABLE/SKIPPED/ERROR)",
          "EPISTEMIC_IMPEDANCE" in ev,
          f"events={sorted(ev.keys())}")
    if "EPISTEMIC_IMPEDANCE" not in ev:
        # 出错时打印原因帮助定位
        for t, p in captured:
            print(f"    emitted {t}: {p}")
        n_fail = 1
    else:
        summ = ev["EPISTEMIC_IMPEDANCE"]
        # 产物落盘(生产路径:_run_id=None → outputs/epistemic_live_tmp)
        out_json = Path(summ.get("output_dir", "")) / "impedance_summary.json"
        check("生产产物 impedance_summary.json 真实落盘", out_json.exists(), str(out_json))

        detail = json.loads(out_json.read_text(encoding="utf-8")) if out_json.exists() else {}
        n = summ.get("n_spectra", 0)
        check("谱级机制辨识覆盖真机谱(n>=5)", n >= 5, f"n_spectra={n}")
        check("物理静态检查:被动性 Re Z>0 成立(>=80% 谱)",
              summ.get("n_passive", 0) >= 0.8 * n, f"{summ.get('n_passive')}/{n}")
        check("拟合优度合格(加权残差 RMS<0.35,>=80% 谱)",
              summ.get("n_goodfit_wrms_lt_0p35", 0) >= 0.8 * n,
              f"{summ.get('n_goodfit_wrms_lt_0p35')}/{n}")
        check("方案一(谱级):Fisher λ_min 参数可观测性给出有限值(>=80% 谱)",
              summ.get("n_finite_lambda_min", 0) >= 0.8 * n,
              f"{summ.get('n_finite_lambda_min')}/{n}")
        check("机制谱级判别:偏好随温度真实演化(非恒定单一机制)",
              len(summ.get("distinct_mechanisms", [])) >= 2,
              f"distinct={summ.get('distinct_mechanisms')}")
        check("机制谱级判别:最冷3点(穿相变后)偏好多弧/电极阻塞结构",
              summ.get("cold_prefers_multi_arc") is True,
              f"cold3={summ.get('cold3_best_mechanisms')}")
        # 诚实:绝对体相 R 在电极阻塞下弱可辨识,故不强求逐点秩相关达高值,
        # 只如实报告 ρ 方向一致;谱级稳健可辨识的是冷/暖端体相 R 量级差(相变致阻抗上升)。
        rho = summ.get("bulkR_vs_measured_spearman_rho")
        check("体相R 与独立 rb 提取 方向一致(Spearman ρ>0;绝对量级弱可辨识—真实观测性发现,如实报告)",
              rho is not None and rho > 0.0, f"ρ={rho}")
        check("谱级稳健可辨识:冷端(T<-40)体相R 中位 ≫ 暖端(T>-10)中位(相变致总阻抗上升)",
              summ.get("cold_bulkR_gt_warm") is True,
              f"warm_med={summ.get('bulkR_median_warm'):.3g} cold_med={summ.get('bulkR_median_cold'):.3g}"
              if summ.get('bulkR_median_warm') and summ.get('bulkR_median_cold') else
              f"warm={summ.get('bulkR_median_warm')} cold={summ.get('bulkR_median_cold')}")

        print("\n  逐温机制偏好(收尾产物,间隔抽样):")
        fits = detail.get("fits", [])
        for r in fits[::max(1, len(fits) // 9)]:
            ws = " ".join(f"{k}={v}" for k, v in (r.get("aic_weights") or {}).items() if v)
            print(f"    T={r['T_C']:6.1f}°C best={r['best_mechanism']:14s} "
                  f"R_bulk={r['best_bulk_R']:9.3g} rb_meas={r['rb_measured']:9.3g} "
                  f"wrms={r['best_wrms']:.3f} [{ws}]")

        n_fail = sum(1 for _, s, _ in results if s == FAIL)

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   "
          f"(生产方法 hardware_adapter._run_epistemic_impedance 真机谱端到端)")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
