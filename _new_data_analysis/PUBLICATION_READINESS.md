# 发表就绪度评估（PUBLICATION READINESS，重写版 2026-06-24）

> 本文件是**当前状态的就绪度判断**(自评,非录用保证)。执行层的任务卡/排期见
> `OPTIMIZATION_EXECUTION_PLAN_20260622.md`;架构与真实 `file::function` 见
> `SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md`;现状家底见 `PROJECT_SITUATION_REPORT_20260622.md`。
> 据 GPT 第三轮评审(`GPT-3.txt`)+《三项创新可执行优化方案 2026-06-23》docx **重写**(非追加),
> 把口径从"软件 Demo 通过 = 已完成贡献"校正为更严的真实成熟度,并明确 **A、B 双轨都必须做、需持续深化**。

---

## 0. 双轨定位（最重要,先读）

本项目是一个 **EIS-only、表征受限条件下的"证据治理型半闭环自主发现"** 项目。它同时承载两条都必须做、互相支撑、不可互相替代的工作:

| 轨 | 论文/贡献定位 | 现状 | 目标刊 | 是否必须做 |
|---|---|---|---|---|
| **A 轨 — 材料/EIS/治理主线** | EIS-only、低数据下自主发现的**复现下界 ≤ 可分辨效应 ≤ 可声称结论强度**案例 | 接近投稿前收口(分析门已清,缺 G1+写作) | **Tier B**(Comm. Chem./Mater./CRPS/npj);DD/MLST 保底 | **必须** |
| **B 轨 — Scientific Agent 方法学** | 可信科学 Agent 运行时:三重提交 Harness(SciTX)/反事实证明携带记忆(E-Mem)/可认证 Skills(PC-Skills) | 软件层 WP0–WP5 已落地;**尚无真机故障对照** | 潜力 **Tier S / 旗舰方法学** | **必须** |

> **铁律(本轮明确)**:A 和 B **不是二选一**,也不是"做完 A 才碰 B"。两轨并行推进、各自持续深化升级——
> A 的瓶颈是实验台时间(G1),B 全是纯代码(不占实验台),天然可并行。最终是否合并成一篇还是拆两篇,
> 是**发表策略问题**(见 §6),不影响"两件工作都要做扎实"这个前提。

---

## 1. 就绪度评分（1–5,5=可投;A/B 分开打）

| 轴 | A 轨 | B 轨 | 依据 |
|---|---|---|---|
| 科学问题定位 | **4.5** | **4** | "复现地板↔可辨识天花板↔主张封顶"是真方法学贡献,不是材料数字 |
| 真实基础 | **3.5** | **2.5** | A:多批真实 EIS,但线 B 无同配方重复;B:410 测试真,但仍是软件层(未经真机故障对照) |
| 技术稳健性 | **4** | **3** | A:M0–M2 分析门已落地;B:跨层失效闭环互联 + 端到端演示,但无真机对照 |
| 原创性 | **3.5** | **4(潜力)** | A:组合视角新;B:三提交/反事实失效/双账户在 EIS 场景有独特价值 |
| 主张诚信 | **4.5** | **4** | C0–C5 封顶 C4、负结果不藏;B 已诚实标"软件层、未经真机" |
| 系统整合度 | — | **3** | B 轨三包已形成"Skill→事务→证据→记忆→BO→GP 重训"互联闭环;余真机 enforce |

> 解读:**A 轨作为"证据治理案例"=中上,接近可投;B 轨作为"Agent 基础研究"=软件层成体系**,
> 距方法学顶刊还差**真机故障证据 + enforce 生产灰度**(见 §4.4)。

---

## 2. 统一脊柱（A、B 共用的论文主线）

\[ \textbf{可信自治上限} = \min(\text{复现能力},\ \text{可辨识能力},\ \text{执行可靠性},\ \text{证据治理能力}) \]

- **复现能力**(M2-1 复现地板)→ "多小的提升不可信";
- **可辨识能力**(M1-7 模型混淆)→ "多强的机制主张不可支持";
- **执行可靠性**(B 轨 SciTX)→ "哪些测量有资格成为证据";
- **证据治理能力**(B 轨 E-Mem/PC-Skills)→ "失效证据是否被传播、主张是否被过度声称"。

A 轨给出前两项(观测与统计边界),B 轨给出后两项(执行与治理边界);两者合起来才构成"受限观测下自主科学能声称什么"的完整答案。**这就是 A、B 必须都做的根本原因——缺任何一项,这条不等式都不闭合。**

---

## 3. A 轨就绪度（Tier B 案例研究）

### 3.1 已落地的分析门（M0–M2,纯代码,真实结果可复算）

| 门 | 内容 | 真实结果 | 状态 |
|---|---|---|---|
| G2 | Rb 方法不变性 + 合成全管线 FPR | 主力 LRS risk=low;6.15_merged FPR=0.06(超假阳性地板),弱数据集 0.14–0.24 诚实标注 | 🟩 代码落地 |
| G7 | 评分口径注册表(训练 vs 审计目标隔离) | `combined_score` 与 `audit_score_v3` 各带冻结 sha256 | 🟩 代码落地 |
| G8 | 复现地板层级方差 + "差<地板"改概率 | between-specimen 0.252 dex;分析不确定度~0.058 ≪ 地板;线 B top-2 P(不可区分)=0.45 | 🟩 代码落地 |
| (可辨识) | 模型混淆矩阵 | 三律正确判别 0.55–0.73 → design-conditional partial non-identifiability,封顶 C4 有据 | 🟩 代码落地 |
| G4 | LLM 安全 vs 5 确定性基线 | **确定性规则可复制 LLM 把 R 拉回观测域的方向 → LLM 安全价值"可替代"** | 🟩 代码落地(诚实下调叙事) |
| G6 | prompt 信封 + 命名降温 | `PromptEnvelope` + `mechanism_consistency` 别名已加 | 🟩 部分(命名仍需全仓迁移) |

### 3.2 投稿前剩余门槛

| 门 | 内容 | 状态 |
|---|---|---|
| **G1** | 线 B 最佳点 R=0.186/N=1.029 **同配方独立重复 ≥3 片**(独立制备/装夹/最好跨日期)+ 续测 R=0.15、R=0.12 | 🔴 **唯一湿实验门(实验台阻塞)** |
| 写作 | 把 M0–M2 的 v2 结果写进 Methods/Results/SI | 🔴 未做 |
| G3 | 闭环对照全程标注 replay vs 真实前瞻 | 🟡 分析已分层,待手稿统一措辞 |
| G5 | 校准 bootstrap CI + leave-one-family-out;图矢量化/SI | 🟡 出版工程 |
| 计数/命名 | 13/15 数据集口径已澄清(见 §7);`phase_transition` 全仓迁移(见 §7) | 🟡 详见 §7 |

> **G1 的诚实边界**:n=3 在正态近似下样本标准差 95% 区间约 0.52s~6.28s——只能给"**direct preliminary reproducibility estimate**",
> 不是稳定的体系复现地板;但足以去掉 Fig 3 的生物聚合物代理 caveat,并把闭环轨迹从 10 点/2 轮延长。

---

## 4. B 轨就绪度（Tier S 方法学）

### 4.1 工程成熟度矩阵（R0–R5,工程成熟度≠论文档次;2026-06-24 WP0–WP5 后）

| 模块 | 当前 | 目标 | 判断 |
|---|---|---|---|
| Stage0–Stage3 科学主线 | **R4** | R4 保持 | 真实运行,human-supervised 半闭环 |
| SciTX(`scientific_harness`) | **R3→R4(命令路径)** | R5 | 命令路径已收口(`ActionGate` 唯一入口,旁路=0,shadow/enforce);C_M(用途)/C_E(主张)/多见证 C_P 已落地;待真机故障对照 + 测量提交路径接入 |
| E-Mem(`scientific_memory`) | **R3→R4(失效→BO 链)** | R4 | 失效→重建→**GP 重训**闭环已闭到底(`history_bridge`+`bo_retrain_bridge`,真实 history_db);余 L0/L3 层 |
| PC-Skills(`scientific_skills`) | **R2→R3** | R4 | 6 真实 Skill + 三层证书(由检查产生,小样本 provisional)+ 漂移/撤销;待真机成功率 + canary 灰度 |
| 三者端到端集成 | **R3** | R4 | 跨层失效闭环互联 + 端到端撤销演示(B0/B2/B4/B5 真实臂);待 enforce 生产启用 |

> **ESAS-OS 2.0(本轮纯代码升级已落地软件 v1,见 `OPTIMIZATION_EXECUTION_PLAN §10`)**:在上表底座上叠三个 **v2 插件**——
> SciTX→**C³-Harness**(`scientific_convergence/`,收敛动作组合)、E-Mem→**R²-Memory**(`scientific_memory/agent_memory/`,角色隔离/可撤销/多轮记忆)、PC-Skills→**Rb-ACT**(`stage0_measurement/rb_act/`,主动/标定/可弃权的 Rb 动态 Skill)+ 闭合测量提交路径(`scientific_harness/measurement_txn.py`)。
> 四者**软件 v1 + 单测均已落地并跑绿**(本轮 +30 测试,合计 410);它们**提升保真度**(C_M 真正消费 EIS 不确定度、记忆多轮多角色化、收敛由信息价值驱动),但**默认 shadow/只记录、legacy 永不覆盖**;**本身不改变档次**——档次仍由真机故障对照决定(§4.4)。Rb-ACT 是唯一会改写数值链者,走五级接入门,本轮仅到 R0(离线 shadow + 合成验证)。

### 4.2 B 轨的核心命题：取得"系统权威性"（命令路径已达成）

GPT 第三轮评审最尖锐的一刀是:**曾有一条绕过治理内核的物理执行路径**
(`/api/agent → hw.enqueue_command`)。**WP4 Cutover 已消除它**:自主命令统一经 `ActionGate`
(默认 shadow=行为不变,enforce 可阻断 allowlist 外),`scripts/audit_hardware_write_paths.py --strict`
实测 `autonomous_bypass=0`。即**命令路径的系统权威性已取得**;剩余是把**测量提交路径**也接入
`EvidenceTransaction`、并在真机上以 enforce/canary 验证。

```
已落地：Agent Proposal → ActionGate(唯一入口) → [enforce 按策略] → 执行
        测量 → 多见证 C_P → C_M(用途) → C_E(主张) → 失效 → 撤销 → BO 视图重建 → GP 重训
待真机：enforce 生产灰度 + G1 故障对照 + 端到端撤销演示在真机重放
```

### 4.3 已完成（软件层,真实可复算,WP0–WP5）

| 创新 | 实现(WP0–WP5) | 关键验收 |
|---|---|---|
| **SciTX Harness** | `scientific_harness/`:多见证 C_P(`witness.py`)+ C_M(用途)/C_E(主张)(`admission.py` U1–U6)+ `EvidenceTransaction` 编排 + **`ActionGate` 旁路清零** | 不变量 blind_retry=0 / ¬C_P⇒全拒 / ¬C_E(BO)⇒不入;audit autonomous_bypass=0 |
| **E-Mem** | `scientific_memory/`:四值超图 + 失效传播 + 快照写门 + 根去重 + **失效→BO 视图重建→GP 重训** + 压缩证书 | 失效→best 变化可查;撤销桥接重建;压缩破坏即拒证 |
| **PC-Skills** | `scientific_skills/`:6 真实 Skill + **三层证书(Wilson 下界,小样本 provisional)** + 漂移/撤销 + 双账户 | 证书由检查产生不可手填;自信≠执行权 |
| **端到端演示** | `scientific_e2e/`:故障→拦截→撤销→BO 重建→下一动作变;B0/B2/B4/B5 真实臂 + 场景族 | governed 严格优于 ungoverned;跨场景不变 |

> **测试**:全量 `tests/+backend_api/tests/+stage3_mechanism/tests/` = **410 passed, 0 failed**(本轮 ESAS-OS 2.0 v2 插件 +30:测量事务化 9 / R²-Memory 11 / C³-Harness 10);botorch 真实后端已激活;跨层闭环(Skill 撤销→E-Mem 失效→BO 重建→**GP 重训**)+ 端到端撤销演示(governed 严格优于 ungoverned)已互联并测试覆盖。

### 4.4 距 Tier S 还差什么（必须做,不能用"软件通过"预支）

软件层的权威语义、跨层失效闭环与端到端演示均已落地(命令旁路清零、C_P 多见证、C_M 用途/C_E 主张分级、三层证书、失效→BO→GP 重训、压缩证书、端到端撤销演示 governed 严格优于 ungoverned)。

**A. 本轮纯代码深化已落地(提升保真度,不预支档次)** — ESAS-OS 2.0 v2 插件(`OPTIMIZATION_EXECUTION_PLAN §10`):
- ✅ 测量提交路径接 `EvidenceTransaction`(`measurement_txn.py` 离线 helper),使测量证据也走多见证→C_P→C_M→C_E;同 bundle 改谱质量 → U1–U6 准入随之变,¬C_P⇒全拒、blind_retry=0;
- ✅ **Rb-ACT**(`rb_act/`)让 C_M 真正消费 Rb 不确定度(方法分歧/谱质量)、能弃权(ABSTAIN)、能主动建议补测;合成谱(阻塞电极/半圆)REPORT 点估 <0.05 dex、非弃权用例 95% 区间覆盖真值;**仅 R0 离线 shadow,legacy `rb_fitting` 逐位未改**;
- ✅ **R²-Memory**(`agent_memory/`)补多轮 RoundState/多角色投影/来源域守卫(S8 作训练标签**拦截率 100%**)+ 写入门(stale 拒)+ 压缩决策保持;**C³-Harness**(`scientific_convergence/`)把收敛升级为信息价值驱动的动作组合,**C³ 停 ⊆ legacy 停**(永不更早停),shadow 比 legacy 更少错误提前停止。
这些**提高系统保真度与可投性**,均默认 shadow / 旁挂、legacy 永不覆盖。

**B. 仍只能靠真机取得(决定档次的硬证据,保留给 G1)**:
1. **真机故障对照(需 G1)**:把软件演示在真机重放——shadow 记录 + 安全故障注入(ACK 丢失/文件延迟/校准失效/样品 ID 错配),报"挡住了哪些错误"。
2. **enforce 生产灰度**:命令路径已可 enforce;测量提交路径在真机 canary→enforce。
3. **统计证书去 provisional**:小样本下证书为窄包络/provisional,需真机成功率累积。
4. **Rb-ACT R1→R4 解锁**:在线双跑→审计接入→噪声接入→正式接入,逐级需真机覆盖率/校准与预注册。

> **结论不变:B 轨距 Tier S 投稿仍差真机证据;v2 插件是纯代码保真度增益,软件 Demo/测试/v2 通过都不预支档次。**

---

## 5. 主张边界（可声称 vs 不可声称,务必写进手稿）

| 可声称 | 不可声称 |
|---|---|
| "实现了三提交证据准入可执行原型,并在真实在线流程完成 shadow 接口" | "已验证真实湿实验的证据事务 Harness" |
| "实现了主张—证据超图与反事实失效传播原型" | "已实现经真机验证的多 Agent 科学记忆" |
| "实现了 Skill 合同/证书/生命周期/双账户治理" | "已实现经真机认证的湿实验 Skills" |
| "human-supervised、evidence-governed 的半闭环系统" | "完全自主的自驱动实验室" |
| 描述性"传导区间转变 / conductivity breakpoint" | "相变 / 证明了某微观传导机制"(EIS-only 封顶 C4) |

---

## 6. 发表策略（合并 vs 拆分）

- **首选拆两篇**(GPT 三轮一致):A 轨(真实实验+复现地板+可辨识上限+治理闭环)先投 Tier B;B 轨(SciTX+E-Mem+PC-Skills,以 A 轨为真实案例)冲 Tier S。
- **合并冲 Tier S 的前提**:§4.4 的真机证据齐备,且"可信自治上限"统一式真把材料案例与 Agent 运行时缝成一条线;否则会被审稿人当"四条故事平铺/拼凑"。
- **无论合并还是拆分,A 和 B 都要做扎实**——这是发表形式的选择,不是"做不做"的选择。

---

## 7. 关键风险与诚实局限 + P0 完成情况

**A 轨**:① 线 B 地板仍是代理(G1 前);② 复现感知是负结果(单曲线 QC 测不准复现);③ 闭环轨迹短(不声称收敛);④ 材料类不新(新意全在转变+治理+边界);⑤ 机理被自身可辨识性封顶 C4。

**B 轨**:① 全程软件层(无真机故障对照);② enforce 非运行默认(shadow 保行为);③ 基线 B0/B5 真实运行、B2/B4 亦真实臂(已去投影);④ 统计证书成功率仍为合成历史(真机前 provisional);⑤ **Rb-ACT 会改写 Rb→σ→断点→BO 数值链**——风险已由 **`*_v2`+delta(legacy 永不覆盖)+ 五级接入门(本轮已落地 R0 离线 shadow + 合成验证,R1–R4 保留给 G1)+ 合成谱覆盖率验证 + 预注册** 控制(见 §10.3/§10.4);C³(`scientific_convergence`)/R²(`agent_memory`)为只读 shadow/旁挂层,对既有数值结论风险低(已单测验证 C³ 停 ⊆ legacy 停、R² 不改 trial DB/σ)。

**P0(WP0,2026-06-23 完成)**:
1. ✅ 13/15 数据集口径已澄清 — `configs/dataset_registry.yaml`(15=13 lineA[7LRS+4starch+2CHITO]+2 lineB;13 出转变、2 CHITO 负类;扣 `build_regularity` 实跑)。
2. ✅ 目标函数收口 — `assert_campaign_matches_role`(G7 漂移守卫)接入主闭环 Step3。
3. ✅ 硬件写路径审计 + 旁路清零 — WP4 后 `routers/agent.py` 自主命令改经 `ActionGate`,`autonomous_bypass=0`、`--strict` exit 0。
4. 🟡 命名降温 — claim 层 `mechanism_consistency` 别名 + `configs/terminology_aliases.yaml`(含**注册表覆盖核验测试**);**全仓 `phase_transition` 200+ 处 blanket 改名故意不做**(破坏前端 WS 通道/测试/冻结字段,低价值 churn)。
5. ✅ `LLMCallBundle` — `agents/prompt_envelope.py`(完整调用包,真实 Fernet 加密/明文标记,公开侧只发 sha256)。

---

## 8. 一句话结论

> **A 轨(证据治理案例)做完 G1 + 写作 + 措辞收口 → 稳投 Tier B;B 轨(Agent 方法学)
> 经 WP0–WP5 已取得"命令路径系统权威性"(自主旁路清零)+ 跨层失效闭环(撤销→失效→BO 重建→GP 重训)+ 端到端撤销演示,
> 并于本轮叠加 ESAS-OS 2.0 三个 v2 插件(测量事务化 / Rb-ACT R0 / R²-Memory / C³-Harness,纯代码软件 v1),
> 410 测试全覆盖;距 Tier S 投稿仍差"真机故障对照(需 G1,软件替代不了)+ enforce 生产灰度 + Rb-ACT R1–R4 解锁",
> 这是必要条件,不能用"软件 Demo/测试通过"预支。两轨都必须做、并行推进、持续深化——
> 缺任何一轨,"受限观测下自主科学能声称什么"这条主线都不完整。**
