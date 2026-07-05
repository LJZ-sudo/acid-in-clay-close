# 项目真实情况报告（现状快照：2026-07-05）

> **真实性声明**:本报告所有论断均由三类证据支撑——(a) 逐文件读取真实源码、(b) 对真实 stage0/stage1/live-run 产物 JSON 重算、(c) 真实 LLM/盲评消融。凡冻结/存根/只读/代理/缺口处均显式标注,不取自总结文档的自述,不美化、不藏负结果。
> 配套文档:`SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md`(代码级执行追踪 + `file::function`)、`OPTIMIZATION_EXECUTION_PLAN_20260622.md`(可勾选执行计划)、`experiments/docs/PUBLICATION_READINESS.md`(发表就绪度)。
> 本版为**重写版**:合并了此前所有分日期的进展层,只保留截至 2026-07-05 的真实结论。历史 run 用 run-id 作标识(非文档版本日期)。

---

## 1. 这是什么项目

一个 **物理/QC/claim-governed 的 agentic 材料发现项目**:在质子导体(酸-黏土 / 生物聚合物-黏土)上做 **EIS-only、表征受限条件下的"可信自主发现"**。核心不是材料数字,而是**"只有传输数据时,自主 agent 能可信地声称什么"**,并给出两条可测量边界:**复现地板(下界)**与**可辨识性天花板(上界)**。

- **A 轨(材料/EIS/治理主线)**:线 A 迁移推理(酸-黏土→生物聚合物-黏土,发现亚零度传输转变)+ 线 B 凹凸棒土上真实 MOBO+LLM 闭环。目标 **Tier B**。
- **B 轨(Scientific Agent 方法学)**:可信科学 Agent 运行时——三重提交 Harness、证明携带记忆、可认证 Skills,叠加 ESAS-OS 2.0 四插件 + Epistemic-OS 认知层。目标 **Tier S**。
- **一治理核**:可校准主张阶梯 C0–C5 + 防过度声称护栏(EIS-only 硬封顶 C4)。

A、B 双轨都必须做、并行推进:A 的瓶颈是实验台时间,B 主要是代码,天然可并行。

---

## 2. 真实数据家底（测了什么 / 没测什么）

| 体系 | 真实独立重复(已 stage0 处理) | 关键事实 |
|---|---|---|
| **LRS 藕粉** | **7 次**:0429CS, 0509CS, 6.12, 6.15_merged, 0615_s2, 0616_s3, 0617_s3b | 每片有制备文件记录;4 月薄片 0.02cm、6 月标准化 ~0.07cm |
| **starch 淀粉** | **4 次**:0427CS, 0428CS, 6.11, 6.13 | — |
| **CHITO 壳聚糖** | **2 次**:0430CS, 0501CS | 边界反例(低温段仅 2 点,无干净转变) |
| **凹凸棒土(线 B)** | **10 个 trial**(`history_db_attapulgite.json`,各不同 R/N) | 最优 trial1 R=0.186/N=1.029 cs=−1.941 |
| **凹凸棒土全温区 live run** | **4 次真机 run,均为同一物理片 R=0.186/N=1.029** | 详见 §5;**同片重复,非多批多片** |
| S8 海泡石(母体系) | 20-trial 历史 | 仅作先验/迁移参考,**不混入凹凸棒土 BO 训练库** |

**没有的(有意不补)**:任何结构表征(XRD/SEM/DSC/NMR)、新材料体系、新仪器。**DRT 实测不可行**(本数据全 59 点 R²<0,不作证据)。

---

## 3. 系统怎么跑（确定性 vs LLM 的真实分布）

详见架构文档。**真实 LLM 调用**在:① Stage1 Step5 策略规划(`openai/gpt-5.4`,temp=0,只存 prompt SHA256);② Stage0 逐点相变/步长决策 agent(`openai/gpt-5.4`,live 回路,见 §5);③ Stage3 上游 S04–S08(假设/机制/描述符/文献)+ 收尾机制推理链;④ Epistemic 证伪市场(多角色 LLM)。**默认确定性(无 LLM)**:Stage0 全分析管线、Stage1 优化器/记忆/终止/安全、Stage3 的 S09 候选生成(硬编码冻结)+ S10 排序 + S14 阶梯、治理旁路、v2 守卫。

> **诚实关键**:发表那次 S09/S10 是**有意冻结的确定性**(锁时间戳 + 可复现)。项目主张温和:"LLM 从广义文献池选择并重组 + 实验前冻结 + 事后 EIS 验证"(强度 B+),**从不声称"LLM 独立发现 LRS"/收敛/事后改分**。

---

## 4. 三创新点真实进展（A 轨科学结论）

| 创新点 | 完成度 | 真实支撑 | 未闭合 gap |
|---|---|---|---|
| **亚零度传输转变 + 可调** | 高 | 13/15 集有转变,T_break **−22~−39°C**;LRS 低温 Ea **0.69±0.07 eV**(7 重复);陡峭度 LRS≈19×→starch≈2.4×;CHITO 边界反例 | 单体系配方梯度(需新 R/N,G-1) |
| **复现地板 + 可校准治理** | 中高 | 线 B 直接地板 `LINE_B_LOCAL_DIRECT`(3 片同配方):WARM median 0.106/p90 0.146 dex(<代理 0.262)、COLD median 0.158/**p90 0.356 dex(>代理,冷段更松,诚实限制)**;校准 ECE **0.78→0.13** | 三批为回溯离线数据;冷段复现更差 |
| **真实 MOBO+LLM 闭环 + 治理** | 中 | 闭环代码真、recipe SHA256 留痕、前瞻冻结;BO 比 random 快(4.1 vs 5.5);LLM=安全(raw R0.02→LLM R0.28);m6–m8 消融 governed 0% vs popularity 100% | 轨迹短(10 点/2 前瞻轮),不声称收敛 |
| **可辨识性天花板** | 中 | 三机理律 Arrhenius/Mott/VTF 低温支 ΔR²=0.006(不可辨识);AICc 3 段=1.0 → 主张封顶 C4 | 形式化理论完整度 |

---

## 5. B 轨 + 创新点：真机 live 实证现状（本项目最新主战场）

四次凹凸棒土全温区 live run(**同一物理片 R=0.186/N=1.029**,经前端/后端控制回路 `/api/control/start`):

| run-id | 点数 | 用途 | 关键真实结果 |
|---|---|---|---|
| `run_20260629_112156_9db536`(fe2) | 19 | baseline(无 agent 决策) | σ 0.0142→2.29e−6 S/cm;治理三事件逐点齐出、0 翻转、0 盲重试 |
| `run_20260630_135646_f33d5e`(fe3) | 35 | 创新点首次全开 | σ 1.42e−2→2.5e−7(跌 5 数量级、完整穿相变);收尾 stage3 4 次真 gpt-5.4;**收尾未跑证伪市场/阻抗**(那两项 07-01 才接 live) |
| `run_20260702_093757_f7a893`(fe4) | 6 | **G-2 真机故障注入** | 注入 2 类故障全被治理拦截(§6) |
| `run_20260702_144507_52a878`(fe4b) | 33 | **G-4 enforce+canary + 收尾全创新** | enforce 真拒 6 深冷点出 BO;canary 2 次物理执行;收尾 stage3/证书/阻抗/证伪市场齐全(§6) |
| `run_20260703_193436_ba1b26`(llmfix) | 23 | 逐点 LLM 修复复验(19→−20°C) | 0 序列化失败、n≥11 步 11/11 真 LLM(§6) |

**逐点 LLM agent 的真实忠实度(重要诚实更正)**:fe3/fe4b 期间曾有 numpy 序列化 bug,导致 n_points≥11 的步 `json.dumps` 崩溃、静默回落规则决策,而 `llm_called` 字段误报 true——**fe3 实际 35 步中 25 步回落、fe4b 33 步中 23 步回落**。该 bug 已修(`phase_detect._json_default` + `llm_called` 诚实化),并在 llmfix run 上复验通过:**15 次决策 0 序列化失败、n≥11 步全部真 LLM(11/11)**。修复生效于后续 run;历史 run 的测量与治理数据不受影响。

### 5.1 H 系列旧材料代码硬化（2026-07-05,软件实现 + 离线真验）

在动新材料前,用同一片旧材料把此前列为局限的 ③④⑤⑥ 全部**软件实现并用真实数据离线真验**(纯加法 / `*_v2`+delta / legacy 永不覆盖 / opt-in / fail-safe):

| ID | 补的局限 | 落地(文件/函数) | 离线真验证据 |
|---|---|---|---|
| **H1** | ④ C³ 证书只写盘、主循环不消费 | `termination_evaluator._c3_consume` + `evaluate_termination`(新增 `verdict_effective`/`c3` 块,**单调安全 c3_stop⊆legacy_stop**);live `_finalize_c3` 落 `c3_evidence.json` 供 Stage1 聚合自动消费 | `pH1` **11/11**:真 attapulgite history_db replay;C³ 只推迟非硬停、永不更早停、budget 硬停不可推迟、向后兼容 |
| **H2** | ⑤ 仪器见证类故障未真注入 | `scientific_harness/instrument_witness.py`(`OnlineInstrumentWitness`+`submit_measurement_online`)+ `witness.py` 增独立 `TEMP_TRACE`;`_run_instrument_witness`/`_finalize_instrument_witness` 接 live 逐点 | `pH2` **17/17**:真 EIS .txt 作独立 RAW_FILE 见证;ACK 丢失→先核对不盲目重试仍 confirmed、仪器卡住/文件缺失/文件延迟/条码错配/校准过期全不进 BO、blind_retry=0 |
| **H3** | ⑥ canary 仅 2 次真微调 | `_active_design_canary_nudge` 邻域 ±1→±`canary_max_steps`(默认 2)step,仍守包络/回温≤15K/ActionGate | `pH3` **7/7** + `p16` **8/8** 无回归 |
| **H4** | ③ Rb-ACT R4 未激活 | `rb_act/activation.py`(`build_activation`:三条件人审门 + σ_v2 + delta + "BO 不劣化"守卫);`_finalize_rb_r4_activation` 接 live 收尾;`rb_r4_activate`/`rb_r4_signoff` kwargs | `pH4` **6/6**(**87 真谱**):未签核恒 legacy、三条件齐备才产 σ_v2(87 点)、`legacy_overwritten=0`、Spearman=0.995、`bo_not_degraded=true`;`p18` **12/12** 无回归 |

> **诚实边界**:H1–H4 均已**软件实现 + 离线真实数据验证**(77 pytest 无回归);**H2/H3/H4 的真机 live 终验待旧材料一次全温区 run**(不改代码/不伪造);H4 替换态须你的签核 token;R4 跨批生产激活仍属 G-5。物理破坏性故障(短接/断路)仍须 dummy cell。

---

## 6. B 轨硬门(G-系列)真实状态

| 门 | 状态 | 真实证据 |
|---|---|---|
| **G-2 真机硬件故障注入** | 🟢 **已执行** | fe4:`inject_fault` 注入 `SAMPLE_MISMATCH@13.3°C` + `QA_FAIL@7.3°C` → 真实 `measurement_txn` 六用途全 REJECT;`fault_injection_summary.json` `n_injected=2, all_caught=true, any_entered_bo=false`;温控/CHI 未受影响;`p20` 10/10。**协议/见证类故障(ACK/仪器卡住/文件/条码/校准)已由 H2 软件实现并离线真验(`pH2` 17/17),live 终验待旧材料 run;仅电极短接/断路等物理破坏性故障仍须 dummy cell** |
| **G-4 enforce/canary 真机长跑** | 🟢 **已执行** | fe4b:enforce 真拒 6 深冷点(−49.4~−58.4 四点 + −79.4/−82.4)`entered_bo=false` 且真挡出 BO(`n_committed=27/n_rejected=6`,bundle 真过滤 + `.full` 备份 + recipe `source_mode=real`);27 正常点零误拦;canary 2 次 `EPISTEMIC_CANARY_SETPOINT` 物理执行(目标−10.8/−19.7→实测−11.0/−19.8,\|Δ\|≤2.9°C,31 步护栏回退);全程 `bypass=0`;`p21` 10/10 |
| **G-5 Rb-ACT R4 生产替换** | 🟡 **审计门全过 + 激活模式已实现,跨批替换未激活** | fe2+fe3+fe4b 三 run 合并 **87 真谱/75 配对点**,四验收门全过(`gates_pass=true`:paired 75/30、0 未解释翻转、report 0.862/0.6、median\|Δ\|=0.0/0.1 dex);`p18` 12/12。**H4 已实现 R4 激活模式**(三条件人审门+σ_v2+delta,`rb_act/activation.py`),离线用 87 真谱验:签核后 σ_v2 全产出、Spearman=0.995、`legacy_overwritten=0`、`bo_not_degraded=true`(`pH4` 6/6)。**真机替换态 run 须你的签核 token;跨批多片生产激活仍属 G-5** |
| **G-1 新 R/N 前瞻闭环** | 🔴 **未做** | R=0.15/0.12 等未合成;须先经官方 MOBO+LLM 冻结→push→才合成(前瞻纪律) |
| **G-3 多批 live 互证** | 🔴 **未做** | 4 次 full-temp live run 全部**同一物理片**=同片重复,非多片互证;须 ≥3 独立制备片 |

---

## 7. 真实 vs 冻结 vs 存根 vs 只读（诚实清单）

| 组件 | 状态 |
|---|---|
| Stage0 离线/在线、Stage1 闭环、Stage2/3 编排、m6–m8 消融 | **真实可运行** |
| `/api/control`(驱动硬件)、`/api/agent`(决策环) | 真实可运行 |
| `/api/provenance` `/api/campaigns` `/api/samples` | 只读真实 |
| `/api/pipeline` mutating 端点 | **已禁用**(返 disabled) |
| B 轨三包(`scientific_harness`/`memory`/`skills`) | 真实可运行;跨层失效闭环互联 + 端到端撤销演示;自主命令旁路 `autonomous_bypass=0` |
| ESAS-OS 2.0 四插件(`measurement_txn`/`rb_act`/`agent_memory`/`scientific_convergence`) | 真实可运行;**测量事务化/Rb-ACT/R²-Memory 已接 live 回路**;**C³-Harness 已从"只写盘"升级为"主循环消费"(H1:`termination_evaluator` 单调安全消费 `c3_evidence.json`,只推迟非硬停)**;legacy 永不覆盖 |
| 在线仪器见证(`scientific_harness/instrument_witness.py`,H2) | 真实可运行;每点用真实 CHI 文件 sha256 + 温控稳定 + 仪器态经真实 `EvidenceTransaction` 推 C_P;支持协议级故障注入(ACK/仪器卡住/文件/条码/校准);已离线真验(`pH2` 17/17),接 live 逐点,live 终验待旧材料 run |
| Epistemic-OS(`V1.0-qianduan-mainline/analysis/epistemic/`) | 真实可运行;认知证书(σ 层)/阻抗正问题(谱级)/证伪市场(多角色 LLM)**均已接 live 收尾**;active_design 逐点注入 prompt(advisory)+ canary **±2 step 多驱动**(H3) |
| 逐点 LLM agent(`phase_detect`) | 真实调用(n≥5 起,数据积累期 n<5 走规则);**numpy 序列化 bug 已修并复验** |
| Rb-ACT 数值链 | R0–R3 真接、R4 预注册审计通过 + **R4 激活模式已实现(H4,三条件人审门+σ_v2+delta)**;未签核时 **legacy `rb_fitting.py` 仍是 σ/BO 主计算路径**(R4 恒回退 legacy) |
| live 回路 BO | 收尾**一次性 post-sweep BO**(非逐点内层);`entered_bo`=准入标记 |
| S09 候选 / S10 排序 | 默认**确定性冻结**(非现场 LLM) |
| 离线 `create_phase_detector()` | DEPRECATED,恒返回 False |

---

## 8. 诚实局限（不回避）

1. **线 B 地板 n=3 且为回溯离线数据**,冷段 p90 0.356 dex 比代理松 → "候选差<地板" headline 的最大单点风险。
2. **复现感知是负结果**:单曲线 QC 测不准跨片复现(AUROC≈0.52)。
3. **闭环轨迹短**(10 点/2 前瞻轮),不声称收敛。
4. **材料类不新**(藕粉/淀粉/壳聚糖-黏土-磷酸已知),新意全靠转变 + 治理 + 边界。
5. **机理被自身可辨识性封顶 C4**(不声称结构/因果)。
6. **active_design canary 邻域已放宽 ±1→±2 step(H3)** 让更多步实质微调;**仍不做无人值守 enforce 夺权**(有意设计);live 终验待旧材料 run。
7. **C³-Harness 收敛证书已被主循环消费(H1)**:`termination_evaluator` 单调安全消费(只推迟非硬停、永不更早停);canary/enforce 级消费留后续。
8. **Rb-ACT R4 激活模式已实现(H4)**:未签核时数值链恒回退 legacy;真机替换态 run 须你签核 token,跨批生产激活仍属 G-5。
9. **仪器见证类故障已软件实现并离线真验(H2)**;仅物理破坏性故障(短接/断路)须 dummy cell。
10. **live 多批仍是同片重复**(G-3 未做),新 R/N 未合成(G-1 未做);**H2/H3/H4 的 live 终验待旧材料一次全温区 run**。

---

## 9. 发表现状与门槛

- **A 轨**:分析门已清(M0–M2 + G1 直接地板),**推荐主投 Tier B**(Comm. Chem./Mater./CRPS/npj,IF 6–10),DD/MLST 保底。剩余=写作(把 v2 结果 + 直接地板写进 Methods/Results/SI)+ 图矢量化 + 续测新 R/N(G-1)。
- **B 轨**:软件层全体系(WP0–WP5 + ESAS-OS 2.0 四插件 + Epistemic-OS)已落地并真机验证治理路径;**距 Tier S 的真机硬门已收三项**:G-2 真机故障对照 🟢、G-4 enforce/canary 真机执法 🟢、G-5 R4 审计门全过 🟡(替换留人审);**剩余硬门 = G-1 新 R/N 合成 + G-3 多批(多片)live 互证 + G-5 人审激活**。
- **不能用"软件 Demo/测试通过"预支 Tier S**——档次由真机证据决定。

---

## 10. 复现入口（可移植）

```bash
# 后端(V1.0-qianduan-mainline/ 下)
python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000
# 前端(frontend/ 下)
npm install && npm run dev
# 离线 stage0 复算
python stage0_measurement/run_offline.py --data_dir <dir> --material X --thickness 0.07 --area 1.96
# 线 B 闭环 / 前瞻冻结
python stage1_optimization/run_optimization_loop.py --optimizer mobo --campaign_config <json> --stage0_results_dir <dir>
python stage1_optimization/line_b_guardrail_run.py        # FROZEN_SEED=20260608
# B 轨端到端撤销演示 / 硬件写路径审计
python -m scientific_e2e.demo_end_to_end
python scripts/audit_hardware_write_paths.py --strict
# 创新点 live/离线验证脚本(真实数据/真 LLM)见 V1.0-qianduan-mainline/analysis/verification/p*.py
```
- 密钥:各 stage `.env` 填 `LLM_API_KEY`(OpenRouter);`key.txt` 第一行供分析脚本/出图。
- 机器相关项走环境变量(`STAGE0_CHI_DATA_DIR` 等),代码用 `Path(__file__)` 相对解析、可移植。

---

## 11. 诚信纪律（项目灵魂）

- **前瞻**:改主张相关参数前先 git commit+push 盖时间戳(`experiments/prospective`);线 B 官方 recipe 已冻结(freeze_commit `c185379`,2026-06-08,raw R0.0285→LLM R0.28,safety passed)。
- **主张阶梯**:C0–C5,EIS-only **硬封顶 C4**;11 条绝对化措辞正则护栏。
- **闭环留痕**:每轮三件套 SHA256 链;LLM 只存 prompt 指纹。
- **分层**:`replay ≠ real`、每体系独立 history、S8 母体系不混入 BO、v2 声明恒 HOLD、legacy 永不覆盖。

---

## 12. 一句话结论

> 这是一个**证据全真、负结果不藏、主张被代码护栏封顶**的表征受限自主发现项目。**A 轨**已到 Tier B 投稿线(缺写作 + 续测新 R/N)。**B 轨**软件全体系已落地并在真机 live 回路里跑通治理、逐点 LLM 决策、收尾机制推理与认知证书;**H 系列(2026-07-05)已把原先列为局限的 ③C³ 主循环消费、④在线仪器见证+协议级故障注入、⑤canary 多驱动、⑥R4 激活模式全部在旧材料上软件实现并离线真验(`pH1`–`pH4` 全过、77 pytest 无回归)**。距 Tier S 的真机硬门已收 **G-2🟢 + G-4🟢 + G-5🟡**,**剩余 = G-1 新 R/N 合成、G-3 多片 live 互证、G-5 R4 跨批人审激活、G-2 物理破坏性故障(dummy cell)、H2/H3/H4 的 live 终验**——均须物理条件,绝不软件伪造。
