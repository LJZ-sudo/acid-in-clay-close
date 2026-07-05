# 系统架构（代码实证执行追踪，现状快照：2026-07-05）

> 所有 `file::function` / 参数 / 决策节点 / 事件名均来自对真实源码的逐文件读取,未取自总结文档、未臆造。存根/只读/已禁用处均如实标注。
> 与论文 Fig 1(抽象示意)互补:这里是内部"它到底怎么跑"。密钥读 `key.txt`/`.env`;LLM 经 OpenRouter。
> 诚实总纲:S09 候选生成 + S10 排序默认走确定性(非 LLM);项目从不声称"LLM 独立发现 LRS"。
> 本版为**重写版**:合并了此前所有分日期的接线审计,只保留截至 2026-07-05 的代码真相(含 H 系列旧材料硬化 H1–H4)。历史 run 用 run-id 标识。

## 执行链路（人 → Stage0 → Stage1 → Stage2 → Stage3 → 后端 → v2 守卫 → B 轨创新）

```text
[人/实验员/领域专家]
  - 前瞻纪律:改任何主张相关参数前先 git commit+push 盖时间戳(experiments/prospective)
  - 选 campaign(凹凸棒土 attapulgite)+ R/N 配方;或离线复算历史数据
  - 真机:在 /control 连硬件(COM3 TemperatureDriver + ChiExecutor)启动测量
      |-- (真机在线) --> Stage0       |-- (离线/复算) --> Stage0

[1] STAGE 0  测量 → 证据   (stage0_measurement/)
  离线入口: run_offline.py :: OfflineBatchWorkflow  (7 CLI;7 步序列)
  在线入口: run_online.py :: 真机逐温点测量(--material --chi_data_dir --harness_mode ...)
  逐温点 EIS 管线: eis_pipeline.py :: analyze_eis_point  (严格 5 步)
    1) QA   data_quality.py :: assess_data_quality  [确定性·一票否决]
         致命1: 250kΩ 量程触顶;致命2: 低频失真>3 次 → REJECTED_BY_QA
    2) KK   kk_validation.py :: validate_kk_consistency (v5.0)  中位数判据 mu_median<0.2
         符号 bug 已修: Z = zreal + 1j*zimag
    3) Rb   rb_fitting.py  [确定性·4 策略路由,深冷→常温]  sigma = thickness/(Rb*area)
    4) DRT  drt_analysis.py [本数据 R^2<0,不作证据]
    5) 状态判定 → OK / suspect
  逐点相变/步长决策(在线): phase_detect.py
    - analyze_experiment_state: Rb 单步跳跃/累积增长硬编码触发(无需 LLM)
    - 逐点 LLM agent: build_decision_user_message → 真调 OpenRouter(默认 openai/gpt-5.4)
      消费 R²-Memory 投影 + C³ 收敛证书 + active_design 建议;n<5 数据积累期走规则
      _json_default 归一 numpy 类型(修复历史序列化崩溃);llm_called 诚实标记
    - 离线 create_phase_detector() = DEPRECATED,恒返回 False
  Arrhenius 分段: arrhenius.py :: analyze_arrhenius  [确定性·4 模型竞争 + AICc]
  聚合落盘: aggregated_results.json / arrhenius_analysis.json
  后处理 CLI(独立): run_closure_offline.py → stage0_result_bundle.json + closure_report.json
  WS: temperature_update / measurement_complete / phase_transition
      v
[2] STAGE 1  闭环优化(物理↔数字)  (stage1_optimization/)
  主入口: run_optimization_loop.py :: OptimizationOrchestrator.run_optimization_loop()
  前瞻冻结入口: line_b_guardrail_run.py(FROZEN_SEED=20260608)
  Step1 解析 Stage0 [确定] state0_parser.extract_objective_metrics()
         [T-real 闸] mode==real 且 objective_valid==False → raise(拒坏数据入库)
  Step2 记忆固化 [确定·幂等] memory_manager.add_trial + 去重
  Step3 查历史最优 + **G7 守卫** objectives/registry.assert_campaign_matches_role
  Step4 左脑·优化器 mobo_optimizer.suggest_next [T1]  冷启动<5 LHS;ParEGO+GP[Matern2.5]+EI
         (噪声感知 v2: botorch_mobo_v2 :: BotorchMOBO(train_Yvar+qLogNEHVI))
  Step5 右脑·LLM 策略规划 [LLM] strategy_planner.decide_next_step [T2]
         gpt-5.4, temp=0.0;只存 prompt sha256;失败→降级纯优化器(conf=0.5)
  Step6 输出方案 [确定] safety_validator.validate + round_logger 三件套 SHA256 链
  终止评估: termination_evaluator.evaluate_termination (A 性能/B 收敛/C 预算/D 异常)
      v
[3] STAGE 2  统计 → 证据图谱   (stage2_statistics/)
  产物 canonical: exports/stage3_seed.json (8 类 EvidenceUnitV2);S8 仅先验不混入 BO
      v
[4] STAGE 3  机理推理 + 候选生成 + 主张治理   (stage3_mechanism/src/s8_stage3/)
  编排: orchestrator/pipeline.py :: run_from_seed (S03→S14)
  S04 假设 → S05/S06 机制仲裁 → S07 描述符 → S08 文献(OpenAlex live)[上游 LLM 真实参与]
  S09 候选族生成 [默认 STAGE3_S09_DETERMINISTIC_FROM_D4=True → 硬编码,非 LLM]
  S10 排序打分 candidate_audit.audit_candidates [默认确定性 8 维加权]
  S14 主张审计 s14_claim_auditor [C0–C5;EIS-only 硬封顶 C4;11 条绝对化措辞正则]
  Agentic 旁路(advisory,全确定性,不触碰冻结 pipeline)
      v
[5] 后端 API + 驾驶舱   (backend_api/ + frontend/)
  入口: backend_api/main.py FastAPI ⊂ socketio.ASGIApp;uvicorn :8000
  路由: /api/control(真·驱动硬件) /api/agent(决策环+LLM) /api/data /api/runs
    /api/samples /api/campaigns /api/provenance(只读) /api/pipeline(已禁用)
  /api/agent 决策环 :: agent.py::_run_decision_cycle
    _planner_propose → _critic_review → _orchestrator_decide → **ActionGate.submit**
    (WP4 Cutover:不再直连 hw.enqueue_command;shadow=行为不变,enforce 阻断 allowlist 外;
     审计 autonomous_bypass=0,fail-closed)
  hardware_adapter.py::_real_measurement_loop:逐点治理旁路(shadow+Rb-ACT+txn+R²-Memory
    +H2 在线仪器见证)+ 逐点 LLM agent + active_design(H3 canary ±2 step);收尾块调
    stage3/epistemic/impedance/证伪市场 + _finalize_instrument_witness(H2)+ _finalize_rb_r4_activation(H4)
  Socket.IO: _emit_event;通道 temperature_update/measurement_complete/phase_transition/...
  前端: React+Vite+AntD;Monitor 有只读「治理」Tab(实时 + 历史回放)

[6] 三创新点 v2 守卫引擎(独立 CLI, HOLD 偏置)  (experiments/three_pillars/.../v2_engine_tools/)
  run_all_checks(HOLD 偏置:硬编码 v2_claims_status="HOLD", enables_chi_automation=False)
```

## B 轨 Agent 方法学创新 + ESAS-OS 2.0 + Epistemic-OS（stage1_optimization/scientific_*/ + stage0_measurement/rb_act/ + V1.0-qianduan-mainline/analysis/epistemic/）

> 与冻结闭环互补;默认 shadow/旁挂、legacy 永不覆盖。软件层已成体系,真机治理路径已验证(G-2/G-4);H 系列(H1–H4)把 C³ 主循环消费/在线仪器见证/canary 多驱动/R4 激活模式软件实现并离线真验,数值链替换须人审(G-5)。

```text
-- SciTX 三重提交 Harness  scientific_harness/
   commits.py: PhysicalCommit C_P / MetrologicalCommit C_M / EpistemicCommit C_E
   witness.py: 三类 ID + 多见证推断 C_P(仅软件见证⇒至多 possible;样品错配⇒unknown)
   admission.py: C_M(intended_use) U1–U6 分级 + C_E(claim_id);EIS 封顶 C4;过度声称⇒REJECT
   transaction.py: EvidenceTransaction 编排(¬C_P⇒全拒;¬C_E(BO)⇒不入;blind_retry=0)
   action_gate.py: ActionGate 自主硬件命令唯一受控入口(shadow 照常/enforce 阻断 allowlist 外)
   commit_controller / reconciler / event_store(SHA256 链)/ fault_injection / shadow
-- E-Mem 证明携带记忆  scientific_memory/
   claim_graph.py: 四值逻辑超图;invalidation_engine.py: 失效传播;snapshots.py: 版本快照写门
   root_dedup.py: 独立证据根去重;bo_rebuilder.py: 失效→BO 视图重建 + DecisionImpact
   history_bridge.py / bo_retrain_bridge.py: 真实 history_db→优化器在更小集重训 GP(闭到底)
   compression.py: 压缩证书(主张不增强/反证零损失/决策不变,否则拒)
-- PC-Skills 可认证 Skills + 双账治理  scientific_skills/
   skills_eis.py: 6 真实 EIS Skill;certificate_service.py: 形式/统计/计量三层证书(Wilson 下界)
   drift.py/revocation.py: 漂移 SUSPEND/DEGRADE + 撤销作废;dual_account.py: 认知⊥执行账户
-- 端到端撤销演示  scientific_e2e/demo_end_to_end.py
   认证 Skill→SciTX 事务(含故障点)→无效不进 BO→撤销→E-Mem 失效→BO 视图重建→best E1→E3
   governed 严格优于 ungoverned(B0/B2/B4/B5 真实臂)
== ESAS-OS 2.0 四插件(默认 shadow/旁挂,legacy 永不覆盖)==
-- 测量路径事务化(P0)  scientific_harness/measurement_txn.py
   build_measurement_signals_from_bundle(Stage0 bundle→U1–U6 信号,可注入 rb_act/rb_r4 信号)
   ReplayInstrument(RAW_FILE 见证 + DONE + sample_id)→EvidenceTransaction.process
   **已接前端 live 回路**:逐点准入,not C_P(样品错配/无文件)⇒全拒;blind_retry=0
-- Rb-ACT 动态分析 Skill(P1)  stage0_measurement/rb_act/  (不改 rb_fitting.py)
   features.py/skill.py: 对数域贝叶斯模型平均→RbPosterior + REPORT/ABSTAIN + 主动建议
   synthetic.py/shadow.py: 合成谱验证 + 双跑 delta;σ 喂 admission.assess_use(C_M 真消费 EIS 质量)
   prereg.py: R4 预注册契约(方法指纹+验收门+UTC+contract_hash 封印)+ audit_series + 审计-only 信号
   activation.py(H4): R4 激活模式——三条件门(rb_r4_activate + gates_pass + 人审 token)才旁产
     σ_v2 + delta + "BO 不劣化"守卫(Spearman≥0.99);legacy 永不覆盖;缺任一条件恒回退 legacy
   接入门:R0 离线 → R1 在线双跑 → R2 审计 → R3 噪声(train_Yvar)→ R4 激活模式已实现(**须人审签核,跨批生产激活属 G-5**)
-- R²-Memory 角色隔离/可撤销/多轮记忆(P2)  scientific_memory/agent_memory/
   store.py: L0 不可变事件层 + 写门(无写权/自相矛盾⇒DENY;stale⇒REBASE)+ 来源域守卫(S8 拦截 100%)
   **已接 live**:live_memory_bridge.read_projection 逐点注入 LLM prompt(角色投影 + 外域参照)
-- C³-Harness 收敛动作组合(P3)  scientific_convergence/
   models.py: ConvergenceState(五类不确定度)+ Action(STOP/REPLICATE/.../CONTINUE)
   policy.py: U(a)=E[ΔHV]+λ·VoI-β·cost-γ·risk;单调约束 C³ 停⊆legacy 停
   harness.py: shadow 于 evaluate_termination 之上→ConvergenceCertificate
   **现状(H1 已消费)**:`termination_evaluator._c3_consume` 单调安全消费(c3_stop⊆legacy_stop,
     只推迟非硬停、永不更早停、budget 硬停不可推迟);`evaluate_termination` 出 `verdict_effective`/`c3`;
     live `_finalize_c3` 落 `c3_evidence.json` 供 Stage1 聚合自动消费;`pH1` 11/11 真 replay
== Epistemic-OS 认知层  V1.0-qianduan-mainline/analysis/epistemic/(均已接 live 收尾)==
-- 认知证书三对象(σ(T) 层,4 经验温度律高斯预测)
   epistemic_models: arrhenius/mott/vtf/segmented(log-σ vs 1/T + Fisher Jacobian)
   Scheme1 可观测性证书: FIM λ_min + 机制等价类(sup_a D_JS + UnionFind)
   Scheme2 anytime-valid 证伪: eprocess(E-process)+ Ville 不等式
   Scheme3 最小判别实验集: 加权集合覆盖(bitmask DP / 贪心)+ action_cost
   live 接线: hardware_adapter._run_epistemic(收尾)→ epistemic_summary.json + 事件
-- 阻抗级正问题  impedance_models.py(谱级,已接 live 收尾)
   MechanismModel{impedance_forward_operator, predicted_invariants, domain_of_validity}
   M1_single / M2_bulk_elec / M3_two;fit_spectrum(least_squares + AIC + Fisher λ_min)
   live 接线: hardware_adapter._run_epistemic_impedance → impedance_summary.json + EPISTEMIC_IMPEDANCE
-- 主动实验设计  active_design.py
   aic_posterior · action_cost(越冷越贵)· expected_discrimination(后验加权两两 JS/成本)
   live 接线: _epistemic_next_action(advisory 注入 prompt)+ _active_design_canary_nudge
             (canary 经 ActionGate EPISTEMIC_CANARY_SETPOINT 微调;硬护栏三重;
              **H3:邻域 ±1→±`canary_max_steps` 默认 2,让更多步实质微调**)
-- 多角色 LLM 证伪市场  falsification_market.py(真 OpenRouter,已接 live 收尾)
   LLMClient · Contract · proposer/falsifier/auditor(LLM)· referee_settle(确定性结算)
   live 接线: hardware_adapter._run_falsification_market(opt-in)→ falsification_market.json + MARKET_SETTLED
== H 系列旧材料代码硬化(2026-07-05,软件实现 + 离线真验;live 终验待旧材料 run)==
-- H1 C³ 主循环消费  closed_loop/termination_evaluator.py::_c3_consume(见上 C³ 块)  `pH1` 11/11
-- H2 在线仪器见证  scientific_harness/instrument_witness.py
   OnlineInstrumentWitness(真 CHI 文件 sha256 + 温控稳定 TEMP_TRACE + 仪器态)→ EvidenceTransaction
   submit_measurement_online;协议级故障注入 ACK_LOSS/INSTRUMENT_STUCK/FILE_MISSING/FILE_DELAY/
   SAMPLE_SWAP/CALIBRATION_EXPIRED(驱动边界软件注入,绝不碰物理安全)
   live 接线: _run_instrument_witness(逐点)+ _finalize_instrument_witness → instrument_witness_summary.json;`pH2` 17/17(真 EIS 文件)
-- H3 canary 多驱动  hardware_adapter._active_design_canary_nudge(邻域 ±canary_max_steps)  `pH3` 7/7
-- H4 Rb-ACT R4 激活模式  rb_act/activation.py(见上 Rb-ACT 块)+ _finalize_rb_r4_activation → rb_act_r4_activation.json;`pH4` 6/6(87 真谱)

验证: 全量 tests/+backend_api/tests/+stage3_mechanism/tests/ = **411 pytest collected**
   (408 def test_ + 3 parametrize;232+16+163;见 test_count_snapshot.json)
   硬件写路径审计 autonomous_bypass=0(scripts/audit_hardware_write_paths.py --strict 过)
全程护栏: replay != real · 每体系独立 history_db · claim 审计 · 前瞻冻结 · legacy 永不覆盖
```

---

## 决策节点速查（真实代码）

| 节点 | 位置 | 判据 | 后果 |
|---|---|---|---|
| T-real(坏数据闸) | `run_optimization_loop.py` Step1 | mode==real 且 objective_valid==False | raise,拒写 DB |
| T-G7(口径漂移) | `objectives/registry.py::assert_campaign_matches_role` | campaign != 注册表 training | raise |
| T1 优化器模式 | `mobo_optimizer.suggest_next` | len(P)<5 | 冷启动 LHS;否则 ParEGO |
| T2 LLM 规划 | `strategy_planner.decide_next_step` | LLM/JSON/值域任一失败 | 降级纯优化器(conf=0.5) |
| T-safety | `safety_validator.validate` | 越 campaign 边界 | passed=False |
| 终止 A/B/C/D | `termination_evaluator` | 性能/收敛/预算/异常 | continue/can_end/must_end |
| T-S09/S10 模式 | `s09_..._generator` / `candidate_audit` | 两 flag 默认 True | 确定性(非 LLM) |
| T-claim 封顶 | `s14_claim_auditor` | EIS-only 证据 | 硬封顶 C4 |
| T-逐点 LLM | `phase_detect.build_decision_user_message` | n<5 数据积累 / LLM 失败 | 走规则(llm_called=False) |
| T-CP(物理见证) | `scientific_harness/witness.py` | 仅软件见证 | 至多 possible |
| T-gate(命令路径) | `action_gate.py` | 自主命令 + enforce + allowlist 外 | BLOCKED;shadow 照常下发 |
| T-commit-gate(测量路径) | `hardware_adapter._commit_gate_enforces` | mode∈{canary,enforce} 且点被拒 | 真挡出 BO;shadow 只记录 |
| T-RbACT(弃权) | `rb_act/skill.py` | u_total 过大/方法严重分歧 | ABSTAIN + 主动建议 |
| T-Use(来源域守卫) | `agent_memory/store.py::assert_use` | use∈forbidden(S8 作 training) | UsageViolation(拦截 100%) |
| T-C³停(单调,H1 已消费) | `termination_evaluator._c3_consume` | 非硬停 + 证据不足 | verdict_effective=continue_c3_defer(只推迟,永不更早停/不推迟 budget 硬停) |
| T-R4 激活(H4 人审门) | `rb_act/activation.py::build_activation` | rb_r4_activate ∧ gates_pass ∧ 人审 token | 三者齐才旁产 σ_v2+delta;缺一恒回退 legacy |
| T-在线见证(H2) | `scientific_harness/instrument_witness.py` | 见证不全/协议故障 | 见证类故障不进 BO;ACK 丢失先核对不盲目重试 |

## 确定性 vs LLM（诚实标注）

- **确定性(无 LLM)**:Stage0 全管线、Stage1 优化器+记忆+终止+安全、S09/S10 默认、S14 阶梯、治理旁路判定逻辑、v2 守卫、认知证书/阻抗数学。
- **真实 LLM 调用**:Stage1 Step5 策略规划(gpt-5.4);**Stage0 逐点相变/步长 agent(gpt-5.4,live,n≥5)**;Stage3 上游 S04–S08 + 收尾机制推理链;Epistemic 证伪市场(多角色)。
- **关键诚实点**:发表那次 S09/S10 是有意冻结的确定性;项目主张温和,从不声称"LLM 独立发现 LRS"/收敛/事后改分。

## 真实可运行 vs 只读/存根/已禁用

| 组件 | 状态 |
|---|---|
| Stage0 离线/在线、Stage1 闭环、Stage2/3 编排 | 真实可运行 |
| /api/control、/api/agent | 真实可运行 |
| /api/provenance、/api/campaigns、/api/samples | 只读真实 |
| /api/pipeline mutating 端点 | 已禁用(返 disabled) |
| B 轨三包(WP0–WP5) | 真实可运行(411 pytest collected;跨层失效闭环 + 端到端撤销演示;autonomous_bypass=0) |
| ESAS-OS 2.0 四插件 | 真实可运行;measurement_txn/Rb-ACT/R²-Memory **已接 live**;**C³ 已被主循环消费(H1,单调安全)**;legacy 永不覆盖 |
| 在线仪器见证(instrument_witness,H2) | 真实可运行;真 CHI 文件+温控+仪器态经 EvidenceTransaction 推 C_P;协议级故障注入;`pH2` 17/17;接 live,终验待旧材料 run |
| Epistemic-OS(认知证书/阻抗/证伪市场/active_design) | 真实可运行,**均已接 live 收尾**;fe4b 真机佐证齐全;**H3 canary 邻域 ±2 step** |
| 逐点 LLM agent(phase_detect) | 真实调用(n≥5);numpy 序列化 bug 已修并 llmfix run 复验 |
| `harness_mode` enforce/canary(命令路径) | 真实可运行;fe4b canary 2 次物理执行、bypass=0 |
| 测量提交门控(P13-D,mode 感知) | 真实可运行;fe4b enforce 真拒 6 点出 BO;温控/CHI 永不门控 |
| Rb-ACT 数值链 | R0–R3 真接、R4 预注册审计过 + **R4 激活模式已实现(H4,`pH4` 6/6,87 真谱)**;未签核时 legacy `rb_fitting.py` 仍主路径 |
| live 回路 BO | 收尾一次性 post-sweep(非逐点内层);`entered_bo`=准入标记 |
| 离线 create_phase_detector() | DEPRECATED,恒返回 False |

> 溯源:本文件由对 `stage0_measurement/`、`stage1_optimization/`、`stage3_mechanism/`、`stage2_statistics/`、`backend_api/`、`frontend/`、`experiments/three_pillars/`、`V1.0-qianduan-mainline/analysis/epistemic/` 真实源码逐文件读取得到。

---

## 附录 A — `material_priority_score`（S10 确定性排序内核）

> `scoring/candidate_audit.py :: audit_candidates`(L358-477),每候选 deterministic 打分。8 主权重和 1.0。全确定性、无 LLM。

```text
material_priority_score = clamp(
    0.20*mechanism_fit + 0.18*evidence_quality + 0.18*formulation_completeness
  + 0.14*low_temperature_plausibility + 0.11*processability + 0.10*(1-risk)
  + 0.05*novelty + 0.04*citation_validity
  - term_leakage_penalty(0.3 当 source_term_ok=False)
  + 0.05*prospective_status_score )
```

| 分量(权重) | 函数::行 | 要点 |
|---|---|---|
| mechanism_fit(0.20) | `_mechanism_fit_score` L311 | 0.45*descriptor_coverage + 0.35*roles + 0.20*clamp(core+bonus) |
| evidence_quality(0.18) | `_evidence_quality_score` L290 | 每对支持 conf+0.10 取均 + diversity + pair_count |
| formulation_completeness(0.18) | `_formulation_completeness` | host/acid/clay/additive 完整度 |
| low_T_plausibility(0.14) | `_low_temperature_plausibility` L326 | 基 0.25;冷/253/193、bound-water、attapulgite 加分 |
| processability(0.11) | `_processability_score` L344 | 基 0.55;film/membrane 加;brittle/swelling 减 |
| (1-risk)(0.10) | `_risk_score` L207 | free-acid-leakage/bulk-water-freez .25 … reproducibility .04 |
| novelty(0.05) | `_NOVELTY_BASE` L20 | novel 0.85 / close 0.55 / exact 0.25 |
| citation_validity(0.04) | `_citation_validity` | 引用 card_id 落有效文献卡比例 |

## 附录 B — `pipeline.py :: run_from_seed`（S03→S14 编排全链）

```text
run_from_seed(seed):  # pipeline.py L101
  串行: evidence → hypothesis_board → mechanism_lit → arbitration → descriptor_sheet
        → material_lit → family_set → instance_set → ranking
  派发:
    s03_evidence_builder      [确定]
    s04_hypothesis_generator  [LLM]   s05_literature_scout_mech [LLM/OpenAlex]
    s06_mechanism_arbiter     [LLM]   s06b_design_principle_extr [LLM]
    s07_descriptor_extractor  [LLM]   s08_literature_scout_mat   [LLM/OpenAlex]
    s09_candidate_family_gen  [默认确定]  s10_instance_ranker [默认确定]
    s12/s13/s14_claim_auditor [确定·C0–C5 封顶]  s11_report_compiler [最后编译]
  每步 _run_guardrails + _run_source_term_audit(检 S08 污染)+ output_hashes → run_manifest
```

## 附录 C — `eis_pipeline.py :: analyze_eis_point`（单温点 5 步）

```text
1) 数据清洗 np.array, temperature_K=T_C+273.15
2) QA 一票否决: max_impedance_fatal=250000Ω; noise_reversal_fatal=3 → REJECTED_BY_QA
3) KK v5.0: mu_median<0.2;is_valid=False 只置 kk_warning 不熔断;Z=zreal+1j*zimag
4) Rb: 4 法(zero_crossing/valley/low_freq_plateau/equivalent_circuit);深冷 plateau 优先;sigma=thickness/(Rb*area)
5) DRT(可选)[R^2<0 不作证据]   6) 相变分(可选)phase_detect 硬触发
→ status: OK / REJECTED_BY_QA / PARTIAL
```
> Arrhenius(序列级):4 模型竞争(单段 k=2 / 2段连续 k=4 / 3段连续 k=6 / 2段非连续 k=5,需 Chow p<0.05 + 跳跃>2σ);AICc + 5.0 改善阈值。

## 附录 D — Stage1 终止象限阈值表 + campaign

- 目标 `combined_score = log10(σ_room) - 3.0*Ea_high - 0.5*ea_low_excess`(maximize);`ea_low_excess=max(0, Ea_low-1.5*Ea_high)`。
- 参数域:R ∈ [0,1.04](焦磷酸极限),N ∈ [0.5,1.3]。S8 20-trial 不混入 attapulgite BO。

| 象限 | 函数 | 触发判据 |
|---|---|---|
| A 性能达标 | `_eval_performance` | σ_rt≥0.03 且 Ea_high≤0.10 且 ea_low_excess≤0.20 且 cs≥−1.6 且 ≥2 去重配方 |
| B 收敛 | `_eval_convergence` | ≥2 条:best_score 近 5 提升<0.10;近 3 (R,N) L2≤0.05;近 3 GP std≤0.20 |
| C 预算 | `_eval_budget` | trials ≥ 20 |
| D 异常 | `_eval_anomaly` | safety_box 连败≥2;贴边连续 2 次;stage0 连败≥3 |

## 附录 E — Stage3 主张阶梯 C0–C5 + 禁词表（`s14_claim_auditor.py` L136-163）

| claim 类型 | 阶梯 | 含义 |
|---|---|---|
| closed_loop_source_system | C1 | 单(母)体系测量/优化事实 |
| retrospective_validation | C2 | 跨批相对一致性 |
| llm_transfer_candidate | C2 | 跨体系迁移(选择/重组层) |
| prospective_validation | C3 | 冻结后实测的经验验证 |
| mechanism_discovery(别名 mechanism_consistency) | C4 | 机理一致性(封顶,保留替代解释) |

- 硬封顶 `_C4_CAP="C4"`:EIS 传输-only 绝不自动出 C5(结构/因果);超 C4 压回 C4。
- L1 closed_loop 仅当 `closed_loop_validity=="prospective_real" 且 n_rounds≥3` 才 supported。
- `claim_guardrails._ABSOLUTE_CLAIM_PATTERNS`(11 条正则):proves/证明/confirms/establishes/conclusively/definitively/unambiguously/EIS proves 等(命中记 ClaimViolation)。

## 附录 F — 创新点 live 接线真相表（file:line，截至 2026-07-05）

> 用于快速核对"文档所述创新在代码里到底接到哪一步"。均为纯加法、不改 legacy、fail-safe。

| 模块 / 声明 | live 接线真相 | 关键 file / 验证 |
|---|---|---|
| `epistemic.active_design` | 🟢 `_epistemic_next_action`(advisory 注入 prompt)+ `_active_design_canary_nudge`(canary 经 ActionGate 微调 setpoint,硬护栏:邻域/包络/回温≤15K;**H3:邻域 ±1→±2 step 多驱动**) | `hardware_adapter.py`;`p16` 8/8;`pH3` 7/7 |
| `epistemic` 认知证书(可观测性/最小判别集/e-process) | 🟢 收尾 `_run_epistemic` 真调 | `hardware_adapter.py`;fe4b:AIC=segmented、e-process log_E_max=4130 |
| `epistemic.impedance_models` | 🟢 收尾 `_run_epistemic_impedance` 对真机谱跑谱级机制辨识 → impedance_summary.json + EPISTEMIC_IMPEDANCE | `p15` 10/10;fe4b:31 谱、被动性全成立 |
| `epistemic.falsification_market` | 🟢 收尾 `_run_falsification_market`(opt-in)对真 σ(T) 跑多角色 LLM 市场(真 OpenRouter)→ MARKET_SETTLED | `p13b` 8/8、9 次真 LLM;fe4b:9 次真调 |
| stage3 机制推理链 | 🟢 收尾 `_run_stage3_reasoning`(S03→S04→S05→S06→S06b,真 LLM)→ stage3_reasoning_summary.json | `p9` 17/17;fe4b:3 次真 gpt-5.4、选定 H2 |
| 命令路径 enforce/canary | 🟢 **G-4 真机执行(fe4b)**:2 次 EPISTEMIC_CANARY_SETPOINT 物理执行(±0.3°C)、31 步护栏回退、bypass=0 | `action_gate.py`;`p21` 10/10 |
| 测量提交门控 mode(P13-D) | 🟢 `_commit_gate_mode`(shadow\|canary\|enforce)+ `_commit_gate_enforces()`;**G-4(fe4b)**:6 深冷点真拒出 BO、27 点零误拦、`.full` 审计备份 | `commit_gate.py`;`p17` 9/9;`p21` |
| G-2 真机故障注入 | 🟢 **fe4 执行**:`inject_fault`(多条)注入 SAMPLE_MISMATCH/QA_FAIL → 六用途全 REJECT、all_caught=true、温控/CHI 未受影响 | `_maybe_inject_governance_fault`;`p20` 10/10 |
| 逐点 agent LLM 忠实度 | 🟢 **两 bug 已修并真机复验(llmfix run)**:默认模型改 `openai/gpt-5.4`(旧 `deepseek-v3.1` 非法);`_json_default` 修 numpy 序列化 + `llm_called` 诚实化。复验:0 序列化失败、n≥11 步 11/11 真 LLM | `hardware_adapter.py`;`phase_detect._json_default` |
| C³-Harness 收敛证书 | 🟢 **H1 已消费**:`termination_evaluator._c3_consume` 单调安全消费(c3_stop⊆legacy_stop,只推迟非硬停);`evaluate_termination` 出 `verdict_effective`/`c3`;live `_finalize_c3` 落 `c3_evidence.json` | `closed_loop/termination_evaluator.py`;`pH1` 11/11 |
| 在线仪器见证 + 协议级故障注入 | 🟢 **H2 已实现并离线真验**:`OnlineInstrumentWitness`(真 CHI 文件 sha256 + TEMP_TRACE + 仪器态)→ EvidenceTransaction;ACK/仪器卡住/文件/条码/校准 6 类故障;`_run_instrument_witness`/`_finalize_instrument_witness` 接 live | `scientific_harness/instrument_witness.py`;`pH2` 17/17。**live 终验待旧材料 run;物理破坏性故障须 dummy cell** |
| Rb-ACT R4 | 🟢 **H4 激活模式已实现**:三条件人审门 + σ_v2 + delta + "BO 不劣化"守卫;离线 87 真谱验 `legacy_overwritten=0`/Spearman=0.995/`bo_not_degraded=true`。R0–R3 真接 + **G-5 审计门全过**(87 真谱/75 配对点) | `rb_act/activation.py`+`prereg.py`;`p18` 12/12;`pH4` 6/6。**真机替换态须签核 token,跨批生产激活属 G-5** |
| live 回路 BO | 🟡 收尾一次性 post-sweep BO(非逐点内层);`entered_bo`=准入标记 | `post_processing.json` |

> 收口 Plan(把 🟡/🔴 真实补齐,含 H 系列)见 `OPTIMIZATION_EXECUTION_PLAN`。**H1–H4 已软件实现 + 离线真验;H2/H3/H4 的 live 终验待旧材料一次全温区 run。**
