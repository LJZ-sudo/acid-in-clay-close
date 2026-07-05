# 硬件写路径审计报告（direct hardware call report）

- 生成时间：2026-07-05T21:45:16.752985+08:00
- 命中总数：31
- **自主旁路点（应清零）：0**

## 角色分布

| 角色 | 命中数 |
|---|---|
| ADAPTER_SINK | 6 |
| DRIVER_DEFINITION | 2 |
| HARNESS_SHADOW | 3 |
| LEGACY_ONLINE | 15 |
| OPERATOR_MANUAL | 4 |
| TEST | 1 |

## 自主旁路点（AUTONOMOUS_AGENT,绕过 SciTX）

（无）

## 全部命中

| 文件 | 行 | token | 角色 |
|---|---|---|---|
| backend_api/routers/control.py | 166 | hw_start | OPERATOR_MANUAL |
| backend_api/routers/control.py | 258 | hw_stop | OPERATOR_MANUAL |
| backend_api/routers/control.py | 270 | set_temperature | OPERATOR_MANUAL |
| backend_api/routers/control.py | 277 | trigger_measurement | OPERATOR_MANUAL |
| backend_api/services/hardware_adapter.py | 680 | TemperatureDriver_ctor | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 695 | ChiExecutor_ctor | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 1192 | set_temperature | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 1621 | set_temperature | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 4319 | set_temperature | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 4350 | set_temperature | ADAPTER_SINK |
| stage0_measurement/b_track_live_driver.py | 104 | TemperatureDriver_ctor | LEGACY_ONLINE |
| stage0_measurement/b_track_live_driver.py | 106 | ChiExecutor_ctor | LEGACY_ONLINE |
| stage0_measurement/b_track_live_driver.py | 108 | ChiExecutor_ctor | LEGACY_ONLINE |
| stage0_measurement/b_track_live_driver.py | 192 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/run_online.py | 372 | TemperatureDriver_ctor | LEGACY_ONLINE |
| stage0_measurement/run_online.py | 386 | ChiExecutor_ctor | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 586 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 691 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 748 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 774 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 819 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 942 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 945 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 1403 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 1515 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/modules/automation/chi_executor.py | 1037 | ChiExecutor_ctor | DRIVER_DEFINITION |
| stage0_measurement/modules/hardware/temp_driver.py | 267 | set_temperature | DRIVER_DEFINITION |
| stage1_optimization/scientific_harness/action_gate.py | 4 | enqueue_command | HARNESS_SHADOW |
| stage1_optimization/scientific_harness/commit_controller.py | 75 | instrument_dispatch | HARNESS_SHADOW |
| stage1_optimization/scientific_harness/transaction.py | 94 | instrument_dispatch | HARNESS_SHADOW |
| tests/test_stage0_stage1_contracts.py | 213 | ChiExecutor_ctor | TEST |
