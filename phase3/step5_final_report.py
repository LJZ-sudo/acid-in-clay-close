# -*- coding: utf-8 -*-
"""
Phase 3 Step 5：生成 Phase 3 汇总报告

汇总 step1–step4 的结果，输出 phase3_final_report.md（仅基于 close 内数据与输出）。
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import json

CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE3_RESULTS_DIR = CLOSE_ROOT / "output" / "phase3_results"
MODELS_DIR = PHASE3_RESULTS_DIR / "models"
CONFINEMENT_DIR = PHASE3_RESULTS_DIR / "confinement"


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("Phase 3 Step 5：生成汇总报告")
    print("=" * 60)

    lines = []
    lines.append("# Phase 3 汇总报告（close 内闭环）")
    lines.append("")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("**数据来源**: close/output/phase1_results")
    lines.append("**输出目录**: close/output/phase3_results")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. 数据与模型
    lines.append("## 1. 数据与模型概览")
    lines.append("")
    if (PHASE3_RESULTS_DIR / "integrated_data.csv").exists():
        import pandas as pd
        df = pd.read_csv(PHASE3_RESULTS_DIR / "integrated_data.csv")
        lines.append(f"- 共 **{len(df)}** 个 segment，来自 **{df['sample_id'].nunique()}** 个样品")
        for mat in sorted(df["material_type"].unique()):
            n = len(df[df["material_type"] == mat])
            lines.append(f"  - {mat}: {n} segments")
    else:
        lines.append("- 未找到 integrated_data.csv，请先运行 step1。")
    lines.append("")

    metrics_path = MODELS_DIR / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
        lines.append("### 模型指标")
        lines.append("")
        if metrics.get("s60"):
            m = metrics["s60"]
            lines.append(f"- **S60 基准模型**: R²={m.get('r2', 0):.4f}, CV R²={m.get('cv_r2_mean', 0):.4f}±{m.get('cv_r2_std', 0):.4f}, MAE={m.get('mae_eV', 0):.4f} eV, n={m.get('n', 0)}, 剔除异常值={m.get('n_removed_outliers', 0)}")
        if metrics.get("s8"):
            m = metrics["s8"]
            lines.append(f"- **S8 限域模型**: R²={m.get('r2', 0):.4f}, CV R²={m.get('cv_r2_mean', 0):.4f}, n={m.get('n', 0)}")
        if metrics.get("delta_Ea"):
            d = metrics["delta_Ea"]
            lines.append(f"- **ΔEa 统计**: mean={d['mean']:.4f} eV, std={d['std']:.4f} eV, 范围=[{d['min']:.4f}, {d['max']:.4f}] eV")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 2. 限域效应
    lines.append("## 2. 限域效应 ΔEa")
    lines.append("")
    summary_path = CONFINEMENT_DIR / "summary.json"
    if summary_path.exists():
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        o = summary.get("overall", {})
        ci = f", 95%CI=[{o.get('ci_95_low')}, {o.get('ci_95_high')}]" if o.get("ci_95_low") is not None else ""
        lines.append(f"- 整体: mean ΔEa = **{o.get('mean', 0):.4f}** eV, std = {o.get('std', 0):.4f} eV{ci}")
        if summary.get("low_T_under_230K"):
            lt = summary["low_T_under_230K"]
            ci_lt = f", 95%CI=[{lt.get('ci_95_low')}, {lt.get('ci_95_high')}]" if lt.get("ci_95_low") is not None else ""
            lines.append(f"- 低温 (<230K): mean ΔEa = {lt['mean']:.4f} eV, n={lt.get('n', 0)}{ci_lt}")
        if summary.get("high_T_over_270K"):
            ht = summary["high_T_over_270K"]
            ci_ht = f", 95%CI=[{ht.get('ci_95_low')}, {ht.get('ci_95_high')}]" if ht.get("ci_95_low") is not None else ""
            lines.append(f"- 高温 (>270K): mean ΔEa = {ht['mean']:.4f} eV, n={ht.get('n', 0)}{ci_ht}")
        if summary.get("low_vs_high_T_ttest"):
            t = summary["low_vs_high_T_ttest"]
            lines.append(f"- 低温 vs 高温 ΔEa: t={t.get('t_statistic', 0):.3f}, p={t.get('p_value', 0):.4f}, 显著(p<0.05)={t.get('significant_005', False)}")
        if summary.get("delta_Ea_vs_T_linear_fit"):
            fit = summary["delta_Ea_vs_T_linear_fit"]
            lines.append(f"- ΔEa(T) 线性: slope={fit.get('slope_per_K', 0):.6f} eV/K, slope_95%CI={fit.get('slope_ci_95', [None, None])}")
        lines.append("")
        lines.append("图表: `output/phase3_results/confinement/delta_ea_plot.png`")
    else:
        lines.append("- 未找到限域分析结果，请先运行 step3。")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 3. ML-AI 验证
    lines.append("## 3. ML 与 AI 报告对照")
    lines.append("")
    val_path = PHASE3_RESULTS_DIR / "ml_ai_validation.json"
    if val_path.exists():
        with open(val_path, "r", encoding="utf-8") as f:
            val = json.load(f)
        lines.append("（方案 B：区间内 vs 区间外 mean(Ea) 对照）")
        lines.append("")
        for zone, v in val.get("validation", {}).items():
            if v.get("verdict") == "SKIP":
                lines.append(f"- **{zone}**: {v.get('reason', '—')}")
            else:
                d = v.get("diff_ci_95") or [None, None]
                d0 = f"{d[0]:.4f}" if d[0] is not None else "—"
                d1 = f"{d[1]:.4f}" if d[1] is not None else "—"
                lines.append(f"- **{zone}**: 区间内 mean(Ea)={v.get('mean_Ea_in_range', 0):.4f} (n={v.get('n_in', 0)}), 区间外 mean(Ea)={v.get('mean_Ea_out_range', 0):.4f} (n={v.get('n_out', 0)}), diff_95%CI=[{d0}, {d1}], p={v.get('p_value', 0):.4f} -> **{v.get('verdict')}**")
    else:
        lines.append("- 未找到 ml_ai_validation.json，请先运行 step4。")
    lines.append("")
    lines.append("---")
    lines.append("")
    # Meyer-Neldel
    lines.append("## 4. Meyer-Neldel 分析")
    lines.append("")
    mn_path = PHASE3_RESULTS_DIR / "meyer_neldel" / "summary.json"
    if mn_path.exists():
        with open(mn_path, "r", encoding="utf-8") as f:
            mn = json.load(f)
        for key, r in mn.items():
            if r.get("E_MN_eV") is not None:
                lines.append(f"- **{key}**: E_MN = {r['E_MN_eV']:.3f} eV, R² = {r.get('r_squared', 0):.4f}, p = {r.get('p_value', 0):.4f}, n = {r.get('n_points', 0)}")
        lines.append("")
        lines.append("图表: `output/phase3_results/meyer_neldel/meyer_neldel_s8.png`")
    else:
        lines.append("- 未找到 Meyer-Neldel 结果，请先运行 step_meyer_neldel.py。")
    lines.append("")
    lines.append("---")
    lines.append("")
    # 5. 跨材料验证（P2）
    lines.append("## 5. 跨材料验证（S8 模型迁移）")
    lines.append("")
    cross_path = PHASE3_RESULTS_DIR / "cross_material" / "summary.json"
    if cross_path.exists():
        with open(cross_path, "r", encoding="utf-8") as f:
            cross = json.load(f)
        for mat, r in cross.get("materials", {}).items():
            lines.append(f"- **{mat}**: n={r.get('n', 0)}, mean(α)={r.get('mean_alpha', 0):.4f}, std(α)={r.get('std_alpha', 0):.4f}, MAE={r.get('mae_eV', 0):.4f} eV")
        if cross.get("overall"):
            o = cross["overall"]
            lines.append(f"- 整体: n_segments={o.get('n_segments', 0)}, mean_alpha(加权)={o.get('mean_alpha_weighted', 0):.4f}")
        lines.append("")
        lines.append("明细: `output/phase3_results/cross_material/cross_material_details.csv`")
    else:
        lines.append("- 未找到跨材料验证结果，请先运行 step6_cross_material.py。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. 输出文件一览")
    lines.append("")
    lines.append("| 文件 | 说明 |")
    lines.append("|------|------|")
    lines.append("| `phase3_results/integrated_data.csv` | segment 级数据 |")
    lines.append("| `phase3_results/models/s60_baseline.pkl` | S60 模型 |")
    lines.append("| `phase3_results/models/s8_confinement.pkl` | S8 模型 |")
    lines.append("| `phase3_results/confinement/delta_ea_by_segment.csv` | ΔEa 明细 |")
    lines.append("| `phase3_results/confinement/delta_ea_plot.png` | ΔEa–T 图 |")
    lines.append("| `phase3_results/ml_ai_validation.json` | ML–AI 验证结果（区间对照） |")
    lines.append("| `phase3_results/meyer_neldel/summary.json` | Meyer-Neldel 分析 |")
    lines.append("| `phase3_results/meyer_neldel/meyer_neldel_s8.png` | ln(σ₀)–Ea 图 |")
    lines.append("| `phase3_results/cross_material/summary.json` | 跨材料验证（α=Ea_实际/Ea_预测） |")
    lines.append("| `phase3_results/cross_material/cross_material_details.csv` | 跨材料明细 |")
    lines.append("")

    out_md = PHASE3_RESULTS_DIR / "phase3_final_report.md"
    PHASE3_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  已写入 {out_md}")

    print("\n[Step 5 完成]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
