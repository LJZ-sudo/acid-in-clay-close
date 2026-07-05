# analysis/ — 研究分析代码包（原顶层 research/ 代码，2026-07-05 并入主线）

> 结构与逐文件状态文档（生成于 2026-07-05，基于代码级核查）。
> I/O 约定：读 `experiments/data/`（lineA_*/lineB_* 数据集）与 `experiments/runs/`，写 `experiments/results/`。代码内锚定方式：先向上找 `V1.0-qianduan-mainline` 再取 `parent / "experiments"`。
> 结论：**83 个 .py 无 LEGACY/SUPERSEDED 文件**；分三类——生产接线的库、可重跑的分析脚本、和一次性里程碑验证脚本（p2–p21 / pH1–pH4，属"已完成使命但作为证据保留"）。

## 0. 分类图例

- **✅ 库（生产/测试接线）**：被 backend_api 或 tests/ 直接 import；
- **▶️ 现役脚本**：可重跑的分析/出图工具（多数被 `sensitivity_jobs` 以 `python -m analysis....` 提示引用）；
- **📌 一次性验证**：p*/pH* 系列，验证某个硬化里程碑，产物固化在 `experiments/results/`，脚本保留作可追溯证据。

## 1. 逐子包说明

### stage0_v2/ — v2 重分析核心（M0 版本化/溯源/冻结）
```
versions.py                 # ✅ 库 · M0 溯源核心：git 锚、configs/*.yaml 的 sha256 注入、freeze_legacy_manifest（legacy_freeze_manifest.json 由它生成）
raw_loader.py               # ✅ 库 · 数据集发现/加载（experiments/data 下 lineA_*/lineB_*）
conductivity_uncertainty.py # ✅ 库 · σ 不确定度（tests/test_conductivity_uncertainty.py 覆盖）
repro_floor_variance.py     # ✅ 库 · 复现地板方差（tests/test_repro_floor_probability.py 覆盖）
arrhenius_robust.py         # ▶️ 脚本 · 稳健 Arrhenius（sensitivity_jobs 提示 python -m analysis.stage0_v2.arrhenius_robust）
breakpoint_uncertainty.py   # ▶️ 脚本 · 断点不确定度
rb_method_invariance.py     # ▶️ 脚本 · Rb 方法不变性
synthetic_validation.py     # ▶️ 脚本 · 合成校验
identifiability_v2.py       # ▶️ 脚本 · 可辨识性 v2
README.md                   # 子包自带说明
legacy_freeze_manifest.json # 🧊 冻结产物 · 遗留物 hash 清单（prospective-release 冻结件）
```

### epistemic/ — 认知治理（生产接线）
全部 6 个模块为 **✅ 库**：`hardware_adapter.py` 以 sys.path 注入 `analysis/` 后 opt-in 导入（active_design canary、impedance 前向校验、falsification_market、stage3 live 桥等）。

### calibration/ — 校准
`repro_and_calibration.py`、`repro_full_calibration.py` 为 ✅ 库/▶️ 脚本双用；其余为 ▶️ 现役脚本。README.md 自带。

### evaluation/
`policy_ablation.py` # ✅ 库 ·（tests/test_policy_ablation.py 覆盖）策略消融，写 experiments/results/。

### regularity/ / replay/ / analysis_scripts/
全部 ▶️ 现役脚本：
- `regularity/build_regularity.py`：规律性证据构建（读 experiments/data）；
- ~~`drt/`~~：已于 2026-07-05 下线归档（实测 DRT 不可行，59/59 点 R²<0）→ `archive/drt_decommissioned_20260705/drt_negative_result/`;
- `replay/`：run 证据回放（README.md 自带）；
- ~~`figures/`~~ + ~~`analysis_scripts/build_pptx.py`~~：预手稿汇报 deck 与概念草图，已归档 → `archive/report_deck_20260705/`（正式图表管线在 `manuscript/figures/`）；
- `analysis_scripts/`：杂项分析（含 `b_track_live_fulltemp.py` 全温程分析、`bind_evidence.py` 证据绑定等）；
- `natfig.py`（包根）：✅ 库 · Nature 风格出图工具，被 calibration/replay 出图脚本复用。

### ablation/ — M6/M7/M8 消融 + 线 A 冻结验证
```
m6_ablation.py + m6_*.py    # ▶️ 脚本 · M6 选择器消融（5 变体，直接 import s8_stage3；参照冻结的 20260607_openrouter_publication_v2）
m7_full_ablation.py + m7_*  # ▶️ 脚本 · M7 证据治理消融（3 臂 × 5 种子，S09 不同证据池；产物写 ablation/m7_full/）
m8_s10_ranking.py + m8_*    # ▶️ 脚本 · M8 S10 排序消融（干扰候选注入）；m8_critic_memory_loop.py 走 Tier-3 agentic 环
line_a_verdict.py           # ▶️ 脚本 · 线 A 预注册预测判定
line_a_analysis/            # 🧊 冻结产物 · 线 A 验证证据（文本/JSON）
```
注意：本子包的产物直接写在 `ablation/` 内部（历史约定），不写 experiments/results/。

### verification/ — 里程碑验证脚本（25 个）
全部 📌 一次性验证，按里程碑编号 p2–p21、pH1–pH4（如 `p9_stage3_live_verify.py` 用真 run 事件驱动 stage3 live 桥、`p10_epistemic_verify.py`、`p11_impedance_forward_verify.py`、`p19_count_precision_verify.py`）。其中 7 个的产物固化在 `experiments/results/epistemic_out/`、`experiments/results/p9_stage3_out/`。脚本保留 = 证据可复跑，不建议删除或"归档走"。

## 2. 消费关系速查

| 消费者 | 依赖 |
|---|---|
| backend_api/services/hardware_adapter.py | epistemic/（opt-in 全套） |
| backend_api/services/sensitivity_jobs.py | 读 experiments/results/，缺件提示 `python -m analysis.stage0_v2.*` |
| tests/（3 个） | stage0_v2.conductivity_uncertainty、stage0_v2.repro_floor_variance、evaluation.policy_ablation |
| 冻结流程 | stage0_v2/versions.py（legacy_freeze_manifest）+ configs/*.yaml sha256 |
