# S60 深度机理分析报告生成方案（参考 S8 与 close/phase2）

**目的**：在已有 S8 深度分析流程基础上，说明如何生成「每个 S60 样品的单样品报告」和「S60 材料级深度分析报告」，便于后续实现时对齐逻辑。

**状态**：阶段 1、阶段 2 均已执行完成；S60 材料级深度报告已生成。

---

## 生成结果概览（已生成）

### 阶段 1 产出

- **单样品机理报告**：共 **17 份** `S60-xxx_mechanism_report.md`，位于 `close/output/phase2_reports/`。
- **覆盖样品**：S60-1-1-1、S60-1-3-1、S60-2-1-1 ～ S60-2-14-1 等 16 个样品（部分样品有多份子实验报告）。

### 阶段 2 产出

- **S60 材料级深度机理报告**：`close/output/deep_analysis/S60_deep_mechanism_analysis.md`
  - **生成时间**：2026-01-30
  - **模型**：Claude Opus 4.5
  - **基于数据**：16 个样品、17 份单样品报告、62 个 Arrhenius 分段；温度范围约 182–294 K，R 范围约 0.007–1.041。
- **Prompt 备份**：`close/output/deep_analysis/S60_deep_analysis_prompt.txt`（供复现或调整用）。

### 报告内容要点（摘要）

- **定位**：S60 为纯 H₃PO₄ 液体电解质（无黏土、无限域），作为 Acid-in-Clay（如 S8）的「无限域基线」对比对象。
- **EIS 形态**：室温/高温类直线（Rb 极小、Warburg 扩散主导）；低温半圆+尾（水相变、Rb 增大、介电弛豫进入测量窗口）；与 S8 限域体系在界面数量、氢键连续性、水分状态上的差异有简述。
- **Arrhenius 与机理**：多段 Ea（0.047–0.939 eV）对应 Grotthuss / Vehicle / 水相变耦合；低温高 Ea 更可能为 Grotthuss 重排受限而非 Vehicle 主导；Meyer-Neldel 补偿效应有讨论。
- **温度依赖性**：高温高效 Grotthuss、中温混合、低温受限 Grotthuss；水相变（冰点、过冷、玻璃化）对传导路径的影响。
- **R 与性能**：R（酸/水摩尔比）对 Ea 与电导率的影响及较优 R 区间。
- **应用与对比**：纯酸体系适用场景、与 S8 的优劣势、作为基线的研究角色。

上述要点可直接用于论文 Discussion 中「S60 基线机理」与「S8 vs S60」的叙述；与 Phase 3 的 ΔEa、Meyer-Neldel 数值结果一致。

---

## 一、S8 深度分析报告生成逻辑（现有）

### 1.1 两阶段流程

| 阶段 | 脚本 | 输入 | 输出 |
|------|------|------|------|
| **阶段 1：单样品机理报告** | `phase2/run_batch_reports.py` | `close/output/phase1_results/S8*_analysis_result.json` | `close/output/phase2_reports/S8-xxx_mechanism_report.md`（每个样品一份） |
| **阶段 2：材料级深度分析** | `phase2/run_s8_deep_analysis.py` | ① 上述 `S8*_mechanism_report.md` ② `phase1_results/S8*_analysis_result.json`（抽 segment 统计） | `close/output/deep_analysis/S8_deep_mechanism_analysis.md` |

### 1.2 阶段 1 详细逻辑（run_batch_reports.py）

- 遍历 `phase1_results/*_analysis_result.json`，按 `sample_id` 前缀过滤材料（如 `--material S8` 则只处理 S8）。
- 对每个 JSON：
  - 用 **SampleMechanismGenerator** 读取 JSON → `convert_to_report_format()` 转为 mechanism 所需格式 → 调 **build_mechanism_prompt(report)**（来自 auto_control.modules.mechanism_report）生成 prompt。
  - 调用 LLM（默认 Claude Sonnet），将返回内容写入 `{sample_id}_mechanism_report.md`。
- 输出目录：`close/output/phase2_reports/`。  
- **S60 已支持**：`run_batch_reports.py` 的 WHITELIST 含 S60，执行 `--material S60` 即可为所有 S60 样品生成 `S60-xxx_mechanism_report.md`。需确认 `SampleMechanismGenerator` / `build_mechanism_prompt` 对 S60（无黏土、N 常为 0）的兼容性；若有 S8 专用分支，需扩展为按 material_type 区分或通用化。

### 1.3 阶段 2 详细逻辑（run_s8_deep_analysis.py）

1. **load_sample_reports(report_dir, 'S8')**  
   - 在 `phase2_reports/` 下 glob `S8*_mechanism_report.md`，读入每份报告内容，得到 `List[Dict]`（含 sample_id、content、length）。

2. **load_segment_data_from_json(data_dir, 'S8')**  
   - 在 `phase1_results/` 下 glob `S8*_analysis_result.json`，从每个 JSON 的 `arrhenius.segments` 抽 segment 行（sample_id, R, N, T_avg_K, Ea_eV, r_squared, ln_sigma0），汇总为 DataFrame。  
   - S60 的 JSON 同样有 `arrhenius.segments` 和 `R`；`N` 可为 0，现有逻辑可直接复用。

3. **segment_stats**  
   - 由上述 DataFrame 计算 n_samples、n_segments、T_min/max、R_min/max、N_min/max、Ea_min/max，供 prompt 中「数据统计」使用。S60 无 N 时 N_min/max 可为 0。

4. **summarize_sample_reports(reports)**  
   - 从各单样品报告正文中抽取与「假设/ hypothesis」相关的句子，拼成简短摘要。可原样复用。

5. **build_deep_analysis_prompt(...)**  
   - **S8 专用**：材料知识（海泡石、磷酸）、6 大必需部分（EIS 形态、Arrhenius 斜率、温度依赖性、**最优 R-N 配比**、实验建议、应用场景）。  
   - **S60 需单独实现**：无黏土/无限域，不写「最优 N 配比」「限域」；改为强调纯 H₃PO₄、Vehicle/Grotthuss、Ea 与 R/温度关系、与 S8 的对比定位等（见下节）。

6. **call_opus45(prompt)**  
   - 调用 Claude Opus 4.5，生成长文本。

7. **写文件**  
   - 将模型输出写入 `deep_analysis/S8_deep_mechanism_analysis.md`，并写入元信息（生成时间、模型、基于多少样品/报告）。

---

## 二、S60 深度分析报告需要如何生成

### 2.1 总体流程（与 S8 对齐）

- **先做阶段 1**：为每个 S60 样品生成单样品机理报告。  
- **再做阶段 2**：基于所有 S60 单样品报告 + S60 的 segment 数据，生成一份 S60 材料级深度分析报告。

### 2.2 阶段 1：S60 单样品报告

- **执行方式**：在 close 目录下执行  
  `python phase2/run_batch_reports.py --material S60`  
  （若脚本里 processed_dir 指向 `close/output/phase1_results`、output_dir 指向 `close/output/phase2_reports`）。
- **输入**：`close/output/phase1_results/S60*_analysis_result.json`。  
- **输出**：`close/output/phase2_reports/S60-1-1-1_mechanism_report.md`、`S60-2-1-1_mechanism_report.md` 等，每个 S60 样品一份。
- **实现注意**：  
  - `SampleMechanismGenerator.convert_to_report_format()` 及 `build_mechanism_prompt()` 若当前针对 S8（含 N、黏土），需确认对 S60（N=0、无黏土）是否兼容；必要时按 `material_type` 分支或传参，避免 N/黏土相关描述在 S60 上不合理。

### 2.3 阶段 2：S60 材料级深度分析报告

- **推荐做法**：新增脚本 `phase2/run_s60_deep_analysis.py`，结构与 `run_s8_deep_analysis.py` 一致，但材料改为 S60，并换用 S60 专用 prompt。
- **输入**：  
  - `close/output/phase2_reports/S60*_mechanism_report.md`（阶段 1 产出）；  
  - `close/output/phase1_results/S60*_analysis_result.json`（用于 segment 统计）。
- **输出**：`close/output/deep_analysis/S60_deep_mechanism_analysis.md`。
- **逻辑复用**：  
  - `load_sample_reports(report_dir, 'S60')`：glob `S60*_mechanism_report.md`。  
  - `load_segment_data_from_json(data_dir, 'S60')`：同上，仅把 material 改为 'S60'，S60 的 JSON 已有 segments 和 R，N 可为 0。  
  - `summarize_sample_reports(reports)`：不变。  
  - **需新增**：`build_deep_analysis_prompt_s60(...)`（或原函数加 material 分支），见下。

### 2.4 S60 深度分析 Prompt 内容要点（与 S8 的差异）

- **材料定位**：纯 H₃PO₄ 液体电解质，无黏土、无限域；作为 S8 的「无限域基线」对比对象。
- **背景知识**：仅用磷酸/质子传导相关（如 `ACID_DETAILED_KNOWLEDGE['H3PO4']`、`PROTON_MECHANISM_KNOWLEDGE` 等），不引入黏土知识；可简要说明「无黏土、无 N、仅 R 与温度」。
- **数据统计**：与 S8 相同，给出 n_samples、n_segments、T 范围、**R 范围**、Ea 范围；N 范围若全为 0 可写「不适用」或省略。
- **报告必需部分建议**（对应 S8 的 6 部分做裁剪与替换）：  
  1. **EIS 曲线形态机理解释**：纯酸体系下的形态及与温度的关系（可保留，与 S8 对比时有用）。  
  2. **Arrhenius 斜率/分段机理**：多段 Ea 的物理含义、Vehicle vs Grotthuss 等（保留）。  
  3. **温度依赖性机理**：高/中/低温段主导机制（保留）。  
  4. **R（酸/水比）与性能关系**：替代 S8 的「最优 R-N 配比」；给出 R 对 Ea/电导率的影响及「最优 R」的定性或定量建议。  
  5. **实验建议与改进方向**：纯酸体系下的验证实验、与 S8 对比实验建议（可选）。  
  6. **应用场景与定位**：纯酸体系的适用场景、与 S8（限域）的优劣对比（保留）。  
- **不必包含**：限域效应、N、黏土结构、最优 N 配比等 S8 专属内容。
- **输出要求**：与 S8 一致（中文、字数下限、结构清晰）；标题改为「S60（Pure H₃PO₄）质子传导深度机理分析报告」等。

### 2.5 与 material_deep_analyzer 的对应关系

- `close/phase2/core/material_deep_analyzer.py` 中已有 **S60 深度分析** 逻辑：  
  - `generate_s60_deep_analysis()`：从 `*_template_report.md` 收集 S60 报告，用 `_build_s60_deep_analysis_prompt()` 生成 prompt，调 LLM，写 S60 报告。  
- 但该模块使用的是 **template_report**（`S60-*_template_report.md`），而当前 S8 深度分析流水线使用的是 **mechanism_report**（`S8-*_mechanism_report.md`） + `run_s8_deep_analysis.py`。  
- 因此有两种可选路线：  
  - **路线 A（推荐）**：与 S8 一致，采用「mechanism_report + 专用 run_s60_deep_analysis.py」。即阶段 1 用 `run_batch_reports.py --material S60` 生成 `S60*_mechanism_report.md`，阶段 2 用新建的 `run_s60_deep_analysis.py` 读这些 mechanism 报告和 phase1 的 S60 JSON，用 S60 专用 prompt 生成 `S60_deep_mechanism_analysis.md`。  
  - **路线 B**：沿用 material_deep_analyzer，改为先生成 S60 的 template_report（若现有流程有对应入口），再调用 `generate_s60_deep_analysis()`；此时需统一「单样品报告」是 template 还是 mechanism，避免与 S8 流程两套约定混用。  
- 建议采用 **路线 A**，这样 S8 与 S60 的深度分析在「单样品报告类型 + 材料级脚本」上一致，便于维护和对比。

---

## 三、实施步骤小结（不写代码，仅顺序）

1. **确认/补齐 S60 单样品报告**  
   - 运行 `phase2/run_batch_reports.py --material S60`，输入为 close 下 phase1_results 中的 S60 JSON。  
   - 检查生成的 `S60-*_mechanism_report.md` 是否覆盖全部 S60 样品，且内容对「无黏土、仅 R」合理；若有 S8 专用逻辑，在 sample_mechanism_generator 或 build_mechanism_prompt 中做 S60 兼容。

2. **新增 S60 材料级深度分析脚本**  
   - 新建 `phase2/run_s60_deep_analysis.py`，复用 run_s8_deep_analysis 的框架：  
     - load_sample_reports(..., 'S60')；  
     - load_segment_data_from_json(..., 'S60')；  
     - summarize_sample_reports；  
     - **S60 专用** build_deep_analysis_prompt_s60（仅磷酸知识、无黏土、R 与温度、6 部分按上节调整）；  
     - call_opus45；  
     - 写出 `deep_analysis/S60_deep_mechanism_analysis.md`。

3. **（可选）统一入口**  
   - 若希望一条命令先跑 S8 再跑 S60，可在 run_all 或单独脚本中先 `run_batch_reports --material S8`，再 `run_s8_deep_analysis`；再 `run_batch_reports --material S60`，再 `run_s60_deep_analysis`；无需改现有 S8 逻辑。

按上述顺序即可在「先每个 S60 样品单独报告，再 S60 深度分析报告」的流程上与 S8 对齐，并兼顾 S60 材料特性（无黏土、无限域、仅 R 与温度）。

---

## 四、运行说明（已实现代码）

### 前提

- 工作目录：在 **close** 目录下执行（或从项目根目录指定 close 路径）。
- 环境：已安装 `phase2` 所需依赖（含 `config.api_config` 的 OPENROUTER 配置，用于阶段 2 调用 Claude Opus 4.5）。
- 数据：`close/output/phase1_results/` 下已有 S60 的 `*_analysis_result.json`（Phase 1 已跑完）。

### 阶段 1：生成 S60 单样品机理报告

```bash
cd close
python phase2/run_batch_reports.py --material S60 --max 25
```

- **作用**：为每个 S60 样品调用 LLM 生成单样品机理报告，写入 `close/output/phase2_reports/S60-xxx_mechanism_report.md`。
- **参数**：`--max 25` 可覆盖当前 close 内所有 S60 样品（约 17 个）；若只测几个样品可改为 `--max 5`。已存在的报告会被跳过（SKIP）。
- **耗时**：每个样品约一次 API 调用，总时间取决于样品数与网络，可数分钟到十余分钟。

### 阶段 2：生成 S60 材料级深度分析报告

**先做一次 dry-run（不调 API，仅验证流程）：**

```bash
cd close
python phase2/run_s60_deep_analysis.py --dry-run
```

- **作用**：加载 S60 单样品报告与 phase1 的 segment 数据，生成 S60 专用 prompt 并保存到 `close/output/deep_analysis/S60_deep_analysis_prompt.txt`，**不调用 API**。用于确认代码可运行、路径与数据无误。

**正式运行（调用 Claude Opus 4.5）：**

```bash
cd close
python phase2/run_s60_deep_analysis.py
```

- **作用**：在 dry-run 的基础上调用 Claude Opus 4.5，生成 S60 深度机理报告，写入 `close/output/deep_analysis/S60_deep_mechanism_analysis.md`。
- **依赖**：需配置好 `config.api_config.OPENROUTER_CONFIG`（API key、base_url）。若未配置会报错。
- **耗时**：单次 API 调用，约 1–3 分钟。

### 输出文件一览

| 阶段 | 输出路径 | 说明 |
|------|----------|------|
| 阶段 1 | `close/output/phase2_reports/S60-xxx_mechanism_report.md` | 每个 S60 样品一份单样品机理报告 |
| 阶段 2（dry-run 也会生成） | `close/output/deep_analysis/S60_deep_analysis_prompt.txt` | S60 深度分析用的完整 prompt |
| 阶段 2（正式运行） | `close/output/deep_analysis/S60_deep_mechanism_analysis.md` | S60 材料级深度机理分析报告 |
