# 项目真实情况报告(2026-06-22,2026-06-24 更新)

> **真实性声明**:本报告所有论断均由(a)逐文件读取真实源码、(b)对真实 stage0/stage1 产物 JSON 重算、(c)真实 LLM/盲评消融(m6–m8)三类证据支撑;凡冻结/存根/只读/代理/缺口处均显式标注。**不取自总结文档的自述,不美化、不隐藏负结果。** 配套:`SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md`(代码级执行追踪 + 附录 A–E 下钻)、`THREE_INNOVATIONS_CODE_GROUNDED_20260618.md`(创新点+数据)、`_new_data_analysis/PUBLICATION_READINESS.md`(就绪度)、`MANUSCRIPT_*`(手稿)。

---

## 1. 这是什么项目(定位)

一个 **物理/QC/claim-governed 的 agentic 材料发现项目**:在质子导体(酸-黏土 / 生物聚合物-黏土)上做 **EIS-only、表征受限条件下的"可信自主发现"**。核心不是材料数字,而是**"看不全(只有传输数据)时,自主 agent 能可信地声称什么"**,并给出两条**可测量边界**:**复现地板(下界)**与**可辨识性天花板(上界)**。

- **两模式**:线 A(迁移推理:从酸-黏土证据迁移到生物聚合物-黏土,发现亚零度传输转变);线 B(凹凸棒土上跑真实 MOBO+LLM 闭环)。
- **一治理核**:可校准的主张阶梯 C0–C5 + 防过度声称护栏。

## 2. 真实数据家底(测了什么 / 没测什么)

| 体系 | 真实独立重复(已 stage0 处理) | 关键事实 |
|---|---|---|
| **LRS 藕粉** | **7 次**:0429CS, 0509CS, 6.12, 6.15_merged, 0615_s2, 0616_s3, 0617_s3b | 每片厚度均有制备文件记录(4月 `材料制备过程.txt` / 6月 `材料制备.txt`);4 月薄片 0.02cm、6 月标准化 ~0.07cm |
| **starch 淀粉** | **4 次**:0427CS, 0428CS, 6.11, 6.13 | — |
| **CHITO 壳聚糖** | **2 次**:0430CS, 0501CS | 边界反例(低温段仅 2 点,无干净转变) |
| **凹凸棒土(线B)** | **10 个 trial**(`history_db_attapulgite.json`,各不同 R/N) | 最优 trial1 R=0.186/N=1.029 cs=−1.941;**无同配方重复**(→ 见 §7 缺口 G1) |
| S8 海泡石(母体系) | 20-trial 历史 | **仅作先验/迁移参考,不混入凹凸棒土 BO 训练库**(campaign JSON `transfer_reference` 明确) |

**没有的(有意不补)**:任何结构表征(XRD/SEM/DSC/NMR)、新材料体系、新仪器。**DRT 实测不可行**(本数据 R²<0,不作证据)。

## 3. 系统怎么跑(确定性 vs LLM 的真实分布)

详见 `SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md`。**真实 LLM 调用仅在**:Stage1 Step5 策略规划(`openai/gpt-5.4`,temperature=0.0,只存 prompt SHA256 指纹、不存原文);Stage0 在线相变(可选 `gpt-5.2`);Stage3 上游 S04–S08(假设/机制/描述符/文献)。**默认确定性(无 LLM)**:Stage0 全分析管线、Stage1 优化器/记忆/终止/安全、**Stage3 的 S09 候选生成(`_build_d4_deterministic_output` 硬编码)+ S10 排序(8 维加权)+ S14 阶梯**、agentic 旁路、v2 守卫。

> **诚实关键**:发表那次 S09/S10 是**有意冻结的确定性**(锁时间戳 + 可复现,项目公开记录);因此本项目**主张温和**:"LLM 从广义文献池**选择并重组** + 实验前冻结 + 事后 EIS 验证"(强度 B+),**从不声称"LLM 独立发现 LRS"/收敛/事后改分**。

## 4. 三创新点真实进展

| 创新点 | 完成度 | 真实支撑 | 未闭合 gap |
|---|---|---|---|
| **P1 亚零度传输转变 + 可调** | 高 | 13/15 集有转变,T_break **−22~−39°C**;LRS 低温 Ea **0.69±0.07 eV**(7 重复);陡峭度 LRS≈19×→starch≈2.4×;CHITO 边界反例 | 单体系配方梯度(仅凹凸棒土能做,需 G1-B) |
| **P2 复现地板 + 可校准治理** | 中高 | 地板 σ 0.245(6月)/0.32(全)dex;校准 ECE **0.78→0.13**(留一数据集,只去过自信不增分辨力);单曲线 QC **测不准**跨片复现(AUROC≈0.52) | 线 B 直接地板(现用 LRS 代理,G1-A) |
| **P3 真实 MOBO+LLM 闭环 + 治理** | 中 | 闭环代码真、recipe SHA256 留痕、前瞻冻结;诚实 null;BO 比 random 快(4.1 vs 5.5);LLM=安全(R0.02→0.28);m6–m8 消融 governed 0% vs popularity 100% 干扰 | 轨迹短(10点/2前瞻轮) |
| **可辨识性天花板(P2 理论)** | 中 | 三机理律 Arrhenius/Mott/VTF 在低温支 **ΔR²=0.006**(不可辨识);AICc 3 段=1.0(描述符可辨识)→ 主张封顶 C4 | 形式化理论完整度(若冲更高档) |

**B 轨 Agent 方法学创新(冲 Tier S)** — 经 WP0–WP5(2026-06-24),三创新已从"并列软件包"推进到**跨层失效闭环互联 + 自主命令旁路清零 + 端到端撤销演示**;**但仍未经真机故障对照,不擅自计入当前档次**(诚实定位):

| 创新点 | 当前实现(WP0–WP5 后) | 成熟度 / 验收 |
|---|---|---|
| **SciTX 三重提交 Harness** | `scientific_harness/`:C_P 多见证推断(`witness.py`,仅软件见证⇒至多 possible)+ C_M(intended_use) 分级(`admission.py` U1–U6)+ C_E(claim_id) 绑定主张 + `EvidenceTransaction` 编排 + **`ActionGate` 自主命令唯一入口** | **R3→R4(命令路径)**:审计 `autonomous_bypass=0`、`--strict` 过;shadow/enforce 模式;待真机故障对照(G1) |
| **E-Mem 证明携带记忆** | `scientific_memory/`:四值逻辑超图 + 失效传播 + 快照写门 + 根去重 + 失效→视图重建 + 压缩证书 + **`history_bridge`/`bo_retrain_bridge`(真实 history_db 物化 → GP 重训)** | **R3→R4(失效→BO 链)**:失效→重建→**GP 重训**已闭到底;待 L0/L3 层 |
| **PC-Skills 可认证 Skills + 双账治理** | `scientific_skills/`:6 真实 EIS Skill + **三层证书(形式/统计/计量,Wilson 下界,小样本 provisional)**+ runtime/漂移/撤销 + 认知⊥执行双账户 | **R2→R3**:证书由检查产生(不可手填);待真机成功率 + canary 灰度 |

> **跨层闭环已互联 + 端到端演示**:PC-Skills 撤销 → E-Mem 失效 → 重建 BO 视图 → **GP 在更小 committed 集上重训**(`history_bridge`+`bo_retrain_bridge`,真实 history_db);`scientific_e2e/demo_end_to_end.py` 跑通完整真链(best E1→E3,**governed 严格优于 ungoverned**,B0/B2/B4/B5 真实臂)。全量 **208 测试全绿**。
> 配套 M0–M2 v2 分析模块见 `_new_data_analysis/stage0_v2/`(版本冻结 / Rb 方法不变性 / 稳健 Arrhenius / 断点不确定度 / 合成 FPR / 可辨识性 / 复现地板方差 / 电导不确定度),均只产 `*_v2` 旁路、不覆盖 legacy。

## 5. 关键真实结果(产物可复算)

- **复现地板** `_new_data_analysis/repro_floor/`:combined_score 地板 0.26–0.33;闭环顶端 2/9 候选落地板内 → 诚实 null 的定量根因。
- **校准 ON/OFF** `_new_data_analysis/calibration/g2g3_*`:ECE 0.775→0.126;Murphy reliability 0.61→0.02、resolution 0.011→0.012(只去过自信)。
- **复现感知负结果** `calibration/repro_aware_*`:留一数据集 AUROC≈0.5(KK 跨数据集与复现率弱负相关 −0.20)。
- **可辨识性** `identifiability/`:ΔR²=0.006 / AICc 3 段=1.0。
- **闭环对照** `replay/strategy_comparison.*`:BO 4.1 vs random 5.5;纯BO 无约束最优=R0.02 边缘=记录 raw-MOBO,LLM 拉回 R0.28。
- **跨样品规律** `regularity/`:13 集 T_break/两段 Ea 规律图(SVG/TIFF)。
- **治理 agent 消融** `m6_baseline_ablation/`(M6–M8,真 LLM gpt-5.4 + 跨模型盲评):污染池 governed 0% 纳入 vs popularity 100%;护栏 40→0;盲评 governed 4.3≫popularity 1.0。

## 6. 真实 vs 冻结 vs 存根 vs 只读(诚实清单)

| 组件 | 状态 |
|---|---|
| Stage0 离线/在线、Stage1 闭环、Stage2/3 编排、m6–m8 消融 | **真实可运行** |
| `/api/control`(驱动硬件)、`/api/agent`(决策环) | 真实可运行 |
| `/api/provenance` `/api/campaigns` `/api/samples` | 只读真实 |
| `/api/pipeline` mutating 端点 | **已禁用**(返 disabled) |
| evidence_jobs `threshold_sweep` / `ablation` | **已做实**(M1-8,读 v2 真实产物) |
| three_pillars v2 工具 | 真实可运行,但 **v2 科学声明恒 HOLD、CHI 自动化恒关** |
| B 轨三创新(`scientific_harness`/`memory`/`skills`,WP0–WP5) | 真实可运行(208 测试全绿;跨层失效闭环互联 + 端到端撤销演示;**自主命令旁路已清零**);**软件层,未经真机故障对照,不擅自计入档次** |
| `routers/agent.py` 自主硬件命令 | **已收口经 `ActionGate` 唯一入口**(默认 shadow=行为不变,enforce 可拦截);审计 `autonomous_bypass=0` |
| `run_online.py --harness_mode shadow\|canary\|enforce` | 真实可运行;shadow 对定温扫描有效,canary/enforce 诚实降级 shadow(属自主路径),待 G1 启用 |
| `scripts/audit_hardware_write_paths.py` | 只读审计 + `--strict` CI 门(当前 0 旁路,exit 0) |
| `_new_data_analysis/stage0_v2/*`(M0–M2 v2 分析) | 真实可运行,只产 `*_v2` 旁路产物,**不覆盖 legacy 冻结结果** |
| 离线 `create_phase_detector()` | DEPRECATED,恒返回 False |
| S09 候选 / S10 排序 | 默认**确定性冻结**(非现场 LLM) |
| 线 B 复现地板 | 现为 **LRS 生物聚合物代理**(非凹凸棒土实测)→ G1 |
| 手稿 ECE 旧值 0.05 | 已更正为诚实 0.13(随机划分泄漏值弃用) |

## 7. 诚实局限(不回避)

1. **线 B 地板是代理**(无同配方重复)→ "候选差<地板" headline 的最大单点风险。
2. **复现感知是负结果**:单曲线 QC 测不准复现,目前无可用的逐测点复现预测器。
3. **复现性本身中等偏弱**(σ 仅复现到 ~1.8–2.1×)。
4. **闭环轨迹短**(10点/2前瞻轮),不声称收敛。
5. **材料类不新**(藕粉/淀粉/壳聚糖-黏土-磷酸已知),新意全靠"转变 + 治理 + 边界"。
6. **机理被自身可辨识性结论封顶**(只能到描述符层,不能声称结构/因果)。
7. 零碎:starch_0427CS 的 T_break≈−5°C 离群;CHITO 反例仅 n=2。
8. **B 轨全程软件层**:三创新未经真机故障对照;enforce 非运行默认(shadow 保行为)。

## 8. 发表现状与门槛(详见 PUBLICATION_READINESS)

- **推荐主投 Tier B**(Comm. Chemistry/Materials / CRPS / npj 计算包装,IF 6–10);**DD/MLST 保底**(IF 4–6,已到投稿线)。
- 全文(Abstract+Intro+Methods+Results 3.1–3.6+Discussion)+ 7 图 + 7 图注 + 消融/对照/诊断/定位**已齐**。
- **A 轨唯一仍需"动手测"的硬门槛 = G1**:复现 **R=0.186/N=1.029 ×3**(测线 B 直接地板)+ 续测 **R=0.15/N=1.03、R=0.12/N=1.00**(解决"最优在边缘还是内部")。其余为出版工程(图矢量化/SI)+ `nature-polishing` 措辞。
- **G1 时同步开 Harness shadow**:`run_online.py --harness_mode shadow` 在真机测量旁路记录三提交对账,为 Tier S 的 Harness 主张攒**真机证据**;只记录、fail-safe,不影响 G1。
- **冲 Tier S 的 B 轨(WP0–WP5 已落地)**:三创新已"运行时语义 + 跨层失效闭环 + 自主命令旁路清零 + 端到端撤销演示";距 Tier S 投稿仍差 **真机故障对照(需 G1)+ enforce 生产灰度**(详见 `OPTIMIZATION_EXECUTION_PLAN §9` 遗留项排序),**不能用"软件 Demo/测试通过"预支 Tier S**。

## 9. 复现入口(可移植)

```bash
# 后端(V1.0-qianduan-mainline/ 下)
python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000
# 前端(frontend/ 下)
npm install && npm run dev          # http://127.0.0.1:5173
# 离线 stage0 复算
python stage0_measurement/run_offline.py --data_dir <dir> --material X --thickness 0.07 --area 1.96
# 线 B 闭环 / 前瞻冻结
python stage1_optimization/run_optimization_loop.py --optimizer mobo --campaign_config <json> --stage0_results_dir <dir>
python stage1_optimization/line_b_guardrail_run.py        # FROZEN_SEED=20260608
# B 轨端到端撤销演示 / 硬件写路径审计
python -m scientific_e2e.demo_end_to_end        # (在 stage1_optimization/ 下)
python scripts/audit_hardware_write_paths.py --strict
```
- 密钥:各 stage `.env` 填 `LLM_API_KEY`(OpenRouter);`key.txt` 第一行供分析脚本/出图。
- 机器相关项全走环境变量(`STAGE0_CHI_DATA_DIR` 等),代码用 `Path(__file__)` 相对解析、可移植。

## 10. 诚信纪律(项目灵魂)

- **前瞻**:改参数前先 git commit+push 盖时间戳(`prospective_2026H2`);线 B 官方 recipe 已冻结(freeze_commit `c185379`,frozen_at 2026-06-08,raw R0.0285→LLM R0.28,safety passed)。
- **主张阶梯**:C0–C5,EIS-only **硬封顶 C4**(不声称结构/因果);11 条绝对化措辞正则护栏。
- **闭环留痕**:每轮三件套 SHA256 链(suggestion/stage0_result/decision_trace);LLM 只存 prompt 指纹。
- **分层**:`replay ≠ real`、每体系独立 history、S8 母体系不混入 BO、v2 声明恒 HOLD。

---

> 一句话:**这是一个证据全真、负结果不藏、主张被代码护栏封顶的表征受限自主发现项目;当前真实结果已到 Tier B 投稿线,唯一仍需动手的硬门槛是 G1 那一组凹凸棒土同配方重复实验。B 轨三创新软件层(WP0–WP5)已成体系、208 测试全覆盖,但距 Tier S 仍差真机证据。**
