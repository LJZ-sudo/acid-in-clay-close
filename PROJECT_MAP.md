# PROJECT_MAP（2026 清理版）

> 本文件是 `close/` 子项目的“地图”。  
> 代码和文档按 **Core / Support / Archive** 三层组织，方便后续维护和删减。

---

## 1. Core（当前主线，必须保留）

### 1.1 入口脚本

- `auto_control/run_closed_loop.py`  
  闭环流程主入口：CHI 数据 → Rb 拟合 → Arrhenius → 报告 + AI 评估（可选）。

- `phase3/run_all.py`  
  Phase 3 一键入口：从 `output/phase1_results` 出发，依次执行：
  - `step1_data_preparation.py`
  - `step2_train_models.py`
  - `step3_confinement_analysis.py`
  - `step4_ml_ai_validation.py`
  - `step_meyer_neldel.py`
  - `step6_cross_material.py`
  - `step5_final_report.py`

- `run_phase2_complete.py`  
  Phase 2 批量机理分析/报告入口（目前主要用于离线更新 AI 报告）。

### 1.2 配置与材料参数

- `data/`  
  - `raw_eis/`：原始 EIS 数据（不要动）。
  - `材料数据说明.xlsx`：R、N、L、S 的唯一真相源。

- `config/`  
  - `material_params.py`：从 Excel 正确提取 R/N/L/S，修正了早期版本中 R/N 搞反的问题。
  - `analysis_config.py`：滤波、拟合、Arrhenius、可视化全局参数。

### 1.3 核心算法模块

- `specific_conductance/`  
  - `data_processing.py`：原始 EIS 数据滤波和预处理。
  - `rb_fitting.py`：Nyquist 圆拟合、Rb 提取、质量评估。
  - `conductivity.py`：电导率计算与相关辅助函数。
  - 如在用：`temperature_control.py`, `main.py` 等温控辅助入口。

- `auto_control/`  
  - `integrated_temp_chi_controller.py`：整合温控 + CHI 测量 + 数据处理的控制器。
  - `integrated_workflow.py`：相变检测 + 3 K / 1 K 步长自适应采样工作流。
  - `modules/`：
    - `acquisition.py`：CHI 文件扫描和测量历史管理。
    - `rb_fit.py`：Rb 拟合封装。
    - `arrhenius.py`：Arrhenius 分析逻辑（闭环用）。
    - `data_analysis.py`：数据解析与分析辅助。
    - `report.py`, `report_bundle.py`：JSON/Markdown 报告生成和打包。
    - `mechanism_report.py`：为 AI 机理分析准备输入。

### 1.4 Phase 1 / Phase 3 分析

- `phase1/`  
  - `step1_parse_eis.py`：扫描 `data/raw_eis`，解析 EIS 文件结构。  
  - 未来迁移/实现 Phase 1 pipeline 的占位文件（`step2_*`, `step3_*`, `step4_*`）。

- `phase3/`  
  - `step1_data_preparation.py`：从 Phase 1 结果整理 ML 训练数据。
  - `step2_train_models.py`：训练基线（S60）与限域（S8）模型。
  - `step3_confinement_analysis.py`：ΔEa 分析与温度依赖。
  - `step4_ml_ai_validation.py`：ML 与 AI 报告交叉验证。
  - `step_meyer_neldel.py`：Meyer–Neldel 规律分析。
  - `step6_cross_material.py`：跨材料普适性分析。
  - `step5_final_report.py`：Phase 3 汇总报告。

- `phase3-v2.0/`  
  - 如果当前论文主要基于 v2.0 的深度分析（例如 enhanced_prompts、改进版指标），则将整个目录视为 Core；  
  - 若仅部分使用，可在此文件中进一步标记哪些脚本仍为主线。

### 1.5 论文图像与表格

- `paper_figure/`  
  - 总览与配色：
    - `FIGURES_OVERVIEW.md`
    - `PAPER_FIGURES_INDEX.md`
    - `FIGURE_COLOR_SCHEME.md`
    - `FIGURES_UPDATE_REPORT.md`
  - 各图子目录：
    - `figure1/2/3/4/...` 等目录中的：
      - `plot_*.py`：生成论文图的主脚本。
      - `*_data.csv`：绘图数据文件。
      - `README.md` / `*_SUMMARY.txt`：图像说明与版本记录。

- `paper/`  
  - 总览与写作指南：
    - `README.md`
    - `INTEGRATED_SYSTEM_GUIDE.md`
    - `CLOSE_AGENT_GUIDE.md`
    - `SI_COMPLETE_GUIDE.md`
    - `GPT_PAPER_WRITING_PACKAGE.md`
  - SI 表格与 Note：
    - `SI_table/` 下：
      - `SI_Note1_Rb_fitting_methods.md`
      - `SI_Note2_Arrhenius_segmentation.md`
      - `SI_Note3_experimental_methods.md`
      - `SI_Note4_phase_transition_detection.md`
      - 主表 `MainTable*` 与 `TableS*` CSV。
  - AI 报告与评分：
    - `SI_reports/`：S8 深度分析报告、评分规则、示例输出等。

### 1.6 文档与当前草稿

- `docs/`  
  - `CLOSE_PROJECT_COMPREHENSIVE_GUIDE.md`
  - `CLOSE_PROJECT_GUIDE_PART1.md`, `CLOSE_PROJECT_GUIDE_PART2.md`
  - `KNOWLEDGE_BASE_VS_NO_KB_ANALYSIS.md`
  - 论文与 SI 当前草稿：
    - `Draft_V2_1_En_REFS_V2.txt`
    - `SI-V1.1_FINAL.txt`

### 1.7 通用工具

- `utils/`  
  - `FileUtils`, `MathUtils`, `PlottingUtils` 等工具类，供多处复用。

---

## 2. Support（支撑分析 / 图像调试 / 可能会用到）

这些模块不属于“主流程”，但：

- 常用于调试、验证和重画图；
- 对理解当前结果和未来扩展有帮助。

### 2.1 论文图调试脚本

- `paper_figure/` 中仍保留的一些 `check_*` 或版本对比类脚本。  
  例如：`check_segment4_coverage.py`, `check_actual_plot.py` 等。
- 2026 首轮清理中，已删除一批明显属于 `diagnose_*`, `verify_*`, `debug_*` 的脚本。
- 这些文件主要用于：
  - 检查拟合质量与原始数据一致性；
  - 比较不同版本图像和参数选择；
  - 支撑“方法可靠性”的额外验证。

### 2.2 Phase 2 辅助脚本与 Prompt

- `phase2/` 中与 prompt 调优、知识库分析相关但非主入口的脚本，例如：
  - `prompts/deep_analysis_prompts.py`
  - 若干用于生成/对比 prompt、分析知识库效果的脚本。
  - `run_batch_reports.py` 等批量生成助手。

### 2.3 输出与中间工件

- `output/` 中除“当前论文正在用的结果”之外的部分：
  - 例如旧版深度分析 prompt、中间 JSON/Markdown 报告等，可视为 Support，
    后续按时间戳或用途再进一步归档。

### 2.4 其它辅助脚本与文档

- 一些 `test_*.py`, `fix_*.py`：
  - 2026 首轮清理中，`test_phase1.py`, `test_phase2.py`, `test_phase3.py`, `test_single_sample.py` 已删除；
  - 第二轮清理中，`fix_rn_in_output.py`, `fix_s60_conductivity_phase1.py`, `check_rn_consistency.py` 已删除。
- `docs/` 中偏方法/定位但不直接写入正文的文档：
  - 例如将来可能会看的 prompt 说明等。

---

## 3. Archive（已弃用 / 历史参考，逐步迁移）

> 说明：本区内容建议逐步移动到以下目录，不再主动维护。

- `archive_code/`  
  - 旧版本脚本、已被新实现完全替代的分析代码；
  - 一次性 exploratory 脚本，确认不会再用于主论文或闭环系统。

- `archive_output/`  
  - 旧版本 Phase 1/2/3 结果；
  - 已经不再与当前实现一致、且不会在文章中引用的报告和图像。

- `archive_docs/`  
  - 早期项目说明、旧写作草稿，与当前实现明显不符的文档。  
  - 建议在文件顶部加上：`OBSOLETE – kept only for historical reference.`。

> 暂时还没有完全迁移完的旧内容，可以在本节中先列为“候选”，后续再实际移动：
> - `phase3-v2.0/` 中那些你已经不再使用、并且新版 Phase 3 已覆盖/替代的脚本和数据。
> - 很久以前的中间结果 / debug 输出（如老的 analysis 结果、早期 example 输出等）。
> - 任何以 `_deprecated`, `backup`, `old`, `v0`, `v1` 命名的子目录。

---

## 4. 使用与维护约定

1. **新增主线代码**：放入 Core 目录（并在本文件中登记）。  
2. **调试/一次性脚本**：若可能重用，放入 Support 并简要写明用途；用完确认不会再用可移入 Archive。  
3. **过时内容**：在文件顶部注明 `OBSOLETE`，然后移动到 `archive_*`，避免与当前主线混淆。  
4. **不要直接修改 Archive 中的文件**；若确实需要复活，先移动回 Support 或 Core，并在本文件中更新记录。