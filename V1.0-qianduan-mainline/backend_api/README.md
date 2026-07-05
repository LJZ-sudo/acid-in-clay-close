# backend_api/ — 统一 FastAPI 后端（端口 8000）

> 结构与逐文件状态文档（生成于 2026-07-05，基于代码级核查）。
> 启动：`python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000`（在 `V1.0-qianduan-mainline/` 下）。

## 0. 定位

整个系统的唯一后端：REST + Socket.IO 的驾驶舱服务。前身是 Flask(5000)+FastAPI(8000) 双服务，已合并为单一 FastAPI 应用。路由层刻意保持薄——校验/拆包 Pydantic 模型后全部交给 `HardwareAdapter` 单例。

所有 I/O 路径锚定在仓库级 `experiments/`（`PROJECT_ROOT.parent / "experiments" / ...`）：run 证据库在 `experiments/runs/`，stage0 产物在 `experiments/output/`，敏感性分析读 `experiments/results/`。

## 1. 结构与逐文件状态

```
backend_api/
├─ main.py                    # ✅ 现役 · 应用入口：FastAPI + SocketIO 封装、CORS、lifespan、10 个 router 注册
├─ routers/
│  ├─ control.py              # ✅ 现役 · /api/control：启动/停止/暂停实验、人工控制端点（审计角色 OPERATOR_MANUAL）
│  ├─ data.py                 # ✅ 现役 · /api/data：测量历史、Arrhenius 计算、stage1 报告读取（另有 3 个 /api/* 兼容别名）
│  ├─ agent.py                # ✅ 现役 · /api/agent：自主决策环（审计角色 AUTONOMOUS_AGENT），状态存 experiments/runs/_agent_state/
│  ├─ agents.py               # ✅ 现役 · /api/agents：多 Agent 看板（只读）
│  ├─ runs.py                 # ✅ 现役 · /api/runs：run 列表/详情/events.jsonl 流（读 experiments/runs/）
│  ├─ evidence_jobs.py        # ✅ 现役 · 挂在裸 /api 前缀：GET /api/evidence/{id}、POST /api/jobs/threshold_sweep|ablation、报告下载
│  ├─ samples.py              # ✅ 现役 · /api/samples：样品闭环报告卡（读 experiments/output/stage0_results 与 ao_stage0_results；触发 code/ 的 ao 处理）
│  ├─ campaigns.py            # ✅ 现役 · /api/campaigns：campaign 状态 + 官方 recipe（读 experiments/prospective/line_B.../official_recipe.json）
│  ├─ provenance.py           # ✅ 现役 · /api/provenance：git 锚 + LLM 溯源 + 线 B 官方 recipe（只读）
│  └─ pipeline.py             # ⛔ 遗留/已停用 · /api/pipeline：所有 POST 返回 410 Gone；仅为旧前端探针保留不 404（docstring 已自述）
├─ services/
│  ├─ hardware_adapter.py     # ✅ 现役 · ~4700 行核心网关（详见 §3）
│  └─ sensitivity_jobs.py     # ✅ 现役 · threshold_sweep / ablation 任务：读 experiments/results/ 的 v2 分析产物，缺件时给 python -m analysis.stage0_v2.* 提示
└─ tests/                     # 🧪 测试 · 4 个契约测试（campaigns/hardware_adapter/pipeline/sensitivity_jobs），随全量 pytest 收集
```

## 2. API 面速查

| Router | 前缀 | 代表端点 |
|---|---|---|
| control | `/api/control` | POST start / stop / pause、GET status |
| data | `/api/data` | GET measurements、POST calculate_arrhenius（+根级兼容别名 `/api/calculate_arrhenius` 等 3 个） |
| agent | `/api/agent` | 决策环配置/决策记录（decisions.jsonl） |
| agents | `/api/agents` | 多 Agent 状态看板 |
| runs | `/api/runs` | GET 列表、GET {id}、events 流（SSE/WS） |
| evidence_jobs | `/api`（裸） | GET evidence/{id}、POST jobs/threshold_sweep、GET reports/download |
| samples | `/api/samples` | 样品闭环卡、ao 批次处理触发 |
| campaigns | `/api/campaigns` | campaign 状态 + 线 B recipe |
| provenance | `/api/provenance` | 溯源信息（只读） |
| pipeline | `/api/pipeline` | ⛔ 全部 410（已停用） |

注意：`evidence_jobs.py` 没有子前缀，路由直接挂在 `/api` 下，容易误以为在别的模块。

## 3. hardware_adapter.py（核心单例）

`get_hardware_adapter()` 返回模块级单例；`HardwareAdapter.start()` 是全部 50+ 实验参数（含 ESAS-OS opt-in 开关）的唯一入口。职责分块：

1. **硬件网关**：温控串口 + CHI 执行（审计角色 ADAPTER_SINK，6 个写原语命中点）；
2. **测量主循环**：温度序列、点测量、shadow 三重提交；
3. **SciTX 治理**：measurement_txn / instrument witness / commit gate 接入；
4. **run 证据库**：`RUNS_DIR = ../experiments/runs/<run_id>/`（events.jsonl、evidence/、manifest）；
5. **后处理管线**：EIS 分析、Arrhenius、ao 数据摄入（写 `experiments/raw/ao/` 与 `experiments/output/ao_stage0_results/`）；
6. **epistemic 钩子**（opt-in）：`sys.path` 注入 `analysis/` 后导入 `epistemic`（active_design canary、impedance 前向、falsification market、stage3 live 桥）。

## 4. 现役 / 遗留判定汇总

- **现役 12**：main.py + 9 个 router（除 pipeline）+ 2 个 service。
- **遗留 1**：`routers/pipeline.py`（唯一死代码，410 占位；正确的 Stage3 入口是 `python -m s8_stage3.orchestrator.run_stage3`）。
- **测试 4**：`tests/test_*.py`。
