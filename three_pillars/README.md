# three_pillars — 三个创新点的最小必要资产

本目录是**唯一规范位置**,汇总了三个创新点所需的全部"非代码"证据/协议/工具。
原则:**无小论文、无冻结包、无多版本副本**。代码主体仍在 `V1.0-qianduan-mainline/`;
本目录只放代码之外、且会被引用或作为投稿证据的东西。

> 整理来源:从原 `paper/current/`(去掉了 `package_builds/` 整套嵌套副本)和 `codex/`
> (去掉了 manuscript / 投稿 / remediation 流程产物)中**只抽取必要文件**复制而来。
> `paper/` 与 `codex/` 两个原目录已于 2026-06-05 整体删除;`V1/tests/test_paper_bo_v2_gate_contracts.py`
> 同步删除(它原本通过 importlib 加载 `paper/current/scripts/` 的 56 个脚本)。

---

## 创新点 → 资产 / 源代码 位置映射

### Pillar 1 — Evidence-constrained transfer agent(acid-in-clay → biopolymer–clay membrane motif)
证据与 agent harness **全部在 `V1.0-qianduan-mainline/` 内**,本目录不复制,只在
`pillar1_transfer_agent/README.md` 给出指针(避免产生第二份副本)。
关键证据:query packet `QP-S08-001.json`(2026-04-17)、paper card
`manual_8d58a81c9e_card.json`(2026-04-19)**均早于首次实验(04-25)**,
构成"motif 级推理先于实验"的时间线。

### Pillar 2 — Cooling-resilient pathway continuity descriptor(LRS 正验证 / CHITO 边界验证)
- `pillar2_descriptor_qc/eis_qc_v2/` — QC-gated EIS 证据(几何审计、manual vs auto Rb、三级 QC、代表性 Nyquist)
- `pillar2_descriptor_qc/benchmark_condition_audit/` — 基准条件审计(对比文献的条件差异)
- `pillar2_descriptor_qc/tables/final_benchmark_table.csv` — LRS Ea 对文献基准表
- `pillar2_descriptor_qc/figure_data/` — `ea_benchmark_table.csv`、`wide_temperature_performance_summary.csv`

### Pillar 3 — Physics/QC-gated EIS-in-the-loop(BO+LLM 真实闭环,不过度声称收敛/发现)
- `pillar3_eis_in_the_loop/bo_v2_objective_spec_20260527.md` — MOBO 目标契约(被 `mobo_optimizer.py` 引用)
- `pillar3_eis_in_the_loop/bo_v2_locked_campaign_plan_zh_20260527.md` — v2 锁定 campaign 计划
- `pillar3_eis_in_the_loop/bo_v2_locked/` — 前瞻执行协议(轮次模板、protocol_lock、历史审计)
- `pillar3_eis_in_the_loop/v2_engine_tools/` — claim-audit / QC 工具(append-only、manual Rb QC、claim 校验)
- `pillar3_eis_in_the_loop/v2_phase_c_experiment_protocol/` — 前瞻 MOBO 实验执行协议
- `pillar3_eis_in_the_loop/v2_phase_b_intelligence_dryrun/` — BO+LLM 智能层 dry-run
- 配套代码(留在 V1.0):`V1.0-qianduan-mainline/stage1_optimization/optimizers/mobo_optimizer.py`、
  单目标闭环历史 `.../stage1_optimization/output/attapulgite_aice/closed_loop_metrics.json`、
  campaign 历史 `.../stage1_optimization/campaign_memory/history_db_attapulgite.json`

---

## 历史记录(已完成的迁移)

`V1.0-qianduan-mainline/` 的 Python **不 import `codex` 也不 import `paper`**;唯一一处运行期引用
`mobo_optimizer.py` 已指向本目录(`three_pillars/pillar3_eis_in_the_loop/bo_v2_objective_spec_20260527.md`)。
以下原目录已在 2026-06-05 整体删除:

- `paper/current/`            — 需要的已抽到 `three_pillars/`;`package_builds/` 为整套嵌套副本
- `codex/`                    — manuscript / 投稿 / remediation 流程产物,三点不依赖
- 各 `初稿-*.docx` / 手稿 markdown — 按"不再有小论文"原则丢弃

`three_pillars/` 内部各文件中残留的少量历史引用(Phase A/B 验收报告里"过去时态的 paper/current"
声明)作为历史记录保留;**面向未来的活路径已全部改写为 `three_pillars/` 内的位置**。
