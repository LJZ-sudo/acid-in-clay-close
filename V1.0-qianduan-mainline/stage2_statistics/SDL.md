# Stage2 开发与优化约束

当前状态日期：2026-04-30

## 1. Stage2 职责边界

Stage2 只负责从 S8 表格数据中生成结构化证据地图。它不负责：

- 生成最终机理结论。
- 生成材料候选。
- 调用 LLM。
- 替代 Stage3 的机理仲裁。

Stage2 应输出可审计证据，而不是过度解释。

## 2. 当前主流程

```text
s8_input.csv
→ DataProfiler
→ AnalysisPlanner
→ SanityChecker
→ TrendAnalyzer / ModelCompetitor / MorphologyExpert
→ EvidenceSynthesizer
→ VizEngine
→ EvidenceAtlas
→ exports/*.json
```

## 3. EvidenceUnit 约束

每条证据必须区分：

- `observation`：直接统计观察。
- `interpretation`：基于统计观察的物理解释。
- `question`：后续 Stage3 可以消费的机理问题。

禁止把假说写成已证明事实。例如：

- 不应写“证明发生渗流相变”。
- 应写“提示可能存在渗流类连通性转变”。

## 4. support_metrics 约束

后续优化必须保持字段契约稳定。当前计划采用以下规范：

### 4.1 临界点证据

```json
{
  "composition_variable": "R",
  "critical_value": 0.3,
  "critical_value_unit": "composition",
  "R_critical": 0.3
}
```

如果变量是 `N`，则写入 `N_critical`。

### 4.2 Meyer-Neldel 证据

```json
{
  "E_MN_eV": 0.02,
  "r_squared": 0.9,
  "slope": 50.0,
  "intercept": 1.0,
  "p_value": 0.001
}
```

可视化层必须读取上述字段，不能读取旧字段 `E_MN/R2`。

## 5. confidence 约束

`confidence` 是规则化证据权重，不是严格统计置信概率。后续所有新 evidence 都应包含：

```json
{
  "confidence_basis": {
    "rule_id": "...",
    "formula": "...",
    "inputs": {},
    "interpretation": "启发式证据权重，不等同于严格统计置信概率"
  }
}
```

## 6. 清洗与 excluded samples

`SanityChecker` 不应只输出聚合过滤数量。后续必须导出：

- `exports/excluded_samples.csv`
- `exports/excluded_samples.json`

每条排除记录至少包含：

- `row_index`
- `sample_id`
- `rule_id`
- `column`
- `value`
- `threshold`
- `reason`

## 7. 文档规则

- `README.md` 描述当前架构和运行方式。
- `ANALYSIS_COMPLETE.md` 只记录当前 exports 快照，不保留旧运行结论。
- 本文件记录开发约束。
- 旧内容如果与当前代码/exports 不一致，直接替换，不叠加补丁说明。

## 8. 修改规则

在本目录优化时遵守：

- 先读完整目录再改。
- 对确认有问题的逻辑，删除旧逻辑并替换成清晰的新逻辑。
- 不保留一次性脚本。
- 不保留临时测试数据。
- 修改后必须运行 S8 pipeline 或至少做导入/语法级验证。

