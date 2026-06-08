# Pillar 1 — Evidence-constrained transfer agent(指针,不复制)

本创新点的证据与 agent harness **全部位于 `V1.0-qianduan-mainline/` 内**。
为避免出现第二份副本,这里只列指针;请直接引用 V1.0 中的原始文件。

## 时间线证据(motif 级推理先于实验)
- `V1.0-qianduan-mainline/stage3_mechanism/literature_workspace/00_query_packets/s08_materials/QP-S08-001.json`
  — agent 生成的检索包,**2026-04-17**(含 polysaccharide PEM / clay-polymer composite / starch phosphoric acid 等查询)
- `V1.0-qianduan-mainline/stage3_mechanism/literature_workspace/04_paper_cards/materials/manual_8d58a81c9e_card.json`
  — 材料 paper card,**2026-04-19**
- 二者均早于首次 EIS 实验(2026-04-25),支撑"先推理后实验"的 transfer 叙事。

## Agent harness(说明"是 agent,不只是脚本")
- `V1.0-qianduan-mainline/stage3_mechanism/src/s8_stage3/agentic/memory.py`   — episodic memory(append-only、确定性回放)
- `V1.0-qianduan-mainline/stage3_mechanism/src/s8_stage3/agentic/critic.py`   — produce-critique-revise 自我批判(overclaim / eis_overclaim 规则)
- `V1.0-qianduan-mainline/stage3_mechanism/src/s8_stage3/agentic/heartbeat.py`— liveness / 进度遥测
- `V1.0-qianduan-mainline/stage1_optimization/agents/strategy_planner.py`     — LLM 决策 + 参数/schema 校验(NextExperimentRecipe)
- `V1.0-qianduan-mainline/stage3_mechanism/src/s8_stage3/config/llm_gateway.py`— 统一 LLM 网关(结构化输出、缓存、temperature=0/seed 可复现)

## 候选与验证绑定（2026-06-07e 更新）
- registry 候选(冻结候选) + `stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2/12_validation_binding/validation_binding_report.json`
- **重建后的 timing anchor**: `stage3_mechanism/data/validation/timing_reference_registry.json`
  - `preregistered_at = 2026-05-08T13:29:43+00:00`，**早于 2026-05-09 的 7 项 transfer-validation 实验**。
  - 原始 anchor registry 在 2026-05-18 清理 commit `4b6ee61` 中被作为遗留归档误删；
    2026-06-07e 据保留的文件名时间戳 `candidate_validation_link_20260508T132943Z.json`
    与 `experimental_feedback.json::provenance.agent_registry_run_id="a42de8d3b4"` 等
    证据透明重建。过程见 `stage3_mechanism/CHANGELOG.md` 条目 [2026-06-07d] / [2026-06-07e]
    与 `outputs/MANIFEST.md`。
- **2026-06-07e Stage3 S13/S14 重审结果**: `prospective_validation = PASS`
  （2 条候选 `PC-a42de8d3b4-01` / `PC-a42de8d3b4-05` 满足"frozen 早于 measured"判据），
  并以 `STAGE3_FINAL_AUDIT=true` 出具，同时移除 `llm_transfer_candidate` 的缓存复用 caveat。
- 双锚叙事：早期 query packet (QP-S08-001, 2026-04-17) + paper card
  (manual_8d58a81c9e_card, 2026-04-19) 作为更强的 "motif 级推理先于实验"
  补充证据保留——论文可与 timing_reference_registry.json 双锚并列引用。

## 母系统实验证据(本地副本,2026-06-07 从 stage1_optimization 迁入)
- `s8_acid_in_clay_mother_system/history_db_s8_sepiolite.json`
  — S8 sepiolite AiCE 体系的 20 trial 真机优化历史(2026-04-13 ~ 2026-05-01)。
- `s8_acid_in_clay_mother_system/s8_sepiolite_campaign_config.json`
  — 当年 S8 campaign 的 R/N 边界与 domain knowledge。
- `s8_acid_in_clay_mother_system/README.md` — 子目录说明,含迁移背景与未来 re-ingest 指南。

这些文件不再被 `stage1_optimization` 的任何代码路径读取(已于 2026-06-07 完成 6 处 fallback 改写),
仅作为 Pillar 1 transfer 叙事的"母系统先验"在写作和审稿中使用。
