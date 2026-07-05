# G4 — related-work positioning + references (2026-06-22)

> 目的:明确本文相对 2026 既有"自驱动/agent/可复现-UQ/claim-审计"工作的增量,并给出真实参考锚点。
> 纪律(nature-polishing/citation):**不编造引用**;以下条目来自本项目检索/基线表的真实结果;
> **最终投稿前每条 DOI/arXiv 需用 `nature-citation` 复核**。定位 = "复现地板 + 可辨识性天花板"的组合,
> 在 EIS-only、真实独立重复条件下;这是与下列工作的差异轴。

## 1. 定位对照表(本文 vs 2026 代表工作)

| 工作(真实锚点) | 证据来源 | 复现地板(实测) | 诚实 null | 可辨识性封顶 | 与本文差异 |
|---|---|---|---|---|---|
| Hierarchical multi-agent LLM, **npj Comput. Mater. 2026** | DFT 模拟 | ✗ | ✗ | ✗ | 它=计算加速;本文=湿实验可信边界 |
| A-Lab GPSS / agentic SDL(锂卤化物),**arXiv 2604.11957** | 真机器人合成 | ✗(命中率上升,无地板) | 部分 | ✗ | 它=规模化合成;本文=量化复现极限+主张许可 |
| LLM-Guided BO(LGBO),**arXiv 2605.17976** | 干基准+1 湿例 | ✗ | ✗ | ✗ | 它=BO 收敛更快;本文=诚实 null + 地板解释 |
| Multi-stage BO for SDL,**Digital Discovery 2026 (D5DD00572H)** | 仿真+回溯 | ✗ | — | ✗ | 它=代理测量加速;本文=把噪声地板作为采集约束 |
| ADePT 自主实验室评估,**Comm. Chem. 2026 (s42004-026-01932-9)** | 框架/评估 | ✗ | — | ✗ | 它=机器人能力评估;本文=科学主张可信度评估 |
| SDL 2.0 综述,**Materials Horizons 2026 (D5MH01984B)** | 综述 | — | — | — | 提出愿景;本文给可测协议(地板/天花板) |
| Reasoning-to-Simulation(AI4Mat-ICLR 2026) | MD 模拟 | ✗ | 自承需实验 | ✗ | 它=模拟验证;本文=真实 EIS 验证 |
| **本文** | **EIS-only 真实独立重复** | **✅ 0.245–0.33 dex** | **✅ 线B 候选差<地板** | **✅ 描述符可辨识/机理不可辨识(ΔR²=0.006)** | — |

**一句话定位**:据我们所知,**同时**(i)从真实独立重复**实测**制造复现地板、(ii)以**结构可辨识性**把 agent 主张形式化封顶、(iii)把闭环**诚实 null** 定量归因到该地板,在 EIS-only/表征受限设定下,尚无直接对应工作;最接近的是误支持/claim-审计与可复现-UQ 各自的单点,但未在真实湿实验重复 + 传输-only 约束下合并。

## 2. agent-vs-baseline 对照(本项目已有,真实)

`m6_baseline_ablation`(M6–M8,真 LLM gpt-5.4 / 跨模型盲评)提供了**强对照臂**:
- M7:污染池中 governed LLM **0% 干扰纳入** vs popularity **100%**(5 seed)。
- M8-1:critic+memory 把过度声称 **40→0**(护栏 ON/OFF)。
- M8-3:跨家族盲评 governed **4.3** ≫ random 2.1 ≫ popularity **1.0**(2 judge×3 seed)。
→ 可作为"治理 agent 相对朴素基线的可证伪增量"写入,**这部分对照已达投稿级**(诚实边界:小池、单候选池,见各报告)。

## 3. 真实参考锚点(投稿前用 nature-citation 复核 DOI)

**域内材料基线(`ea_benchmark_table.csv`,有出处)**
- 母体系 acid-in-clay(海泡石/H₃PO₄):σ₂₅°C≈15 mS/cm、Ea≈0.12 eV、−82°C≈0.023 mS/cm — **PubMed 35443084**(LIT-AICE-2022)。
- 低 Ea 框架:POP,**J. Mater. Chem. A 2020, 10.1039/c9ta06807d**(Ea≈0.039);MFM-300(Cr),**JACS 2022, 10.1021/jacs.2c04900**(Ea≈0.04)。
- 淀粉-壳聚糖共混质子导体(材料"类"已存在,佐证新颖度边界):cites=212 条(OpenAlex,标题级)。

**方法/agent/SDL 邻域(2026)**
- Hierarchical multi-agent LLM,npj Comput. Mater.,**10.1038/s41524-026-02139-1**。
- Agentic SDL(锂卤化物 spinel),**arXiv:2604.11957**。
- LLM-Guided BO(LGBO),**arXiv:2605.17976**。
- Multi-stage BO for SDL,Digital Discovery 2026,**10.1039/D5DD00572H**。
- ADePT,Comm. Chem. 2026,**s42004-026-01932-9**。
- SDL 2.0 综述,Mater. Horiz. 2026,**10.1039/D5MH01984B**。

**EIS 非唯一性 / DRT 病态(支撑可辨识性封顶)**
- RL-ECM agent "distinguishing such topologies using EIS data alone remains an open problem"(arXiv 2604.27266,**待 nature-citation 复核**)。
- DRT 正则化主观/病态反演(OSTI 1957991 / KIT,**待复核**)。

## 4. related-work 段落(期刊体草稿,可入正文)

Autonomous and self-driving laboratories have advanced rapidly, from agentic large-language-model
reasoning that accelerates simulation-based catalyst search to robotic platforms that synthesise
and screen air-sensitive inorganic conductors, and from language-model-guided Bayesian
optimisation to multi-stage acquisition that exploits cheap proxy measurements. These studies
optimise for the performance of the returned material and typically validate either in
simulation or through automated screening. A complementary line on autonomous-laboratory
evaluation and on uncertainty calibration has begun to ask how trustworthy such systems are.
What remains uncommon is a treatment that quantifies, from the same inexpensive transport data
used for discovery, both the fabrication reproducibility floor that limits what can be measured
and the structural-identifiability ceiling that limits what can be claimed, and that reports the
closed-loop outcome faithfully when these limits bind. The present work addresses this gap in a
characterisation-frugal, impedance-only setting, and pairs it with a governed agent whose
candidate generation and ranking are shown, against naive baselines, to resist high-citation
off-topic distractors.
