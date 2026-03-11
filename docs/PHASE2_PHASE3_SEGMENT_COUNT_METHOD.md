# Phase 2 与 Phase 3 的 segment 统计差异说明（方法/SI 用）

**目的**：说明 Phase 2 材料级深度报告中的“segment 数/样品数”与 Phase 3 的 `integrated_data` 行数为何可能不同，以及是否需要在论文中对比说明二者差距。

---

## 一、差异来源

| 统计对象 | Phase 2 | Phase 3 |
|----------|---------|---------|
| **数据来源** | 直接从各 phase1 JSON 的 `arrhenius.segments` 读取 | step1 从 phase1 JSON 读取 segments，**无分段时**对单样品做全温区 Arrhenius 拟合，生成 **1 行** 代表该样品（fallback） |
| **无分段样品** | 不纳入统计（该样品在材料级报告中无 segment 行） | 纳入：每个无分段样品在 integrated_data 中占 **1 行** |
| **典型结果** | segment 数 = 仅“有分段”样品的各段之和 | 行数 = 上述 segment 数 + 无分段样品的个数 |

因此：**同一批 phase1 文件下，Phase 2 的 segment 总数 ≤ Phase 3 的 integrated_data 行数**，差值 = 无分段样品数量（每个最多贡献 1 行）。

---

## 二、当前数据下的数量对比（参考）

在 close 当前 `output/phase1_results` 与 `output/phase3_results/integrated_data.csv` 下：

- **Phase 2 方式**（仅 `arrhenius.segments`）：segment 总数 **232**，至少有一个 segment 的样品数 **71**。
- **Phase 3 方式**（integrated_data）：总行数 **239**，不同样品数 **78**。
- **差值**：239 − 232 = **7** 行，对应 7 个在 Phase 2 下“无 segment”的样品在 Phase 3 中各有 1 行（fallback）。

结论：**两者差距很小**（约 3%），全部来自“无分段样品”的 fallback；对限域分析、ML–AI 验证等结论无实质影响。

---

## 三、论文中建议的表述（方法或 SI）

- **差异说明**：在方法或 SI 中可简要写明：
  - “材料级深度报告（Phase 2）的 segment 统计仅基于 phase1 中具有 Arrhenius 分段的样品；Phase 3 建模与验证所用的 segment 级数据在无分段时对单样品做全温区拟合并计为 1 行，以便将无分段样品纳入跨材料验证等分析。”
- **是否需要单独对比说明“两者没有很大差距”**：**不必**。当前差值仅 7 行（7 个无分段样品），占比小；若审稿人问起，可引用本说明文档或上述一句表述即可。若希望更保守，可在 SI 加一句：“Phase 2 与 Phase 3 的 segment/行数差异仅来自无分段样品的不同处理方式，数量差异在 3% 以内，对主要结论无影响。”

---

## 四、小结

| 项目 | 说明 |
|------|------|
| **差异原因** | Phase 2 无 fallback，Phase 3 对无分段样品生成 1 行。 |
| **数量关系** | Phase 3 行数 = Phase 2 segment 数 + 无分段样品数。 |
| **当前差距** | 7 行（约 3%），无需在正文中单独做“两者没有很大差距”的对比分析。 |
| **方法/SI** | 建议用一句话说明二者统计口径差异及来源即可。 |
