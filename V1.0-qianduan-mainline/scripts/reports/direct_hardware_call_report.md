# 硬件写路径审计报告（direct hardware call report）

- 生成时间：2026-06-24T09:40:24.412612+08:00
- 命中总数：27
- **自主旁路点（应清零）：0**

## 角色分布

| 角色 | 命中数 |
|---|---|
| ADAPTER_SINK | 6 |
| DRIVER_DEFINITION | 2 |
| HARNESS_SHADOW | 3 |
| LEGACY_ONLINE | 11 |
| OPERATOR_MANUAL | 4 |
| TEST | 1 |

## 自主旁路点（AUTONOMOUS_AGENT,绕过 SciTX）

（无）

## 全部命中

| 文件 | 行 | token | 角色 |
|---|---|---|---|
| stage0_measurement/run_online.py | 365 | TemperatureDriver_ctor | LEGACY_ONLINE |
| stage0_measurement/run_online.py | 379 | ChiExecutor_ctor | LEGACY_ONLINE |
| tests/test_stage0_stage1_contracts.py | 213 | ChiExecutor_ctor | TEST |
| backend_api/routers/control.py | 124 | hw_start | OPERATOR_MANUAL |
| backend_api/routers/control.py | 205 | hw_stop | OPERATOR_MANUAL |
| backend_api/routers/control.py | 217 | set_temperature | OPERATOR_MANUAL |
| backend_api/routers/control.py | 224 | trigger_measurement | OPERATOR_MANUAL |
| backend_api/services/hardware_adapter.py | 581 | TemperatureDriver_ctor | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 596 | ChiExecutor_ctor | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 1024 | set_temperature | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 1423 | set_temperature | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 2750 | set_temperature | ADAPTER_SINK |
| backend_api/services/hardware_adapter.py | 2781 | set_temperature | ADAPTER_SINK |
| stage0_measurement/controllers/online_workflow.py | 586 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 691 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 748 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 774 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 819 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 942 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 945 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 1403 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/controllers/online_workflow.py | 1515 | set_temperature | LEGACY_ONLINE |
| stage0_measurement/modules/automation/chi_executor.py | 845 | ChiExecutor_ctor | DRIVER_DEFINITION |
| stage0_measurement/modules/hardware/temp_driver.py | 267 | set_temperature | DRIVER_DEFINITION |
| stage1_optimization/scientific_harness/action_gate.py | 4 | enqueue_command | HARNESS_SHADOW |
| stage1_optimization/scientific_harness/commit_controller.py | 75 | instrument_dispatch | HARNESS_SHADOW |
| stage1_optimization/scientific_harness/transaction.py | 94 | instrument_dispatch | HARNESS_SHADOW |
