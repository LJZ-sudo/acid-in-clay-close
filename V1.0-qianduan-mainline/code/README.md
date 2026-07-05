# code 运行辅助层

当前状态日期：2026-05-01

## 定位

`code/` 不是正式 stage 模块，而是运行、回放、转换和 smoke 辅助层。正式模块仍在：

- `stage0_measurement/`
- `stage1_optimization/`
- `stage2_statistics/`
- `stage3_mechanism/`

`code/` 负责把历史 S8 数据与四阶段模块串起来。

## 当前结构与逐文件状态（2026-07-05 核查）

> 判定依据：grep 全仓调用方 + git 最后改动时间。**被 live 后端实际调用的只有
> `process_ao_stage0.py`（及其 import 的 `process_new_materials_stage0.py`）**；
> 其余 stage0/stage2 批处理脚本是历史 S8 一次性工具，保留作回放/复现。

```text
code/
├── shared/
│   ├── paths.py                      # ✅ 现役 · 全仓路径注册表（STAGE3_MECHANISM_DIR 等常量，被多处引用）
│   ├── manifest.py                   # ✅ 现役 · runner manifest 写入工具
│   └── subprocess_utils.py           # ✅ 现役 · 子进程编码/封装工具
├── agent_ops/
│   ├── heartbeat.py                  # ✅ 现役 · Agent 运维心跳
│   └── memory.py                     # ✅ 现役 · Agent 运维记忆辅助
├── stage0_processing/
│   ├── process_ao_stage0.py          # ✅ 现役 · ao（凹凸棒）样品 Stage0 处理，backend_api/samples 经 subprocess 调用
│   ├── process_new_materials_stage0.py # ✅ 现役 · 新材料 Stage0 处理（被 process_ao_stage0 import；亦属 legacy 冻结管线）
│   ├── run_stage0_wrapper.py         # ✅ 现役 · 调 stage0_measurement 的编码包装
│   └── batch_process_s8_final.py     # 📦 历史一次性 · S8 全量批处理（回顾性数据已固化，保留可复跑）
├── stage1_tools/                     # ▶️ 离线联调工具（不在 live 链路，联调/回放在用）
│   ├── run_offline_loop.py           #    一键离线闭环（Stage1 + Virtual Oracle）
│   ├── virtual_oracle.py             #    虚拟 oracle：recipe → 最近邻真实样品
│   ├── initialize_cold_start.py      #    冷启动
│   ├── reset_optimization_history.py #    交互式清史（危险操作，需输入 yes）
│   └── _campaign_paths.py            #    campaign 路径辅助
└── stage2_preprocessing/             # 📦 历史一次性 · S8 → Stage2 CSV 生成（s8_input.csv 已固化）
    ├── run_full_pipeline.py
    ├── batch_extract_eis_features.py
    ├── convert_stage0_to_stage2.py
    └── extract_s8_eis_features.py
```

注：下文历史章节中提到的 `extract_s8_rn_from_excel.py`、`process_s8_with_dta.py` 已不在当前目录（早前清理移除），相关运行说明仅作历史参考。

## Stage1 Replay

默认使用 LLM 最终 recipe 进行 Virtual Oracle 匹配，同时保留 BO 建议作为对照。

```powershell
cd code\stage1_tools
python run_offline_loop.py --iterations 1 --verbose --no-early-stop
```

Virtual Oracle 单独运行：

```powershell
python virtual_oracle.py --use-final-recipe --verbose
python virtual_oracle.py --use-optimizer-suggestion --verbose
```

输出：

- campaign `storage.output_dir/next_experiment_recipe.json`
- campaign `storage.output_dir/last_virtual_oracle_match.json`
- campaign `storage.output_dir/virtual_oracle_manifest.json`
- campaign `storage.output_dir/replay_loop_manifest.json`

## Stage2 Preprocessing

从历史 Stage0 结果生成 Stage2 CSV：

```powershell
cd code\stage2_preprocessing
python run_full_pipeline.py
```

输出：

- `stage2_statistics/data/s8_input.csv`
- `stage2_statistics/data/s8_input.manifest.json`
- `stage2_statistics/data/s8_input.full_pipeline_manifest.json`

## Stage0 历史处理

用于离线历史数据处理，不连接真实设备：

```powershell
cd code\stage0_processing
python batch_process_s8_final.py --dry-run
python batch_process_s8_final.py
```

真实设备在线测量仍应使用 `stage0_measurement/run_online.py`，不要从 `code/` 中直接控制硬件。

## 规则

- `code/` 可以保留长期 runner 和 smoke 辅助脚本。
- 不保留一次性临时脚本。
- 核心算法应放在正式 stage 模块中，`code/` 只调用。
- 每个长期 runner 应输出 manifest，记录输入、输出、hash 和模式。

# Code 目录说明

本目录包含 **Stage0** 数据处理和 **Stage1** 优化辅助脚本。下文路径均以仓库根目录 **`V1.0-qianduan-mainline`** 为当前工作目录（在终端中先 `cd` 到该目录）。

## 目录结构

```
code/
├── stage0_processing/          # Stage0：批量/单样品 EIS 与 Arrhenius 后处理
│   ├── batch_process_s8_final.py       # 批量处理全部 S8 样品（主入口）
│   ├── process_s8_with_dta.py          # 单样品连通性测试（脚本内写死样品名）
│   ├── run_stage0_wrapper.py           # 调用 stage0_measurement 时的编码包装
│   └── extract_s8_rn_from_excel.py     # 从 Excel 提取 R/N，写入 inventory
│
└── stage1_tools/               # Stage1：离线闭环与冷启动辅助
    ├── virtual_oracle.py               # 根据 recipe 匹配最近邻真实样品并写入 demo_stage0_results
    ├── initialize_cold_start.py        # 冷启动：选中位样品并复制到 demo_stage0_results
    ├── run_offline_loop.py             # 循环：Stage1 优化器 + Virtual Oracle
    └── reset_optimization_history.py   # 交互式清空 campaign 历史（需输入 yes）
```

## 运行前准备

1. **Python 环境**：建议使用独立 venv/conda，并在本机已安装可运行的 `python`。
2. **Stage0 依赖**（Rb 拟合、Arrhenius 等）：
   ```bash
   cd stage0_measurement
   pip install -r requirements.txt
   ```
   若在 Windows 上曾出现 **NumPy 2.x 与 SciPy 二进制不兼容**（导入 `scipy`/`numpy` 报错），请固定 NumPy 1.x，例如：
   ```bash
   pip install "numpy>=1.24.0,<2.0"
   ```
3. **Stage1 与 LLM**（运行 `stage1_optimization/run_optimization_loop.py` 或离线闭环时需要）：
   - 在 **`stage1_optimization/.env`** 中配置 API 相关变量（例如 `LLM_API_KEY`；具体键名以 `stage1_optimization/agents/llm_client.py` 为准）。
   - 安装 Stage1 依赖：见仓库根目录说明或 `stage1_optimization` 内 `requirements`/`README`（若存在）。

---

## Stage0：数据处理

### 批量处理（生成/更新 Rb 与 Arrhenius）

在仓库根目录执行：

```bash
cd code/stage0_processing
python batch_process_s8_final.py --dry-run
python batch_process_s8_final.py
```

| 模式 | 作用 |
|------|------|
| **`--dry-run`** | 只扫描并打印将要处理的样品与扫描，**不写文件、不跑拟合**，用于检查路径与清单。 |
| **默认（无 `--dry-run`）** | 对 `data/raw_eis/S8` 下各样品执行转换与分析，结果写入 **`output/stage0_results/<样品>/<扫描>/`**。 |

常用可选参数：

- `--verbose`：更详细的控制台输出  
- `--stop-on-error`：首个失败即停止（便于排错）

**主要输出文件**（每个扫描子目录下）：

- `aggregated_results.json`：各温度点 Rb、电导率等  
- `arrhenius_analysis.json`：Arrhenius 多段拟合结果  

汇总日志：`output/stage0_results/batch_processing_summary.json`。

### 单样品快速测试

用于验证环境与单条流水线是否正常。当前脚本在 **`if __name__ == "__main__"`** 里写死默认样品 `S8-2-1-1`、扫描 `300-120K 3K-min`；换样品需编辑 `process_s8_with_dta.py` 中的 `TEST_SAMPLE` / `TEST_SCAN`。

```bash
cd code/stage0_processing
python process_s8_with_dta.py
```

### 从 Excel 提取 R/N（inventory）

在仓库根目录：

```bash
cd code/stage0_processing
python extract_s8_rn_from_excel.py
```

依赖仓库内 `data/材料数据说明.xlsx`（路径以脚本内配置为准）。典型输出：

- `output/stage0_results/s8_sample_rn.json`  
- `output/stage0_results/s8_sample_rn.csv`  

供批量脚本或 Stage1 样品库使用。

---

## Stage1：优化与离线闭环

Stage1 的**主程序**在 **`stage1_optimization/`**（不在 `code/` 下）。`code/stage1_tools/` 提供冷启动、虚拟样品回放和一键多轮脚本。

### 方式 A：一键离线闭环（推荐用于联调）

在仓库根目录：

```bash
cd code/stage1_tools
python run_offline_loop.py --iterations 10
```

常用参数：

- `--iterations N`：重复 **N** 次「运行 Stage1 → 运行 Virtual Oracle」（**硬上限**；满足早停时会提前结束）。
- `--cold-start`：首轮前先执行 `initialize_cold_start.py --reset`（选中心样品、复制到 `demo_stage0_results`、可选清空历史）。
- `--verbose`：打印子进程完整输出（**可看到 LLM / 贝叶斯等日志**；默认成功时较安静）。
- **早停（默认开启）**：两种判据为 **或** 关系，先满足先停：( **[B]** 连续 **K** 次 Virtual Oracle 命中同一 `result_folder` ，默认 K=3，可调 `--oracle-repeat-patience` )；( **[A]** 连续 **M** 轮全局 `combined_score` 无提升，需 `--score-plateau-rounds M`，默认 M=0 表示关闭 )。**若更在意在线实验语义（只要 A）**：使用 `--no-oracle-early-stop` 并设置 `--score-plateau-rounds`（例如 10）。`--no-early-stop` 关闭全部早停，仅跑满 `N` 轮。

示例：全新一轮实验（冷启动 + 5 轮 + 详细日志）：

```bash
cd code/stage1_tools
python run_offline_loop.py --iterations 5 --cold-start --verbose
```

### 方式 B：手动分步

**1. 冷启动（准备 `demo_stage0_results`）**

```bash
cd code/stage1_tools
python initialize_cold_start.py --reset
```

`--reset` clears the campaign `storage.history_db` selected by `--campaign_config`; attapulgite real history requires an explicit allow flag.

**2. 运行 Stage1 主循环（贝叶斯 + LLM 策略）**

必须在 **`stage1_optimization`** 目录下执行（因为模块导入与相对路径）：

```bash
cd stage1_optimization
python run_optimization_loop.py ^
  --campaign_config campaigns/attapulgite_aice_campaign.json ^
  --stage0_results_dir demo_stage0_results ^
  --output_dir output
```

（Linux/macOS 将 `^` 换为行末 `\`。）

注意：参数名为 **`--stage0_results_dir`**，不是 `--stage0-dir`。

**3. Virtual Oracle（用 recipe 匹配真实样品并覆盖 demo 输入）**

```bash
cd code/stage1_tools
python virtual_oracle.py --verbose
```

**4. 重复步骤 2–3** 即形成「建议 → 回放」闭环。

### 清空优化历史（交互式）

```bash
cd code/stage1_tools
python reset_optimization_history.py
```

按提示输入 **`yes`** 才会删除并备份当前历史；适合在严重重复试验或损坏的 `history_db_attapulgite.json` 后重来。

---

## 样品几何参数（S8 批处理默认）

批量脚本中统一使用（与 `batch_process_s8_final.py` 一致）：

- 厚度 **L**：0.12 cm  
- 电极面积 **S**：3.919348 cm²  

---

## 注意事项

1. **工作目录**：`batch_process_s8_final.py`、`run_offline_loop.py` 等通过 `PROJECT_ROOT` 定位仓库根目录；请在上述说明的目录下启动，不要随意移动脚本路径而不更新代码。  
2. **编码**：Windows 下脚本已对 stdout/stderr 做 UTF-8 处理；若 PowerShell 仍乱码，可尝试 `chcp 65001` 或使用 Windows Terminal。  
3. **Stage0 结果全为 null**：优先检查 NumPy/SciPy 版本与 `stage0_measurement` 能否单独导入并跑通单样品测试。  
4. **离线闭环看不到 LLM 日志**：使用 `run_offline_loop.py --verbose`，或直接进入 `stage1_optimization` 单独运行 `run_optimization_loop.py` 查看完整日志。

## 相关文档

- 仓库总览：`../README.md`  
- Stage0 使用说明：`../stage0_measurement/USER_GUIDE.md`（若存在）  
- Stage1 架构说明：`../stage1_optimization/SDL_ARCHITECTURE_CURSOR_RULE.md`（若存在）  
