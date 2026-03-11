# Close 独立使用说明（方案 D）

**适用对象**：仅持有 close 代码与已有数据（如 `phase1_results` 压缩包）的读者，希望在不接触父项目（V1.0-qianduan）的前提下复现 **Phase 2 与 Phase 3**。  
**方案**：采用**方案 D**（仅文档与使用方式独立），不修改 close 代码；通过本说明与既有文档，实现“仅 close + 已有数据”的复现流程。

---

## 一、能独立复现到什么程度？

| 阶段 | 是否仅凭 close + 已有数据复现 | 前提 |
|------|------------------------------|------|
| **Phase 3** | **可以** | `close/output/phase1_results/` 下已有 `*_analysis_result.json`；step4 需 `close/output/deep_analysis/S8_deep_mechanism_analysis.md`（可由 Phase 2 生成或随数据包提供）。 |
| **Phase 2** | **可以** | close 内已配置 `config/api_config.py`（API 密钥等）；`close/output/phase1_results/` 下已有 Phase 1 的 JSON。 |
| **Phase 1** | **不可以** | 当前 Phase 1 依赖父项目（V1.0-qianduan）下的 **specific_conductance** 等模块。若需从原始 EIS 数据跑通 Phase 1，需在父项目环境中运行，或采用 `docs/CLOSE_STANDALONE_OPTIONS.md` 中的方案 A/B/C。 |

---

## 二、仅 close + 已有数据：复现 Phase 3

**前提**：  
- 已将 `close` 代码放到本地（如 `./close`）。  
- 已将 Phase 1 结果放入 `close/output/phase1_results/`，即该目录下存在若干 `*_analysis_result.json`。  
- （可选）若需运行 step4（ML–AI 区间对照），需存在 `close/output/deep_analysis/S8_deep_mechanism_analysis.md`；若无，可先跑 Phase 2 生成，或跳过 step4、仅跑 step1/2/3/5/6。

**步骤**（在 **close** 目录下执行）：

```bash
# 安装 Phase 3 依赖
pip install -r phase3/requirements.txt

# 一键运行 Phase 3 全流程（推荐）
python phase3/run_all.py
```

或分步执行：

```bash
python phase3/step1_data_preparation.py
python phase3/step2_train_models.py
python phase3/step3_confinement_analysis.py
python phase3/step4_ml_ai_validation.py    # 需 S8 深度报告存在
python phase3/step_meyer_neldel.py
python phase3/step6_cross_material.py
python phase3/step5_final_report.py
```

**预期输出**：`close/output/phase3_results/` 下出现 `integrated_data.csv`、`models/`、`confinement/`、`ml_ai_validation.json`、`meyer_neldel/`、`cross_material/`、`phase3_final_report.md` 等。详见 `phase3/REPRODUCIBILITY.md`。

---

## 三、仅 close + 已有数据：复现 Phase 2

**前提**：  
- 已将 `close` 代码放到本地。  
- `close/output/phase1_results/` 下已有 Phase 1 的 `*_analysis_result.json`。  
- close 内已配置 **API**：在 `close/config/api_config.py` 中配置好 OpenRouter（或所用 LLM API），以便 Phase 2 调用。

**步骤**（建议从**项目根目录**运行，使 `close` 作为子目录；或从 close 目录运行并确保 `config.api_config` 可被导入）：

```bash
# 单样品机理报告（按材料）
python close/phase2/run_batch_reports.py --material S8
python close/phase2/run_batch_reports.py --material S60

# 材料级深度报告
python close/phase2/run_s8_deep_analysis.py
python close/phase2/run_s60_deep_analysis.py
```

**预期输出**：  
- `close/output/phase2_reports/` 下出现 `*_mechanism_report.md`。  
- `close/output/deep_analysis/` 下出现 `S8_deep_mechanism_analysis.md`、`S60_deep_mechanism_analysis.md`。

---

## 四、数据包建议（便于审稿/合作方复现）

若希望审稿人或合作方**仅凭 close + 数据包**复现 Phase 2/3，建议提供：

1. **close** 代码（当前仓库或打包为 zip）。  
2. **phase1_results 压缩包**：将 `close/output/phase1_results/` 下所有 `*_analysis_result.json` 打成一个压缩包，说明解压到 `close/output/phase1_results/`。  
3. **（可选）deep_analysis 压缩包**：若希望对方直接跑 Phase 3 含 step4，可一并提供 `close/output/deep_analysis/S8_deep_mechanism_analysis.md`（及可选 S60），说明解压到 `close/output/deep_analysis/`。  
4. **本说明**：将本文档（或 `docs/CLOSE_STANDALONE_README.md`）与 `phase3/REPRODUCIBILITY.md` 一并提供，并注明 Phase 2 需自行配置 `config/api_config.py`（API 密钥等）。

对方在**不接触父项目**的情况下，可按第二节复现 Phase 3，按第三节复现 Phase 2（需配置 API）。

---

## 五、Phase 1 与“完全独立”的 close

当前 **Phase 1**（从原始 EIS 到 `*_analysis_result.json`）依赖父项目（V1.0-qianduan）下的 **specific_conductance** 等模块，因此**仅凭 close 无法从原始 EIS 跑通 Phase 1**。

若未来需要“代码级完全独立”的 close（含 Phase 1 在无父项目下可运行），可采用 `docs/CLOSE_STANDALONE_OPTIONS.md` 中的 **方案 A（独立发行包）**、**方案 B（vendor + 路径优先级）** 或 **方案 C（环境/配置开关）**；方案 D 不修改代码，仅通过文档与使用方式实现 Phase 2/3 的独立复现。

---

## 六、相关文档

| 文档 | 用途 |
|------|------|
| **CLOSE_DOCS_AND_CODE_DEPENDENCY.md** | 文档/代码依赖总览；方案 D 采用说明。 |
| **CLOSE_STANDALONE_OPTIONS.md** | 独立化方案 A/B/C/D 分析与选择。 |
| **phase3/REPRODUCIBILITY.md** | Phase 3 可复现性（命令、依赖、输出列表）。 |
| **CLOSE_PROJECT_GUIDE_PART1.md / PART2.md** | 完整项目指南（含 Phase 1/2/3 与 auto_control）。 |
