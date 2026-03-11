# Phase 2 报告约定说明

**目的**：明确 Phase 2 中单样品报告与材料级深度报告的数据源与命名约定，避免混用。

---

## 材料级深度分析以 mechanism_report 为准

**当前 S8/S60 材料级深度分析**使用的单样品报告为 **mechanism_report** 流水线产出，**不以** template_report 为准。

| 流水线 | 单样品报告命名 | 用途 | 材料级深度报告 |
|--------|----------------|------|----------------|
| **mechanism_report** | `*_mechanism_report.md`（如 `S8-3-1-1_mechanism_report.md`、`S60-2-14-1_mechanism_report.md`） | 单样品机理解读 | **S8_deep_mechanism_analysis.md**、**S60_deep_mechanism_analysis.md**（本流水线为准） |
| template_report | `*_template_report.md`（如 `S60-*_template_report.md`） | 其他模板类报告 | 不参与 step4 所用的 S8 深度报告数据源 |

**运行方式**：

- **阶段 1（单样品）**：`python phase2/run_batch_reports.py --material S8` 或 `--material S60` → 生成 `*_mechanism_report.md`。
- **阶段 2（材料级）**：`python phase2/run_s8_deep_analysis.py` 或 `python phase2/run_s60_deep_analysis.py` → 读取上述 mechanism 报告与 phase1 JSON，生成 `close/output/deep_analysis/S8_deep_mechanism_analysis.md`、`S60_deep_mechanism_analysis.md`。

Phase 3 的 step4（ML–AI 区间对照）所使用的“AI 推荐区间”来自 **S8_deep_mechanism_analysis.md**（从报告第四部分解析 R/N 区间），即 **mechanism_report → run_s8_deep_analysis → S8 深度报告** 这条链路。

**注意**：template_report 为另一套流程，若只运行其中一条流水线或误用另一种报告类型，会导致“找不到报告”或材料级报告基于的样本集不同。复现论文或审稿时请以 **mechanism_report + run_s8/s60_deep_analysis** 为准。
