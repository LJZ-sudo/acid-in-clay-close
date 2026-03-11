# -*- coding: utf-8 -*-
"""
材料深度机理分析提示词

用于生成材料级深度机理分析报告，包含6大必需内容：
1. EIS曲线形态机理
2. Arrhenius斜率变化机理
3. 室温机理分析
4. 低温机理分析
5. 最优R-N配比预测
6. 实验建议/新材料预测/应用场景

更新日期: 2026-01-26
"""

from typing import Dict, List, Any, Optional
from datetime import datetime


def build_deep_analysis_system_prompt() -> str:
    """构建系统提示词"""
    return """你是电化学/固态离子导体专家，专门研究质子导体材料。你的专业领域包括：

1. **质子传导机理**：Grotthuss机制、Vehicle机制、Packed-acid机制
2. **阻抗谱(EIS)分析**：Nyquist图解读、等效电路、Rb提取
3. **Arrhenius分析**：活化能计算、分段拟合、断点物理意义
4. **纳米限域效应**：黏土材料孔道限域、低温质子传导
5. **材料设计**：配方优化、性能预测

**重要原则**：
- 必须基于提供的实验数据做推断，不能凭空想象
- 每个结论必须引用具体数据支持
- 低温高Ea不等于Vehicle机制，要结合物理可行性判断
- 限域体系在低温仍可能通过Packed-acid机制导电
"""


def build_deep_analysis_user_prompt(
    material_id: str,
    clay_type: str,
    acid_type: str,
    knowledge_section: str,
    data_summary: Dict[str, Any],
    sample_reports_summary: str,
    arrhenius_summary: str,
) -> str:
    """
    构建用户提示词
    
    Args:
        material_id: 材料ID（如 S8）
        clay_type: 黏土类型
        acid_type: 酸类型
        knowledge_section: 知识库背景信息
        data_summary: 数据统计摘要
        sample_reports_summary: 单样品机理报告摘要
        arrhenius_summary: Arrhenius分析摘要
        
    Returns:
        完整的用户提示词
    """
    
    prompt = f"""# {material_id} 材料深度机理分析任务

## 任务说明

请基于以下实验数据和单样品分析报告，生成 **{material_id}** 材料的深度机理分析报告。

报告必须包含以下**6大必需章节**，每个章节必须有具体数据支持：

---

## 1. 材料背景信息

{knowledge_section}

---

## 2. 数据统计摘要

- **材料**: {material_id} ({clay_type} + {acid_type})
- **样品数量**: {data_summary.get('n_samples', 'N/A')}
- **R范围**: {data_summary.get('R_range', 'N/A')}
- **N范围**: {data_summary.get('N_range', 'N/A')}
- **温度范围**: {data_summary.get('temp_range_K', 'N/A')} K
- **电导率范围**: {data_summary.get('sigma_range', 'N/A')} S/cm
- **Ea范围**: {data_summary.get('Ea_range_eV', 'N/A')} eV

### 性能排名（按室温电导率）

{data_summary.get('performance_ranking', '无排名数据')}

---

## 3. Arrhenius分析摘要

{arrhenius_summary}

---

## 4. 单样品机理报告摘要

{sample_reports_summary}

---

## 【必须输出的6大章节】

请严格按照以下结构输出分析报告。每个章节必须包含：
- **具体数据引用**（温度、电导率、Ea等数值）
- **机理推断**
- **证据支持**

### 第一章：EIS曲线形态机理分析

**必须回答**：
1. 室温/高温下EIS曲线为什么呈现"类直线"形态？
2. 低温下为什么变成"半圆+直线"形态？
3. 这种形态变化反映了什么物理过程？
4. 不同R/N配比的样品，形态变化有什么规律？

### 第二章：Arrhenius斜率变化机理分析

**必须回答**：
1. 为什么Arrhenius曲线存在分段（斜率变化）？
2. 断点温度的物理意义是什么？
3. 高温段和低温段的Ea差异说明什么？
4. 是否存在多个转变温度？各自的物理意义？
5. 警告：低温高Ea不等于Vehicle机制！请结合物理可行性分析。

### 第三章：室温传导机理分析

**必须回答**：
1. 室温下主导的质子传导机制是什么？（Grotthuss/Vehicle/Packed-acid？）
2. 黏土孔道限域对室温传导有什么影响？
3. 酸浓度（R参数）如何影响室温传导？
4. 液固比（N参数）如何影响室温传导？

### 第四章：低温传导机理分析

**必须回答**：
1. 低温下（<200K）传导机制是否发生变化？
2. 玻璃化转变对传导有什么影响？
3. 为什么限域体系在极低温（<150K）仍能导电？
4. Packed-acid机制在低温是否主导？证据是什么？
5. 最低有效导电温度是多少？对应电导率是多少？

### 第五章：最优R-N配比预测

**必须回答**：
1. **高温（室温）最优配比**: R = ?, N = ?
   - 预测最佳电导率及依据
   - 为什么这个配比最优？机理解释
   
2. **低温最优配比**: R = ?, N = ?
   - 预测最佳电导率及依据
   - 低温最优是否与高温不同？为什么？

3. **配比-性能关系总结**
   - R对性能的影响规律
   - N对性能的影响规律
   - 交互作用（R×N）

### 第六章：综合建议

**必须回答**：

**6.1 实验建议**
- 建议进行的下一步实验是什么？
- 需要补充哪些测量/表征？

**6.2 新材料预测**
- 基于机理分析，预测什么新材料可能有更好性能？
- 理论依据是什么？

**6.3 应用场景**
- {material_id}材料适合什么应用场景？
- 高温应用 vs 低温应用的优劣势？

---

## 输出格式要求

1. 使用Markdown格式
2. 每个结论必须引用具体数据（温度、Ea、电导率等）
3. 对于不确定的推断，明确标注"假设"或"待验证"
4. 避免空泛描述，每句话必须有信息量
5. 如果数据不足以支持某个结论，明确说明

---

请开始分析：
"""
    
    return prompt


def build_arrhenius_summary(
    segments_data: List[Dict[str, Any]],
    breakpoints: List[float] = None
) -> str:
    """
    构建Arrhenius分析摘要
    
    Args:
        segments_data: 所有样品的分段数据
        breakpoints: 常见断点温度列表
    """
    if not segments_data:
        return "无Arrhenius分段数据"
    
    lines = []
    
    # 统计分段数分布
    n_segments_dist = {}
    for seg in segments_data:
        n = seg.get('n_segments', 1)
        n_segments_dist[n] = n_segments_dist.get(n, 0) + 1
    
    lines.append("### 分段数分布")
    for n, count in sorted(n_segments_dist.items()):
        lines.append(f"- {n}段: {count}个样品")
    
    # 统计Ea范围
    all_Ea = [s.get('Ea_eV', 0) for s in segments_data if s.get('Ea_eV')]
    if all_Ea:
        lines.append(f"\n### Ea统计")
        lines.append(f"- 范围: {min(all_Ea):.3f} - {max(all_Ea):.3f} eV")
        lines.append(f"- 平均: {sum(all_Ea)/len(all_Ea):.3f} eV")
    
    # 温度区间统计
    lines.append(f"\n### 典型分段情况")
    lines.append("| 温区 | 典型Ea (eV) | 样品数 |")
    lines.append("|------|------------|--------|")
    
    # 按温度区间分组
    high_T_Ea = [s['Ea_eV'] for s in segments_data if s.get('T_avg_K', 300) > 250 and s.get('Ea_eV')]
    mid_T_Ea = [s['Ea_eV'] for s in segments_data if 200 <= s.get('T_avg_K', 300) <= 250 and s.get('Ea_eV')]
    low_T_Ea = [s['Ea_eV'] for s in segments_data if s.get('T_avg_K', 300) < 200 and s.get('Ea_eV')]
    
    if high_T_Ea:
        avg = sum(high_T_Ea) / len(high_T_Ea)
        lines.append(f"| >250K (高温) | {avg:.3f} | {len(high_T_Ea)} |")
    if mid_T_Ea:
        avg = sum(mid_T_Ea) / len(mid_T_Ea)
        lines.append(f"| 200-250K (中温) | {avg:.3f} | {len(mid_T_Ea)} |")
    if low_T_Ea:
        avg = sum(low_T_Ea) / len(low_T_Ea)
        lines.append(f"| <200K (低温) | {avg:.3f} | {len(low_T_Ea)} |")
    
    return "\n".join(lines)


def build_sample_reports_summary(
    reports: List[Dict[str, Any]],
    max_samples: int = 5
) -> str:
    """
    构建单样品机理报告摘要
    
    Args:
        reports: 单样品报告列表
        max_samples: 最多显示的样品数
    """
    if not reports:
        return "无单样品报告数据"
    
    lines = ["### 典型样品分析摘要", ""]
    
    # 显示top N样品的关键发现
    for i, report in enumerate(reports[:max_samples]):
        sample_id = report.get('sample_id', f'Sample {i+1}')
        lines.append(f"**{sample_id}**:")
        
        # 温度范围
        temp_range = report.get('temp_range_K')
        if temp_range:
            lines.append(f"- 温度: {temp_range[0]:.0f}-{temp_range[1]:.0f} K")
        
        # Arrhenius信息
        arr = report.get('arrhenius', {})
        if arr:
            lines.append(f"- 分段数: {arr.get('n_segments', 1)}")
            segments = arr.get('segments', [])
            for j, seg in enumerate(segments[:3]):  # 最多3段
                Ea = seg.get('Ea_eV', 0)
                T_range = seg.get('temp_range_K', [])
                r2 = seg.get('r_squared', 0)
                if T_range and len(T_range) >= 2:
                    lines.append(f"  - 段{j+1}: {T_range[1]:.0f}-{T_range[0]:.0f}K, Ea={Ea:.3f}eV, R²={r2:.3f}")
        
        # 关键发现
        findings = report.get('key_findings', [])
        if findings:
            lines.append("- 关键发现:")
            for f in findings[:2]:
                lines.append(f"  - {f}")
        
        lines.append("")
    
    if len(reports) > max_samples:
        lines.append(f"*...还有 {len(reports) - max_samples} 个样品报告*")
    
    return "\n".join(lines)


def build_data_summary(
    samples_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    构建数据统计摘要
    
    Args:
        samples_data: 样品数据列表
    """
    if not samples_data:
        return {}
    
    n_samples = len(samples_data)
    
    # 提取参数
    R_values = [s.get('R', 0) for s in samples_data if s.get('R')]
    N_values = [s.get('N', 0) for s in samples_data if s.get('N')]
    temps = []
    sigmas = []
    Eas = []
    
    for s in samples_data:
        temps.extend(s.get('temperatures', []))
        sigmas.extend([x for x in s.get('conductivity_values', []) if x and x > 0])
        arr = s.get('arrhenius', {})
        for seg in arr.get('segments', []):
            if seg.get('Ea_eV'):
                Eas.append(seg['Ea_eV'])
    
    # 性能排名（按室温电导率）
    ranking = []
    for s in samples_data:
        sample_id = s.get('sample_id', 'unknown')
        temps_s = s.get('temperatures', [])
        sigmas_s = s.get('conductivity_values', [])
        
        # 找室温附近的电导率
        rt_sigma = None
        for t, sigma in zip(temps_s, sigmas_s):
            if t and sigma and 293 <= t <= 303:
                rt_sigma = sigma
                break
        
        if rt_sigma:
            ranking.append((sample_id, rt_sigma, s.get('R', 0), s.get('N', 0)))
    
    # 排序
    ranking.sort(key=lambda x: -x[1])  # 按电导率降序
    
    ranking_str = ""
    if ranking:
        ranking_str = "| 排名 | 样品 | 室温σ (S/cm) | R | N |\n"
        ranking_str += "|------|------|-------------|---|---|\n"
        for i, (sid, sigma, R, N) in enumerate(ranking[:10], 1):
            ranking_str += f"| {i} | {sid} | {sigma:.4e} | {R:.3f} | {N:.2f} |\n"
    
    return {
        'n_samples': n_samples,
        'R_range': f"{min(R_values):.3f} - {max(R_values):.3f}" if R_values else "N/A",
        'N_range': f"{min(N_values):.2f} - {max(N_values):.2f}" if N_values else "N/A",
        'temp_range_K': f"{min(temps):.0f} - {max(temps):.0f}" if temps else "N/A",
        'sigma_range': f"{min(sigmas):.2e} - {max(sigmas):.2e}" if sigmas else "N/A",
        'Ea_range_eV': f"{min(Eas):.3f} - {max(Eas):.3f}" if Eas else "N/A",
        'performance_ranking': ranking_str,
    }


# 测试
if __name__ == "__main__":
    print(build_deep_analysis_system_prompt()[:500])
