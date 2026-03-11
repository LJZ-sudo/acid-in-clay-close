# Closed-Loop EIS 分析子项目（2026 清理版）

本目录是 **EIS 自驱动闭环分析系统 + 论文图表/结果** 的主代码仓。  
旧版本代码和历史输出会逐步移动到 `archive_*` 目录，仅作参考。

---

## 1. 当前系统的四个核心目标

1. **方法可靠性**：  
   从 CHI 原始 EIS 数据自动完成 Rb 拟合、导电率计算和多段 Arrhenius 分析，证明自动结果物理合理，并优于传统低分辨率/两段拟合基线。

2. **自驱动相变检测与采样优化**：  
   在线分析 EIS 曲线和导电率变化，实时检测相变/机制转变区域，在 3 K 粗步长与 1 K 精细步长之间自动切换。

3. **AI 机理 + 新材料/下一步实验指导**：  
   基于 Phase 1/3 结果和材料知识库生成深度机理报告，提出机理假设、新配比/新材料预测，并给出可直接执行的后续实验建议。

4. **我们的系统 vs 商用大模型**：  
   对比“带闭环 + ML + 知识库的 Agent 报告”和“直接调用商用大模型”的机制分析质量，在机理深度、数据利用、实验可操作性等维度展示优势。

---

## 2. 运行入口（目前仍在使用）

### 2.1 Phase 3 全流程（基于 Phase 1 结果）

在 `V1.0-qianduan/close/` 目录下：

```bash
cd close
python phase3/run_all.py
```

`run_all.py` 顺序调用：

1. `step1_data_preparation.py`
2. `step2_train_models.py`
3. `step3_confinement_analysis.py`
4. `step4_ml_ai_validation.py`
5. `step_meyer_neldel.py`
6. `step6_cross_material.py`
7. `step5_final_report.py`

输出写入 `close/output/phase3_results/`，用于论文主结果和 AI 报告的定量输入。

> 说明：Phase 1（原始 EIS → Rb → Arrhenius 分段）在主项目中已完成，这里主要复用 `specific_conductance/` 中的实现。算法细节见 `paper/SI_table/SI_Note2_Arrhenius_segmentation.md`。

### 2.2 自驱动闭环 & 相变检测

**完整闭环处理（已有 CHI 数据）：**

```bash
cd close
python auto_control/run_closed_loop.py \
  --data-dir E:\chi_data \
  --config experiment_data/experiment_data.json \
  --thickness 0.01 \
  --area 1.0 \
  --min-points 5 \
  --output-dir experiment_data \
  --bundle-report
```

功能概览：

- 扫描 `E:\chi_data` 内 CHI 输出文件；
- 自动完成数据读取 → Rb 半圆拟合 → 导电率计算；
- 对成功点做 Arrhenius 分段分析；
- 生成 `report.json` + `report.md` + 可选 AI 报告打包产物。

**相变检测 + 自适应步长实验：**

- 主要逻辑在：
  - `auto_control/integrated_temp_chi_controller.py`
  - `auto_control/integrated_workflow.py`
  - `specific_conductance/data_processing.py`, `rb_fitting.py`, `conductivity.py`
- 相变检测和 Phase Jump Score 的细节见：
  - `paper/SI_table/SI_Note4_phase_transition_detection.md`

---

## 3. 目录结构总览

更细的分层见 `PROJECT_MAP.md`，这里只列关键部分。

```text
close/
├── auto_control/          # 闭环控制 & 相变检测 & 报告生成
├── config/                # 材料参数 & 分析超参数
├── data/                  # 原始 EIS 数据 & 材料 Excel
├── docs/                  # 项目综合说明 & 论文草稿 & SI 草稿
├── output/                # Phase1/2/3 结果 & 深度分析输出
├── paper/                 # SI Note、主表格、机理报告评分、写作指南
├── paper_figure/          # 论文图脚本 + 数据 + 配色/版本说明
├── phase1/                # Phase 1 pipeline 规划（部分逻辑从主项目迁移）
├── phase2/                # AI 机理 & 新材料/实验建议
├── phase3/                # ML + 限域效应 + 交叉验证 + 跨材料
├── phase3-v2.0/           # Phase3 v2.0 深度分析（如仍在用则视为核心）
├── specific_conductance/  # Rb 拟合、电导率计算、温控辅助
├── utils/                 # 文件/数学/绘图工具
└── archive_*/             # 旧代码/旧输出/旧文档（逐步迁移中）
```

---

## 4. 与论文结构的对应关系

- **Figure 1：架构 / 物理–数字交换**
  - 代码：`auto_control/`, `specific_conductance/`，以及主项目中的 `frontend_web` Orchestrator。
  - 文档：`paper/INTEGRATED_SYSTEM_GUIDE.md`, `paper/CLOSE_AGENT_GUIDE.md`。

- **Figure 2：自驱动相变检测 & 自适应采样**
  - 代码：`auto_control/integrated_temp_chi_controller.py`, `integrated_workflow.py`。
  - 文档：`paper/SI_table/SI_Note4_phase_transition_detection.md`。
  - 数据：典型自驱动实验的 `experiment_data/` 记录。

- **Figure 3：ML 分段 / ΔEa / 机理 & 新材料预测**
  - 代码：`phase3/step*_*.py`, `phase3-v2.0/*`。
  - 表格：`paper/SI_table/TableS2_confinement_effect_by_temperature.csv` 等。
  - AI 报告：`output/phase2_reports/`, `paper/SI_reports/*`。

- **Figure 4：我们的系统 vs 商用模型**
  - 代码：`paper_figure/figure4_model_comparison/*`。
  - 文档：`paper/SI_table/TableS7_report_evaluation_scores.csv`，`paper_figure/figure4_model_comparison/scoring_prompt.md`。

---

## 5. 清理与维护约定

- **新增主线代码**：优先放入 `auto_control/`, `phase3/`, `specific_conductance/`, `paper_figure/` 等 Core 目录，并在 `PROJECT_MAP.md` 中登记。
- **调试/一次性脚本**：放入 Support 区（在 `PROJECT_MAP.md` 中注明用途），用完且确认不会再用时移动到 `archive_code/`。
- **过时输出/文档**：在文件顶部注明 `OBSOLETE`，并移动到 `archive_output/` 或 `archive_docs/`，避免与当前主线混淆。

---

## 6. GitHub 上传说明

- 当前 `close/` 已经补充：
  - `.gitignore`
  - `.env.example`
  - `GITHUB_UPLOAD_GUIDE.md`
  - `GITHUB_PREUPLOAD_CHECKLIST.md`
  - `ENVIRONMENT_SETUP.md`
- API 密钥不再内置在 `close/config/api_config.py` 与 `close/auto_control/modules/report_bundle.py` 中；上传 GitHub 前，请通过环境变量提供：
  - `OPENROUTER_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `OPENAI_API_KEY`
- 推荐做法：
  1. 把 `close/` 作为单独仓库上传；
  2. 先用于 GPT / GitHub 分析和论文协作；
  3. 当前已完成 standalone 化前三轮：主入口、主论文图脚本、`auto_control/` 与关键辅助脚本都已做过路径规范化；
  4. 当前最重要的收尾信息见：
     - `GITHUB_UPLOAD_GUIDE.md`
     - `ENVIRONMENT_SETUP.md`
  5. 还未完全标准化的主要是：环境依赖、硬件依赖、数据分发与最终安装说明。
