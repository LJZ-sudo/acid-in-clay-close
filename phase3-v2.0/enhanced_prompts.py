# -*- coding: utf-8 -*-
"""
增强版深度分析 Prompt 构建器

在原有 Phase 2 prompt 基础上，注入 Phase 3 ML 定量结果，
包括限域效应量化、Meyer-Neldel 分析、模型性能、跨材料验证等。

Prompt 结构：
  1. 材料背景信息（知识库）
  2. 实验数据统计（Phase 1）
  3. Arrhenius 分析摘要
  4. **ML建模定量结果（Phase 3）** ← 新增
  5. 单样品报告摘要（Phase 2）
  6. 增强版分析任务
  7. 输出要求

版本: 2.0
日期: 2026-02-06
"""

import json
from typing import Dict, Any, List, Optional
import numpy as np


def build_enhanced_deep_analysis_prompt(
    material: str,
    phase1_data: List[Dict],
    phase2_reports: List[Dict],
    phase3_results: Dict[str, Any],
    knowledge: Dict[str, Any],
) -> str:
    """
    构建增强版深度分析 prompt

    Args:
        material:       材料ID（如 S8）
        phase1_data:    Phase 1 分析结果 JSON 列表
        phase2_reports: Phase 2 单样品机理报告列表
        phase3_results: Phase 3 v2.0 ML 结果（字典）
        knowledge:      材料知识库

    Returns:
        完整的增强版 prompt 字符串
    """
    sections = []

    # ==== 标题 ====
    sections.append(f"# {material} 材料增强版深度机理分析任务\n")
    sections.append("（本分析基于实验数据 + ML建模定量结果，请充分利用 ML 定量证据）\n")

    # ==== Section 1: 材料背景 ====
    sections.append(_build_knowledge_section(material, knowledge))

    # ==== Section 2: 数据统计 ====
    sections.append(_build_data_summary_section(material, phase1_data))

    # ==== Section 3: Arrhenius 摘要 ====
    sections.append(_build_arrhenius_section(phase1_data))

    # ==== Section 4: Phase 3 ML 结果 ★新增★ ====
    sections.append(_build_phase3_ml_section(phase3_results))

    # ==== Section 5: 单样品报告摘要 ====
    sections.append(_build_sample_reports_section(phase2_reports))

    # ==== Section 6: 增强版分析任务 ====
    sections.append(_build_enhanced_analysis_tasks(material))

    # ==== Section 7: 输出要求 ====
    sections.append(_build_output_requirements())

    return "\n".join(sections)


# ============================================================
# Section 1: 材料背景
# ============================================================

def _build_knowledge_section(material: str, knowledge: Dict) -> str:
    """构建知识库背景段落"""
    lines = ["---\n", "## 1. 背景信息\n"]

    clay_type = knowledge.get("clay_type", "Unknown")
    acid_type = knowledge.get("acid_type", "Unknown")
    clay_kb = knowledge.get("clay_knowledge", {})
    acid_kb = knowledge.get("acid_knowledge", {})

    lines.append(f"### 1.1 材料基本信息")
    lines.append(f"- **材料编号**: {material}")
    lines.append(f"- **黏土类型**: {clay_type} ({clay_kb.get('chinese_name', '')})")
    lines.append(f"- **酸体系**: {acid_type} ({acid_kb.get('chinese_name', '')})")

    if clay_kb:
        lines.append(f"\n### 1.2 {clay_type} 材料知识")
        lines.append(json.dumps(clay_kb, ensure_ascii=False, indent=2))

    if acid_kb:
        lines.append(f"\n### 1.3 {acid_type} 体系知识")
        lines.append(json.dumps(acid_kb, ensure_ascii=False, indent=2))

    # 质子传导机理
    proton_mech = knowledge.get("proton_mechanism", {})
    if proton_mech:
        lines.append("\n### 1.4 质子传导机理背景")
        lines.append(json.dumps(proton_mech, ensure_ascii=False, indent=2))

    # EIS 形态
    eis_morph = knowledge.get("eis_morphology", {})
    if eis_morph:
        lines.append("\n### 1.5 EIS曲线形态解释")
        lines.append(json.dumps(eis_morph, ensure_ascii=False, indent=2))

    # Arrhenius 分段
    arr_seg = knowledge.get("arrhenius_segmentation", {})
    if arr_seg:
        lines.append("\n### 1.6 Arrhenius分段解释")
        lines.append(json.dumps(arr_seg, ensure_ascii=False, indent=2))

    return "\n".join(lines)


# ============================================================
# Section 2: 数据统计摘要
# ============================================================

def _build_data_summary_section(material: str, phase1_data: List[Dict]) -> str:
    """构建 Phase 1 数据统计段落"""
    lines = ["---\n", "## 2. 实验数据统计摘要\n"]

    if not phase1_data:
        lines.append("（无 Phase 1 数据）")
        return "\n".join(lines)

    n_samples = len(phase1_data)
    R_vals = [d.get("R", 0) for d in phase1_data if d.get("R")]
    N_vals = [d.get("N", 0) for d in phase1_data if d.get("N")]
    all_temps = []
    all_sigmas = []
    all_Ea = []
    seg_count = {}

    for d in phase1_data:
        temps = d.get("temperatures", [])
        sigmas = d.get("conductivity_values", [])
        all_temps.extend([t for t in temps if t and t > 0])
        all_sigmas.extend([s for s in sigmas if s and s > 0])

        arr = d.get("arrhenius", {})
        segs = arr.get("segments", [])
        n_seg = len(segs)
        seg_count[n_seg] = seg_count.get(n_seg, 0) + 1
        for seg in segs:
            ea = seg.get("Ea_eV")
            if ea and ea > 0:
                all_Ea.append(ea)

    lines.append(f"- **材料**: {material}")
    lines.append(f"- **样品数量**: {n_samples}")
    if R_vals:
        lines.append(f"- **R 范围**: {min(R_vals):.3f} ~ {max(R_vals):.3f}")
    if N_vals:
        lines.append(f"- **N 范围**: {min(N_vals):.2f} ~ {max(N_vals):.2f}")
    if all_temps:
        lines.append(f"- **温度范围**: {min(all_temps):.1f} ~ {max(all_temps):.1f} K")
    if all_sigmas:
        lines.append(f"- **电导率范围**: {min(all_sigmas):.2e} ~ {max(all_sigmas):.2e} S/cm")
    if all_Ea:
        lines.append(f"- **Ea 范围**: {min(all_Ea):.3f} ~ {max(all_Ea):.3f} eV")

    # R-N 组合
    rn_combos = set()
    for d in phase1_data:
        r = d.get("R")
        n = d.get("N")
        if r and n:
            rn_combos.add((round(r, 3), round(n, 2)))
    lines.append(f"- **R-N 组合数**: {len(rn_combos)}")

    # 分段分布
    if seg_count:
        seg_str = ", ".join([f"{n}段: {c}个" for n, c in sorted(seg_count.items())])
        lines.append(f"- **分段数分布**: {seg_str}")

    # 性能排名
    ranking = []
    for d in phase1_data:
        sid = d.get("sample_id", "")
        temps = d.get("temperatures", [])
        sigmas = d.get("conductivity_values", [])
        for t, s in zip(temps, sigmas):
            if t and s and 293 <= t <= 303:
                ranking.append((sid, s, d.get("R", 0), d.get("N", 0)))
                break
    ranking.sort(key=lambda x: -x[1])

    if ranking:
        lines.append("\n### 性能排名（按室温电导率）")
        lines.append("| 排名 | 样品 | σ_RT (S/cm) | R | N |")
        lines.append("|------|------|-------------|---|---|")
        for i, (sid, sigma, r, n) in enumerate(ranking[:10], 1):
            lines.append(f"| {i} | {sid} | {sigma:.4e} | {r:.3f} | {n:.2f} |")

    return "\n".join(lines)


# ============================================================
# Section 3: Arrhenius 摘要
# ============================================================

def _build_arrhenius_section(phase1_data: List[Dict]) -> str:
    """构建 Arrhenius 分析摘要"""
    lines = ["---\n", "## 3. Arrhenius分析摘要\n"]

    all_segs = []
    for d in phase1_data:
        arr = d.get("arrhenius", {})
        for seg in arr.get("segments", []):
            temp_range = seg.get("temp_range_K") or seg.get("T_range_K", [0, 0])
            if isinstance(temp_range, (list, tuple)) and len(temp_range) >= 2:
                t_avg = np.mean(temp_range)
            else:
                t_avg = 0
            ea = seg.get("Ea_eV", 0)
            if ea > 0:
                all_segs.append({"T_avg_K": t_avg, "Ea_eV": ea})

    if not all_segs:
        lines.append("（无 Arrhenius 分段数据）")
        return "\n".join(lines)

    # 按温区分组
    high_T = [s["Ea_eV"] for s in all_segs if s["T_avg_K"] > 250]
    mid_T = [s["Ea_eV"] for s in all_segs if 200 <= s["T_avg_K"] <= 250]
    low_T = [s["Ea_eV"] for s in all_segs if s["T_avg_K"] < 200]

    lines.append("| 温区 | 典型 Ea (eV) | Segment数 |")
    lines.append("|------|-------------|-----------|")
    if high_T:
        lines.append(f"| >250K (高温) | {np.mean(high_T):.3f} | {len(high_T)} |")
    if mid_T:
        lines.append(f"| 200-250K (中温) | {np.mean(mid_T):.3f} | {len(mid_T)} |")
    if low_T:
        lines.append(f"| <200K (低温) | {np.mean(low_T):.3f} | {len(low_T)} |")

    all_Ea = [s["Ea_eV"] for s in all_segs]
    lines.append(f"\n- **总 Segment 数**: {len(all_segs)}")
    lines.append(f"- **Ea 平均值**: {np.mean(all_Ea):.3f} eV")
    lines.append(f"- **Ea 标准差**: {np.std(all_Ea):.3f} eV")

    return "\n".join(lines)


# ============================================================
# Section 4: Phase 3 ML 结果 ★核心新增★
# ============================================================

def _build_phase3_ml_section(phase3_results: Dict[str, Any]) -> str:
    """
    构建 Phase 3 ML 建模定量结果段落

    这是增强版 prompt 的核心新增内容
    """
    lines = [
        "---\n",
        "## 4. ML建模定量分析结果（Phase 3 Agent 自动生成）\n",
        "**以下数据来自机器学习建模和统计分析，为机理推断提供定量支撑。"
        "请在分析中充分引用这些 ML 结果。**\n",
    ]

    if not phase3_results:
        lines.append("（Phase 3 ML 分析未执行或无结果）")
        return "\n".join(lines)

    # ---- 4.1 模型性能 ----
    metrics = phase3_results.get("model_metrics", {})
    if metrics:
        lines.append("### 4.1 预测模型性能\n")
        s60 = metrics.get("s60", {})
        s8 = metrics.get("s8", {})
        if s60:
            lines.append(f"- **S60 基准模型**（纯酸液，无限域效应）:")
            lines.append(f"  - 模型: Ea = f(R, T), Ridge 回归 + 二次多项式")
            lines.append(f"  - R² = {s60.get('r2', 0):.4f}, 5-fold CV R² = {s60.get('cv_r2_mean', 0):.4f} ± {s60.get('cv_r2_std', 0):.4f}")
            lines.append(f"  - MAE = {s60.get('mae_eV', 0):.4f} eV, 样品数 = {s60.get('n_samples', 0)}")
            lines.append("  - 物理意义：代表「无限域效应」时的 Ea 基线\n")
        if s8:
            lines.append(f"- **S8 限域模型**（海泡石限域）:")
            lines.append(f"  - 模型: Ea = f(R, N, T, T×N, T×R, R×N), 梯度提升回归")
            lines.append(f"  - R² = {s8.get('r2', 0):.4f}, 5-fold CV R² = {s8.get('cv_r2_mean', 0):.4f}")
            lines.append(f"  - 样品数 = {s8.get('n_samples', 0)}")
            lines.append(f"  - 物理意义：捕捉限域条件下 Ea 的多因素依赖关系\n")

        delta = metrics.get("delta_Ea", {})
        if delta:
            lines.append(f"- **ΔEa 概览** (S8实际 - S60预测):")
            lines.append(f"  - mean = {delta.get('mean', 0):.4f} eV, std = {delta.get('std', 0):.4f} eV")
            lines.append(f"  - range = [{delta.get('min', 0):.4f}, {delta.get('max', 0):.4f}] eV\n")

    # ---- 4.2 限域效应量化 ----
    conf = phase3_results.get("confinement", {})
    if conf:
        lines.append("### 4.2 限域效应定量分析 (ΔEa = Ea_S8实际 − Ea_S60预测)\n")
        lines.append("**核心发现：海泡石限域使 Ea 系统性升高，且低温效应显著强于高温。**\n")

        overall = conf.get("overall", {})
        if overall:
            ci_low = overall.get("ci_95_low")
            ci_high = overall.get("ci_95_high")
            ci_str = f"95%CI: [{ci_low:.4f}, {ci_high:.4f}]" if ci_low is not None else "CI 不可用"
            lines.append(f"- **整体 ΔEa**: {overall.get('mean', 0):.4f} ± {overall.get('std', 0):.4f} eV ({ci_str}, n={overall.get('n', 0)})")

        low_T = conf.get("low_T_under_230K", {})
        mid_T = conf.get("mid_T_230_270K", {})
        high_T = conf.get("high_T_over_270K", {})

        if low_T.get("mean") is not None:
            lines.append(f"- **低温 (<230K)**: ΔEa = {low_T['mean']:.4f} eV (n={low_T.get('n', 0)})")
        if mid_T.get("mean") is not None:
            lines.append(f"- **中温 (230-270K)**: ΔEa = {mid_T['mean']:.4f} eV (n={mid_T.get('n', 0)})")
        if high_T.get("mean") is not None:
            lines.append(f"- **高温 (>270K)**: ΔEa = {high_T['mean']:.4f} eV (n={high_T.get('n', 0)})")

        ttest = conf.get("low_vs_high_T_ttest", {})
        if ttest:
            sig = "显著" if ttest.get("significant_005") else "不显著"
            lines.append(f"- **低温 vs 高温差异检验**: t = {ttest.get('t_statistic', 0):.3f}, p = {ttest.get('p_value', 0):.6f} ({sig})")

        linear = conf.get("delta_Ea_vs_T_linear_fit", {})
        if linear:
            slope = linear.get("slope_per_K", 0)
            slope_ci = linear.get("slope_ci_95", [0, 0])
            lines.append(f"- **ΔEa(T) 线性趋势**: slope = {slope:.6f} eV/K (95%CI: [{slope_ci[0]:.6f}, {slope_ci[1]:.6f}])")
            lines.append(f"  - R² = {linear.get('r_squared', 0):.4f}")
            lines.append(f"  - 物理意义：限域效应随温度升高每 K 减少约 {abs(slope)*1000:.2f} meV\n")

    # ---- 4.3 Meyer-Neldel ----
    mn = phase3_results.get("meyer_neldel", {})
    if mn:
        lines.append("### 4.3 Meyer-Neldel 补偿效应\n")
        lines.append("**补偿规律: ln(σ₀) = a + Ea/E_MN, E_MN 为特征补偿能量**\n")

        lines.append("| 材料/温区 | E_MN (eV) | R² | p值 | n |")
        lines.append("|-----------|-----------|-----|------|---|")
        for key in ["S8", "S60", "S8_high_T", "S8_low_T"]:
            d = mn.get(key, {})
            if d and d.get("E_MN_eV") is not None:
                label = {"S8": "S8 全体", "S60": "S60 基线", "S8_high_T": "S8 高温(≥270K)", "S8_low_T": "S8 低温(<230K)"}.get(key, key)
                lines.append(f"| {label} | {d['E_MN_eV']:.4f} | {d.get('r_squared', 0):.4f} | {d.get('p_value', 0):.2e} | {d.get('n_points', 0)} |")

        lines.append("")
        # 解读
        s8_all = mn.get("S8", {})
        s8_high = mn.get("S8_high_T", {})
        s8_low = mn.get("S8_low_T", {})
        if s8_all and s8_high and s8_low:
            emn_all = s8_all.get("E_MN_eV", 0)
            emn_high = s8_high.get("E_MN_eV", 0)
            emn_low = s8_low.get("E_MN_eV", 0)
            if emn_all and emn_high and emn_low:
                lines.append(f"- **关键发现**: 高温 E_MN ({emn_high:.4f} eV) > 低温 E_MN ({emn_low:.4f} eV)")
                lines.append(f"  - 提示高温和低温可能有不同的传导机制/能量景观")
                lines.append(f"  - kT_room ≈ 0.026 eV ≈ E_MN(S8高温)，说明热涨落与补偿能量匹配\n")

    # ---- 4.4 跨材料验证 ----
    cross = phase3_results.get("cross_material", {})
    if cross:
        mats = cross.get("materials", {})
        if mats:
            lines.append("### 4.4 跨材料迁移验证 (α = Ea实际 / Ea_S8模型预测)\n")

            # Material identity mapping (from material_config.py)
            _MAT_IDENTITY = {
                "S8":  "Sepiolite + H₃PO₄ (primary, pore 0.5 nm)",
                "S14": "Halloysite + H₃PO₄ (tubular, pore ~15 nm)",
                "S16": "Bentonite + H₃PO₄ (layered, interlayer ~1.2 nm)",
                "S95": "Sepiolite + H₂SO₄ (same clay as S8, different acid)",
                "S96": "Bentonite + H₂SO₄ (layered + sulfuric acid)",
                "S97": "Halloysite + H₂SO₄ (tubular + sulfuric acid)",
                "S6":  "Sepiolite + Phytic acid (same clay as S8, multi-phosphate acid)",
                "S13": "Bentonite + Phytic acid (layered + multi-phosphate acid)",
                "S15": "Kaolin + Phytic acid (layered 1:1 type, pore ~0.7 nm)",
                "S12": "Pure water system (no acid, baseline)",
                "S60": "Pure H₃PO₄ liquid (no clay, bulk baseline)",
            }

            lines.append("**Material identity reference:**")
            for mat in sorted(mats.keys()):
                identity = _MAT_IDENTITY.get(mat, "Unknown composition")
                lines.append(f"- **{mat}**: {identity}")
            lines.append("")

            lines.append("| Material | Composition | n | α (mean±std) | MAE (eV) |")
            lines.append("|----------|-------------|---|--------------|----------|")
            for mat, data in sorted(mats.items()):
                identity = _MAT_IDENTITY.get(mat, "Unknown")
                # Short label for table
                short = identity.split("(")[0].strip() if "(" in identity else identity
                lines.append(f"| {mat} | {short} | {data.get('n', 0)} | {data.get('mean_alpha', 0):.3f} ± {data.get('std_alpha', 0):.3f} | {data.get('mae_eV', 0):.4f} |")
            overall = cross.get("overall", {})
            if overall.get("mean_alpha_weighted"):
                lines.append(f"\n- Overall weighted α = {overall['mean_alpha_weighted']:.3f} (α≈1 means S8 model transfers well)")
            lines.append("")
            lines.append("**Interpretation guide:**")
            lines.append("- α ≈ 1: Similar confinement to S8 → model transfers well")
            lines.append("- α < 1: Weaker confinement than S8 → lower Ea than predicted, possibly larger pores or weaker clay-acid interaction")
            lines.append("- α > 1: Stronger confinement than S8 → higher Ea than predicted, possibly different mechanism or stronger surface effects")
            lines.append("- Compare materials sharing the same clay (e.g., S8 vs S6 vs S95 — all Sepiolite) to isolate acid effects")
            lines.append("- Compare materials sharing the same acid (e.g., S8 vs S14 vs S16 — all H₃PO₄) to isolate clay structure effects\n")

    # ---- 4.5 对分析的指引 ----
    lines.append("### 4.5 ML结果对机理分析的指引\n")
    lines.append("请在后续分析中参考以上 ML 定量结果，特别是：")
    lines.append("1. **限域效应的温度依赖性**: ΔEa 在低温显著高于高温，说明限域对低温传导机制的影响更大")
    lines.append("2. **Meyer-Neldel 补偿能量**: E_MN 的温区差异暗示不同温度下的传导机制不同")
    lines.append("3. **模型预测能力**: S60→S8 的 ΔEa 量化了限域的额外能垒贡献")
    lines.append("4. **跨材料可比性**: α 值反映不同黏土-酸体系的限域特性差异\n")

    return "\n".join(lines)


# ============================================================
# Section 5: 单样品报告摘要
# ============================================================

def _build_sample_reports_section(reports: List[Dict]) -> str:
    """构建 Phase 2 单样品报告摘要"""
    lines = ["---\n", "## 5. 单样品机理报告摘要\n"]

    if not reports:
        lines.append("（无单样品报告数据）")
        return "\n".join(lines)

    lines.append(f"**共 {len(reports)} 个样品报告，以下展示前 20 个代表性样品：**\n")

    for r in reports[:20]:
        content = r.get("content", "")
        sample_id = r.get("sample_id", "unknown")

        # 提取关键发现（寻找 hypothesis/假设 段落）
        hypotheses = []
        in_hyp = False
        for line in content.split("\n"):
            if "hypothesis" in line.lower() or "假设" in line:
                in_hyp = True
            elif line.startswith("#") and in_hyp:
                in_hyp = False
            elif in_hyp and line.strip():
                hypotheses.append(line.strip()[:100])

        if hypotheses:
            lines.append(f"**{sample_id}**: {'; '.join(hypotheses[:2])}")
        else:
            lines.append(f"**{sample_id}**: 报告已生成")

    if len(reports) > 20:
        lines.append(f"\n*...还有 {len(reports) - 20} 个样品报告*")

    return "\n".join(lines)


# ============================================================
# Section 6: 增强版分析任务
# ============================================================

def _build_enhanced_analysis_tasks(material: str) -> str:
    """构建增强版分析任务描述"""
    return f"""---

## 6. 分析任务

请基于以上背景知识、实验数据和 **ML 建模定量结果**，生成一份全面的 {material} 材料深度机理分析报告。
报告**必须包含以下 6 个部分**：

「以下子问题为建议涵盖的要点，请结合数据写成连贯的机理分析，不必逐条机械作答。」

### 必需部分 1: EIS曲线形态机理解释
- 为什么室温/高温下EIS曲线呈类直线形态？
- 为什么低温下EIS曲线变成半圆加直线？
- 形态变化与限域结构的关系

### 必需部分 2: Arrhenius斜率变化机理
- 为什么Arrhenius曲线存在斜率突变？
- 不同温度区间的活化能差异说明了什么？
- **关键：结合 ML 定量的 ΔEa 数据（Section 4.2），量化讨论限域对 Ea 的贡献**
- **结合 Meyer-Neldel 分析结果（Section 4.3），讨论补偿效应的物理意义**
- 高温段 E_MN 与低温段 E_MN 的差异暗示什么？

### 必需部分 3: 温度依赖性机理分析
- 室温传导机理是什么？（Grotthuss/Vehicle/Packed-acid？）
- 低温传导机理是什么？
- **利用 ΔEa 的温度依赖性（slope = X eV/K），解释限域效应为何在低温更显著**
- 相变温度点的物理意义
- 各机制贡献比例随温度的变化

### 必需部分 4: 最优配比预测
- 高温区：定义温区范围，给出最优 R-N 配比及机理依据
  - 格式: **R = x ± dx, N = a ± da**
- 低温区：定义温区范围，给出最优 R-N 配比及机理依据
  - 格式: **R = x ± dx, N = a ± da**
- **ML 模型特征重要性分析：R, N, T 哪个对 Ea 影响最大？**
- R 和 N 如何协同影响传导性能？

### 必需部分 5: 实验建议与新材料预测
- 验证上述机理假设需要哪些实验？
- 如何进一步优化 {material} 材料性能？
- **参考跨材料验证结果（Section 4.4），分析其他黏土-酸体系的限域差异**
- 预测哪些新材料组合可能有更好性能？
- 酸种类替换的预期效果

### 必需部分 6: 应用场景分析
- {material} 材料适合哪些应用场景？
- 工作温度范围的限制
- 与其他质子导体的比较
- 工业化挑战
"""


# ============================================================
# Section 7: 输出要求
# ============================================================

def _build_output_requirements() -> str:
    """输出格式要求"""
    return """---

## 7. 输出要求

- 使用**英文**撰写
- 每个部分需有充分的科学论证
- **必须引用 Section 4 中的 ML 定量数据**作为证据支持
- 给出具体的数值预测和置信度
- 对于不确定的推断，明确标注"hypothesis"或"to be verified"
- 总字数不少于 3000 词
- 使用 Markdown 格式，包含表格和公式

请开始生成报告：
"""
