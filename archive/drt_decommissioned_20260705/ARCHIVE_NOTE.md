# DRT 模块下线归档（2026-07-05）

## 为什么下线

用户决定：DRT（弛豫时间分布）在本项目数据上已被实测验证**不可行**，不再保留在主线代码中。

实测依据（见 `drt_negative_result/README.md`，基于 lineA LRS 6.15 真实 CHI 谱）：

- 59 个温度点，标准 Tikhonov DRT 重构 **R² 全部 < 0**（范围 [−190.96, −0.18]），0/59 达到 R²>0.8；
- 低频为电极阻塞型大容性尾，超出纯弛豫核的表示能力，截断高频弧也救不回来；
- 模型无关弧顶频率 `f_peak = argmax(−Z'')` 在 57/59 个点无法检测。

结论保持不变：传输侧证据严格限定为 **Rb + σ + 分段 Arrhenius + 转变温**，不声称 DRT 弛豫机理。

## 归档内容

| 路径 | 原位置 | 说明 |
| --- | --- | --- |
| `drt_analysis.py` | `V1.0-qianduan-mainline/stage0_measurement/modules/analysis/algorithms/` | Tikhonov DRT 纯函数算法（原本默认 `run_drt=False` 休眠） |
| `drt_negative_result/` | `V1.0-qianduan-mainline/analysis/drt/` | 负结果验证脚本 `drt_evolution.py` + 产物 `relaxation_evolution.json/.png` + 原 README |

## 主线代码同步改动

- `eis_pipeline.py`：移除 `run_drt` 参数与 DRT 步骤（原默认 False，行为无回归）；`drt_result` 键保留恒为 None 以兼容历史 bundle 消费者。
- `algorithms/__init__.py` / `modules/analysis/__init__.py`：移除 drt_analysis 导出。
- `hardware_adapter.py`：移除 `run_drt=False` 调用参数。
- `closure_features.py`：`_extract_drt_peaks` 的可靠性门（R²>0.8）保留，仅对历史 bundle 生效，继续保证不可靠峰进不了 closure 卡。

历史谱如需复算 DRT，可直接运行本目录内 `drt_negative_result/drt_evolution.py`（需临时把 `drt_analysis.py` 加回 import 路径）。
