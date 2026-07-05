# archive/ — 历史/被取代产物归档（行为保持型重构，2026-07-05）

> 本目录存放**已被取代但需保留历史的产物**。全部经 `git mv` 迁入（保留历史），
> 迁移前已核查：**无任何现役代码 import / 读取这些路径**（仅文档文本提及）。
> 本目录内容**只读**——不修改、不删除、不被主线代码引用。

## 归档清单与取代关系

| 归档路径 | 原位置 | 被谁取代 / 归档原因 |
|---|---|---|
| `_new_data_analysis/repro_floor/` | `_new_data_analysis/repro_floor/` | v1 复现地板分析 → `stage0_v2/repro_floor_variance.py`；直接地板产物见 `V1.0-qianduan-mainline/output/e1_floor/LINE_B_LOCAL_DIRECT.json` |
| `_new_data_analysis/repro_floor_v2/`（如后续迁入） | 同名 | 过渡 stub，正式实现已在 `stage0_v2/` |
| `_new_data_analysis/identifiability/` | `_new_data_analysis/identifiability/` | v1 可辨识性 demo → `identifiability_v2/` + `stage0_v2/identifiability_v2.py` |
| `_new_data_analysis/lineB_R0.42/` | 同名 | 无日期旧批 → `lineB_R0.42_6.11/`（June 重测为准） |
| `_new_data_analysis/MANUSCRIPT_BLUEPRINT.md` 等 DD 四件套 + `PRESUBMISSION_REVIEW.md` | `_new_data_analysis/` | 2026-06-21 DD 稿系 → live 目标为 `TIER_S_MANUSCRIPT_DRAFT_20260622.md` + `PUBLICATION_READINESS.md` |
| `_new_data_analysis/p1_governance_smoke.py` / `p1_memory_verify.py` | `_new_data_analysis/` | 早期 Phase-1 smoke → 高编号 p 系列 / pH 系列覆盖 |
| `V1.0-qianduan-mainline/codex/` | 同名 | 2026-06-08 一次性审计快照（零运行时读取）；`scripts/audit_mainline.py` 会按需重新生成 `codex/`（该目录现已 gitignore） |
| `manuscript/report_ppt/` | 同名 | 预手稿阶段 PPT（lab-meeting 用），无现役引用 |
| `m6_baseline_ablation/_*.py / _*.txt` | `m6_baseline_ablation/` | throwaway 探针/scratch 脚本与输出 |
| `drt_decommissioned_20260705/` | `stage0_measurement/.../drt_analysis.py` + `analysis/drt/` | DRT 实测不可行（59/59 点重构 R²<0），用户决定下线；负结果证据一并保存 |
| `report_deck_20260705/` | `analysis/figures/` + `analysis/analysis_scripts/build_pptx.py` | 预手稿阶段汇报 deck 与概念草图 → 正式图表管线在 `manuscript/figures/` |

## 同期入口收敛（非归档，但同一次重构）

- `_new_data_analysis/b_track_live_driver.py` → **收编至** `V1.0-qianduan-mainline/stage0_measurement/b_track_live_driver.py`，
  定为唯一 CLI 全温区 live driver（路径解析已改为 `Path(__file__)` 相对，行为不变）。
