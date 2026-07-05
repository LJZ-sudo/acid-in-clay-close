# S8 acid-in-clay mother system — 母系统证据

本目录是 **Pillar 1 transfer agent** 的"母系统证据"：从 S8 (酸-海泡石 AiCE) 体系到下游 attapulgite AiCE → biopolymer-clay membrane motif 的 transfer 链的起点。

## 为什么把这些文件从 `stage1_optimization/` 迁过来

S8 的 20 trial 优化历史与 campaign 边界**不属于当前在跑的 BO 训练库**（当前主线是
`stage1_optimization/campaign_memory/history_db_attapulgite.json`）。
它们的真实角色是 transfer agent 叙事的"母系统先验"，应该和 Pillar 1
的其它证据（文献检索包、paper cards、design principles）放在一起、统一引用。

代码侧确认（2026-06-07 grep）：

- `agents/llm_client.py` / `strategy_planner.py` / `planner_prompts.py` 全部 **0 处**
  读取 S8 history。
- `attapulgite_aice_campaign.json` 原有的 `transfer_reference` 字段是 declarative-only，
  无任何 .py 文件消费。
- 5 处代码出现的 `"campaign_memory/history_db.json"` 都是 fallback default，
  现在 fallback 已经改成 `"campaign_memory/history_db_attapulgite.json"`。

因此把 S8 资产物理移动到这里不会影响任何活代码路径，但保留了未来 transfer
论证 / 写作 / re-ingest 所需的全部原始数据。

## 内容清单

- `history_db_s8_sepiolite.json` — S8 在 sepiolite 通道内的 20 trial 真机优化历史
  （2026-04-13 ~ 2026-05-01，原 `stage1_optimization/campaign_memory/history_db.json`）。
  目标 = combined_score = log10(σ_RT) − 3.0 · Ea_high。
- `s8_sepiolite_campaign_config.json` — 当年 S8 campaign 的 R/N 边界
  （R∈[0, 1.041]、N∈[2.5, 7.006]）与中文 domain_knowledge
  （原 `stage1_optimization/campaigns/s8_sepiolite_campaign.json`）。

## 与 Pillar 1 其它证据的关系

- 文献证据（"先推理后实验"的 motif）：见上层 `../README.md` 中的
  `00_query_packets/`、`04_paper_cards/` 等指针。
- 母系统**实验**证据（"sepiolite AiCE 真的能做出 σ@25 °C ~ 2e-2 S/cm"的样本量级）：
  就是本目录的 20 trial JSON。
- 转化目标（biopolymer-clay membrane motif）：
  见 `stage3_mechanism/outputs/verification/<latest>/04b_design_principles/design_principles.json`。

## 如果未来要把 S8 重新喂给 Stage1

可以让某个 campaign config 的 `storage.history_db` 指向本路径
（相对路径或绝对路径都行），`MemoryManager` 与 BayesianOptimizer 不需要改动。
但要严守一条：**不要把 S8 trial 与 attapulgite trial 混进同一个 history_db**
（campaign_name 校验会拦截，但物理隔离更安全）。
