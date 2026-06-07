# Changelog

本文档记录 `stage3_mechanism` 本轮（2026 年 4 月）推理迭代的关键决定与代码/提示词变更。
版本号按 **内部迭代轮次** 递增（非 SemVer），每个条目都写明"为什么改"而不仅仅是"改了什么"。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [2026-06-07c] Publication v2：切换到 OpenRouter，跨提供方稳健性验证

### Why（业务动因）

V1 publication 跑（`20260607_mixed_tier_publication`）虽成功，但暴露两个问题：(1) polo 中转的 `deepseek-v4-pro` 在 CHEAP tier 上不稳定，9/19 次 empty response（gateway retry 救回但浪费时间和 token）；(2) 跑完之后 polo 账户额度即被耗尽（剩余 `-¥7.61`），重跑 v2 时 s04 第一次 LLM 调用即 403 崩溃。同时需要验证：核心发现是否对 LLM 提供方鲁棒（不仅是对单个模型鲁棒）。

### What

1. **切换 LLM 提供方** polo → **OpenRouter**：
   - `STAGE3_API_BASE_URL`: `https://poloai.top/v1` → `https://openrouter.ai/api/v1`
   - `STAGE3_API_KEY`: 替换为 OpenRouter `sk-or-v1-...` key
   - `STAGE3_MODEL_CHEAP`: `deepseek-v4-pro` → `openai/gpt-5.2`（用户决策：v2 用 gpt-5.2 全面替代 deepseek）
   - `STAGE3_MODEL_STANDARD`: `gpt-5.2` → `openai/gpt-5.2`（加 `openai/` 前缀以匹配 OpenRouter 命名规范）
   - `STAGE3_MODEL_PREMIUM`: `gpt-5.4` → `openai/gpt-5.4`
2. **修复 `llm_gateway.py` smoke_chat()** `max_tokens=5` → `64`：gpt-5 系列内部 reasoning tokens 会先消耗 max_tokens 配额，5 不够，会被上游 OpenAI 拒为 400。
3. **备份策略**：保留 `.env.bak.20260607-pre-mixed-tier`（原始 polo all-deepseek 配置）、`.env.bak.20260607-v2-cheap-gpt52`（v2 polo 配置但额度不足未跑成）、`.env.bak.20260607-openrouter`（当前 OpenRouter 配置）三份快照。

### Outcomes

- **跑步性能**：5 分 37 秒（exit 0），比 V1 polo 跑（34 min）**快 6.1×**。
- **稳定性**：13/13 LLM 调用一次性成功，**零失败、零 retry**（V1 有 9 次失败）。
- **成本**：54,971 total tokens（V1 79,119，**降 31%**），估算 ≈ $0.35 / ¥2.5。
- **跨提供方稳健性验证通过**：
  - Top-1 候选 `Starch/PVA/organic-modified attapulgite/H₃PO₄` 在 V2/V1/OLD 三个版本中完全一致（分数 0.883/0.891/0.895，量级 < 1.5%）。
  - Top-2 候选 `Chitosan/organic-modified attapulgite/H₃PO₄` 三版本完全一致。
  - Top-5 候选集合三版本 **5/5 重叠**，仅 #3-#5 顺序略有不同。
  - ranking_robustness 三版本均 `stability_class=stable`。
- **路由完美按 STEP_TIER_MAP 工作**：3 次 gpt-5.4（s04/s06/s06b）、10 次 gpt-5.2（s05_lit/s07/s08_sum × 8）。

### Anchored authoritative snapshot

`outputs/verification/20260607_openrouter_publication_v2/` is now the canonical
publication-grade snapshot. V1 (`20260607_mixed_tier_publication/`) and OLD
(`20260526_final_audit_cacheoff_full/`) retained as cross-validation evidence.

---

## [2026-06-07b] Publication-grade run：混合 tier 路由 + STEP_TIER_MAP bug 修复

### Why（业务动因）

清理与哈希链修复完成后，需要做一次"权威 publication 级别"的真 LLM + 真文献跑，作为论文阶段的基线快照。审计历史 `20260526_final_audit_cacheoff_full/llm_cost_summary.json` 时确认：上轮 11 次 LLM 调用全部用 `deepseek-v4-pro`（三 tier 均为同一模型，per-step 分级路由被完全架空）。本轮恢复 STAGE3 设计的分层路由意图，让主推理链使用 `gpt-5.4`，描述符抽取使用 `gpt-5.2`，文献摘要保留 `deepseek-v4-pro`。

同时审计 `STEP_TIER_MAP` 时发现 3 个 key 命名 bug：代码里 `gateway.chat_json(step=...)` 实际传入的 step 名（`s05_literature_mechanism`、`s06b_design_principle_extractor`、`s08_summarize_batch`）与 `STEP_TIER_MAP` 里登记的 key（`s05_literature_scout_mechanism`、缺失、`s08_summarize`）不一致，导致这 3 个 step 一直走 `STEP_TIER_MAP.get(..., ModelTier.CHEAP)` 的 fallback 路径。fallback 的最终 tier 恰好是 CHEAP（设计意图也是 CHEAP），所以肉眼上没察觉，但路由是"对错巧合"，必须显式登记。

### What

1. **修复 `src/s8_stage3/config/model_registry.py` STEP_TIER_MAP**：补登 3 个真实 step 名：
   - `s05_literature_mechanism` → CHEAP（保留旧 `s05_literature_scout_mechanism` 作为 legacy alias）。
   - `s06b_design_principle_extractor` → PREMIUM（新增）。
   - `s08_summarize_batch` → CHEAP（保留旧 `s08_summarize` 作为 legacy alias）。
2. **修改 `.env`**：`STAGE3_MODEL_STANDARD` deepseek-v4-pro → `gpt-5.2`；`STAGE3_MODEL_PREMIUM` deepseek-v4-pro → `gpt-5.4`；`STAGE3_MODEL_CHEAP` 保持 `deepseek-v4-pro`。备份保留为 `.env.bak.20260607-pre-mixed-tier`。
3. **执行 publication 跑**（34 分 11 秒，exit 0）：
   - `python -m s8_stage3.orchestrator.run_stage3 --mode real --llm-mode live --literature-mode hybrid --stage2-output-dir stage2_statistics/exports --output-dir stage3_mechanism/outputs/verification/20260607_mixed_tier_publication`
   - 14 次成功调用 + 9 次 retry-recovered failure（全部集中在 polo 中转 deepseek-v4-pro 的 CHEAP tier）。`gpt-5.4` 和 `gpt-5.2` 零失败。
   - 总 token 79,119 (prompt 45,251 + completion 33,868)。

### Outcomes

- **Top-1 / Top-2 候选与 5/26 历史 audit 跑完全一致**（含 #2 完全相同的 0.844 分），证明结果对模型选择稳健。
- **Top-5 候选集合 4/5 一致**（仅 #3-#5 顺序略有变化），`ranking_robustness.stability_class=stable, top1_stability=0.995, top3_jaccard=0.81`。
- **gpt-5.4 在主推理链上速度大幅提升**：s06_mechanism_arbiter 由 509 s → 55 s (**9.3× 加速**)；s04_hypothesis_generator 由 153 s → 36 s (**4.3× 加速**)；输出 completion token 减少 60-70%（更紧凑）。
- 路由 sanity 验证通过：`s04 / s06 / s06b → gpt-5.4`、`s07 → gpt-5.2`、`s05_lit / s08_sum / paper_card_* → deepseek-v4-pro`。

### Caveats

- polo 中转的 deepseek-v4-pro 在 CHEAP tier 上稳定性一般（empty response / timeout 共 9 次），但 gateway 内置 retry + agent-level fallback 全部救回，未影响最终产物。如未来需更高稳定性，可考虑把 CHEAP 改为 `gpt-4o-mini` 或 `gpt-4.1-mini`（两者在 polo 端点已探针验证可用）。
- 本轮使用的 stage2 seed 为重跑后的 `4edbd136...`（与 5/26 的 `fe7f48cc...` 不同），所以下游分数有轻微差异 (top-1 0.895 → 0.891)，但量级 < 1%、排名不变。

---

## [2026-06-07] Tier-A 全量清理：根目录文档 + Stage2 哈希链 + 全 stage3 子目录

### Why（业务动因）

stage3_mechanism 根目录长期积累了若干"非运行入口"的设计/规划文档（`tinging.md`、`FUTURE_OPTIMIZATION.md`），与 SDL "本文件不是论文草稿、不是历史报告" 原则冲突。同时，`stage2_statistics/exports/MANIFEST.md` 记录的 `stage3_seed.json` SHA256 与文件实际哈希不一致（`3f68b832...` vs `fe7f48cc...`），破坏了 Stage2→Stage3 信息线的可重复性。进一步，stage3 各子目录积累了大量历史迭代废稿、orphan 代码、死工具、以及与 V2 合约脱钩的旧 cache/log，需要一次性扫荡。

### What

1. **删除**根目录历史文档：
   - `tinging.md`（24 KB 设计哲学便签，文件自标 "not a runnable entrypoint"，README/SDL/AGENTS 均未引用，内容已被 stage3-SDL.md 和代码实现取代）。
   - `FUTURE_OPTIMIZATION.md`（13 KB 后续优化方案，自标 "historical planning note"，绑定未来实验回流场景，当前主线收束阶段不再依赖）。
   - `.pytest_cache/`（pytest 缓存，重跑测试时自动重建）。
2. **新增**`stage3-SDL.md §1.1 "历史文档例外条款"`：明确根目录只允许保留 `CHANGELOG.md / README.md / AGENTS.md / stage3-SDL.md` 四份文档，禁止再增任何其他 `.md`。
3. **修复**`stage2_statistics/exports/MANIFEST.md` 哈希链：重跑 `main_agent.py`，更新 seed_id（`SEED-4d8b27dd` → `SEED-1ad04c55`）和 SHA256（`3f68b832...` → `4edbd136...`），并在 MANIFEST 加注"重跑 main_agent 后必须同步更新本文件 SHA256"的提示。

### What (Tier-A 子目录清理)

按"零风险"标准（0 callers / 已自标 legacy / 自动重建的 cache）执行以下 19 类删除：

| 类别 | 项目 | 备注 |
|---|---|---|
| **Caches & empty** | `src/s8_stage3/__pycache__/`, `tests/__pycache__/`, `tests/fixtures/`, `literature_workspace/05_evidence_rows/` | 自动重建或空目录 |
| **Orphan code** | `src/s8_stage3/preprocess/stage2_loader.py` (41 L), `sample_graph.py` (37 L), `segment_rebuilder.py` (87 L) | 0 callers；V2 合约前的 Stage3 本地预处理三件套，已被 `adapters/stage2_seed_adapter.py` 完全替代 |
| **Dead tools** | `scripts/export_advisor_pdf.py` (28 KB) + 空 `scripts/` 目录 | 输入 `stage3_report_advisor.md` 已被 L+D4 方案废弃，且 reportlab 不在 requirements.txt |
| **Stale logs** | `logs/llm_calls.jsonl` (400 KB), `logs/run_d2.log`, `logs/run_nolit.log`, `logs/archive/20260518_llm_calls_pre_convergence.jsonl` (538 KB) | mock 跑产物 / 已被 CHANGELOG 文字记录覆盖的历史 log |
| **outputs/ 历史废稿** | `outputs/archive/20260518_legacy_stage3_outputs/` (8.4 MB, pre-V2-contract 5 个旧产物), `verification/20260525_*_rerun{,2,3_filtered,4_filtered_b4}/` (跑挂的中间残骸), `verification/20260526_*_full` 5 个被 final 覆盖的迭代版, `verification/20260520_*` 3 个被 `_rerun` 覆盖的版本, `20260519_stability_s14_verify`, `20260518_post_optimization_s03_verify` | 共 ~14 MB |
| **data/ 历史快照** | `data/cache/archive/20260518_pre_convergence_cache/` (1.98 MB / 192 文件), `data/input/{data_profile,execution_plan,visualization_manifest}.json` (~5 KB) | cache MANIFEST 自标 "do not use"；3 个 json 无代码引用 |
| **Manifest 同步** | `outputs/MANIFEST.md`, `data/cache/MANIFEST.md`, `logs/MANIFEST.md` 全部更新以反映新结构 | |

### Acceptance

- 58/58 Stage2/Stage3 契约测试通过（含 pipeline_smoke、stage2_stage3_contracts、legacy_source_helpers 等）。
- `stage3_seed.json` 实际 SHA256 与 stage2 MANIFEST 记录一致 (`4edbd136...`)。
- 信息线核查报告确认：stage0→stage2→stage3 数据链路完整，无样品丢失、无哈希漂移。
- stage3 体量：`outputs/` 从 18.6 MB / 949 文件 减至 4.06 MB / 182 文件 (-78%)，`data/` 从 2.8 MB / 254 文件 减至 0.85 MB / 47 文件，根目录 -37 KB，src `preprocess/` 5 文件减至 3 文件。
- 总计释放 ~17 MB / ~900 文件 + 165 行 dead code。

### Tier-B 已执行项（[2026-06-07] 续）

紧接 Tier-A 后，按"低风险 + 逐项审议"模式完成以下 Tier-B 操作：

| 项 | 操作 | 体量 | 备注 |
|---|---|---|---|
| **B1** | 暂留 `data/input/s8_input.csv` | 456 KB | 与 stage2 同 sha256 的副本；删除需同步修剪 `input_resolver.py` 第 5 fallback。下轮决定 |
| **B2** | `data/input/s8_evidence_atlas.json` 迁移至 `data/input/archive/s8_evidence_atlas_20260413_48units.json` + README | 46 KB | V1 atlas 早期快照（48 单位，当前 stage2 atlas 已演化到 56 单位）；从 fallback 路径中移除但保留 reproducibility 凭证 |
| **B3** | 删除 `outputs/stage3_current_real_mock_20260518_215842/` | 0.6 MB | 已被 `verification/20260607_post_cleanup_smoke/` (新 seed, mock-mode) bit-identical 取代 |
| **B4** | 删除 `outputs/verification/20260518_*` 4 个 S03-only 快照 | 1.4 MB | 主线收束阶段的 S03 诊断快照，被 20260607 完整 13-step 跑覆盖 |
| **B5** | 删除 `outputs/verification/{20260519,20260520,20260525_rerun5_final}_*` 3 个旧 seed 单功能终版 | 1.4 MB | 全部被 `20260526_final_audit_cacheoff_full` (hybrid 全链终版) 与 `20260607_post_cleanup_smoke` (mock 基线) 共同覆盖 |

### Pipeline 回归验证

完成 Tier-A/B 后立即用新 seed `4edbd136...` 跑了完整 13-step pipeline (mock LLM + mock lit)，结果与历史 mock 基线对比：

- 新跑 Top-3：`High-amylose plant starch / PVA / H3PO4 / sepiolite` (0.82), `Crosslinked PAAm-g-starch / H3PO4` (0.79), `biomass-starch-A / PVA / H3PO4 / 1D-clay` (0.68)
- 旧 mock 基线 Top-3：完全一致（同名、同分数、同顺序）
- `ranking_stability_class=stable`, `top1_stability=1.0`, `top3_jaccard=1.0`

证明 Tier-A/B 清理对 pipeline 行为 0 扰动。

### outputs/ 最终结构

完成后 outputs/ 仅保留：
- `MANIFEST.md` (更新)
- `stage3/README.md` (默认输出占位)
- `verification/20260526_final_audit_cacheoff_full/` (L+D4 hybrid 全链终版，0.69 MB)
- `verification/20260607_post_cleanup_smoke/` (mock 基线，0.48 MB)

从清理前 18.6 MB / 949 文件 → 1.18 MB / 75 文件 (**-94%**)

### Tier-C/D 未执行项（待进一步决策）

- **Tier B (residual)**: `data/input/s8_input.csv` (456 KB) — 与 stage2 同 sha256 副本，下一轮决定是否删除 + 同步修剪 `input_resolver.py`。
- **Tier C**: `agents/s01_data_auditor.py` + `s02_segment_builder.py` + 配套 `tests/test_stage3_legacy_source_helpers.py` — legacy 但有测试保护，AGENTS.md 暂保留。
- **Tier D**: `literature_workspace/01_manual_inbox/` (118 MB) + `03_parsed_text/` (132 MB) — 大块 PDF 仓库，pipeline runtime 不必需但人类审稿/supplementary 需要。等论文定稿决定。

### Publication-grade 物证再生说明

当前两个保留快照都不是 "publication-grade"：
- `20260526_final_audit_cacheoff_full/` 是 hybrid 真跑，但 seed 已过期 (`fe7f48cc...`)
- `20260607_post_cleanup_smoke/` 是新 seed (`4edbd136...`)，但 mock 模式不产生论文级候选

如需"金标"物证，需以下两步骤之一：
1. 用当前 seed `4edbd136...` 跑一次完整 hybrid + live LLM（消耗真实 API 调用预算）
2. 用当前 seed `4edbd136...` 跑一次 hybrid + mock LLM（取真文献但 LLM 用 mock，半金标）

---

## [2026-04-20] 方案 L + D4 — 冷端重聚焦 + 组件×描述符×量化锚点三元组证据

### Why（业务动因）

方案 D2 把文献粒度从"整篇论文配方"降到"原子化组件"，已经把藕粉从 PAEK 路线解绑，但两个方法学问题仍未闭环：

1. **温度窗口错位**：S8 数据是 **182–299 K（室温到 −91 °C）冷端**，但先前 S07 描述符和 S10 的 `wide_temperature_potential` 评分项都隐式偏向"温度越宽越好"，导致 HT-PEM 原型（PBI / H₃PO₄、磷酸玻璃、PAEK > 80 °C）因"理论宽温性"仍能拿高分，甚至进入 Top-3。这与实验实际操作区间不一致。
2. **tinging.md 哲学只实现了一半**：D2 的 `component_evidence_pool` 只告诉 LLM "这篇论文里用到了 attapulgite"，并没有告诉它"这篇论文 **证明了** attapulgite **能做** D2（1-D 限域通道）、量化锚点是 35.3 mS/cm@80 °C"。S10 的 `evidence_support` 最终还是审计 S09 自己声明的 `descriptor_satisfied`——形成 LLM 自说自话的闭环。

### How（设计）

**方案 L（冷端重聚焦，最小侵入）**：

1. `prompts/s07_descriptor_extractor.md`：新增 *Experimental operating window* 段，显式写入 182–299 K 并要求至少一条描述符编码（a）结合水 / 增塑剂连续性、（b）基体力学与介电连续性、（c）酸冷端稳定性。明确惩罚泛化的"宽温稳定"短语。
2. `prompts/s09_family_generator.md`：新增 *cold-side-operation guidance (soft)* 段。鼓励：抗冻共溶剂（甘油、乙二醇、DES）、生物质结合水多糖主体、低 Tg 基体、带界面结合水的 1D/2D 黏土。劝退（但保留作对照）：PBI / H₃PO₄、> 80 °C PAEK、纯磷酸玻璃。自由 H₃PO₄ 必须在 `risk_flags` 里注明抗结晶策略。
3. `prompts/s10_instance_ranker.md`：`wide_temperature_potential` → `cold_to_room_T_robustness`，重写为 4 个子项的合取（结合水连续性 / 200 K 力学连续性 / 酸冷端稳定性 / 182–299 K 量化锚点）。没有明示冷端策略的 HT-PEM 原型上限 0.4 分。
4. `llm/prompt_packing.py`：`pack_for_s09` / `pack_for_s10` 新增 `system_context` 透传（`temperature_window_K`, `chemistry_summary`, `key_variables`）；orchestrator / S09 / S10 agent 签名同步。

**方案 D4（组件×描述符×量化锚点三元组证据）**：

1. **合约层**：`src/s8_stage3/contracts/literature.py` 新增 `ComponentDescriptorClaim(component, descriptor_ids, quantitative_anchor, claim_text, confidence)`；`LiteratureCard` 新增 `component_descriptor_claims: list[ComponentDescriptorClaim]`。
2. **S08 prompt**：`prompts/s08_literature_materials.md` 重写为两段产出——`synthesis_notes`（族级）+ `component_descriptor_claims_by_card[card_id]`（按卡片 × 组件 × 描述符列出 claim，强制量化锚点带温度上下文）。
3. **S08 agent**：`agents/s08_literature_scout_materials.py` 的 `_summarize_with_llm` 改为同时解析 `synthesis_notes` 与 `claims_by_card`；`run_s08` 把 claims 挂回 `LiteratureCard.component_descriptor_claims`；包含对未知 `descriptor_ids` 的过滤。
4. **打包层**：`pack_for_s09` 把 `descriptor_claim_pool = flatten(所有 card 的 claims)` 作为 **Primary input**，`component_evidence_pool`（D2）和 `raw_cards_fallback` 降级为兜底；`usage_note` 明示"一条 claim 只绑定它自己的 (component, descriptor, anchor)，不绑定该 paper 的完整配方上下文"。
5. **S09 prompt**：每条 `element_evidence[i].descriptor_satisfied` 必须有 `descriptor_claim_pool` 里至少一条匹配 claim 背书（相同 component 或近邻 analog + 相同 descriptor_id），并把背书 paper_id 写入 `analog_paper_ids`；没有背书的必须显式写"no S08 analog; inferred from public physicochemical knowledge"。
6. **S10 `evidence_support` → 独立审计覆盖率**：S10 拿到 `descriptor_claim_pool` 后直接审计 S09 声明的 (component, descriptor) 配对在 pool 里是否有 claim；同组件全分、跨组件类比半分、无 claim 0 分。这把"LLM 自说自话"彻底打断。
7. **Mock + tests**：`mock/mock_llm.py::_mock_s08` 为每张卡加 `component_descriptor_claims`，`_mock_s07` 描述符重写为冷端导向，`_mock_s10` 把 criterion id 换名；`tests/test_contracts.py` 新增 `ComponentDescriptorClaim` 合约测试。

### 本轮重跑结果（L + D4 主榜单 Top-6）

| 名次 | 配方 | 组合类型 | 总分 | cold_to_room_T | evidence_support |
|:---:|---|:---:|:---:|:---:|:---:|
| **1** | **藕粉 / PVA / 凹凸棒 / H₃PO₄ / 甘油** 五元膜 | **novel** | **0.826** | 0.82 | 0.90 |
| 2 | 壳聚糖 / PVA / halloysite / H₃PO₄ / 乙二醇 | novel | 0.785 | 0.80 | 0.78 |
| 3 | 藕粉 / 壳聚糖 / H₃PO₄ / 甘油 | novel | 0.747 | 0.84 | 0.75 |
| 4 | PAAm-g-淀粉 + H₃PO₄ + 甘油 水凝胶 | close_variant | 0.723 | 0.76 | 0.70 |
| 5 | PVA / 磷酸玻璃微粒 / 甘油 | novel | 0.617 | 0.38 | 0.80 |
| 6 | PBI / H₃PO₄-loaded halloysite（HT-PEM 对照） | exact_match | 0.613 | **0.32** | 0.96 |

### 本轮重跑结果的关键变化 vs D2

- **tinging.md 目标配方 `藕粉 + PVA + 凹凸棒 + H₃PO₄`（+甘油以覆盖 D1/D5）**直接升为 Rank 1，来自 4 篇不同论文的原子 claim 自由重组，不是文献里的现成配方；
- HT-PEM 原型（PBI / H₃PO₄ / halloysite）正确定位为 Rank 6 `exact_match` 对照：`evidence_support = 0.96`（文献密集）、`cold_to_room_T_robustness = 0.32`（冷端不友好）——与 S8 实验语境一致；
- 本轮 S08 从 19 张卡中抽出 **23 条 `ComponentDescriptorClaim`**（10 / 19 张卡有结构化证据），0 条因 `descriptor_ids` 非法被丢弃；
- 整条 pipeline 的"自说自话"断开：S10 对 S09 的五条 (component, descriptor) 声明独立审计出 5/5 背书，未背书的 glycerol ↔ D1/D5 被显式标注为"prior-knowledge inference"。

### 方法学结论（一句话）

> **anchor bias 的彻底解法不是"把组件拆出来"，而是"把 (component × descriptor × quantitative_anchor) 拆出来"。** D2 让藕粉从 PAEK 中走出来，D4 让 S10 能独立审计藕粉满足 D4 这件事本身；L 确保这场审计发生在 182–299 K 而不是 > 80 °C 的想象空间里。

### Changed

- `src/s8_stage3/contracts/literature.py`: 新增 `ComponentDescriptorClaim`；`LiteratureCard.component_descriptor_claims`。
- `src/s8_stage3/prompts/s07_descriptor_extractor.md`: 冷端操作窗口段（L）。
- `src/s8_stage3/prompts/s08_literature_materials.md`: 全文重写为"synthesis + claims"双产出（D4 + L 温度锚点要求）。
- `src/s8_stage3/prompts/s09_family_generator.md`: cold-side-operation guidance（L）+ `descriptor_satisfied` 必须有 claim 背书（D4）。
- `src/s8_stage3/prompts/s10_instance_ranker.md`: `cold_to_room_T_robustness`（L）+ `evidence_support` 独立审计覆盖率（D4）+ `ranking_rationale` 强制提及冷端分数。
- `src/s8_stage3/llm/prompt_packing.py`: `pack_for_s09` / `pack_for_s10` 新增 `descriptor_claim_pool` 与 `system_context` 透传。
- `src/s8_stage3/agents/s08_literature_scout_materials.py`: `_summarize_with_llm` 同时解析 synthesis + claims。
- `src/s8_stage3/agents/s09_candidate_family_generator.py`, `s10_instance_ranker.py`, `orchestrator/pipeline.py`: 签名透传 `system_context`。
- `src/s8_stage3/mock/mock_llm.py`: `_mock_s07/s08/s10` 同步 L + D4。
- `tests/test_contracts.py`: 新增 `ComponentDescriptorClaim` 合约测试；`LiteratureCard.component_descriptor_claims` 默认空列表断言。
- `outputs/stage3/10_reports/stage3_report_advisor.md` & `stage3_report_advisor_EN.md`: 论文式重写，Abstract / Methods / Results / Discussion / Appendices 完整结构，中英双版；`scripts/export_advisor_pdf.py` 新增 CLI 参数支持双语 PDF 出版。
- 旧 `outputs/stage3/` 归档至 `outputs/stage3_preLD4_20260420_094753/` 以便回溯对照。

### Cost

1 次 S04→S11 完整重跑（premium tier · GPT-5.4，~10 min；8 次 LLM 调用，2 次缓存命中，70 763 tokens），途中遇到 4 次 403 quota 瞬时错误均自动重试成功，0 步失败。代码改动约 7 个源文件 + 4 个 prompt + 1 个测试文件 + 1 个出版脚本，净增约 320 行；报告产出两份 MD + 两份 PDF。

---

## [2026-04-20] 方案 D2 — 描述符驱动的组件证据池 · 拆解文献 anchor bias

### Why（业务动因）

方案 D3 的对照实验确认了文献输入的双重作用：**正面是可审计性与具体性，负面是把 LLM 推理拉进某篇论文的完整配方骨架**。最典型的症状是"藕粉"只有一篇 S08 anchor 论文（PAEK 体系），结果藕粉被锁在 Rank 4 的 PAEK 路线上，而 `tinging.md` 设想的 **藕粉 + PVA + 1-D 黏土 + H₃PO₄** 水基路线完全浮不出水面。D3 只是**诊断**并把这一局限写进报告附录 B/C；D2 要做的是**闭环修复**：用正确的粒度喂文献，既保留 anchor 的审计价值，又解锁跨论文重组的组合自由度。

### How（设计）

把 S08 → S09 的输入从"每篇论文的完整配方说明"重构为**原子化后的描述符级组件证据池**：

1. **合约层**：在 `src/s8_stage3/contracts/material.py::ElementEvidence` 新增 `descriptor_satisfied: list[str]` 字段（带 `field_validator` 兼容字符串/列表输入），显式声明每个组分满足哪些机理描述符。
2. **打包层**：`src/s8_stage3/llm/prompt_packing.py::pack_for_s09` 完全重写——
   - 新增 `_atomize_components()`：用正则从每条 `LiteratureCard.summary` 中抽取 `Substance:` 行和 tail region，切分、去噪（`composite membranes / proton exchange membranes / films / …`）、去重，得到单个组件列表。
   - 新 S09 输入结构：`descriptors + component_evidence_pool (扁平化的 {component, paper_id, paper_descriptor_axes, short_title} 清单) + raw_cards_fallback (原子化失败的卡片兜底) + usage_note`。
   - `usage_note` 中显式声明："共现在同一 `paper_id` 下的组件并不要求共同使用——你可以自由地把它们与其他论文的组件重新组合。"
3. **Prompt 层**：
   - `src/s8_stage3/prompts/s09_family_generator.md`：输入说明段重写，要求 LLM 使用组件池自由重组，`element_evidence` 示例更新为带 `descriptor_satisfied` 字段。
   - `src/s8_stage3/prompts/s10_instance_ranker.md`：`evidence_support` 评分标准从"paper_id 数量"改为"**描述符覆盖比例** = `covered_descriptors / required_descriptors`"，其中 `covered_descriptors` 通过 `element_evidence.descriptor_satisfied` 的并集得到。
4. **Mock + tests**：同步更新 `src/s8_stage3/mock/mock_llm.py::_mock_s09`（I1/I2/I3 加 `descriptor_satisfied`）与 `tests/test_contracts.py`（新增 `ElementEvidence.descriptor_satisfied` 合约测试 + field_validator 行为测试）。

### 结果（D2 主榜单 Top-7）

| 名次 | 配方 | 组合类型 | 分数 |
|---|---|:---:|:---:|
| 1 | 壳聚糖 (蟹壳) / PVA / 凹凸棒 / H₃PO₄ | novel | 0.876 |
| 2 | PAEK / 淀粉 / halloysite / H₃PO₄ | novel | 0.834 |
| **3** | **藕粉 (美人红) / PVA / halloysite / H₃PO₄** | **novel** | **0.825** |
| 4 | PAAm-g-淀粉 / 壳聚糖 / H₃PO₄ 水凝胶膜 | novel | 0.823 |
| 5 | PBI / H₃PO₄ / 凹凸棒 | close | 0.802 |
| 6 | 藕粉 (美人红) / 壳聚糖 / H₃PO₄ / 甘油 | novel | 0.754 |
| 7 | 磷酸玻璃 NbO/BaO/LaO/GeO₂/B₂O₃ | exact | 0.606 |

### D2 相较方案 B 的实际改变

- **藕粉路线从 Rank 4（绑 PAEK）上升为 Rank 3（解绑，走 PVA / halloysite 水基路线）**——这正是 `tinging.md` 的视觉方向（halloysite 与 `tinging.md` 的 attapulgite 同属 1-D 纤维/管状黏土，机理等价）。
- `novel_combination` 计数从 4 提升到 5（Top-7 里 5 条新组合）。
- Rank 6 出现**纯生物质 + 甘油**的"最简单工艺"路线（藕粉 + 壳聚糖 + H₃PO₄ + 甘油），为实验提供了一条极低门槛的对照。
- Rank 1 完全没变——证明"壳聚糖 + PVA + 凹凸棒 + H₃PO₄"确实是 S8 邻域的共识主干，不是 anchor 带来的错觉。

### 方法学结论（一句话）

> **anchor bias 的根源不是"文献不该喂"，而是"文献喂的粒度错了"。** 按"整篇论文配方"喂，LLM 默认共现即共同使用；按"描述符级组件"喂，LLM 既保留 element-level 审计锚点，又解锁跨论文重组的组合自由度。

### Changed

- `src/s8_stage3/contracts/material.py`：`ElementEvidence` 新增 `descriptor_satisfied: list[str]` + field_validator。
- `src/s8_stage3/llm/prompt_packing.py`：新增 `_atomize_components / _clean_component / _SUBSTANCE_PATTERN / _NOISE_TOKENS`；`pack_for_s09` 完全重写。
- `src/s8_stage3/prompts/s09_family_generator.md`：输入段说明 + `element_evidence` 示例重写。
- `src/s8_stage3/prompts/s10_instance_ranker.md`：`evidence_support` 评分规则重写为 descriptor coverage。
- `src/s8_stage3/mock/mock_llm.py`：`_mock_s09` 同步加 `descriptor_satisfied`。
- `tests/test_contracts.py`：合约测试同步 + 新增 descriptor_satisfied validator 专用测试。
- `outputs/stage3/10_reports/stage3_report_advisor.md / .pdf`：主榜 Top 5 → Top 7，设计哲学、§4 全部 Rank、§5 实验路径、§7 文献支撑说明、附录 C 全部改写为 D2 叙事。

### Cost

1 次 S04→S11 完整重跑（premium tier，~8 min）；代码改动约 4 个源文件 + 2 个 prompt + 2 个测试文件，净增约 180 行。

---

## [2026-04-19] 方案 D3 — 有/无材料文献对照实验 · 系统能力边界自检

### Why（业务动因）

方案 B 实装后，Top-4 全部成为 novel_combination，藕粉进入 Rank 4。但评审会问一个方法学层面的质疑：**你给系统喂的文献有没有把 LLM 的推理带偏？** 换言之，我们需要分清"文献给系统注入了创造力"（则文献是拐杖）与"文献给系统锚定了具体性和审计性"（则文献是证据本身）这两种截然不同的作用模式。

### How

保持 S04/S05（机理证据+机理文献）不变，只把 S08 材料文献关掉（`--literature-mode mock`），其余 pipeline 一致。得到一份 LLM prior-only 的对照 Top-list，与主榜单并排对比。

### 结果（对照 Top-5）

| 名次 | 主榜单（有材料文献） | 对照榜单（无材料文献） |
|---|---|---|
| 1 | 壳聚糖(蟹壳)/PVA/凹凸棒/H₃PO₄ | **高直链玉米淀粉/凹凸棒/H₃PO₄** |
| 2 | 壳聚糖(蟹壳)/halloysite/H₃PO₄ | 高直链玉米淀粉/壳聚糖/凹凸棒/H₃PO₄ |
| 3 | PAAm-g-淀粉/Nb₂O₅/H₃PO₄ | 甘薯淀粉/CMC-Na/凹凸棒/H₃PO₄ |
| 4 | **PAEK/藕粉(美人红)/halloysite/H₃PO₄** | 甘薯淀粉/凹凸棒/H₃PO₄ |
| 5 | PVA/PEG/MMT/H₃PO₄ | **PVA/凹凸棒/H₃PO₄** |

两边的 `combination_novelty` 分布完全一致（4 novel / 1 close / 1 exact），但具体配方差异显著。

### 三条关键发现

1. **LLM prior 相当对路**：无文献模式 Top-4 全部落在"淀粉 + 凹凸棒 + H₃PO₄"骨架，与 tinging.md 直觉方案 5/5 骨架里有 3 条重合。GPT-5.4 对"H₃PO₄ + 一维黏土 + 富羟基生物质"这一共识起点掌握得很稳。
2. **文献的角色是具体性 + 可审计性，不是创造力**：有文献时"藕粉（美人红品种，Nelumbo nucifera）"这种品种级别的具体性、以及"相较 manual_1190463586 把磷钨酸换成游离 H₃PO₄"这种可证伪的 novelty claim 才成立；无文献时只能退化为"high-amylose maize starch"、"relative to MAT2（空占位符）"这种不可回溯的表述。
3. **有文献的代价是 anchor bias**：藕粉在 S08 里仅一篇 anchor 论文（PAEK 体系），导致 LLM 把藕粉黏在了 PAEK 骨架上（Rank 4）。而无文献模式下"生物质 + 凹凸棒 + H₃PO₄"骨架反而自然浮现（只是藕粉具体物种无法被点名）。这是方案 D2 要解决的问题。

### 方法学结论（已写入报告附录 B）

> 本系统的核心价值不是"从零凭空造新材料"（GPT-5.4 的先验已经能给出合理方向），而是把 LLM 的推理**锚定到具体、可引用、可审计的本土文献证据上**。**文献不是拐杖，是证据本身**。

### Added

- 对照实验完整输出：`outputs/stage3_noLit/`（与主榜单 `outputs/stage3/` 同级）。
- `stage3_report_advisor.md / .pdf` 追加**附录 B（系统能力边界的自我校验）**与**附录 C（已识别的改进方向：方案 D2 描述符驱动证据形态）**。

### Cost

1 次 S04→S11 完整重跑（~7 min，premium tier），零代码改动。

---

## [2026-04-19] 方案 B — 重构 evidence 模型为"组合新颖度 + element-level 证据"

### Why（业务动因）
上一轮（2026-04-15 收尾轮）虽然把藕粉推到 Rank 2，但仔细审视 Top-5 会发现：**除 Rank 2 之外其他候选几乎都是某篇文献配方的原样复制**。这违背"从机理推导新材料"的初衷——系统输出的应该是**已知组分的新组合**，而不是检索出来的现成配方。根因分析指向三个层面的放大效应：

1. **`evidence_tier` 二分法过于粗糙**：`literature_backed` 的定义是"具体物种有 ≥1 篇文献支撑"，这在 LLM 视角下就是"照抄文献"；`mechanism_analog` 要求 4 段长推理链，实际被 LLM 用作"例外出口"，只产出 1 条。
2. **硬约束"至少 2 条 literature_backed"**：直接逼迫 Top-list 里 ≥ 40 % 是已有配方。
3. **S10 打分里 `s8_proximity` 权重 0.8 过高**：奖励靠近母体系，而"靠近母体系"在实践中意味着靠近现有文献。

### How（关键决定）
全面重构证据模型，参考 `tinging.md` 的"element-level evidence with combination-level novelty"哲学：

- **废弃** `evidence_tier` 二分法。
- **引入** `combination_novelty` 三档：`novel_combination`（整条配方非任一文献报道，主体）/ `close_variant`（差 ≤ 1 组分）/ `exact_match`（文献完全一致，仅作对照基线）。
- **引入** `element_evidence`：逐组分记录"该组分由哪些 S08 论文形成 element-level 类比"，`literature_support_card_ids` 变为派生字段（所有 element_evidence 里 paper_id 的去重并集）。
- **硬约束变向**：≥ 5 条 instance 中至少 3 条 `novel_combination`，至多 1 条 `exact_match`。
- **打分变向**：S10 新增 `combination_novelty` 维度（权重 1.2）并把 `s8_proximity` 权重从 0.8 降到 0.3，让"组合新颖性"真正成为奖励维度。
- **`novelty_rationale` 强制所有 instance 都填**（包括 exact_match，解释为什么它作为对照基线值得保留）。

### Schema / Contract
- `src/s8_stage3/contracts/material.py`：删除 `EvidenceTier`；新增 `CombinationNovelty` 与 `ElementEvidence`；`MaterialInstance` 添加 `components` / `combination_novelty` / `element_evidence`；增加 `@model_validator` 从 `element_evidence` 自动派生 `literature_support_card_ids`。
- `src/s8_stage3/contracts/ranking.py`：`RankedCandidate.evidence_tier` → `combination_novelty`。

### Prompts
- `src/s8_stage3/prompts/s09_family_generator.md`：加入"Design philosophy"段（新材料 = 已知组分的新组合）；把"Evidence tiering"章节整体替换为"Element-level evidence vs combination-level novelty"；更新硬约束（novel_combination ≥ 3、exact_match ≤ 1）；更新 JSON 输出模板。
- `src/s8_stage3/prompts/s10_instance_ranker.md`：criterion 6 由"tier-aware scoring"改为"element-level literature coverage"；新增 criterion 11 `combination_novelty`（权重 1.2）；`s8_proximity` 权重 0.8 → 0.3。
- `src/s8_stage3/prompts/s11_report_compiler.md`：明确禁止 `literature_backed` / `mechanism_analog` / `evidence_tier` / "Innovation candidate" 等术语出现在 advisor-facing 正文；指示把 `exact_match` 自然描述为"control baseline route"。

### Agent 代码
- `src/s8_stage3/agents/s09_candidate_family_generator.py`：软重试提示改为引导更多 `novel_combination`；审计块从按 tier 分别校验改为统一校验（`novelty_rationale ≥ 120 char`、`element_evidence` 非空、paper_id 在池内），并统计 novelty 分布。
- `src/s8_stage3/agents/s10_instance_ranker.py`：从 S09 承袭 `combination_novelty` 而非 `evidence_tier`，并记录排名后的 novelty 分布。
- `src/s8_stage3/agents/s11_report_compiler.py`：`top_candidates_summary` 兜底逻辑里，把"主榜单外的 `mechanism_analog` 追加"改为"主榜单外的 `novel_combination` 追加"；去掉 Markdown 输出里的 tier 标签和"Innovation candidate"分支。
- `src/s8_stage3/agents/s08_literature_scout_materials.py`：注释改为"component-level analog evidence"措辞。

### Prompt packing / Mock
- `src/s8_stage3/llm/prompt_packing.py`：`pack_for_s10` 透传 `combination_novelty` + `element_evidence` + `components`；`pack_for_s11` 的 `analog_extras` → `novel_extras`，并更新配套日志字段名。
- `src/s8_stage3/mock/mock_llm.py`：三条 mock instance 改用 `combination_novelty` + `element_evidence`；Rank 1 示范 `novel_combination`（淀粉 + PVA + 海泡石 + H₃PO₄）、Rank 2 示范 `exact_match` control baseline、Rank 3 示范 `novel_combination`（藕粉 + PVA + 凹凸棒 + H₃PO₄）。

### 测试
- `tests/test_contracts.py`：`test_material_contract` 改用新 schema，覆盖 `exact_match` 承袭派生 paper_id 与 `novel_combination` 四组分的 element_evidence 去重合并。
- `tests/test_ranker_constraints.py`：`test_mock_ranking_tiered_evidence` → `test_mock_ranking_combination_novelty`，强制所有候选的 `novelty_rationale` ≥ 120 char。
- 回归：87 / 87 测试通过。

### 本轮端到端结果（live, `gpt-5.4` premium）
- **S09 输出**：6 instance，novelty 分布 **novel_combination=4, close_variant=1, exact_match=1**。正是硬约束想要的分布。
- **S10 Top-list**：
  - `#1 (0.834)` 壳聚糖(蟹壳) + PVA + 凹凸棒 + H₃PO₄ — novel_combination
  - `#2 (0.823)` 壳聚糖(蟹壳) + halloysite + H₃PO₄ — novel_combination
  - `#3 (0.763)` PAAm-g-淀粉水凝胶 + Nb₂O₅ + H₃PO₄ — novel_combination
  - `#4 (0.757)` PAEK + **藕粉(Meirenhong)** + halloysite + H₃PO₄ — novel_combination
  - `#5 (0.733)` PVA/PEG + MMT + H₃PO₄ — close_variant（"加游离磷酸"的近似变体）
  - `#6 (0.499)` 低熔点磷酸玻璃 — exact_match（文献对照基线，分数被 combination_novelty 权重压低到 0.5 附近，符合预期）

### 文献变化
- `literature_workspace/01_manual_inbox/s08_materials/` 新增 4 个 PDF（Li 2024 starch / Qin 2014 PA-3D / Jadav 2016 PVA+MMT+H3PO4 / 其他）。
- 新增 paper card：`manual_8d58a81c9e_1_card.json`（"Li 2024 H₃PO₄-retention proton channel starch" 的变体条目，relevance 0.8）。
- 证据行重建：mechanism 106 行、materials 123 行；context packs 重建 5 个。

### 报告
- 重写 `outputs/stage3/10_reports/stage3_report_advisor.md` 以反映新 Top-list；去掉所有"证据层 / literature_backed / mechanism_analog"表述；突出"Top-4 全是新组合路线"的事实；实验路径建议改为"首选 Rank 1（主力）+ Rank 2（机理验证）+ Rank 4（生物质特色 / 藕粉）并行"；重导出 PDF。

---

## [2026-04-15] 本轮收官 — 分享版 + 归档

### Added
- **`outputs/stage3/10_reports/stage3_report_advisor.md` / `.pdf`**
  - 面向导师分享的 **中文精炼版**：一页总结 + 关键事实表 + 机理图像 + Top-5 候选卡 + 实验路径 + 风险声明 + 文献清单。
  - 原英文学术版 `stage3_report.md` 保留为 LLM 产出的原始证据。
- **`scripts/export_advisor_pdf.py`**
  - 基于 ReportLab 4.x 的 Markdown→PDF 渲染器。支持 ATX 标题、段落、粗体 / 斜体 / 行内代码、GitHub-style pipe 表格、无序列表、引用块、分割线。
  - **化学式自动上下标**：Unicode 下标 / 上标字符（₀-₉ / ² / ³ / ₐ / ⁻ / 等）在渲染阶段统一转成 `<sub>` / `<super>` 标签，解决 msyh 等中文字体缺少这些 glyph 的问题（H₃PO₄ / Nb₂O₅ / R² / 10⁻³⁰ 等均能正确渲染）。
  - **视觉设计**：深靛墨绿配色（slate-900 主色 / teal-700 强调）；章节标题左侧带短色条；Top-5 候选材料用"徽章 + 标题"卡片样式（Rank 1 金、Rank 2 绿、Rank 3–5 灰）；表格深绿表头 + 浅灰斑马纹；引用块左粗色条 + 浅绿背景；页脚简洁分割线。
  - 中文字体：微软雅黑（`msyh.ttc`） + 粗体（`msyhbd.ttc`，回退到 `simhei.ttf`） + 等宽 Consolas。
  - 用法：在 `stage3_mechanism/` 下执行 `python scripts/export_advisor_pdf.py`。
- **`CHANGELOG.md`**（本文件）

### Changed — Advisor report content
- 去掉 Top-5 表格中的 **"证据层"** 列（原本列出 `literature_backed` / `mechanism_analog` 的分类标签）。
- 每条 Rank 候选的详情段不再出现 `Evidence tier`、`Innovation candidate`、`literature_backed`、`mechanism_analog` 等技术术语；Rank 2 的"创新"属性通过自然语言（"★ 本轮新提出的实验方案"、"在现有公开文献中暂无完全相同的报道——这正是其实验价值所在"）表达。
- 文献支撑清单去掉 `manual_xxxx` 风格的技术 ID，只保留"文献主题 / 支撑对象 / 相关度"三列可读列；完整 ID 与 paper card 在仓库里的 `literature_workspace/` 仍可随时回溯。
- 封面副标题改为 **"给导师的分享版 · Advisor Edition"**（原先重复了标题正文，属于冗余）。

### Cleaned up
- 删除 `intput/`（拼写错误的空目录重复项）、`data/literature_workspace/`、`literature_workspace/05_evidence_rows/`、`.pytest_cache/`、老调试日志 `logs/run_lotus_round2.log` / `run_lotus_round3.log`。
- 合并 `requirements-stage3.txt` → `requirements.txt`（单一依赖清单），并删除前者。
- 保留 `data/cache/`、`logs/llm_calls.jsonl`（LLM 审计轨迹）、`literature_workspace/01–04/`（原始 PDF、解析文本、paper cards）、所有设计文档。

---

## [2026-04-15] V2 机理 + 创新材料组合（收尾轮）

### 核心业务决定
- **Top-2 升级为"藕粉+PVA+H₃PO₄+Nb₂O₅"**（起初位列 Rank 7）。
- **机理写成"双水群受限网络 + 阶梯式传输转换"**，明确接受 `T_arc ≠ T_break` 且明确解释 EIS 从室温直线到低温"半圆+直线"的演化。
- **验收标准**：Top list ≥ 5 条、至少一条 `mechanism_analog` 创新项进前 5、S06 必须对 EIS 演化给出物理解释。

### Changed — Prompts

- `src/s8_stage3/prompts/s06_mechanism_arbiter.md`
  - 新增"EIS 形貌温度演化解释"的强制任务点（必须在 (a) 弛豫时间、(b) 慢过程涌现、(c) 结构/组分变化 之间给出归因）。
  - 新增"General reasoning heuristics"与"Required `why_not` self-critique"两段软约束段落（**拒绝硬约束形式**，避免把 `T_arc/T_break ≥ 50 K → 两网络` 写死）。
- `src/s8_stage3/prompts/s09_family_generator.md`
  - 家族数 `2–4` → **`3–5`**；总 instance 数 **≥ 5**（硬要求写法，但是数量性硬约束，非机理性硬约束）。
  - 要求至少 2 条 `literature_backed` 且 **至少 1 条 `mechanism_analog`**。
  - 新增 **"Synergistic / hybrid-archetype encouragement"** 软引导段：显式鼓励当描述符同时要求多种互补角色时合成为同一 family（OH-rich 生物聚合物 + 成膜聚合物 + 1-D 黏土 + 自由酸）。此改动直接把"藕粉+PVA+Nb₂O₅"推到 Rank 2。
  - 家族设计指引（跨聚合物骨架/无机相/酸集成方式/生物质）+ 实验可行性指引（优先水基、商品级试剂）。
- `src/s8_stage3/prompts/s10_instance_ranker.md`
  - 排序准则由 7 维扩展到 **10 维**，新增 `s8_proximity`、`experimental_feasibility`、`biomass_accessibility`。
- `src/s8_stage3/prompts/s11_report_compiler.md`
  - Section 2 明确要求包含 `mechanism_label` / `mechanism_justification` / T_arc–T_break 解释 / 独立段的 **EIS morphology evolution**。
  - 输入从"ranker 输出"切换为 `top_candidates`（流水线侧已保障其包含 top-K + analog extras）。

### Changed — Contracts & Agents

- `src/s8_stage3/contracts/mechanism.py`
  - `MechanismCard` 新增 `eis_evolution_explanation: str`、`why_not: list[str]` 字段。
- `src/s8_stage3/agents/s06_mechanism_arbiter.py`
  - `mc_keys` 同步扩展。
- `src/s8_stage3/agents/s09_candidate_family_generator.py`
  - **新增软重试（soft retry）机制**：若首次 LLM 输出 instances 数 < `MIN_INSTANCES=5`，自动再请求 1 次并附加"please add more instances"的指令。历史上 ~30% 首次调用都欠量，此机制无损补齐。
- `src/s8_stage3/agents/s11_report_compiler.py`
  - **修复截断 bug**：原先 `ranking.ranked_candidates[:5]` 在打包之前就丢掉了所有排名 ≥ 6 的候选，导致 `mechanism_analog` 创新项在高竞争轮里永远进不了 Top list。修复后传入完整 ranking，由 `pack_for_s11` 基于 `top-K + analog extras` 规则筛选。
  - 新增 `_build_top_candidates_summary(...)` 确定性地从 ranking 重建 `report.top_candidates_summary`（不再依赖 LLM 记住全部 id，避免幻觉 id）。
  - Markdown 输出中对 `mechanism_analog` 候选明确标注 "Innovation candidate" 并附 `novelty_rationale` 摘录。
- `src/s8_stage3/llm/prompt_packing.py`
  - `pack_for_s11` 现在同时注入：top-K（默认 5）候选 + 所有不在 top-K 中的 `mechanism_analog` 额外候选 + `mechanism_justification` + `t_arc_t_break_explanation` + `eis_evolution_explanation` + `mechanism_caveats`。
- `src/s8_stage3/mock/mock_llm.py`
  - `_mock_s06` 补全 `eis_evolution_explanation` 与 `why_not` 字段以匹配新 Contract。

### Changed — Model Routing

- `.env`：`STAGE3_MODEL_TIER=` 留空（让 step-tier 路由生效，而不是被全局覆盖为 `cheap`）。
- `.env`：`STAGE3_OPENALEX_MAILTO` / `STAGE3_CROSSREF_MAILTO` → `liujinzhen72@gmail.com`（启用 polite pool）。
- `src/s8_stage3/config/model_registry.py`：`STEP_TIER_MAP` 按步骤分级
  - **PREMIUM（gpt-5.4）**：S04 假说生成 / S06 机理仲裁 / S09 候选家族生成 / S10 实例排序 / S11 报告编译
  - **STANDARD（gpt-5.2）**：S07 描述符抽取
  - **CHEAP（gpt-4o-mini）**：S05 / S08 文献摘要、paper card 抽取等辅助任务
  - **选型原因**：主推理链的成本差远小于质量差（~10× cost vs 明显更高的 ranking 稳定性 + 更少的 retry）；辅助任务大多数是结构化抽取，cheap 模型足够。

### Fixed（按时序）
- `mechanism_analog` 候选（如藕粉）被 S11 报告截断 → 见上 `s11_report_compiler.py` 修复。
- `ModuleNotFoundError: No module named 's8_stage3'` → 明确运行前需 `set PYTHONPATH=src`（README / 示例更新）。
- `smoke_chat` 显示用 `gpt-4o-mini` 的迷惑 → 说明 smoke_chat 硬编码 `cheap` tier 是设计使然，仅用于最便宜的连通性验证。
- 全流水线在预期使用 premium 时仍用 `gpt-4o-mini` → 根因是 `.env` 里 `STAGE3_MODEL_TIER=cheap` 全局覆盖了 step-map；通过清空该变量并启用 step-map 解决。
- 手动 PDF ingest 遇到非 ASCII 文件名 `FileNotFoundError` → 使用 `pathlib` + `\\?\` 前缀 + `os.scandir` 的 rename util 处理。
- S09 偶发少于 5 个 instance → 见上 soft-retry 修复。

### Design principles confirmed this round
1. **EIS 形貌是启发式**，不能单独证明机理。`s11` 报告底部保留 `EIS Disclaimer` 并在机理描述中明示 "does not uniquely determine mechanism"。
2. **机理 caveat 与 `why_not` 是硬要求**：任何机理选择都必须公开承认其它候选机理在哪些数据模式上更强。
3. **材料要"可做"而不是"文献里已做"**：`mechanism_analog` 候选接受"4 段类比链"作为创新合法性的结构化证据，而不是直接电导论文。
4. **流水线要"可审计"**：所有 LLM 调用落盘到 `logs/llm_calls.jsonl`；每一条候选可回溯到 `literature_support_card_ids`；`top_candidates_summary` 由代码确定性构建而非 LLM 复述。
5. **硬约束要审慎**：数量性硬约束（≥5 条）可以接受；机理性硬约束（某温差 → 某网络类型）拒绝，改为软启发。

---

## [Earlier in this round] 早期铺垫

### Added
- **手动文献入库**（`literature_workspace/01_manual_inbox/materials/`）共增加 4 篇核心论文：
  - Sepiolite + H₃PO₄ 质子电解质
  - Attapulgite / 1-D clay 质子传导 review
  - PVA + H₃PO₄ + 改性蒙脱土质子电解质
  - PVA/starch 氢键相容性
  + 已有的 PBI + halloysite + H₃PO₄（原始 archetype 锚点）
  + 藕粉品系级理化表征卡（C 型结晶、T_糊化）
- `SystemContext` Pydantic 模型：在所有 LLM 调用中注入"S8 实验体系基本描述"（避免模型凭借 domain 先验对 acid-in-clay 误判）。
- 独立的无泄漏检查器（`validation/no_leakage_checker.py`）：保证 S01–S05 阶段不能直接提到具体材料名。

### Process decisions
- **推理链分层**：确定从 S00（种子） → S01 数据装配 → S02 图谱解读 → S03 现象卡 → S04 假说生成 → S05 文献检索机理 → S06 机理仲裁 → S07 描述符抽取 → S08 文献检索材料 → S09 候选家族 → S10 实例排序 → S11 报告编译 的 12 步结构。
- **外部化 prompt**：所有 prompt 从 `.py` 挪到 `src/s8_stage3/prompts/*.md`，便于版本控制与审阅。
- **Paper cards 单独建库**：每篇文献先转成结构化 `PaperCard`，再在检索阶段映射到机理/材料，避免 LLM 反复读原文。

---

## Open items / 后续轮次可能的改进

- [ ] `stage3_report.md`（英文版）在机理段落有小冗余（EIS 声明出现两次），可在 `s11_report_compiler.md` 增加去重指令。
- [ ] S02 存在一处 Ea 估计为负的小 bug（上游拟合），当前下游只消费定性信号，不影响结论，但值得修。
- [ ] `ranking_notes` 偶尔抱怨某个 `novelty_rationale` 引用了不在 `literature_support_card_ids` 中的 paper ——这是严格审计在工作，不是缺陷，但未来可增加一个自动"引用白名单强制注入"步骤。
- [ ] 目前 `STAGE3_MODEL_TIER` 的语义是"全局覆盖"，未来可改为"hint，由 step-map 决定是否采纳"以避免本轮碰到的迷惑。
