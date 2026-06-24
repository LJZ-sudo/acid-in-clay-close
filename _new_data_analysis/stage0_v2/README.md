# stage0_v2 — M0/M1/M2 分析硬化层

> 按 `OPTIMIZATION_EXECUTION_PLAN_20260622.md` 实现的 v2 分析层。**只读 legacy 产物 + `configs/` 冻结策略,
> 产出 `_new_data_analysis/<topic>/*_v2.json`,绝不改写冻结管线**(`stage0_measurement/*`、
> `code/stage0_processing/process_new_materials_stage0.py`、各 `official_recipe.json`)。

## 模块与对应门禁

| 模块 | 任务/门 | 作用 | 运行 | 产物 |
|---|---|---|---|---|
| `versions.py` | M0 | 版本常量 / 配置 sha256 / `make_provenance` / `write_delta_report` / `freeze_legacy_manifest` | `python -m _new_data_analysis.stage0_v2.versions` | `legacy_freeze_manifest.json`(已冻结 40 产物) |
| `raw_loader.py` | M0 | 复用 `chi_parser` 读原始谱(符号约定与 legacy 一致),按 basename 在本机重定位 | (库) | — |
| `rb_method_invariance.py` | M1-1 / G2 | 四法并行 + 可信集一致性 + 4 条固定策略轨迹 → 转变是否方法不变 | `... rb_method_invariance --kind lineA` (~56s) | `rb_invariance/*_v2.json` |
| `arrhenius_robust.py` | M1-3 | `flag_sequence_anomalies` 全点保留 + Student-t 稳健 Ea + 留一稳定性 | `... arrhenius_robust --kind lineA` (~280s) | `arrhenius_robust/*_v2.json` |
| `breakpoint_uncertainty.py` | M1-5 | 残差 bootstrap → 断点 95% CI + p_break + 实践可辨识性分级 | `... breakpoint_uncertainty --n_boot 150` (~370s) | `breakpoint_uncertainty/*_v2.json` |
| `synthetic_validation.py` | M1-2 | 无转变合成数据全管线 FPR + 注入断点检出力 | `... synthetic_validation --n_draws 80` (~320s) | `synthetic_validation/*_v2.json` |
| `identifiability_v2.py` | M1-7 | Arrhenius/VTF/Mott 模型混淆矩阵 → design-conditional 可辨识性 | `... identifiability_v2 --n_draws 300` (~57s) | `identifiability_v2/*_v2.json` |
| `repro_floor_variance.py` | M2-1 / G8 | 复现地板层级方差(scope + CI)+ "差<地板"→ 概率 `P(\|Δ\|>δ)` | `... repro_floor_variance` (~6s) | `repro_floor_v2/*_v2.json` |

配套(主线内,被上述模块复用):
- `stage0_measurement/.../rb_fitting.py :: fit_all_rb_methods`(M1-1,加性)
- `stage0_measurement/.../eis_pipeline.py :: flag_sequence_anomalies`(M1-3,加性)
- `stage0_measurement/.../evidence_admission.py`(M1-4 证据准入,纯函数)
- `stage1_optimization/objectives/registry.py`(M1-6 目标注册表)
- `stage1_optimization/agents/prompt_envelope.py`(M2-5 prompt 溯源)

## 真实结果摘要(关键 LRS 数据集)

- **M1-1 方法不变性**:主力 LRS(0429/0509/6.12/6.15_merged/0615_s2)`risk=low`,可信集方法间 spread ~5e-4 dex,断点跨策略一致(跨度 1–5 K);较弱样本(0616/0617/6.15_s1)`medium`(诚实)。
- **M1-3 不删点**:多数数据集留一 `preserve=1.0 / transition=1.0`;Student-t 稳健 Ea 与 OLS 差 <0.02 eV(异常点保留但不拖拽结论)。
- **M1-5 断点 CI**:4/5 关键 LRS `p_break=1.00`、CI 窄(6.15_merged [238.9,241.0]K=−34~−32℃)→ `robust_empirical_transition`;0429CS(0.02cm 薄片)CI 宽 → 诚实 `weak_or_wide_break`。
- **M1-2 全管线 FPR**:6.15_merged(n=59)FPR=0.06(≤0.10,转变超过假阳性地板);其余 0.14–0.24(诚实标"需同时报 FPR");注入断点检出率=100%。
- **M1-7 可辨识性**:三律正确判别率仅 0.55–0.73(随机=0.33)→ `partially_identifiable`;真实最优均 VTF,但 30–45% 会被误判 → 不能声称唯一机理(量化版)。
- **M2-1 复现地板**:BETWEEN_SPECIMEN log10σ sd=0.252 dex(CI [0.13,0.32]);CROSS_BATCH 4月vs6月差 0.34 dex(厚度混杂);线B top-2 combined_score Δ=0.217 → `P(不可区分)=0.45`(诚实 null 的概率版)。

## 测试(`V1.0-qianduan-mainline/tests/`)

`test_stage0_rb_all_methods.py`(5)· `test_stage0_sequence_anomalies.py`(4)· `test_evidence_admission.py`(7)· `test_objective_registry.py`(7)· `test_repro_floor_probability.py`(5)= **28 passed**。

## 纪律

阈值改动前先 git commit;产物带 `provenance`(分析版本 + config sha256 + git commit);legacy 只读(见 `legacy_freeze_manifest.json`)。
