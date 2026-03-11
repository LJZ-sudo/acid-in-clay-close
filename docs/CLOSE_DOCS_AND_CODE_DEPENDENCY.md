# Close 文档与代码依赖说明

**目的**：说明 close 内文档是否独立、以及其中提到的代码运行是否需要依赖其他文档或项目。  
**当前状态**：除文档级独立说明外，`close/` 已完成**standalone 化第一轮代码改造**。主入口脚本已优先使用 `close/` 自身模块；本文档以下内容据此更新。详见 `docs/CLOSE_STANDALONE_README.md` 与 `docs/CLOSE_STANDALONE_OPTIONS.md`。

---

## 一、文档是否独立？

### 1.1 指南类文档（CLOSE_PROJECT_GUIDE / COMPREHENSIVE）

| 文档 | 是否独立 | 说明 |
|------|----------|------|
| **CLOSE_PROJECT_GUIDE_PART1.md** | 可单独阅读 | 第一部分：项目概述、系统架构、Phase 1/2 介绍。 |
| **CLOSE_PROJECT_GUIDE_PART2.md** | **接续 PART1** | 开头注明“接续 PART1”；第二部分：Phase 3、auto_control、流程与故障排除等。与 PART1 合在一起构成完整使用指南。 |
| **CLOSE_PROJECT_COMPREHENSIVE_GUIDE.md** | **在 PART1+PART2 基础上增强** | 针对论文写作的增强版，含科学原理、方法学、论文结构对应；与前述两部分的目录与内容有对应关系。 |

**结论**：  
- **内容上**：PART1、PART2、COMPREHENSIVE 是一套**系列文档**，不是三个完全独立、互不引用的文档。  
- **代码片段**：文档中的“关键代码”多为**示意/简化**，用于说明逻辑或数据流；**真正可运行的是 close 仓库里的脚本**（如 `phase1/run_batch.py`、`phase2/run_s8_deep_analysis.py`、`phase3/step1_data_preparation.py` 等），不能直接把文档里的代码块当作完整程序运行。

### 1.2 其他 close/docs 文档

- **PHASE3_PAPER_READINESS_ANALYSIS.md**、**ML_AI_VALIDATION_OPTIONS.md**、**PHASE2_PHASE3_CONSISTENCY_AND_GAPS_REPORT.md** 等：各自围绕某一主题（论文适用性、ML–AI 表述、Phase2/3 一致性），**可单独阅读**，但会交叉引用同一套流程与输出路径（如 `close/output/phase3_results`）。

---

## 二、代码运行是否需要“链接到其他文档/项目”？

这里“链接”指：**运行 close 内脚本时，是否必须依赖 close 以外的目录、配置文件或其它仓库**。

### 2.1 不依赖“其他文档”

- 脚本的输入输出是 **close 内的路径**（如 `close/output/phase1_results`、`close/output/deep_analysis`），不要求额外“文档”作为输入。  
- 文档（含指南、PHASE3 分析等）是**给人看的说明**，不是程序运行时的依赖。

### 2.2 对“项目/目录”的依赖

| 阶段 | 脚本 | 是否依赖 close 外部的项目/目录 | 说明 |
|------|------|--------------------------------|------|
| **Phase 1** | `phase1/run_batch.py`、step1 等 | **主入口已不依赖父目录** | 第一轮后，`phase1/run_batch.py` 已改为优先使用 `close/specific_conductance/` 与 `close/auto_control/modules/`。是否能完整跑通，后续仍取决于本地数据、输出目录和运行环境。 |
| **Phase 2** | `run_s8_deep_analysis.py`、`run_batch_reports.py` 等 | **否（对父目录主依赖已去除）** | 第一轮后，脚本已统一优先使用 `close/config/api_config.py` 与 `close/phase2/*` 模块，不再默认依赖父目录 `V1_ROOT`。 |
| **Phase 3** | `phase3/step1_data_preparation.py` 等 | **否**（在已有数据前提下） | 所有路径均以 **CLOSE_ROOT** 为基准（如 `close/output/phase1_results`、`close/output/phase3_results`）。只要 `close/output/phase1_results` 下已有 Phase 1 的 `*_analysis_result.json`，即可在 **close 目录** 内运行 step1→step5/step6，无需父项目或其它仓库。step4 会读 `close/output/deep_analysis/S8_deep_mechanism_analysis.md`，属于 close 内部输出。 |

### 2.3 小结

- **文档**：指南系列（PART1 + PART2 + COMPREHENSIVE）是一套，文档内代码为示意；其他主题文档可单独看，但会引用同一套流程。  
- **代码运行**：  
  - **Phase 3**：仅需 close 自身 + 已有 Phase 1 结果（及 step4 所需的 S8 深度报告），**不需要链接到其他项目或文档**。  
- **Phase 2**：可从 close 运行并使用 close 的 config，**一般不依赖“其他文档”**，也已去除主入口对父项目的默认依赖。  
- **Phase 1**：主入口已经改为使用 close 内部模块，但完整运行仍受本地数据、环境与历史输出准备情况影响。

**当前阶段**：  
- **Phase 3**：在已有 `close/output/phase1_results`（及 step4 所需的 `close/output/deep_analysis/S8_deep_mechanism_analysis.md`）的前提下，**仅凭 close 目录**即可复现，无需父项目或其它文档。  
- **Phase 2**：在 close 内已配置 `config/api_config.py` 时，从 close 目录运行即可；不依赖“其它文档”，主入口也已不再默认依赖父项目。  
- **Phase 1**：主入口已切换到 close 内部模块；若需进一步做到更稳定的“独立分发运行”，见 `docs/CLOSE_STANDALONE_OPTIONS.md` 的后续方案。  

**一站式复现说明**（仅 close + 已有数据）：见 **`docs/CLOSE_STANDALONE_README.md`**。
