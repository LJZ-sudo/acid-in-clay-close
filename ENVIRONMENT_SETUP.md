# ENVIRONMENT_SETUP

## 1. 目标

这份文档用于说明 `close/` 在 GitHub 上传后的运行边界：

- 哪些功能只需要基础 Python 科学计算环境；
- 哪些功能需要 LLM / API Key；
- 哪些功能需要本地 GUI 自动化与硬件环境；
- 哪些“运行失败”是环境依赖缺失，而不是代码路径问题。

---

## 2. 推荐 Python 版本

- 推荐：`Python 3.10` 或 `Python 3.11`
- 最低建议：`Python 3.8+`

---

## 3. 分层环境说明

### 3.1 最小分析环境

适用范围：

- `phase1/run_batch.py`
- `phase2/run_batch_reports.py`
- `phase2/run_s8_deep_analysis.py`
- `phase2/run_s60_deep_analysis.py`
- `phase3/run_all.py`
- `phase3-v2.0/run_agent.py`
- `paper_figure/` 下大多数绘图脚本

建议安装：

```bash
pip install numpy pandas matplotlib scipy scikit-learn requests
```

说明：

- 这是最适合 GitHub 代码审阅、GPT 分析、论文图复现的基础环境。
- `close/phase3/requirements.txt` 当前也覆盖了其中一部分核心依赖。

### 3.2 图像与 GUI 辅助环境

适用范围：

- `auto_control/run_chi.py`
- `auto_control/chi_parameter_setter.py`
- `auto_control/integrated_workflow.py`
- `auto_control/integrated_temp_chi_controller.py`
- 一些需要模板识别或截图的自动化脚本

建议额外安装：

```bash
pip install pillow opencv-python pyautogui
```

说明：

- `pyautogui` 依赖真实桌面会话，不适合纯服务器/无头环境。
- 这类脚本通常默认在 Windows 本地桌面环境下运行。

### 3.3 串口 / 硬件控制环境

适用范围：

- `auto_control/main.py`
- `auto_control/temp_controller.py`
- `auto_control/integrated_temp_chi_controller.py`

建议额外安装：

```bash
pip install pyserial
```

说明：

- 这部分不仅需要 Python 包，还需要：
  - 本机串口可用；
  - 温控设备驱动正常；
  - CHI 软件与测量流程可在本机实际执行。

### 3.4 API / LLM 环境

适用范围：

- `phase2/*.py`
- `run_phase2_complete.py`
- `phase3-v2.0/react_agent.py`
- `auto_control/modules/report_bundle.py`

需要环境变量：

```bash
OPENROUTER_API_KEY=
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
```

可选环境变量：

```bash
OPENROUTER_MODEL=anthropic/claude-opus-4.5
FALLBACK_MODEL=anthropic/claude-3.7-sonnet
```

说明：

- 这些变量的模板已经写在 `.env.example`。
- 如果不做 LLM 调用，只做本地数据分析和论文图复现，可以不配置这些 key。

---

## 4. 推荐安装方式

### 4.1 仅做 GitHub 分析 / 论文图复现

```bash
python -m venv .venv
.venv\Scripts\activate
pip install numpy pandas matplotlib scipy scikit-learn requests
```

### 4.2 需要运行 `paper_figure/` 和部分自动化脚本

```bash
pip install pillow opencv-python
```

### 4.3 需要运行完整 `auto_control/`

```bash
pip install pyautogui pyserial
```

---

## 5. 已验证的环境边界

在当前仓库整理过程中，已经明确验证过：

- `auto_control/run_closed_loop.py` 的导入可以通过；
- `auto_control/modules/data_analysis.py` 的导入可以通过；
- `phase2/core/sample_mechanism_generator.py` 的导入可以通过；
- `paper_figure/figure16/plot_entropy_enthalpy_schematic.py` 可以运行；
- `paper_figure/figure4_model_comparison/plot_figure4_comparison.py` 可以运行。

同时也明确发现：

- `auto_control/run_chi.py` 若缺少 `pyautogui` 会导入失败；
- `auto_control/main.py` 若缺少 `serial`（`pyserial`）会导入失败。

这些属于**环境依赖缺失**，不是 standalone 路径改造失败。

---

## 6. GitHub 上传前的现实建议

如果你的目标是：

- 让 GPT / GitHub 继续分析和优化代码；
- 让别人理解系统结构；
- 复现论文图和大部分分析流程；

那么当前推荐做法是：

1. 上传 `close/` 主代码与文档。
2. 不强求在 GitHub 上“一键跑通硬件闭环”。
3. 把硬件相关脚本明确视为“需要本地 Windows + GUI + 串口 + CHI 软件”的专用层。

---

## 7. 仍未完全标准化的部分

- 仓库根目录还没有统一的 `pyproject.toml`
- 也没有覆盖全仓的单一 `requirements.txt`
- `auto_control/` 中仍有少量极旧历史脚本未纳入主线规范
- 数据输入、输出样例、硬件模板图片和本地实验路径仍偏“研究原型”风格

所以当前更准确的定位是：

- **适合上传 GitHub 做分析、整理、论文协作**
- **适合继续收敛成独立仓库**
- **但还不是标准化发布版软件包**
