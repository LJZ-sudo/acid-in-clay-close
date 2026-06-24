# M7 Full Ablation — 量化 governed LLM agent (S09) 相对基线的增量

> 真 LLM（OpenRouter `openai/gpt-5.4`）跑 S09 候选生成；关掉冻结的
> `deterministic_from_d4`。3 个证据池 arm × 5 seeds + 2 个确定性基线 × 2 个池。
> 共 16 次 LLM 调用（1 smoke + 15 generation）。
> 全部产物在 `m6_baseline_ablation/m7_full/`，**未碰主线代码 / 未写主线 outputs**。

## 1. 实验设计

| arm | 证据池 | 目的 |
|---|---|---|
| **A0** governed_full | 完整冻结池（7 描述符 + 31 卡 + 39 D4-claim） | agent 主臂 |
| **A1** ablate_evidence | 抽空全部文献证据内容（仅留 D1–D7 描述符） | 测"证据约束"的价值 |
| **A2** distractor_injected | 完整池 + 注入 6 张高显著 off-topic 卡（LiFePO4/硅负极/MXene/钙钛矿/MoS₂/Pt），每张多条 claim 以抬高频次 | 测抗干扰 |

确定性基线（不调 LLM，同池）：
- **random** — 从池内组分随机组配
- **popularity** — 按 claim 频次堆叠最热组分

指标：`distractor_inclusion_rate`（候选组分命中 off-topic 词表占比，越低越好）、
`ontopic_rate`（命中质子导体相关词表占比）、`evidence_audit_rate`（element_evidence 引用的 paper_id 落在池内的占比）、
`seed_stability_jaccard`（同 arm 跨 seed 组分集合平均 Jaccard）。

## 2. 核心结果

| 方法 | 池 | 干扰项纳入率 | on-topic 率 | 证据可审计率 | seed 稳定性 |
|---|---|---|---|---|---|
| **A0 governed LLM** | 干净 | **0.00** | 0.95 | 1.00 | 0.65 |
| **A1 LLM (去证据)** | redacted | **0.00** | 0.88 | 1.00 \* | 0.58 |
| **A2 governed LLM** | **+干扰项** | **0.00** | 0.99 | 1.00 | 0.61 |
| random baseline | 干净 | 0.00 | 0.80 | — | — |
| popularity baseline | 干净 | 0.00 | 1.00 | — | — |
| random baseline | **+干扰项** | 0.10 | 0.70 | — | — |
| **popularity baseline** | **+干扰项** | **1.00** | 0.00 | — | — |

（每个 LLM arm = 5 seeds 平均；`distractor_inclusion_rate` 在所有 15 个 LLM run 中**逐个**都是 0.0。）

## 3. 关键结论

### 3.1 杀手级对照：抗干扰（A2 vs popularity，同一污染池）
往证据池注入 6 张高频干扰卡后：
- **popularity 基线 100% 崩盘**：top 组分变成
  `LiFePO4 / silicon anode / Ti3C2 MXene / CsPbI3 perovskite / MoS2 / Pt/C` —— 干扰项纳入率 **1.00**，on-topic **0.00**。
- **governed LLM agent 完全不为所动**：5/5 seed 干扰项纳入率 **0.00**，on-topic **0.99**。

→ 这量化了 agent 相对"按热度选材料"的增量：**面对污染文献池，频次驱动的基线被带偏到 100%，
而受描述符语义 + cold-side 约束的 agent 抗干扰到 0%。** 这是可写进论文的硬对照。

### 3.2 证据约束的真正价值是"可溯源"，不是"防跑题"（A0 vs A1）
去掉全部文献证据内容后（A1），LLM 仍能生成 on-topic 候选（0.88）——说明**模型内部知识本就很强**，
"证据池"不是用来防止它跑题的。
\* **caveat（必须诚实写）**：A1 的 `evidence_audit_rate` 仍显示 1.0，是因为我保留了卡的 `card_id`（只 redact 了内容），
LLM 照样把这些**空壳 id** 贴进 `analog_paper_ids`。这恰恰暴露了"裸 LLM 自报证据"的风险：
**模型会贴 id，但只有证据池真含 (component×descriptor) claim 时，这些引用才可信。**
→ 这正是本系统设计 D4 claim 池 + 下游 S10 独立 claim 锚定审计的理由：把"LLM 自报自证"换成"上游证据独立锚定"。

### 3.3 收敛稳定但非退化
seed 间组分集合 Jaccard ≈ 0.58–0.65：核心 motif（chitosan / starch / PVA / 1D 粘土 / 磷酸 / DES）跨 seed 稳定，
边缘组分有合理变化 —— 是"稳定但非死记"的健康表现。

## 4. 对创新点1（transfer agent）的意义
- 现在有了**真 LLM 臂**的逐 seed 数据，可直接写"governed agent vs naive popularity"的消融。
- 主张边界（与预注册一致）：**"agent 在受污染证据池中保持 0% 干扰项纳入、100% 候选可链回池内证据"**，
  而频次基线 100% 被带偏。**不**主张"LLM 独立发明 LRS / 收敛 / 发现新机制"。

## 5. 诚实 caveat（不可隐藏）
1. 单模型（gpt-5.4）、N=5 seed、temperature=0.6；非大规模统计。
2. on-topic / distractor 分类用**人工词表**（确定性、可复现，但词表本身是作者设定）。
3. A1 的 `evidence_audit_rate` 受"保留 card_id"影响（见 §3.2），不能解读为"无证据也可溯源"。
4. compact prompt 下 LLM 省略 `role_in_formulation`/`analog_reason`，做了兜底占位；
   **每个 run 的未修改 LLM 原始输出**已存档 `m7_full/A*_seed*_raw.json`，可核。
5. 盲评（让独立评审对候选物理合理性打分）尚未做 —— 可选的进一步加强。

## 6. 产物清单（m7_full/）
- `metrics.json` — 全部指标（arm 聚合 + per-seed + baseline）
- `A{0,1,2}_*_seed{1..5}_raw.json` — 每个 run 的 LLM 原始输出（未修改，留证）
- `console.txt` — 运行日志
