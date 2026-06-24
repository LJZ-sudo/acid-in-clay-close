# M8 — Agent Loop + 排序抹除力 + 跨模型盲评（旁路演示，不碰主线）

> 目的：在 M7（S09 生成阶段：治理 agent 对高频干扰项 0% 采纳）的基础上，把"被治理的 agent"
> 这一主张延伸到**完整 agent 闭环机制**、**S10 排序阶段**、以及**独立模型的盲评**，
> 用于支撑 Pillar 1（evidence-constrained transfer agent）与 Pillar 3（physics/QC-gated 执行）
> 在"系统创新"角度（目标刊：Nature Communications）的说服力。
>
> 纪律：全部在 `m6_baseline_ablation/` 旁路执行，**不写主线库、不改冻结产物、不改预注册**。
> 冻结主线 run（`20260607_openrouter_publication_v2`）当初 S09/S10 是 `deterministic_from_d4`
> （为锁时间戳的有意冻结），这里的实验是**冻结之后的能力演示**，与主线证据严格分层。

---

## 实验一：critic + memory 完整 agent 闭环（produce → critique → revise）

用项目**真实的** agentic 组件（`s8_stage3/agentic/critic.py` + `memory.py`），其中 critic 装载的是
项目自己的反-EIS-过度声称护栏（`claim_guardrails._ABSOLUTE_CLAIM_PATTERNS`：`proves/confirms/establishes/definitively/...`）。

- **naive 臂**（用 style directive 诱导其"把 EIS 当机制证明"，模拟未治理 agent）：
  - round0：critic 抓到 **40 处** overclaim（10×proves / 10×confirms / 10×establishes / 10×definitively）
  - critic 反馈 → LLM 修订 → round1：**0 处**，`converged_clean=true`
- **governed 臂**（项目默认谨慎措辞）：round0 即 **0 处**，无需修订
- **memory**：9 条 episodic 记录（`s09_produce`×2 / `candidate_text`×3 / `s09_revise`×1 / `critique`×3）已持久化到 `m8_agent_loop/memory.json`

**含义**：这不是"LLM 套壳"，而是有 produce→critique→revise 自纠环 + 可审计记忆的真实闭环。
naive 臂的 40→0 收敛**直接演示了护栏在闭环中的纠偏作用**；governed 臂的 0 说明默认策略本身就达标。

> 诚实边界：naive 的过度声称是 prompt **诱导**出来的（为触发 critic 规则），用于演示闭环机制，
> 不代表"未诱导的 LLM 必然以该比例过度声称"。critic 是**词面级**绝对化措辞护栏（治理层），
> 不是语义真值判官。

产物：`m8_agent_loop/{loop_summary.json, memory.json, m_loop_run.log}`，脚本 `m8_critic_memory_loop.py`。

---

## 实验二：S10 排序阶段的抗干扰（真 LLM 排序器）

构造**被污染候选集** = M7 治理 agent 在污染池(A2)生成的 5 个质子导体候选
+ 3 个高显著 off-topic 干扰候选（LiFePO4 电池正极 / 硅负极 / CsPbI3 钙钛矿太阳能）。
交错排列以消除位置偏置，关掉 `s10_deterministic_from_audit`，用**真 LLM S10 排序器**排序。

| 排名 | 类型 | total_score | 候选 |
|---|---|---|---|
| #1 | governed | 0.77 | Starch/PVA/choline chloride–H3PO4 eutectic |
| #2 | governed | 0.76 | Chitosan/PVA/attapulgite/H3PO4 |
| #3 | governed | 0.74 | Chitosan/halloysite/H3PO4 composite |
| #4 | governed | 0.63 | H3PO4 in halloysite nanotubes |
| #5 | governed | 0.62 | Phosphate glass/starch/PVA |
| #6 | **DISTRACTOR** | **0.27** | LiFePO4 battery cathode |
| #7 | **DISTRACTOR** | **0.27** | Silicon Li-ion anode |
| #8 | **DISTRACTOR** | **0.27** | CsPbI3 perovskite solar |

- `all_distractors_below_all_governed = True`
- 均分：governed **0.704** vs distractor **0.27**（≈2.6×）

### 多 seed 统计（M8-2b，5 个 M7 治理候选集 × 逐 seed 重排）

| 指标 | 结果 |
|---|---|
| 干扰项全压制命中率 | **5/5 seed**（每个 seed `worst_governed_rank=5`、`best_distractor_rank=6`） |
| 治理候选均分 | **0.721 ± 0.02** |
| 干扰候选均分 | **0.171 ± 0.05** |
| 分差(mean) | **0.55** |

每个 seed 都是干扰项被整体压到治理候选之下，方差极小（脚本 `m8_s10_multiseed.py`，产物 `m8_s10_multi/`）。

**含义**：治理不仅在**生成阶段**拦住干扰项（M7：0% 采纳），在**排序阶段**也把混进来的干扰项
整体压到底部；且这一行为在 5 个 seed 上**稳定可复现**（命中率 5/5，分差 0.55±极小方差），
不再是单次方向性观察。

产物：`m8_s10/{ranking_summary.json,...}`（单次）+ `m8_s10_multi/s10_multiseed_summary.json`（多 seed），
脚本 `m8_s10_ranking.py` / `m8_s10_multiseed.py`。

---

## 实验三：跨模型盲评（去"自评"嫌疑）

把三类来源候选混合、**匿名（C01…C11）、随机打乱**，交给一个**独立评审模型**按统一 rubric
对"作为冷窗(~182–299 K)质子导体的物理合理性 + 证据接地度"打 1–5 分。**评审看不到来源标签**。

- 生成模型：`openai/gpt-5.4`
- 评审模型：`google/gemini-2.5-flash`（**不同家族，真·跨模型独立评审**）

| 来源 | 平均 plausibility | 平均 groundedness | n |
|---|---|---|---|
| **governed**（M7 治理生成） | **4.0** | **4.8** | 5 |
| random（池内随机组配） | 2.33 | 3.33 | 3 |
| **popularity**（高频组分=干扰项主导） | **1.0** | **1.0** | 3 |

评审对 popularity 候选的判语（独立、未被告知来源）：*"LiFePO4 and silicon anode are Li-ion
battery materials… components from unrelated domains"* —— 准确识别为电池/太阳能 off-topic。

### 多评审 × 多 seed 统计（M8-3b）

把候选来源跨 **3 个 seed**（governed 取 M7 三个 seed、random 重采样、重匿名）混合，
交给 **2 个跨家族独立评审模型**（`google/gemini-2.5-flash` + `meta-llama/llama-3.3-70b-instruct`，
均 ≠ 生成模型 gpt-5.4）。共 2 judge × 3 seed = 6 组合。

| 来源 | plausibility (mean±std) | groundedness (mean±std) | n 打分 |
|---|---|---|---|
| **governed** | **4.30 ± 0.64** | **4.97 ± 0.18** | 30 |
| random | 2.06 ± 0.71 | 2.22 ± 1.08 | 18 |
| **popularity** | **1.00 ± 0.00** | **1.00 ± 0.00** | 18 |

按评审分项（plausibility 均值），两个独立模型一致同序：

| 评审模型 | governed | random | popularity |
|---|---|---|---|
| google/gemini-2.5-flash | 4.07 | 1.78 | 1.00 |
| meta-llama/llama-3.3-70b | 4.53 | 2.33 | 1.00 |

> 评审池里 `anthropic/claude-3.5-sonnet`、`x-ai/grok-2-1212` 在该 key 上 404 不可用，
> `deepseek/deepseek-chat` 当时被上游限流（429）；最终落到 2 个跨家族评审，已足够交叉验证。

**含义**：在去掉"agent 给自己贴了标签的输出打分"这一嫌疑后，**两个异构模型、3 个 seed 一致**给出
governed ≫ random ≫ popularity，且 popularity（干扰项主导）被两个评审在所有 seed 上都打到
**地板分 1.0（零方差）**。这把"治理带来真实质量差异"的结论从"同模型单次自评"加固到
"多模型多 seed 盲评"，带均值±标准差。

产物：`m8_blind/{...}`（单次） + `m8_blind_multi/{blind_multi_summary.json, blind_multi_records.json, console.txt}`（多评审多 seed），
脚本 `m8_blind_eval.py` / `m8_blind_multi.py`。

---

## 对论文（NC 系统创新口）的增量

把 Pillar 1 的"被治理的迁移 agent"主张做成了**三阶段、可证伪、可复现**的证据链：

1. **生成阶段**（M7）：治理 agent 对注入的高频干扰项 **0% 采纳**；popularity 基线全军覆没。
2. **排序阶段**（M8-2）：真 LLM 排序器把混入的干扰项整体压到底部（0.704 vs 0.27）。
3. **独立盲评**（M8-3）：跨模型(gemini-2.5-flash)匿名打分 governed 4.0 / random 2.33 / popularity 1.0。
4. **闭环机制**（M8-1）：critic+memory 的 produce→critique→revise 真实自纠（40→0）+ 可审计记忆，
   回答"它到底算不算 agent"——harness/critic/memory 都是已实现、已测试的真组件，这里给出 live 演示。

## 诚实边界（必须随报告一起写进论文/附录，不得省略）

- 全部为**冻结之后的旁路演示**，**不属于**预注册的冻结主线 run；与主线证据分层，未改任何主线产物。
- 已补统计：S10 排序做了 **5 seed**（命中率 5/5，gov 0.721±0.02 vs dis 0.171±0.05）；
  盲评做了 **2 跨家族评审 × 3 seed**（n=30 governed 打分）。M7 生成阶段的 5-seed 统计见
  `M7_FULL_ABLATION_REPORT.md`。三阶段现在都有重复，不再是单次方向性观察。
- 仍属**小规模 + 单候选池**证据：每 seed governed 5 / distractor·random 各 3；评审模型只有 2 个
  （claude/grok 该 key 不可用、deepseek 被限流）。结论稳健但不主张大样本统计功效。
- critic 为**词面级**绝对化措辞护栏，非语义真值判官；naive 过度声称为 prompt 诱导以触发护栏。
- 不声称"发现 LRS"、不声称收敛、不事后改分——与 §6 claim 护栏一致。

## 复现入口

```bash
# 1) critic+memory 闭环
python m6_baseline_ablation/m8_critic_memory_loop.py
# 2) S10 排序抗干扰（单次 + 多 seed 统计）
python m6_baseline_ablation/m8_s10_ranking.py
python m6_baseline_ablation/m8_s10_multiseed.py
# 3) 跨模型盲评（单次 + 多评审×多 seed 统计）
python m6_baseline_ablation/m8_blind_eval.py
python m6_baseline_ablation/m8_blind_multi.py
```
（密钥读 `key.txt` 第一行；LLM 经 OpenRouter，gen=gpt-5.4 /
judges=gemini-2.5-flash + llama-3.3-70b）
