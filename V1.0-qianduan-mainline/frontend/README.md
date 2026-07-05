# frontend/ — 驾驶舱前端（React + Vite + Ant Design，端口 5173）

> 结构与逐文件状态文档（生成于 2026-07-05，基于路由表与 import 链核查）。
> 开发：`npm run dev`（vite；`/api` 与 `/socket.io` 代理到 127.0.0.1:8000 后端）。构建：`npm run build`。

## 0. 现役 / 遗留判定核心结论

- **主线 6 页 + 1 详情页为现役生产路由**；
- **7 个 `pages/dev/` 页面由 `config/mainline.js` 的 `ENABLE_DEV_ROUTES` 门控（生产构建为 false）**——整棵 `components/cockpit/`、`workbench/`、`agentOs/`、`agent/`、`live/`、`analysis/`、`demo/`、`runReplay/` 组件树只在 dev 路由下渲染，属于**保留的开发/演示功能**，不是生产死代码但也不在主线；
- 大量旧路径（/dashboard、/cockpit、/thought-chain、/runs/:id 等）保留为重定向别名，防旧书签 404。

## 1. 页面路由（App.jsx）

| 路由 | 页面 | 状态 |
|---|---|---|
| `/`（Home）、`/control`、`/monitor`、`/analysis`、`/report`、`/optimization` | `pages/stage0/`（Home/Control/Monitor/Analysis/Report/Optimization + AIThinkingPanel/GovernancePanel 子面板） | ✅ 现役主线 |
| `/sample/:sampleId` | `pages/SampleClosureCard.jsx`（样品闭环报告卡） | ✅ 现役 |
| `/dev/legacy-overview`、`/dev/agent`、`/dev/analysis`、`/dev/validation`、`/dev/demo`、`/dev/replay/:id`、`/dev/legacy-cockpit` | `pages/dev/`（LegacyOverview/AgentWorkbench/AnalysisHub/ValidationLoopPage/DemoHome/RunReplay/LegacyLiveExperiment） | 🚧 dev 门控（ENABLE_DEV_ROUTES） |
| 其余 20+ 条 | 全部是 Navigate 重定向别名 | ♻️ 兼容层 |

## 2. src/ 结构

```
src/
├─ main.jsx / App.jsx          # ✅ 入口 + 路由表（DevOnly 门控组件在此）
├─ config/
│  ├─ mainline.js              # ✅ ENABLE_DEV_ROUTES 开关（主线/开发功能分界线）
│  └─ paper_outline.ts         # 论文大纲配置（dev 分析页用）
├─ api/                        # ✅ 后端 API 封装层（client.js 为 axios 基座）
│  │  agent / agents / campaigns / control / data / mainAgent /
│  │  provenance / runsAudit / samples / v1Runs.ts(+types)
│  └─ autonomous.js            # ⚠️ 无页面直接 import（经 v1Runs.ts 间接使用）
├─ pages/
│  ├─ stage0/                  # ✅ 现役主线 6 页 + 2 面板
│  ├─ SampleClosureCard.jsx    # ✅ 现役
│  └─ dev/                     # 🚧 7 个 dev 门控页
├─ components/
│  ├─ layout/                  # ✅ MainLayout / Header / Sidebar
│  ├─ common/                  # ✅ 状态徽章、连接状态、语言切换、错误边界等
│  ├─ charts/                  # ✅ Arrhenius / Conductivity / Temperature 图表
│  ├─ campaign/ command/       # ✅ 主线页面使用
│  └─ cockpit/ workbench/ agentOs/ agent/ live/ analysis/ demo/ runReplay/
│                              # 🚧 仅 dev 页引用（含 analysis/validationLoop/）
├─ stores/                     # ✅ zustand：agentStore / dataStore / runEventStore / uiStore / arrheniusRunStore
├─ services/                   # ✅ websocket.js（socket.io 客户端）、sse.js、runEventsStream.js
├─ hooks/                      # ✅ useSystemTruth / useStageOutputLoader / useThoughtChainRefetch / useWiredHitlExplicitApproval
├─ features/runEvents/         # ✅ run 事件流特性模块
├─ analysis/studioPaths.js     # 🚧 dev 分析页路径辅助
├─ i18n/                       # ✅ 中英双语
└─ __tests__/                  # 🧪 node --test 单测
```

## 3. 后端依赖面

主线页面主要调用：`/api/control/*`（启停）、`/api/data/*`（测量与 Arrhenius）、`/api/agent/*`（决策环）、`/api/runs/*`、`/api/samples/*`、`/api/campaigns/*`、`/api/provenance/*`，以及 socket.io 实时通道。dev 页额外调用 `/api/agents/*`、evidence/jobs 系列端点。

## 4. 维护建议

- 判断某组件是否"生产在用"，看它的 import 链是否经过 `pages/stage0/` 或 `SampleClosureCard`；只被 `pages/dev/` 引用的一律视为 dev 门控功能。
- 删除 dev 功能前先确认 `ENABLE_DEV_ROUTES` 的使用场景（内部演示/回放调试仍依赖它）。
