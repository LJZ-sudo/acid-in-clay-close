# Pre-submission review (nature-reviewer skill) — 2026-06-21

> ② 产物。按 `nature-reviewer` 技能格式:3 审稿人(仅侧重不同)+ 交叉综合 + 风险项。基于
> `MANUSCRIPT_INTRO_METHODS.md` + `MANUSCRIPT_RESULTS_DISCUSSION_ABSTRACT.md` 的真实草稿事实。
> 立场=审稿人(非作者辩护)。不臆造身份/实验/引用;不下编辑部录用结论。目标档=Digital Discovery / MLST
> 现实档(非字面 Nature),按"originality / importance / interdisciplinary readership / technical
> soundness / readability"五轴评估。**故意把作者自评 #1 的弱点照审稿人会挑的方式写足。**

## Review setup
- **Input scope**: Abstract + Introduction + Methods + Results + Discussion 草稿;图为占位(floor/regularity/repro_aware/identifiability/replay 真实产出),无完整 SI、无完整参考文献。
- **Assessment boundary**: 仅就所给草稿与图说明评审;未见原始谱、误差棒细节、统计检验完整报告、参考文献表;据此处的 confidence 有边界。
- **Shared manuscript claim summary**: 仅凭传输(EIS)数据,(1) 跨 4 体系 13 重复确立可调的亚零度质子传输转变;(2) 实测制造复现地板,并证明单曲线 QC 不能预测跨片复现(留一数据集 AUROC≈0.5),repeats 上 isotonic 把 ECE 0.75→0.05;(3) 结构可辨识性将主张封顶在描述符层;(4) 真实闭环报告诚实 null(顶端候选差 < 地板)。
- **Visible evidence base**: 13/15 集分段转变;LRS 低温 Ea 0.69±0.07(7 重复);地板 0.245–0.33 dex;留一 AUROC≈0.5(KK-only 0.31);三机理律 ΔR²=0.006;AICc 3 段≈1.0;闭环 10 点/2 前瞻轮。
- **Missing materials affecting confidence**: 完整误差量化与显著性检验、参考文献与定位对比、线 B 同配方重复、SI 制样/EIS 细节、图的最终版与图注。

---

## Reviewer 1 — emphasis: uncertainty quantification & methodological claims
- **Overall assessment**: 概念框架(地板+天花板)有吸引力且诚实,但**核心方法贡献相当一部分是负/null 结果**,需要更强的"这为什么是贡献而非局限"的论证。
- **Who would be interested, and why**: 自驱动实验室、主动学习与不确定性校准社区——因为它把"湿实验复现"与"agent 把握度"直接对接,这一对接在该领域确实少见。
- **Major strengths**: (1) 用真实独立重复而非模拟/文本做校准;(2) 留一数据集协议防泄漏,方法学上规范;(3) 结论与证据对齐、负结果不藏。
- **Major concerns**:
  1. **KK-only 留一 AUROC=0.31(显著低于 0.5)需要解释**。低于随机意味着跨数据集系统性反相关,审稿人会怀疑 QC 评分被数据集身份混淆,或标签构造引入偏差;不解释会被视为管线问题而非"洞见"。
  2. **"单曲线测不准复现"与"isotonic 把 ECE 0.75→0.05"表面张力**:若把握度无判别力(AUROC≈0.5),那 ECE 的改善主要来自把所有把握度拉到基率附近(re-centering),其"校准"价值需说清是 reliability 而非 resolution——否则像是用低信息预测换低 ECE。
  3. **可辨识性结论的新颖性**:EIS 反演非唯一/DRT 病态是公认事实;作者需说明"把它形式化为主张许可"相对既有 identifiability 文献到底新在哪,否则会被读成"已知事实换个说法"。
- **Technical failings to address**: 给出 AUROC<0.5 的诊断(按数据集分层、置换检验);报告地板与 AUROC 的置信区间/自助误差;明确 ECE 改善的 reliability vs resolution 分解。
- **Assessment vs criteria**: technical soundness 中上(协议规范),originality 中(负结果+已知非唯一性),readability 好。
- **Recommendation posture**: 适合方法型期刊的 major revision;以负结果为主轴需要把"贡献性"论证补足。

## Reviewer 2 — emphasis: materials & electrochemistry
- **Overall assessment**: 作为材料发现稿件偏弱;**材料体系不新、机理被作者自我封顶**,正面材料增量有限,更像方法/计量学论文。
- **Who would be interested, and why**: 质子导体与固态离子学读者会对"亚零度两段转变 + 跨体系规律"有兴趣,但会要求更强的电化学严谨性。
- **Major strengths**: 宽温(至约 −90 °C)密集 EIS 数据有价值;7 重复的低温 Ea=0.69±0.07 eV 是可信的定量锚。
- **Major concerns**:
  1. **新颖度**:藕粉/淀粉/壳聚糖–黏土–磷酸属已知质子导体家族,"换生物聚合物"易被评为增量;卖点必须完全压在转变描述符与方法上,但那样材料读者的兴趣下降。
  2. **边界反例证据薄**:CHITO 仅 2 个数据集且低温段仅 2 点即判"无干净转变",样本不足以支撑"边界"定性。
  3. **离群与一致性**:starch 某片 T_break≈−5 °C 明显偏离同族 −24~−31 °C;需说明是制样差异还是分析假象,否则削弱"规律"。
  4. **复现到 ~1.8–2.1×** 的电导一致性按固态离子学标准属中等偏弱,审稿人会质疑由此得出的所有结论的精度。
  5. **缺机理判据**:无变湿度/变电极/DRT 有效性等电化学对照,"传输证据"是否足以排除电极极化/接触电阻贡献需要正面回应。
- **Technical failings to address**: 补 CHITO 重复或下调其结论强度;解释 starch 离群;给出室温电导与文献基线的同条件对比(已用有出处基线,但需同湿度/同几何说明);明确两电极构型下接触/电极贡献的排除。
- **Assessment vs criteria**: importance 中(方法>材料),technical soundness 中(电化学对照不足),originality 中下(材料层面)。
- **Recommendation posture**: 若作为材料稿=major revision 偏 reject 风险;若重定位为方法稿则更合适。

## Reviewer 3 — emphasis: autonomous systems / self-driving labs
- **Overall assessment**: 诚实的系统论文,**治理与诚实 null 是亮点**,但"自主发现"的正面成果有限,需说明相对已有 SDL/agent 工作的增量。
- **Who would be interested, and why**: SDL/agent 方法论读者——因为它把"诚实边界"做成可测协议,这正是该领域当前缺口。
- **Major strengths**: (1) 前瞻冻结+时间戳、null 如实报告,符合该领域对可信度的呼声;(2) 把闭环 null 用复现地板定量解释,逻辑闭环漂亮;(3) 两模式一治理核的组织清晰。
- **Major concerns**:
  1. **闭环证据弱**:10 点/2 前瞻轮、代理弱,无法支撑关于自主优化的一般性结论;"loop optimizes noise"是有力叙事但样本极小。
  2. **关键 headline 依赖代理地板**:线 B 没有同配方重复,"顶端候选差<地板"用的是生物聚合物代理地板——这是**核心主张的最大单点风险**,必须补线 B 直接地板或显著弱化措辞。
  3. **相对既有工作的增量**:误支持/claim 审计/可复现 UQ 已有 2026 文献,作者需明确"复现地板+可辨识性许可"组合的独特性,否则 originality 受质疑。
  4. **泛化声称**:Discussion 称框架可迁移到其他表征受限场景,但仅单一材料家族证据,属 over-generalisation,需收敛。
- **Technical failings to address**: 补 ≥2 个线 B 同配方重复以把地板测在优化体系上;把"可迁移"降为"假设";给出与 1–2 个最接近的既有方法的并列对照。
- **Assessment vs criteria**: originality 中上(组合视角),importance 中上(诚实协议),technical soundness 受限于轨迹与代理地板。
- **Recommendation posture**: major revision;补线 B 直接地板是从"有趣"到"可信"的关键。

---

## Cross-review synthesis
- **Consensus strengths**: 诚实/可复现导向、真实独立重复做校准、闭环 null 的定量解释、可辨识性把主张封顶——四者共同构成一个连贯且少见的"可信边界"框架。
- **Consensus technical risks**:
  1. **线 B 地板是代理**(无同配方重复)→ 核心 headline 单点风险(R3 重,R1 次)。
  2. **复现感知=负结果**,且 KK-only AUROC<0.5 未解释(R1 重,R3 次)。
  3. **材料新颖度低 + 机理自封顶**,正面增量有限(R2 重)。
  4. **闭环轨迹短/代理弱**,一般性主张证据不足(R3 重)。
  5. **小样本边界**:CHITO n=2、starch 离群(R2)。
- **Where emphasis differs**: R1 聚焦 UQ 严谨(AUROC<0.5、ECE 的 resolution vs reliability);R2 聚焦材料/电化学对照与新颖度;R3 聚焦闭环证据与代理地板。
- **Broad-interest / significance readout**: 对 SDL/UQ 读者有清晰跨域吸引力;对纯材料读者吸引力弱。定位到方法/数字发现期刊更匹配。
- **Most important issues before a strong case**:
  1. **补 ≥2 个线 B 同配方重复**,把复现地板直接测在优化体系上(消除最大单点风险)。
  2. **诊断并解释 KK-only AUROC<0.5**;把 ECE 改善拆成 reliability/resolution。
  3. **明确相对 2026 既有"误支持/可复现 UQ/claim 审计"工作的增量**。
  4. **收敛泛化措辞**;补 CHITO 证据或弱化"边界反例";解释 starch 离群。

## Risk / unsupported claims
- "loop optimizes noise / 候选差<地板" — 目前由**生物聚合物代理地板**支撑,线 B 体系内未直接证实(not established;需同配方重复)。
- "framework transfers to other characterization-frugal settings" — 单材料家族证据,属 not assessable / over-general。
- "single-curve QC cannot predict reproducibility" — 在本数据成立,但 KK-only AUROC<0.5 的机制未解释,稳健性 not fully established。
- 可辨识性"许可阶梯"的**新颖性**相对既有 EIS 非唯一性/identifiability 文献 — 在所给材料中未做并列对照,not assessable。
- 机理仍为假设(作者已正确声明);任何"抑制结冰/限域水"表述须保持假设语气。
