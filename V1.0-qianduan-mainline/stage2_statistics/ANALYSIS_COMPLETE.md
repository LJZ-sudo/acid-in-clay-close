# Stage2 当前运行快照

快照更新日期：2026-04-30  
事实来源：`exports/data_profile.json`、`exports/execution_plan.json`、`exports/s8_evidence_atlas.json`、`exports/visualization_manifest.json`

## 1. 说明

本文件替代旧版“完成报告”。旧版报告记录的是 2026-04-12 左右的历史运行状态，包含 1068 行、44 条证据、MorphologyExpert 禁用等旧信息；这些内容已与当前 `exports` 不一致。

从现在开始，Stage2 的真实状态以 `exports/*.json` 为准。本文件只记录当前快照和后续优化注意事项。

## 2. 当前输入数据

- 输入文件：`data/s8_input.csv`
- 行数：1081
- 列数：34
- 样品数：40
- 温度范围：182.15-299.15 K
- 温度跨度：约 117 K
- R 取值数：20
- N 取值数：25
- R2 平均值：约 0.9309
- 高质量数据占比：约 68.9%（R2 > 0.9）

## 3. 当前执行计划

`exports/execution_plan.json` 显示当前 5 个模块全部启用：

1. `sanity_checker`
2. `trend_analyzer`
3. `model_competitor`
4. `morphology_expert`
5. `evidence_synthesizer`

这和旧报告中“MorphologyExpert 禁用”的状态不同。

## 4. 当前导出结果

- `exports/s8_evidence_atlas.json`
- `exports/data_profile.json`
- `exports/execution_plan.json`
- `exports/visualization_manifest.json`

当前 atlas metadata 显示：

- 原始数据行数：1081
- 清洗后数据行数：1031
- 当前图表清单：`ea_vs_R_trend`、`meyer_neldel`
- 当前证据总数：55
- 当前 question 层证据：7
- 当前主题分布：`transport_dynamics` 9、`composition_sensitivity` 41、`phase_transition` 5
- 当前层级分布：`observation` 4、`interpretation` 44、`question` 7
- 当前逐行排除记录：50

## 5. 当前已知技术债

### 5.1 confidence 来源

`EvidenceUnit` 已增加 `confidence_basis` 字段。当前主要 specialist 已写入 rule、formula、inputs 和 interpretation。注意：`confidence` 仍是规则化证据权重，不等同于严格统计置信概率。

### 5.2 字段契约

当前已完成两处字段契约修复：

- `TrendAnalyzer` 输出通用 `critical_value`，并按变量补充 `R_critical/N_critical` 兼容字段。
- `main_agent` 会将 `E_MN_eV/r_squared` 归一化为 `E_MN/R2` 后交给 `VizEngine`。

### 5.3 excluded samples

`SanityChecker` 已导出逐行排除原因：

- `exports/excluded_samples.csv`
- `exports/excluded_samples.json`

### 5.4 Question 层

`EvidenceSynthesizer` 已扩展 profile-based 触发器。当前 S8 运行生成 7 条 question 层证据。

### 5.5 EIS 形貌措辞

`MorphologyExpert` 已将“证明”类绝对措辞改为“提示/线索/需独立验证”。EIS 形貌和 Arrhenius 折点只能作为机理线索，不能写成等效电路或相变的唯一证明。

## 6. 下一步优化

本轮 Stage2 优化按以下顺序进行：

1. 继续检查 `confidence_basis` 是否覆盖所有新证据路径。
2. 评估 `MorphologyExpert` 当前 T_arc/T_break 结果是否科学合理。
3. 视需要增加正式单元测试，但不保留一次性测试脚本。
4. 将本次 Stage2 输出下发给 Stage3 前，先人工快速审阅 7 条 question 是否适合进入 Stage3。

## 7. 运行命令

```powershell
cd <repo-root>\V1.0-qianduan-mainline
python stage2_statistics\main_agent.py stage2_statistics\data\s8_input.csv
```
