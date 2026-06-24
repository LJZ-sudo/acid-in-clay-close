# FactoryLab 商业推广视频 · 规划文档（分镜脚本 + 演示前端技术方案）

> 生成日期：2026-06-11
> 定位：面向 **投资人 / FactoryLab 路演**。把 `acid-in-clay-close`（酸-黏土质子导体发现项目）作为 **AIAF OS "数字世界 ↔ 物理世界"科学发现闭环的活体 demo**。
> 数据口径：**真实数据为主，允许画面美化/动画，绝不改数值**。前端为 **脱离真实后端的"演示专用"独立应用**（数据预置 JSON 快照，便于录屏不出错）。
> 本文含：Part 1 视频分镜脚本 + 旁白文案；Part 2 演示前端技术方案；Part 3 真实数据快照清单；Part 4 执行落地记录（已建前端）。

---

## 决策确认（2026-06-11 用户拍板）

1. **受众**：投资人 / FactoryLab 路演。
2. **前端**：独立"演示专用"应用，**全部隔离在 `promo_video/demo_frontend/`，不碰仓库其他目录**；数据预置、便于录屏。已搭建并验证可运行。
3. **数据**：真实数据为主，允许画面美化/动画，**不改数值**。
4. **Agent↔Skill 映射**：在 ACT1 总览中把每个闭环环节对应到 FactoryLab 的 Agent / Skill / MEU（数据见 `aiafLoop.json`）。
5. **demo + 泛化叙事**：明确"本项目只是一个 demo"，并在 ACT6 展示同一套 Skills 可泛化到固态电解质、钙钛矿、催化剂、制药 DoE 等更多工业/科研场景。
6. **新材料页**：展示系统生成的**新材料候选列表**（5 条冻结排名）；机理/数据只展示 **LRS 薄膜 + CHITO**（已剔除弃用的 4.25CS 厚膜）。
7. **ACT3 硬件**：约 **1 分钟**真实录屏，直接嵌入前端（放 `src/assets/hardware_demo.mp4`）。
8. **字幕/配音**：仅中文；**不要 logo / 品牌色**（仅保留轻量文字标识）；**AI 配音**（见下方"配音"小节）。

---

## 修订记录（2026-06-11 第二轮 · 用户反馈后一次性修改）

> 用户反馈核心：① 没体现"这是 demo + 工具通用可泛化到各行业 + Agent/Skills"；② ACT2 不要出现精确时间戳与"AI 独立发现 / 选择重组"否定框；③ "诚实 null"措辞不好；④ 没声音，要加配音。

1. **结构 7 幕 → 8 幕**：在 ACT1 总览后**新增一幕「通用能力层 · Agent + Skills 工程栈」**（`Act2Capability.jsx` + `capabilityStack.json`）。把 FactoryLab "工程壁垒"对应到项目**真实存在的代码模块**，并标注每条"可泛化到 X"：
   - 上下文工程 ← `config/llm_gateway.py`（结构化输出·temperature=0·schema 校验）
   - 任务编排/状态机 ← S03–S14 确定性流水线 + `strategy_planner.py`
   - 技能运行时 ← `schema_validator` + `no_leakage_checker` + 各 step Skill
   - 记忆+心跳 ← `agentic/memory.py`、`heartbeat.py`、`code/agent_ops/*`
   - 自省评审 ← `agentic/critic.py`（产出→自省→修订）
   - 审计+回滚/分级自治 ← execution-engine 硬门禁 + S14 claim 审计
   全片标识打出 **DEMO** 角标 + "工具通用、不绑定 EIS"。
2. **ACT2（新材料）**：**删除**副标题里的精确时间戳 `2026-06-07T11:57:12Z` 与 `term_leakage=0 / llm=live / cache=off` 术语串；**删除**"AI 独立发现了新材料 → AI 选择并重组了已有证据"划线否定框。改为**正向治理条**：`证据可追溯 · 排名可复现 · 全程可审计`（玻璃箱价值，但不带自我否定、也不反向吹"独立发现"）。仅保留"实验前冻结"概念，不报精确时刻。
3. **ACT5（闭环）标题**：`真实 BO+LLM 闭环 · 诚实 null` → **`数字 ⇌ 物理 · 真实闭环执行（全程可审计）`**；improvement=0 仍如实显示，但落点从"失败/null"改为"结果如实回报，才让闭环可信"。
4. **配音（路线 A：烘焙进 app）**：用 **edge-tts**（微软 Edge 中文神经语音 `zh-CN-YunxiNeural`，免费、零 key）按每幕旁白生成 `src/assets/audio/<scene>.mp3`，由 `App.jsx` 在该幕播放时自动播放；无 mp3 时回退浏览器 `speechSynthesis`。录屏时开"系统声音"即带人声。静音切换：界面按钮 / 键盘 `m` / `?mute=1`。
   - 项目 `.env` 内是 **OpenRouter** key（`sk-or-...`，无 TTS 接口），故未用 OpenAI TTS；改用 edge-tts。
   - 重新生成：`python scripts/gen_audio.py --voice zh-CN-YunxiNeural`（旁白文本在脚本 `NARRATION`，须与 `App.jsx` 的 `SCENES[].narration` 一致）。

---

## 修订记录（2026-06-11 第三轮 · 商业演示打磨 + 去技术化）

> 反馈核心：这是**给企业的商业演示模板**——弱化内部问题、去掉所有技术黑话与 Stage 代号、让「新材料 / 新机理 / 数字⇌物理闭环」更醒目；并据三份附件补足内容（原非硬件幕偏短）。

1. **全片去「Stage / Sxx / 内部代号」**：`aiafLoop.json` 的环节描述、`Act1Overview` 副标题/结语、`capabilityStack.json` 的实现项全部改为面向企业的概念化表达（不再出现 Stage0/1/3、S08、OpenAlex、term_leakage、prospective_real、BO、history、.py 文件名等）。
2. **第1幕 Hook**：数字/物理世界换成自绘 **SVG 图标**（AI 芯片 / 实验烧瓶）；删「本 demo 展示我们如何用一个真实的质子导体发现项目把它跨过去」；标题改为更主动的「让 AI 在数字世界里想清楚，再到物理世界里把材料做出来、测出来」。
3. **顶部 brandtag 去「Demo」**：`FactoryLab · AIAF OS · 数字 ↔ 物理 发现闭环`。
4. **第4幕 新材料**：删「（实验前冻结排名）」；新增**发现漏斗**（海量文献/组合 → AI 迁移推理 → 5 个高潜力新材料）让"新材料"成为主角；治理条上移到候选列表正下方（不再贴底）。
5. **第5幕 物理**：删标题「（真实硬件录屏）」与字幕「（真实录屏，非仿真）」；live 角标改「实时测量」。用户自行把 ~9 分钟录屏剪到 2–3 分钟嵌入。
6. **第6幕 新机理（重点重写）**：弃用学术术语「冷却韧性通路连续性描述符」，改大白话「**为什么有的材料，低温下还能导电？**」；删「这是判据，不是单一指标」「同几何、同质控下描述符给出区分力」等费解句；KK 黑话(133→0)从可见层移除；σ(T)/Eₐ 图保留并改平实标注；收尾接**商业价值**（低温/极端环境材料研发）。
7. **第7幕 闭环（正向重写）**：标题改「**数字 ⇌ 物理 · 真实闭环执行（全程可审计）**」；**移除** improvement=0 / 诚实 null / 几何修复 / "未超过初始点" 与 score 轨迹图；改为正向呈现闭环**能力**——真实 6 轮、自动合成测量、4 道安全门禁、全程审计，并用**真实 R/N 参数探索轨迹**图体现「AI 在配方空间自主探索」。措辞「性能可持续优化、可放心交付」。诚信处理：不编造提升曲线，只是不展开单轮 null。
8. **第8幕 收尾（按附件补强）**：标题改「**一次验证，一套能力 —— 同一个 AIAF OS，泛化到整个制造业**」；新增 BP 真实的**泛化层级**（项目→企业→园区→城市/区域→国家行业）+ 种子库 **12 条真实链路**网格（高亮本 demo 所在「材料与电化学研发」）；统计数与 Excel 一致（288/12/156/163/136）。
9. **配音全部重录**：旁白重写（衔接更顺、商业语气、略夸张但不堆术语），`gen_audio.py` 的 `NARRATION` 同步并重生成 8 段 mp3；`gen_audio.py` 增加**逐条重试**（edge-tts 偶发 NoAudioReceived 不再中断全批）。各幕 `dur` 按实测音频长度对齐（hook 20s / overview 27s / capability 26s / material 21s / physical 60s / mechanism 22s / closedloop 23s / outro 25s；非硬件合计 ~2:44）。
10. **附件二次分析（V4.1 / V3.1 / 种子库 V1.1）落点**：泛化叙事用了 BP「能力拆成可组合单元、从项目到企业/园区/城市/国家」「6 大高优先行业」「12 条链路」；新机理接 BP「低温/高湿特种机器人、极端环境材料」；闭环治理对齐「先仿真→授权→执行→审计、分级自治 P0–P4」。

---

## Part 0. 一句话叙事主轴（贯穿全片）

> FactoryLab 的 AIAF OS 愿景里最难、也最值钱的一环，是让 AI 真正在"数字世界"里想清楚，再到"物理世界"里把材料做出来、测出来、并**诚实地知道自己发现了什么**。这件事大多数人停在 PPT 里——**我们用一个真实的质子导体发现项目把它跑通了**。

三个支柱对应视频三个"被看见"的能力：
- **发现新材料** ← 证据约束的迁移智能体（数字世界推理）
- **发现新机理** ← 冷却韧性通路连续性描述符（物理世界测量 + 机理判别）
- **闭环** ← Stage0⇄Stage1 真实 BO+LLM 迭代 + 物理/QC 门禁 + claim 治理

**核心差异化（贵在诚实）**：本片把"可审计、不过度声称、连失败也如实报告"做成**卖点**，而非回避。这与 FactoryLab BP 的「**先卖可验证能力，不卖黑箱自治**」「分级自治 P0–P4 + 全量审计」「玻璃箱而非黑箱」完全同频。

---

## Part 1. 视频分镜脚本 + 旁白文案

整片建议 **3:10–3:30**，模块化分 **8 幕**（ACT0–ACT6，其中 ACT1 后插入"通用能力层"幕）。下方 Part 1 为初版 7 幕脚本，**实际成片以上方"修订记录"为准**（已加通用能力层幕、删时间戳/否定框、改闭环标题、加配音）。
旁白为中文、投资人语气；每幕给出【画面/前端页面】【旁白】【屏幕字幕关键词】【数据来源】【时长】。

### ACT 0 — 冷开场 / 钩子（0:00–0:20）
- **画面**：黑底，左"数字世界"（代码/agent 流），右"物理世界"（EIS 阻抗弧/电化学工作站），中间一道裂缝。裂缝缓慢被一条闭环弧线连上。
- **旁白**：「AI 能不能真的——在数字世界里想清楚一个材料，再到物理世界里把它做出来、测出来，并且**诚实地知道自己到底发现了什么**？这中间，隔着一道大多数人跨不过去的缝。」
- **字幕**：数字世界 ↔ 物理世界 · 这道缝，我们跨过去了
- **数据来源**：纯视觉
- **时长**：20s

### ACT 1 — 定位：这是 AIAF OS 的活体 demo（0:20–0:45）
- **画面**：FactoryLab AIAF OS 标准闭环图「观测 → 理解 → 建模 → 仿真 → 授权 → 执行 → 反馈 → 学习」，逐环点亮；点亮的同时，下方对齐浮现项目 Stage 标签。
- **旁白**：「FactoryLab 的 AIAF OS，把工业发现拆成一个闭环。别人停在示意图，我们把它接到了真实的测量硬件、真实的智能体、和真实的材料上。这是 L02 材料链路上，一个跑通了的科学发现闭环。」
- **字幕**：观测→理解→建模→仿真→授权→执行→反馈→学习 | Stage0 / Stage1 / Stage3
- **数据来源**：AIAF OS 闭环（BP V3.1 §4.1）；Stage 映射见本仓 `THREE_PILLARS_..._20260608.md` A.3
- **时长**：25s
- **映射叠层文案**：观测=Stage0 EIS/QC｜理解·建模=Stage3 证据+文献侦察｜仿真·授权=claim audit + execution-engine 门禁｜执行=真实合成+EIS｜反馈·学习=Stage1 BO 写回 history

### ACT 2 — 数字世界：迁移智能体发现"新材料候选"（0:45–1:25）
- **画面**：演示前端「新材料 / Digital Discovery」页。
  1. 母体系（酸-黏土）+ 广义文献池 → 智能体推理动画；
  2. 产出 **20260607 冻结排名**（卡片/表格逐行落定）；
  3. **决策迹/provenance 链**：文献 → 描述符 → 候选，连线高亮；
  4. **claim audit 镜头**：弹出审计条，把"independently discovered"红色划掉，降级为绿色"selected / recombined"。
- **旁白**：「先看数字世界。一个证据约束的迁移智能体，从酸-黏土母体系出发，在广义生物质与聚合物文献池里，推理出一批生物聚合物–黏土的候选材料，并冻结了一份排名——淀粉/莲藕淀粉第一，壳聚糖第二。注意这一步：当智能体想说'我独立发现了新材料'，系统的确定性审计当场把它拦下来，只允许它说'我选择并重组了已有证据'。**这就是玻璃箱**。」
- **字幕**：冻结排名 2026-06-07 · 无泄漏(term_leakage=0) · claim audit：禁止"独立发现"，只允许"选择/重组"
- **数据来源**：`stage3_mechanism/.../20260607_openrouter_publication_v2/11_candidate_registry/prospective_candidates.json`（rank1 淀粉/PVA/有机改性凹凸棒土/H₃PO₄=0.883；rank2 壳聚糖=0.823；rank3 Halloysite=0.819；preregistered_at=2026-06-07T11:57:12Z；llm_mode=live；cache=False；term_leakage_penalty=0）；S14 claim auditor
- **时长**：40s

### ACT 3 — 物理世界：硬件闭环执行（复用你的录屏）（1:25–2:00）
- **画面**：**嵌入你已录好的硬件测试前端录屏**（宽温 EIS 测量、CHI 工作站、实时 σ(T)/Arrhenius 跳动）。四角加 FactoryLab/AIAF 品牌框 + 字幕条。
- **旁白**：「数字世界选出的候选，进入物理世界。真实的电化学工作站、真实的宽温阻抗谱测量——从室温一路降到极低温。这一段是真实硬件录屏，不是仿真画面。」
- **字幕**：真实硬件 · 宽温 EIS · 实时电导率/Arrhenius
- **数据来源**：你已有的硬件录屏；实时图对应 `frontend/.../live/LiveSigmaT`、`LiveArrhenius`
- **时长**：35s（按录屏可压缩/延长）

### ACT 4 — 发现"新机理"：冷却韧性描述符（2:00–2:35）
- **画面**：演示前端「新机理 / Mechanism」页。
  1. 宽温 σ(T) 双曲线对照：**LRS（韧性，曲线平滑延伸到低温）** vs **CHITO（在约 233K 急剧坍塌）**；
  2. 分段 Arrhenius，标注高温段 Eₐ：LRS 0.037 eV vs 母体系 0.12 eV；
  3. 角标弹出 KK 一致性：220 条谱、KK 警告由 133 → **0**（修正后数据干净）。
- **旁白**：「在物理世界里，我们看到一个新机理：用一个'冷却韧性通路连续性描述符'，能把'低温下还能导'的材料和'低温就崩'的材料**干净地区分开**。莲藕淀粉的势垒只有 0.037 电子伏特，逼近已报道的最低水平；而壳聚糖在零下四十度附近坍塌——同样的几何、同样的质控，描述符给出了区分力。这不是一个指标，是一个能迁移的判据。」
- **字幕**：LRS 韧性 Eₐ≈0.037 eV｜CHITO 低温坍塌（边界验证）｜KK 一致性 133→0
- **数据来源**：`pillar2_descriptor_qc/`（LRS 5.9CS Eₐ=0.037、4.29CS=0.042；CHITO 4.30CS/5.1CS σ(233K)≈4e-5）；对标 POP-2020(0.039)/MFM-300Cr(0.040)/AiCE sepiolite(0.12)；`KK_SIGN_CORRECTION.md`
- **时长**：35s

### ACT 5 — 闭环：数字⇄物理反复迭代 + 诚实 null（2:35–3:00）
- **画面**：演示前端「闭环 / Closed-Loop」页。
  1. Stage1(BO+LLM 建议 R/N) ⇄ Stage0(测 EIS/QC) 来回流动动画，计数 6 轮（05-11→05-17）；
  2. execution-engine 硬门禁：人工批准卡片（hash 绑定）亮"仿真通过→双人审批→放行"；
  3. **诚实条**：improvement = 0、最优仍是 Trial 1、7 次几何修复——全部如实显示。
- **旁白**：「闭环在数字与物理之间真实地来回了六轮。每一步高风险动作都先仿真、再授权、后执行，全程审计。而最关键的一点是：这一轮优化**并没有超过初始点**，我们就如实写'执行成功、但未实现提升'。**在投资人和同行眼里，敢报告失败的系统，才是可信的系统。**」
- **字幕**：真实闭环 6 轮 · prospective_real · improvement=0（诚实 null）· 先仿真→授权→执行→审计
- **数据来源**：`closed_loop_metrics.json`（n_closed_loop_rounds=6；closed_loop_validity=prospective_real；absolute_improvement=0.0；best=Trial1 R=0.186/N=1.029；geometry_repair_count=7；n_llm_adjusted=3）；`bo_v2_locked/execution_engine`
- **时长**：25s

### ACT 6 — 收尾：从一个发现闭环到一个产业基础设施（3:00–3:20）
- **画面**：镜头从单个发现闭环拉远，化为种子库网格（288 场景 / L02 材料链路高亮），再收束到 FactoryLab logo + 一句话定位。
- **旁白**：「一个质子导体的发现闭环，背后是同一套可复用的能力——它可以泛化到材料、电芯、PACK 的整条链路，泛化到种子库里的每一个场景。FactoryLab：让工业发现，从 PPT 里的闭环，变成可验证、可执行、可审计的产业能力。」
- **字幕**：288 场景种子库 · L02 材料与电化学研发 · FactoryLab · AIAF OS
- **数据来源**：种子库 V1.1（288 场景/12 链路/156 Agent/163 Skills/136 MEU）
- **时长**：20s

### 旁白完整连读版（录音用，约 320 字）
> AI 能不能真的——在数字世界里想清楚一个材料，再到物理世界里把它做出来、测出来，并且诚实地知道自己到底发现了什么？这中间，隔着一道大多数人跨不过去的缝。
> FactoryLab 的 AIAF OS 把工业发现拆成一个闭环。别人停在示意图，我们把它接到了真实的硬件、真实的智能体和真实的材料上。
> 先看数字世界：一个证据约束的迁移智能体，从酸-黏土母体系出发，推理出一批生物聚合物–黏土候选，并冻结排名——淀粉第一，壳聚糖第二。当它想说"我独立发现了新材料"，确定性审计当场把它拦下，只允许说"我选择并重组了已有证据"。这就是玻璃箱。
> 候选进入物理世界：真实的宽温阻抗谱测量。我们看到一个新机理——一个冷却韧性描述符，把"低温还能导"和"低温就崩"的材料干净地区分开。
> 闭环在数字与物理之间真实来回了六轮，先仿真、再授权、后执行，全程审计。而这一轮并没有超过初始点，我们就如实报告——敢报告失败的系统，才是可信的系统。
> 一个发现闭环，背后是可泛化到整条材料链路的能力。FactoryLab：让工业发现，变成可验证、可执行、可审计的产业能力。

---

## Part 2. 演示前端技术方案（独立 demo 应用）

### 2.1 总体形态
- **独立 Vite 应用**，目录建议 `promo_video/demo_frontend/`，与主线 `V1.0-qianduan-mainline/frontend` **解耦**：不连后端、不连 socket.io，所有数据来自 `src/data/*.json` 预置快照。
- **技术栈对齐现有**：React + Vite + Ant Design + ECharts（现有驾驶舱用的图表库），降低组件移植成本。
- **品牌层**：顶部 FactoryLab / AIAF OS 主题（深色、科技蓝/青）、logo slot、统一字幕条组件 `<CaptionBar/>`。
- **演示动线模式（关键）**：内置 `?autoplay=1` 自动播放编排器，按 ACT0→6 固定时序切页 + 触发动画 + 顶部进度条，**一次录屏到底不出错**；另保留手动模式供讲解。

### 2.2 页面结构（5 个核心页 + 1 串场总览）
| 路由 | 页面 | 对应视频幕 | 复用现有组件（从主线移植） | 新建/改造 |
|---|---|---|---|---|
| `/overview` | AIAF OS 闭环总览（串场） | ACT1 | `command/DualLoopStatic`、`agentOs/AgentOsTriad` | 闭环图叠加 Stage 标签动画 |
| `/material` | 新材料 · 迁移发现 | ACT2 | `analysis/CandidateSpaceTab`、`campaign/Top3Table`、`campaign/ProvenancePanel`、`agentOs/DecisionTimeline` | provenance 连线动画、claim audit "划线降级"动效 |
| `/physical` | 物理世界 · 硬件执行 | ACT3 | `live/LiveSigmaT`、`live/LiveArrhenius`、`cockpit/MeasurementMetrics` | 主用**录屏嵌入**；此页作备份/补拍 |
| `/mechanism` | 新机理 · 冷却韧性描述符 | ACT4 | `analysis/MechanismTab`、`charts/ConductivityChart`、`charts/TemperatureChart` | LRS vs CHITO 双曲线对照、KK 角标 |
| `/closedloop` | 闭环 · 迭代+门禁+诚实 null | ACT5 | `command/DualLoopStatic`、`campaign/BORecipeCard`、`agentOs/ApprovalQueuePanel`、`campaign/ParetoMini` | 6 轮流动动画、诚实条高亮 |
| `/outro` | 种子库泛化收尾 | ACT6 | — | 种子库网格、L02 高亮、logo |

### 2.3 组件移植原则
- 现有组件多依赖 socket/后端 props → 移植时改为 **接收预置 JSON 的纯展示组件**（去掉数据拉取逻辑，props 注入快照）。
- 保留视觉与图表配置，剥离 `useEffect` 轮询 / WebSocket 订阅。
- 统一加一层 `<DemoStage active step=.../>` 编排容器控制动画时序。

### 2.4 视觉/动效要点（"real_polished"）
- 数值一律来自快照、**只读不改**；美化仅限：配色、入场动画、连线高亮、计数滚动、曲线生长动画。
- claim audit "划线降级" 是全片记忆点，单独做一个醒目动效组件。
- 物理世界一段以录屏为主，前端页仅作补拍/兜底。

---

## Part 3. 真实数据快照清单（需从仓库提取为 demo 预置 JSON）

| 快照文件（建议名） | 源 | 用途/字段 |
|---|---|---|
| `frozen_ranking.json` | `.../20260607_openrouter_publication_v2/11_candidate_registry/prospective_candidates.json` | ACT2 排名 top5、分数、run_id、preregistered_at、registry_hash、term_leakage_penalty、llm_mode/cache |
| `claim_audit.json` | `.../13_claim_audit/claim_audit_report.*` | ACT2 审计结论（llm_transfer_candidate=PASS；禁 independently discovered → selected/recombined） |
| `wide_temperature.json` | `pillar2_descriptor_qc/.../wide_temperature_performance_summary.csv` | ACT4 LRS/CHITO σ(T)、Eₐ（注意 4.25CS 弃用一致性，见写作方案 C.3-2） |
| `ea_benchmark.json` | `manuscript/figures/ea_vs_thickness.csv` + 对标值 | ACT4 Eₐ 对标（POP-2020/MFM-300Cr/AiCE sepiolite） |
| `kk_summary.json` | `KK_SIGN_CORRECTION.md` + `manuscript/figures/kk_*` | ACT4 KK 133→0、μ_median、220 谱 |
| `closed_loop.json` | `stage1.../closed_loop_metrics.json` | ACT5 n_rounds=6、prospective_real、improvement=0、best=Trial1、geometry_repair=7、时间线 05-11→05-17 |
| `seed_library.json` | 种子库 V1.1 统计摘要 | ACT6 288/12/156/163/136；L02 链路高亮 |
| `aiaf_loop.json` | BP V3.1 §4.1 + 三支柱 A.3 | ACT1 闭环环节 ↔ Stage 映射文案 |

### 待办与开放项
- [ ] 确认硬件录屏的实际时长与画面内容，据此定 ACT3 时长与是否需要 `/physical` 补拍页。
- [ ] 确认 4.25CS（厚膜）是否在视频中出现：写作方案已弃用它，ACT4 建议**只展示 LRS 薄膜 + CHITO**，避免厚度混淆与数据不一致。
- [ ] 确认是否需要英文字幕版（投资人若含海外）。
- [ ] 确认 logo / 品牌色 / 配音（真人 or AI 配音）。
- [ ] 提取上述 8 个快照 JSON（Part 3），再开始搭 demo_frontend。

> 诚信红线（与项目灵魂一致，制作时不得违反）：闭环 improvement=0 必须如实呈现；前瞻锚点是"冻结后验证"而非"独立发现"；Eₐ 用"逼近已报道最低/record-level"，**禁用"世界纪录"**；物理世界镜头标注"真实硬件录屏"。

---

## Part 4. 执行落地记录（2026-06-11 已完成）

### 已建：独立演示前端 `promo_video/demo_frontend/`
- 技术栈：Vite + React 18 + ECharts；暗色科技风；16:9 画布自适应；**完全隔离**（独立 `node_modules`，不连后端、不 import 主线代码）。
- 运行：`cd promo_video/demo_frontend && npm install && npm run dev` → `http://127.0.0.1:5273/`；录屏用自动播放：`/?autoplay=1`；单幕深链：`/?scene=N`。
- 操作：空格播放/暂停、←/→切幕、R 重播。
- 7 幕组件：`scenes/Act0Hook…Act6Outro.jsx`；编排器在 `App.jsx`（各幕 dur 驱动自动播放，ACT3 固定 60s 给录屏）。
- 验证：所有模块 Vite 转译无误；Edge 无头截图确认 ACT0/ACT2/ACT4/ACT5 渲染正常、ECharts 出图、真实数据正确。

### 数据快照（真实，已提取到 `demo_frontend/src/data/`）
`frozenRanking.json`（5 条候选冻结排名）·`claimAudit.json`·`wideTemperature.json`（LRS×2 + CHITO×2 的 σ(T)）·`eaBenchmark.json`·`kkSummary.json`（133→0）·`closedLoop.json`（6 轮/improvement=0/几何修复 7）·`seedLibrary.json`·`aiafLoop.json`（闭环↔Stage↔Agent/Skill/MEU 映射 + 泛化领域）。每个文件顶部 `_source` 标注真实来源。

### 第二轮已完成（2026-06-11）
- 结构升级为 **8 幕**：新增 `scenes/Act2Capability.jsx`（通用能力层）+ `data/capabilityStack.json`；`App.jsx` 重排场景、各幕加 `narration`、加配音编排与静音控制；全片打 **DEMO** 角标。
- ACT2 删时间戳/术语串与"独立发现"否定框 → 正向治理条（可追溯/可复现/可审计）。
- ACT5 标题改 `数字 ⇌ 物理 · 真实闭环执行（全程可审计）`；闭环正文措辞正向化（`closedLoop.json` 同步）。
- 配音：`scripts/gen_audio.py` + edge-tts 生成 8 段中文 mp3 到 `src/assets/audio/`（hook 11.8s / overview 12.3s / capability 21.3s / material 20.1s / physical 13.2s / mechanism 13.7s / closedloop 16.5s / outro 16.7s），各幕 `dur` 已留足缓冲。

### 待用户补充
- [ ] 把 1 分钟硬件录屏命名 `hardware_demo.mp4` 放入 `demo_frontend/src/assets/`（ACT3 自动嵌入）。
- [ ] 录屏：浏览器开 `/?autoplay=1`，**录屏软件开"系统声音"**即带配音；想静音录画面用 `/?mute=1`。
- [ ] 微调：各幕时长在 `App.jsx` 的 `SCENES[].dur`；字幕在 `SCENES[].caption`；旁白在 `SCENES[].narration`（改后重跑 `gen_audio.py`）。
- [ ] 换音色/语速：`python scripts/gen_audio.py --voice zh-CN-XiaoxiaoNeural --rate +5%`。
