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

## 候选与验证绑定
- registry 候选(冻结候选)+ `stage3_mechanism/outputs/verification/.../12_validation_binding/validation_binding_report.json`
  — 注意 `preregistered_at` 晚于实验,叙事应以上面早期 query packet / paper card 的 `created_at` 为准,避免"前瞻"误述。

## 母系统实验证据(本地副本,2026-06-07 从 stage1_optimization 迁入)
- `s8_acid_in_clay_mother_system/history_db_s8_sepiolite.json`
  — S8 sepiolite AiCE 体系的 20 trial 真机优化历史(2026-04-13 ~ 2026-05-01)。
- `s8_acid_in_clay_mother_system/s8_sepiolite_campaign_config.json`
  — 当年 S8 campaign 的 R/N 边界与 domain knowledge。
- `s8_acid_in_clay_mother_system/README.md` — 子目录说明,含迁移背景与未来 re-ingest 指南。

这些文件不再被 `stage1_optimization` 的任何代码路径读取(已于 2026-06-07 完成 6 处 fallback 改写),
仅作为 Pillar 1 transfer 叙事的"母系统先验"在写作和审稿中使用。
