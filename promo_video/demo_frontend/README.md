# FactoryLab 发现闭环 · 演示前端（录屏用）

独立 Vite + React 应用，**完全隔离在 `promo_video/` 内**，不连后端、不碰主线代码。
所有数据来自 `src/data/*.json` —— 从项目真实产物提取的快照（数值未改动）。

## 运行
```bash
cd promo_video/demo_frontend
npm install
npm run dev
# 打开 http://127.0.0.1:5273
# 自动播放（录屏用）：http://127.0.0.1:5273/?autoplay=1
```

## 操作
- 空格：播放 / 暂停
- ← / →：上一幕 / 下一幕
- R：从头重播
- 右上角按钮同上

## 7 幕结构（对应 PROMO_VIDEO_PLAN）
0 钩子 · 1 AIAF OS 闭环总览 · 2 新材料候选（迁移+claim 审计）·
3 物理硬件录屏 · 4 新机理描述符 · 5 闭环+诚实 null · 6 泛化收尾

## 嵌入硬件录屏（ACT3，约 1 分钟）
把录屏文件命名为 `hardware_demo.mp4` 放到：
```
promo_video/demo_frontend/src/assets/hardware_demo.mp4
```
ACT3 会自动嵌入并随播放进度自动播放；无文件时显示占位框。

## 录制建议
- 浏览器全屏（F11），16:9；画布自动按 16:9 居中。
- 用 `/?autoplay=1` 一次性走完；总时长约 3:53（ACT3 固定 60s 给录屏）。
- 中文 AI 配音按 `PROMO_VIDEO_PLAN` 的连读旁白单独生成，后期对轨。

## 数据快照来源
见各 `src/data/*.json` 顶部的 `_source` 字段。
