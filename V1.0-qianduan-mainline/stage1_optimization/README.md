# stage1_optimization/ — 优化闭环 + 科学 Agent 治理层（SciTX / E-Mem / PC-Skills / C³）

> 结构与逐文件状态文档（生成于 2026-07-05，基于代码级核查）。
> 结论：**91 个 .py 无一遗留死文件**——要么生产在用，要么是可运行的 demo/bench；S8 海泡石旧物已于 2026-06-07 迁出（见 `campaign_memory/MANIFEST.md`）。

## 0. 定位与分层

自上而下七层：

1. **入口**：`run_optimization_loop.py`（闭环主入口，`--optimizer mobo`）、`line_b_guardrail_run.py` / `line_b_round2_run.py`（线 B 官方 recipe 侧写）、`suggest_next.py` / `line_b_suggest_next.py`；
2. **左脑 optimizers/**：`bayesian_opt.py`（skopt EI）→ `mobo_optimizer.py`（ParEGO/skopt）→ `botorch_mobo_v2.py`（SingleTaskGP + qLogNEHVI；**尚未接入 --optimizer 开关**，经 tests 与桥接使用）；
3. **右脑 agents/**：`strategy_planner.py` → `llm_client.py`（.env 的 LLM_API_KEY）→ `prompts/planner_prompts.py`；溯源在 `prompt_envelope.py`（PromptEnvelope/LLMCallBundle）；
4. **SciTX B 轨 scientific_harness/**：`action_gate.py` → `commit_controller.py`（C_P/C_M/C_E 三重提交）→ `event_store.py`（SHA256 账本）；`admission.py`（证据准入）、`witness.py` / `instrument_witness.py`（见证人）、`measurement_txn.py`（测量事务）、`commit_gate.py`、`shadow.py`（非侵入挂到 live G1 测量）、`reconciler.py`、`fault_injection.py`、`rbact_noise_bridge.py`（Rb-ACT 噪声桥）、`transaction.py`、`commits.py`；`demo_a.py` 为可运行演示；
5. **E-Mem scientific_memory/**：`claim_graph.py`（SQLite 四值主张图）+ `agent_memory/`（R²-Memory，角色隔离 store/models/bench）；`invalidation_engine.py` 失效传播 → `bo_retrain_bridge.py` 触发 BO 重建（`bo_rebuilder.py`）；`snapshots.py`、`root_dedup.py`、`compression.py`、`history_bridge.py`、`live_memory_bridge.py`（live 桥）、`schema.py`；`demo_b.py` 演示；
6. **PC-Skills scientific_skills/**：`registry.py` + `certificate_service.py` + `runtime.py` + `drift.py` + `revocation.py` + `dual_account.py` + `risk_coverage.py` + `contracts.py` + `skills_eis.py`；`demo_c.py` 演示；
7. **C³-Harness scientific_convergence/**：影子收敛证书（`harness.py`/`policy.py`/`models.py`/`bench.py`），只延后、绝不抢先于遗留终止判据。

支撑模块：`canonical_input/`（`campaign_parser.py` 的 CampaignConfig、`design_space.py`、`state0_parser.py`）、`objectives/registry.py`（目标注册表 + G7 守卫 `assert_campaign_matches_role`，读 `configs/objective_registry.yaml`）、`safety/safety_validator.py`、`closed_loop/`（`termination_evaluator.py` 终止判据、`metrics_aggregator.py`、`round_logger.py`）、`contracts/next_experiment_schema.py`、`campaign_memory/`（`memory_manager.py` + `history_db_attapulgite.json` = 冻结的凹凸棒历史库）、`scientific_e2e/`（`demo_end_to_end.py` 的 B0/B2/B4/B5 臂 + `ro_crate.py` RO-Crate 打包器，冻结流程在用）、`rebuild_closed_loop_metrics.py`（指标重建工具）。

## 1. 外部消费者（谁在用这里）

- **backend_api** 通过 `sys.path.insert` 引用：`routers/agent.py`（主 Agent 环）、`routers/campaigns.py`（`evaluate_termination`）、`services/hardware_adapter.py`（.env LLM_API_KEY + SciTX 事务）；
- **experiments/live/hw2*.py** 真机脚本同样 sys.path 注入后调用 harness/memory；
- **tests/**（mainline 顶层 36 个测试文件）大面积覆盖本目录（见 tests/README.md 对照表）。

## 2. 现役 / 遗留判定汇总

| 类别 | 文件 |
|---|---|
| ✅ 生产在用 | 上述全部层的非 demo 文件（最近改动集中在 2026-07-04/05：run_optimization_loop、line_b_*、witness、commit_gate、live_memory_bridge、rbact_noise_bridge） |
| 🧪 demo/bench（可运行、非生产链路） | `scientific_harness/demo_a.py`、`scientific_memory/demo_b.py`、`scientific_skills/demo_c.py`、`scientific_e2e/demo_end_to_end.py`、`scientific_convergence/bench.py`、`scientific_memory/agent_memory/bench.py` |
| ⚠️ 现役但未接开关 | `optimizers/botorch_mobo_v2.py`（qLogNEHVI 实现完成，`--optimizer` CLI 开关尚未指向它） |
| 🧊 冻结数据 | `campaign_memory/history_db_attapulgite.json`（旧品历史库，勿动） |
| ⛔ 遗留 | 无（S8/sepiolite 旧物 2026-06-07 已迁出） |

## 3. 已知例外：`output/` 运行时目录

`stage1_optimization/output/attapulgite_aice/` 是 campaign 运行时产物目录，由
`campaigns/attapulgite_aice_campaign.json` 的 `storage.output_dir`（相对 stage1 根）指定，
backend 与 `run_optimization_loop.py` 都按此解析。它是主线目录里**唯一保留的运行时 I/O**——
路径写死在冻结的 campaign 配置与历史 recipe 溯源里，迁到 `experiments/` 属于行为改变，
留待下一次 campaign 版本升级时一并处理。
