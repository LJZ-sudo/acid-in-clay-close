# Stage3-SDL：S8 体系“证据 → 机理 → 新材料”分层推理重构标准

> 2026-05-18 mainline note: this file remains the architectural standard, but
> the executable Stage3 step list is defined in
> `src/s8_stage3/orchestrator/state_machine.py`. The current chain is
> S03/S04/S05/S06/S06b/S07/S08/S09/S10/S12/S13/S14/S11.

## 1. 文档目的

本文件是 Stage3 代码重构的唯一上位标准。  
所有 Cursor 对 stage3 文件夹的修改，必须以本文件为最高约束。  
任何新代码、提示词、数据结构、输出结果，都必须能够映射回本文定义的：

- 主目标
- 推理顺序
- 目录结构
- 输入输出契约
- 系统提示词
- 验收标准

本文件不是论文草稿，不是材料结论，不是实验方案清单。  
本文件只定义：**Stage3 应该如何工作**。

### 1.1 历史文档例外条款

stage3_mechanism 根目录原则上**不允许保留"历史报告"形态的文档**，但下列文件是显式例外：

- `CHANGELOG.md` —— 记录每轮代码/提示词迭代的"为什么改"（D2/D4/L 等方案演化），是 Keep a Changelog 标准实践，**允许保留**。修改方案、新增 prompt、改 schema 时必须同步更新 CHANGELOG。
- `README.md` —— 当前 Stage3 入口说明。
- `AGENTS.md` —— Cursor 代理规则。
- `stage3-SDL.md`（本文件） —— 架构标准。

除上述 4 个根目录文档外，**不允许新增任何其他 `.md`**（包括 `tinging.md`、`FUTURE_OPTIMIZATION.md`、`*_REPORT.md`、`*_PROPOSAL.md` 等命名），新设计提案应直接写入对应 `prompts/` 或 `contracts/` 代码改动 + CHANGELOG 条目。

---

## 2. Stage3 的唯一主流程

Stage3 的目标不是“直接从表格猜材料”，而是严格遵循下面的单向主流程：

### 主流程
1. **证据层（Evidence）**
2. **竞争机理假说层（Hypotheses）**
3. **文献调研 I：只为约束机理，不为找材料（Mechanism Literature）**
4. **机理仲裁层（Mechanism Arbitration）**
5. **机理描述符抽取层（Descriptor Extraction）**
6. **文献调研 II：只为找材料家族，不为直接下结论（Material Literature）**
7. **材料家族生成层（Family Generation）**
8. **材料实例化与排名层（Instantiation + Ranking）**
9. **报告编译层（Report Compilation）**

### 当前代码入口说明
当前 `src/s8_stage3/orchestrator/pipeline.py` 默认从已经构建好的
`Stage3SeedBundle` 进入 S03，并执行 S03→S04→S05→S06→S06b→S07→S08→S09→S10→S12→S13→S14→S11。S01/S02 的代码保留为可选
预处理/审计模块，但不在默认 pipeline 中自动执行。Real 模式通过
`adapters/stage2_seed_adapter.py` 从 Stage2 五件套构建 seed bundle。

因此，当前实现中的“主流程”对应上面的 9 层科学推理层，不等同于
`state_machine.py` 中包含 S01/S02 的完整依赖图。后续如果需要把 S01/S02
纳入默认运行，必须同步修改 pipeline、测试和本 SDL。

### 禁止事项
- 禁止在证据层提前写入具体材料名。
- 禁止在机理仲裁前出现“藕粉 / PVA / 凹凸棒土 / 海泡石”等具体路线作为上游先验。
- 禁止把 EIS 启发式特征写成等效电路唯一物理断言。
- 禁止让 LLM 直接吃完整 CSV 后自由发挥。
- 禁止将“文献调研”和“材料排名”混成一个步骤。
- 禁止任何 step 直接跨级输出最终材料结论。

---

## 3. Stage3 的总原则

## 3.1 推理原则
Stage3 必须像一个受约束的多智能体系统，而不是一个大 prompt。

每一层只做该层允许做的事：

- 证据层只能说“数据支持什么”
- 假说层只能说“有哪些可竞争解释”
- 文献 I 只能说“哪些机理被文献支持/削弱”
- 仲裁层只能输出“当前最可工作的单一机理”
- 描述符层只能输出“材料应具备什么机制属性”
- 文献 II 只能围绕机制描述符去搜材料家族
- 排名层才能出现具体候选材料和 Top List

## 3.2 非预设原则
Stage3 不允许把“藕粉、PVA、凹凸棒土”作为上游输入先验。  
这些具体材料只能在“材料家族生成/实例化/排名”阶段自然出现。

## 3.3 末端约束原则
最终 Top List **必须包含至少一条藕粉相关路线**，但这条路线必须通过以下路径自然浮现：

`数据证据 → 机理 → 描述符 → 材料家族 → 具体实例`

而不是：

`用户希望要藕粉 → 上游 prompt 提前塞入藕粉`

## 3.4 可审计原则
Stage3 的每一个最终结论，都必须能追溯到：
- 哪个输入文件
- 哪个 step 的中间结果
- 哪条文献卡片
- 哪个仲裁结果
- 哪个评分项

---

## 4. S8 体系的科学约束

## 4.1 数据对象
当前对象是 S8 系列样品，以海泡石等黏土为固相、磷酸水溶液为液相。  
Stage3 的输入核心来自 Stage2 的表格化结果，而不是原始口头印象。

## 4.2 EIS 表述脚注（强制）
以下脚注必须写入所有正式输出模板中：

> `arc_visible`、Nyquist 比值、`semicircle_*` 等来自启发式算法（含多分支频率排序等），仅用于 EIS 形貌分层与趋势提示，不等同于等效电路唯一解，也不等同于通过 Kramers–Kronig 检验后的物理判定。因此凡涉及圆弧/半圆/界面过程的表述，均应理解为“与……一致 / 提示 / 倾向于”，而非“证明存在……”。

## 4.3 已知上游事实的程序化解释
Stage3 设计时必须显式保留以下上游事实：
- 数据是宽温区
- EIS 形貌特征存在
- Meyer–Neldel 关系显著
- Arrhenius 相比 VTF 更优
- `T_arc` 与 `T_break` 存在明显失配

这些事实不能被直接写成最终机理，但必须进入假说生成与仲裁逻辑。

---

## 5. 新的目录结构（重构目标）

建议将旧的 step3x、step3d*、core 杂糅脚本整体迁移到 `legacy/`，然后重建为如下结构：

```text
stage3/
├─ stage3-SDL.md
├─ AGENTS.md
├─ README.md
├─ pyproject.toml
├─ requirements-stage3.txt
├─ .env.example
├─ .cursor/
│  └─ rules/
│     ├─ 00-stage3-core.mdc
│     ├─ 01-stage3-json-only.mdc
│     ├─ 02-stage3-no-material-leakage.mdc
│     └─ 03-stage3-tests-first.mdc
├─ legacy/
│  └─ old_stage3_mechanism/
├─ data/
│  ├─ input/
│  │  ├─ s8_input.csv
│  │  ├─ data_profile.json
│  │  ├─ execution_plan.json
│  │  ├─ s8_evidence_atlas.json
│  │  └─ visualization_manifest.json
│  └─ cache/
├─ outputs/
│  └─ stage3/
│     ├─ 00_preprocess/
│     ├─ 01_evidence/
│     ├─ 02_hypotheses/
│     ├─ 03_literature_mechanism/
│     ├─ 04_mechanism/
│     ├─ 05_descriptors/
│     ├─ 06_literature_materials/
│     ├─ 07_material_families/
│     ├─ 08_material_instances/
│     ├─ 09_ranking/
│     └─ 10_reports/
├─ src/
│  └─ s8_stage3/
│     ├─ __init__.py
│     ├─ config/
│     │  ├─ settings.py
│     │  ├─ llm_gateway.py
│     │  ├─ model_registry.py
│     │  ├─ prompt_registry.py
│     │  └─ runtime_flags.py
│     ├─ contracts/
│     │  ├─ evidence.py
│     │  ├─ hypothesis.py
│     │  ├─ literature.py
│     │  ├─ mechanism.py
│     │  ├─ descriptor.py
│     │  ├─ material.py
│     │  ├─ ranking.py
│     │  └─ report.py
│     ├─ io/
│     │  ├─ paths.py
│     │  ├─ loaders.py
│     │  ├─ writers.py
│     │  └─ snapshots.py
│     ├─ preprocess/
│     │  ├─ stage2_loader.py
│     │  ├─ quality_filter.py
│     │  ├─ segment_rebuilder.py
│     │  ├─ eis_guardrails.py
│     │  └─ sample_graph.py
│     ├─ agents/
│     │  ├─ s01_data_auditor.py
│     │  ├─ s02_segment_builder.py
│     │  ├─ s03_evidence_builder.py
│     │  ├─ s04_hypothesis_generator.py
│     │  ├─ s05_literature_scout_mechanism.py
│     │  ├─ s06_mechanism_arbiter.py
│     │  ├─ s07_descriptor_extractor.py
│     │  ├─ s08_literature_scout_materials.py
│     │  ├─ s09_candidate_family_generator.py
│     │  ├─ s10_instance_ranker.py
│     │  └─ s11_report_compiler.py
│     ├─ scoring/
│     │  ├─ evidence_score.py
│     │  ├─ mechanism_score.py
│     │  ├─ material_score.py
│     │  └─ sensitivity.py
│     ├─ validation/
│     │  ├─ schema_validator.py
│     │  ├─ claim_guardrails.py
│     │  ├─ citation_guardrails.py
│     │  └─ no_leakage_checker.py
│     ├─ orchestrator/
│     │  ├─ pipeline.py
│     │  ├─ state_machine.py
│     │  └─ run_stage3.py
│     └─ prompts/
│        ├─ global_system.md
│        ├─ s03_evidence_builder.md
│        ├─ s04_hypothesis_generator.md
│        ├─ s05_literature_mechanism.md
│        ├─ s06_mechanism_arbiter.md
│        ├─ s07_descriptor_extractor.md
│        ├─ s08_literature_materials.md
│        ├─ s09_family_generator.md
│        ├─ s10_instance_ranker.md
│        └─ s11_report_compiler.md
└─ tests/
   ├─ test_contracts.py
   ├─ test_no_material_leakage.py
   ├─ test_prompt_loading.py
   ├─ test_llm_gateway.py
   ├─ test_pipeline_smoke.py
   └─ test_ranker_constraints.py
```

---

## 6. Agent 总清单（9 步主流程）

下表是 Stage3 的**唯一权威规范**：任何 agent 的行为必须严格对齐本表。字段含义：
- **Kind**：`deterministic`（无 LLM）/ `llm`（调用 LLM）/ `hybrid`（LLM + 规则后处理）
- **Input**：严格输入契约
- **Output**：严格输出契约 + 落盘路径
- **Guard**：该步触发的护栏或硬断路器（failing 时必须 `raise RuntimeError`）
- **Leakage**：是否允许出现具体材料名

| Step | Agent | Kind | Input | Output & Path | Guard / Circuit-Breaker | Leakage |
|---|---|---|---|---|---|---|
| S01 | Data Auditor | deterministic | Stage2 CSV + `data_profile.json` | `audit_report.json` → `00_preprocess/data_audit.json` | `status="fail"` 时 abort | forbidden |
| S02 | Segment Builder | deterministic | clean CSV rows | `SeedBundle` → `00_seed_real/seed_bundle_real.json` | seed sanitizer flags（只记录不 fail） | forbidden |
| S03 | Evidence Builder | deterministic | `Stage3SeedBundle` | `EvidenceBundle` → `01_evidence/evidence_cards.json` | `check_leakage("s03", …)`；必须包含 EIS 免责卡 | forbidden |
| S04 | Hypothesis Generator | llm | `EvidenceBundle` | `HypothesisBoard` → `02_hypotheses/hypothesis_board.json` | 必须返回 4 个假说；`prior_plausibility` 必须 ∈ [0,1]；`check_leakage` | forbidden |
| S05 | Literature Scout (Mechanism) | hybrid | `HypothesisBoard`（+ literature subsystem） | `LiteratureSurvey` → `03_literature_mechanism/literature_cards_mechanism.json` | `manual_strict` 下缺 ctx-pack / paper-cards / evidence-rows → `raise` | forbidden |
| S06 | Mechanism Arbiter | llm | `EvidenceBundle` + `LiteratureSurvey(mechanism)` | `MechanismArbitrationResult` → `04_mechanism/mechanism_card.json` | 必须恰好 1 个 mechanism；必须含 `t_arc_t_break_explanation`；`check_leakage` | forbidden |
| S07 | Descriptor Extractor | llm | `MechanismArbitrationResult` | `DescriptorSheet` → `05_descriptors/descriptor_sheet.json` | `len(descriptors) < 3` → `raise`；`check_leakage` | forbidden |
| S08 | Literature Scout (Materials) | hybrid | `DescriptorSheet`（+ literature subsystem） | `LiteratureSurvey` → `06_literature_materials/literature_cards_materials.json` | 与 S05 相同的 `manual_strict` 硬断路器 | **family-level allowed**（abstract family 名允许，具体配方仍禁止） |
| S09 | Candidate Family Generator | llm | `DescriptorSheet` + `LiteratureSurvey(materials)` | `MaterialFamilySet` + `MaterialInstanceSet` → `07_material_families/` + `08_material_instances/` | `len(families) < 1` 或 `len(instances) < 1` → `raise`；family 层 `check_leakage`（instance 层放开） | family forbidden / instance allowed |
| S10 | Instance Ranker | llm | `MaterialInstanceSet` + `MechanismArbitrationResult` + `LiteratureSurvey(materials)` | `RankingResult` → `09_ranking/ranked_top_list.json` | `validate_ranking_consistency`；lotus 末端诊断（见 §14.1） | allowed |
| S11 | Report Compiler | llm | 全量上游产物 | `Stage3Report` → `10_reports/stage3_report.{json,md}` | audit trail 补全；EIS 免责强制写入 | allowed |

> **解释性预设（允许且显式声明）**：S04 的 4 个假说标签（Grotthuss / percolation / VTF / multi-threshold）**是源自质子输运经典文献的领域候选空间**，不是对最终结论的锚定。S04 只负责在此空间内分配 `prior_plausibility` 和 `supporting/conflicting_evidence_ids`，仲裁权在 S06。

---

## 7. 文献子系统（S05 / S08 共享，与主流程解耦）

Stage3 的文献层**不是主 pipeline 的一个步骤**，而是一个**独立的、可单独运行的子系统**，仅在 S05 / S08 处被主 pipeline 消费。

### 7.1 两条独立子线
```
mechanism sub-line:   query_packet_s05  →  inbox(s05_mechanism/)  →  registry  →  paper_cards/mechanism  →  evidence_rows (mech)  →  mechanism_evidence_table  →  ctx-s05 / ctx-s06
materials sub-line:   query_packet_s08  →  inbox(s08_materials/)   →  registry  →  paper_cards/materials  →  evidence_rows (mat)  →  material_evidence_table   →  ctx-s08 / ctx-s09 / ctx-s10
```
两条子线**共享 registry**（同一篇论文可出现在两条子线，用 `source_stage` 字段区分），但**各自独立生成 paper cards、evidence rows、curated tables、context packs**。这样做的目的：**防止材料文献污染机理推理**——S05 只能看到来自 `s05_mechanism/` 的证据，不会被 S08 的材料家族引导。

### 7.2 Literature Workspace 7 层目录
```
literature_workspace/
├─ 00_query_packets/         # by build_query_packets_only 生成，给人工 Google Scholar 检索
│   ├─ s05_mechanism/QP-S05-001.{json,md}
│   └─ s08_materials/QP-S08-001.{json,md}
├─ 01_manual_inbox/          # 人工把 PDF 放进来（两个子目录对应两条子线）
│   ├─ s05_mechanism/*.pdf
│   └─ s08_materials/*.pdf
├─ 02_registry/              # 持久化 paper_registry.{json,csv}
├─ 03_parsed_text/           # paper_reader 的 PDF/txt/json 解析产物（ParsedPaper）
├─ 04_paper_cards/           # paper_card_builder 的 LLM 结构化抽取
│   ├─ mechanism/<paper_id>_card.json
│   ├─ materials/<paper_id>_card.json
│   └─ <...>/card_quality_log.json
├─ 05_evidence_rows/         # 从 cards 拆出的原子 claims（可选保存，builder 内存中流转即可）
├─ 06_curated_tables/        # evidence_table_builder 的优先级筛选结果
│   ├─ mechanism_evidence_table.json
│   └─ material_evidence_table.json
└─ 07_context_packs/         # 下游 step 的最小扇入上下文
    ├─ ctx-s05.json  ctx-s06.json
    └─ ctx-s08.json  ctx-s09.json  ctx-s10.json
```

### 7.3 单独运行的 CLI 命令（与主 pipeline 解耦）
```bash
# Step A：从 S04 产物生成 query packets（人工去 Google Scholar 检索）
python -m s8_stage3.orchestrator.run_stage3 --build-query-packets-only

# Step B：把下载的 PDF 放入 01_manual_inbox/{s05_mechanism,s08_materials}/*.pdf 后
python -m s8_stage3.orchestrator.run_stage3 --ingest-manual-papers

# Step C：对 registry 中每一条 ingest_status!='carded' 的论文跑 LLM 抽取
python -m s8_stage3.orchestrator.run_stage3 --rebuild-paper-cards --llm-mode live

# Step D：从 paper cards 构建 evidence rows → curated tables → context packs
python -m s8_stage3.orchestrator.run_stage3 --rebuild-evidence-tables
```
**Step A–D 每一步都是幂等的**：重复运行不会破坏已有 registry 条目；质量门控未通过的 card 自动走 `fallback_keyword_extract`；registry 的 `ingest_status` 会如实更新为 `carded | carded_fallback | card_failed_quality_gate`。

### 7.4 Paper Card 质量门控
- **最小质量阈值**：`mechanism_relevant_findings + numerical_findings + eis_shape_findings + arrhenius_vtf_findings ≥ 2`
- **fallback extractor**：当 LLM 抽取低于阈值，用 deterministic 关键词正则（`conductivity | S/cm | activation energy | eV | Nyquist | semicircle | tail | Arrhenius | VTF | Grotthuss | vehicular | proton hopping | interfacial water`）挽救 findings；挽救成功 → `carded_fallback`，仍然失败 → `card_failed_quality_gate`
- **日志**：`04_paper_cards/<side>/card_quality_log.json` 按论文记录 status、findings 计数、fallback 是否触发

---

## 8. 运行模式矩阵

Stage3 的行为由 4 个正交参数共同决定：

| 参数 | 取值 | 含义 |
|---|---|---|
| `--mode` | `mock` / `real` | 种子来源：`mock_seed_factory` / Stage2 真实 CSV |
| `--llm-mode` | `mock` / `live` | LLM 调用：`mock_llm` 生成合成 JSON / 真实 OpenAI-compatible API |
| `--literature-mode` | `mock` / `api` / `manual` / `hybrid` | 文献来源：`mock_literature_bank` / OpenAlex API / 手工 inbox / manual 优先 + api 补充 |
| `--manual-strict` | off / on | 仅在 `literature-mode=manual` 生效：关 → 缺 artifact 时回退 registry；开 → 缺 artifact 直接 `raise` |

**推荐组合**：
1. **开发/回归**：`--mode mock --llm-mode mock --literature-mode mock` — 纯离线、零 API、0.4s 完成 73 tests，用于冒烟
2. **种子适配验证**：`--mode real --llm-mode mock --literature-mode mock` — 验证 Stage2 → Seed 适配器
3. **机理/材料推理验证**：`--mode real --llm-mode live --literature-mode mock` — 不涉及文献，只看 LLM 推理
4. **正式小批验证（本轮刚完成）**：`--mode real --llm-mode live --literature-mode manual --manual-strict` — 使用真实文献证据，fail-closed
5. **大批量检索阶段**：`--mode real --llm-mode live --literature-mode hybrid` — manual 为主、OpenAlex 为补，去重合并

---

## 9. 端到端数据流与可审计性

### 9.1 物理数据流
```
Stage2 outputs (CSV + profile + atlas)
    │
    ▼
[adapters/stage2_seed_adapter]  ──►  Stage3SeedBundle  ──►  00_seed_real/
    │                                          │
    │                                          ▼
    │                              [pre_llm/seed_sanitizer]
    │                                          │
    │                                          ▼
    │                              S03 EvidenceBundle  ──►  01_evidence/
    │                                          │
    ▼                                          ▼
Literature Workspace              S04 HypothesisBoard  ──►  02_hypotheses/
(query packets / inbox /                       │
 cards / evidence rows /                       ▼
 context packs)  ──── ctx-s05 ──►  S05 LiteratureSurvey  ──►  03_literature_mechanism/
                                               │
                                               ▼
                                   S06 MechanismArbitration  ──►  04_mechanism/
                                               │
                                               ▼
                                   S07 DescriptorSheet  ──►  05_descriptors/
                                               │
                 ─── ctx-s08 ──►  S08 LiteratureSurvey  ──►  06_literature_materials/
                                               │
                                               ▼
                                   S09 FamilySet + InstanceSet  ──►  07_material_families/ + 08_material_instances/
                                               │
                                               ▼
                                   S10 RankingResult  ──►  09_ranking/
                                               │
                                               ▼
                                   S11 Stage3Report  ──►  10_reports/
```

### 9.2 可审计字段矩阵
每一个最终候选材料 `RankedCandidate` 必须能沿下面的字段链回溯到**具体输入**：

| 回溯目标 | 通过字段 | 落盘文件 |
|---|---|---|
| 原始 Stage2 样品 | `source_sample_ids`（E 卡） | `01_evidence/evidence_cards.json` |
| 机理选择理由 | `selected_hypothesis_id`, `evidence_alignment[]`, `literature_support[]` | `04_mechanism/mechanism_card.json` |
| 机理文献证据 | `literature_support_card_ids`（family 层）+ `ctx-s05.included_row_ids` | `03_literature_mechanism/` + `07_context_packs/` |
| 材料家族映射 | `descriptor_match[]`（F 层）| `07_material_families/` |
| 材料实例来源 | `family_id`（I 层）+ `literature_support_card_ids` | `08_material_instances/` |
| 评分依据 | `criteria_scores[].score`, `criteria_scores[].weight` | `09_ranking/ranked_top_list.json` |
| 运行成本 | `run_cost_summary.json` | `outputs/stage3/` |

**任何一条链路断掉，都视为 SDL 违规**。

### 9.3 幂等与可恢复
- 所有 agent 输出**写文件而非内存**；所有 LLM 调用可 `--no-cache` 旁路，否则按 `(step, prompt_hash, tier)` 落盘缓存
- `--until s0X` 支持增量运行到某步后停止，后续步骤可独立补跑
- 主 pipeline 的断路器 `raise RuntimeError` 后，`run_cost_summary.json` 依然写盘（见 `pipeline._write_cost_summary`），便于事后溯源

---

## 10. 护栏与评分（validation + scoring）

### 10.1 三层护栏
| Guardrail | 位置 | 时机 | 行为 |
|---|---|---|---|
| Schema Validator | `validation/schema_validator.py` | 每个 LLM 输出 | pydantic `model_validate` 失败 → `raise` |
| No-Leakage Checker | `validation/no_leakage_checker.py` | S03–S07 + S09 families 层 | 匹配材料名正则 → `logger.warning`（可升级为 `assert_no_leakage`） |
| Claim Guardrail (EIS) | `validation/claim_guardrails.py` | 所有 step | 命中"绝对化" EIS claim（如 "proves", "is the circuit"）→ `logger.warning` |

> **当前策略**：leakage / claim 级都是 **soft warning**，schema 级是 **hard raise**。在正式验证阶段可以把 leakage 也升级为 hard。

### 10.2 评分
- `scoring/evidence_score.py`：给 `EvidenceCard.confidence` 提供确定性复核
- `scoring/mechanism_score.py`：给 `MechanismArbitrationResult.confidence` 提供一致性检查
- `scoring/material_score.py::compute_weighted_score`：**可独立复算** `RankedCandidate.total_score`，用于验证 S10 LLM 是否按加权规则排序
- `scoring/material_score.py::validate_ranking_consistency`：检查 rank 与 score 是否单调

**定位**：评分不是主决策器，而是**对 LLM 输出的事后验证**。

### 10.3 Seed Sanitizer
`pre_llm/seed_sanitizer.py` 在任何 LLM 调用之前对 `SeedBundle` 做异常数据点标记（`sanitization_flags`），产物写入 `00_sanitizer_digest.json`，同时作为 system prompt 注入给所有下游 LLM 步骤。

---

## 11. LLM Gateway（config/llm_gateway.py）

- **协议**：OpenAI-compatible `chat.completions`，同时支持 `response_format=json_schema`（OpenAI 原生）与 `json_object`（Polo 等兼容平台）
- **结构化输出降级策略**：由 `STAGE3_USE_STRUCTURED_OUTPUTS` 控制；当平台返回 `400 invalid response_format` 时自动降级到 `json_object`
- **模型分级**：`cheap / standard / premium` 三档，由 `ModelRegistry` 注入；默认所有 step 走 `cheap`，可按 step 覆写
- **缓存**：`(step_id, hash(messages), tier)` 作为键，存在 `data/cache/` 下；`--no-cache` 旁路
- **成本统计**：`get_cost_summary()` 统计 `call_count / cache_hits / tokens`，落盘为 `run_cost_summary.json`
- **重试**：交给 OpenAI SDK 的内置 exponential backoff（429）；400 做一次降级重试

---

## 12. 验收标准（Definition of Done）

一次 Stage3 运行被视为**可接受的正式产物**，必须同时满足：

1. **结构完整**：`outputs/stage3/{00..10}_*/` 所有目录均有对应 JSON；`run_cost_summary.json` 存在
2. **契约合规**：所有 JSON 可以被对应 pydantic 模型无错地 `model_validate`
3. **零 hard guardrail 违规**：schema validator / S07 descriptor-min / S09 family-min / S09 instance-min 未触发 `raise`
4. **零泄漏**：`check_leakage` 在 S03–S07 + S09-families 返回 0 条违规
5. **可审计链完整**：任意一条 `RankedCandidate` 能回溯到 §9.2 表中的全部 7 类字段
6. **文献证据可追溯**（manual-strict 模式）：`03_literature_mechanism/` 与 `06_literature_materials/` 的每条 `LiteratureCard.card_id` 能在 `paper_registry.json` 找到对应 `paper_id`
7. **EIS 免责声明写入报告**：`stage3_report.md` 结尾含 `> **EIS Disclaimer**: ...`
8. **测试通过**：`pytest -q` 全绿（当前基线 73 tests）

---

## 13. 测试矩阵（tests/）

| 类别 | 文件 | 保障 |
|---|---|---|
| 契约 | `test_contracts.py` | Pydantic 模型字段、默认值、校验规则 |
| 无泄漏 | `test_no_material_leakage.py` | S03–S07 输出不含具体材料名 |
| 文献工作流 | `test_literature_workflow.py` | query packet / registry / dedupe / reader / card / evidence row / table / context pack + manual-strict 模式 + 质量门控 + fallback extractor |
| LLM Gateway | `test_llm_gateway.py` | mock / live 路径、cost summary、call count |
| Prompt 装载 | `test_prompt_loading.py` | 所有 prompt .md 可载入 |
| Mock Pipeline | `test_pipeline_smoke.py` | S03+S06b+S12-S14+S11 端到端（mock seed + mock LLM） |
| 整链冒烟 | `test_pipeline_smoke.py` | run_mock / run_real 最小断言 |
| 排序约束 | `test_ranker_constraints.py` | `validate_ranking_consistency`、lotus 末端诊断 |

**底线**：新增任何 agent 或 prompt 时，必须同步补对应测试，测试总数只增不减。

---

## 14. 科研严谨性条款（含修复记录）

本节是 SDL 的**科研严谨性硬约束区**。§14.2–§14.6 在 2026-04-15 均已**落实到代码**，不再是"待办项"。以下内容既是对过去问题的交代，也是对未来变更的**强制约束**——任何回滚这些约束的修改都必须先修改本节。

### 14.1 §3.3 "末端约束原则" 的澄清修订
原文："最终 Top List **必须包含至少一条藕粉相关路线**" 会与 §3.2 非预设原则产生字面冲突。**正确理解**为：

> **末端浮现检查（诊断性，非强制性）**：如果 `MaterialInstanceSet` 中存在 `lotus_related=true` 的实例，但该实例**未**出现在 `RankingResult.ranked_candidates` 中，S10 须在日志记录 `"[S10] lotus instance exists but not ranked — check prompt or ranking bias"`。**不允许**后置向 Top List 强行插入 lotus，否则等价于上游先验。

`s10_instance_ranker.py` L58–68 的当前实现（仅 `logger.info`，不强插）是**符合**本澄清的。

### 14.2 Prompt 去锚定（强制）[DONE 2026-04-15]
- **S09 family generator** 禁止把任何具体物质（尤其 `"Lotus starch"`）写入 prompt 示例。`lotus_related` 字段只能作为**如实描述性 flag**使用（当且仅当 instance 的 base material 是藕粉衍生物时置 true），不得作为"目标命中 flag"。
- **S06 mechanism arbiter** 的 OUTPUT FORMAT 示例必须用占位符（`"<one of the hypothesis_ids from S04, chosen strictly on evidence>"`），禁止写死具体 hypothesis ID。
- **落点**：`prompts/s09_family_generator.md`、`prompts/s06_mechanism_arbiter.md`。

### 14.3 Supports / Weakens 字段贯通（强制）[DONE 2026-04-15]
**推理链**：Paper Card LLM → PaperCard.supports_axes / conflicts_axes → EvidenceRow.supports / weakens → ContextPack.key_supports / key_weakens → 下游 S06/S09 LLM 消费。

- `PaperCard` 契约（`contracts/paper_card.py`）**必须**包含 `supports_axes: dict[str,str]` 与 `conflicts_axes: dict[str,str]`，推荐 key 为 `transport | phase_structure | temperature_dependence | transition_topology`（与 §14.6 假说维度对齐）。
- `paper_card_builder._CARD_SYSTEM_PROMPT` **必须**让 LLM 输出这两个字段（允许空 dict）。
- `evidence_row_builder.extract_evidence_rows` **必须**把 `card.supports_axes` / `card.conflicts_axes` 展开为 `"axis:value"` 字符串，透传到每一条 `mechanism_claim` 或 `arrhenius_vtf` 类型的 `EvidenceRow.supports` / `weakens`。
- `context_pack_builder.build_context_pack` 已有的聚合逻辑（`r.supports/r.weakens → key_supports/key_weakens`）保持不变。

### 14.4 Mechanism Tags 的否定语义（强制）[DONE 2026-04-15]
`evidence_row_builder._infer_mechanism_tags` **必须**对关键词做否定前瞻：在命中关键词前 30 字符内若出现 `no | not | non | without | absence of | against | rules out | inconsistent with`，则该 tag 作为**负向** tag，通过 `EvidenceRow.weakens = ["mechanism:<tag>"]` 呈现；正向 tag 仍写入 `mechanism_tags`。

### 14.5 Confidence 与论文 Relevance 联动（强制）[DONE 2026-04-15]
`EvidenceRow.confidence` **必须**按 `confidence = base_weight × PaperCard.relevance_judgement.score` 计算，其中：

| 证据类型 | base_weight |
|---|---|
| mechanism_claim | 0.60 |
| direct_measurement (numeric) | 0.80 |
| direct_measurement (EIS) | 0.50 |
| direct_measurement (Arrhenius/VTF) | 0.70 |
| limitation | 0.50 |

当 `relevance_judgement.score` 缺失或非 [0,1] 浮点时，fallback 到 `1.0`（相当于只用 base）。

### 14.6 假说生成必须 data-driven，不得预设标签（强制）[DONE 2026-04-15]
**违反**条款示例（已废止）：老版 S04 prompt 直接写 `Generate 4 competing hypotheses covering: 1. Grotthuss threshold hopping, 2. Single percolation threshold, 3. Cooperative VTF rearrangement, 4. Multi-threshold confined acid-water network`。这让 S04 变成"填空器"而非"生成器"，不符合 §3.1 "假说层只能说**有哪些**可竞争解释"。

**正确规范**：
- S04 prompt 只提供 **4 个假说维度**（transport / phase_structure / temperature_dependence / transition_topology）和每个维度的**候选取值列表**（典型值，非穷举），由 LLM 基于 evidence 自主**组合**并**命名**（`mechanism_label` 必须是 self-descriptive，而不是 textbook 标签）。
- 生成数量范围 **3–5 个**（不是固定 4 个），真实取决于 evidence 支持多少个 genuinely distinct story。
- **竞争条件硬约束**：至少一个维度上存在 ≥2 个假说取值不同；任意两个假说的 `mechanism_axes` 不得完全相同。
- **契约强制**：`Hypothesis.mechanism_axes: dict[str,str]` 是**必须填充**的字段（虽然默认 `default_factory=dict` 以向后兼容，但 prompt 的 CRITICAL RULES 明确要求四个 key 都要填）。
- **下游对齐**：§14.3 的 Paper Card `supports_axes / conflicts_axes` 必须使用相同的 key 空间，使得论文证据能按维度定位到 S04 生成的假说。

---

## 15. 版本与变更控制

- 本文件是 Stage3 的**唯一上位标准**。任何对 `agents/` `contracts/` `prompts/` `orchestrator/` `validation/` `scoring/` `literature/` 的修改，**必须**先回答：
  1. 该修改是否改变了本文件中任何一条约束？
  2. 如果是，是否先更新本文件并获得审阅？
- 本文件的变更使用 `CHANGELOG` 段在文末追加；不允许无记录地覆盖。
- `legacy/` 目录是**只读冻结区**，不在 SDL 作用域内。

---

## 附录 A：推理链条与"藕粉末端浮现"的正确理解

按 §3.2 非预设原则，藕粉**不能**出现在 S03 / S04 / S05 / S06 / S07 的任何输入、prompt 或输出中。它只能通过以下因果链在 S09 实例层**自然浮现**：

```
多 Ea 片段 + T_arc≠T_break + 宽温区 + Meyer-Neldel  (S03 evidence)
    ↓
multi-threshold confined acid-water network reconnection  (S04 candidate + S06 arbitration)
    ↓
{ OH-rich matrix,  nano-confined water channels,  strong Brønsted acid retention,  percolated H-bond network }  (S07 descriptors)
    ↓
OH-rich polysaccharide + strong Brønsted acid  (S09 family)
    ↓
Lotus starch / H3PO4 ; Cellulose / H3PO4 ; Chitosan / H3PO4 ; ...  (S09 instance)
    ↓
ranked list with lotus possibly (not mandatorily) in top-K  (S10)
```

如果 S07 描述符不是"OH-rich + 强酸保留 + H-bond 网络"，那么 S09 就**不应**生成 lotus 路线。**lotus 出现与否是 Stage3 推理忠实度的诊断指标**，不是目标。

---

## 附录 B：与既有 §3.3 的关系

§3.3 原文的"**必须包含至少一条藕粉相关路线**"应读作：

- **规范性语义**（SDL 强制）：推理链的**描述符空间必须允许** lotus 路线浮现（即 S07 不能把 "plant-derived" / "polysaccharide" 排除在候选之外）
- **非规范性语义**（不强制）：最终 Top List 是否**实际**含有 lotus，取决于 S10 的多维评分结果；如果 lotus 在 S09 实例层出现但 S10 未纳入 Top List，应记录诊断但**不**强插

§14.1 是对此的权威澄清。

---

## CHANGELOG

- **2026-04-15（第二次）**：§14.2–§14.6 由"待修复"升级为"强制条款 + 已落地"。对应代码改动：
  - `prompts/s04_hypothesis_generator.md` — 用 4 维假说空间替代 4 个固定标签；3–5 个竞争假说；强制填充 `mechanism_axes`。
  - `prompts/s06_mechanism_arbiter.md`、`prompts/s09_family_generator.md` — 示例去锚定。
  - `contracts/hypothesis.py` — 新增 `Hypothesis.mechanism_axes`。
  - `contracts/paper_card.py` — 新增 `supports_axes` / `conflicts_axes`。
  - `literature/paper_card_builder.py` — prompt 要求输出 axes 字段；builder 贯通。
  - `literature/evidence_row_builder.py` — confidence 按 `base × relevance` 计算；`_infer_mechanism_tags` 支持否定前瞻；`card.supports_axes / conflicts_axes` 透传到 `EvidenceRow.supports / weakens`。
  - `mock/mock_llm.py::_mock_s04` — 四个 hypothesis 均补上 `mechanism_axes`（mock 路径对齐新 schema）。
- **2026-04-15（第一次）**：补齐 §6–§15 + 附录 A/B；对 §3.3 做澄清修订（§14.1）；记录 7 项已知科研严谨性改进项；与当前代码状态对齐（Pipeline / LiteratureWorkspace / manual-strict / 质量门控 / fallback extractor / 可审计矩阵）。
- **（早于 2026-04-15）**：§1–§5 原版 SDL 主流程、禁止事项、总原则、科学约束、目录结构。
