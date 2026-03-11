# GITHUB_UPLOAD_GUIDE

## 1. 推荐上传策略

如果你的目标是：

- 把当前论文主线整理成一个更清晰的仓库；
- 让 GPT / GitHub 对当前主线代码和文档做分析优化；
- 降低整个大仓库的噪音；

那么推荐的第一选择是：

- **只上传 `close/` 作为单独仓库**

原因：

- `close/` 已经是当前论文和分析的主线；
- 大量旧脚本、旧故事线、临时分析脚本都已经集中清理；
- `close/README.md` 和 `close/PROJECT_MAP.md` 已经能帮助外部模型快速理解结构。

---

## 2. 目前 `close/` 的 GitHub 预处理状态

已完成：

- 已移除 `close/config/api_config.py` 中的真实硬编码 API key
- 已移除 `close/auto_control/modules/report_bundle.py` 中的真实硬编码 API fallback
- 已完成 standalone 化第一轮入口改造：
  - `phase1/run_batch.py`
  - `phase2/run_batch_reports.py`
  - `phase2/run_s8_deep_analysis.py`
  - `phase2/run_s60_deep_analysis.py`
  - `phase3-v2.0/agent.py`
  - `phase3-v2.0/react_agent.py`
  - `phase3-v2.0/run_agent.py`
- 已完成 standalone 化第二轮纸图脚本整理：
  - `paper_figure/generate_all_figures.py`
  - `paper_figure/figure5` 到 `paper_figure/figure16` 主绘图脚本的路径初始化已统一
- 已完成 standalone 化第三轮路径规范化：
  - `auto_control/_path_setup.py`
  - `auto_control/run_closed_loop.py`
  - `auto_control/run_chi.py`
  - `auto_control/chi_parameter_setter.py`
  - `auto_control/temp_controller.py`
  - `auto_control/integrated_workflow.py`
  - `auto_control/main.py`
  - `auto_control/modules/data_analysis.py`
  - `auto_control/modules/rb_fit.py`
  - `auto_control/integrated_temp_chi_controller.py`
  - `phase1/step1_parse_eis.py`
  - `phase2/core/sample_mechanism_generator.py`
  - `utils/__init__.py`
- 已新增：
  - `.gitignore`
  - `.env.example`
  - `ENVIRONMENT_SETUP.md`
  - `GITHUB_PREUPLOAD_CHECKLIST.md`

这意味着：

- 现在的 `close/` 已经明显更适合上传 GitHub；
- 至少不会把当前发现的 `close` 内部真实密钥直接推上去。
- 主入口脚本已经不再优先依赖父目录 `V1_ROOT`。
- `paper_figure` 的主批量绘图脚本也已完成一轮独立路径规范化。
- `auto_control` 和一批剩余辅助脚本也已经收敛到统一的 standalone 路径写法。

---

## 3. 上传前你需要知道的一个关键事实

### `close/` 还不是完全独立运行仓

虽然 `close/` 已经是主线，并且主入口已完成第一轮 standalone 化，但它当前**仍不是完全独立运行仓**。

仍需要继续排查/收尾的点：

- 少量历史文档仍在描述旧状态，需要继续同步。
- 仍有个别历史脚本（例如极旧实验/调试脚本）未纳入统一规范，不影响当前主线但尚未完全收尾。
- 数据、输出、环境变量、硬件依赖（如 `pyautogui`、`serial`）与可复现实验输入，还没有整理成“一键 clone 即运行”的标准分发形态。

所以：

- **用于代码审阅 / GPT 分析 / 论文整理**：只上传 `close/` 是可行的
- **用于别人 clone 后一键运行全部功能**：当前还不够，但环境依赖和分发边界已经补充到 `ENVIRONMENT_SETUP.md`

---

## 4. 最适合上传 GitHub 的 `close/` 内容

建议上传并保留：

- `README.md`
- `PROJECT_MAP.md`
- `CLEANUP_CANDIDATES.md`
- `config/`
- `phase1/`
- `phase2/`
- `phase3/`
- `phase3-v2.0/`
- `auto_control/`
- `specific_conductance/`
- `paper/`
- `paper_figure/`
- `docs/`
- `.gitignore`
- `.env.example`
- `ENVIRONMENT_SETUP.md`

本地保留但默认不建议提交：

- `output/`
- `data/raw_eis/`
- 本地缓存、日志、临时文件

这些已经通过 `.gitignore` 做了默认忽略。

---

## 4.1 环境依赖边界

上传后最容易让人误解的一点是：

- **路径问题** 和 **环境问题** 现在已经不是一回事。

当前主线代码经过前三轮 standalone 化后，主入口和主图脚本的路径逻辑已经明显收敛。  
如果后续有人运行时报错，更可能是下面这些环境原因：

- 缺少 `requests`
- 缺少 `scikit-learn`
- 缺少 `pillow`
- 缺少 `opencv-python`
- 缺少 `pyautogui`
- 缺少 `pyserial`
- 缺少 API key
- 缺少本地 CHI / 串口 / GUI / 硬件环境

详细说明见：

- `ENVIRONMENT_SETUP.md`

---

## 5. 上传后 GPT 能帮你做什么

如果 `close/` 上传到 GitHub，GPT / GitHub 分析最有价值的方向是：

1. **仓库结构优化**
   - 帮你继续把 `close` 切成更清晰的“可运行主线 / 论文图生成 / 历史兼容层”

2. **standalone 化收尾**
   - 继续定位残余的历史依赖、环境依赖与文档偏差
   - 逐步把 `close` 变成真正可独立 clone 运行的仓库

3. **Phase 2 / Phase 3 逻辑统一**
   - 识别 `close/phase2` 与外层老 `phase2` 的重复
   - 继续删掉冗余实现

4. **论文支撑材料整理**
   - 让 `paper/`, `paper_figure/`, `docs/` 之间形成更清晰的引用关系

5. **配置和密钥管理**
   - 进一步把 API / 模型配置收敛到 `.env + .env.example + README` 的规范形式

---

## 6. 如果你还想进一步把 `close` 做成“独立仓库”

后续仍可继续做的操作：

1. 继续审查这些区域：
   - `docs/`
   - 少量极旧历史脚本
   - 环境与安装分发层

2. 当前已完成的收尾重点：
   - 已补齐环境依赖说明
   - 已区分“可本地分析”与“可硬件闭环运行”
   - 已初步梳理独立分发所需的安装说明和输入约束

3. 现在的状态：
   - **前四轮已完成**：主入口、主论文图脚本、`auto_control/`、关键辅助脚本、环境说明与 GitHub 上传边界都已整理
   - **后续重点**：极旧脚本收尾、统一安装文件、进一步标准化发布

---

## 7. 当前建议

如果你现在的目标只是：

- 把当前主线放到 GitHub
- 让 GPT 帮你看代码、看论文支撑逻辑

那我建议你：

1. 直接把 `close/` 作为新仓库上传
2. 暂时不要把整个根仓库一起传
3. 上传后如果还要继续，就做“极旧脚本清理 + 统一安装文件”这一轮

