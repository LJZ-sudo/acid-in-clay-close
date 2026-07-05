# 预注册 · 线 A：生物聚合物–黏土迁移基元的前瞻验证

状态：`DRAFT_TO_FREEZE`（写好后按 `../README.md` 协议 commit + push，push 完成前不得开始合成）
预注册者：JZ
预注册日期：2026-06-08
硬化目标：Pillar 1（evidence-constrained transfer agent）+ Pillar 2（cooling-resilient descriptor）→ B+ 升 A

---

## 1. 冻结锚点（不可改）

本线**复用**已存在的权威冻结排名，不重新生成：

| 字段 | 值 |
|---|---|
| 来源文件 | `V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2/11_candidate_registry/prospective_candidates.json` |
| run_id | `stage3-1842d1f1ea` |
| registry_hash | `6bd73a12a53b7a6e7f6696c6687b7265ffbd518a90ce7537d72a30e18eacebde` |
| preregistered_at | `2026-06-07T11:57:12Z` |
| discovery_mode | `broad_literature_pool_selection` |
| LLM 设置 | `llm_mode=live`, `enable_cache=False`, `term_leakage_penalty=0`（未偷看生物聚合物实验结果） |
| 母体系来源 | S8 acid-in-clay（海泡石）证据 + 广义生物质/聚合物/黏土文献池 |

> 迁移叙事要点：排名是从**酸-黏土母体系**迁移、纯文献池选择得到的，与待验证的生物聚合物 EIS 结果**无因果泄漏**。这是"evidence-constrained transfer"的核心，也是审稿人最看重的一点。

## 2. 冻结排名（Top-5，逐字取自上述 registry）

| rank | instance_id | 候选 | score_before_experiment | 本线是否合成验证 |
|---|---|---|---|---|
| 1 | I1 | Starch / PVA / 有机改性凹凸棒土 / H₃PO₄ 膜（allowed_claim 指向 lotus-root-starch / LRS） | 0.8833 | ✅ 是（LRS + 玉米淀粉两支） |
| 2 | I2 | Chitosan / 有机改性凹凸棒土 / H₃PO₄ | 0.8233 | ✅ 是（CHITO） |
| 3 | I3 | Halloysite 纳米管 / H₃PO₄ / PVA | 0.8192 | ❌ 否（另一种黏土，列为未来工作） |
| 4 | I5 | PVA / chitosan / Nb₂O₅ / H₃PO₄ | 0.7381 | ❌ 否（未来工作） |
| 5 | I4 | PAAm-g-starch / H₃PO₄ 水凝胶 | 0.7078 | ❌ 否（未来工作） |

排名稳定性（取自同一快照 claim audit）：`top1_stability=1.0`，`top3_jaccard=1.0`，`ranking_stability_class=stable`。

## 3. 待合成样品矩阵（本线实际要做的实验）

| 样品代号 | 对应候选 | 角色 | 几何控制（关键） | 重复数 |
|---|---|---|---|---|
| LRS-thin | I1（starch 分支，LRS） | **正验证** | 薄膜带：目标厚度 0.02–0.03 cm | ≥3 |
| LRS-thick | I1（starch 分支，LRS） | **几何对照**（拆解厚度混淆） | 厚膜带：目标厚度 0.08–0.10 cm | ≥2 |
| CORN-starch | I1（starch 分支，玉米淀粉） | 淀粉支泛化对照 | 与 LRS-thin 同几何带 | ≥2 |
| CHITO | I2（chitosan） | **边界验证** | 与 LRS-thin 同几何带 | ≥2 |

> 几何对照（LRS-thin vs LRS-thick）是**设计层**消除"低 Eₐ 只因薄膜"质疑的唯一干净办法（见分析报告 Part B/C 的厚度混淆）。务必同批、同温序、同 manual-Rb QC 流程处理。

## 4. 预注册的可证伪预测（实验前写死，事后不得改）

阈值依据现有 acid-in-clay / 旧生物聚合物 screening 量级设定，全部为**预测**，失败即为真实负结果（可发表）。

### 4.1 LRS = 正验证（cooling-resilient）
判为"确认"需**同时**满足（在薄膜带、manual-Rb 通过的主窗口）：
- (a) 高温段 `Ea_high ≤ 0.06 eV`；
- (b) 冷却保持：`σ(253 K) / σ(273 K) ≥ 0.5`（273→253 K 衰减不超过 ~2×）；
- (c) 连续性：`σ` 在降到 `≤ 233 K` 时仍可测（`> 1×10⁻⁵ S/cm`）。

### 4.2 CHITO = 边界验证（non-resilient）
预测 CHITO 在**相同几何/QC**下**不满足** 4.1，且呈现以下**至少一项**冷尾失效特征：
- `σ(233 K)` 较 `σ(273 K)` 跌 `≥ 1` 个数量级；或
- 出现段不稳定 / mid-segment 表观 `Ea > 1 eV`（转变/失效指标，非正常跳跃势垒）。

### 4.3 玉米淀粉 = 淀粉支泛化
预测：淀粉支可工作（高温段电导与 LRS 同量级），但低温连续性可能早于 LRS 退化 → 用于检验"淀粉家族通用性 vs LRS 个体最优"。

### 4.4 几何对照（厚度混淆检验）
预测：LRS-thin 的 `Ea_high` 显著低于 LRS-thick。
- 若成立 → 论文须如实写"低 Eₐ 是**薄膜几何 + 家族**共同效应"，**不**声称材料内禀；
- 若 LRS-thick 也低 → 反而支持"家族内禀"更强主张。
两种结果都报告。

## 5. QC 与判定流程（绑定已有代码）

- 描述符与三 claim band 定义：`three_pillars/pillar2_descriptor_qc/descriptor_definition.md`
- 实现：`V1.0-qianduan-mainline/stage0_measurement/modules/closure/closure_features.py` + `modules/analysis/algorithms/arrhenius.py`
- 处理命令：
  ```bash
  cd V1.0-qianduan-mainline
  python -m code.stage0_processing.process_new_materials_stage0 --sample <id> --input data/新材料/<id>/
  python -m stage0_measurement.run_closure_offline --sample <id>
  ```
- **主文本定量 Eₐ 只允许取自 KK 干净的高温段窗口**；冷尾点（auto/manual Rb 不一致或 KK 警告）一律降到 Exploratory，只做定性连续性讨论。
- 每个 (sample, T) 点保留 manual Rb 与 auto Rb 及差异（`selected_rb_qc_v2.csv` 同口径）。

## 6. 结果绑定（append-only，不回改预测）

实验完成后：
1. 用 `V1.0-qianduan-mainline/stage3_mechanism/src/s8_stage3/agents/s13_validation_binder.py` 把 EIS 结果作为 validation link **追加**到 registry（不修改 S09/S10/S12 排名）；
2. 重跑 S14 `s14_claim_auditor`；
3. 因预注册锚 `2026-06-07` 早于本线实验，`prospective_validation` 这次为**原生 PASS（非重建）**。

## 7. 允许 / 禁止声称（与 S14 一致）

- ✅ 允许："LLM 从广义生物质/聚合物/黏土文献池**选择并重组**了该基元；候选在实验前被冻结（远端盖戳），随后由宽温 EIS 前瞻验证。"
- ✅ 允许（性能）："record-level / comparable to lowest reported barriers"（对照 `final_benchmark_table.csv`）。
- ❌ 禁止："LLM **独立发明/发现**了 LRS"；"world record / 全球最低 Eₐ"；"EIS 证明了机制"。

## 8. 留痕（push 后回填）

- [ ] 预注册 commit hash：`__________`
- [ ] push 时间（UTC）：`__________`
- [ ] 远端 URL / Zenodo DOI：`__________`
- [ ] 实验开始日期（须晚于 push）：`__________`
