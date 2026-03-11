# 使 Close 成为独立文档/项目的方案分析

**目标**：让 `close/` 能够以“独立”方式使用（尽量不依赖父项目 `V1.0-qianduan` 或其它外部目录），同时**不改变 close 当前在父项目中的行为**。  
**当前状态（2026-03 第四轮后）**：已不再只是“方案 D（仅文档独立）”。  
- **第一轮**：主入口脚本 `phase1/run_batch.py`、`phase2/run_batch_reports.py`、`phase2/run_s8_deep_analysis.py`、`phase2/run_s60_deep_analysis.py`、`phase3-v2.0/agent.py`、`phase3-v2.0/react_agent.py`、`phase3-v2.0/run_agent.py` 已改为优先使用 `close/` 内部模块。  
- **第二轮**：`paper_figure/generate_all_figures.py` 与 `figure5` 到 `figure16` 主绘图脚本已统一为显式 `SCRIPT_DIR / PAPER_FIG_DIR / CLOSE_ROOT` 路径初始化方式，减少独立仓使用时的路径脆弱性。  
- **第三轮**：`auto_control/` 主入口、分析模块与剩余关键辅助脚本已收敛到统一的 standalone 路径写法，并新增 `auto_control/_path_setup.py` 作为共享初始化入口。  
- **第四轮**：环境依赖说明、GitHub 上传边界和“本地分析 vs 硬件闭环”区别已补充到 `ENVIRONMENT_SETUP.md` 与 `GITHUB_UPLOAD_GUIDE.md`。  
一站式说明见 **`docs/CLOSE_STANDALONE_README.md`**、**`ENVIRONMENT_SETUP.md`**。

---

## 一、当前“不独立”的点

### 1.1 代码依赖（运行脚本时）

| 依赖项 | 使用位置 | 说明 |
|--------|----------|------|
| **主入口脚本中的 `V1_ROOT` 依赖** | `phase1/run_batch.py`、`phase2/*.py`、`phase3-v2.0/*` | **第一轮已处理**。这些主入口已切换为优先使用 `close/` 内部模块，不再把父目录作为默认优先导入源。 |
| **`specific_conductance`** | `phase1/run_batch.py` | `close/specific_conductance/` 已存在，且第一轮已改为从 `close/` 内部解析。 |
| **`auto_control.modules`** | `phase1/run_batch.py` | `close/auto_control/modules/` 已存在，第一轮已改为从 `close/` 内部解析。 |
| **`config.api_config`** | `phase2` 多个脚本 | 已统一改为使用 `close/config/api_config.py`。 |
| **历史文档和辅助脚本** | `docs/`、少量历史脚本、极旧实验脚本 | **仍需少量收尾**。主要问题已从“主线入口依赖父目录”转为“个别旧脚本和安装分发方式尚未完全标准化”。 |

### 1.2 文档依赖（阅读/使用指南时）

- **CLOSE_PROJECT_GUIDE_PART2** 接续 PART1；**COMPREHENSIVE** 与 PART1+PART2 对应。
- 文档内代码块为示意，可执行逻辑在 close 仓库的脚本中，需与“代码依赖”一起考虑才能独立运行。

---

## 二、方案概览

在**不破坏现有行为**（在 V1.0-qianduan 内运行一切照旧）的前提下，可选思路有四类：

1. **独立发行包（Standalone Bundle）**：不改 close 仓库本身，单独做一个“close 独立版”发行包。  
2. **close 内 vendor + 路径优先级**：在 close 内增加“自包含依赖”，通过路径优先级实现独立，未提供时行为与现有一致。  
3. **环境/配置开关（Standalone 模式）**：用环境变量或配置开关切换“父项目模式”与“独立模式”。  
4. **仅文档与使用方式独立**：不追求 Phase 1 在无父项目下可跑，只把文档和 Phase 2/3 的使用方式说清楚，便于“只拿 close”的读者复现 Phase 2/3。

下面分别展开，并说明对“close 现状”的影响及是否需要改代码。

---

## 三、方案 A：独立发行包（不改 close 仓库）

**思路**：保持当前 close 仓库**一行不改**。单独做一个“close 独立版”的发行物（如 zip/另一个 repo/CI 产出的包），内容 = close + 拷贝进来的 `specific_conductance`（及必要时 `config`、`auto_control` 子集）+ **仅在该发行包内**存在的少量补丁（如只在该包内改 path 逻辑），使该包内脚本只认 close 与包内依赖。

**优点**：  
- close 主仓库**零改动**，现状完全不受影响。  
- 独立用户只需下载“独立版”即可运行，不依赖父项目。

**缺点**：  
- 需要维护两套：主仓库 vs 独立发行包（或打包脚本）。  
- 独立包内的“补丁”需要随 close 或 specific_conductance 的变更而更新。

**对 close 现状的影响**：无。  
**是否需要改 close 内代码**：不需要；改的是“发行包”里的副本或打包脚本。

---

## 四、方案 B：close 内 vendor + 路径优先级（最小改代码）

**思路**：  
1. 在 close 内增加目录，用于“自包含依赖”，例如 `close/vendor/specific_conductance/`（通过拷贝或 submodule 从父项目取得，或由文档说明“若需独立运行请放置于此”）。  
2. 在 **Phase 1 / Phase 2 的入口脚本**中做**最小改动**：在加入 V1_ROOT 之前，先判断“若 `CLOSE_ROOT/vendor/specific_conductance` 存在，则把 `CLOSE_ROOT/vendor` 和/或 `CLOSE_ROOT` 插入到 path 最前”，再按现有逻辑插入 V1_ROOT。这样：  
   - **有 vendor**：优先用 close 内 vendor，不依赖父项目即可跑 Phase 1。  
   - **无 vendor**：行为与现在完全一致，仍用 V1_ROOT 下的 specific_conductance。

**优点**：  
- 同一套 close 仓库既可嵌入父项目用，也可在“拷贝好 vendor 后”单独用。  
- 改动集中、可读性好（仅 path 顺序与条件判断）。

**缺点**：  
- 需要一次性的小改动（若干行 path 逻辑）。  
- vendor 内容需文档说明如何取得/更新（拷贝脚本或 submodule 等）。

**对 close 现状的影响**：在未提供 vendor 的机器上行为与现在一致。  
**是否需要改 close 内代码**：需要，但仅限“路径优先级”的少量逻辑。

---

## 五、方案 C：环境/配置开关（Standalone 模式）

**思路**：通过环境变量（如 `CLOSE_STANDALONE=1`）或 close 内配置文件（如 `config/standalone.json`）声明“独立模式”。各入口脚本在开头：若为独立模式，则**不**把 V1_ROOT 加入 `sys.path`，仅使用 CLOSE_ROOT 及 close 内 vendor；否则保持现有逻辑。

**优点**：  
- 行为由显式开关控制，易于理解和调试。  
- 与方案 B 类似，可共用同一套 vendor 目录。

**缺点**：  
- 需要在一处或多处入口读配置/环境变量并分支。  
- 若用户忘记设开关，在“只有 close”的环境下会直接报错，需在文档中写清楚。

**对 close 现状的影响**：默认不设开关时与现在一致。  
**是否需要改 close 内代码**：需要，读配置/环境变量并分支 path。

---

## 六、方案 D：仅文档与使用方式独立（不改代码）

**思路**：不追求在“无父项目”时跑通 Phase 1，只把“close 能独立到什么程度”写清楚，并让文档与 Phase 2/3 的使用方式自洽、可独立阅读和复现。

**具体做法**：  
1. **文档**：在 `CLOSE_DOCS_AND_CODE_DEPENDENCY.md` 或新文档中明确写出：  
   - Phase 3 在已有 `phase1_results`（及 step4 所需 S8 报告）的前提下，**仅依赖 close 自身**即可复现。  
   - Phase 2 在 close 内已配置 `config/api_config.py` 时，从 close 目录运行即可，不依赖“其它文档”。  
   - Phase 1 当前依赖父项目下的 `specific_conductance`，若需“完全独立”的 close，需采用方案 A/B/C 之一。  
2. **使用方式**：提供“仅用 close + 已有数据”的复现流程（例如：给定 `phase1_results` 压缩包 + close 代码，如何从 Phase 2/Phase 3 跑起），使审稿人或合作方在**不接触父项目**的情况下也能复现 Phase 2/3。  
3. **指南文档**：如需“单文档阅读”体验，可增加一份 **CLOSE_STANDALONE_README.md**，把 PART1+PART2 中与“仅 close + 已有数据”相关的章节摘成一条龙说明，并注明“Phase 1 需父项目或见方案 A/B/C”。

**优点**：  
- **零代码改动**，close 现状完全不受影响。  
- 文档与使用方式独立，便于“只拿 close”的读者理解边界和复现能力。

**缺点**：  
- Phase 1 仍无法在无父项目环境下跑通，真正“代码级”独立只到 Phase 2/3。

**对 close 现状的影响**：无。  
**是否需要改 close 内代码**：不需要。

---

## 七、对比与建议

| 方案 | 是否改 close 代码 | 对现状影响 | Phase 1 独立运行 | 文档/使用独立 |
|------|-------------------|------------|------------------|----------------|
| **A. 独立发行包** | 不改主仓库 | 无 | 在独立包内可以 | 可一并提供独立文档 |
| **B. vendor + 路径优先级** | 少量 path 逻辑 | 无 vendor 时同现状 | 有 vendor 时可以 | 可配合文档说明 |
| **C. 环境/配置开关** | 读配置/环境变量 | 默认同现状 | 开关+vendor 时可 | 可配合文档说明 |
| **D. 仅文档与使用方式** | 不改 | 无 | 不可以 | 是（Phase 2/3 + 说明） |

**建议**：  
- 若**近期不想动代码**：优先做 **方案 D**，并可在文档中注明“若将来需要 close 完全独立，可采用方案 A 或 B”。  
- 若**接受一次最小改动**：在方案 D 基础上增加 **方案 B**（vendor + 路径优先级），即可在不影响现状的前提下，让“拷贝好 vendor 的 close”单机独立运行。  
- 若**希望主仓库零改动、只做发行**：采用 **方案 A**，用脚本或 CI 生成“close-standalone”包。

---

## 八、若采用方案 B 的后续实施要点（供将来改代码时参考）

- **涉及文件**：`phase1/run_batch.py`，以及 Phase 2 的 `run_s8_deep_analysis.py`、`run_batch_reports.py`、`run_s60_deep_analysis.py`（若希望独立模式下只用 close 的 config，可在此做 path 优先级）。  
- **逻辑**：在现有 `sys.path.insert(0, V1_ROOT)` 之前，若存在 `CLOSE_ROOT / "vendor" / "specific_conductance"`，则先 `sys.path.insert(0, str(CLOSE_ROOT / "vendor"))` 和/或保证 `CLOSE_ROOT` 在 path 前部，再按原样插入 V1_ROOT。  
- **vendor 内容**：至少需包含父项目中的 `specific_conductance` 包（与 run_batch 中 import 的模块一致）；是否把 `auto_control.modules` 也拷入 vendor 或继续使用 close 内 `auto_control`，需按实际 import 解析结果决定。  
- **文档**：在 README 或 `CLOSE_DOCS_AND_CODE_DEPENDENCY.md` 中说明“独立运行：将 specific_conductance 置于 close/vendor/ 下，见 docs/CLOSE_STANDALONE_OPTIONS.md”。

---

**说明**：目前已经完成**代码级 standalone 化第一轮**，不再是“未对 close 仓库做任何代码修改”的状态。后续若需进一步做到更接近“一键 clone 运行”，可继续实施方案 A/B/C，或做第二轮文档与辅助脚本收尾。
