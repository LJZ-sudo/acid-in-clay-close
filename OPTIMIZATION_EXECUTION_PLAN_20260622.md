# 优化执行计划（EXECUTION PLAN,重写版 2026-06-24）

> 这是一份**可执行、可勾选、可验收**的执行计划。判档/就绪度见 `_new_data_analysis/PUBLICATION_READINESS.md`;
> 架构与真实 `file::function` 见 `SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md`;现状家底见 `PROJECT_SITUATION_REPORT_20260622.md`。
> 据 GPT 第三轮评审 + 《三项创新可执行优化方案 2026-06-23》docx **重写**(非追加),引入 ESAS-OS 唯一权威链、
> R0–R5 成熟度、WP0–WP5 工作包与 shadow→canary→enforce 切换。

> **双轨铁律(贯穿全程)**:
> ① **A 轨(材料/EIS/治理)与 B 轨(Agent 方法学)都必须做、并行推进、持续深化**——不是二选一,也不是"做完 A 才碰 B"。
> ② 改任何影响主张的参数/阈值前,先 `git commit + push` 盖时间戳(`prospective_2026H2` 纪律)。
> ③ **绝不覆盖已发表/冻结产物**——一律产 `*_v2` 并行版 + `delta_report`;先把阈值/策略写进 `configs/*` 冻结再跑全量。
> ④ 除 **G1 与后续凹凸棒土闭环**外不新增湿实验;故障评测一律用空载/参考电路/dummy/软件注入,**不在 G1 贵重样品上做破坏性注入**。

---

## 1. 现状基线与双轨目标

**现状**:Stage0–3 科学主线真实运行(R4);M0–M2 分析门与 M5 三包(SciTX/E-Mem/PC-Skills)软件实现 + Demo 已完成,并经 WP0–WP5 推进到"跨层失效闭环互联 + 自主命令旁路清零 + 端到端撤销演示"(208 测试全绿,botorch 真实后端已激活)。**最大缺口已从"系统权威性"收敛为"真机故障对照"**。

| 对象 | WP0–WP5 后成熟度 | 目标 | 仍差什么(纯代码/真机) |
|---|---|---|---|
| Stage0–Stage3 科学主线 | **R4** 真实运行 | R4 保持 | — |
| SciTX Harness | **R3→R4(命令路径)** | R5 | 命令路径已收口(旁路=0、shadow/enforce);测量提交路径接 `EvidenceTransaction`;真机故障对照(G1) |
| E-Mem | **R3→R4(失效→BO 链)** | R4 | 失效→BO **已闭到 GP 重训**(`history_bridge`+`bo_retrain_bridge`,真实 history_db);余 L0/L3 层 |
| PC-Skills | **R2→R3** 6 Skill+三层证书+漂移/撤销 | R4 | 统计证书需真机成功率(小样本现为 provisional);canary 真机灰度 |
| 三者集成 | **R3** 跨层失效闭环互联 + **端到端撤销演示通过**(WP5,governed 严格优于 ungoverned) | R4 | enforce 生产启用 + 真机故障对照(G1) |

> R0=概念/文档,R1=Schema+代码,R2=单测/软件 Demo,R3=真实流程 shadow / 跨层闭环,R4=真实流程强制路径,R5=多批真机+故障对照+跨场景。
> 工程成熟度 ≠ 论文档次;主线 R4 仍是 human-supervised 半闭环,非"完全自主"。
> **2026-06-24 进展**:WP0–WP5 已把 SciTX/E-Mem/PC-Skills 从"并列软件包(R1–R2)"推进到"跨层失效闭环互联 + 自主命令旁路清零 + 端到端撤销演示(R3,部分 R4)"。

---

## 2. 已完成（M0–M2 分析门 + M5 软件 Demo,代码实证）

> 以下为已落地、可复算的真实成果(浓缩;逐任务细节见各模块与 `_new_data_analysis/stage0_v2/README.md`)。

| 里程碑 | 状态 | 关键交付与真实结果 |
|---|---|---|
| **M0** 冻结/版本化 | ✅ | `configs/*.yaml`(4 冻结策略)+ `stage0_v2/versions.py`(锚定 40 legacy 产物,delta_report) |
| **M1** 分析稳健性 | ✅ 8/8 | Rb 方法不变性(主力 LRS risk=low)/合成 FPR(6.15_merged=0.06)/不删点稳健 Arrhenius/证据准入(P(无效谱进BO)=0)/断点 CI≈−34~−32℃/评分注册表(G7)/可辨识性 0.55–0.73/后端 stub 做实 |
| **M2** G1 前冻结 | ✅ 5/5 | 复现地板层级方差(between-specimen 0.252 dex,分析不确定度~0.058≪地板)/Stage0 带不确定度/噪声感知 MOBO(`BotorchMOBO`=SingleTaskGP(train_Yvar)+qLogNEHVI 真机实跑)/LLM vs 5 基线(G4:安全价值可替代)/PromptEnvelope+命名别名 |
| **M5** B 轨三包软件 Demo | ✅ 3/3 | SciTX `scientific_harness/`(🅰️Demo A)、E-Mem `scientific_memory/`(🅱️Demo B)、PC-Skills `scientific_skills/`(🅲Demo C)均 acceptance_pass=True |

**测试**:全量 **208 passed, 0 failed**。
**诚实边界**:M5/WP 系列均为**软件层**(故障注入/历史失效夹具/合同认证/模拟器),证明运行时语义可用;**尚未经真机故障对照**——这正是下一阶段(§3 / §9)的主任务。

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
- [ ] **B 轨剩余(纯代码,P2)**:测量提交路径接 `EvidenceTransaction`;WP5 指标 bootstrap CI/B1·B3 中间臂;WP1 补充模块;`compiler.py`;E-Mem L0/L3 层(均见 §9)

**A 轨下一阶段（Tier B 投稿,需实验台）**
- [ ] M3-1 G1 同配方重复 + 续测(唯一湿实验门)
- [ ] G1 当天 shadow 全开 + 自然故障对账
- [ ] 写作:M0–M2 v2 结果写进 Methods/Results/SI + G3 措辞 + G5 出版工程
- [ ] M4 后续闭环:概率化终止 + 新配方vs重复(≥3 前瞻轮)

---

## 9. 遗留项统一排序与处理方案（2026-06-24 统一分析）

> WP0–WP5 核心已落地(**208 测试全绿**)。下表把执行中**有意挂起的遗留项**统一排序。
> 原则不变:G1 是唯一湿实验门(A 轨);B 轨遗留全是纯代码,可与 G1 并行。

| 优先级 | 遗留项 | 归属 | 类型 | 处理方案 |
|---|---|---|---|---|
| **P0** | G1 同配方重复 + 写作 | A 轨 | 湿实验+写作 | A 轨投 Tier B 的硬门;B 轨不阻塞它 |
| ✅ done | 失效→BO 真正闭到 GP 重训 | WP3-e | 纯代码 | `bo_retrain_bridge.rebuild_and_resuggest`(真实 history_db,n_train −1) |
| ✅ done | `history_db` 物化为 `CommittedObservationView` | WP3-e | 纯代码 | `history_bridge.materialize_committed_view`(只读真实 JSON) |
| ✅ done | RO-Crate 复现包 | WP5 | 纯代码 | `scientific_e2e/ro_crate.py` |
| ✅ done | 端到端撤销演示 + 真实基线臂 B0/B2/B4/B5 + 场景族 | WP5/P2-4 | 纯代码 | `demo_end_to_end.py`(governed 严格优于 ungoverned;跨场景不变) |
| ✅ done | 测量 shadow 升级为 WP1 按用途准入(U1–U6 逐点) | P2-2 | 纯代码 | `shadow.py::_per_use_admission`(fail-safe) |
| **P1** | 真机故障对照(把软件演示在真机重放)+ enforce canary 灰度 | WP4/WP5 | **真机** | 需实验台;软件替代不了 |
| **P2** | 测量提交路径接 `EvidenceTransaction`(命令路径已收口;数据路径已由 `history_bridge` enforce) | WP4 剩余 | 纯代码 | `run_online` 测量结果旁路喂事务 |
| 🟡 不做 blanket | 全仓 `phase_transition→transport_regime_change` 术语迁移(200+ 处) | P0-3 专项 | 纯代码 | **故意不做 blanket 改名**(破坏前端 WS 通道/测试/冻结字段,低价值 churn);reviewer 风险已由 claim 层别名 + 手稿措辞 + `terminology_aliases.yaml`(含**注册表覆盖核验测试**)处理 |
| **P2** | WP1 补充模块 `policy/sample_state/instrument_state/compensation` | WP1 剩余 | 纯代码 | 保真度增量;随真机 G1 见证需求逐个补 |
| **P2** | WP5 指标 bootstrap CI + B1/B3 独立基线臂(治理指标确定性,跨场景已验证不变) | WP5 剩余 | 纯代码 | 投稿工程 |
| **P3** | `compiler.py`(函数/SOP→Skill IR 自动编译);E-Mem L0/L3 层 | WP2/WP3 剩余 | 纯代码 | 锦上添花;当前已够支撑闭环 |

**处理顺序建议**:B 轨纯代码高价值项(端到端演示、失效→BO→GP 重训、RO-Crate、数据路径 enforce、按用途 shadow)**均已完成**;剩余 B 轨纯代码为 P2 工程项(测量路径/指标 CI/补充模块),价值递减。**决定性下一步是 P1 真机故障对照(需 G1)**——软件替代不了。G1(A 轨)按实验台排期,B 轨剩余 P2 可并行。

---

> **一句话**:**B 轨纯代码部分 WP0–WP5 已基本做尽——语义审计 / SciTX 2.0(C_M 用途·C_E 主张·多见证 C_P·事务编排)/ PC-Skills(6 Skill·三层证书·漂移撤销·双账户)/ E-Mem(快照·根去重·失效→BO **闭到 GP 重训**·压缩证书)/ Cutover 旁路清零 / 端到端撤销演示(真实 B0/B2/B4/B5 臂)/ RO-Crate;
> **208 测试全覆盖**、自主硬件旁路=0、governed 严格优于 ungoverned。
> 距 Tier S 投稿仅剩 **P1 真机故障对照(需 G1,软件替代不了)+ enforce 生产灰度** 与少量 P2 工程项(软件 Demo 不预支档次)。A 轨 G1/写作并行。两轨持续深化。**
