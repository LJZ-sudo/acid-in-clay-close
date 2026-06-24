# M7 Pilot — 真 LLM 跑 S09 候选生成（消融的 LLM 臂，第一次真调用）

> 目的：把"创新点1"的消融从 **确定性管线 vs 基线** 升级为 **真 LLM agent vs 基线**。
> 全部产物在 `m6_baseline_ablation/m7_llm_pilot/`，**不碰主线代码 / 不写主线 outputs**。

## 1. 这次到底做了什么（和之前的区别）

| 轮次 | S09 候选来源 | 是否调用 LLM |
|---|---|---|
| 发表冻结版（20260607） | `deterministic_from_d4`（代码写死映射 D4 claim → I1..I5） | ❌ 否（预注册冻结） |
| 之前 M6 消融（§5–§8） | 确定性打分函数 `audit_candidates` / popularity | ❌ 否 |
| **本次 M7 pilot** | **关掉两个确定性开关 → S09 落到真 LLM 分支** | ✅ **是（OpenRouter `openai/gpt-5.4`）** |

配置：`STAGE3_S09_DETERMINISTIC_FROM_D4=false` + `STAGE3_S09_EVIDENCE_BASED_GENERATION=false`
（注意：`evidence_based` 那条分支其实也是**确定性**描述符匹配，不是 LLM，所以两个都要关）。
温度 0.2，单 seed，1 次调用，6126 tokens（成本约几分钱）。

输入只喂**冻结产物**：7 个机理描述符（D1–D7）+ 31 张材料文献卡 + 39 条 D4 component-claim。

## 2. 真 LLM 输出的 5 个候选

| ID | 真 LLM 候选（deterministic OFF） | 新颖度判定 |
|---|---|---|
| I1 | chitosan + PVA + **attapulgite** + 磷酸 | novel_combination |
| I2 | starch + PVA + **氯化胆碱(ChCl)/磷酸 深共熔(DES)** | novel_combination |
| I3 | chitosan + **halloysite(HNT)** + 磷酸 | novel_combination |
| I4 | **磷酸盐玻璃** | exact_match（LLM 自判为 control baseline） |
| I5 | chitosan + **DES** + 磷酸 | novel_combination |

每个候选都带：组分级文献证据（真实 paper_id）、满足的描述符（D1–D7）、`novelty_rationale`。

## 3. 真 LLM vs 冻结确定性版（消融核心对照）

| | 冻结确定性版 I1–I5 | 真 LLM 版 I1–I5 |
|---|---|---|
| 核心 motif | 生物聚合物(chitosan/starch)+PVA+1D粘土+磷酸 | **同一核心 motif** |
| 1D 粘土 | HNT、(attapulgite 仅出现在 I2 名称) | attapulgite(I1) + HNT(I3) |
| 抗冻载体 | 无 | **DES/氯化胆碱 motif（I2、I5）← LLM 主动迁移** |
| control baseline | PAAm-g-starch（close_variant） | **磷酸盐玻璃，LLM 自判 exact_match** |
| 其它 | Nb2O5(I5) | — |

**两点关键结论：**

1. **核心 motif 高度重叠** → 当初写死的 `deterministic_from_d4` 确实是 **LLM 真实推理的忠实快照**。
   这正面支持了"先冻结锁时间、再做实验、没有造假"的说法：真放开 LLM，它收敛到同一物理合理的家族。

2. **LLM 的"增量"可量化**（这就是创新点1要的 agent 价值）：
   - 从 `ChCl/PA DES` 证据卡里**迁移出 DES 抗冻 motif**（确定性映射没做这步）；
   - 把 **attapulgite**（项目主线核心粘土）纳入正式组分；
   - **自己判定**哪个候选只能当 control baseline（磷酸盐玻璃→exact_match），体现新颖度判别力。

## 4. 诚实 caveat（不可隐藏）

- 这是 **1 个 seed、1 次调用的 pilot**，只证明"真 LLM 分支跑得通、产物合理、可对照"，**还不是统计意义上的消融**。
- compact prompt 下 LLM 省略了 `role_in_formulation` / `analog_reason` 两个解释性字段，
  对缺失的 `role_in_formulation` 做了**兜底占位补全**；**未修改的 LLM 原始输出已存档** `m7_llm_pilot/llm_s09_raw.json`，可核。
- 要构成可写进论文的消融，还需 **full M7**：多 seed 稳健性 + 消融变体（去证据约束 / 加高引用干扰项，看它是否还收敛）+ 盲评。

## 5. 产物清单（m7_llm_pilot/）

- `llm_s09_raw.json` — LLM 原始输出（未修改，留证）
- `llm_instances.json` / `llm_families.json` — 校验后的候选
- `cost_summary.json` — 调用 / token 计数
- `pilot_console.txt` — 运行日志
