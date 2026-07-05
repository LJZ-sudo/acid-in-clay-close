# stage0_measurement/ — 测量执行与 EIS 分析层

> 结构与逐文件状态文档（生成于 2026-07-05，基于代码级核查）。
> 结论：**本目录没有死文件**——46 个 .py 全部现役（个别文件内含休眠方法，见 §4）。

## 0. 定位与架构约定

Stage0 负责：温控 + CHI660E 电化学工作站驱动、EIS 谱采集、KK 校验、Rb 拟合、Arrhenius 分析、闭环特征提取。

架构铁律：`modules/` 层是纯函数（无 print、无全局状态、无副作用），业务编排只放 `controllers/`；真实硬件写路径被硬件审计（`scripts/audit_hardware_write_paths.py`）盯死，全部命中点见 §3。

## 1. 结构与逐文件状态

```
stage0_measurement/
├─ b_track_live_driver.py       # ✅ 现役 · 主力真机 CLI（B 轨 live 驱动，2026-07 采用；审计类别 LEGACY_ONLINE）
├─ run_online.py                # ✅ 现役 · 在线入口（保留角色；已知首扫 bug，phase detector 为占位 stub）
├─ run_offline.py               # ✅ 现役 · 离线复算入口（读已有 CHI 数据重跑分析）
├─ run_closure_offline.py       # ✅ 现役 · 闭环特征离线提取入口
├─ config.py                    # ✅ 现役 · 环境变量（STAGE0_CHI_DATA_DIR 等）与路径配置
│
├─ controllers/
│  ├─ online_workflow.py        # ✅ 现役 · 在线主编排（内含休眠方法 _run_main_cooling_loop）
│  ├─ offline_workflow.py       # ✅ 现役 · 离线编排
│  └─ state_manager.py          # ✅ 现役 · 运行状态机
│
├─ modules/
│  ├─ analysis/
│  │  ├─ eis_pipeline.py        # ✅ 现役 · 单点 EIS 分析总管（analyze_eis_point）
│  │  ├─ data_quality.py        # ✅ 现役 · 数据质量门
│  │  ├─ evidence_admission.py  # ✅ 现役 · 证据准入（configs/evidence_admission_v2.yaml）
│  │  ├─ phase_detect.py        # ✅ 现役 · LLM 相变检测 Agent（OpenRouter gpt-5.2）
│  │  └─ algorithms/
│  │     ├─ rb_fitting.py       # ✅ 现役 · Rb 多方法拟合（主证据路径）
│  │     ├─ kk_validation.py    # ✅ 现役 · KK 校验（3.2.0 起故意为 warning-only，不作硬熔断）
│  │     └─ arrhenius.py        # ✅ 现役 · Arrhenius/断点拟合
│  │        （drt_analysis.py 已于 2026-07-05 下线 → archive/drt_decommissioned_20260705/）
│  ├─ automation/
│  │  ├─ chi_executor.py        # ✅ 现役 · CHI 执行器（真机写原语；三层防御：窗口守卫→宏救援→新鲜度守卫）
│  │  ├─ chi_window_guard.py    # ✅ 现役 · CHI 窗口守卫
│  │  └─ chi_macro_rescue.py    # ✅ 现役 · CHI 宏救援
│  ├─ hardware/
│  │  ├─ temp_driver.py         # ✅ 现役 · 温控驱动（真机写原语：__init__ / set_temperature）
│  │  └─ monitor.py             # ✅ 现役 · 温度监控
│  ├─ io_utils/
│  │  ├─ chi_parser.py          # ✅ 现役 · CHI .txt 谱解析（被 analysis/、experiments/live 广泛复用）
│  │  ├─ dta_parser.py          # ✅ 现役 · Gamry DTA 解析
│  │  ├─ persistence.py         # ✅ 现役 · 结果持久化
│  │  ├─ result_bundle.py       # ✅ 现役 · 结果包 schema
│  │  └─ run_manifest.py        # ✅ 现役 · run manifest 写入
│  ├─ closure/
│  │  ├─ closure_agent.py       # ✅ 现役 · 样品闭环报告 Agent
│  │  ├─ closure_features.py    # ✅ 现役 · 闭环特征提取
│  │  └─ closure_schema.py      # ✅ 现役 · 闭环 schema
│  └─ reporting/
│     └─ plotter.py             # ✅ 现役 · 绘图
│
└─ rb_act/                      # ✅ 现役 · R0-R4 激活阶梯（当前只跑 R0 影子，rb_r4_active 硬编码 False，不碰生产值）
   ├─ activation.py / features.py / prereg.py / schema.py
   ├─ shadow.py / skill.py / synthetic.py
```

## 2. 入口对照

| 入口 | 角色 |
|---|---|
| `b_track_live_driver.py` | **当前主力真机 CLI**（qualification run 用它）；审计分类 LEGACY_ONLINE |
| `run_online.py` | 在线入口（历史主力，保留；首扫描存在已知 bug；`create_phase_detector()` 是显式 no-op 占位） |
| `run_offline.py` / `run_closure_offline.py` | 离线复算/闭环提取 |
| backend_api | 不直接跑这些 CLI，而是经 `hardware_adapter` 复用 modules/ 与 controllers/ |

## 3. 硬件审计命中点（不可随意改动）

- `TemperatureDriver.__init__` / `set_temperature`（modules/hardware/temp_driver.py）
- `ChiExecutor.execute_measurement`（modules/automation/chi_executor.py）
- backend_api 侧的 `enqueue_command`
- 审计基线：hits=31，`autonomous_bypass=0`（LLM/Agent 无直达硬件路径）

## 4. 已知休眠/占位（文件现役、局部不用）

- `online_workflow._run_main_cooling_loop`：死方法，不在当前调用链。
- ~~`drt_analysis.py`~~：已于 2026-07-05 下线归档（实测 DRT 不可行，R² 全部 <0）→ `archive/drt_decommissioned_20260705/`。
- `run_online.create_phase_detector()`：占位 stub，真 LLM 检测在 `phase_detect.py`。
