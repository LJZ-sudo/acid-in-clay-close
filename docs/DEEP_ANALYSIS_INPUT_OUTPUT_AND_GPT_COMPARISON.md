# Phase2 深度机理分析：输入/输出说明与 GPT 对比实验设计

**文档目的**：说明 S8 深度机理分析报告的生成流程、模型输入/输出，以及如何设计「系统报告 vs 通用大模型（如 GPT）」的对比实验与提示词。

---

## 一、close 文件夹与 phase2 结构概览

### 1.1 close 整体结构

- **phase1**：EIS 解析、Arrhenius 分段等，产出 `*_analysis_result.json`
- **phase2**：单样品机理报告 + **材料级深度机理分析**（本报告重点）
- **phase3**：ML 训练、Meyer-Neldel、step4 用 S8 深度报告解析 R/N 区间等
- **output**：
  - `phase2_reports/`：单样品 `*_mechanism_report.md`
  - **`deep_analysis/`**：S8/S60 深度报告 `*_deep_mechanism_analysis.md`、`S8_deep_analysis_prompt.txt`

### 1.2 phase2 中与深度报告相关的核心文件

| 文件 | 作用 |
|------|------|
| `phase2/run_s8_deep_analysis.py` | S8 深度分析**主入口**：加载数据→拼 prompt→调 API→写报告 |
| `phase2/prompts/deep_analysis_prompts.py` | 另一套 prompt 模板（`build_deep_analysis_system_prompt` / `build_deep_analysis_user_prompt`），当前 run_s8 未直接使用，但可复用思路 |
| `phase2/data/material_knowledge_base.py` | **知识库**：黏土/酸/质子机理/EIS 形态/Arrhenius 分段等 |
| `run_phase2_complete.py` | 一键跑 Phase2，其中 Part2 调用 `generate_s8_deep_analysis()`，逻辑与 `run_s8_deep_analysis.py` 一致 |

---

## 二、深度机理分析报告是如何生成的

### 2.1 流程概览

```
Phase1 结果 (JSON) + Phase2 单样品报告 (MD)
           ↓
   load_segment_data_from_json() + load_sample_reports()
           ↓
   summarize_sample_reports() → 单样品关键发现摘要
           ↓
   material_knowledge_base 中取出：海泡石、磷酸、质子机理、EIS 形态、Arrhenius 分段
           ↓
   build_deep_analysis_prompt() → 拼成完整 user prompt
           ↓
   call_opus45(system_prompt, user_prompt)  // Claude Opus 4.5
           ↓
   响应写入 S8_deep_mechanism_analysis.md
```

### 2.2 数据来源

- **Segment 数据**：`output/phase1_results/S8*_analysis_result.json`  
  - 每个样品：`sample_id`, `R`, `N`，以及 `arrhenius.segments[]`（`temp_range_K`/`T_range_K`, `Ea_eV`, `r_squared`, `ln_sigma0` 等）
- **单样品报告**：`output/phase2_reports/S8*_mechanism_report.md`  
  - 被汇总成「关键发现」短摘要（每样品约 1～2 条假设/依据），写入 prompt 的「2.2 单样品报告关键发现汇总」

---

## 三、模型的输入是什么（系统侧）

调用大模型时是 **两条消息**：**system** + **user**。

### 3.1 System 提示（角色与原则）

- **内容**（来自 `run_s8_deep_analysis.py` 的 `call_opus45`）：
  - 固定一句：*「你是电化学和固态离子导体领域的顶级专家，专门研究限域纳米材料中的质子传导机理。请提供深入、全面、科学严谨的分析。」*
- **作用**：设定角色，不包含本项目的材料知识或数据。

### 3.2 User 提示（完整任务 + 知识库 + 数据）

User 提示由 `build_deep_analysis_prompt()` 生成，**已保存为** `output/deep_analysis/S8_deep_analysis_prompt.txt`，结构如下：

| 区块 | 内容来源 | 是否属于「知识库」 |
|------|----------|--------------------|
| **1. 背景信息** | | |
| 1.1 材料基本信息 | 固定：S8、海泡石、磷酸 | 否（仅标识） |
| 1.2 海泡石材料知识 | `CLAY_DETAILED_KNOWLEDGE['Sepiolite']` | **是** |
| 1.3 磷酸体系知识 | `ACID_DETAILED_KNOWLEDGE['H3PO4']` | **是** |
| 1.4 质子传导机理背景 | `PROTON_MECHANISM_KNOWLEDGE` | **是** |
| 1.5 EIS曲线形态解释 | `EIS_MORPHOLOGY_KNOWLEDGE` | **是** |
| 1.6 Arrhenius分段解释 | `ARRHENIUS_SEGMENTATION_KNOWLEDGE` | **是** |
| **2. 实验数据汇总** | | |
| 2.1 数据统计 | 由 segment 统计：样品数、T/R/N/Ea 范围 | 否（数据） |
| 2.2 单样品报告关键发现汇总 | `summarize_sample_reports(reports)` | 否（数据） |
| **3. 分析任务** | 固定的 6 大部分及子问题 | 否（任务说明） |
| **4. 输出要求** | 中文、科学论证、引用知识库、数值预测、≥3000 字 | 否 |

因此：

- **系统调用大模型时的输入** = **System 消息** + **User 消息**（即上述完整 prompt，其中 **1.2～1.6 即知识库**）。

---

## 四、模型的输出是什么

- **格式**：Markdown 文本，先由脚本写入标题与元数据，再拼接模型返回的正文。
- **结构**：报告**必须包含以下 6 个部分**（与 prompt 中「3. 分析任务」一致）：

1. **EIS 曲线形态机理解释**（类直线 vs 半圆+直线、与限域关系）
2. **Arrhenius 斜率变化机理**（分段、断点、Meyer-Neldel）
3. **温度依赖性机理分析**（室温/低温、Grotthuss/Vehicle/Packed-acid）
4. **最优配比预测**（高温/低温 R-N、协同关系）
5. **实验建议与新材料预测**（验证实验、酸替换等）
6. **应用场景分析**（适用场景、温度限制、优劣势）

- **实际产物**：`output/deep_analysis/S8_deep_mechanism_analysis.md`（含生成时间、模型名、样品数等元数据 + 上述 6 部分正文）。

---

## 五、与 GPT 对比实验的设计思路

目标：**对比「本系统生成的 S8 深度报告」与「通用大模型（如 GPT）在可控条件下的分析报告」**，以便评估领域知识库与结构化 prompt 的增益。

核心问题：  
- **系统侧**：输入 = 知识库 + 数据汇总 + 任务说明（即当前 `S8_deep_analysis_prompt.txt`）。  
- **GPT 侧**：若要做公平对比，需要明确「给 GPT 的输入」是否包含同一份知识库。

下面给出两种常见对比方案，以及「系统输入」与「给 GPT 的输入」的对应关系。

---

### 5.1 方案 A：公平对比「有无知识库」的差异

- **目的**：看**仅靠通用能力**（不喂领域知识库），GPT 能否写出与系统报告同水平、同结构的分析。
- **系统侧输入**（保持不变）：  
  - System：专家角色一句。  
  - User：**完整 prompt** = 知识库(1.2～1.6) + 数据(2.1～2.2) + 任务(3) + 输出要求(4)。  
  - 对应文件：可直接用 **`output/deep_analysis/S8_deep_analysis_prompt.txt`**（系统调用时就是这样传的）。
- **给 GPT 的输入**（不包含知识库）：  
  - System：可与系统一致（例如同一句专家角色），或略简化为「你是电化学与质子导体领域专家」。  
  - User：**仅包含**  
    - 1.1 材料基本信息（S8、海泡石、磷酸）；  
    - 2.1 数据统计；  
    - 2.2 单样品报告关键发现汇总；  
    - 3. 分析任务（6 大部分及子问题）；  
    - 4. 输出要求。  
  - **不包含**：1.2～1.6（海泡石/磷酸/质子机理/EIS/Arrhenius 的详细知识库）。  
- **对比维度**：  
  - 是否覆盖 6 大部分、是否引用具体数据、机理表述是否与文献共识一致（如「低温高 Ea 不简单等于 Vehicle」）、数值预测是否合理等。

这样设计时：**系统 = 知识库 + 数据 + 任务；GPT = 数据 + 任务**，便于突出「知识库」的贡献。

---

### 5.2 方案 B：同输入对比「不同模型」的差异

- **目的**：在**输入完全一致**的前提下，比较 Claude Opus 4.5 与 GPT 的报告质量差异（控制变量为模型，而非是否有知识库）。
- **系统侧输入**：同上，即完整 `S8_deep_analysis_prompt.txt`（含知识库）。  
- **给 GPT 的输入**：  
  - **与系统完全一致**：把 **同一份** `S8_deep_analysis_prompt.txt` 作为 User 消息，System 可沿用同一句专家角色（或针对 GPT 微调一句）。  
- **对比维度**：结构完整性、数据引用准确性、机理深度、R-N 预测与可接受范围是否明确等。

此时：**系统与 GPT 的输入相同（都含知识库）**，差异仅来自模型与接口。

---

### 5.3 小结：系统 vs GPT 的输入对应关系

| 对比目的         | 系统调用时的输入                     | 提供给 GPT 的输入                         |
|------------------|--------------------------------------|-------------------------------------------|
| 方案 A：有无知识库 | 完整 prompt（知识库+数据+任务）      | **仅数据+任务**（去掉 1.2～1.6 知识库）   |
| 方案 B：同输入比模型 | 完整 prompt（知识库+数据+任务）      | **同一份完整 prompt**（含知识库）         |

- **系统提供的输入**：始终包含知识库（来自 `material_knowledge_base.py`），已全部写在 `S8_deep_analysis_prompt.txt` 里。  
- **若要做「不含知识库」的对比**：需要从该文件中**删掉 1.2～1.6 整块**，仅保留 1.1、2、3、4，作为「给 GPT 的 prompt」；不要给 GPT 注入本项目的材料/机理知识库。  
- **若要做「同输入」的对比**：直接把 `S8_deep_analysis_prompt.txt` 原样作为 GPT 的 User 消息即可。

---

## 六、提示词与文件层面的具体做法

### 6.1 系统侧（当前已满足）

- 输入：  
  - System：`run_s8_deep_analysis.py` 里 `call_opus45()` 的 `system` 字符串。  
  - User：`build_deep_analysis_prompt(...)` 的返回值，与 **`output/deep_analysis/S8_deep_analysis_prompt.txt`** 内容一致（含知识库）。
- 输出：`output/deep_analysis/S8_deep_mechanism_analysis.md`。

### 6.2 为 GPT 准备「仅数据+任务」的 prompt（方案 A）

- 从 `S8_deep_analysis_prompt.txt` 中：  
  - **保留**：1.1、2.1、2.2、3、4（及标题与分隔）。  
  - **删除**：1.2、1.3、1.4、1.5、1.6 整段（从「### 1.2 海泡石材料知识」到「### 1.6 Arrhenius分段解释」 inclusive）。  
- 可在 1.1 后加一句说明，例如：「以下仅提供材料标识与实验数据，请基于你的电化学与质子导体知识进行分析。」  
- 将结果另存为例如：`output/deep_analysis/S8_deep_analysis_prompt_for_GPT_no_kb.txt`，便于复现与对比。

### 6.3 为 GPT 准备「与系统同输入」的 prompt（方案 B）

- 直接使用 **`output/deep_analysis/S8_deep_analysis_prompt.txt`** 作为 GPT 的 User 消息即可，无需改内容。  
- 若希望可复现，可另存一份副本，如 `S8_deep_analysis_prompt_for_GPT_with_kb.txt`（内容与现有 prompt 相同）。

### 6.4 System 消息建议（GPT）

- 方案 A/B 均可使用与系统类似的角色设定，例如：  
  *「你是电化学和固态离子导体领域的专家，专门研究限域纳米材料中的质子传导机理。请基于所给数据与任务，提供深入、全面、科学严谨的分析。」*  
- 若 GPT 对长 prompt 有长度限制，可考虑只保留「2. 实验数据汇总」和「3. 分析任务」+「4. 输出要求」，并在前面用 1～2 句话说明材料为 S8（海泡石+磷酸）。

---

## 七、对比时可用的评估维度（建议）

1. **结构**：6 大部分是否都出现、是否有明确小标题。  
2. **数据引用**：是否引用 2.1/2.2 中的具体样品、温度、Ea、R/N 等。  
3. **机理一致性**：是否出现「低温高 Ea = Vehicle」等与文献共识不符的表述；是否区分 Grotthuss/Packed-acid/Vehicle。  
4. **R-N 与可接受范围**：第四部分是否给出高温/低温 R、N 及可接受范围（与 step4 解析一致更佳）。  
5. **可验证性**：实验建议、新材料预测是否具体、可操作。

---

## 八、总结

- **深度机理报告生成**：`phase2/run_s8_deep_analysis.py` 读取 Phase1 JSON + Phase2 单样品报告，从 `material_knowledge_base` 取知识库，拼成 System + User，调 Claude Opus 4.5，写出 `S8_deep_mechanism_analysis.md`。  
- **模型输入**：System = 专家角色；User = 知识库(1.2～1.6) + 数据汇总(2.1～2.2) + 任务(3) + 输出要求(4)。  
- **模型输出**：6 部分 Markdown 深度机理报告。  
- **与 GPT 对比**：  
  - **方案 A**：给 GPT **不含知识库**的 prompt（仅 1.1+2+3+4），突出知识库的增益。  
  - **方案 B**：给 GPT **与系统相同的完整 prompt**（含知识库），比较模型差异。  
- **系统提供的输入**包含知识库；**要做公平对比时**，给 GPT 的输入应**不包含** 1.2～1.6 知识库；要做同输入对比时，给 GPT 的输入**与系统完全一致**即可。  
- 现有 `output/deep_analysis/S8_deep_analysis_prompt.txt` 即为系统真实输入，可直接用于复现与方案 B；从中去掉 1.2～1.6 即可得到方案 A 的 GPT 用 prompt。
