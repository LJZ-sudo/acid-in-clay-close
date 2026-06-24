# P4 — Line-B 闭环回溯回放(retrospective replay)

> 2026-06-21。**真实旧数据,不做新实验,不调 LLM,不编造数字。**
> 对应 `THREE_INNOVATIONS_CODE_GROUNDED_20260618.md` §9 P4 / §5.3 / §3。

## 这是什么

对 **真实 10 点** attapulgite 优化历史(`stage1_optimization/campaign_memory/history_db_attapulgite.json`)
+ 两轮 **已冻结记录** 的官方 recipe(`prospective_2026H2/line_B_mobo_closed_loop/official_recipe*.json`)
做回溯 backtest,**复用项目自己的真实优化器纯函数**
(`optimizers/mobo_optimizer.py` 的 `pareto_front_indices` / `dominated_hypervolume` / `score_v3`)
+ 同核 GP(Matern ν=2.5,与 `MOBOOptimizer` 代理一致)。

运行:`python _new_data_analysis/replay/line_b_replay.py`(确定性,`random_state=0`,可复现)。

## 三个真实结论(诚实 null)

1. **实测 Pareto/HV 轨迹**:Pareto 前沿 1→5、dominated hypervolume 1.0e-3→2.62e-3;
   但 **单目标最优自始至终是 T1(R0.186/N1.029,combined_score=−1.941)**,从未被超越;
   **两轮前瞻(n=9→10)前沿与 HV 都没再增长 → 前瞻轮未扩展 Pareto 前沿**
   (精确匹配 recipe 的 `forbidden_claim`:不得声称 BO+LLM 证明普适最优/事后改分成功)。

2. **代理预测力 backtest(留一未来,combined_score)**:**MAE=0.335 仅略胜 naive-mean 0.384、Spearman=0.21**(7 个 backtest 点)
   → 短轨迹下代理**有但很弱**的预测力,如实报告,不夸大。

3. **raw-MOBO → LLM 修正评估**(用已记录真实冻结值,SHA-256 provenance,不重调 LLM):
   - Round 1:raw MOBO R=0.0285/N=0.9841 → LLM R=0.28/N=0.96 → T9 score=−2.365(在 10 点前沿,未超最优,gap −0.424)
   - Round 2:raw MOBO R=0.2447/N=0.9228 → LLM R=0.42/N=1.02 → T10 score=−2.556(不在前沿,未超最优,gap −0.615)
   - **两轮都没超过 campaign 最优 = 诚实 null**;LLM 把 raw-MOBO 的极低酸点(R≈0.03)在物理上上调到中低酸区(对 BO 方向的物理修正,非否定)。

## 意义

用真实旧数据**验证了闭环逻辑可被回放与审计**,同时**诚实暴露**了"轨迹短(10点/2轮)、代理弱(Spearman 0.21)、前瞻未扩展前沿"——
这正是创新点 3(真实物理↔数字闭环)该有的诚实姿态:**报告执行真实性与可审计性,不声称收敛/Pareto 扩展**。

## 诚实边界

- 回放 ≠ 新实验;LLM 修正用**已冻结记录值**,不假装在线复现 LLM(版本/随机性不可复现)。
- combined_score 为历史真实记录的单目标(v2 公式);多目标视图用项目锁定的 v2 三目标(σ_RT↑、Ea_high↓、ea_low_excess↓)。
- strategy_planner 的 Evidence-Gated 升级(残差 GP + 在线信任)**未做**,属下一篇方法增量。

## 产物

- `replay_report.json` — 三问的全部真实数字。
- `replay_trajectory.png` —(a)实测 Pareto/HV 轨迹;(b)代理 backtest 预测 vs 实测散点。
- `line_b_replay.py` — 可复现脚本(复用项目真实优化器纯函数)。
