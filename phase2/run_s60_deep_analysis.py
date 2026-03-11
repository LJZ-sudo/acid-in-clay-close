# -*- coding: utf-8 -*-
"""
S60材料深度机理分析

使用 Claude Opus 4.5 基于所有 S60 单样品报告生成材料级深度分析（纯 H3PO4，无黏土/无限域）。

使用方法:
    cd close
    python phase2/run_s60_deep_analysis.py              # 完整运行（需 API）
    python phase2/run_s60_deep_analysis.py --dry-run     # 仅加载数据并生成 prompt，不调 API（用于验证）
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

# 设置项目根目录
PHASE2_ROOT = Path(__file__).resolve().parent
CLOSE_ROOT = PHASE2_ROOT.parent

# 第一轮 standalone 化：优先只使用 close 自身模块
sys.path.insert(0, str(CLOSE_ROOT))

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config.api_config import OPENROUTER_CONFIG

from phase2.data.material_knowledge_base import (
    ACID_DETAILED_KNOWLEDGE,
    PROTON_MECHANISM_KNOWLEDGE,
    EIS_MORPHOLOGY_KNOWLEDGE,
    ARRHENIUS_SEGMENTATION_KNOWLEDGE,
)


def load_sample_reports(report_dir: Path, material: str = 'S60') -> List[Dict]:
    """加载所有 S60 单样品报告"""
    reports = []
    for report_file in report_dir.glob(f"{material}*_mechanism_report.md"):
        sample_id = report_file.stem.replace("_mechanism_report", "")
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
        reports.append({'sample_id': sample_id, 'content': content, 'length': len(content)})
    return reports


def load_segment_data_from_json(data_dir: Path, material: str = 'S60') -> pd.DataFrame:
    """从 phase1 JSON 加载 segment 数据（S60 无黏土，N 可为 0）"""
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
    parts = []
    for r in reports:
        content = r['content']
        lines = content.split('\n')
        hypotheses = []
        in_hyp = False
        for line in lines:
            if 'hypothesis' in line.lower() or '假设' in line:
                in_hyp = True
            elif line.startswith('#') and in_hyp:
                in_hyp = False
            elif in_hyp and line.strip():
                hypotheses.append(line.strip()[:100])
        parts.append(f"**{r['sample_id']}**: {'; '.join(hypotheses[:2])}" if hypotheses else f"**{r['sample_id']}**: 报告已生成")
    return "\n".join(parts[:20])


def build_deep_analysis_prompt_s60(
    sample_reports_summary: str,
    segment_stats: Dict,
    acid_knowledge: Dict,
) -> str:
    """S60 专用深度分析提示词：纯 H3PO4，无黏土/无限域，强调 R 与温度、Vehicle/Grotthuss。"""
    n_str = f"{segment_stats['N_min']:.2f} ~ {segment_stats['N_max']:.2f}" if segment_stats.get('N_max', 0) != 0 else "不适用（纯酸无黏土）"
    prompt = f"""# S60材料（纯 H₃PO₄）深度机理分析任务

## 1. 背景信息

### 1.1 材料基本信息
- **材料编号**: S60
- **体系**: 纯磷酸液体电解质（无黏土、无限域）
- **酸体系**: 磷酸 (H₃PO₄)
- **定位**: 作为 Acid-in-Clay（如 S8）的「无限域基线」对比对象

### 1.2 磷酸体系知识
{json.dumps(acid_knowledge, ensure_ascii=False, indent=2)}

### 1.3 质子传导机理背景
{json.dumps(PROTON_MECHANISM_KNOWLEDGE, ensure_ascii=False, indent=2)}

### 1.4 EIS曲线形态解释
{json.dumps(EIS_MORPHOLOGY_KNOWLEDGE, ensure_ascii=False, indent=2)}

### 1.5 Arrhenius分段解释
{json.dumps(ARRHENIUS_SEGMENTATION_KNOWLEDGE, ensure_ascii=False, indent=2)}

---

## 2. 实验数据汇总

### 2.1 数据统计
- **样品数量**: {segment_stats['n_samples']}
- **Segment 数量**: {segment_stats['n_segments']}
- **温度范围**: {segment_stats['T_min']:.1f} K ~ {segment_stats['T_max']:.1f} K
- **R (酸/水摩尔比) 范围**: {segment_stats['R_min']:.3f} ~ {segment_stats['R_max']:.3f}
- **N (液/固比)**: {n_str}
- **Ea (活化能) 范围**: {segment_stats['Ea_min']:.3f} ~ {segment_stats['Ea_max']:.3f} eV

### 2.2 单样品报告关键发现汇总
{sample_reports_summary}

---

## 3. 分析任务

请基于以上背景知识和实验数据，生成一份 **S60（纯 H₃PO₄）** 材料的深度机理分析报告。报告**必须包含以下 6 个部分**：

### 必需部分 1: EIS 曲线形态机理解释（纯酸体系）
- 纯酸体系下室温/高温 EIS 曲线为何呈类直线形态？
- 低温下形态变化反映了什么物理机制？
- 与黏土限域体系（如 S8）的形态差异及原因

### 必需部分 2: Arrhenius 斜率变化机理
- 为什么 Arrhenius 曲线存在斜率突变？
- 不同温度区间的活化能差异说明了什么？
- 与质子传导机制转变（Vehicle / Grotthuss）的关系
- 结合 Meyer-Neldel 规则进行分析

### 必需部分 3: 温度依赖性机理分析
- 高温/中温/低温段主导传导机理是什么？
- 相变或拐点温度点的物理意义
- Grotthuss vs Vehicle vs 其他机制的贡献

### 必需部分 4: R（酸/水比）与性能关系
- R 对 Ea 与电导率的影响规律
- 高温区与低温区下较优的 R 范围及原因
- 基于物理机制的 R 优化建议（S60 无 N，仅讨论 R）

### 必需部分 5: 实验建议与改进方向
- 验证上述机理假设需要哪些实验？
- 纯酸体系性能改进方向
- 与 S8（限域）对比实验的建议

### 必需部分 6: 应用场景与定位
- S60 纯酸材料适合哪些应用场景？
- 工作温度范围限制
- 与 S8（Acid-in-Clay）相比的优劣势
- 作为「无限域基线」在研究中的角色

---

## 4. 输出要求

- 使用中文撰写
- 每个部分需有充分的科学论证
- 引用材料知识库中的相关参数
- 给出具体的数值范围或定性结论
- 总字数不少于 3000 字
- 报告标题请使用：**# S60（Pure H₃PO₄）质子传导深度机理分析报告**

请开始生成报告："""
    return prompt


def call_opus45(prompt: str, max_tokens: int = 32000) -> Optional[str]:
    """调用 Claude Opus 4.5 生成 S60 深度分析"""
    import requests
    api_key = OPENROUTER_CONFIG['api_key']
    url = OPENROUTER_CONFIG['base_url']
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com/eis-data-analysis',
        'X-Title': 'EIS Deep Analysis - S60 Material',
    }
    data = {
        'model': 'anthropic/claude-opus-4.5',
        'messages': [
            {
                'role': 'system',
                'content': '你是电化学和固态离子导体领域的专家，熟悉纯液体电解质与质子传导机理。S60 为纯 H3PO4 液体，无黏土、无限域。请提供深入、科学严谨的分析。',
            },
            {'role': 'user', 'content': prompt},
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
                err = choices[0].get('error', {})
                if err:
                    print(f"[ERROR] {err.get('message', 'Unknown')}")
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
        print(f"[ERROR] {str(e)[:80]}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description='S60 材料深度机理分析')
    parser.add_argument('--dry-run', action='store_true', help='仅加载数据并生成 prompt，不调用 API')
    args = parser.parse_args()
    dry_run = getattr(args, 'dry_run', False)

    print("\n" + "=" * 80)
    print("S60 材料深度机理分析 (Claude Opus 4.5)")
    print("=" * 80)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if dry_run:
        print("[DRY-RUN] 仅生成 prompt，不调用 API")

    report_dir = CLOSE_ROOT / "output" / "phase2_reports"
    data_dir = CLOSE_ROOT / "output" / "phase1_results"
    output_dir = CLOSE_ROOT / "output" / "deep_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: 加载 S60 单样品报告
    print("\n[Step 1] 加载 S60 单样品报告...")
    reports = load_sample_reports(report_dir, 'S60')
    print(f"  找到 {len(reports)} 个 S60 样品报告")
    if len(reports) < 1:
        print("  [ERROR] 未找到 S60 单样品报告，请先运行: python phase2/run_batch_reports.py --material S60 --max 25")
        return 1

    # Step 2: 加载 S60 segment 数据
    print("\n[Step 2] 加载 S60 segment 数据...")
    df = load_segment_data_from_json(data_dir, 'S60')
    if len(df) == 0:
        print("  [ERROR] 未找到 S60 的 phase1 数据，请确认 close/output/phase1_results 下存在 S60*_analysis_result.json")
        return 1
    segment_stats = {
        'n_samples': int(df['sample_id'].nunique()),
        'n_segments': len(df),
        'T_min': float(df['T_avg_K'].min()),
        'T_max': float(df['T_avg_K'].max()),
        'R_min': float(df['R'].min()),
        'R_max': float(df['R'].max()),
        'N_min': float(df['N'].min()),
        'N_max': float(df['N'].max()),
        'Ea_min': float(df['Ea_eV'].min()),
        'Ea_max': float(df['Ea_eV'].max()),
    }
    print(f"  样品数: {segment_stats['n_samples']}, segments: {segment_stats['n_segments']}")
    print(f"  R 范围: {segment_stats['R_min']:.3f} ~ {segment_stats['R_max']:.3f}")

    # Step 3: 汇总单样品报告
    print("\n[Step 3] 汇总单样品报告...")
    reports_summary = summarize_sample_reports(reports)

    # Step 4: 构建 S60 专用 prompt
    print("\n[Step 4] 构建 S60 深度分析提示词...")
    acid_knowledge = ACID_DETAILED_KNOWLEDGE.get('H3PO4', {})
    prompt = build_deep_analysis_prompt_s60(reports_summary, segment_stats, acid_knowledge)
    prompt_path = output_dir / "S60_deep_analysis_prompt.txt"
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"  提示词已保存: {prompt_path} ({len(prompt)} 字符)")

    if dry_run:
        print("\n[DRY-RUN] 已跳过 API 调用，流程验证完成。")
        print("  正式运行请执行: python phase2/run_s60_deep_analysis.py")
        return 0

    # Step 5: 调用 API 生成报告
    print("\n[Step 5] 调用 Claude Opus 4.5 生成深度分析...")
    response = call_opus45(prompt, max_tokens=32000)
    if response and len(response) > 500:
        report_file = output_dir / "S60_deep_mechanism_analysis.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# S60（Pure H₃PO₄）质子传导深度机理分析报告\n\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("**模型**: Claude Opus 4.5\n")
            f.write(f"**基于数据**: {segment_stats['n_samples']} 个样品, {len(reports)} 份单样品报告\n\n")
            f.write("---\n\n")
            f.write(response)
        print(f"\n[OK] 深度分析报告已保存: {report_file}")
        print(f"  报告长度: {len(response)} 字符")
    else:
        print("[ERROR] 深度分析生成失败或返回过短")
        return 1

    print("\n" + "=" * 80)
    print("S60 深度分析完成!")
    print("=" * 80)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
