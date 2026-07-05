# stage3_mechanism/ 结构与逐模块状态文档

> 生成于 2026-07-05，基于代码级核查。入口/运行方式见同目录 `README.md`；架构最高权威是 `stage3-SDL.md`；Agent 约束见 `AGENTS.md`；决策日志见 `CHANGELOG.md`。
> 结论：`src/s8_stage3/` 内**唯一遗留死代码是 `agents/s09b_top_list_to_campaign_seed.py`**；其余全部现役（部分为 opt-in）。

## 1. 目录总览

```
stage3_mechanism/
├─ README.md / stage3-SDL.md / AGENTS.md / CHANGELOG.md   # 治理文档四件套
├─ requirements.txt / .env.example
├─ src/s8_stage3/            # 唯一生产包（详见 §2）
├─ tests/                    # 🧪 21 个测试文件（73 条测试基线，见 §4）
├─ audit/candidate_terms/    # 源词审计配置（lotus_root_starch.yaml，S14 消费）
├─ data/
│  ├─ input/archive/         # ⛔ V1 遗留 · s8_evidence_atlas_20260413_48units.json（resolver 第 5 优先级，正常永远走不到）
│  ├─ cache/current/         # gitignored · llm_cache/ + literature_cache/
│  └─ validation/            # 🧊 受保护证据 · experimental_feedback.json、biopolymer_validation_results.csv、timing_reference_registry.json（three_pillars 主张审计引用，改动必须记 CHANGELOG）
├─ literature_workspace/     # 文献子系统工作区（00 查询包→02 注册表→04 论文卡→06 表格→07 上下文包；01/03 gitignored）
├─ logs/                     # llm_calls.jsonl gitignored
└─ outputs/
   ├─ stage3/                # 新 run 占位（不作隐式真值）
   └─ verification/
      ├─ 20260607_openrouter_publication_v2/   # 🧊 冻结 · 权威发表产物（analysis/ablation m6-m8 的参照）
      ├─ 20260607_mixed_tier_publication/      # 🧊 冻结 · V1 polo 交叉验证证据
      ├─ 20260526_final_audit_cacheoff_full/   # 🧊 冻结 · 历史 deepseek 基线
      └─ 20260607_post_cleanup_smoke/          # 🧊 冻结 · mock 回归快照
```

## 2. src/s8_stage3/ 逐模块状态

### agents/ — 流水线步骤（S01–S14）
默认执行链（state_machine.py）：seed_sanitizer → S03 → S04 → S05 → S06 → S06b → S07 → S08 → S09 → S10 → S12 → S13 → S14 → S11。

| 模块 | 状态 | 说明 |
|---|---|---|
| s03_evidence_builder.py | ✅ | 确定性：SeedBundle → EvidenceBundle，注入 EIS 免责声明卡 |
| s04_hypothesis_generator.py | ✅ LLM | 3–5 个竞争机理假说（mechanism_axes） |
| s05_literature_scout_mechanism.py | ✅ 混合 | 机理侧文献综述 |
| s06_mechanism_arbiter.py | ✅ LLM | 仲裁出唯一 MechanismCard |
| s06b_design_principle_extractor.py | ✅ LLM | 可迁移设计原则 |
| s07_descriptor_extractor.py | ✅ LLM | 描述符表（≥3） |
| s08_literature_scout_materials.py | ✅ 混合 | 材料侧文献 + 逐文 ComponentDescriptorClaim |
| s09_candidate_family_generator.py | ✅ | 家族/实例生成（默认 deterministic_from_d4，不调 LLM） |
| s10_instance_ranker.py | ✅ | 排序（默认 deterministic_from_audit）+ 藕粉诊断 |
| s11_report_compiler.py | ✅ | 报告汇编（默认确定性） |
| s12_prospective_registry.py | ✅ | 验证前冻结候选注册表（前瞻性证明关键件） |
| s13_validation_binder.py | ✅ | 绑定实测 CSV + experimental_feedback，推断 claim_eligibility |
| s14_claim_auditor.py | ✅ | 主张阶梯审计（C0–C5，PASS/TODO） |
| s01_data_auditor.py / s02_segment_builder.py | ⚠️ opt-in | 遗留 CSV 审计辅助，不在默认链 |
| **s09b_top_list_to_campaign_seed.py** | **⛔ 遗留** | docstring 自标 LEGACY；参数空间仍是 S8 海泡石（与凹凸棒不匹配）；无任何 import |

### 其他子包（全部现役）

| 子包 | 内容 |
|---|---|
| adapters/ | input_resolver（5 级输入解析）、stage2_seed_adapter（V2 seed 权威）、live_seed_adapter（⚠️ opt-in：真机测量→Stage3 桥，p9 验证脚本使用） |
| agentic/ | ⚠️ Tier-3 opt-in：critic / heartbeat / memory（由 orchestrator/agentic_review.py 驱动，不在主链） |
| config/ | settings（STAGE3_* 环境变量）、llm_gateway（OpenAI 兼容 + 结构化输出回退 + 缓存 + 成本汇总）、model_registry（三档模型路由）、prompt_registry（prompts/*.md + SHA256）、runtime_flags |
| contracts/ | 20+ 个 Pydantic 契约（每步输出落盘前强校验） |
| io/ | writers / loaders / paths / snapshots（debug 用） |
| literature/ | 文献子系统 13 模块（ingest→registry→dedupe→paper_card→evidence_row→curated_table→context_pack；OpenAlex provider） |
| llm/ | prompt_packing（含 D2 组分原子化防锚定偏置） |
| mock/ | 🧪 测试专用 mock（seed / llm / literature bank） |
| orchestrator/ | run_stage3（CLI 入口）、pipeline、state_machine、agentic_review（opt-in） |
| pre_llm/ | seed_sanitizer（数值异常旗标，注入所有下游 LLM 系统提示） |
| preprocess/ | eis_guardrails（EIS 免责/过度主张检测）、quality_filter |
| prompts/ | 12 个外置 .md 提示词（**禁止内联提示词**，AGENTS.md 铁律） |
| scoring/ | 5 个事后核验器 + ranking_robustness_v2（C2 稳健性，绝不改写 ranked_top_list.json） |
| validation/ | schema_validator（硬失败）、no_leakage_checker、claim_guardrails、citation_guardrails、source_term_auditor |

## 3. 外部消费者

- `analysis/ablation/m6_* m7_* m8_*`：直接 import s8_stage3，参照冻结的 publication_v2 产物；
- `analysis/verification/p9_stage3_live_verify.py`：经 live_seed_adapter 用真 run 事件驱动；
- `backend_api/routers/pipeline.py`：⛔ 已停用（410），仅提示正确入口是 run_stage3 CLI；
- `stage2_statistics/exports/stage3_seed.json`：上游权威输入。

## 4. 运行模式要点

- 默认 deterministic 开关（S09/S10/S11）为 true → 正常 run 只有 S04/S06/S06b/S07（+S05/S08 摘要）实际调 LLM；
- 当前供应商 OpenRouter（`openai/gpt-5.4` PREMIUM / `openai/gpt-5.2` STANDARD+CHEAP）；V1 polo 供应商产物保留作跨供应商稳健性证据；
- `STAGE3_FINAL_AUDIT=true` 自动关缓存；
- 测试：`$env:PYTHONPATH='stage3_mechanism/src'; python -m pytest -q stage3_mechanism\tests`（基线 73 条）。
