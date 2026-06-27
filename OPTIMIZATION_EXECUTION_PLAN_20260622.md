# 优化执行计划（EXECUTION PLAN,重写版 2026-06-24）

> 这是一份**可执行、可勾选、可验收**的执行计划。判档/就绪度见 `_new_data_analysis/PUBLICATION_READINESS.md`;
> 架构与真实 `file::function` 见 `SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md`;现状家底见 `PROJECT_SITUATION_REPORT_20260622.md`。
> 据 GPT 第三轮评审 + 《三项创新可执行优化方案 2026-06-23》docx **重写**(非追加),引入 ESAS-OS 唯一权威链、
> R0–R5 成熟度、WP0–WP5 工作包与 shadow→canary→enforce 切换。

> **双轨铁律(贯穿全程)**:
> ① **A 轨(材料/EIS/治理)与 B 轨(Agent 方法学)都必须做、并行推进、持续深化**——不是二选一,也不是"做完 A 才碰 B"。
> ② 改任何影响主张的参数/阈值前,先 `git commit + push` 盖时间戳(`prospective_2026H2` 纪律)。
> ③ **绝不覆盖已发表/冻结产物**——一律产 `*_v2` 并行版 + `delta_report`;先把阈值/策略写进 `configs/*` 冻结再跑全量(见 §10.3)。
> ④ 除 **G1 与后续凹凸棒土闭环**外不新增湿实验;故障评测一律用空载/参考电路/dummy/软件注入,**不在 G1 贵重样品上做破坏性注入**。
> ⑤ **下一阶段主战场 = ESAS-OS 2.0(§10)**:在 SciTX/E-Mem/PC-Skills 底座之上加三个 **v2 插件**(Rb-ACT / R²-Memory / C³-Harness)+ 闭合测量提交路径。**不重命名、不推倒现有三件套**;Rb-ACT 唯一会动数值链,走 §10.4 五级接入门;C³ 因依赖前两者输出,**放最后**(否则退化成人工停止规则)。

---

## 1. 现状基线与双轨目标

**现状**:Stage0–3 科学主线真实运行(R4);M0–M2 分析门与 M5 三包(SciTX/E-Mem/PC-Skills)软件实现 + Demo 已完成,并经 WP0–WP5 推进到"跨层失效闭环互联 + 自主命令旁路清零 + 端到端撤销演示"(botorch 真实后端已激活)。**本轮已叠加 ESAS-OS 2.0 三个 v2 插件软件 v1(§10:测量事务化 / Rb-ACT R0 / R²-Memory / C³-Harness,+30 测试跑绿,legacy 永不覆盖)以提高保真度与可投性。最大缺口仍为"真机故障对照"(保留给 G1)。**

| 对象 | WP0–WP5 后成熟度 | v2 升级(§10) | 目标 | 仍差什么(纯代码/真机) |
|---|---|---|---|---|
| Stage0–Stage3 科学主线 | **R4** 真实运行 | — | R4 保持 | — |
| SciTX Harness → **C³-Harness** | **R3→R4(命令路径)** | ✅ C³ 收敛动作组合 + ✅ 测量路径事务化(本轮软件 v1) | R5 | 命令路径已收口(旁路=0);**测量提交路径离线事务化已落地(§10.1)**;余在线 enforce + 真机故障对照(G1) |
| E-Mem → **R²-Memory** | **R3→R4(失效→BO 链)** | ✅ RoundState/角色视图/使用权限/决策回放(§10.2,本轮软件 v1) | R4 | 失效→BO **已闭到 GP 重训**;L0/L3、多轮/角色记忆 + 跨域守卫**已落地软件 v1**;余真机重放 |
| PC-Skills → **Rb-ACT** | **R2→R3** 6 Skill+三层证书 | ✅ Rb 主动/标定/可弃权动态 Skill R0(本轮软件 v1) | R4 | Rb-ACT **R0 离线 shadow + 合成验证已落地**;统计证书需真机成功率;Rb-ACT R1→R4 走五级门(§10.4) |
| 三者集成 | **R3** 跨层失效闭环互联 + 端到端撤销演示通过 | ✅ C³ 收敛证书统一五类不确定度(含 Rb-ACT 计量) | R4 | enforce 生产启用 + 真机故障对照(G1) |

> R0=概念/文档,R1=Schema+代码,R2=单测/软件 Demo,R3=真实流程 shadow / 跨层闭环,R4=真实流程强制路径,R5=多批真机+故障对照+跨场景。
> 工程成熟度 ≠ 论文档次;主线 R4 仍是 human-supervised 半闭环,非"完全自主"。
> **2026-06-24 进展**:WP0–WP5 已把三件套推进到"跨层失效闭环互联 + 自主命令旁路清零 + 端到端撤销演示(R3,部分 R4)";本轮**已落地** **ESAS-OS 2.0 三个 v2 插件软件 v1(纯代码,§10)**——测量路径离线事务化(`measurement_txn`)、Rb-ACT R0(`rb_act`,离线 shadow + 合成验证)、R²-Memory(`agent_memory`)、C³-Harness(`scientific_convergence`),+30 测试跑绿、legacy 永不覆盖;真机/enforce/Rb-ACT R1–R4 保留给 G1。

---

## 2. 已完成（M0–M2 分析门 + M5 软件 Demo,代码实证）

> 以下为已落地、可复算的真实成果(浓缩;逐任务细节见各模块与 `_new_data_analysis/stage0_v2/README.md`)。

| 里程碑 | 状态 | 关键交付与真实结果 |
|---|---|---|
| **M0** 冻结/版本化 | ✅ | `configs/*.yaml`(4 冻结策略)+ `stage0_v2/versions.py`(锚定 40 legacy 产物,delta_report) |
| **M1** 分析稳健性 | ✅ 8/8 | Rb 方法不变性(主力 LRS risk=low)/合成 FPR(6.15_merged=0.06)/不删点稳健 Arrhenius/证据准入(P(无效谱进BO)=0)/断点 CI≈−34~−32℃/评分注册表(G7)/可辨识性 0.55–0.73/后端 stub 做实 |
| **M2** G1 前冻结 | ✅ 5/5 | 复现地板层级方差(between-specimen 0.252 dex,分析不确定度~0.058≪地板)/Stage0 带不确定度/噪声感知 MOBO(`BotorchMOBO`=SingleTaskGP(train_Yvar)+qLogNEHVI 真机实跑)/LLM vs 5 基线(G4:安全价值可替代)/PromptEnvelope+命名别名 |
| **M5** B 轨三包软件 Demo | ✅ 3/3 | SciTX `scientific_harness/`(🅰️Demo A)、E-Mem `scientific_memory/`(🅱️Demo B)、PC-Skills `scientific_skills/`(🅲Demo C)均 acceptance_pass=True |

**测试**:全量 **410 passed, 0 failed**(含本轮 ESAS-OS 2.0 v2 插件 +30:测量事务化 9 / R²-Memory 11 / C³-Harness 10;Rb-ACT R0 套件已并入)。
**诚实边界**:M5/WP 与 ESAS-OS 2.0 v2 系列均为**软件层**(故障注入/历史失效夹具/合同认证/模拟器/合成谱),证明运行时语义可用;**尚未经真机故障对照**——这正是下一阶段(§3 / §10 P4)的主任务。

---

## 3. 下一阶段执行计划（双轨并行）

> 总目标:**A 轨 → 投出 Tier B;B 轨 → 取得系统权威性,具备冲 Tier S 的真实证据**。
> B 轨按 docx 的 WP0–WP5 推进(已完成,见 §8);A 轨按 G1 + 写作推进。两者并行(A 占实验台,B 纯代码)。

### 3.1 B 轨工作包（WP0–WP5,目标=唯一权威链）

**WP0 · 语义/审计(P0)**:ObjectiveRegistry 收口 / DatasetRegistry / 术语别名 / LLMCallBundle / 硬件写路径审计。
**WP1 · SciTX 2.0**:`EvidenceTransaction` + 三类 ID 分离 + 双状态机 + C_M(用途)/C_E(主张) + 多见证 C_P + `--harness_mode`。
**WP2 · PC-Skills**:6 真实 EIS Skill + 三层证书(形式/统计/计量) + runtime/drift/revocation + 双账户。
**WP3 · E-Mem**:L0–L3 + 版本快照写门 + 根去重 + 失效→BO 重建→GP 重训 + 压缩证书。
**WP4 · Cutover**:`ActionGate` 自主硬件命令唯一入口;shadow→canary→enforce;旁路清零。
**WP5 · 评测/发表**:端到端撤销演示 + 基线 B0–B5 + 故障矩阵 + RO-Crate。

(各 WP 的逐项落地与文件见 §8 主看板。)

### 3.2 A 轨任务（Tier B 投稿,与 B 轨并行）

| 任务 | 类型 | 阻塞 | DoD |
|---|---|---|---|
| **M3-1 G1** R=0.186/N=1.029 同配方 ≥3 独立片 + 续测 R=0.15、R=0.12 | 湿实验 | 实验台 | `LINE_B_LOCAL_DIRECT` 直接地板;去 Fig3 代理 caveat |
| **G1 当天 shadow 全开** + 自然故障 shadow 对账(不破坏性注入) | 湿实验+码 | 实验台 | g1_transaction_manifest + shadow_discrepancy_report |
| 把 M0–M2 v2 结果写进 Methods/Results/SI;G3 措辞;G5 图矢量/SI + bootstrap CI | 写作 | 无 | Tier B 成稿 |
| **M4** 后续闭环:概率化终止 + 新配方vs重复(`U=E[ΔHV]+λI−βC−γR`),延到 ≥3 前瞻轮 | 湿实验+码 | 实验台 | closed-loop 主张达 `s14_claim_auditor` 自身门槛 |

### 3.3 ESAS-OS 2.0（B 轨纯代码主战场,本轮执行,详见 §10）

WP0–WP5 已把"系统是否权威"答完;**剩下的纯代码价值集中在三个 v2 插件 + 测量路径闭合**——它们提升**保真度**(C_M 真正消费 EIS 不确定度,而非换名)、**多轮/多角色记忆真实性**、以及**收敛动作的科学性**(从"几条阈值"升级为"信息价值驱动的动作组合")。执行顺序、五级接入门、`*_v2`+delta 纪律与验收指标在 §10 固化。**真机/enforce/canary 仍保留给 G1**。

---

## 4. 必须写进代码的 12 条系统不变量（B 轨权威性的硬约束）

1. Agent 不得直接访问 `hw.enqueue_command` 或厂商驱动。
2. 人工 override 必与自主路径隔离,并产生 `HumanOverrideEvent`。
3. 每次调用尝试、物理作用和证据记录必须有不同 ID。
4. 未解析物理状态的超时不得重试。
5. Instrument success 不得自动生成 `PhysicalEffect=confirmed`。
6. `PhysicalEffect=confirmed` 不得自动生成 `MetrologicalCommit`。
7. `MetrologicalCommit` 必须绑定 `intended_use`。
8. `EpistemicCommit` 必须绑定 `claim_id` 与允许的最高主张等级。
9. 未 Committed 的观察不得进入 BO、长期记忆或论文事实表。
10. Agent 输出/摘要/重复转述不得形成新的独立证据根。
11. Skill 只能在有效证书和适用包络内执行。
12. 证据/校准/分析版本/Skill 失效时,必须产生下游影响报告并重建可用视图。

---

## 5. 三阶段切换（不得跳过）

| 模式 | 控制权 | 场景 | 升级条件 | 回退条件 |
|---|---|---|---|---|
| **SHADOW** | legacy 控制,SciTX 只记录 | G1 及初始真机对账 | 事件完整;差异均被解释;无性能影响 | 导入失败或记录影响测量 |
| **CANARY** | 少数低风险 Skill 经 SciTX | 参考电路/dummy/低风险 EIS | 设计故障通过;证书有效;人工 oracle 一致 | 任何严重漏检/误执行 |
| **ENFORCE** | 自主模式唯一经 PC-Skills+SciTX | 正式闭环 | 连续批次稳定;应急 override 验证 | 证书失效/状态不确定/严重故障 |

> 上表是**自主硬件命令**的三阶段切换。**Rb-ACT(唯一会改写数值链的 v2)另走更细的五级接入门(§10.4)**:R0 离线 shadow → R1 在线双跑 → R2 审计接入(不进 BO)→ R3 噪声接入(只喂 `train_Yvar`,均值仍 legacy)→ R4 正式接入(预注册后)。本轮只做到 R0(+合成验证),后续逐级解锁。

---

## 6. CI / 验收矩阵（合并里程碑分支前对应行须全绿）

| 模块 | 验收项 | 关联 |
|---|---|---|
| 语义/审计 | 13/15、目标函数、主张类型唯一;自主代码无未授权驱动调用 | WP0 |
| 事务状态机 | 所有合法/非法状态转移;ACK 丢失/重复/乱序/部分文件经 reconcile | WP1 |
| 用途准入 | 同一谱对 U1–U6 不同准入;证据不能支持超上限主张 | WP1 |
| 物理见证 | 每事务必需见证完整或显式 Quarantine | WP1 |
| Skill 包络 | 边界/固件/校准/状态越界被拒;后置不满足下一前置时拒绝组合 | WP2 |
| 失效→BO | 失效后训练视图、最优 trial、终止判定重建;GP 在更小集重训 | WP3 |
| 多 Agent | 旧版本写入被拒;同 DOI/实验只计一根 | WP3 |
| 压缩 | 条件/反证/来源保留且关键决策不翻转 | WP3 |
| 旁路 | 自主硬件写路径唯一(CI allowlist;`--strict` exit 0) | WP4 |
| 端到端 | 故障→隔离→撤销→BO 重建→下一动作改变 | WP5 |
| 分析门(A) | 无转变合成 FPR 已量化;每 BO 观测带方差或 UNKNOWN;每 trial 带目标定义哈希 | M1/M2 |

---

## 7. 风险与回滚

- **过早切 enforce 破坏 G1**:严格 shadow→canary→enforce;G1 只旁路记录。
- **过度工程化**:先 Postgres+Outbox+显式状态机证明语义,**暂缓** Kafka/Neo4j/Temporal;向量库只作 L3 缓存。
- **样本少致 Skill 统计证书虚假精确**:窄包络 + 置信下界 + 人工审批 + 明确 provisional。
- **C_M/C_E 只是换名包装现有 QC**:按用途/主张建独立验证 + 人工 oracle + 下游影响,避免同源自证。
- **改 Stage0 影响历史结论**:M0 强制并行版 + delta_report,legacy 永不覆盖。
- **评分注册表破坏旧 DB**:无 `objective_definition_id` 时按 `combined_score_v1` 回填并记 `backfilled=true`。
- **论文贡献分散**:A/B 双轨;B 轨以"跨层错误链"为主叙事,不平铺四条故事。
- **(本轮教训)文档编码**:`.md` 一律 UTF-8;**禁用 PowerShell `Get-Content|Set-Content` 改 CJK 文档**(会按系统码页有损重编码);编辑用专用工具(UTF-8)。

---

## 8. 主看板（可勾选）

**已完成（M0–M2 + M5 软件 Demo）**
- [x] M0 冻结/版本化;M1 八门;M2 五门(含 botorch 真实后端激活)
- [x] M5-A SciTX / M5-B E-Mem / M5-C PC-Skills 三包 + Demo A/B/C 通过

**B 轨（取得系统权威性,纯代码,与 A 并行)— WP0–WP5 已完成**
- [x] **WP0 语义/审计**:P0-1 ObjectiveRegistry 收口(`assert_campaign_matches_role` G7 漂移守卫)+ P0-2 DatasetRegistry(`dataset_registry.yaml`,**13/15 = 13 lineA[7LRS+4starch+2CHITO]+2 lineB**)+ P0-3 术语别名(`terminology_aliases.yaml`)+ P0-4 LLMCallBundle(真实 Fernet)+ P0-5 硬件写路径审计
- [x] **WP1 SciTX 2.0**:WP1-a C_M(用途 U1–U6)`admission.py` / WP1-b C_E(主张) / WP1-c 三类 ID+多见证 C_P `witness.py` / WP1-d `EvidenceTransaction` 编排(不变量 blind_retry=0、¬C_P⇒全拒、¬C_E(BO)⇒不入) / WP1-e `run_online.py --harness_mode`
- [x] **WP2 PC-Skills**:6 真实 EIS Skill `skills_eis.py` / 三层证书 `certificate_service.py`(Wilson 下界,小样本 provisional,证书由检查产生) / runtime+双账户(忽略自报置信) / drift+revocation
- [x] **WP3 E-Mem**:快照写门 `snapshots.py` / 根去重 `root_dedup.py` / 失效→BO 重建 `bo_rebuilder.py`(`apply_revocation_impact` 桥接 WP2) / 压缩证书 `compression.py` / **WP3-e 失效→GP 重训** `history_bridge.py`+`bo_retrain_bridge.py`(真实 history_db,n_train −1)
- [x] **WP4 Cutover**:`action_gate.py::ActionGate` 唯一入口(shadow 默认=行为不变 / enforce 阻断 allowlist 外)+ `routers/agent.py` fail-closed 收口 → **`autonomous_bypass=0`、`--strict` exit 0**
- [x] **WP5 评测**:端到端撤销演示 `scientific_e2e/demo_end_to_end.py`(best E1→E3,governed 严格优于 ungoverned)+ 真实基线臂 B0/B2/B4/B5 + 场景族 + 故障矩阵 + RO-Crate `ro_crate.py` + 测量/数据路径 enforce(`history_bridge`)
**ESAS-OS 2.0 v2 升级（本轮纯代码主战场,详见 §10）— P0–P3 软件 v1 已落地**
- [x] **P0** 测量提交路径接 `EvidenceTransaction`(`scientific_harness/measurement_txn.py` + `ReplayInstrument`;同 bundle 改谱质量→U1–U6 变、¬C_P⇒全拒、blind_retry=0;9 测试)
- [x] **P1(R0)** Rb-ACT 动态分析 Skill(`stage0_measurement/rb_act/`:特征/后验/弃权/主动建议/合成验证/shadow delta;legacy `rb_fitting` 逐位未改;仅 R0,R1–R4 保留给 G1)
- [x] **P2** R²-Memory(`scientific_memory/agent_memory/`:RoundState/角色投影/使用权限+来源域守卫/L0 写门/决策回放/`ProtonAgentMemoryBench`;forbidden-use 拦截 100%;11 测试)
- [x] **P3** C³-Harness(`scientific_convergence/`:五类不确定度/动作组合/信息价值效用/shadow 收敛证书;**C³ 停 ⊆ legacy 停**、更少错误提前停;10 测试)
- [ ] **P4(保留 G1/真机)** 真机故障对照 + enforce/canary 灰度 + Rb-ACT R1→R4 解锁
- [ ] 旧 P2/P3 工程项(WP5 bootstrap CI/B1·B3 臂、WP1 补充模块、`compiler.py`)价值递减,按需补

**A 轨下一阶段（Tier B 投稿,需实验台）**
- [ ] M3-1 G1 同配方重复 + 续测(唯一湿实验门)
- [ ] G1 当天 shadow 全开 + 自然故障对账
- [ ] 写作:M0–M2 v2 结果写进 Methods/Results/SI + G3 措辞 + G5 出版工程
- [ ] M4 后续闭环:概率化终止 + 新配方vs重复(≥3 前瞻轮)

---

## 9. 已闭项快照（WP0–WP5 + 已完成纯代码,勿重复造轮子）

> 下列均已落地、可复算、被测试覆盖。新工作**只在其上加 v2 插件**,不重做。

- **WP0 语义/审计**:ObjectiveRegistry 收口 / DatasetRegistry(13/15)/ 术语别名(claim 层)/ LLMCallBundle(Fernet)/ 硬件写路径审计。
- **WP1 SciTX**:`EvidenceTransaction` 编排 + C_M(U1–U6)/C_E(主张)/多见证 C_P + `run_online --harness_mode`。
- **WP2 PC-Skills**:6 真实 EIS Skill + 三层证书(Wilson 下界,provisional)+ runtime/drift/revocation + 双账户。
- **WP3 E-Mem**:快照写门 / 根去重 / 失效→BO **闭到 GP 重训**(`history_bridge`+`bo_retrain_bridge`,真实 history_db)/ 压缩证书。
- **WP4 Cutover**:`ActionGate` 唯一入口 → **`autonomous_bypass=0`、`--strict` exit 0**。
- **WP5 评测**:端到端撤销演示(governed 严格优于 ungoverned)+ 真实基线臂 B0/B2/B4/B5 + 场景族 + 故障矩阵 + RO-Crate。
- **🟡 故意不做**:全仓 `phase_transition→transport_regime_change` blanket 改名(破坏前端 WS/测试/冻结字段,低价值 churn;reviewer 风险已由 claim 层别名 + `terminology_aliases.yaml` 覆盖)。

---

## 10. ESAS-OS 2.0 升级方案（本轮纯代码主战场:排序 · 五级门 · v2+delta · 验收）

> 据 GPT 第四轮(`GPT-4.txt` 后半)把三大创新细化为 **C³-Harness / R²-Memory / Rb-ACT** 三个 **v2 能力插件**(不是新架构、不是改名),叠加在现有 SciTX/E-Mem/PC-Skills 底座上;再闭合**测量提交路径**。
> **代码核查**:`scientific_convergence/`、`stage0_measurement/rb_act/` 此前不存在(全新);`EvidenceTransaction` 仅在测试/e2e demo 用,**尚未接入 `run_online`/`canonical_input` 主测量路径**——这正是 §10.1 的 P0。

### 10.0 执行排序（先做能解锁后者者;C³ 必须放最后）

| 优先级 | 项 | 类型 | 状态 | DoD(本轮目标) → 实测 |
|---|---|---|---|---|
| **P0** | 测量提交路径接 `EvidenceTransaction`(离线可测 helper)| 纯代码 | ✅ 落地 | `measurement_txn` 从 Stage0 bundle 构事务,U1–U6 准入随谱质量变化;`ReplayInstrument` 文件/状态见证可跑;¬C_P⇒全拒、blind_retry=0;`run_online` enforce 保留给 G1 ✓9 测试 |
| **P1** | **Rb-ACT** 动态分析 Skill(离线 shadow + 合成验证)| 纯代码 | ✅ R0 落地 | `rb_act` 在合成谱上输出后验+弃权(ABSTAIN)+主动建议;REPORT 点估 <0.05 dex、非弃权 95% 区间覆盖真值;`shadow_run` delta vs legacy;`rb_fitting` legacy 逐位未改 ✓ |
| **P2** | **R²-Memory**(RoundState/角色视图/使用权限/写门/决策回放/benchmark)| 纯代码 | ✅ 落地 | `agent_memory` 角色读写隔离、forbidden-use(S8 作训练标签)拦截=100%、stale 写拒绝、压缩前后 top-1 动作+主张等级不变;`ProtonAgentMemoryBench` 全过 ✓11 测试 |
| **P3** | **C³-Harness**(收敛状态/动作组合/信息价值/shadow 策略/收敛证书)| 纯代码 | ✅ 落地 | `scientific_convergence` 在 `evaluate_termination` 之上 **shadow** 给出动作组合 + 收敛证书;**C³ 停 ⊆ legacy 停**(永不更早停)、比 legacy 更少错误提前停;只记录不夺权 ✓10 测试 |
| **P4(保留)** | 真机故障对照 + enforce/canary 灰度 + Rb-ACT R1→R4 解锁 | **真机** | 🔴 保留 G1 | —(本轮不做) |

> A 轨 **G1 同配方重复 + 写作**是独立硬门(P0 级,占实验台),与上面 B 轨纯代码 P0–P3 **并行**,互不阻塞。

### 10.1 方向一 · 测量保真度:Rb-ACT + 测量路径事务化

**Rb-ACT**(`stage0_measurement/rb_act/`,新建,**不改 `rb_fitting.py`**):在既有 `fit_all_rb_methods()`(并行四法 + 可信集 + 集成 + 与 legacy 对照)之上加**决策层**——
(a) 谱质量特征 → 适用性门;(b) 对数域贝叶斯模型平均得 Rb 后验(点估 + 95% 区间 + 方法分歧/谱质量两类不确定度分解);(c) **弃权(ABSTAIN)**:不确定度过大或方法严重分歧时拒绝给值并附原因码;(d) **主动测量建议**:输出"扩频/加测温点/换夹具"等下一步动作;(e) `shadow` 双跑 legacy↔Rb-ACT 产 `delta_report`。
其不确定度天然喂给 `admission.assess_use` 的 `rb_method_spread_dex / rb_method_success / ecm_fallback`,使 **C_M 真正消费 EIS 证据质量,而非换名**。

**测量路径事务化**(`scientific_harness/measurement_txn.py`,新建):把 Stage0 结果 bundle 物化为 `measurement_signals` + `ReplayInstrument`(文件/历史见证),驱动既有 `EvidenceTransaction.process()`,使**测量证据**也走"多见证→C_P→C_M(用途)→C_E(主张)→是否进 BO"。本轮提供**离线可测 helper**;`run_online` 在线 enforce 接入保留给 G1(避免在无真机时伪造在线见证)。

### 10.2 方向二 · R²-Memory（角色隔离 / 可撤销 / 多轮记忆）

`scientific_memory/agent_memory/`(新建,**与 SQLite 证据图/`history_bridge` 互补,不替换**):
- `RoundState`:单 Agent 多轮的结构化交接(目标/已知/未决/下一步),取代裸文本上下文;
- 角色视图:不同角色(测量/分析/优化/审稿)读到**经治理的不同投影**,写入受限;
- `UsagePolicy` + **来源域守卫**:记忆项带 `allowed_uses/forbidden_uses`(如 acid-in-clay 的 S8 标 `transfer_reference`,**禁止**直接作 biopolymer–clay 的训练标签),防跨域误用;
- 写入门:`PROPOSED → 校验(快照/根去重/使用权限) → ACTIVE/CONTESTED/REJECTED`,旧版本写入被拒;
- **决策回放**:全量记忆 vs 压缩记忆下,top-1 动作 + 主张等级是否一致(决策保持性验证,接 `compression.py`);
- 小型 `ProtonAgentMemoryBench`:覆盖"失效传播 / 跨域守卫 / 多轮一致 / 压缩保持"的可复算任务。

### 10.3 `*_v2` + delta 纪律（任何 v2 升级强制遵守）

1. **冻结**:阈值/策略先写进 `configs/*.yaml` 并 `git commit+push` 盖时间戳,再跑全量;
2. **并行**:v2 产物一律 `*_v2` 命名,**legacy 产物只读、永不覆盖**;
3. **delta**:每次 v2 运行产 `delta_report`(逐条对比 legacy:Rb/σ/断点/最优 trial/收敛判定有没有翻转、翻转是否被解释);
4. **预注册**:任何会改主张的接入(尤其 Rb-ACT ≥R3)前,先在 `prospective_2026H2` 写明允许/禁止声称再开跑;
5. **可回滚**:缺 `objective_definition_id`/版本字段时按 legacy 回填并记 `backfilled=true`。

### 10.4 Rb-ACT 五级接入门（唯一会改写数值链的 v2,逐级解锁）

| 级 | 接入方式 | 对结论的作用 | 解锁条件 | 本轮 |
|---|---|---|---|---|
| **R0** | 离线 shadow:只在历史/合成谱上跑,产 delta,不影响任何产物 | 0(纯观察) | — | ✅ 本轮 |
| **R1** | 在线双跑:G1 当天与 legacy 并行记录,仍用 legacy 值 | 0(留痕) | R0 delta 可解释 | 🔴 G1 |
| **R2** | 审计接入:Rb-ACT 弃权/分歧进 C_M 审计,**不进 BO** | 仅收紧准入,不改数值 | 合成验证 + 人工 oracle 一致 | 🔴 后续 |
| **R3** | 噪声接入:把 Rb-ACT 方差喂 `train_Yvar`,**均值仍 legacy** | 改 BO 权重,不改历史 σ | 预注册 + 多批稳定 | 🔴 后续 |
| **R4** | 正式接入:Rb-ACT 后验均值作主值(产 `*_v2` + delta) | 改数值链 | 真机覆盖率/校准达标 + 预注册 | 🔴 后续 |

### 10.5 方向三 · C³-Harness（收敛动作组合,放最后)

`scientific_convergence/`(新建,**shadow 于 `termination_evaluator.evaluate_termination` 之上,不改写它**):把"收敛=几条阈值触发"升级为**收敛状态 + 动作组合**——
- `ConvergenceState`:统一五类不确定度(性能差距 / BO 后验 std / **计量不确定度(来自 Rb-ACT)** / 复现地板 / 主张稳定度);
- `ActionPortfolio`:候选动作不止"新配方",含 `REPLICATE/REMEASURE/EXTEND_FREQ/ADD_TEMP/DIAGNOSE/STOP`;
- 信息价值效用 `U(a)=E[ΔHV]+λ·VoI−β·cost−γ·risk`(第一版确定性候选 + 概率效用,不必上完整 POMDP);
- `policy`:**shadow** 给出推荐动作组合 + 与 legacy verdict 的 `delta`,**只记录不夺权**;
- `ConvergenceCertificate`:声明"在何种不确定度下、依据哪些证据、建议何动作",可审计。

### 10.6 验收指标（逐模块固化,合并前对应项须全绿)

> 状态图例:✅=本轮软件已验证(单测跑绿);🔴=保留 G1/真机。

| 模块 | 验收项(可量化) | 本轮 |
|---|---|---|
| 测量事务化(§10.1)| 同一 bundle 改变谱质量 → U1–U6 准入随之变化;¬C_P ⇒ 全 REJECT;blind_retry=0;离线 helper 单测通过 | ✅(`test_measurement_txn` 9) |
| **Rb-ACT**(§10.1)| 合成谱(已知 Rb,阻塞电极/半圆模型):REPORT 用例点估误差 <0.05 dex、非弃权用例 **95% 区间必覆盖真值**(校准诚实)、覆盖率 **≥0.9(保守:过覆盖可接受)**;高噪/无高频锚点/方法分歧(Rb vs Rb+Rct)**ABSTAIN 命中** + 主动建议(扩频/换夹具/重测)命中;弃权值不外报 → 不引入 legacy 没有的 false breakpoint;`rb_fitting` legacy 不被改写(对照值逐位一致) | ✅ 软件/合成(`test_rb_act`);真实 LRS 谱 delta 无未解释翻转 🔴 G1 |
| **R²-Memory**(§10.2)| forbidden-use(S8 作训练标签)**拦截率=100%**;反证/条件压缩后保留;stale(旧快照)写入被拒;**压缩前后 top-1 动作 + 主张等级一致**;benchmark 全过 | ✅(`test_r2_memory` 11) |
| **C³-Harness**(§10.5)| 动作组合可复算;注入"已收敛但仍探索/未收敛却想停"场景 → C³ shadow 比 legacy **更少错误提前停止**;收敛证书字段完整、与 `evaluate_termination` 不矛盾 | ✅(`test_c3_harness` 10) |

### 10.7 对现有结论的影响矩阵 + 回滚

| v2 | 触碰范围 | 对已发表/冻结结论风险 | 升级门 | 回滚 |
|---|---|---|---|---|
| C³-Harness | 只读 termination + 加 shadow 层 | **低**(不改数值、不夺权)| 默认 shadow | 关 shadow 即恢复 legacy |
| R²-Memory | 新增记忆层,旁挂 | **很低**(不改 trial DB/σ)| 写门 + 角色隔离 | 停用 agent_memory |
| **Rb-ACT** | **会改 Rb→σ→断点→BO 数值链** | **中–高** | **§10.4 五级门**(本轮仅 R0) | legacy 永不覆盖;任何级别都可退回 legacy 值 |

---

> **一句话**:**WP0–WP5 已把"系统是否权威"答完(旁路=0、失效闭到 GP 重训、端到端撤销、RO-Crate);本轮 B 轨纯代码主战场已落地 ESAS-OS 2.0 三个 v2 插件软件 v1**——**测量路径事务化(P0,✅)→ Rb-ACT 提升计量保真度(P1,✅ 五级门只到 R0)→ R²-Memory 补多轮/多角色记忆(P2,✅)→ C³-Harness 升级收敛动作组合(P3,✅ shadow 放最后)**,+30 测试跑绿、全程 `*_v2`+delta、legacy 永不覆盖、收敛/记忆默认只记录不夺权。**真机故障对照 / enforce 灰度 / Rb-ACT R1–R4 保留给 G1(软件替代不了,不预支档次)。A 轨 G1+写作并行。两轨持续深化。**
