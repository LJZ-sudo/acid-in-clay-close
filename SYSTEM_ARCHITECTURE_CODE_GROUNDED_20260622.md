# 系统架构（代码实证执行追踪，2026-06-22,2026-06-24 重写）

> 所有 file::function / 参数 / 决策节点 / 事件名均来自对真实源码的逐文件读取(4 路并行代码探查),未取自总结文档、未臆造名字;存根/只读/已禁用处均如实标注。
> 与论文 Fig 1(抽象示意)互补:这里是内部"它到底怎么跑"。密钥读 `key.txt`/`.env`;LLM 经 OpenRouter。
> 诚实总纲:S09 候选生成 + S10 排序默认走确定性(非 LLM);Stage1 闭环的 LLM 只在 Step5 修正建议;v2 科学声明恒 HOLD、CHI 自动化恒关。项目从不声称"LLM 独立发现 LRS"。
> (本版用 ASCII 结构字符重写——原 Unicode 框图在一次 PowerShell 误操作中编码损坏;内容已据幸存的真实 file::function 标识 + 本会话改动如实恢复。)

## 执行链路（人 -> Stage0 -> Stage1 -> Stage2 -> Stage3 -> 后端 -> v2守卫 -> B轨创新）

```text
[人/实验员/领域专家]
  - 前瞻纪律:改任何参数前先 git commit+push 盖时间戳(prospective_2026H2)
  - 选 campaign(凹凸棒土 attapulgite_aice)+ R/N 配方;或离线复算历史数据
  - 真机:在 /control 连硬件(COM3 TemperatureDriver + ChiExecutor)启动测量
      |-- (真机在线) --> Stage0       |-- (离线/复算) --> Stage0

[1] STAGE 0  测量 -> 证据   (stage0_measurement/)
  离线入口: run_offline.py :: OfflineBatchWorkflow  (7 CLI: --data_dir --material
    --thickness --area --chi_pattern --output_dir --disable_reporting;7 步序列)
  逐温点 EIS 管线: eis_pipeline.py :: analyze_eis_point  (严格 5 步)
    1) QA   data_quality.py :: assess_data_quality  [确定性·一票否决]
         致命1: 250kΩ 量程触顶;致命2: 低频失真>3 次 -> REJECTED_BY_QA
    2) KK   kk_validation.py :: validate_kk_consistency (v5.0)
         中位数判据 mu_median<0.2;警告模式不熔断(只置 kk_warning)
         符号 bug 已修: Z = zreal + 1j*zimag(历史误用 -1j 已废)
    3) Rb   rb_fitting.py  [确定性·4 策略路由,深冷->常温]
         深冷 low_freq_plateau 优先;否则 zero_crossing -> valley -> plateau -> ECM 兜底
         sigma = thickness/(Rb*area)  (几何来自 CLI)
    4) DRT  drt_analysis.py(Tikhonov+L-curve)[本数据 R^2<0,不作证据]
    5) 状态判定 -> OK / suspect (status, validity_flags)
  相变检测: phase_detect.py :: analyze_experiment_state
         Rb 单步跳跃/累积增长 = 硬编码触发,无需 LLM
         LLM 路径用 PHASE_DETECT_MODEL(默认 gpt-5.2),仅在线有效;
         离线 create_phase_detector() = DEPRECATED/PLACEHOLDER 恒返回 False
  Arrhenius 分段: arrhenius.py :: analyze_arrhenius  [确定性·竞争多模型]
         4 模型: 单段/2段连续/3段连续/2段非连续(+Chow Test);AICc 权重 + 5.0 改善阈值;
         序列级 extract_valid_arrhenius_series() Rb 单调性过滤剔反常跳点;
         产物: transition_temps_K[], segments[](Ea_eV/slope/n_points/温区)
  聚合落盘: aggregated_results.json / arrhenius_analysis.json / offline_run_manifest.json
  后处理 CLI(独立): run_closure_offline.py :: result_bundle.build_bundle_for_sample()
         -> stage0_result_bundle.json + closure_report.json (注:bundle 非 run_offline 生成)
  在线入口: run_online.py :: 真机逐温点测量(--material --chi_data_dir ...)
         --harness_mode shadow|canary|enforce(默认 shadow):create_eis_analyzer 旁路喂
         scientific_harness 记 C_P/C_M/C_E 对账 -> shadow_harness_log.jsonl(只记录、fail-safe)
  WS(在线): temperature_update / measurement_complete / phase_transition
      | sigma(T)·Ea·T_break·quality_flags (经 canonical_input 摄入)
      v
[2] STAGE 1  闭环优化(物理<->数字)  (stage1_optimization/)
  主入口: run_optimization_loop.py :: main() -> OptimizationOrchestrator.run_optimization_loop()
         (--optimizer bo|mobo, --mode replay|virtual_oracle|real, --optimizer_seed)
  前瞻冻结入口: line_b_guardrail_run.py :: main()(FROZEN_SEED=20260608,只跑 Step4-6,
         不写 history_db,写 official_recipe.json)
  Step1 解析 Stage0 [确定] canonical_input/state0_parser.py :: extract_objective_metrics()
         -> conductivity_room_temp_S_cm/ea_high_temp_eV/ea_low_excess_eV/n_segments/combined_score/objective_valid
         [T-real 闸] mode==real 且 objective_valid==False -> raise(拒坏数据入库)
  Step2 记忆固化 [确定·幂等] campaign_memory/memory_manager.py :: add_trial(...) + _find_duplicate_trial 去重
  Step3 查询历史最优 [确定] get_best_trial(...);**G7 守卫**:objectives/registry.py::
         assert_campaign_matches_role 校验 campaign 目标键/方向 == 注册表 training 角色(漂移即报错)
  Step4 左脑·优化器 optimizers/mobo_optimizer.py :: MOBOOptimizer.suggest_next() [T1]
         三目标 locked_v2_objectives;冷启动 len(P)<5 LHS;ParEGO(Dirichlet+Augmented Tchebycheff)
         GP[Matern2.5]+EI;纯函数审计 pareto_front_indices/dominated_hypervolume;
         (噪声感知 v2: optimizers/botorch_mobo_v2.py :: NoiseAwareParEGO / BotorchMOBO(train_Yvar+qLogNEHVI))
  Step5 右脑·LLM 策略规划 [LLM] agents/strategy_planner.py :: decide_with_fallback->decide_next_step [T2]
         gpt-5.4, temperature=0.0, max_tokens=8000;只存 prompt sha256(M2-5 PromptEnvelope/
         P0-4 LLMCallBundle 可存完整加密调用包,公开侧只发 sha256);
         Pydantic 校验 + 值域校验;失败 -> 降级纯优化器(conf=0.5)
         (实弹: raw MOBO R=0.0285/N=0.9841 -> LLM 修正 R=0.28/N=0.96, safety pass)
  Step6 输出方案 [确定] safety_validator.validate [T-safety] + round_logger 三件套 SHA256 链
  终止评估: termination_evaluator.py :: evaluate_termination()(A 性能/B 收敛/C 预算/D 异常)
      | history_db_attapulgite.json (R/N -> combined_score)
      v
```
```text
[3] STAGE 2  统计 -> 证据图谱   (stage2_statistics/)
  产物 canonical: exports/stage3_seed.json (schema 0.2.0, source_system=s8_reference,
    stage3_ready=True, input_hashes);8 类 EvidenceUnitV2;V1 atlas 仅诊断;
    S8 海泡石母体系仅作证据/先验,不混入凹凸棒土 BO 训练库
      | stage3_seed.json (input_hashes 锚定)
      v
[4] STAGE 3  机理推理 + 候选生成 + 主张治理   (stage3_mechanism/src/s8_stage3/)
  编排: orchestrator/pipeline.py :: run_from_seed (S04->S14, run_manifest 记 stage2_seed_sha256)
  S04 假设 -> S05/S06 机制仲裁 -> S07 描述符 -> S08 文献(OpenAlex live)[上游 LLM 真实参与]
  S09 候选族生成 agents/s09_candidate_family_generator.py [T-S09]
       默认 STAGE3_S09_DETERMINISTIC_FROM_D4=True -> _build_d4_deterministic_output()
       硬编码 F1/F2/F3 + I1-I5,不调 LLM(有意冻结=锁时间戳+可复现,非"偷偷写死冒充 AI 发现")
  S10 排序打分 scoring/candidate_audit.py :: audit_candidates [T-S10]
       默认 STAGE3_S10_DETERMINISTIC_FROM_AUDIT=True;material_priority_score=8 维加权(附录A)
  S14 主张审计 agents/s14_claim_auditor.py [T-claim 阶梯封顶]
       C0-C5;EIS-only 硬封顶 C4(机理不可声称);claim_guardrails 11 条绝对化措辞正则
       (M2-5: mechanism_consistency 为 mechanism_discovery 的首选别名)
  Agentic 旁路(advisory) orchestrator/agentic_review.py(全确定性,不触碰冻结 pipeline)
  产物: 09_ranking / 12_validation_binding / 13_claim_audit(publication_blockers)
      v
[5] 后端 API + 驾驶舱(只读看板 + 控制)  (backend_api/ + frontend/)
  入口: backend_api/main.py FastAPI ⊂ socketio.ASGIApp;uvicorn :8000
  路由(10): /api/control(真·驱动硬件) /api/agent(规则环+LLM兜底) /api/data /api/runs
    /api/samples(只读) /api/campaigns(只读) /api/provenance(只读) /api/agents
    /api/pipeline(已禁用,返 disabled) evidence_jobs(threshold_sweep/ablation 已做实 M1-8)
  /api/agent 决策环 :: agent.py::_run_decision_cycle (SSE)
    _planner_propose -> _critic_review(QC C/D->RE_MEASURE) -> _orchestrator_decide
    -> **ActionGate.submit**(WP4 Cutover:不再直连 hw.enqueue_command;默认 shadow 照常下发=
       行为不变,enforce 阻断 allowlist 外;审计 autonomous_bypass=0,fail-closed)
  Socket.IO: hardware_adapter.py::_emit_event;通道 temperature_update/measurement_complete/
    phase_transition/status_change/thought_chain_event
  前端: frontend/ React+Vite+AntD;vite proxy :5173 -> :8000;页面 /control /monitor /analysis ...

[6] 三创新点 v2 守卫引擎(独立 CLI, HOLD 偏置)  (three_pillars/pillar3_.../v2_engine_tools/)
  v2tools_common.py: sha256_file/rollup_hash/scan_forbidden(25 禁用语)/safe_out_path(拒写主线)
  verify_append_only_chain.py / verify_approval_binding.py / run_all_checks.py(HOLD 偏置:
    全过才 DRYRUN_ALLOWED;硬编码 v2_claims_status="HOLD", enables_chi_automation=False)
  审计: scripts/audit_mainline.py(只读) 扫残留绝对路径 + schema/泄漏正则
```

## B 轨 Agent 方法学创新（WP0-WP5 已落地,Tier S 目标）  (stage1_optimization/scientific_*/)

> 与冻结闭环互补;**软件层,未经真机故障对照,不擅自计入档次**。

```text
-- SciTX 三重提交 Harness  scientific_harness/
   commits.py: PhysicalCommit C_P / MetrologicalCommit C_M / EpistemicCommit C_E
   witness.py(WP1-c): 三类 ID(ExecutionAttempt/PhysicalEffect/evidence)+ 多见证推断 C_P
        仅软件见证 => 至多 possible;独立文件+DONE => confirmed;样品错配 => unknown
   admission.py(WP1-a/b): C_M(intended_use) U1-U6 分级 + C_E(claim_id) 绑定主张
        EIS 封顶 C4;断点与 Rb 方法切换重合 => CONTESTED;过度声称 => REJECT
   transaction.py(WP1-d): EvidenceTransaction 编排 尝试->见证->C_P->C_M->C_E
        不变量 not C_P => 全拒;not C_E(BO) => 不入;blind_retry=0;三 ID 分离
   action_gate.py(WP4): ActionGate 自主硬件命令唯一受控入口
        shadow 照常下发=行为不变 / enforce 阻断 allowlist 外
   commit_controller / reconciler / event_store(SHA256 链)/ fault_injection / shadow(接 run_online)
-- E-Mem 证明携带记忆  scientific_memory/
   claim_graph.py: 四值逻辑超图 + 最小支持集;invalidation_engine.py: 失效传播
   snapshots.py(WP3-a): 版本快照 + 写门(stale=>REBASE / 用失效证据=>REJECTED)
   root_dedup.py(WP3-b): 独立证据根去重(多 Agent 同 DOI 只计一根)
   bo_rebuilder.py(WP3-c): 失效->CommittedObservationView 重建 + DecisionImpact;
        apply_revocation_impact 桥接 PC-Skills 撤销->BO 重建
   history_bridge.py / bo_retrain_bridge.py(WP3-e): 真实 history_db 物化为 committed 视图 +
        CommittedMemoryView -> 优化器在更小集上重新拟合 GP(闭环到底)
   compression.py(WP3-d): 压缩证书(主张不增强/反证零损失/决策不变,否则拒)
-- PC-Skills 可认证 Skills + 双账治理  scientific_skills/
   skills_eis.py(WP2-b): 6 真实 EIS Skill(组合 post|=pre + 环境前置)
   certificate_service.py(WP2-c): 形式/统计/计量三层证书(Wilson 下界;小样本 provisional;
        证书由检查产生不可手填);runtime.py: 执行 gate + Evidence Bundle;
        drift.py/revocation.py: 漂移 SUSPEND/DEGRADE + 撤销作废证书
   dual_account.py: 认知账户(Brier) ⊥ 执行账户(RiskClearing,忽略自报置信)
-- 端到端撤销演示(WP5)  scientific_e2e/demo_end_to_end.py
   认证 Skill->SciTX 事务(含故障点)->无效不进 BO->撤销 Skill->E-Mem 失效->BO 视图重建->best E1->E3
   governed 严格优于 ungoverned(无效准入/BO 污染/错误最优存活 全 0 vs 基线 1);真实 B0/B2/B4/B5 臂 + 场景族
   ro_crate.py: RO-Crate 复现包
验证: 全量 tests/+backend_api/tests/ = **208 passed**;硬件写路径审计 autonomous_bypass=0
   (scripts/audit_hardware_write_paths.py --strict 过)
-- 配套 v2 分析(M0-M2,只产 *_v2 旁路,绝不覆盖 legacy)  _new_data_analysis/stage0_v2/:
   versions · rb_method_invariance · arrhenius_robust · breakpoint_uncertainty ·
   synthetic_validation · identifiability_v2 · repro_floor_variance · conductivity_uncertainty

全程护栏: replay != real · 每体系独立 history_db · claim 审计 · 前瞻冻结
```
---

## 决策节点速查(真实代码)

| 节点 | 位置 | 判据 | 后果 |
|---|---|---|---|
| T-real(坏数据闸) | `run_optimization_loop.py` Step1 | mode==real 且 objective_valid==False | raise,拒绝写 DB |
| T-G7(口径漂移) | `objectives/registry.py::assert_campaign_matches_role` | campaign 目标键/方向 != 注册表 training | raise |
| T1 优化器模式 | `mobo_optimizer.suggest_next` | len(P)<5 | 冷启动 LHS;否则 ParEGO |
| T2 LLM 规划 | `strategy_planner.decide_with_fallback` | LLM/JSON/键/值域任一失败 | 降级纯优化器(conf=0.5) |
| T-safety | `safety_validator.validate` | 越 campaign 边界 | passed=False(N/R 极值仅 warning) |
| 终止 A/B/C/D | `termination_evaluator` | 性能/收敛/预算/异常 | continue/can_end/must_end |
| T-S09 模式 | `s09_candidate_family_generator` | STAGE3_S09_DETERMINISTIC_FROM_D4 | 默认硬编码 I1-I5(非 LLM) |
| T-S10 模式 | `candidate_audit.audit_candidates` | STAGE3_S10_DETERMINISTIC_FROM_AUDIT | 默认确定性排序 |
| T-claim 封顶 | `s14_claim_auditor` | EIS-only 证据 | 硬封顶 C4(机理不可声称) |
| v2 gate | `run_all_checks.run_all` | 任一检查未过 | HOLD(科学声明恒 HOLD) |
| T-CP(物理见证) | `scientific_harness/witness.py` | 仅软件见证 | 至多 possible(非 confirmed) |
| T-gate(WP4) | `scientific_harness/action_gate.py` | 自主命令 + enforce + allowlist 外 | BLOCKED;shadow 则照常下发 |

## 确定性 vs LLM(诚实标注)

- **确定性(无 LLM)**:Stage0 全管线(QA/KK/Rb/Arrhenius/相变硬触发)、Stage1 优化器+记忆+终止+安全、**S09 默认生成、S10 默认排序、S14 阶梯、agentic 旁路、v2 守卫、B 轨三包的判定逻辑**。
- **真实 LLM 调用**:Stage1 Step5 策略规划(gpt-5.4,temp 0.0,只存 prompt 指纹/可选完整加密包);Stage0 在线相变可选(gpt-5.2);Stage3 上游 S04-S08;S09 仅在两 flag 关闭时。
- **关键诚实点**:发表那次 S09/S10 是有意冻结的确定性(锁时间戳+可复现);项目主张温和:"LLM 从广义文献池选择并重组 + 实验前冻结 + 事后 EIS 验证"(B+),从不声称"LLM 独立发现 LRS"/收敛/事后改分。

## 真实可运行 vs 只读/存根/已禁用

| 组件 | 状态 |
|---|---|
| Stage0 离线/在线、Stage1 闭环、Stage2/3 编排 | 真实可运行 |
| /api/control(驱动硬件)、/api/agent(决策环) | 真实可运行 |
| /api/provenance、/api/campaigns、/api/samples | 只读真实 |
| /api/pipeline 的 mutating 端点 | 已禁用(返 disabled,指向正确替代) |
| evidence_jobs threshold_sweep / ablation | 已做实(M1-8,读 v2 真实产物;缺失返回生成命令而非伪造) |
| three_pillars v2 工具 | 真实可运行,但 v2 科学声明恒 HOLD、CHI 自动化恒关 |
| B 轨三包(`scientific_harness`/`scientific_memory`/`scientific_skills`,WP0-WP5) | 真实可运行(**208 测试全绿**;跨层失效闭环互联 + 端到端撤销演示;含 C_M(用途)/C_E(主张)/多见证 C_P/三层证书/失效->BO 闭到 GP 重训);**软件层,未经真机故障对照,不擅自计入档次** |
| `routers/agent.py` 自主硬件命令(`ActionGate`,WP4) | 已收口唯一入口;默认 shadow=行为不变,enforce 可拦截;审计 `autonomous_bypass=0`、`--strict` 过、fail-closed |
| `run_online.py --harness_mode shadow\|canary\|enforce` | 真实可运行;shadow 对定温扫描有效;canary/enforce 诚实降级 shadow(属自主路径),待 G1 启用 |
| `_new_data_analysis/stage0_v2/*` v2 分析 | 真实可运行,只产 `*_v2` 旁路产物,绝不覆盖 legacy 冻结结果 |
| stage0_result_bundle.json | 由 `run_closure_offline.py` 生成(非 run_offline.py) |
| 离线 create_phase_detector() | DEPRECATED/PLACEHOLDER,恒返回 phase_detected=False |

> 溯源:本文件由对 `stage0_measurement/`、`stage1_optimization/`、`stage3_mechanism/`、`stage2_statistics/`、`backend_api/`、`frontend/`、`three_pillars/` 真实源码逐文件读取得到;file::function 与参数均可在源码核对。
---

## 附录 A — 下钻①:`material_priority_score`(S10 确定性排序内核)

> `scoring/candidate_audit.py :: audit_candidates`(L358-477),每候选 deterministic 打分。8 个主权重和为 1.0,外加两项调整。全确定性、无 LLM。

```text
material_priority_score = clamp(                      # L444-455
    0.20*mechanism_fit + 0.18*evidence_quality + 0.18*formulation_completeness
  + 0.14*low_temperature_plausibility + 0.11*processability + 0.10*(1-risk)
  + 0.05*novelty + 0.04*citation_validity            # 8 主维, sum weight=1.00
  - term_leakage_penalty(0.0 或 source_term_ok=False 时 0.3)
  + 0.05*prospective_status_score )                  # 1.0 当有 S13 绑定前瞻验证,否则 0.0
# 独立门控 audit_gate_score = clamp(L431-437):0.35*descriptor_claim_coverage
#   + 0.15*citation_validity + 0.35*novelty + 0.15*(1-risk) - leakage + 0.05*prospective
```

| 分量(权重) | 函数::行 | 计算要点 |
|---|---|---|
| mechanism_fit(0.20) | `_mechanism_fit_score` L311 | 0.45*descriptor_claim_coverage + 0.35*roles + 0.20*clamp(core+bonus) |
| evidence_quality(0.18) | `_evidence_quality_score` L290 | 每对支持 conf+0.10(定量锚)取均 + diversity + pair_count |
| formulation_completeness(0.18) | `_formulation_completeness` | 配方角色完整度(host/acid/clay/additive) |
| low_T_plausibility(0.14) | `_low_temperature_plausibility` L326 | 基 0.25;冷/253/193、bound-water、attapulgite、pva/starch/chitosan 加分;bulk water 减分 |
| processability(0.11) | `_processability_score` L344 | 基 0.55;film/membrane 加;dispersion/brittle/swelling 减 |
| (1-risk)(0.10) | `_risk_score` L207-232 | free-acid-leakage/bulk-water-freez .25 … reproducibility .04 |
| novelty(0.05) | `_NOVELTY_BASE` L20 | novel_combination 0.85 / close_variant 0.55 / exact_match 0.25 |
| citation_validity(0.04) | `_citation_validity` | 候选引用 card_id 落在有效文献卡集合的比例 |

> M6 实测:该确定性分对权重留一/200-seed 扰动 top1_stability=1.0(稳健;但流行度基线也能选中 LRS,见 m6 报告)。

## 附录 B — 下钻②:`pipeline.py :: run_from_seed`(S03->S14 编排全链)

```text
run_from_seed(seed):                                  # pipeline.py L101
  状态串行: evidence -> hypothesis_board -> mechanism_lit -> arbitration
            -> descriptor_sheet -> material_lit -> family_set -> instance_set -> ranking
  派发(L142-245):
    s03_evidence_builder      [确定·证据装配]
    s04_hypothesis_generator  [LLM 假设]      s05_literature_scout_mech [LLM 机制文献]
    s06_mechanism_arbiter     [LLM 机制仲裁]  s06b_design_principle_extr [设计原则]
    s07_descriptor_extractor  [LLM 描述符]    s08_literature_scout_mat   [LLM OpenAlex]
    s09_candidate_family_gen  [默认确定 _build_d4]  s10_instance_ranker [默认确定 audit 排序]
    s12_prospective_registry  s13_validation_binder  s14_claim_auditor [确定·C0-C5 封顶]
    s11_report_compiler       [最后才编译报告]
  每步 _run_guardrails -> no_leakage_checker;_run_source_term_audit 检 S08 污染
```
- self.gateway 传给 s04-s08 = 上游真 LLM;s09 生成/s10 排序默认确定性;s14 阶梯确定性。
- 每步 output_hashes + guardrail_warnings 落 run_manifest(记 stage2_seed_sha256)-> 全链可溯源。
- s11 报告编译排在 s14 之后(报告须等主张审计定稿)。

## 附录 C — 下钻③:`eis_pipeline.py :: analyze_eis_point`(单温点 5 步,L45)

```text
1) 数据清洗 np.array, temperature_K=T_C+273.15
2) QA 一票否决 assess_data_quality: max_impedance_fatal=250000Ω; noise_reversal_fatal=3 -> REJECTED_BY_QA
3) KK validate_kk_consistency(v5.0): mu_median<0.2;is_valid=False 只置 kk_warning 不熔断;Z=zreal+1j*zimag
4) Rb fit_rb_and_conductivity: 4 法(zero_crossing/valley/low_freq_plateau/equivalent_circuit);
   路由 深冷 plateau 优先,否则级联;valley_prominence=0.15;sigma=thickness/(Rb*area)
5) DRT(可选) [R^2<0 不作证据]   6) 相变分(可选) phase_detect 硬触发
-> status: OK / REJECTED_BY_QA / PARTIAL;字段 kk_warning/rb_method/kk_score
```
> Arrhenius(序列级):4 模型竞争(单段 k=2 / 2段连续 k=4 / 3段连续 k=6 / 2段非连续 k=5,需 Chow Test p<0.05 + 跳跃>2σ);AICc 权重 + 5.0 改善阈值防过拟合。

## 附录 D — 下钻④:Stage1 终止象限阈值表 + campaign

- 目标 `combined_score = log10(σ_room) - 3.0*Ea_high - 0.5*ea_low_excess`(maximize);`ea_low_excess=max(0, Ea_low-1.5*Ea_high)`。
- 参数域:R ∈ [0,1.04](1.04≈H2P2O7 焦磷酸极限),N ∈ [0.5,1.3]。S8 20-trial 不混入 attapulgite BO。

| 象限 | 函数 | 触发判据(真实阈值) |
|---|---|---|
| A 性能达标 | `_eval_performance` | σ_rt≥0.03 且 Ea_high≤0.10 且 ea_low_excess≤0.20 且 cs≥−1.6 且 ≥2 个归一 L2≥0.05 去重配方 |
| B 收敛 | `_eval_convergence` | 需≥2 条:best_score 近 5 trial 提升<0.10;近 3 次 (R,N) 归一 L2≤0.05;近 3 次 GP std≤0.20 |
| C 预算 | `_eval_budget` | trials ≥ max_total_trials=20 |
| D 异常 | `_eval_anomaly` | safety_box 连败≥2;推荐贴边连续 2 次;stage0 连败≥3 |

> 安全验证 `safety_validator.validate`:硬边界越界->passed=False;N>n_high*0.9 / N<n_low*1.1 / R>0.9 -> warning;ea_low>1.5*ea_high -> Arrhenius 退化告警。

## 附录 E — 下钻⑤:Stage3 主张阶梯 C0-C5(`s14_claim_auditor.py` L136-163)+ 禁词表

| claim 类型 | 阶梯 | 含义 |
|---|---|---|
| closed_loop_source_system | C1 | 单(母)体系测量/优化事实 |
| retrospective_validation | C2 | 跨批相对一致性 |
| llm_transfer_candidate | C2 | 跨体系迁移(选择/重组层) |
| prospective_validation | C3 | 冻结后实测的经验验证 |
| mechanism_discovery(别名 mechanism_consistency) | C4 | 机理一致性(封顶,保留替代解释) |

- 硬封顶 `_C4_CAP="C4"`:EIS 传输-only 绝不自动出 C5(结构/因果);超 C4 一律压回 C4(L160-161)。
- L1 closed_loop 仅当 `closed_loop_validity=="prospective_real" 且 n_rounds≥3` 才 supported。
- `claim_guardrails.py :: _ABSOLUTE_CLAIM_PATTERNS`(11 条正则):proves/证明/唯一说明/confirms/establishes/conclusively/definitively/unambiguously/等效电路已确定/EIS 已证明/EIS proves(命中即记 ClaimViolation,带 ±60 字上下文)。




