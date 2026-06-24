# 创新点深挖:Skills / Harness / Memory(6 步法,代码实证)2026-06-22

> 把创新点**固定到三个 agent 工程轴**:`skills`(技能)、`harness engineering`(执行/治理骨架)、`memory`(记忆),
> 按你定义的 6 步法逐步走。**全部以真实 `.py` 代码为依据**(不信总结文档;本轮三路并行核查了
> stage0/stage1/stage3 真实实现),并刻意**避开"材料性能"**——只在数学 / 物理 / 计算机 / 博弈论 /
> 实验设计 / 自驱动的"底层机制"上找增量。
>
> **核心判断(先说结论)**:这三轴不是三个独立方向,而是同一条论文主轴
> ("把'自主发现的可信度'做成可测量、可复算的东西,用复现地板↓ + 可辨识性天花板↑夹出来")
> 的三个落点——
> **Memory = 把两条边界"存下来";Harness = 用两条边界"管住执行";Skills = 用两条边界"给能力定型"。**
> 这正好是"一个内核、三个切面",和你 PPT 第 1 页的三创新点同构。

---

## 第 0 步 · 为什么固定到这三轴(对齐项目灵魂)

| 轴 | 在本项目代码里的真实承载 | 和论文灵魂的接口 |
|---|---|---|
| **Memory** | `campaign_memory/memory_manager.py`(单文件 JSON、每体系隔离、`_find_duplicate_trial`)、`closed_loop/round_logger.py`(SHA256 链)、`anchors.json`/`bind_evidence.py`(证据锚)、`agentic/memory.py::EpisodicMemory`(advisory) | 复现地板 = 记忆"能被测准到什么程度";诚实 null = 记忆点之间"分不分得开" |
| **Harness** | `run_optimization_loop.py::OptimizationOrchestrator`(6 步)、`safety/safety_validator.py`、`closed_loop/termination_evaluator.py`(A/B/C/D)、`s14_claim_auditor.py`(C0–C5 封顶 C4)、`scripts/audit_mainline.py` | 可辨识性天花板 = harness "允许声称到哪";claim 阶梯 = 执行被治理 |
| **Skills** | stage3 `agents/s03…s14`(EXECUTABLE_STEPS)、stage0 `eis_pipeline.py::analyze_eis_point`(6 步)、`scoring/candidate_audit.py`(8 权重)、`config/model_registry.py::STEP_TIER_MAP` | 描述符可辨识 / 机理不可辨识 = 每个 skill "能 license 到哪一层主张" |

> 一句话:别的 SDL 论文把 skills/harness/memory 当**工程**;我们把它们当**认识论**——
> 每一行记忆、每一次执行、每一个技能,都带着"它配得上多强的主张"这个标签。这是真空位。

---

## 第 1 步 · 关键技术 / 思维模型 catalog(结构化压缩,非逐条 1000)

> 诚实说明:逐字列 1000 条无信息量;这里把"黑灯实验室 / 自驱动 / agent"的技术空间压成
> **8 类 × 各 12–20 个真实技术点**(约 130 个),覆盖你要的"科学技术 + 技术点 + 思维模型"。
> 用 ★ 标"和我们三轴强相关、后面会用到"的。

**A. 自驱动实验室闭环(SDL)**:贝叶斯优化★、多目标 BO/ParEGO★、批量 BO(q-EI)、约束 BO★、
安全 BO(SafeOpt)★、成本感知 BO、信息论采集(EIG/BALD)★、Thompson 采样、多保真 BO、
迁移/上下文 BO★、主动学习停准则★、闭环编排(ask-tell)★、虚拟 oracle/replay★、
数字孪生、实验调度、机器人执行、在线再校准★。

**B. agent 架构**:ReAct、Plan-and-Execute★、反思/自我批判(Reflexion)★、produce-critique-revise★、
工具调用(function calling)★、工具/技能注册表★、能力路由(skill routing)★、多智能体辩论、
角色分工(planner/critic/executor)★、黑板架构★、有界递归/预算护栏★、降级/回退策略★、
确定性核 + LLM 边缘的分层★、温度=0 可复现调用★。

**C. 记忆系统**:情节记忆(episodic)★、语义记忆、工作记忆、向量检索(RAG)、
append-only 日志★、内容寻址(content-addressed/哈希)★、单调序号(非墙钟)★、
去重/幂等写★、负样本记忆(failure memory)★、不确定性附注的记忆★、
provenance/数据血缘★、可篡改证据链(tamper-evidence)★、跨战役迁移记忆★、
"待执行但未完成"挂起记忆★、记忆压缩/遗忘。

**D. 不确定性 / 校准**:贝叶斯后验、GP 预测方差★、共形预测(conformal)★、
ECE/Brier/可靠性图★、Murphy 分解(reliability/resolution)★、isotonic/Platt 校准★、
留一/留一数据集协议★、aleatoric vs epistemic 分解★、跨片相关噪声建模★、
重复性方差分解★、复现地板(reproducibility floor)★。

**E. 可辨识性 / 反问题**:结构可辨识性★、Fisher 信息矩阵★、实用可辨识性(profile likelihood)★、
模型竞争(AIC/AICc/BIC)★、模型不可分性 ΔR²★、KK 一致性(因果/线性/稳定)★、
正则化反演(Tikhonov/DRT)★、灵敏度分析、等价类/不可区分流形★。

**F. 形式化 / 类型 / 验证**:类型系统★、effect system(效应类型)★、精化类型(refinement types)★、
契约式设计(pre/post/invariant)★、格/偏序(lattice)★、单调函数/不动点★、
SMT/模型检查、能力安全(capability security)★、信息流类型(声称分级 = 安全等级)★、
证明对象(proof-carrying)★。

**G. 实验设计 / 博弈**:最优实验设计(D/A/E-optimal)★、序贯实验设计★、
EIG/期望信息增益★、停时理论(optimal stopping)★、多臂老虎机/后悔界★、
机制设计/诚实激励(proper scoring rules)★、对抗鲁棒性、最小最大遗憾★、
价值-成本-风险统一效用★。

**H. 科研诚信 / 治理**:预注册★、claim 分级阶梯★、过度声称检测(禁词)★、
前瞻冻结(git 时间戳)★、可复现性(replay≠real)★、审计/路径卫生★、
假支持率(false-support rate)★、盲评/跨模型评审★。

---

## 第 2 步 · 目标 + 条件,以及 catalog 里哪些"用得上"

**目标(三轴各一句)**:
- Memory:让记忆"自带可信度"——存下来的不只是结果,还有"它能被测准到什么程度 / 能撑起什么主张"。
- Harness:让执行被两条边界"管住"——不提不可区分的点、不声称不可辨识的机理、降级要分级。
- Skills:让每个技能"有认识论类型"——声明它能 license 的最高主张层,调度即类型检查。

**真实条件(代码实测,非假设)**:
- 只有 EIS 传输数据;样本少(线 B 10 点、线 A 4 族 13 重复);**不补结构表征**。
- 记忆当前只存 `(R,N)→objectives + combined_score`(`memory_manager.py`),**无地板/无不确定性/无可辨识性元数据**;`EpisodicMemory` 真实但 **advisory、未接主线**;`round_logger` 有 SHA256 链但 **rounds/ 目录尚无已跑文件**;provenance 靠 git SHA 字符串、**非 sha256 append-only**。
- harness:`termination_evaluator` 阈值**手设在 campaign JSON**;LLM 失败是**二元**回退(`decide_with_fallback`,confidence=0.5,单次不重试);**无"已建议未执行"黑名单**(GP 不知道 pending);`safety_validator` 是**规则告警**非风险模型;acquisition **不知道复现地板**。
- skills:**没有显式 skill 注册表/契约**,调度是 `pipeline.py::run_from_seed` 的**硬编码 if/elif**;最接近注册表的是 `STEP_TIER_MAP`(只管模型档位);EIS 封顶 C4 靠**硬编码常量 `_C4_CAP`**,不是类型系统;LLM **不选用哪个 skill**(顺序固定)。

**映射(catalog → 三轴)**:
- Memory ← C(记忆)+ D(不确定性/地板)+ H(provenance/可复现)。
- Harness ← A(约束/安全/信息论采集/停准则)+ G(实验设计/停时/效用)+ B(降级)。
- Skills ← F(类型/effect/格/契约)+ B(技能注册/路由)+ E(可辨识性作前置)。

---

## 第 3 步 · 别人做到哪了,哪里"不够好"(逐轴,代码视角)

> 别人有大量现成件(BoTorch/Ax 的 BO、LangGraph 的 agent harness、向量库 memory、共形预测库……),
> 但**直接拿来用不了**——因为他们解决的是"更快找到更好材料",而我们要解决的是"在测不准 + 不可辨识下
> 如何不骗自己"。逐条说不够在哪:

**Memory 轴 · 现状不够**:
1. 主流 agent memory(向量 RAG / episodic)存的是**文本/embedding**,不存**物理可区分性**;两条只差 0.05 dex(< 地板)的记录被当成两个不同事实——这正是"诚实 null"反例的来源。
2. SDL 的 history 存 `x→y`(我们也是),**不存 y 的复现地板**;于是 acquisition 会去"优化噪声"。
3. 没有**负记忆 / 挂起记忆**:失败原因、已建议未执行的点没有一等公民地位(我们代码确认无 pending blacklist)。
4. provenance 多用时间戳/git(我们也是),**缺写入时的密码学链**(round_logger 有设计但未跑通)。

**Harness 轴 · 现状不够**:
1. BO/MOBO 采集函数(EI/ParEGO)**最大化目标**,不内建"信息增益要 ≥ 不可复现噪声"的约束 → 会推到 R≈0.02 边缘(我们实测纯 BO 漂移)。
2. 终止判据(包括我们)是**手设阈值** + 收敛启发式,不是**停时最优 / 期望剩余信息**;"该不该停"没有信息论根据。
3. 降级是**二元**(LLM↔BO),没有"按可信度分级降级";claim 封顶是**硬编码常量**,不是可证的不变量。
4. 安全多是**规则/边界**(我们 5 条告警),不是把"可合成性 + 复现地板 + 可辨识性"统一进一个**风险-信息效用**。

**Skills 轴 · 现状不够**:
1. 技能调度普遍是**固定流水或 LLM 自由 function-calling**;前者不灵活、后者不可证(LLM 可能调用一个无法支撑下游主张的技能)。我们是前者(硬编码 if/elif)。
2. 技能的输出 schema 有(Pydantic),但**没有"认识论类型"**——没人声明"S06 机理仲裁最高只能 license C4""EIS 技能不能 license 结构主张";现在靠 S14 末端**事后**封顶,不是**类型前置**。
3. 没有**能力求解**:给定想要的主张层级,自动推导"需要哪些技能链 + 哪些证据",并在不可达时给 typed error。

---

## 第 4 步 · 三个足够创新的解决方案(底层:数学/物理/CS/博弈)

> 三个点各扮演一位专家给出,**互相咬合成一个系统**,且**全部不碰材料性能**。

### 创新 A(Memory)——**复现-可辨识双边界记忆**(Boundary-Annotated Episodic Memory, BAEM)
*(专家视角:统计/度量几何 + 数据血缘)*

- **一句话**:记忆的最小单元从 `x→y` 升级为
  `record = (x, y, floor(x,T), 𝓘-state, provenance-hash, status∈{real,replay,pending,failed})`。
- **底层数学**:在目标空间上引入一个由**复现地板**诱导的**等价关系**——
  `a ~ b  ⟺  |y(a) − y(b)| < floor`(在匹配温度上),记忆真正存的是这个**商空间 M/~** 上的等价类,
  而不是裸点。"两个候选是不是同一个发现"成为一个**可判定的几何问题**,而非主观。
- **为什么新**:别人存点,我们存"**点 + 它的不可区分半径**";`combined_score 地板`(§11.3 已实现的传播)
  第一次成为记忆的**一等字段**。负记忆(failed)、挂起记忆(pending,堵住"重复提议未执行点"的洞)
  都进同一结构。provenance 从 git 字符串升级为 `round_logger` 的 **SHA256 链真正跑通**。
- **可证性质**:`dedup-by-floor`(同一等价类只留代表元)、`monotone-provenance`(append-only、seq 单调)、
  `replay-isolation`(status=replay 永不参与 acquisition)——都能写成单元测试断言。

### 创新 B(Harness)——**地板-可辨识双门控的采集与停时**(Floor-&-Identifiability-Gated Acquisition, FIGA)
*(专家视角:信息论 + 最优停时 + 反问题)*

- **一句话**:把采集函数和终止从"最大化目标 / 手设阈值"改成
  **"净信息增益 ≥ 复现地板"** 的门控,并让 claim 升级被**可辨识性谱**硬门控。
- **底层数学**:
  - 重定义采集 `α_net(x) = EIG(x) − λ·floor(x)`(期望信息增益**扣掉不可复现噪声**);
    只有 `α_net(x) > 0` 且"与最近已测点的期望目标差 ≥ 1 个地板宽"的 `x` 才允许进 history
    (这把 §11.3 / E1 的"判距规则"从论文文字**变成 harness 的硬约束**)。
  - 终止用**最优停时**:当"再做一个实验的期望净信息增益 < 其成本/风险"时停——
    替换现在 `termination_evaluator` 的手设 B 类启发式,给"该不该停"一个信息论根据。
  - claim 升级门 = **可辨识性谱可分性**:用模型竞争可分度(ΔAICc / Fisher 信息可分性)
    作为升 C 级的**前置条件**;不可分 → 类型上就拒绝升级(把 `_C4_CAP` 从硬编码常量
    升级成"由可辨识性算出的、随证据变化的天花板")。
- **为什么新**:SDL 的 safe-BO/约束 BO 约束的是**参数可行域**;我们约束的是**认识论可行域**
  (不提不可区分的点、不声称不可辨识的机理)。降级也从二元变**分级**:
  LLM 失败 → 按"可信度预算"回退到"纯 BO 但 claim 自动降一级",而不是简单 confidence=0.5。

### 创新 C(Skills)——**主张类型化的技能契约**(Claim-Typed Skill Contracts, CTSC)
*(专家视角:类型理论 / effect system + 能力安全)*

- **一句话**:给每个 skill(S03–S14、EIS 6 步)一个**认识论类型签名**:
  `skill : Evidence[τ_in] --⟦max_claim=Ck, needs=identifiable(...)⟧--> Evidence[τ_out]`,
  把 claim 阶梯 C0–C5 做成一个**格(lattice)**,skill 是格上的**单调函数**,
  pipeline 合法 ⟺ 想要的下游 claim 类型能被上游技能链**类型推导可达**。
- **底层数学/CS**:
  - claim 等级 `{C0<...<C5}` 是全序格;"证据类型"是 product lattice(传输/结构/因果…);
    skill 的 `max_claim` 是一个**上确界封顶算子**(EIS 技能的封顶算子把任何输入 ∧ C4)。
  - 调度 = **类型检查 + 能力求解**:给定目标 claim,反向求解"需要哪条 skill 链";
    若不可达(例如想要 C5 机理但只有 EIS 技能)→ **编译期 typed error**,而不是末端 S14 事后否决。
  - 这是 **effect system**:claim-level 是"效应",skill 调用会"累积效应",
    `run_from_seed` 的 if/elif 链被一个**带效应检查的调度器**取代(注册表 = `skill → 类型签名` 的 dict)。
- **为什么新**:别人要么固定流水(不可证)、要么 LLM 自由调工具(更不可证)。
  我们让"**能不能声称**"在**调度时**就被类型系统挡住——这是把本项目末端的 S14 治理
  "**左移**"成贯穿全链的类型纪律。这正是论文"可辨识性天花板"的工程化身。

> **三点合一**:BAEM 存边界 → FIGA 用边界管执行 → CTSC 用边界给技能定型。
> 一句话给老师:**"我们不优化材料,我们把'自主科学的可信度'做成了可存(memory)、
> 可执行(harness)、可类型检查(skills)的一等对象。"**

---

## 第 5 步 · 三点的完整功能构建方案(落到真实文件/数据结构/接口)

### A. BAEM(Memory)
- **新模块**:`stage1_optimization/campaign_memory/boundary_memory.py`
  - 数据结构 `BoundaryRecord{x, y, floor_dex, identifiability_tag, provenance_sha, status}`。
  - 扩展 `memory_manager.py`:`add_trial()` 落盘时附 `floor`(调用 `_new_data_analysis/repro_floor` 已有逻辑)、
    `status`;新增 `add_pending(x)` / `resolve_pending()` / `add_failed(x, reason)`。
  - `is_distinguishable(a,b)`:`|Δy| ≥ floor` 才返回 True(商空间判定),供 acquisition 调用。
- **接通**:让 `closed_loop/round_logger.py` 的 SHA256 链真正在每轮写出(补 rounds/ 实跑);
  `EpisodicMemory`(已实现)从 advisory 接进闭环,记录每轮 critic/降级事件。
- **接口**:`get_history()` 返回值新增 `floor`、`status`;`provenance.py` 暴露链头哈希。
- **验收**:三条单测——dedup-by-floor、monotone-seq、replay 永不进训练集。

### B. FIGA(Harness)
- **新模块**:`stage1_optimization/closed_loop/acquisition_gate.py`
  - `net_acquisition(x) = eig(x) − λ·floor(x)`;`gate_propose(x, history)`:不满足"判距 ≥ 1 地板宽"则拒绝并要求重采。
  - 改 `run_optimization_loop.py` Step 4↔5 之间插入 `acquisition_gate`;LLM 降级改为**分级**
    (`decide_with_fallback` 返回的 recipe 带 `claim_demotion=1`)。
- **改 `termination_evaluator.py`**:新增 E 类"信息停时"——`expected_remaining_EIG < cost_risk` 触发;
  保留 A/C/D,把 B 类启发式标注为"被 E 类取代的旧式"。
- **改 `s14_claim_auditor.py`**:`_C4_CAP` 从常量改为 `identifiability_ceiling(evidence)` 的返回值
  (输入是 §可辨识性分析的 ΔR²/AICc 可分度;EIS-only 时仍解析为 C4,但**有依据**)。
- **验收**:重放线 B 10 点,证明 FIGA 会拒绝 R≈0.02 边缘提议(对齐实测"LLM 拉回"结论)。

### C. CTSC(Skills)
- **新模块**:`stage3_mechanism/src/s8_stage3/contracts/skill_types.py`
  - `ClaimLevel` 格 + `SkillSignature{consumes, produces, max_claim, requires_identifiable}`。
  - `SKILL_REGISTRY: dict[str, SkillSignature]`(把现有 S03–S14 + EIS 6 步登记进去;**这就是缺失的显式注册表**)。
  - `typecheck_chain(steps, target_claim)`:在 `pipeline.py::run_from_seed` 入口先跑,不可达即 typed error。
- **改 `orchestrator/pipeline.py`**:if/elif 链外包一层 `dispatch(step, ctx)`,调用前校验 effect(claim 不超 skill 的 `max_claim`)。
- **复用**:`discovery.py` 的 discovery_mode 强度、`claim_guardrails`/`eis_guardrails` 作为类型检查的 runtime 兜底。
- **验收**:构造"想要 C5 机理 + 只挂 EIS 技能"的链 → 必须在调度前抛 typed error(而非跑到 S14 才否决)。

---

## 第 6 步 · 代码实证的 13 小时升级计划(逐文件、可执行、按收益排序)

> 原则:**先做能直接进论文/答辩的最小可证增量**,每块都有"产物 + 验收"。括号为预计工时。

| 时段 | 轴 | 具体改动(真实文件) | 产物 / 验收 |
|---|---|---|---|
| **H1–H3** | Memory | 新建 `boundary_memory.py`;给 `memory_manager.add_trial` 附 `floor`+`status`;补 `add_pending/failed` | 单测:dedup-by-floor / replay 隔离通过;`history` 多出 floor 字段 |
| **H3–H4** | Memory | 让 `round_logger` 在一次 replay 跑中真正写出 `round_001..010_*.json`(补"链跑通") | `closed_loop_rounds/` 出现真实文件 + 链式 hash 自校验脚本通过 |
| **H4–H7** | Harness | 新建 `acquisition_gate.py`(net-EIG − floor + 判距);接进 `run_optimization_loop` Step4.5;降级改分级 | 重放线 B:gate 拒绝 R≈0.02;日志显示 `claim_demotion` |
| **H7–H8** | Harness | `termination_evaluator` 加 E 类"信息停时";`_C4_CAP`→`identifiability_ceiling()` | 终止报告多出 `info_stopping`;天花板有可辨识性依据 |
| **H8–H11** | Skills | 新建 `skill_types.py`(ClaimLevel 格 + `SKILL_REGISTRY` + `typecheck_chain`);登记 S03–S14 + EIS 6 步 | `typecheck_chain` 对"C5+EIS-only"抛 typed error |
| **H11–H12** | Skills | `pipeline.run_from_seed` 入口加 `typecheck_chain` + 每步 `dispatch` effect 校验 | 现有默认链类型检查通过;跑通回归 |
| **H12–H13** | 全 | 写 `INNOVATION_IMPL_NOTES.md` + 3 张机制图(BAEM 商空间 / FIGA 门控 / CTSC 格),并把"双边界贯穿三轴"写进 Discussion 的"未来工作/方法贡献" | 论文多一节"可信度作为一等对象"的方法贡献 + 答辩 backup |

**与发表的衔接(诚实)**:
- 这三点是**方法论增量**,可显著抬高 Originality(当前自评 3.5)和 Importance;**但不改变** G1(凹凸棒土同配方重复)仍是唯一实验硬门槛。
- 即使只落地 **A(BAEM)+ C(CTSC) 的最小版**,也足以把论文从"诚实 null 的现象描述"升级成
  "**把可信边界做成可存、可类型检查的系统**"——这是 Tier B 甚至冲更高的真正抓手,且**全程不碰材料性能**。

---

## 附:三点 vs 现有代码的"够不够"一句话总览

| 创新 | 现有代码最接近的东西 | 差距(为何现成的不够) | 落地文件 |
|---|---|---|---|
| **A BAEM** | `memory_manager.py` + `round_logger`(SHA链)+ `EpisodicMemory`(advisory) | 只存 x→y,无地板/无 pending/无负记忆;链未跑通;episodic 未接主线 | `campaign_memory/boundary_memory.py` |
| **B FIGA** | `optimizers/*` + `termination_evaluator`(A/B/C/D)+ `safety_validator` | 采集不知地板;停时手设;降级二元;封顶硬编码 | `closed_loop/acquisition_gate.py` |
| **C CTSC** | `STEP_TIER_MAP` + Pydantic schema + `s14`(末端封顶) | 无认识论类型;调度硬编码 if/elif;封顶在末端非前置 | `contracts/skill_types.py` |
