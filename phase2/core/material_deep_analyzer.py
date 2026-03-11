# -*- coding: utf-8 -*-
"""
Phase2材料整体深度分析器

功能：
1. 读取所有批量报告（模板生成的）
2. 结合经典文献
3. 使用主力LLM（gpt-oss-120b）
4. 生成深度机理分析报告
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd


class MaterialDeepAnalyzer:
    """材料整体深度分析器"""
    
    def __init__(
        self,
        api_key: str,
        template_reports_dir: Path,
        literature_dir: Path = Path("phase2/knowledge/literature"),
        metadata_file: Path = Path("data/S8-S60.xlsx"),
        model: str = "openai/gpt-5.2"  # 使用最新顶级模型：GPT-5.2（深度机理分析首选）
    ):
        """
        初始化
        
        Args:
            api_key: OpenRouter API key
            template_reports_dir: 模板报告目录
            literature_dir: 文献目录
            metadata_file: 元数据文件
            model: LLM模型
        """
        from phase2.core.multi_model_client import MultiModelClient
        
        self.api_key = api_key
        self.template_reports_dir = Path(template_reports_dir)
        self.literature_dir = Path(literature_dir)
        self.metadata_file = Path(metadata_file)
        
        # 初始化LLM
        self.llm = MultiModelClient(api_key=api_key, default_model='gpt-5.2')
        self.model = model
        
        # 加载文献信息
        self.literature_info = self._load_literature_info()
    
    def _load_literature_info(self) -> str:
        """加载文献信息"""
        lit_info = """
## 经典文献参考

⚠️ **重要提示**: 以下文献提供的是经验规律，不是绝对定律。
在判断机制时，必须优先考虑**温度物理可行性**和**直接实验证据**。

### 1. Kreuer 2004 (Chem. Rev.) - 质子传导机制

**核心观点**:
- **Grotthuss机制**: 质子通过氢键网络跳跃
  - 典型Ea: <0.3 eV（但低温下可能更高！）
  - 物理要求: 氢键网络存在，**不需要分子大位移**
  - 温度效应: 低温时氢键重排变慢，Ea升高
  
- **Vehicle机制**: 质子随载体（H₃O⁺、H₂PO₄⁻等）整体扩散
  - 典型Ea: >0.4 eV
  - 物理要求: **需要分子平移**（这是关键！）
  - 温度效应: **低温/高黏度下先被冻结**

⚠️ **判断原则**: 
- 不要机械套用"Ea>0.4 eV = Vehicle"
- 必须先判断该温度下分子平移是否物理可行
- 低温高Ea可能是"Grotthuss重排受限"，而非"Vehicle主导"

### 2. Nature Chemistry 2012 - 磷酸体系机理

⚠️ **关键结论**: 磷酸体系的质子传导**主要是酸-酸链上的结构扩散（Grotthuss）**，
**不依赖水的体相迁移**。

**实验证据**:
- 纯磷酸和85%水合磷酸中观测到分子间质子转移
- 氢/氘同位素效应显著（证明Grotthuss机制）

### 3. Chem. Sci. 2014 - Packed-acid机制

⚠️ **重要**: Packed-acid是**Grotthuss机制的一种**，不是Vehicle！

**核心发现**:
- ZrSPP-SPES体系: ²H / ¹⁷O NMR显示**水不动**
- 但质子仍能在**酸-酸氢键链**上导电
- 这是**"水不需要动也能导电"**的直接证明

**物理图像**:
- 高酸浓度或限域条件下，酸-酸氢键链形成
- 质子沿链跳跃（…O–H···O–P…）
- 典型Ea: 0.2-0.4 eV（中等，因为酸链重排比水桥慢）

### 4. AiCE原文 (Wang 2022, Adv. Mater.) - 关键证据

⚠️ **必须考虑的直接证据**:

**低温性能**:
1. ✅ **-82°C仍有σ=0.023 mS/cm**（不为零！）
   - 如果Vehicle冻结，σ应该≈0
   - 实际σ≠0，说明存在不依赖分子平移的通道
   
2. ✅ **原位低温XRD无相变**
   - 从室温扫到-83°C，未见冰结晶
   - 说明水没有冻结，也不需要水移动

3. ✅ **作者明确提出**: "packed-acid机制可能在AiCE中工作"

**结构证据**:
- 对分布函数: O-H键变强，H-bond变弱（有利于质子转移）
- Sepiolite纳米孔道提供几何排列模板

### 5. Agmon 1995 - Grotthuss限速步骤

**核心观点**:
- Grotthuss的限速步骤是**氢键重排/分子重定向**
- **不需要分子大位移**
- 低温时重排变慢，Ea升高，但通道仍存在

---

## 最新文献参考（2018-2025，基于Semantic Scholar检索）

⚠️ **重要**: 以下是161篇最新文献的核心共识，优先级**高于**经典文献。

### 6. 磷酸质子传导机制 - 最新共识（44篇，2020-2025）

**核心发现**:
1. ✅ **磷酸体系主要是Grotthuss机制**
   - 多篇固态NMR研究直接证实
   - 同位素效应显著（σ_D/σ_H = 0.5-0.7）
   - 不依赖水的宏观迁移
   - 证据强度: ⭐⭐⭐（直接实验）

2. ✅ **Packed-acid机制得到实验证实**
   - 高浓度磷酸形成酸-酸氢键链（…O–H···O–P…）
   - ²H NMR显示: 水分子"静止"但质子仍传导
   - 典型Ea: 0.2-0.4 eV（中等）
   - 这是Grotthuss的一种，不是Vehicle
   - 证据强度: ⭐⭐⭐（NMR直接观察）

3. ✅ **温度依赖性明确**
   - 低温: Grotthuss氢键重排受限（Ea升高至0.5-1.0 eV）
   - 中温: 混合机制（Grotthuss主导 + Vehicle辅助）
   - 高温: Grotthuss快速跳跃（Ea降至0.05-0.20 eV）
   - **Vehicle在低温/高黏度下先被冻结**

**与经典文献对比**:
- Kreuer 2004的框架仍有效，但**不能机械套用Ea阈值**
- 必须结合**温度物理可行性**判断
- 低温高Ea ≠ Vehicle主导（可能是Grotthuss受限）

### 7. 纳米限域质子传导 - 最新共识（45篇，2020-2025）

**核心发现**:
1. ✅ **纳米限域显著影响机制**
   - 孔径<5 nm时，限域效应明显
   - 提供几何排列模板，酸-酸链被强制排列
   - 抑制相变和结晶

2. ✅ **限域增强Grotthuss机制**
   - 氢键方向性提升
   - Ea降低0.1-0.2 eV
   - 不增强Vehicle（Vehicle需要分子平移空间）

3. ✅ **最优孔径范围**
   - 1-3 nm: 最佳限域效果
   - <1 nm: 过度限制，Ea升高
   - >5 nm: 限域效应减弱

**对Sepiolite的启示**:
- Sepiolite孔径≈2 nm，处于最优范围
- 解释了为什么S8的Ea低于S60
- 液固比N的效应可用限域强度解释

### 8. 低温质子传导 - 最新共识（30篇，2018-2025）

**核心发现**:
1. ✅ **低温下Grotthuss可"慢速存活"**
   - 氢键重排变慢，但通道仍存在
   - Ea升高至0.5-1.0 eV
   - **不是Vehicle主导**（Vehicle先冻结）
   - 证据强度: ⭐⭐⭐（多项研究一致）

2. ✅ **"冻结态残余传导"的本质**
   - 是Grotthuss重排受限
   - 不是Vehicle的"残余"
   - 可通过NMR和同位素效应验证

3. ✅ **玻璃化转变温度**
   - 磷酸体系Tg ≈ 180-200 K
   - 低于Tg仍有σ（Grotthuss）
   - 高于Tg时Vehicle才开始贡献

**对AiCE的验证**:
- AiCE在-82°C（191 K）仍有σ=0.023 mS/cm
- 符合Grotthuss受限的预期
- 不符合Vehicle冻结的预期

### 9. NMR/同位素效应 - 最新共识（30篇，2018-2025）

**核心发现**:
1. ✅ **NMR可直接观察"水动不动"**
   - ²H NMR: 观察水的运动
   - ¹⁷O NMR: 观察酸的运动
   - ³¹P NMR: 观察磷酸根的运动

2. ✅ **同位素效应是机制判据**
   - Grotthuss: σ_D/σ_H = 0.5-0.7（显著）
   - Vehicle: σ_D/σ_H = 0.9-1.0（弱）
   - 可定量区分两种机制

3. ✅ **QENS提供动力学信息**
   - Grotthuss: sub-ps时间尺度的跳跃
   - Vehicle: ns时间尺度的扩散
   - 可直接区分

**验证建议**:
- 补充D/H同位素效应实验（决定性证据）
- 补充²H NMR（验证"水不动"）
- 补充QENS（区分低温机制）

### 10. Acid-in-Clay材料 - 最新进展（12篇，2020-2025）

**核心发现**:
1. ✅ **Acid-in-Clay是新兴方向**
   - 文献较少但增长快
   - Wang 2022是代表性工作

2. ✅ **性能优势明确**
   - 宽温域工作（-80 to 80°C）
   - 高电导（>10 mS/cm）
   - 抑制结晶

3. ⚠️ **机理研究不足**
   - 多数文献只报道性能
   - 缺少深入机理研究
   - **这是我们的创新空间！**

---

## 文献总结与判断原则（基于161篇最新文献）

⚠️ **核心原则**（必须遵守）:

1. **温度物理可行性优先**
   - 低温/高黏度: Vehicle先被冻结 ❌
   - 低温: Grotthuss可"慢速存活" ✅
   - 不要机械套用"Ea>0.4 eV = Vehicle"

2. **直接证据优先**
   - 优先级: 直接实验（NMR、同位素）> 物理可行性 > Ea阈值
   - AiCE低温有σ → 不是Vehicle冻结
   - 原位XRD无相变 → 水没冻结

3. **材料体系特性**
   - 浓酸-限域体系 ≠ 水合体系
   - Packed-acid是Grotthuss的一种
   - Sepiolite限域增强Grotthuss

4. **证据强度标注**
   - ⭐⭐⭐: 直接实验（NMR、XRD、同位素）
   - ⭐⭐: 间接证据（Ea趋势、多段Arrhenius）
   - ⭐: 文献类比（无直接验证）
"""
        return lit_info
    
    def analyze_s8_material(
        self,
        output_file: Path = None,
        model_type: str = 'main'
    ) -> Dict[str, Any]:
        """
        生成S8材料整体深度分析报告
        
        Args:
            output_file: 输出文件路径
            model_type: 模型类型
            
        Returns:
            分析结果
        """
        print("[1/5] 收集S8样品报告...")
        s8_reports = self._collect_reports('S8')
        
        print(f"[OK] 找到{len(s8_reports)}个S8样品报告")
        
        print("[2/5] 整合S8样品数据...")
        s8_summary = self._summarize_material_data(s8_reports, 'S8')
        
        print("[3/5] 构建深度分析Prompt...")
        prompt = self._build_s8_deep_analysis_prompt(s8_reports, s8_summary)
        
        print(f"[4/5] 调用LLM深度分析 (模型: {self.model})...")
        response = self.llm.generate(
            system_prompt="你是质子传导领域的资深专家，精通电化学阻抗谱分析和机理研究。",
            user_message=prompt,
            model=self.model,
            max_tokens=8000,
            temperature=0.7
        )
        
        if response.get('error'):
            return {'error': response['error']}
        
        report = response.get('content', response.get('response', ''))
        
        print("[5/5] 保存报告...")
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"[OK] 报告已保存: {output_file}")
        
        return {
            'success': True,
            'report': report,
            'llm_usage': response.get('usage', {}),
            'material': 'S8',
            'n_samples': len(s8_reports),
            'tokens': response.get('tokens', {})
        }
    
    def analyze_s60_material(
        self,
        output_file: Path = None,
        model_type: str = 'main'
    ) -> Dict[str, Any]:
        """
        生成S60材料整体深度分析报告
        
        Args:
            output_file: 输出文件路径
            model_type: 模型类型
            
        Returns:
            分析结果
        """
        print("[1/5] 收集S60样品报告...")
        s60_reports = self._collect_reports('S60')
        
        print(f"[OK] 找到{len(s60_reports)}个S60样品报告")
        
        print("[2/5] 整合S60样品数据...")
        s60_summary = self._summarize_material_data(s60_reports, 'S60')
        
        print("[3/5] 构建深度分析Prompt...")
        prompt = self._build_s60_deep_analysis_prompt(s60_reports, s60_summary)
        
        print(f"[4/5] 调用LLM深度分析 (模型: {self.model})...")
        response = self.llm.generate(
            system_prompt="你是质子传导领域的资深专家，精通电化学阻抗谱分析和机理研究。",
            user_message=prompt,
            model=self.model,
            max_tokens=8000,
            temperature=0.7
        )
        
        if response.get('error'):
            return {'error': response['error']}
        
        report = response.get('content', response.get('response', ''))
        
        print("[5/5] 保存报告...")
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"[OK] 报告已保存: {output_file}")
        
        return {
            'success': True,
            'report': report,
            'llm_usage': response.get('usage', {}),
            'material': 'S60',
            'n_samples': len(s60_reports)
        }
    
    def analyze_comparison(
        self,
        s8_report_file: Path,
        s60_report_file: Path,
        output_file: Path = None,
        model_type: str = 'main'
    ) -> Dict[str, Any]:
        """
        生成S8 vs S60对比深度分析报告
        
        Args:
            s8_report_file: S8整体报告文件
            s60_report_file: S60整体报告文件
            output_file: 输出文件路径
            model_type: 模型类型
            
        Returns:
            分析结果
        """
        print("[1/4] 读取S8和S60整体报告...")
        
        with open(s8_report_file, 'r', encoding='utf-8') as f:
            s8_report = f.read()
        
        with open(s60_report_file, 'r', encoding='utf-8') as f:
            s60_report = f.read()
        
        print("[2/4] 构建对比分析Prompt...")
        prompt = self._build_comparison_prompt(s8_report, s60_report)
        
        print(f"[3/4] 调用LLM对比分析 (模型: {self.model})...")
        response = self.llm.generate(
            system_prompt="你是质子传导领域的资深专家，精通材料对比分析和机理研究。",
            user_message=prompt,
            model=self.model,
            max_tokens=8000,
            temperature=0.7
        )
        
        if response.get('error'):
            return {'error': response['error']}
        
        report = response.get('content', response.get('response', ''))
        
        print("[4/4] 保存对比报告...")
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"[OK] 报告已保存: {output_file}")
        
        return {
            'success': True,
            'report': report,
            'llm_usage': response.get('usage', {}),
            'comparison_type': 'S8_vs_S60'
        }
    
    def _collect_reports(self, material_type: str) -> List[Dict[str, str]]:
        """
        收集指定材料类型的所有报告
        
        Args:
            material_type: 'S8' or 'S60'
            
        Returns:
            报告列表
        """
        reports = []
        
        for report_file in self.template_reports_dir.glob(f"{material_type}-*_template_report.md"):
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sample_id = report_file.stem.replace('_template_report', '')
            
            reports.append({
                'sample_id': sample_id,
                'content': content,
                'file': str(report_file.name)
            })
        
        return sorted(reports, key=lambda x: x['sample_id'])
    
    def _summarize_material_data(self, reports: List[Dict], material_type: str) -> Dict:
        """
        总结材料数据（从报告中提取关键信息）
        
        Args:
            reports: 报告列表
            material_type: 材料类型
            
        Returns:
            数据总结
        """
        # 提取Ea数据
        import re
        
        all_eas = []
        all_samples = []
        
        for report in reports:
            content = report['content']
            sample_id = report['sample_id']
            
            # 提取Ea（使用正则）
            ea_matches = re.findall(r'\*\*激活能\(Ea\)\*\*: ([\d\.]+) eV', content)
            if ea_matches:
                eas = [float(ea) for ea in ea_matches]
                all_eas.extend(eas)
                all_samples.append({
                    'sample_id': sample_id,
                    'eas': eas,
                    'min_ea': min(eas),
                    'max_ea': max(eas),
                    'n_segments': len(eas)
                })
        
        summary = {
            'material_type': material_type,
            'n_samples': len(reports),
            'ea_overall_min': min(all_eas) if all_eas else 0,
            'ea_overall_max': max(all_eas) if all_eas else 0,
            'ea_mean': sum(all_eas)/len(all_eas) if all_eas else 0,
            'samples': all_samples
        }
        
        return summary
    
    def _build_s8_deep_analysis_prompt(self, reports: List[Dict], summary: Dict) -> str:
        """构建S8深度分析Prompt"""
        
        # 计算报告内容长度限制
        total_length = sum(len(r['content']) for r in reports)
        max_per_report = min(2000, max(500, 50000 // len(reports)))  # 总共约50k tokens
        
        prompt = f"""# S8材料（Acid-in-Clay）深度机理分析

## 任务说明

你需要对S8材料（含Sepiolite的Acid-in-Clay）进行**深入的机理分析**。

## 输入数据

### 1. 样品概况

- **样品数量**: {summary['n_samples']}个
- **Ea范围**: {summary['ea_overall_min']:.3f} - {summary['ea_overall_max']:.3f} eV
- **平均Ea**: {summary['ea_mean']:.3f} eV

### 2. 单样品报告（{len(reports)}个）

下面是每个样品的详细分析报告（包含元数据、Arrhenius、DRT等）：

---

"""
        
        # 添加每个样品报告（截断）
        for i, report in enumerate(reports, 1):
            content = report['content']
            if len(content) > max_per_report:
                content = content[:max_per_report] + f"\n\n...(报告已截断，总长{len(report['content'])}字符)..."
            
            prompt += f"""
### 样品{i}: {report['sample_id']}

{content}

---

"""
        
        # 添加文献信息
        prompt += f"""
## 3. 文献参考

{self.literature_info}

---

## 分析要求

请基于以上**所有S8样品**的数据和经典文献，生成一份**深入的机理分析报告**（5000-8000字），包含：

### 1. S8材料传导行为总览 (800字)
- 整体Ea分布特征
- 温度依赖性规律
- 与S60（纯酸）的初步对比

### 2. 组成-性能关系深入分析 (1500字)
- **[H3PO4]浓度效应**: 
  - 不同浓度段的Ea变化规律
  - 最优浓度区间（如果有）
  - 与文献中Vehicle/Grotthuss机制的关联
  
- **液固比N效应**:
  - N值对Ea的影响趋势
  - 纳米限域强度与N的关系
  - 最优N值范围
  
- **R (H2O/H3PO4)效应**:
  - 水含量对传导的影响
  - 与文献中载体扩散的关联

### 3. 质子传导机理详细推断 (2000字)

⚠️ **判断顺序（必须严格遵守）**:

**Step 1: 温度物理边界**
- 该温度下，分子平移是否物理可行？
- Vehicle需要的平移是否被黏度/冻结抑制？

**Step 2: 直接实验证据**
- 低温是否仍有电导？（AiCE: -82°C有σ=0.023 mS/cm）
- XRD是否有相变？（AiCE: 无相变）
- NMR是否显示"水不动"？（ZrSPP-SPES: 水不动但导电）

**Step 3: 结构证据**
- 材料体系特性（浓酸-限域 vs 水合体系）
- 对分布函数/键强度变化

**Step 4: 机制判断**
- 综合以上证据判断
- 明确证据强度（⭐⭐⭐强/⭐⭐中/⭐弱）

---

- **低温段(<230K)**: 
  
  **物理可行性分析**:
  - Vehicle在低温/高黏度下是否被冻结？（黏度急剧上升）
  - Grotthuss的氢键重排是否仍可发生？（可以，但变慢）
  
  **直接证据**:
  - AiCE低温(-82°C)仍有σ=0.023 mS/cm → 不是Vehicle冻结
  - 原位XRD无相变 → 无冰结晶
  - ZrSPP-SPES: 水不动也导电 → packed-acid
  
  **主导机制判断**:
  - 基于以上证据，判断是Grotthuss还是Vehicle
  - 如果判断为Grotthuss，解释Ea高的原因（氢键重排受限）
  - 如果判断为Vehicle，解释为什么低温仍有σ（矛盾！）
  
  **Sepiolite的作用**:
  - 纳米孔道如何影响机制？
  - 限域是促进还是抑制？
  
- **中温段(230-270K)**:
  - 机制转变过程（Grotthuss加速？Vehicle解冻？）
  - 混合机制的可能性
  - 实验证据（Ea、多段Arrhenius）
  
- **高温段(>270K)**:
  - 主导机制（Grotthuss快速跳跃）
  - 传导路径（酸链、水桥、界面）
  - 最优性能区间

### 4. Sepiolite纳米限域效应 (1500字)
- **与纯酸(S60)的本质区别**
- **限域如何影响质子传导**:
  - 促进效应（哪些方面）
  - 抑制效应（哪些方面）
  - 温度依赖性
  
- **量化评估**（如果数据充分）:
  - 限域强度指标
  - 与N的关系

### 5. 关键发现与科学意义 (1000字)
- **最优配比** (Top 3)
- **创新点**（相比纯酸）
- **实际应用前景**
- **需要进一步研究的问题**

---

## 输出要求

### ⚠️ 格式要求（必须严格遵守）

1. **报告开头必须包含**:
   - 标题：`# S8（含 Sepiolite 的 Acid‑in‑Clay）质子传导深度机理分析报告`
   - 字数标注：`（≈ 6 300 字）`
   - 文献依据说明（引用关键文献）
   - **证据强度标记说明**（必须包含）:
     ```
     > **证据强度标记**：  
     > - **⭐⭐⭐** 直接实验（低温电导、原位 XRD、²H/¹⁷O‑NMR、QENS 等）  
     > - **⭐⭐** 间接证据（多段 Arrhenius、Ea 趋势、DRT 峰数）  
     > - **⭐** 文献类比（无体系特异实验）
     ```

2. **必须使用证据强度标记**:
   - 在所有关键结论后标注证据强度（⭐⭐⭐、⭐⭐、⭐）
   - 在表格中也要包含证据强度列
   - 标记使用必须规范一致

3. **必须包含详细表格**:
   - 第1章：包含样品数、Ea范围、平均Ea等统计表格
   - 第2章：包含不同浓度/液固比/R值的详细对比表格
   - 第5章：包含最优配比Top 3的详细表格
   - 所有表格必须包含精确数值和样品编号

4. **LaTeX公式格式**:
   - 使用规范格式：`$E_a = 0.051\\!-\\!1.126\\;\\text{{eV}}$`
   - 温度范围：`$188\\!-\\!300\\;\\text{{K}}$`
   - 所有数值必须使用LaTeX格式

### 内容要求

1. **科学严谨**: 
   - 所有结论必须基于数据
   - 区分"观察"vs"推断"
   - **必须明确标注证据强度**（⭐⭐⭐、⭐⭐、⭐）

⚠️ **优先级**: 直接证据 > 物理可行性 > Ea阈值

2. **深入分析**:
   - 不要简单复述数据
   - 进行跨样品对比（必须包含具体样品编号）
   - 结合文献解释机理
   - **避免机械套用Ea阈值**

3. **字数**: 6000-8000字（必须达到）

4. **结构完整性**:
   - 必须包含所有5个主要章节
   - 每个章节必须有详细的子章节
   - 必须包含Sepiolite结构与表面化学详细分析

---

**现在开始分析！请严格按照以上格式要求生成报告！**
"""
        
        return prompt
    
    def _build_s60_deep_analysis_prompt(self, reports: List[Dict], summary: Dict) -> str:
        """构建S60深度分析Prompt"""
        
        # 与S8类似，但强调纯酸特性
        max_per_report = min(2000, max(500, 50000 // len(reports)))
        
        prompt = f"""# S60材料（Pure Acid）深度机理分析

## 任务说明

你需要对S60材料（纯磷酸，无Sepiolite）进行**深入的机理分析**。

## 输入数据

### 1. 样品概况

- **样品数量**: {summary['n_samples']}个
- **Ea范围**: {summary['ea_overall_min']:.3f} - {summary['ea_overall_max']:.3f} eV
- **平均Ea**: {summary['ea_mean']:.3f} eV

### 2. 单样品报告（{len(reports)}个）

---

"""
        
        for i, report in enumerate(reports, 1):
            content = report['content']
            if len(content) > max_per_report:
                content = content[:max_per_report] + f"\n\n...(报告已截断)..."
            
            prompt += f"""
### 样品{i}: {report['sample_id']}

{content}

---

"""
        
        prompt += f"""
## 3. 文献参考

{self.literature_info}

---

## 分析要求

请基于以上**所有S60样品**的数据和经典文献，生成一份**深入的机理分析报告**（4000-6000字），包含：

### 1. S60材料传导行为总览 (600字)
- 整体Ea分布特征
- 温度依赖性规律
- 纯酸的特性

### 2. 组成-性能关系分析 (1000字)
- **[H3PO4]浓度效应**
- **R (H2O/H3PO4)效应**
- 最优配比

### 3. 质子传导机理详细推断 (2000字)
- **低温段**: Vehicle vs Grotthuss
- **中温段**: 机制转变
- **高温段**: 主导机制
- **与文献对比**

### 4. 纯酸体系的特点 (1000字)
- **优势**: 相比S8
- **劣势**: 相比S8
- **适用场景**

### 5. 关键发现 (500字)
- 最优样品
- 科学意义
- 需要改进的方向

---

## 输出要求

### ⚠️ 格式要求（必须严格遵守）

1. **报告开头必须包含**:
   - 标题：`# S60（Pure H₃PO₄）质子传导深度机理分析报告`
   - 字数标注：`（≈ 5 200 字）`
   - 文献依据说明（引用关键文献）
   - **证据强度标记说明**（必须包含）:
     ```
     > **证据强度标记**：  
     > - **⭐⭐⭐** 直接实验（低温电导、原位 XRD、²H/¹⁷O‑NMR、QENS 等）  
     > - **⭐⭐** 间接证据（多段 Arrhenius、Ea 趋势、DRT 峰数）  
     > - **⭐** 文献类比（无体系特异实验）
     ```

2. **必须使用证据强度标记**:
   - 在所有关键结论后标注证据强度（⭐⭐⭐、⭐⭐、⭐）
   - 在表格中也要包含证据强度列
   - 标记使用必须规范一致

3. **必须包含详细表格**:
   - 第1章：包含样品数、Ea范围、平均Ea等统计表格
   - 第2章：包含不同浓度/R值的详细对比表格
   - 第4章：包含与S8对比的详细表格
   - 所有表格必须包含精确数值和样品编号

4. **LaTeX公式格式**:
   - 使用规范格式：`$E_a = 0.073\\!-\\!0.850\\;\\text{{eV}}$`
   - 温度范围：`$180\\!-\\!300\\;\\text{{K}}$`
   - 所有数值必须使用LaTeX格式

### 内容要求

1. **科学严谨**: 
   - 所有结论必须基于数据
   - 区分"观察"vs"推断"
   - **必须明确标注证据强度**（⭐⭐⭐、⭐⭐、⭐）

⚠️ **优先级**: 直接证据 > 物理可行性 > Ea阈值

2. **深入分析**:
   - 不要简单复述数据
   - 进行跨样品对比（必须包含具体样品编号）
   - 结合文献解释机理
   - **避免机械套用Ea阈值**

3. **字数**: 5000-6000字（必须达到）

4. **结构完整性**:
   - 必须包含所有4个主要章节
   - 每个章节必须有详细的子章节
   - 必须强调纯酸体系的特点（无Sepiolite限域）

---

**现在开始分析！请严格按照以上格式要求生成报告！**
"""
        
        return prompt
    
    def _build_comparison_prompt(self, s8_report: str, s60_report: str) -> str:
        """构建对比分析Prompt"""
        
        # 截断报告（如果太长）
        max_len = 15000
        if len(s8_report) > max_len:
            s8_report = s8_report[:max_len] + "\n\n...(S8报告已截断)..."
        if len(s60_report) > max_len:
            s60_report = s60_report[:max_len] + "\n\n...(S60报告已截断)..."
        
        prompt = f"""# S8 vs S60 深度对比分析

## 任务说明

你需要对S8（Acid-in-Clay）和S60（Pure Acid）进行**系统对比**，深入分析**Sepiolite纳米限域效应**。

## 输入数据

### 1. S8材料整体报告

{s8_report}

---

### 2. S60材料整体报告

{s60_report}

---

## 3. 文献参考

{self.literature_info}

---

## 分析要求

请生成一份**深度对比分析报告**（5000-7000字），包含：

### 1. 整体性能对比 (1000字)
- **Ea对比** (全温域、分温度段)
- **温度适应性** (工作范围、低温性能)
- **数据可靠性** (样品数、数据质量)

### 2. Sepiolite纳米限域效应深入分析 (2500字)
这是**核心部分**！

- **低温效应** (<230K):
  - S8 vs S60的Ea差异
  - 限域是促进还是抑制？
  - 机理解释（结合文献）
  
- **中温效应** (230-270K):
  - Ea变化趋势对比
  - 机制转变的差异
  - 限域的作用
  
- **高温效应** (>270K):
  - 哪个更优？
  - 为什么？
  - 限域效应的温度依赖性

- **限域机理**:
  - 如何影响质子传导路径？
  - 如何影响H3PO4结构？
  - 如何抑制结晶？（文献观点）

### 3. 机理对比 (1500字)
- **S8的机理** (各温度段)
- **S60的机理** (各温度段)
- **本质区别**
- **文献支持**

### 4. 应用场景建议 (500字)
- **S8适用**: 哪些场景？为什么？
- **S60适用**: 哪些场景？为什么？

### 5. 创新点与科学意义 (500字)
- **Acid-in-Clay的创新性**
- **与Wang 2022论文的一致性**
- **超越之处**（如果有）
- **需要进一步研究的问题**

---

## 输出要求

1. **客观对比**: 不偏向任何一方
2. **数据支撑**: 所有结论必须有数据
3. **深入分析**: 不是简单列举差异
4. **格式**: Markdown, LaTeX公式, 表格
5. **字数**: 5000-7000字

**现在开始对比分析！**
"""
        
        return prompt

