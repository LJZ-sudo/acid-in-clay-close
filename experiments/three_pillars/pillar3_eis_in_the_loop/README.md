# Pillar 3 — Physics/QC-gated EIS-in-the-loop execution

本目录汇总 Pillar 3 的"BO+LLM 真实闭环执行"证据，对应论文创新点 **"物理与
QC 双闸门下的 EIS-in-the-loop 执行"**。原则：**真实闭环、不过度声称收敛、
不声称发现 LRS** —— 仅声称"机器+人+物理约束下的真闭环已 4 轮稳定执行"。

> 计算/优化主体代码（MOBO optimizer、stage1 closed loop、campaign memory）
> 仍位于 `V1.0-qianduan-mainline/stage1_optimization/`；本目录是**协议 +
> 工具 + 前瞻 dry-run 证据**的最小集，配合主线 stage1 输出共同支撑闯关。

---

## 顶层契约文件

- `bo_v2_objective_spec_20260527.md` — **MOBO 目标契约**（被
  `V1.0-qianduan-mainline/stage1_optimization/optimizers/mobo_optimizer.py`
  运行期引用）。改这份文件即改优化目标，是闭环锁定的单一事实源。
- `bo_v2_locked_campaign_plan_zh_20260527.md` — **v2 锁定 campaign 计划**
  （中文，给实验执行人看的轮次设计 + 边界）。

## `bo_v2_locked/` — 前瞻执行协议 + 轮次产物

- `protocol_lock.json` — 协议锁定签名（R/N 边界、QC 阈值、温度阶梯）
- `round_package_schema.md` — 每轮包结构契约
- `attapulgite_aice_v2_*.json` / `history_*.json` — 历史审计快照
- `prospective_round_template_*.json` — 前瞻轮次模板
- `round_01_v2-R1_locked_repeat/` ... `round_04_v2-R4_llm_guardrail_adjusted/`
  — **V2-locked 协议下的 4 个轮次执行包**（含每轮 LLM 决策、protocol diff、QC 报告）。

> **关于"几轮"的三个数字** —— 三者各自正确，不要混淆：
> - **`bo_v2_locked/round_01–04` = 4 轮**：V2-locked 协议下、需要 lab 端
>   走 approval / preflight gate 的 prospective lab handoff 包。
> - **`closed_loop_metrics.json::n_closed_loop_rounds = 6`**：BO 真闭环已完成的
>   全部"agent 建议 → 真机测量 → 回写"循环次数（T2–T7 都满足
>   `measured_after_suggestion_hash != null` 的因果链）。
> - **`closed_loop_metrics.json::n_history_trials = 8`**：含 T1 cold-start
>   先验（无前置 suggestion）+ T2–T7 BO 闭环 + T8 收尾共 8 个 trial。
>
> 与之配套的诚实声明：`closed_loop_validity = prospective_real`，
> `termination_status.verdict = continue`（**未触发收敛**），
> `convergence.triggered = false`，且 `limitations` 字段自陈
> "7 trial 用了显式厚度修复"——三者共同支撑"真闭环 + 不过度声称收敛"的 Pillar 3 立场。
- `execution_engine/` — 轮次包构造器 + lab 集成 + tracker（append-only、可回放）

## `v2_engine_tools/` — Claim 审计 + QC 工具链

- claim-audit / manual Rb QC / claim 校验脚本与单元测试
- `tests/fixtures/` — append-only / claim-audit / phase-c protocol 多套 fixture
- 与 stage1 / stage3 共同确保"声明 ≤ 证据"（防 overclaim guardrail）

## `v2_phase_b_intelligence_dryrun/` — BO+LLM 智能层 dry-run

- adapter / dryrun 报告 / metrics / nest fixtures / phase A 验收报告
- 用于在不消耗真机的情况下验证 strategy_planner + MOBO 的稳定性

## `v2_phase_c_experiment_protocol/` — 前瞻 MOBO 实验执行协议

- Phase-C 阶段（从 Phase B dry-run 过渡到真实 MOBO）的协议、迁移记录、提交清单

---

## 与代码主体的关系

| 资产 | 本目录 | V1.0 代码主体 |
|---|---|---|
| MOBO 目标定义 | `bo_v2_objective_spec_20260527.md` (规范文档) | `stage1_optimization/optimizers/mobo_optimizer.py` (实现) |
| Campaign 历史 | `bo_v2_locked/history_*.json` (审计快照) | `stage1_optimization/campaign_memory/history_db_attapulgite.json` (运行库) |
| 闭环度量 | — | `stage1_optimization/output/attapulgite_aice/closed_loop_metrics.json` (运行产物) |
| Claim 审计 | `v2_engine_tools/` (工具源码 + 测试) | （此处即 source-of-truth） |
| 实验协议 | `bo_v2_locked/round_*/` (轮次包) + `v2_phase_c_*` (协议) | 主线代码不依赖（运行时不被 import） |

闭环度量 `closed_loop_metrics.json` 在 stage3 mechanism pipeline 的
`s14_claim_auditor` 里被用作 "closed_loop_source_system: supported=True
→ closed_loop_validity=prospective_real, n_rounds=6" 的真值依据。
