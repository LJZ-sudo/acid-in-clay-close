# Stage2 Statistics: S8 Evidence Atlas

Current status date: 2026-05-19

Stage2 converts the S8 retrospective acid-in-clay dataset into the canonical
evidence contract consumed by Stage3. It is not part of the attapulgite AiCE
Stage0/Stage1 BO training loop.

## Current Role

- Source system: S8 sepiolite retrospective evidence.
- Source mode: retrospective.
- Primary input: `data/s8_input.csv`.
- Canonical Stage2 -> Stage3 contract: `exports/stage3_seed.json`.
- Backward-compatible export: `exports/s8_evidence_atlas.json`.

`stage3_seed.json` is the authoritative handoff artifact. The legacy atlas and
CSV files are retained for diagnostics and historical compatibility, but Stage3
strict real mode should consume the V2 seed.

## Main Entrypoint

```powershell
cd D:\acid-in-clay-close\V1.0-qianduan-mainline
python stage2_statistics\main_agent.py stage2_statistics\data\s8_input.csv
```

By default the pipeline writes to:

```text
stage2_statistics/exports/
```

Use `--output-dir` only when deliberately writing an isolated verification run.

## Current Outputs

The current default export set is:

- `stage3_seed.json`: canonical V2 seed for Stage3.
- `evidence_units.json`: V2 evidence units.
- `s8_evidence_atlas.json`: legacy-compatible evidence atlas.
- `data_profile.json`: input profile and data coverage.
- `execution_plan.json`: enabled analysis modules.
- `visualization_manifest.json`: figure manifest; written as `{}` when no plots are emitted.
- `run_summary.json` / `run_summary.md`: run-level audit summary.
- `excluded_samples.csv` / `excluded_samples.json`: rows excluded during quality filtering.

The current canonical seed is expected to include:

- `schema_version`
- `source_system="s8_reference"`
- `source_mode="retrospective"`
- `input_files`
- `input_hashes`
- `stage3_ready`
- `stage3_blocking_reasons`
- `sample_summary`
- `segment_fits`
- `evidence_units`

## Contract Rules

- Missing `R` or `N` must be reflected in `quality_flags` and block Stage3 readiness.
- Stage2 may still write audit artifacts when `stage3_ready=false`.
- Stage3 strict real mode must reject a non-ready seed.
- S8 evidence is a mother-system reference, not attapulgite BO training data.

## Tests

```powershell
cd D:\acid-in-clay-close\V1.0-qianduan-mainline
python -m pytest -q tests\test_stage2_current_seed_contract.py stage3_mechanism\tests\test_stage2_stage3_contracts.py
```

## Maintenance Notes

- Treat `exports/stage3_seed.json` as the current truth for Stage3 input.
- Do not delete raw `data/s8_input.csv` or historical exports; archive old
  generated outputs into dated folders when they are no longer current.
- Update this README when the Stage2 -> Stage3 schema changes.

## 结构与逐文件状态（2026-07-05 核查）

本目录是**独立的 S8 回顾性统计模块**：不参与凹凸棒 Stage0/Stage1 BO 闭环，唯一下游是 Stage3（经 `exports/stage3_seed.json`，SHA256 锁定的受保护产物，40 样品 / 158 段 / 13 证据单元）。

```
stage2_statistics/
├─ main_agent.py               # ✅ 现役 · 唯一 CLI 入口（编排 planner→specialists→core→exports）
├─ config.py                   # ✅ 现役 · 模块配置
├─ core/
│  ├─ schema.py / schema_v2.py # ✅ 现役 · V1/V2 数据契约（V2 为权威）
│  ├─ segment_fitter.py        # ✅ 现役 · Arrhenius 分段拟合
│  ├─ meyer_neldel_segment.py  # ✅ 现役 · Meyer-Neldel 段分析
│  ├─ sample_aggregator.py     # ✅ 现役 · 样品级聚合
│  ├─ sample_trend.py          # ✅ 现役 · 样品趋势
│  ├─ morphology_features.py   # ✅ 现役 · 形貌特征
│  ├─ strength_rules.py        # ✅ 现役 · 证据强度规则
│  ├─ stage3_seed_builder.py   # ✅ 现役 · V2 seed 构建器（核心输出）
│  └─ base_specialist.py       # ✅ 现役 · specialist 基类
├─ planner/
│  ├─ data_profiler.py         # ✅ 现役 · 输入画像（data_profile.json）
│  └─ analysis_planner.py      # ✅ 现役 · 执行计划（execution_plan.json）
├─ specialists/                # ✅ 现役 · 5 个分析专家（trend/morphology/model_competitor/sanity/evidence_synthesizer）
├─ utils/
│  ├─ statistics_lib.py        # ✅ 现役 · 统计工具
│  └─ viz_engine.py            # ✅ 现役 · 图形引擎
├─ data/s8_input.csv           # 🧊 冻结输入 · 勿删
└─ exports/
   ├─ stage3_seed.json         # 🧊 受保护产物 · Stage3 权威输入（hash 契约测试盯守）
   └─ s8_evidence_atlas.json   # ⚠️ V1 遗留 · 仅诊断/兼容用途，Stage3 strict real 模式不消费
```

判定：**代码全部现役，无死文件**；唯一"旧物"是 V1 的 `s8_evidence_atlas.json` 导出（保留兼容）。守护测试：`tests/test_stage2_current_seed_contract.py`（seed hash 契约）、`tests/test_stage2_plots_tier2.py`、`stage3_mechanism/tests/test_stage2_stage3_contracts.py`。
