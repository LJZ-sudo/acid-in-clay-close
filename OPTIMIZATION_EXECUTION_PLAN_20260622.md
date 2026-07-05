# 优化执行计划（EXECUTION PLAN，现状快照：2026-07-05）

> 这是一份**可执行、可勾选、可验收**的执行计划。判档/就绪度见 `_new_data_analysis/PUBLICATION_READINESS.md`;架构与真实 `file::function` 见 `SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md`;现状家底见 `PROJECT_SITUATION_REPORT_20260622.md`。
> 本版为**重写版**:合并了此前所有分日期(WP0–WP5 / ESAS-OS 2.0 / Epistemic-OS / P13-A~F / G-系列 / H 系列旧材料硬化)的进展层,只保留截至 2026-07-05 的真实状态——**已完成什么、还差什么**。历史 run 用 run-id 标识。

> **双轨铁律(贯穿全程)**:
> ① **A 轨(材料/EIS/治理)与 B 轨(Agent 方法学)都必须做、并行推进**——不是二选一。A 占实验台,B 主要纯代码,天然并行。
> ② 改任何影响主张的参数/阈值前,先 `git commit + push` 盖时间戳(`prospective_2026H2` 纪律)。
> ③ **绝不覆盖已发表/冻结产物**——一律产 `*_v2` 并行版 + `delta_report`;阈值/策略先写进 `configs/*` 冻结再跑全量。
> ④ 除 **G-1 与后续凹凸棒土闭环**外不新增湿实验;故障评测一律用空载/参考电路/dummy/软件注入,**不在贵重样品上做破坏性物理注入**。
> ⑤ **不用"软件 Demo/测试通过"预支 Tier-S 档次**——档次由真机证据决定。

---

## 1. 现状基线与双轨目标

**现状(一句话)**:Stage0–3 科学主线真实运行(R4);B 轨三包(SciTX/E-Mem/PC-Skills)+ ESAS-OS 2.0 四插件 + Epistemic-OS 认知层软件全体系已落地,且**已在真机 live 回路里跑通治理、逐点 LLM 决策、收尾机制推理与认知证书**;距 Tier-S 的真机硬门已收 **G-2🟢 + G-4🟢 + G-5🟡**,剩余 **G-1 / G-3 / G-5 人审激活**须物理条件。

| 对象 | 成熟度 | 目标 | 仍差什么 |
|---|---|---|---|
| Stage0–Stage3 科学主线 | **R4** 真实运行 | R4 保持 | — |
| SciTX → **C³-Harness** | **R4(命令路径)** | R5 | 命令路径旁路=0、enforce 真机执行(G-4)已过;**C³ 证书只写盘、主循环不消费停机** |
| E-Mem → **R²-Memory** | **R4(失效→BO 链 + live 注入)** | R4 保持 | 失效→GP 重训闭到底;live prompt 注入已接;余真机多批重放 |
| PC-Skills → **Rb-ACT** | **R3(→R4 审计门已过)** | R4 | R0–R3 真接;R4 预注册审计全过;**R4 生产替换未激活(须人审,G-5)** |
| Epistemic-OS 认知层 | **R3(已接 live 收尾)** | R4 | 认知证书/阻抗/证伪市场/active_design 均接 live;余谱级 vs σ 层内层控制、多批 |
| 三者集成 | **R4** | R5 | enforce 生产执法(G-4)已过;余多批 live 互证(G-3)+ 新 R/N(G-1) |

> R0=概念,R1=Schema+代码,R2=单测/软件 Demo,R3=真实流程 shadow / 跨层闭环,R4=真实流程强制路径,R5=多批真机+故障对照+跨场景。
> 工程成熟度 ≠ 论文档次;主线仍是 human-supervised 半闭环,非"完全自主"。

---

## 2. 必须写进代码的 12 条系统不变量（B 轨权威性的硬约束，均已落地）

1. Agent 不得直接访问 `hw.enqueue_command` 或厂商驱动。(✅ ActionGate 唯一入口)
2. 人工 override 必与自主路径隔离,产生 `HumanOverrideEvent`。
3. 每次调用尝试、物理作用、证据记录必须有不同 ID。
4. 未解析物理状态的超时不得重试。(✅ blind_retry=0)
5. Instrument success 不得自动生成 `PhysicalEffect=confirmed`。
6. `PhysicalEffect=confirmed` 不得自动生成 `MetrologicalCommit`。
7. `MetrologicalCommit` 必须绑定 `intended_use`。
8. `EpistemicCommit` 必须绑定 `claim_id` 与允许的最高主张等级。
9. 未 Committed 的观察不得进入 BO、长期记忆或论文事实表。
10. Agent 输出/摘要/重复转述不得形成新的独立证据根。(✅ root_dedup)
11. Skill 只能在有效证书和适用包络内执行。
12. 证据/校准/分析版本/Skill 失效时,必须产生下游影响报告并重建可用视图。

> 审计:`scripts/audit_hardware_write_paths.py --strict` 实测 `autonomous_bypass=0`、exit 0。

---

## 3. 三阶段切换 + Rb-ACT 五级接入门

**自主硬件命令三阶段切换**(不得跳过):

| 模式 | 控制权 | 场景 | 真机现状 |
|---|---|---|---|
| **SHADOW** | legacy 控制,SciTX 只记录 | 初始真机对账 | ✅ 4 次 live run 全程 shadow 记录、0 翻转 |
| **CANARY** | 少数低风险动作经 SciTX | 相邻候选微调 setpoint | ✅ **G-4(fe4b)**:2 次 `EPISTEMIC_CANARY_SETPOINT` 物理执行、bypass=0 |
| **ENFORCE** | 自主模式唯一经 PC-Skills+SciTX | 测量提交门控 | ✅ **G-4(fe4b)**:6 深冷点真拒出 BO、27 点零误拦 |

> **测量提交路径**与**命令路径**门控解耦:`_commit_gate_mode`(测量)+ `ActionGate`(命令);**温控/CHI 物理命令永不纳入门控**(安全)。

**Rb-ACT 五级接入门**(唯一会改写数值链的 v2,逐级解锁):

| 级 | 接入方式 | 对结论作用 | 现状 |
|---|---|---|---|
| **R0** | 离线 shadow(历史/合成谱) | 0(纯观察) | ✅ 已过 |
| **R1** | 在线双跑,仍用 legacy 值 | 0(留痕) | ✅ 已过(真谱双跑 0 翻转) |
| **R2** | 审计接入(进 C_M,不进 BO) | 仅收紧准入 | ✅ 已过(`rb_r4_*` 审计-only 信号喂 txn) |
| **R3** | 噪声接入(Rb-ACT 方差喂 `train_Yvar`) | 改 BO 权重,不改历史 σ | ✅ 已过(`noise_source=RB_ACT_METROLOGICAL_DIRECT`) |
| **R4** | 正式替换(Rb-ACT 后验均值作主值) | 改数值链 | 🟡 **预注册审计门全过(G-5),生产激活未开**(`legacy_override=False`,须人审) |

---

## 4. 已完成（合并快照，均可复算 + 测试/真实数据覆盖）

### 4.1 A 轨分析门 + B 轨软件底座

- **M0–M2 分析门**(纯代码,`_new_data_analysis/stage0_v2/`):冻结/版本化 + Rb 方法不变性 + 合成 FPR + 稳健 Arrhenius + 证据准入 + 断点 CI + 评分注册表(G7)+ 可辨识性 + 复现地板层级方差 + 噪声感知 MOBO + LLM vs 5 基线 + PromptEnvelope。
- **A 轨 G1 主门**:线 B 同配方 3 片独立重复 → `LINE_B_LOCAL_DIRECT`(WARM median 0.106/p90 0.146 dex、COLD median 0.158/**p90 0.356 dex**);去 Fig3 生物聚合物代理 caveat。**诚实边界**:n=3 回溯离线数据、冷段比代理松。
- **B 轨 WP0–WP5**:WP0 语义/审计(ObjectiveRegistry/DatasetRegistry 13/15/术语别名/LLMCallBundle/硬件写路径审计)· WP1 SciTX(`EvidenceTransaction` + C_M(U1–U6)/C_E/多见证 C_P + `--harness_mode`)· WP2 PC-Skills(6 EIS Skill + 三层证书 + drift/revocation + 双账户)· WP3 E-Mem(快照写门/根去重/失效→BO 重建→**GP 重训**/压缩证书)· WP4 Cutover(`ActionGate` 唯一入口 → `autonomous_bypass=0`)· WP5 评测(端到端撤销演示 governed 严格优于 ungoverned + B0/B2/B4/B5 真实臂 + RO-Crate)。
- **ESAS-OS 2.0 四插件**:P0 测量事务化(`measurement_txn`)· P1 Rb-ACT(`rb_act`)· P2 R²-Memory(`agent_memory`,forbidden-use 拦截 100%)· P3 C³-Harness(`scientific_convergence`,C³ 停⊆legacy 停)。**默认 shadow/旁挂,legacy 永不覆盖**。

### 4.2 Epistemic-OS 认知层(GPT 三原创方向)

- **① 阻抗级正问题** `impedance_models.MechanismModel.impedance_forward_operator`:三竞争 ECM 对真机谱拟合,被动性/λ_min/机制随温演化。诚实:电极阻塞下绝对体相 R 弱可辨识。
- **② 三对象驱动内层选温** `active_design.select_next_temperature`:后验加权 JS/成本;replay 自适应 6 点 vs 均匀 14 点。
- **③ 多角色 LLM 证伪市场** `falsification_market`:Proposer/Falsifier/Auditor(真 gpt-5.4)+ Referee 真数据结算;过度自信稻草人信誉崩到 0.10。
- **④ 跨批复现互证**:三批真实测量相变 T 跨批 CV 0.5%/0.9%。

### 4.3 LLM 大脑接闭环

- **逐点 LLM agent**:`R²-Memory 投影 + C³ 收敛证书 + active_design 建议` 注入 prompt,真调 `openai/gpt-5.4`。
- **收尾机制推理链**:`live_seed_adapter` 把 live 测量→Stage3SeedBundle→S03→S04→S05(真 OpenAlex)→S06→S06b,真 LLM 驱动。

### 4.4 A 组收口 P13-A~F(软件侧,均已真实实现)

| ID | 内容 | 验收 |
|---|---|---|
| **P13-A** | 阻抗正问题接 live 收尾 `_run_epistemic_impedance` | `p15` 10/10;fe4b:31 谱、被动性全成立 |
| **P13-B** | 证伪市场接 live 收尾 `_run_falsification_market`(真 OpenRouter) | `p13b` 8/8、9 次真 LLM;fe4b:9 次真调 |
| **P13-C** | active_design canary(`_active_design_canary_nudge`,ActionGate + 硬护栏三重) | `p16` 8/8 |
| **P13-D** | 测量提交门控 mode 感知(`_commit_gate_mode`/`_commit_gate_enforces`) | `p17` 9/9;`run_online.py` 去掉假降级 |
| **P13-E** | Rb-ACT R4 预注册契约 + 审计(`rb_act/prereg.py`) | `p18` 12/12 |
| **P13-F** | 计数/文档精度更正(411 pytest collected)+ `test_live_seed_adapter` | `p19` 6/6 |

### 4.5 B 组真机执行 G-2 / G-4 / G-5

| 门 | 状态 | 真机证据 |
|---|---|---|
| **G-2 真机故障注入** | 🟢 | fe4(`run_20260702_093757_f7a893`):`SAMPLE_MISMATCH@13.3°C`+`QA_FAIL@7.3°C` 六用途全 REJECT、`all_caught=true, any_entered_bo=false`、温控/CHI 未受影响;`p20` 10/10 |
| **G-4 enforce/canary 真机长跑** | 🟢 | fe4b(`run_20260702_144507_52a878`,33 点):enforce 拒 6 深冷点出 BO(27/6)、canary 2 次物理执行、bypass=0;`p21` 10/10 |
| **G-5 Rb-ACT R4 多批审计** | 🟡 | fe2+fe3+fe4b 合并 87 真谱/75 配对点,四门全过 `gates_pass=true`;`p18` 12/12;`rb_r4_active=False`(替换未激活) |

### 4.6 真机暴露并修复的两个真 bug(诚实记录)

1. **逐点 agent 默认模型 ID 非法**:`_agent_model` 默认 `"deepseek-v3.1"` 非法 → 每点 LLM 400 静默回落。已改默认 `openai/gpt-5.4`。
2. **numpy 序列化崩溃**:`phase_detect.build_decision_user_message` 遇 `np.bool_`(n_points≥11)`json.dumps` 崩溃 → **fe3 25/35 步、fe4b 23/33 步逐点 LLM 实际回落规则**,`llm_called` 误报 true。已加 `_json_default` + `llm_called` 诚实化,**llmfix run(`run_20260703_193436_ba1b26`)复验:15 次决策 0 序列化失败、n≥11 步 11/11 真 LLM**。逐点 agent 运行时回落 gap 闭合。

---

## 5. 剩余任务（当前计划：还差什么）

### 5.1 B 轨真机硬门(决定 Tier-S 档次,绝不软件伪造)

| ID | 目标 | 前置条件 | 真机执行 | 验收 = 关闭该门 |
|---|---|---|---|---|
| **G-1 新 R/N 前瞻闭环** | 🔴 R=0.15/N=1.03、R=0.12/N=1.00 未合成 | 官方 MOBO+LLM 出配方 → commit+push 盖戳 → 才合成 | 合成 + 全温区 live(带创新) | 新 R/N 的 σ(T)+机制,回答"最优在边缘还是内部";进 history_db |
| **G-3 多批 live 互证** | 🔴 4 次 live run 全同一物理片 | ≥3 独立制备片(同或多 R/N) | 逐片全温区 live(带创新) | 跨 live-run 机制类别 + 相变一致性,证书去 provisional |
| **G-5 R4 生产激活** | 🟡 审计门已过,替换未激活 | 87 真谱/75 配对点已达标 | 人工签核 → `rb_r4_active=true` + 一次替换态真机 run | Rb-ACT 值进 σ/BO 且"BO 不劣化";`legacy_override` 人审解锁 |
| **G-2↳ 仪器见证类故障** | 🔴 提交路径两类已覆盖 | dummy cell/参考电路 + 真仪器 `EvidenceTransaction` 见证路径 | dummy 上注入 ACK 丢失/校准失效等 | `shadow_discrepancy_report` vs 人工 oracle |

### 5.2 A 轨投稿收口(需实验台 + 写作)

- [ ] G-1 续测新 R/N(见上,须前瞻冻结后合成)。
- [ ] 写作:把 M0–M2 v2 结果 + G1 直接地板写进 Methods/Results/SI;G3 措辞统一 replay vs 真实前瞻;G5 图矢量化/SI + bootstrap CI + leave-one-family-out。
- [ ] M4 后续闭环:概率化终止 + 新配方 vs 重复(`U=E[ΔHV]+λI−βC−γR`),延到 ≥3 前瞻轮。

### 5.3 B 轨软件深化(纯代码,不预支档次)

- [ ] 旧工程项(WP5 bootstrap CI/B1·B3 臂、`compiler.py`)价值递减,按需补。

---

## 5.4 H 系列：旧材料代码硬化计划（现在就做，不等新实验）

> **动机**:目前一直用同一片旧材料(R=0.186/N=1.029)的目的,就是把所有**代码/集成层面**的接线在旧材料上做透、验透,**新材料那次才是干净的前瞻实验**——绝不在真实新数据 run 里现改现调(既破坏前瞻冻结纪律,又污染真实数据)。
> 代码级调研(逐文件核对 `hardware_adapter.py` / `scientific_convergence/` / `rb_act/prereg.py` / `measurement_txn.py`)确认:下列项**均非新实验才能解锁**,可现在用旧材料真实实现 + 验证。全程**纯加法 / `*_v2`+delta / legacy 永不覆盖 / opt-in / fail-safe**;改前先 commit+push 盖戳。
> **诚实边界**:每项先做**软件 + 离线/replay 真实数据验证**(不占实验台、零硬件风险),再排**旧材料真机 run**(19℃ 起)做 live 终验;不用软件验证预支"真机已验"。

### 调研得到的真实现状(为什么现在能做)

| 项 | 代码真相(file:line) | 为什么不是"须新实验" |
|---|---|---|
| ④ C³ 消费 | `_finalize_c3`(hardware_adapter:3931)收尾产真证书、写盘、发 `C3_SHADOW_CERTIFICATE`;`_c3_snapshot`(:3498)已注入逐点 LLM prompt;但**收尾证书 recommended_action 无人消费**,Stage1 `termination_evaluator` 不吃 | 纯软件 + 现有 history_db/run replay 即可验 |
| ⑤ 仪器见证 | 在线只走 `submit_measurement_offline`(ReplayInstrument:RAW_FILE+DONE+sample_id);`_maybe_inject_governance_fault`(:3264)只有 SAMPLE_MISMATCH/QA_FAIL;**无真仪器 PhysicalEffect/ACK/校准见证事务** | 协议/见证级故障(ACK/校准/文件)可在驱动边界软件注入,旧材料安全;仅物理破坏性故障须 dummy cell |
| ⑥ canary 多驱动 | `_active_design_canary_nudge`(:3081)只在 ±1 step 邻域 + 要求实质移动 → fe4b 仅成 2 次 | 放宽可执行邻域(仍在安全包络/回温≤15K)即可,旧材料 run 验 |
| ③ Rb-ACT R4 激活 | **激活路径不存在**:`rb_r4_active` 恒 False(prereg.py:186);R3 已把方差喂 `train_Yvar`(`_write_rbact_noise_for_stage1`:2112) | 建激活模式(σ_v2 从 Rb-ACT 后验均值 + delta)+ 人审门,旧材料替换态 run 验"BO 不劣化" |
| 同类:谱级内层选温 | active_design 现用 σ(T) 点;`impedance_models`(谱级)只在收尾 `_run_epistemic_impedance` 跑,不参与逐点选温 | 谱级判别喂 `_epistemic_next_action`,advisory,replay 可验 |

### H 任务卡

| ID | 目标(补哪条 §7 局限) | 落地方案(文件/函数) | 验收(真实数据) | 诚实边界 |
|---|---|---|---|---|
| **H1** | ④ C³ 证书**被消费**(不再只写盘) | Stage1 `termination_evaluator` 增 `c3_advisory`(shadow→advisory,**硬不变量 c3_stop⊆legacy_stop**,只能推迟停、永不更早停)+ 把收尾 C³ recommended_action(REPLICATE/ADD_TEMP/EXTEND_FREQ)写进 run 的 post-processing 摘要 + `next_experiment` 建议 | `pH1_c3_consume_verify.py` 用真实 history_db/既有 run replay:证书被消费、单调不变量守住、advisory 不改 legacy verdict、REPLICATE 建议真出现在摘要 | advisory-only,不夺停机权;canary/enforce 消费留后续 |
| **H2** | ⑤ 在线**仪器见证路径** + 协议级故障注入 | 新增在线 `InstrumentWitness`:把 CHI 成功/ACK、控温到位、文件写盘作为 **PhysicalEffect 见证**过 `EvidenceTransaction`;`inject_fault` 扩展协议级类型 `ACK_LOSS`/`CALIBRATION_EXPIRED`/`FILE_DELAY`(驱动边界软件注入,**绝不碰样品/温控物理安全**) | `pH2_instrument_witness_verify.py` 驱动生产逻辑 + 单测:见证完整→confirmed、注入 ACK/校准/文件缺失→C_P 见证不全→全拒/Quarantine、blind_retry=0、温控解耦 | 物理破坏性故障(短接/开路)仍须 dummy cell(不在旧样品做) |
| **H3** | ⑥ canary 让 active_design **真正多驱动几点** | `_active_design_canary_nudge` 放宽可执行邻域到 ±2 step(仍守阶梯包络 + 回温≤15K + ActionGate)+ active_design 从可行前向候选集提议,使更多步产生实质微调 | `pH3_canary_more_verify.py` 驱动生产方法:更多步 DISPATCHED、越界仍回退、bypass=0、advisory 行为不变 | 仍**不做无人值守 enforce 夺权**;canary 须人看 |
| **H4** | ③ Rb-ACT **R4 激活模式**(人审门) | 新增激活路径:`rb_r4_activate`(start kwargs+控制 API,**默认 False**)+ 契约 `gates_pass` + **人审 token** 三者齐备才把 Rb-ACT 后验均值经 `rbact_noise_bridge` 旁产 **σ_v2 + delta_report**(legacy σ 只读并存),喂 BO;缺任一条件恒回退 legacy | `pH4_rb_r4_activation_verify.py` 用真谱:未签核→恒 legacy;签核后→σ_v2 产出 + delta 逐点、`legacy_overwritten=0`、"BO 不劣化"(HV/最优 trial 不退) | 数值链改动;须 `*_v2`+delta+人审;旧材料替换态 run 终验;跨批仍属 G-5 |
| **H5(选)** | 同类:谱级内层选温 | `_epistemic_next_action` 增谱级 `impedance_models` 判别项(advisory 注入 prompt) | `pH5_*` replay:谱级判别与 σ(T) 层一致/互补 | advisory-only;可延后 |

### H 系列执行顺序与验证策略

1. **H1**(纯软件,零硬件)→ **H2**(软件+单测)→ **H3**(软件+单测)→ **H4**(软件+delta,需你签核)→ H5(选)。每项独立 `pHx_*_verify.py` 真实数据过 + 全量 pytest 无回归。
2. **旧材料真机 run(19℃)**:软件全过后,排**一次旧材料全温区 live**,一次性 live 验 H2(注入 1–2 个协议级故障)+ H3(canary 多驱动)+ H4(R4 激活态,你签核后)。产物只读验收脚本核对,绝不软件伪造。
3. **纪律**:改前 commit+push 盖戳;legacy 零覆盖;H4 未经你签核**恒不激活**。

### H 系列软件实现进度（2026-07-04，真实数据验证）

| ID | 软件状态 | 落地(文件) | 验证证据(真实数据) |
|---|---|---|---|
| **H1** | 🟢 已实现并验 | `termination_evaluator._c3_consume` + `evaluate_termination`(新增 `verdict_effective`/`c3` 块);`hardware_adapter._finalize_c3` 落 `c3_evidence.json` 供 Stage1 聚合自动消费 | `pH1_c3_consume_verify.py` **11/11**:真 attapulgite history_db replay + 受控停机场景;单调不变量 c3_stop⊆legacy_stop 守住;budget 硬停不可推迟;向后兼容。16 项终止/收敛 pytest 无回归 |
| **H2** | 🟢 已实现并验 | 新增 `scientific_harness/instrument_witness.py`(`OnlineInstrumentWitness`+`submit_measurement_online`)+ `witness.py` 增独立 `TEMP_TRACE` 见证;`hardware_adapter._run_instrument_witness`/`_finalize_instrument_witness` 接 live 逐点;协议故障 `_PROTOCOL_FAULTS` | `pH2_instrument_witness_verify.py` **17/17**:真实 EIS .txt 作独立 RAW_FILE 见证;ACK_LOSS→先核对不盲目重试仍 confirmed、INSTRUMENT_STUCK/FILE_MISSING/FILE_DELAY/SAMPLE_SWAP/CALIBRATION_EXPIRED 全不进 BO、blind_retry=0;适配器生产方法 __new__ 干跑通过 |
| **H3** | 🟢 已实现并验 | `hardware_adapter._active_design_canary_nudge` 邻域由 ±1 step 放宽到 ±`canary_max_steps`(默认 2);新增 `canary_max_steps` kwarg(clamp 1–3) | `pH3_canary_more_verify.py` **7/7**:±2 step 建议 DISPATCHED、±3 仍被拒、包络/回温≤15K/advisory 不变、bypass=0;`p16` **8/8** 无回归 |
| **H4** | 🟢 已实现并验(待你签核跑替换态) | 新增 `rb_act/activation.py`(`build_activation`:三条件人审门 + σ_v2 + delta + "BO 不劣化"守卫);`hardware_adapter._finalize_rb_r4_activation` 接 live 收尾;`rb_r4_activate`/`rb_r4_signoff` kwargs | `pH4_rb_r4_activation_verify.py` **6/6**(**87 真谱**):未签核恒 legacy、三条件齐备才产 σ_v2(87 点)、`legacy_overwritten=0`、Spearman=0.995、`bo_not_degraded=True`;`p18` **12/12** 无回归 |
| **H5** | ⚪ 选做,暂缓 | `_epistemic_next_action` 增谱级判别项 | — |

> **仍待真机(19℃ 旧材料一次 live)**:H2 注入 1–2 个协议级故障(如 `ACK_LOSS`/`INSTRUMENT_STUCK`)、H3 `active_design_mode=canary` 多驱动、H4 `rb_r4_activate=True`+你的 `rb_r4_signoff` 跑替换态,收尾产物由 `instrument_witness_summary.json` / `rb_act_r4_activation.json` 只读核对。**软件已全部离线真验,真机只做 live 终验,绝不改代码/伪造。**

---

## 6. `*_v2` + delta 纪律（任何 v2 升级强制遵守）

1. **冻结**:阈值/策略先写进 `configs/*.yaml` 并 commit+push 盖戳,再跑全量。
2. **并行**:v2 产物一律 `*_v2` 命名,**legacy 产物只读、永不覆盖**。
3. **delta**:每次 v2 运行产 `delta_report`(逐条对比 legacy:Rb/σ/断点/最优 trial/收敛判定有无翻转、翻转是否被解释)。
4. **预注册**:任何会改主张的接入(尤其 Rb-ACT ≥R3/R4)前,先在 `prospective_2026H2` 写明允许/禁止声称再开跑。
5. **可回滚**:缺 `objective_definition_id`/版本字段时按 legacy 回填并记 `backfilled=true`。

---

## 7. 风险与回滚

- **过早切 enforce 破坏 G-1**:严格 shadow→canary→enforce;G-1 只旁路记录。
- **样本少致 Skill 统计证书虚假精确**:窄包络 + 置信下界 + 人工审批 + 明确 provisional。
- **C_M/C_E 只是换名包装现有 QC**:按用途/主张建独立验证 + 人工 oracle + 下游影响。
- **改 Stage0 影响历史结论**:M0 强制并行版 + delta_report,legacy 永不覆盖。
- **论文贡献分散**:A/B 双轨;B 轨以"跨层错误链"为主叙事,不平铺四条故事。
- **(教训)文档编码**:`.md` 一律 UTF-8;禁用 PowerShell `Get-Content|Set-Content` 改 CJK 文档(会有损重编码);编辑用专用工具。
- **(教训)真机才暴露的 bug**:单测的 `sys.path`/mock 可能掩盖真实接线/序列化 bug(如 numpy 序列化、导入路径、默认模型 ID);关键路径须真机 live 复验。

---

## 8. CI / 验收矩阵（合并里程碑分支前对应行须全绿）

| 模块 | 验收项 | 现状 |
|---|---|---|
| 语义/审计 | 13/15、目标函数、主张类型唯一;自主代码无未授权驱动调用 | ✅ |
| 事务状态机 | 合法/非法状态转移;ACK 丢失/重复/乱序/部分文件经 reconcile | ✅ |
| 用途准入 | 同一谱对 U1–U6 不同准入;证据不能支持超上限主张 | ✅ |
| 物理见证 | 每事务必需见证完整或显式 Quarantine | ✅ |
| Skill 包络 | 边界/固件/校准/状态越界被拒 | ✅ |
| 失效→BO | 失效后训练视图/最优 trial/终止判定重建;GP 在更小集重训 | ✅ |
| 旁路 | 自主硬件写路径唯一(CI allowlist;`--strict` exit 0) | ✅ `autonomous_bypass=0` |
| 端到端 | 故障→隔离→撤销→BO 重建→下一动作改变 | ✅ |
| 真机故障对照 | 提交路径两类故障真机拦截 | ✅ G-2;🔴 仪器见证类待 dummy cell |
| enforce 真机执法 | 测量提交 + 命令路径真机灰度 | ✅ G-4 |
| 全量测试 | pytest collected | ✅ **411**(408 def test_ + 3 parametrize;232+16+163) |

---

## 9. 一句话结论

> **A 轨**:分析门已清 + G1 主门已过,余写作 + 续测新 R/N → 稳投 Tier B。**B 轨**:软件全体系(WP0–WP5 + ESAS-OS 2.0 四插件 + Epistemic-OS)已落地并在真机 live 回路跑通治理/逐点 LLM/收尾推理/认知证书,411 pytest collected 全覆盖;距 Tier-S 的真机硬门已收 **G-2🟢 + G-4🟢 + G-5🟡**,**剩余 = G-1 新 R/N 合成、G-3 多片 live 互证、G-5 人审激活替换、仪器见证类故障(dummy cell)**——均须物理条件,不用软件预支档次。两轨并行推进、持续深化。
