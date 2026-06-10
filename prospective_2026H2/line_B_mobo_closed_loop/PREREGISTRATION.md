# 预注册 · 线 B：真实前瞻 MOBO + LLM 闭环（凹凸棒土）

状态：`DRAFT_TO_FREEZE`（须先完成 §4 两处代码改造，再 commit + push，push 完成前不得开始新一轮合成）
预注册者：JZ
预注册日期：2026-06-08
硬化目标：Pillar 3（Physics/QC-gated EIS-in-the-loop execution）→ B+ 升 A

> 边界（与 objective spec 一致）：本线证明的是**执行层能否在真实前瞻闭环中复现/扩展 电导率–Ea Pareto 前沿**；**不**声称 BO+LLM 发现了 LRS、不声称证明了普适最优。

---

## 1. 目标与规则（逐字取自 `three_pillars/pillar3_eis_in_the_loop/bo_v2_objective_spec_20260527.md`，locked 2026-05-27）

**设计变量**：`R`（酸/水摩尔比）、`N`（液/黏土质量比）。参数空间（来自 campaign）：`R ∈ [0.0, 1.04]`，`N ∈ [0.5, 1.3]`。

**多目标（MOBO 的真正目标，三维）**：

| 目标 | 含义 | 方向 |
|---|---|---|
| `sigma_RT` | 近室温质子电导率 (S/cm) | maximize |
| `Ea_high` | 高温段表观活化能 (eV) | minimize |
| `ea_low_excess` | 低温退化罚项 (eV) | minimize |

**Pareto 规则**：新点为 Pareto 改进，当且仅当 primary set 中无任何旧点在三目标上全部 ≥/≤ 它且至少一项严格更优。

**次级标量（仅作汇总，论文以 Pareto 为主）**：
```text
score_v3 = log10(sigma_RT) - 1.0 * Ea_high - 0.2 * ea_low_excess
```

## 2. 历史集（不可改）

- `full_as_run_audit`：T1–T8（保留全部历史与原始时序）。
- `primary_protocol_consistent_set`：**T2–T8**（排除 T1，因其黏土用量未固定到后续 `1 g attapulgite` 协议）。
- 真实闭环计数（已存在）：`stage1_optimization/output/attapulgite_aice/closed_loop_metrics.json` → `n_closed_loop_rounds=6`，`closed_loop_validity=prospective_real`。
- 诚实基线：`absolute_improvement=0.0`，best 仍为 Trial 1 → **当前未收敛、未"发现"**；本线目的是在多目标下推进 Pareto 前沿，而非翻盘单目标分数。
- primary history 指纹：`primary_history_canonical_sha256=6c598afdeca669fe691b0288426ec380cfbca0a115d57e0bb9befa3f0f9b6d8a`。

## 3. 已锁定的待执行 recipe（取自 bo_v2_locked，locked_before_experiment=true）

| round | 角色 | R | N | 来源 / 状态 |
|---|---|---|---|---|
| v2-R1 | locked_repeat（复测 T5 高电导端点） | 0.5 | 1.2 | `round_01_v2-R1_locked_repeat` |
| v2-R2 | locked_repeat（复测 T7 低 Ea_high 端点） | 0.2 | 1.1 | `round_02_v2-R2_locked_repeat` |
| v2-R3 | raw_bo_suggestion | 0.64 | 1.04 | GP+EI over score_v3，rank1，pred_mean=-1.4226，EI=0.577 |
| v2-R4 | llm/agent guardrail adjusted | 0.64 | 1.02 | 从 rank1 调到 rank3，EI 损失 0.002（可忽略），低于 safe_R≤0.8 / safe_N≤1.15 |

> R1/R2 为重复端点（检验可复现性），R3/R4 为推进点。这些已是 fixed-hyperparameter GP 的**单目标 score_v3** 建议；§4 改造后由真正的 **MOBO** 重新产生 Pareto 驱动的建议。

### 3.1 官方冻结的第一轮 MOBO+LLM 建议（真实闭环实跑，2026-06-08，选项 A）

由 §4 改造后的真实闭环离线复现（脚本 `stage1_optimization/line_b_guardrail_run.py`，只读历史、不写库、不伪造 Stage0）。固定随机种子 `optimizer_seed=20260608` 以保证可复现。

| 角色 | R | N | 来源 / 状态 |
|---|---|---|---|
| 左脑 raw MOBO（ParEGO，seed=20260608） | **0.0285** | **0.9841** | `mode=parego`，scalarization weights≈[0.404, 0.590, 0.006] |
| 右脑 LLM guardrail（实时 OpenRouter `openai/gpt-5.4`，T=0.0） | **0.28** | **0.96** | confidence=0.76，safety_box=`passed`（无 violation/warning 越界） |

**LLM 物理修正理由（实时调用，非事后撰写）**：raw MOBO 的 R≈0.029 在数学上探索超低酸区，但物理上质子供体严重不足，会牺牲室温电导、不利 combined_score；故在维持中等装载 N≈0.96 保证网络连续的前提下，把 R 从超低区上调到**中低酸区 R=0.28**，抑制低温结构断裂 —— 属于对 MOBO 方向的**物理修正而非否定**。

**LLM provenance（写死，便于事后核验，不存 prompt 原文）**：
```text
provider_base_url = https://openrouter.ai/api/v1
model             = openai/gpt-5.4
temperature       = 0.0   max_tokens = 8000
system_prompt_sha256 = 4d2cbb4aa8016684a39d0aa326cb8e762603062629081016e086f70eb5424c0a
user_prompt_sha256   = 2064d73446a8455c7a904551fe145ea61923643312ddd1d7b8d46d048c7d444c
prompt_tokens = 2098   completion_tokens = 651
```

> 这是本线**真实前瞻闭环的第一轮官方 recipe**：raw=MOBO，final=LLM 修正后 `R=0.28, N=0.96`，safety 通过。本块连同代码一并 commit + push 后即获服务器时间戳；**push 完成前不得开始合成该 (R,N)**。

### 3.2 第一轮实测结果 + 官方第二轮 MOBO+LLM 建议（2026-06-10）

**第一轮已合成并实测**（`R=0.28, N=0.96`，样品 `BO-R0.28-N0.96-w96y-1`，EIS 实测 2026-06-10 01:34，CHI660E；几何实测 厚度=0.0783cm、面积=1.96cm²）。Stage0 QC 后入库为 **trial 9**：

| 指标 | 值 |
|---|---|
| σ_RT | 9.43×10⁻³ S/cm |
| Ea_high | **0.0594 eV**（T2–T9 全场最低） |
| ea_low_excess | 0.322 eV |
| KK 通过率 | 0%（`KK_WARN_HIGH` → 仅 screening，冷尾 Ea 留 exploratory） |
| score_v3 | **-2.1494** |
| **Pareto 状态** | **`pareto`（非支配点，扩展了前沿；primary set 前沿 6 点）** |

> 对照 §5 性能阈值：σ_RT 0.0094 ❌ / Ea_high 0.0594 ✅ / ea_low_excess 0.322 ❌ → **未达绝对阈值**（诚实 null）；但在多目标 Pareto 口径下，该点**非支配**、在低 Ea_high 轴上扩展了前沿。两条都如实记录，不得只报其一。
> ⚠ 程序说明：昨晚消化 trial 9、给出下一轮建议的主闭环用的是**冻结的单目标 BayesianOptimizer**（`optimization_mode=bayesian`）；本 §3.2 的 score_v3/Pareto 与下方第二轮建议由**真正的 MOBO（ParEGO）** 复算（`line_b_round2_run.py`，只读、不写库）。

**官方第二轮 MOBO+LLM 建议**（reproducer：`stage1_optimization/line_b_round2_run.py`，固定 `seed=20260610`）：

| 角色 | R | N | 来源 / 状态 |
|---|---|---|---|
| 左脑 raw MOBO（ParEGO，seed=20260610） | **0.2447** | **0.9228** | `mode=parego`，weights≈[0.199, 0.294, 0.507]，pareto_front_size=5 |
| 右脑 LLM guardrail（实时 OpenRouter `openai/gpt-5.4`，T=0.0） | **0.42** | **1.02** | confidence=0.76，safety_box=`passed` |

**LLM provenance**（实时调用，写入 `official_recipe_round2.json`）：`model=openai/gpt-5.4`，`temperature=0.0`，`system_prompt_sha256=4d2cbb4a…`，`user_prompt_sha256=76932a37…`，`prompt_tokens=2100`，`completion_tokens=617`。

> 这是**第二轮官方 recipe**：raw=MOBO `R=0.2447/N=0.9228`，final=LLM 修正后 **`R=0.42, N=1.02`**，safety 通过。本块连同 `official_recipe_round2.json` + `line_b_round2_run.py` 一并 commit + push 后即获服务器时间戳；**push 完成前不得开始合成该 (R,N)**。第一轮记录 `official_recipe.json` 不可改动。

## 4. ⚠ 执行前必须完成的两处代码改造（否则达不到"真实 MOBO+LLM 闭环"）

主闭环现状（已核实）：`run_optimization_loop.py` / `suggest_next.py` 用的是**单目标** `optimizers/bayesian_opt.py`；`optimizers/mobo_optimizer.py` 仅被 `__init__`/测试引用，**未接入**。R4 的 guardrail 是 "Codex GPT-5 coding agent guardrail review"，**非闭环内实时 LLM API 调用**。

**改造 1 — 接入 MOBO ✅ 已完成（2026-06-08，待 commit+push 留痕）**
- `run_optimization_loop.py` 新增模块级工厂 `build_stage1_optimizer(optimizer_kind, ...)`：
  `bo`=冻结单目标 BayesianOptimizer（**默认不变**），`mobo`=MOBOOptimizer(ParEGO)。
- **关键键映射**（否则 ParEGO 取不到历史、全程冷启动）：历史持久化的 Stage0 指标名
  `conductivity_room_temp_S_cm / ea_high_temp_eV / ea_low_excess_eV` → 锁定三目标
  `sigma_RT / Ea_high / ea_low_excess`（见 `MOBO_HISTORY_OBJECTIVE_KEYS`）。
- 新增 CLI：`--optimizer {bo,mobo}`（默认 bo）、`--optimizer_seed`（可复现）。
- `MOBOOptimizer` 补 `get_model_prediction()→None`（多目标无单标量预测，主循环已 `if prediction:` 兜底）。
- 契约测试：`tests/test_stage1_mobo_wiring_contract.py`（4 项全过）证明 mobo 路径返回 ParEGO、
  且在真实 T1–T8 上取到全部 8 条多目标训练点（非单目标 BO、非全程冷启动）；既有 19 项 stage1/mobo 测试无回归。
- 每轮 Pareto/score_v3/provenance 由 `get_provenance()` + 测得目标计算（§6）。

**改造 2 — 真实 LLM guardrail ✅ 已完成（选项 A，2026-06-08，待 commit+push 留痕）**

本次选择：**A（接入真实 LLM API）**。已落地：
- `agents/llm_client.py` 默认改为 **OpenRouter + `openai/gpt-5.4`**（`.env` 为准；
  key 与 `stage3_mechanism/.env` 同一把 OpenRouter key）。向后兼容：改 `.env` 可切回 PoloAPI/DeepSeek。
- 修复真实 bug：`temperature = temperature or env` → 改用 `is None` 判断；否则显式传入的
  `temperature=0.0`（guardrail 确定性温度）会被 `or` 当假值丢弃。主闭环已 `LLMClient(temperature=0.0)`。
- 新增 provenance：`LLMClient.get_provenance()` 记录 `model` + `system/user prompt SHA256`
  + `temperature` + tokens（不存 prompt 原文），用于替换旧 "Codex reviewer guardrail" 出处。
- **实测**：OpenRouter `openai/gpt-5.4` 端到端 HTTP 200、`temperature=0.0`、provenance 正常；
  Stage1 全部契约测试无回归。
- 待办（实验时执行）：把每轮 guardrail 决策的 `llm_client.get_provenance()` 写进该轮
  `llm_guardrail.json`，并把 `model_or_reviewer` 从 "Codex GPT-5 coding agent" 改为
  `openrouter/openai/gpt-5.4`（真实调用记录）。

> ⚠ 遗留项（与本线 guardrail 无关，但同属"还在用 deepseek/polo"）：Stage0 `phase_detect.py`
> 内可能有独立硬编码的 DEFAULT_MODEL（旧 deepseek）。若要全仓统一到 OpenRouter，需另行核对该处。

## 5. 预注册的判定与终止规则（取自 closed_loop_metrics 的 termination v3，事前写死）

**单点 Pareto 判定**：按 §1 Pareto 规则，对 T2–T8 primary set 判定每个新点是否为 Pareto 改进。

**性能阈值（任一新点达到即记为达标候选）**：`sigma_RT ≥ 0.03 S/cm` 且 `Ea_high ≤ 0.10 eV` 且 `ea_low_excess ≤ 0.20 eV`，需 ≥2 个 distinct recipe（归一化距离 ≥0.05）达标。

**收敛等价退出**：最近 5 个样本 best 提升 <0.1 **且** 最近 3 次建议归一化 L2 位移 <0.05 **且** GP 预测 std <0.2（满足 ≥2 项触发）。

**预算兜底**：`max_total_trials=20`（当前 8，余 12）。

> 关键诚信约束：**无论收敛与否都如实报告**。若达预算仍未越过性能阈值/未扩展 Pareto，则结论写为"执行层成功完成 N 轮真实前瞻多目标闭环，但在当前预算/参数空间内未实现 Pareto 扩展"——这仍是 Pillar 3 的有效成果（执行证明 + 诚实 null）。

## 6. 每轮数据产物（append-only，取自 objective spec 表）

每轮必须生成并 append（不覆盖历史）：`history_before` → `raw_bo_suggestion`（→ 改造后为 MOBO Pareto 建议）→ `llm_guardrail`（或 agent/human）→ `human_approval`（hash 绑定、批准时间、批准人、最终 recipe）→ `stage0_result`（raw EIS 路径、处理代码版本、电导表、分段 Arrhenius）→ `manual_rb_qc`（manual/auto/selected Rb、差异、QC tier）→ `score`（`sigma_RT`/`Ea_high`/`ea_low_excess`/`score_v3`/Pareto 状态）→ `history_after`。

## 7. 执行硬门禁（已就绪，复用 execution-engine）

`three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/execution_engine` 已定义：append-only、hash 绑定人工批准、批准前禁写、manual EIS only（自动 CHI 阻断直到 macro/dummy-cell 证据）、raw EIS intake 内容 QC、Stage0 提交门、manual Rb QC、score gate、禁覆盖当前包、无序列证据禁 hysteresis、无高级阻抗 sidecar 禁机制证明。
checker：`three_pillars/pillar3_eis_in_the_loop/v2_engine_tools/run_all_checks.py`（默认 HOLD-biased）。

## 8. 时间锚协议（与线 A 相同，关键）

执行顺序严格为：完成 §4 改造 → 锁定 §3/MOBO 重算的 recipe → **commit + push 到远端拿服务器盖戳** → 才开始合成该 (R,N) → 测 EIS → Stage0/manual Rb QC → score/Pareto gate → append-only history_after → 下一轮。**push 前不得合成。**

## 9. 允许 / 禁止声称（与 objective spec 的 locked statements 一致）

- ✅ 允许："v2 campaign 前瞻性地检验执行层能否复现/扩展 电导/Ea Pareto 前沿"；"T1 保留于 full audit、排除于 primary 分析"；"旧 combined score 未确立完成的优化主张"。
- ❌ 禁止："BO+LLM 发现了 LRS"；"BO+LLM 证明了普适最优"；"事后改分把历史 campaign 变成成功的闭环发现"。

## 10. 留痕（push 后回填）

- [x] §4 选项：改造1+改造2（选项 **A**）完成 commit `6e06793`（首轮 MOBO+LLM 闭环 + 预注册包）
- [x] §3.1 官方第一轮 recipe 冻结 commit hash：`c185379`（含 raw MOBO + LLM guardrail + provenance）
- [x] push 时间（UTC+8）：`2026-06-08T12:53:38+08:00`（远端 `LJZ-sudo/acid-in-clay-close`，分支 `remediation/tier3`）
- [ ] 远端 URL / Zenodo DOI：`__________`（如需公开存档再补 DOI）
- [x] 第一轮实验开始日期（晚于 push 时间 2026-06-08T12:53）：`2026-06-10T01:34`（CHI660E，样品 `BO-R0.28-N0.96-w96y-1`）✅ 前瞻顺序成立

### 第二轮（§3.2，R=0.42/N=1.02）留痕
- [ ] 第二轮冻结 commit hash：`__________`（含 `official_recipe_round2.json` + `line_b_round2_run.py` + 本预注册更新 + trial 9 实测结果）
- [ ] push 时间（UTC+8）：`__________`（远端 `LJZ-sudo/acid-in-clay-close`，分支 `remediation/tier3`）
- [ ] 第二轮实验开始日期（**须晚于上面 push 时间**）：`__________`
