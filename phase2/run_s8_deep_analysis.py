# -*- coding: utf-8 -*-
"""
S8材料深度机理分析

使用Claude Opus 4.5基于所有单样品报告生成材料级深度分析

使用方法:
    cd close
    python phase2/run_s8_deep_analysis.py
"""

import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

# 设置项目根目录
PHASE2_ROOT = Path(__file__).resolve().parent
CLOSE_ROOT = PHASE2_ROOT.parent

# 第一轮 standalone 化：优先只使用 close 自身模块
sys.path.insert(0, str(CLOSE_ROOT))

# 解决Windows编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# 导入配置（仅使用 close/config）
from config.api_config import OPENROUTER_CONFIG

from phase2.data.material_knowledge_base import (
    CLAY_DETAILED_KNOWLEDGE, 
    ACID_DETAILED_KNOWLEDGE,
    PROTON_MECHANISM_KNOWLEDGE,
    EIS_MORPHOLOGY_KNOWLEDGE,
    ARRHENIUS_SEGMENTATION_KNOWLEDGE
)


def load_sample_reports(report_dir: Path, material: str = 'S8') -> List[Dict]:
    """加载所有单样品报告"""
    reports = []
    
    for report_file in report_dir.glob(f"{material}*_mechanism_report.md"):
        sample_id = report_file.stem.replace("_mechanism_report", "")
        
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        reports.append({
            'sample_id': sample_id,
            'content': content,
            'length': len(content)
        })
    
    return reports


def load_segment_data_from_json(data_dir: Path, material: str = 'S8') -> pd.DataFrame:
    """从JSON文件加载segment数据"""
    rows = []
    
    for json_file in data_dir.glob(f"{material}*_analysis_result.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        sample_id = data['sample_id']
        R = data.get('R', 0)
        N = data.get('N', 0)
        
        arrhenius = data.get('arrhenius', {})
        segments = arrhenius.get('segments', [])
        
        for seg in segments:
            # 与 Phase 3 step1 一致：兼容 temp_range_K 与 T_range_K
            temp_range = seg.get('temp_range_K') or seg.get('T_range_K', [0, 0])
            temp_range = list(temp_range) if isinstance(temp_range, (list, tuple)) else [0, 0]
            T_avg = (temp_range[0] + temp_range[1]) / 2 if len(temp_range) >= 2 else 0
            
            rows.append({
                'sample_id': sample_id,
                'material': material,
                'R': R,
                'N': N,
                'T_avg_K': T_avg,
                'Ea_eV': seg.get('Ea_eV', 0),
                'r_squared': seg.get('r_squared', 0),
                'ln_sigma0': seg.get('ln_sigma0', 0),
            })
    
    return pd.DataFrame(rows)


def summarize_sample_reports(reports: List[Dict]) -> str:
    """汇总单样品报告的关键发现"""
    summary_parts = []
    
    # 添加说明
    total_samples = len(reports)
    summary_parts.append(f"**说明**：共{total_samples}个样品，此处展示前20个代表性样品的关键发现（覆盖主要R-N组合和温度范围）。\n")
    
    for r in reports[:20]:
        content = r['content']
        lines = content.split('\n')
        
        hypotheses = []
        in_hypotheses = False
        for line in lines:
            if 'hypothesis' in line.lower() or '假设' in line:
                in_hypotheses = True
            elif line.startswith('#') and in_hypotheses:
                in_hypotheses = False
            elif in_hypotheses and line.strip():
                hypotheses.append(line.strip()[:100])
        
        summary_parts.append(f"**{r['sample_id']}**: {'; '.join(hypotheses[:2])}" if hypotheses else f"**{r['sample_id']}**: 报告已生成")
    
    return "\n".join(summary_parts)


def build_deep_analysis_prompt(
    material: str,
    sample_reports_summary: str,
    segment_stats: Dict,
    clay_knowledge: Dict,
    acid_knowledge: Dict
) -> str:
    """构建深度分析提示词"""
    
    prompt = f"""# S8材料深度机理分析任务

## 1. 背景信息

### 1.1 材料基本信息
- **材料编号**: {material}
- **黏土类型**: 海泡石 (Sepiolite)
- **酸体系**: 磷酸 (H₃PO₄)

### 1.2 海泡石材料知识
{json.dumps(clay_knowledge, ensure_ascii=False, indent=2)}

### 1.3 磷酸体系知识
{json.dumps(acid_knowledge, ensure_ascii=False, indent=2)}

### 1.4 质子传导机理背景
{json.dumps(PROTON_MECHANISM_KNOWLEDGE, ensure_ascii=False, indent=2)}

### 1.5 EIS曲线形态解释
{json.dumps(EIS_MORPHOLOGY_KNOWLEDGE, ensure_ascii=False, indent=2)}

### 1.6 Arrhenius分段解释
{json.dumps(ARRHENIUS_SEGMENTATION_KNOWLEDGE, ensure_ascii=False, indent=2)}

---

## 2. 实验数据汇总

### 2.1 数据统计
- **样品数量**: {segment_stats['n_samples']}
- **R-N组合数**: {segment_stats['n_rn_combos']}
- **总分段数**: {segment_stats['n_segments']} segments
- **分段数分布**: {', '.join([f'{n}段样品{k}个' for n, k in sorted(segment_stats['segments_distribution'].items())]) if segment_stats['segments_distribution'] else 'N/A'}
- **温度范围**: {segment_stats['T_min']:.1f} K ~ {segment_stats['T_max']:.1f} K
- **R (酸/水摩尔比) 范围**: {segment_stats['R_min']:.3f} ~ {segment_stats['R_max']:.3f}
- **N (液/固比) 范围**: {segment_stats['N_min']:.2f} ~ {segment_stats['N_max']:.2f}
- **Ea (活化能) 范围**: {segment_stats['Ea_min']:.3f} ~ {segment_stats['Ea_max']:.3f} eV
- **典型Ea值**: 高温段(T>250K)平均 {f"{segment_stats['Ea_high_T_mean']:.3f}" if segment_stats['Ea_high_T_mean'] is not None else 'N/A'} eV，低温段(T<200K)平均 {f"{segment_stats['Ea_low_T_mean']:.3f}" if segment_stats['Ea_low_T_mean'] is not None else 'N/A'} eV

### 2.2 单样品报告关键发现汇总
{sample_reports_summary}

---

## 3. 分析任务

请基于以上背景知识和实验数据，生成一份全面的S8材料深度机理分析报告。报告**必须包含以下6个部分**：
「以下子问题为建议涵盖的要点，请结合数据写成连贯的机理分析，不必逐条机械作答。」

### 必需部分 1: EIS曲线形态机理解释
- 为什么室温/高温下EIS曲线呈类直线形态？
- 为什么低温下EIS曲线变成半圆加直线？
- 这种形态变化反映了什么物理机制，与海泡石限域结构的关系是什么？

### 必需部分 2: Arrhenius斜率变化机理
- 为什么Arrhenius曲线存在斜率突变？
- 不同温度区间的活化能差异说明了什么？
- 这与质子传导机制的转变有何关系？
- 结合Meyer-Neldel规则进行分析

### 必需部分 3: 温度依赖性机理分析
- 室温传导机理是什么？
- 低温传导机理是什么？
- 相变温度点的物理意义是什么？
- Grotthuss vs Vehicle vs Packed-acid机制的贡献

### 必需部分 4: 最优配比预测
- 高温区：根据数据中的温度分布、Arrhenius分段断点、Ea变化等，定义"高温区"的温度范围（例如：T > XX K，XX为基于数据判断的转折温度），给出该温区的最优R-N配比及机理依据；并写出推荐可接受范围，格式为 **R = x ± dx，N = a ± da**（例如 R = 0.35 ± 0.05，N = 4.0 ± 0.5）。建议小节标题含「4.1 高温区」。
- 低温区：根据数据中的温度分布、Arrhenius分段断点、Ea变化等，定义"低温区"的温度范围（例如：T < XX K，XX为基于数据判断的转折温度），给出该温区的最优R-N配比及机理依据；并写出推荐可接受范围，格式为 **R = x ± dx，N = a ± da**。建议小节标题含「4.2 低温区」。
- R和N如何协同影响传导性能？
- 基于物理机制的配比优化建议

### 必需部分 5: 实验建议与新材料预测
- 验证上述机理假设需要哪些实验？
- 如何进一步优化S8材料性能？
- 基于这种限域特性和机理，预测哪些新材料组合可能有更好性能？
- 酸种类替换的预期效果

### 必需部分 6: 应用场景分析
- S8材料适合哪些应用场景？
- 工作温度范围的限制是什么？
- 与其他质子导体材料相比的优劣势
- 工业化应用的潜在挑战

---

## 4. 输出要求

- 使用英文撰写
- 每个部分需有充分的科学论证
- 引用材料知识库中的相关参数
- 给出具体的数值预测和置信度
- 总字数不少于3000字

请开始生成报告："""

    return prompt


def call_opus45(prompt: str, max_tokens: int = 32000) -> Optional[str]:
    """调用Claude Opus 4.5"""
    api_key = OPENROUTER_CONFIG['api_key']
    url = OPENROUTER_CONFIG['base_url']
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com/eis-data-analysis',
        'X-Title': 'EIS Deep Analysis - S8 Material'
    }
    
    data = {
        'model': 'anthropic/claude-opus-4.5',
        'messages': [
            {
                'role': 'system',
                'content': '你是电化学和固态离子导体领域的顶级专家，专门研究限域纳米材料中的质子传导机理。请提供深入、全面、科学严谨的分析。'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': 0.5,
        'max_tokens': max_tokens,
    }
    
    print(f"[API] 调用 Claude Opus 4.5, max_tokens={max_tokens}...")
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            choices = result.get('choices', [])
            if choices:
                content = choices[0].get('message', {}).get('content', '')
                error = choices[0].get('error', {})
                if error:
                    print(f"[ERROR] {error.get('message', 'Unknown')}")
                    return None
                
                usage = result.get('usage', {})
                print(f"[OK] 成功! input={usage.get('prompt_tokens', 'N/A')}, output={usage.get('completion_tokens', 'N/A')}")
                return content
        else:
            print(f"[ERROR] HTTP {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print("[ERROR] 请求超时")
        return None
    except Exception as e:
        print(f"[ERROR] {str(e)[:50]}")
        return None


def main():
    print("\n" + "=" * 80)
    print("S8材料深度机理分析 (Claude Opus 4.5)")
    print("=" * 80)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 路径设置（使用close目录）
    report_dir = CLOSE_ROOT / "output" / "phase2_reports"
    data_dir = CLOSE_ROOT / "output" / "phase1_results"
    output_dir = CLOSE_ROOT / "output" / "deep_analysis"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 加载单样品报告
    print("\n[Step 1] 加载单样品报告...")
    reports = load_sample_reports(report_dir, 'S8')
    print(f"  找到 {len(reports)} 个S8样品报告")
    
    if len(reports) < 5:
        print(f"  [WARN] 报告数量较少，建议先运行 phase2/run_batch_reports.py --material S8")
    
    # 2. 加载segment数据（从JSON文件）
    print("\n[Step 2] 加载segment数据...")
    df = load_segment_data_from_json(data_dir, 'S8')
    
    if len(df) == 0:
        print("  [ERROR] 没有找到S8数据，请先运行Phase 1")
        return
    
    # 计算R-N组合数
    rn_combos = df.groupby(['R', 'N']).size().reset_index()
    n_rn_combos = len(rn_combos)
    
    # 计算分段数分布（从JSON文件统计）
    segments_distribution = {}
    for json_file in data_dir.glob("S8*_analysis_result.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        arrhenius = data.get('arrhenius', {})
        n_seg = len(arrhenius.get('segments', []))
        segments_distribution[n_seg] = segments_distribution.get(n_seg, 0) + 1
    
    # 计算典型Ea值（按温度区间）
    df_high_T = df[df['T_avg_K'] > 250]
    df_low_T = df[df['T_avg_K'] < 200]
    Ea_high_T_mean = df_high_T['Ea_eV'].mean() if len(df_high_T) > 0 else None
    Ea_low_T_mean = df_low_T['Ea_eV'].mean() if len(df_low_T) > 0 else None
    
    segment_stats = {
        'n_samples': df['sample_id'].nunique(),
        'n_segments': len(df),
        'n_rn_combos': n_rn_combos,
        'segments_distribution': segments_distribution,
        'T_min': df['T_avg_K'].min(),
        'T_max': df['T_avg_K'].max(),
        'R_min': df['R'].min(),
        'R_max': df['R'].max(),
        'N_min': df['N'].min(),
        'N_max': df['N'].max(),
        'Ea_min': df['Ea_eV'].min(),
        'Ea_max': df['Ea_eV'].max(),
        'Ea_high_T_mean': Ea_high_T_mean,
        'Ea_low_T_mean': Ea_low_T_mean,
    }
    print(f"  样品数: {segment_stats['n_samples']}, segments: {segment_stats['n_segments']}")
    print(f"  R范围: {segment_stats['R_min']:.3f} ~ {segment_stats['R_max']:.3f}")
    print(f"  N范围: {segment_stats['N_min']:.2f} ~ {segment_stats['N_max']:.2f}")
    
    # 3. 汇总报告
    print("\n[Step 3] 汇总单样品报告...")
    reports_summary = summarize_sample_reports(reports)
    
    # 4. 获取材料知识
    clay_knowledge = CLAY_DETAILED_KNOWLEDGE.get('Sepiolite', {})
    acid_knowledge = ACID_DETAILED_KNOWLEDGE.get('H3PO4', {})
    
    # 5. 构建提示词
    print("\n[Step 4] 构建深度分析提示词...")
    prompt = build_deep_analysis_prompt(
        'S8',
        reports_summary,
        segment_stats,
        clay_knowledge,
        acid_knowledge
    )
    
    prompt_length = len(prompt)
    print(f"  提示词长度: {prompt_length} 字符")
    
    # 保存提示词
    with open(output_dir / "S8_deep_analysis_prompt.txt", 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    # 6. 调用Opus 4.5
    print("\n[Step 5] 调用 Claude Opus 4.5 生成深度分析...")
    response = call_opus45(prompt, max_tokens=32000)
    
    if response and len(response) > 500:
        # 保存报告
        report_file = output_dir / "S8_deep_mechanism_analysis.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# S8材料深度机理分析报告\n\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**模型**: Claude Opus 4.5\n")
            f.write(f"**基于数据**: {segment_stats['n_samples']}个样品, {len(reports)}份单样品报告\n\n")
            f.write("---\n\n")
            f.write(response)
        
        print(f"\n[OK] 深度分析报告已保存: {report_file}")
        print(f"  报告长度: {len(response)} 字符")
        
        # 打印预览
        print("\n" + "=" * 80)
        print("报告预览 (前1000字符):")
        print("=" * 80)
        print(response[:1000])
        print("...\n")
    else:
        print("[ERROR] 深度分析生成失败")
    
    print("\n" + "=" * 80)
    print("深度分析完成!")
    print("=" * 80)


if __name__ == '__main__':
    main()
