# Close项目 Paper 文档目录

**项目定位**: Agent驱动的闭环自主EIS分析平台  
**目标期刊**: Advanced Materials / Nature Communications  
**更新日期**: 2026-02-09 v2

---

## 核心文档（按用途排列）

| 文档 | 用途 | 谁使用 |
|-----|------|--------|
| **[GPT_PAPER_WRITING_PACKAGE.md](./GPT_PAPER_WRITING_PACKAGE.md)** | GPT论文写作包(配合4张主图) | **→ 提供给GPT** |
| [INTEGRATED_SYSTEM_GUIDE.md](./INTEGRATED_SYSTEM_GUIDE.md) | 完整技术指南(v2.0, 893行) | 自己参考/深入了解 |
| [SI_COMPLETE_GUIDE.md](./SI_COMPLETE_GUIDE.md) | SI材料状态跟踪 | 准备投稿材料 |

## SI材料

| 目录 | 内容 | 数量 |
|------|------|------|
| [SI_figure/](./SI_figure/) | SI图像(已有22张+待补3张) | 22 png |
| [SI_table/](./SI_table/) | SI表格(8张)+主论文表格(2张)+SI Notes(4份) | 14 files |
| [SI_reports/](./SI_reports/) | 网页报告+提示词+Agent日志+评分标准 | 8 files |

## 前端Agent系统文档（合作方提供）

| 文档 | 内容 |
|-----|------|
| [FRONTEND_AGENT_GUIDE_PART1.md](./FRONTEND_AGENT_GUIDE_PART1.md) | 多Agent架构, Planner-Critic, 数字-物理桥接 |
| [FRONTEND_AGENT_GUIDE_PART2.md](./FRONTEND_AGENT_GUIDE_PART2.md) | Orchestrator状态机, Evidence Package |
| [FULL_PROJECT_WRITING_GUIDE.md](./FULL_PROJECT_WRITING_GUIDE.md) | AM投稿写作指南 |

## Close分析系统文档

| 文档 | 内容 |
|-----|------|
| [CLOSE_PROJECT_ANALYSIS_REPORT.md](./CLOSE_PROJECT_ANALYSIS_REPORT.md) | Phase 1/2/3详细流程 |
| [DATA_FLOW_AND_DEPENDENCIES.md](./DATA_FLOW_AND_DEPENDENCIES.md) | 数据流与模块依赖 |
| [QUICK_START_GUIDE.md](./QUICK_START_GUIDE.md) | 快速启动 |

---

## 使用GPT写论文的步骤

### 第一步：生成初稿
1. 上传 **GPT_PAPER_WRITING_PACKAGE.md** + **4张主图**
2. 告诉GPT: "请根据这份写作指导和4张图片，为我撰写一篇面向Advanced Materials的Research Article初稿"

### 第二步（可选）：深化特定章节
- 深化Methods → 追加上传 `SI_Note1/2/4`
- 深化Agent推理 → 追加上传 `SI_Agent_execution_log.json`
- 深化Discussion → 追加上传 `INTEGRATED_SYSTEM_GUIDE.md`

### 不需要给GPT的
- Phase 2机理报告（中间产物，已整合进最终报告）
- 传统Pipeline JSON（与主图有微小差异，避免混淆）
- 旧版文档（已被INTEGRATED_SYSTEM_GUIDE取代）

## 标有[PLACEHOLDER]的内容

在 `SI_Note3_experimental_methods.md` 中，以下内容需要用真实数据替换：
- 电化学工作站型号和参数
- 温控设备型号和精度
- 样品制备方法
- Python/软件版本
- 通信协议细节
