# V1.0-qianduan-mainline/ — 主线代码根目录

> 全项目唯一代码之家（2026-07-05 结构收敛后）。运行时 I/O 全部在同级 `../experiments/`
> （raw/ data/ output/ runs/ results/ logs/ prospective/ live/），本目录不放数据与产物。
> 冻结基线：tag `prospective-release-20260705`；pytest 443 passed / 2 skipped；硬件审计 hits=31、autonomous_bypass=0。

## 目录索引（各目录均有自己的 README/结构文档）

| 目录 | 角色 | 文档 | 一句话状态 |
|---|---|---|---|
| `backend_api/` | FastAPI 统一后端（8000） | [README](backend_api/README.md) | 12 文件现役；唯一死代码是 pipeline router（410 占位） |
| `frontend/` | React 驾驶舱（5173） | [README](frontend/README.md) | 主线 6 页现役；7 个 dev 页由 ENABLE_DEV_ROUTES 门控 |
| `stage0_measurement/` | 测量执行 + EIS 分析 | [README](stage0_measurement/README.md) | 46 文件全现役；b_track_live_driver 为主力真机 CLI |
| `stage1_optimization/` | 优化闭环 + SciTX/E-Mem/PC-Skills/C³ | [README](stage1_optimization/README.md) | 91 文件无遗留；botorch MOBO 未接 CLI 开关 |
| `stage2_statistics/` | S8 回顾性统计 → stage3_seed | [README](stage2_statistics/README.md) | 全现役；stage3_seed.json 为受保护产物 |
| `stage3_mechanism/` | 机理推理流水线（S03–S14） | [README](stage3_mechanism/README.md) · [STRUCTURE](stage3_mechanism/STRUCTURE.md) | 唯一遗留：s09b（自标 LEGACY）；4 个冻结发表产物目录 |
| `analysis/` | 研究分析包（原 research/ 代码） | [README](analysis/README.md) | 83 文件无死码；p*/pH* 为里程碑一次性验证 |
| `code/` | 运行辅助层（批处理/离线联调） | [README](code/README.md) | live 后端仅调 process_ao_stage0；S8 批处理为历史一次性 |
| `configs/` | 冻结分析策略 YAML | [README](configs/README.md) | 6 个全现役；4 个 sha256 冻结 |
| `scripts/` | 治理审计 + 冻结报告 | [README](scripts/README.md) | 2 脚本现役；reports/ 为冻结产物 |
| `tests/` | 主线 pytest（36 文件） | [README](tests/README.md) | 含 2 个"文件哈希契约"盯守测试 |

## 全局纪律

1. **行为保持**：任何结构改动后必跑 `python -m pytest -q`（仓库根 443/2；仅主线 409/2）与 `python scripts\audit_hardware_write_paths.py`（hits=31 / bypass=0）。
2. **I/O 出界**：新代码一律读写 `../experiments/`，锚定方式为向上找 `V1.0-qianduan-mainline` 再取 `parent / "experiments"`。唯一保留的例外是 `stage1_optimization/output/`（campaign 配置写死的运行时目录，见其 README §3）。
3. **冻结产物只读**：stage2 exports、stage3 outputs/verification、scripts/reports、campaign_memory 历史库、analysis 的 legacy_freeze_manifest —— 改动即视为篡改证据。
4. **先冻结再跑**：策略/阈值改动先 commit+push 盖时间戳，再跑重算（configs/README.md 铁律）。

## 快速启动

```powershell
cd V1.0-qianduan-mainline
python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000   # 后端
cd frontend; npm run dev                                               # 前端（5173）
python -m pytest -q                                                    # 全量测试
```
