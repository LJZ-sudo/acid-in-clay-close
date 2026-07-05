# experiments/ — 全项目输入/输出与证据之家

> 结构文档（2026-07-05）。本目录**不放可维护代码**（唯一例外是 `live/` 联调探针，见下）；
> 所有可维护代码在同级 `V1.0-qianduan-mainline/`。主线代码以
> `V1.0-qianduan-mainline` 向上一级 + `experiments/` 的方式锚定到这里。

## 目录总览

| 目录 | 角色 | 读/写方 | 状态 |
|---|---|---|---|
| `raw/` | 原始仪器数据（新材料/、ao/、raw_eis/、archive/） | stage0 处理与后端 ao 摄入写入；分析只读 | 追加式 |
| `data/` | lineA_*/lineB_* 各批次数据集（aggregated/arrhenius JSON） | `analysis/stage0_v2/raw_loader.py` 发现与加载 | 🧊 基本冻结 |
| `results/` | v2 分析产物（rb_invariance、repro_floor_v2、epistemic_out、p9_stage3_out 等） | `analysis/` 各脚本写；backend sensitivity_jobs 读 | 可再生 |
| `runs/` | 真机 run 证据库（events.jsonl、evidence/、收尾产物；含 fe2/fe3/fe4/fe4b/llmfix 等 12 个 run） | `hardware_adapter` 写；replay/验证脚本读 | 🧊 证据，只追加 |
| `output/` | stage0 bundles / e1_floor / b_track_real / agent_ops | stage0/后端写 | 可再生 |
| `outputs/` | epistemic 临时产物 | epistemic 模块 | 可再生 |
| `logs/` | 后端运行日志（gitignore） | 后端 | 可丢弃 |
| `prospective/` | 前瞻预注册（线 A / 线 B PREREGISTRATION + official_recipe） | 只读；改动=预注册纪律事件 | 🧊 冻结 |
| `three_pillars/` | **三创新点固化证据 + pillar3 执行引擎/门禁**（2026-07-05 自仓库顶层迁入） | 只读证据 + v2_engine_tools 独立 CLI（HOLD 偏置） | 🧊 hash 锁定 |
| `live/` | hw0..hw3 / watch_* 真机联调探针（含串口写，**刻意留在主线硬件审计面之外**） | 人工联调 | 现役工具 |
| `docs/` | PUBLICATION_READINESS、TIER_S 手稿草案、真机联调方案 | 快照文档 | 现役 |
| `scientific_harness/` `scientific_memory/` `scientific_skills/` | 三 Demo（demo_a/b/c、p4/p6 故障报告）的固化输出 | demo 脚本产物 | 🧊 证据 |

## three_pillars/ 说明（迁入后）

```
three_pillars/
├─ pillar1_transfer_agent/       # S8 海泡石母体系（campaign config + 20-trial history，仅作先验，不混入 BO）
├─ pillar2_descriptor_qc/        # 描述符/QC 证据（eis_qc_v2、benchmark_condition_audit、figure_data、tables）
└─ pillar3_eis_in_the_loop/
   ├─ bo_v2_locked/              # 🧊 锁定 campaign + R1–R4 round 包（preflight hash manifest、审批绑定）
   ├─ v2_engine_tools/           # 独立守卫 CLI（run_all_checks 等 10 个工具 + 34 条 pytest；只写自身 out/）
   ├─ v2_phase_b_intelligence_dryrun/  # 🧊 Phase B 干跑冻结记录（run_phase_b_dryrun.py 引用已退役的 codex/ 路径，仅作历史记录，不可直接重跑）
   └─ v2_phase_c_experiment_protocol/  # Phase C 实验协议
```

- 消费方：`code/stage1_tools/_campaign_paths.py`（S8 replay 默认 campaign）、`manuscript/figures/build_*.py`（图数据）、Stage1 优化器文档引用（objective spec）。
- 纪律：bo_v2_locked 与 dryrun 产物为 hash 锁定证据，**任何改写=篡改**；v2_engine_tools 只允许写 `out/`。

## 纪律

1. `runs/`、`prospective/`、`three_pillars/`、三 Demo 产物 = 证据，只读/只追加；
2. `results/`、`output/`、`outputs/` = 可再生产物，重算前先冻结 configs 并 commit+push 盖时间戳；
3. 本目录新增代码一律不允许（工具归 `V1.0-qianduan-mainline/`，联调探针例外须走 `live/` 并保持在审计面之外的自觉）。
