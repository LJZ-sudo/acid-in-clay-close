# Stage1 Optimization：AiCE 双脑配方规划层

当前状态日期：2026-06-07

## 1. 阶段定位

`stage1_optimization` 是 attapulgite AiCE 真机闭环的配方优化与下一步实验规划层。它读取 Stage0 结果目录，提取宽温域 EIS / Arrhenius 指标，写入 campaign memory，再由贝叶斯优化器给出数学建议，并由 LLM 策略规划器结合物理约束生成下一轮 recipe。

**当前主线（且唯一）campaign** 是 `attapulgite_aice_campaign`，使用真实 Stage0/Stage1 history：`campaign_memory/history_db_attapulgite.json`。S8/sepiolite 母系统证据已于 2026-06-07 迁出本目录，归档到 `three_pillars/pillar1_transfer_agent/s8_acid_in_clay_mother_system/`，作为 Pillar 1 transfer agent 的母证据使用，**不再进入 Stage1 任何代码路径**。

## 2. 当前真实目录结构

```text
stage1_optimization/
├── run_optimization_loop.py
├── suggest_next.py                       # 单次推荐入口（不写库）
├── rebuild_closed_loop_metrics.py        # 确定性 metrics 重建
├── requirements.txt
├── .env.example
├── .env                                  # 本地密钥文件，不要提交/传播
├── SDL_ARCHITECTURE_CURSOR_RULE.md
├── __init__.py
├── campaigns/
│   └── attapulgite_aice_campaign.json
├── canonical_input/
│   ├── campaign_parser.py
│   ├── design_space.py
│   └── state0_parser.py
├── campaign_memory/
│   ├── memory_manager.py
│   ├── history_db_attapulgite.json       # 当前 AiCE real history（唯一）
│   └── MANIFEST.md
├── optimizers/
│   ├── base_optimizer.py
│   ├── bayesian_opt.py                   # 冻结主线（单目标 GP+EI）
│   └── mobo_optimizer.py                 # v2 prospective 多目标，独立于冻结闭环
├── agents/
│   ├── llm_client.py
│   ├── strategy_planner.py
│   └── prompts/
│       ├── planner_prompts.py
│       ├── planner_system.md
│       └── planner_user_template.md
├── contracts/
│   └── next_experiment_schema.py
├── safety/
│   └── safety_validator.py
├── closed_loop/
│   ├── round_logger.py
│   ├── metrics_aggregator.py
│   └── termination_evaluator.py
└── output/
    ├── MANIFEST.md
    └── attapulgite_aice/
        ├── next_experiment_recipe.json
        ├── closed_loop_metrics.json
        └── closed_loop_rounds/
```

旧文档中提到的 `README.md`、`PROJECT_SUMMARY.md`、`example_usage.py` 不存在，不再作为事实源。`s8_sepiolite_campaign.json`、`history_db.json`、`campaign_memory/{archive,backups}/`、`output/archive/20260518_legacy_s8_root_output/` 已于 2026-06-07 移除/迁出，请参考 `three_pillars/pillar1_transfer_agent/s8_acid_in_clay_mother_system/`。

## 3. 当前执行链

```text
campaign JSON
→ State0Parser 解析 demo / Stage0 风格结果
→ MemoryManager 写入 history_db
→ BayesianOptimizer 生成 optimizer_suggestion
→ StrategyPlanner 构建 prompt
→ LLMClient 调用模型
→ NextExperimentRecipe 校验
→ campaign storage.output_dir/next_experiment_recipe.json
```

## 4. 当前 campaign

当前主线（且唯一）campaign：

- `campaigns/attapulgite_aice_campaign.json`
- 设计变量：`R`、`N`
- 目标：`combined_score`
- 公式：`math.log10(conductivity_room_temp_S_cm) - 3.0 * ea_high_temp_eV - 0.5 * ea_low_excess_eV`
- 当前仍是单目标标量化，不是 Pareto/MOBO（MOBO 实现见 `optimizers/mobo_optimizer.py`，定位为 v2 prospective 旁支，独立于冻结闭环）。

历史 reference（不再属于 Stage1）：

- S8 sepiolite 母系统的 campaign config + 20 trial history 已迁出本目录，归档至
  `three_pillars/pillar1_transfer_agent/s8_acid_in_clay_mother_system/`。
- 当前 Stage1 代码路径中**没有任何 .py 文件读取 S8 history**；`attapulgite_aice_campaign.json` 的
  `transfer_reference` 字段是 declarative marker，仅供 Pillar 1 写作/论证引用。

## 5. 当前已知问题

1. `next_experiment_recipe.json` 已包含最小 provenance；后续仍可继续扩展 prompt hash / model version 的审计粒度。
2. LLM prompt 仍由 Python 字符串内联构建，不利于版本化和审稿。
3. LLM 对 BO 建议的修改只在终端摘要中显示，未结构化写入 JSON。
4. 当前只有 campaign 参数边界校验，没有独立的 chemistry safety box。
5. `run_optimization_loop.py` 的旧命令说明提到 `OPENAI_API_KEY`，但实际使用 `LLM_API_KEY/LLM_BASE_URL/LLM_MODEL`。
6. MOBO / Pareto 前沿仍未作为当前主线实现，后续可作为科研增强。

## 6. 本轮优化目标

先做低风险、可复现、可投稿的结构性升级：

1. 增加 `--mode replay|virtual_oracle|real` 和 `--source_tag`。
2. 在 recipe metadata 中写入 `source_mode`、`source_tag`、`stage0_real_device`。
3. `BayesianOptimizer` 暴露 `get_provenance()`。
4. Prompt 外置为 `.md` 模板并记录 sha256。
5. 输出 `optimizer_vs_llm_delta`。
6. 增加 `SafetyValidator`，在落盘前做硬约束/警告。

## 7. 环境变量

Stage1 使用 `agents/llm_client.py` 读取：

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `LLM_TIMEOUT`

请参考 `.env.example`。不要在文档或代码中写入真实密钥。

## 8. 当前推荐运行方式

```powershell
cd <repo-root>\V1.0-qianduan-mainline
python stage1_optimization\run_optimization_loop.py ^
  --campaign_config stage1_optimization\campaigns\attapulgite_aice_campaign.json ^
  --stage0_results_dir output\ao_stage0_results\<ao-folder> ^
  --db_path stage1_optimization\campaign_memory\history_db_attapulgite.json ^
  --output_dir stage1_optimization\output\attapulgite_aice ^
  --mode real ^
  --source_tag attapulgite_aice
```

## 9. 修改规则

- 优化器层只做数学和 provenance，不写物理解释。
- Agent 层只做物理解释和参数审查，不直接训练优化器。
- Prompt 应放在 `agents/prompts/*.md`。
- 所有输出必须能说明是 replay、Virtual Oracle 还是真实设备。
- 一次性脚本和临时测试代码不保留。

