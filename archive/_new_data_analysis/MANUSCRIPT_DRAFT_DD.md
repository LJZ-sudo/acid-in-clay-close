# Manuscript draft skeleton — primary target: Digital Discovery (alt: Machine Learning: Sci. & Tech.)

> D1 产物(2026-06-21)。全部论断对应**已跑出的真实产物**(§ = `THREE_INNOVATIONS_CODE_GROUNDED_20260618.md`):
> B1 `regularity/` · 复现地板 `repro_floor/` · 校准 `calibration/repro_full_*` · B2 `calibration/repro_aware_*` · C1 `identifiability/` · 闭环 `replay/`。
> 诚实纪律:不声称收敛、不声称发现 LRS、不声称机理结构;负结果如实写。

---

## 1. 标题(三选一)

1. **Characterization-frugal credible autonomous discovery: a reproducibility floor and an identifiability ceiling for EIS-only proton-conductor optimization**
2. What can an autonomous agent honestly claim from transport-only data? A sub-zero proton-transport transition, its reproducibility floor, and its identifiability ceiling
3. Credible autonomous discovery under EIS-only constraints: reproducibility-floor-aware optimization and identifiability-licensed claims in biopolymer–clay proton conductors

> 推荐 #1(把两个"硬边界"——地板 + 天花板——做成卖点,正中 Digital Discovery 的"可复现 + 诚实"口味)。

## 2. 摘要(草稿,~210 词,全诚实)

Autonomous and self-driving discovery pipelines usually assume rich structural
characterization, yet most laboratories are *characterization-frugal*. We ask a sharper
question: what can an autonomous agent **credibly claim** when it sees only electrochemical
impedance (EIS) transport data? Using dense, wide-temperature EIS across **13 independent
repeats** of four biopolymer/clay–phosphoric-acid composites, we (i) locate a **universal
sub-zero proton-transport transition** (break temperature −22 to −39 °C across all four
material families) whose sharpness is **tunable by composition** (lotus-root-starch sharpest,
low-temperature Ea = 0.69 ± 0.07 eV over 7 repeats; chitosan a boundary negative with no
clean transition). We then make the *limits* explicit and quantitative. A **fabrication
reproducibility floor** (~1.8–2.1× in σ; 0.26–0.33 dex in the optimization objective) is
measured from independent repeats; a leave-one-dataset-out test shows that single-curve QC
confidence **cannot** predict cross-pellet reproducibility (AUROC ≈ 0.5), so reproducibility
must be certified by independent repeats rather than by better single-curve scoring — while an
isotonic calibrator trained on real repeats lowers expected calibration error 0.75 → 0.05. A
**structural-identifiability** analysis proves transport data cannot select the conduction
mechanism (Arrhenius, Mott variable-range-hopping and VTF fit within ΔR² = 0.006), licensing
claims only up to a descriptor-level ladder. Finally, a real MOBO+LLM closed loop on
attapulgite returns an **honest null**: its top candidates differ by *less than* the
reproducibility floor. Together these define a reproducibility-floor + identifiability-ceiling
framework for honest autonomous discovery.

## 3. Figure plan(每图都映射真实产物;最终按 §6 规范出图)

| Fig | 内容 | 真实产物 | 类型 |
|---|---|---|---|
| **1** | Graphical abstract / 概念图(两模式一治理核 + 地板/天花板) | `figures/concept_abstract_draft_0.png`(OpenRouter 初稿→PPT 精修) | 概念(非数据) |
| **2** | (a) 一条 LRS 的 59 点分段 Arrhenius(转变);(b) 13 集转变规律(陡峭度图 + T_break) | `regularity/regularity.png` + LRS arrhenius_analysis | matplotlib 真实 |
| **3** | (a) 复现地板 vs 闭环候选;(b) 校准经验曲线 ECE 0.75→0.05 + 可靠性图 | `repro_floor/floor_vs_loop.png` + `calibration/repro_full_calibration.png` | matplotlib 真实 |
| **4** | 复现感知把握度负结果:留一数据集 AUROC≈0.5(KK/+Rb,T/全特征) | `calibration/repro_aware_auroc.png` | matplotlib 真实 |
| **5** | 结构可辨识性:(a) 机理不可辨识(3 律 R² 差 0.006);(b) 描述符可辨识(AICc 3 段=1.0) | `identifiability/identifiability.png` | matplotlib 真实 |
| **6**(SI 或正文) | 闭环 retrospective replay 轨迹(诚实 null) | `replay/replay_trajectory.png` | matplotlib 真实 |

## 4. 正文结构(建议)

1. **Intro** — 自主发现的"表征受限"现实;问题:看不全时能可信声称到什么程度。开放问题锚点见 §6 of canonical doc。
2. **Discovery (Line A)** — 亚零度传输转变 + 13 集普适/可调(Fig 2);CHITO 边界反例。
3. **Reproducibility floor** — 独立重复测出地板;单曲线 QC 测不准复现(Fig 3a, Fig 4);校准机(Fig 3b)。
4. **Identifiability ceiling** — 结构可辨识性 → C0–C5 主张许可(Fig 5)。
5. **Closed loop (Line B)** — 真实 MOBO+LLM + 诚实 null:候选差 < 地板(Fig 6 + 复现地板对照)。
6. **Discussion** — 地板 + 天花板 = 表征受限下可信自主发现的框架;局限(单母体系直接地板待补、点 3 留下一篇)。

## 5. Cover letter(草稿,投 Digital Discovery)

> Dear Editors,
>
> We submit "*Characterization-frugal credible autonomous discovery…*" for consideration in
> Digital Discovery. Autonomous discovery is usually demonstrated under rich characterization;
> we instead ask what an agent can **credibly** claim from transport-only EIS — the regime most
> real labs actually operate in. Our contribution is deliberately **honesty-first** and fits
> the journal's emphasis on reproducibility and transparently reported results, including
> negative ones: (1) a universal, composition-tunable sub-zero proton-transport transition
> established over **13 independent repeats**; (2) a **measured fabrication reproducibility
> floor**, with a leave-one-dataset-out demonstration that single-curve QC confidence cannot
> predict cross-pellet reproducibility (a clean negative result) and an isotonic calibrator
> that nonetheless cuts ECE 0.75→0.05; (3) a **structural-identifiability** result that
> formally bounds the mechanistic claims a transport-only agent may make; and (4) a real
> MOBO+LLM closed loop reported as an **honest null** — its top candidates differ by less than
> the reproducibility floor. All data, code and prospective registrations are openly available;
> no result is post-hoc reweighted. We believe this reproducibility-floor + identifiability-
> ceiling framing is broadly useful to the self-driving-lab community.

## 6. 出图规范(Digital Discovery,最终提交)

- 格式 **TIFF ≥ 600 dpi**(可先交 EPS/PDF);宽度 **单栏 8.3 cm / 双栏 17.1 cm**,高 ≤ 23.3 cm;字号清晰(≥7 pt)。
- TOC 图 8×4 cm。
- 数据图一律 matplotlib 真实数据导出;概念图(Fig 1)PPT/矢量精修。
- (npj 备选:初稿 300 dpi、单图 <2–3 MB 即可。)

## 7. 数据/代码可得性(草稿)

All processed stage0 outputs, analysis scripts and figures are in `_new_data_analysis/`
(`regularity/`, `repro_floor/`, `calibration/`, `identifiability/`, `replay/`). The Arrhenius
segmentation engine (`stage0_measurement/.../algorithms/arrhenius.py`: pwlf + AICc + Chow test)
and the closed-loop optimizer are open. Prospective Line-B recipes are git-timestamp-frozen
under `prospective_2026H2/` prior to synthesis.
