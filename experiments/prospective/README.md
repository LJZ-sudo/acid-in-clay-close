# prospective_2026H2 — 前瞻升级预注册包

生成日期：2026-06-08
目的：把"LLM 先给结果、再做实验"从**事实**升级为**可向怀疑型审稿人证明的不可篡改证据**。
对应分析见 `../THREE_PILLARS_ANALYSIS_AND_WRITING_PLAN_20260608.md` Part D。

本包含**两条互不替代的并行线**：

| 线 | 文件 | 硬化的创新点 | 优化/验证的轴 |
|---|---|---|---|
| **线 A** | `line_A_biopolymer_transfer/PREREGISTRATION.md` | Pillar 1（迁移）+ Pillar 2（描述符） | 选哪个材料家族（LRS / 玉米淀粉 / CHITO） |
| **线 B** | `line_B_mobo_closed_loop/PREREGISTRATION.md` | Pillar 3（执行引擎） | 凹凸棒土体系内配方 R/N 的多目标闭环 |

---

## ⚠ 核心纪律：冻结 → push 盖戳 → 再动手（两条线都必须遵守）

**这是过去"做对了却证不硬"的唯一缺口。** 本地文件/git 的时间戳作者可改，审稿人默认不认；只有**远端服务器盖戳**才不可篡改。

### 标准操作（每条线开始实验前各做一次）

```powershell
# 1. 确认预注册文件已写好、排名/recipe 已锁死、不再改动
cd C:\Users\JZ\Desktop\paper\acid-in-clay-close

# 2. 提交
git add prospective_2026H2/
git commit -m "preregister: freeze <line A|B> ranking/recipe before experiments (2026-06-08)"

# 3. 关键一步——推到远端拿服务器时间戳（GitHub）
git push origin <branch>

# 4.（强烈建议）再向第三方公证：把该 commit 的快照上传 OSF 或 Zenodo，拿一个带日期的 DOI
#    Zenodo / OSF 的时间戳是独立第三方，效力高于自有 GitHub
```

### 三条铁律
1. **push 完成之前，不得开始任何合成 / EIS 测量。** 顺序错了，整条线的前瞻性作废。
2. **预注册后不修改排名/recipe。** 实验结果只能通过 append-only 的 S13 binding / history_after 追加，不能回改预测。
3. **报告所有已合成候选，不挑结果。** 失败/边界样品也要写进论文或 SI——这正是预注册的价值，也是审稿人信任的来源。

### 留痕清单（实验后回填到各线 PREREGISTRATION.md 末尾）
- 预注册 commit hash + push 时间（`git log -1 --format=%H,%cI`）
- 远端 URL / Zenodo DOI（如有）
- 实验开始日期（应晚于 push 时间）

---

## 两条线与现有冻结证据的关系

- **线 A 锚点**：复用已存在的权威冻结排名
  `V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2/11_candidate_registry/prospective_candidates.json`
  （run_id `stage3-1842d1f1ea`，`registry_hash=6bd73a12…`，`preregistered_at=2026-06-07T11:57:12Z`，live LLM / cache off / `term_leakage_penalty=0`）。
  **不要**混用旧的重建锚 `data/validation/timing_reference_registry.json`（那是另一次旧 run，给 4–5 月旧实验用的）。

- **线 B 锚点**：复用已锁定的 v2 round 协议
  `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/`（objective spec + R1–R4 locked recipes + execution-engine 硬门禁）。
  线 B 在执行前还需完成两处代码改造（见线 B 文件 §4），否则只是"单目标 BO + reviewer guardrail"，达不到"真实 MOBO+LLM 闭环"。
