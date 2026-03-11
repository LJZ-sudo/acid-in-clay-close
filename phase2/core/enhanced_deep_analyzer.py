# -*- coding: utf-8 -*-
"""
Phase2 增强版深度分析器

优化点：
1. 增加max_tokens到16000，支持更长报告
2. 分阶段生成：推理过程 + 最终结论
3. 规范化输出格式
4. 多文件输出：reasoning.md + conclusions.md + full_report.md
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import re


class EnhancedDeepAnalyzer:
    """增强版深度分析器 - 带思考过程"""
    
    def __init__(
        self,
        api_key: str,
        template_reports_dir: Path,
        model: str = "openai/gpt-5.2"
    ):
        """初始化"""
        from phase2.core.multi_model_client import MultiModelClient
        
        self.api_key = api_key
        self.template_reports_dir = Path(template_reports_dir)
        self.llm = MultiModelClient(api_key=api_key, default_model='gpt-5.2')
        self.model = model
        
        # 加载文献知识库
        self.literature_info = self._load_literature_info()
    
    def _load_literature_info(self) -> str:
        """加载精简的文献框架"""
        return """
## 核心文献框架

### 机制判断原则（优先级从高到低）

1. **直接实验证据** (⭐⭐⭐)
   - NMR/QENS: 观察分子运动
   - 同位素效应: σ_D/σ_H区分机制
   - 原位XRD: 相变检测

2. **物理可行性** (⭐⭐)
   - 低温/高黏度: Vehicle先被冻结
   - Grotthuss可"慢速存活"

3. **Ea阈值** (⭐) - 仅供参考，不能机械套用
   - Grotthuss: 通常<0.3 eV（但低温可升至0.5-1.0 eV）
   - Vehicle: 通常>0.4 eV
   - Packed-acid: 0.2-0.4 eV（属于Grotthuss）

### 关键文献结论

| 文献 | 核心发现 |
|-----|---------|
| Kreuer 2004 | Grotthuss/Vehicle判据框架 |
| Nature Chem 2012 | 磷酸体系主要是酸-酸链结构扩散 |
| Chem.Sci 2014 | Packed-acid: 水不动也能导电 |
| Wang 2022 (AiCE) | -82°C仍有σ=0.023 mS/cm，无相变 |
| Agmon 1995 | Grotthuss限速步骤是氢键重排 |
"""
    
    def analyze_material_with_reasoning(
        self,
        material_type: str,
        output_dir: Path
    ) -> Dict[str, Any]:
        """
        带推理过程的材料深度分析
        
        生成三个文件：
        1. {material}_reasoning.md - 详细推理过程
        2. {material}_conclusions.md - 核心结论汇总
        3. {material}_full_report.md - 完整报告
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"开始 {material_type} 材料增强深度分析")
        print(f"{'='*60}")
        
        # 1. 收集报告
        print(f"\n[1/6] 收集{material_type}样品报告...")
        reports = self._collect_reports(material_type)
        print(f"  → 找到 {len(reports)} 个样品")
        
        if len(reports) == 0:
            return {'error': f'未找到{material_type}样品报告'}
        
        # 2. 提取数据摘要
        print(f"\n[2/6] 提取数据摘要...")
        data_summary = self._extract_data_summary(reports, material_type)
        
        # 3. 生成推理过程
        print(f"\n[3/6] 生成详细推理过程 (Step-by-Step)...")
        reasoning_result = self._generate_reasoning(
            material_type, reports, data_summary
        )
        
        if reasoning_result.get('error'):
            return reasoning_result
        
        reasoning_content = reasoning_result['content']
        
        # 保存推理过程
        reasoning_file = output_dir / f"{material_type}_reasoning.md"
        self._save_with_header(
            reasoning_file, 
            reasoning_content,
            f"{material_type} 深度分析 - 推理过程",
            "本文档展示AI分析的完整推理链条"
        )
        print(f"  → 保存: {reasoning_file.name}")
        
        # 4. 生成核心结论
        print(f"\n[4/6] 基于推理生成核心结论...")
        conclusions_result = self._generate_conclusions(
            material_type, data_summary, reasoning_content
        )
        
        if conclusions_result.get('error'):
            return conclusions_result
        
        conclusions_content = conclusions_result['content']
        
        # 保存结论
        conclusions_file = output_dir / f"{material_type}_conclusions.md"
        self._save_with_header(
            conclusions_file,
            conclusions_content,
            f"{material_type} 深度分析 - 核心结论",
            "本文档汇总关键发现和结论"
        )
        print(f"  → 保存: {conclusions_file.name}")
        
        # 5. 生成完整报告（整合版）
        print(f"\n[5/6] 整合生成完整报告...")
        full_report = self._generate_full_report(
            material_type, data_summary, reasoning_content, conclusions_content
        )
        
        full_report_file = output_dir / f"{material_type}_full_report.md"
        with open(full_report_file, 'w', encoding='utf-8') as f:
            f.write(full_report)
        print(f"  → 保存: {full_report_file.name}")
        
        # 6. 生成分析摘要
        print(f"\n[6/6] 完成!")
        
        return {
            'success': True,
            'material': material_type,
            'n_samples': len(reports),
            'files': {
                'reasoning': str(reasoning_file),
                'conclusions': str(conclusions_file),
                'full_report': str(full_report_file)
            },
            'tokens': {
                'reasoning': reasoning_result.get('usage', {}),
                'conclusions': conclusions_result.get('usage', {})
            }
        }
    
    def _collect_reports(self, material_type: str) -> List[Dict]:
        """收集指定材料的报告"""
        reports = []
        for report_file in self.template_reports_dir.glob(f"{material_type}-*_template_report.md"):
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sample_id = report_file.stem.replace('_template_report', '')
            reports.append({
                'sample_id': sample_id,
                'content': content
            })
        
        return sorted(reports, key=lambda x: x['sample_id'])
    
    def _extract_data_summary(self, reports: List[Dict], material_type: str) -> Dict:
        """从报告中提取关键数据"""
        all_eas = []
        all_segments = []
        samples_info = []
        
        for report in reports:
            content = report['content']
            sample_id = report['sample_id']
            
            # 提取Ea
            ea_matches = re.findall(r'\*\*激活能\(Ea\)\*\*: ([\d\.]+) eV', content)
            eas = [float(ea) for ea in ea_matches] if ea_matches else []
            
            # 提取R值
            r_match = re.search(r'\*\*R \(n\(H3PO4\)/n\(H2O\)\)\*\*: ([\d\.]+)', content)
            r_value = float(r_match.group(1)) if r_match else None
            
            # 提取N值
            n_match = re.search(r'\*\*液固比\(N\)\*\*: ([\d\.]+)', content)
            n_value = float(n_match.group(1)) if n_match else None
            
            # 提取温度范围
            temp_matches = re.findall(r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*K', content)
            temp_ranges = [(float(t[0]), float(t[1])) for t in temp_matches] if temp_matches else []
            
            all_eas.extend(eas)
            samples_info.append({
                'sample_id': sample_id,
                'eas': eas,
                'n_segments': len(eas),
                'R': r_value,
                'N': n_value,
                'temp_ranges': temp_ranges
            })
        
        # 分温区统计Ea
        low_temp_eas = []  # <230K
        mid_temp_eas = []  # 230-270K
        high_temp_eas = []  # >270K
        
        for sample in samples_info:
            for i, ea in enumerate(sample['eas']):
                if i < len(sample['temp_ranges']):
                    t_min, t_max = sample['temp_ranges'][i]
                    t_avg = (t_min + t_max) / 2
                    if t_avg < 230:
                        low_temp_eas.append(ea)
                    elif t_avg < 270:
                        mid_temp_eas.append(ea)
                    else:
                        high_temp_eas.append(ea)
        
        return {
            'material_type': material_type,
            'n_samples': len(reports),
            'ea_overall': {
                'min': min(all_eas) if all_eas else 0,
                'max': max(all_eas) if all_eas else 0,
                'mean': sum(all_eas)/len(all_eas) if all_eas else 0
            },
            'ea_by_temp': {
                'low_temp': {
                    'n': len(low_temp_eas),
                    'mean': sum(low_temp_eas)/len(low_temp_eas) if low_temp_eas else 0,
                    'range': (min(low_temp_eas), max(low_temp_eas)) if low_temp_eas else (0, 0)
                },
                'mid_temp': {
                    'n': len(mid_temp_eas),
                    'mean': sum(mid_temp_eas)/len(mid_temp_eas) if mid_temp_eas else 0,
                    'range': (min(mid_temp_eas), max(mid_temp_eas)) if mid_temp_eas else (0, 0)
                },
                'high_temp': {
                    'n': len(high_temp_eas),
                    'mean': sum(high_temp_eas)/len(high_temp_eas) if high_temp_eas else 0,
                    'range': (min(high_temp_eas), max(high_temp_eas)) if high_temp_eas else (0, 0)
                }
            },
            'samples': samples_info
        }
    
    def _generate_reasoning(
        self, 
        material_type: str, 
        reports: List[Dict],
        data_summary: Dict
    ) -> Dict[str, Any]:
        """生成详细推理过程"""
        
        # 构建样品数据表
        samples_table = self._build_samples_table(data_summary['samples'][:20])  # 限制数量
        
        prompt = f"""# {material_type}材料质子传导机理 - 详细推理分析

## 你的任务

请对{material_type}材料进行**逐步推理分析**，展示完整的思考过程。

## 输入数据

### 数据概况
- 样品数量: {data_summary['n_samples']}
- Ea总范围: {data_summary['ea_overall']['min']:.3f} - {data_summary['ea_overall']['max']:.3f} eV
- 平均Ea: {data_summary['ea_overall']['mean']:.3f} eV

### 分温区Ea统计
| 温度区间 | 数据点数 | Ea范围 (eV) | 平均Ea (eV) |
|---------|---------|-------------|-------------|
| 低温 (<230K) | {data_summary['ea_by_temp']['low_temp']['n']} | {data_summary['ea_by_temp']['low_temp']['range'][0]:.3f}-{data_summary['ea_by_temp']['low_temp']['range'][1]:.3f} | {data_summary['ea_by_temp']['low_temp']['mean']:.3f} |
| 中温 (230-270K) | {data_summary['ea_by_temp']['mid_temp']['n']} | {data_summary['ea_by_temp']['mid_temp']['range'][0]:.3f}-{data_summary['ea_by_temp']['mid_temp']['range'][1]:.3f} | {data_summary['ea_by_temp']['mid_temp']['mean']:.3f} |
| 高温 (>270K) | {data_summary['ea_by_temp']['high_temp']['n']} | {data_summary['ea_by_temp']['high_temp']['range'][0]:.3f}-{data_summary['ea_by_temp']['high_temp']['range'][1]:.3f} | {data_summary['ea_by_temp']['high_temp']['mean']:.3f} |

### 样品详情（部分）
{samples_table}

### 文献框架
{self.literature_info}

---

## 推理要求

请按以下结构进行**逐步推理**，每一步都要：
1. 明确说明"我在思考什么"
2. 列出观察到的数据事实
3. 进行逻辑推导
4. 得出阶段性结论
5. 标注证据强度（⭐⭐⭐强/⭐⭐中/⭐弱）

### 推理结构（请严格遵循）

## Step 1: 数据特征识别
> 我首先需要识别数据中的关键模式...

### 1.1 Ea分布特征
- 观察: [列出观察到的Ea分布特征]
- 推导: [解释这些特征意味着什么]
- 小结: [阶段性结论]

### 1.2 温度依赖性
- 观察: [Ea随温度如何变化]
- 推导: [这暗示什么机制]
- 小结: [阶段性结论]

### 1.3 组成效应
- 观察: [R、N值如何影响Ea]
- 推导: [组成-性能关系]
- 小结: [阶段性结论]

---

## Step 2: 物理可行性分析
> 在判断机制之前，我需要先确认物理可行性...

### 2.1 低温段Vehicle可行性
- 问题: 低温下(<230K)，Vehicle机制是否可行？
- 分析: [黏度、扩散系数、玻璃化温度等考虑]
- 结论: [Vehicle是否被冻结]
- 证据强度: ⭐⭐

### 2.2 Grotthuss在低温的可能性
- 问题: 低温下Grotthuss是否还能工作？
- 分析: [氢键重排动力学]
- 结论: [Grotthuss是否可"慢速存活"]
- 证据强度: ⭐⭐

---

## Step 3: 直接证据对照
> 我需要检查是否有直接实验证据...

### 3.1 低温电导证据
- AiCE文献: -82°C仍有σ=0.023 mS/cm
- 本数据: [是否与文献一致]
- 推论: [这支持什么机制]
- 证据强度: ⭐⭐⭐

### 3.2 相变证据
- AiCE文献: 低温XRD无相变
- 推论: [通道是否断裂]
- 证据强度: ⭐⭐⭐

---

## Step 4: 机制判断
> 综合以上分析，我得出机制判断...

### 4.1 低温段(<230K)主导机制
- 证据汇总: [列出支持的证据]
- 排除的可能性: [为什么不是其他机制]
- **最终判断**: [机制名称]
- **Ea高的原因**: [解释]
- 综合证据强度: ⭐⭐⭐/⭐⭐/⭐

### 4.2 中温段(230-270K)主导机制
[同上结构]

### 4.3 高温段(>270K)主导机制
[同上结构]

---

## Step 5: 限域效应分析（如果是S8）
> {"Sepiolite纳米限域如何影响机制..." if material_type == 'S8' else "跳过此步骤"}

---

## 推理总结

### 关键发现
1. [发现1]
2. [发现2]
3. [发现3]

### 证据链
[用箭头展示推理链条，如：数据观察 → 物理可行性 → 直接证据 → 机制结论]

### 不确定性和待验证
- [列出推理中的不确定点]
- [建议的验证实验]

---

请生成完整的推理过程（约4000-6000字）。
"""
        
        response = self.llm.generate(
            system_prompt="你是质子传导领域的资深专家。请进行严谨的逐步推理分析，展示完整的思考过程。",
            user_message=prompt,
            model=self.model,
            max_tokens=16000,  # 增加到16000
            temperature=0.7
        )
        
        return response
    
    def _generate_conclusions(
        self,
        material_type: str,
        data_summary: Dict,
        reasoning_content: str
    ) -> Dict[str, Any]:
        """基于推理生成结构化结论"""
        
        prompt = f"""# {material_type}材料分析 - 核心结论提炼

## 背景

基于前面的详细推理分析，现在需要提炼核心结论。

## 推理过程回顾

{reasoning_content[:8000]}  # 截取关键部分

---

## 任务

请基于推理过程，生成**结构化的核心结论报告**，格式如下：

# {material_type} 核心结论报告

## 一、关键数值汇总

| 指标 | 数值 | 说明 |
|-----|-----|------|
| 样品数 | {data_summary['n_samples']} | |
| Ea范围 | {data_summary['ea_overall']['min']:.3f}-{data_summary['ea_overall']['max']:.3f} eV | |
| [其他关键指标] | | |

## 二、机制判断（分温区）

### 低温段 (<230K)
| 项目 | 内容 |
|-----|------|
| **主导机制** | [机制名称] |
| **Ea典型值** | [数值] eV |
| **物理解释** | [简要解释] |
| **证据强度** | ⭐⭐⭐/⭐⭐/⭐ |

### 中温段 (230-270K)
[同上格式]

### 高温段 (>270K)
[同上格式]

## 三、组成优化建议

| 参数 | 最优范围 | 依据 |
|-----|---------|------|
| R (酸水比) | [范围] | [原因] |
| N (液固比) | [范围] | [原因] |

## 四、核心创新点

1. **发现1**: [一句话描述]
2. **发现2**: [一句话描述]
3. **发现3**: [一句话描述]

## 五、后续验证建议

| 建议实验 | 目的 | 优先级 |
|---------|-----|--------|
| [实验1] | [验证什么] | 高/中/低 |
| [实验2] | | |

---

请生成简洁、结构化的结论报告（约1500-2000字）。
"""
        
        response = self.llm.generate(
            system_prompt="你是一位擅长归纳总结的科学家。请基于推理过程提炼关键结论，输出结构化报告。",
            user_message=prompt,
            model=self.model,
            max_tokens=8000,
            temperature=0.5  # 降低temperature使输出更稳定
        )
        
        return response
    
    def _generate_full_report(
        self,
        material_type: str,
        data_summary: Dict,
        reasoning_content: str,
        conclusions_content: str
    ) -> str:
        """整合生成完整报告"""
        
        report = f"""# {material_type} 材料质子传导深度分析报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**分析方法**: 增强版深度分析（含完整推理链）  
**样品数量**: {data_summary['n_samples']}

---

## 目录

1. [数据概况](#1-数据概况)
2. [核心结论](#2-核心结论)
3. [详细推理过程](#3-详细推理过程)
4. [附录：证据汇总](#4-附录证据汇总)

---

## 1. 数据概况

### 1.1 基本统计

| 指标 | 数值 |
|-----|------|
| 样品数 | {data_summary['n_samples']} |
| Ea范围 | {data_summary['ea_overall']['min']:.3f} - {data_summary['ea_overall']['max']:.3f} eV |
| 平均Ea | {data_summary['ea_overall']['mean']:.3f} eV |

### 1.2 分温区Ea分布

| 温度区间 | 样本数 | Ea范围 (eV) | 平均Ea (eV) |
|---------|-------|-------------|-------------|
| 低温 (<230K) | {data_summary['ea_by_temp']['low_temp']['n']} | {data_summary['ea_by_temp']['low_temp']['range'][0]:.3f}-{data_summary['ea_by_temp']['low_temp']['range'][1]:.3f} | {data_summary['ea_by_temp']['low_temp']['mean']:.3f} |
| 中温 (230-270K) | {data_summary['ea_by_temp']['mid_temp']['n']} | {data_summary['ea_by_temp']['mid_temp']['range'][0]:.3f}-{data_summary['ea_by_temp']['mid_temp']['range'][1]:.3f} | {data_summary['ea_by_temp']['mid_temp']['mean']:.3f} |
| 高温 (>270K) | {data_summary['ea_by_temp']['high_temp']['n']} | {data_summary['ea_by_temp']['high_temp']['range'][0]:.3f}-{data_summary['ea_by_temp']['high_temp']['range'][1]:.3f} | {data_summary['ea_by_temp']['high_temp']['mean']:.3f} |

---

## 2. 核心结论

{conclusions_content}

---

## 3. 详细推理过程

> 💡 **说明**: 以下展示AI分析的完整推理链条，包括每一步的思考过程、数据观察、逻辑推导和阶段性结论。

{reasoning_content}

---

## 4. 附录：证据汇总

### 4.1 证据强度说明

| 标记 | 含义 | 示例 |
|-----|------|------|
| ⭐⭐⭐ | 直接实验证据 | NMR、XRD、同位素效应 |
| ⭐⭐ | 间接证据 | Ea趋势、多段Arrhenius |
| ⭐ | 文献类比 | 无直接验证的推断 |

### 4.2 引用文献

1. Kreuer, K. D. (2004). *Chem. Rev.* - 质子传导机制框架
2. *Nature Chemistry* (2012) - 磷酸体系结构扩散
3. *Chem. Sci.* (2014) - Packed-acid机制
4. Wang et al. (2022). *Adv. Mater.* - AiCE低温性能
5. Agmon, N. (1995). *Chem. Phys. Lett.* - Grotthuss限速步骤

---

*本报告由增强版Phase 2深度分析器自动生成*
"""
        return report
    
    def _build_samples_table(self, samples: List[Dict]) -> str:
        """构建样品数据表格"""
        lines = ["| 样品ID | R | N | 分段数 | Ea范围 (eV) |",
                 "|--------|---|---|--------|-------------|"]
        
        for s in samples:
            ea_range = f"{min(s['eas']):.3f}-{max(s['eas']):.3f}" if s['eas'] else "N/A"
            r_val = f"{s['R']:.3f}" if s['R'] is not None else "N/A"
            n_val = f"{s['N']:.2f}" if s['N'] is not None else "N/A"
            lines.append(f"| {s['sample_id']} | {r_val} | {n_val} | {s['n_segments']} | {ea_range} |")
        
        return "\n".join(lines)
    
    def _save_with_header(
        self, 
        filepath: Path, 
        content: str, 
        title: str, 
        description: str
    ):
        """保存文件并添加标准头部"""
        header = f"""# {title}

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**说明**: {description}

---

"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + content)


def run_enhanced_analysis():
    """运行增强版分析"""
    import os
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    # 获取API Key
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        try:
            from config.api_config import get_api_key
            api_key = get_api_key()
        except:
            print("[ERROR] 未找到API Key")
            return
    
    # 初始化
    analyzer = EnhancedDeepAnalyzer(
        api_key=api_key,
        template_reports_dir=Path("analysis_output/phase2_reports"),
        model="openai/gpt-5.2"
    )
    
    output_dir = Path("analysis_output/phase2_enhanced_reports")
    
    # 分析S8
    print("\n" + "="*70)
    print("开始S8材料增强深度分析...")
    print("="*70)
    result_s8 = analyzer.analyze_material_with_reasoning('S8', output_dir)
    
    if result_s8.get('success'):
        print(f"\n✅ S8分析完成!")
        print(f"   生成文件:")
        for name, path in result_s8['files'].items():
            print(f"   - {name}: {Path(path).name}")
    else:
        print(f"\n❌ S8分析失败: {result_s8.get('error')}")
    
    # 分析S60
    print("\n" + "="*70)
    print("开始S60材料增强深度分析...")
    print("="*70)
    result_s60 = analyzer.analyze_material_with_reasoning('S60', output_dir)
    
    if result_s60.get('success'):
        print(f"\n✅ S60分析完成!")
        print(f"   生成文件:")
        for name, path in result_s60['files'].items():
            print(f"   - {name}: {Path(path).name}")
    else:
        print(f"\n❌ S60分析失败: {result_s60.get('error')}")
    
    print("\n" + "="*70)
    print("增强版深度分析完成!")
    print(f"输出目录: {output_dir}")
    print("="*70)


if __name__ == '__main__':
    run_enhanced_analysis()
