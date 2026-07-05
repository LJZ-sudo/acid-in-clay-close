# 图件计划（acid-in-clay 子刊稿）

> 目的：定稿前明确**要哪些图、为什么要、现在能不能画、用什么工具、数据在哪**。
> 主线（每张图都必须为它服务）：**证据约束的迁移智能体，把"酸-黏土"质子传导原理迁移到生物聚合物–黏土膜；
> 用冷却韧性描述符做正/边界验证；用 QC 门控的 EIS-in-the-loop 真实执行——三支柱由"数字世界↔物理世界"的
> 可审计闭环串起。** 不为主线服务的图一律不收。

工作流：**示意图** → GPT 生成草图 → 放进 PPT 精修升级；**数据图** → 用 Origin 从 CSV 重画（投稿级）。

---

## 一、总览表

| 图 | 类型 | 服务的主线 | 现在能画? | 工具 | 位置 |
|---|---|---|---|---|---|
| **Fig 1** 架构/智能体工作流 | 示意 | **全主线**（数字↔物理闭环 + 治理）旗舰图 | ✅ 现在 | GPT→PPT | 正文 |
| **Fig 2** 分级证据 + 确定性主张审计 | 示意 | 方法学内核（claim 受审计） | ✅ 现在 | GPT→PPT | 正文 |
| **Fig 3** 宽温 σ(T) | 数据 | Pillar 2 描述符 + Pillar 1 结果（LRS/CHITO/淀粉） | ✅ 现在（实验回来加重复样/误差棒） | **Origin** | 正文 |
| **Fig 4** 分段 Arrhenius + Eₐ 对标 | 数据 | Pillar 2 描述符（分段 Arrhenius） + 对标 | ✅ 现在 | **Origin** | 正文 |
| **Fig 5** 闭环 (R,N) 轨迹 + Pareto | 数据 | Pillar 3 执行引擎（MOBO+LLM） | ⚠️ 部分（线 B 回来补原生 Pareto） | **Origin** | 正文 |
| **Fig S1** Pillar 2 QC | 数据 | Pillar 2 稳健性（厚度对照 + 逐温 KK） | ✅ 现在 | **Origin** | SI |
| **Fig S2** 前瞻时间线 | 示意 | 前瞻验证纪律（冻结→盖戳→实验） | ⚠️ 骨架现在（线 A/B 回来填原生时间戳） | GPT→PPT | SI |

> 正文 5 张（Fig 1–5），SI 2 张（Fig S1–S2）。这是子刊常见的"主文 4–6 图"规模，合适。

---

## 二、逐图详解（为什么要 + 怎么画 + 数据在哪）

### Fig 1 · 架构 / 智能体工作流（示意，**现在画**）
- **为什么要（核心理由）**：这是全文身份证。审稿人 30 秒内要看懂"这不是普通材料论文、也不是普通 agent
  论文，而是一个数字↔物理、被治理的闭环"。它一次性呈现 Stage0→3 主线、智能体组件（记忆/自省/心跳/模型网关）、
  以及末端**确定性主张审计**守门。没有这张图，三支柱是散的；有了它，三支柱被一条链串起。
- **工具/流程**：按 `Fig1_architecture_spec.md`（含 Mermaid + GPT 提示词 + 配色/布局）让 GPT 出草图 → PPT 精修。
- **数据**：无（示意）。规格文档：`manuscript/figures/Fig1_architecture_spec.md`。
- **现在可画**：✅。实验回来**无需重画**（结构不变）。

### Fig 2 · 分级证据 + 确定性主张审计（示意，**现在画**）
- **为什么要**：这是你区别于"会拍脑袋的 agent"的方法学内核——证据分级（主结论/补充/探索级）+ 规则化、
  与发现层独立的审计闸门（允许/降级/驳回三出口）。它把"诚实、不过度声称"从口号变成机制图。
- **工具/流程**：按 `Fig2_claim_governance_spec.md`（含 worked example + Mermaid + 提示词）GPT→PPT。
- **数据**：无（示意）。规格文档：`manuscript/figures/Fig2_claim_governance_spec.md`。
- **现在可画**：✅。无需重画。

### Fig 3 · 宽温 σ(T)（数据，**现在画**，Origin）
- **为什么要**：Pillar 2 的"冷却韧性"核心证据 + Pillar 1 迁移结果的可视化。一张图同时给出正验证（LRS 冷尾不塌）、
  边界验证（CHITO 约 −25 °C 骤降）、对照（玉米淀粉）。是"描述符有区分力"的最直观证据。
- **工具**：**Origin**（半对数 σ vs T，三条曲线 + 标记冷却转变区）。当前 `Fig3_sigma_T.png` 是 matplotlib 占位，
  投稿请用 Origin 重画。
- **数据**：
  - 主：`experiments/three_pillars/pillar2_descriptor_qc/eis_qc_v2/selected_rb_qc_v2.csv`（列 `sample_id, temperature_C, selected_conductivity_s_cm`）
  - 摘要：`experiments/three_pillars/pillar2_descriptor_qc/figure_data/wide_temperature_performance_summary.csv`
  - 代表样：LRS=`2026.5.9CS`，CHITO=`2026.4.30CS`，淀粉=`2026.4.27CS`
- **现在可画**：✅。**线 A 回来**：加薄膜重复样曲线/误差棒（升级，不重画）。

### Fig 4 · 分段 Arrhenius + Eₐ 对标（数据，**现在画**，Origin）
- **为什么要**：把描述符（**分段 Arrhenius**）摆上台面，并用高温段 Eₐ 与文献对标，证明 LRS 的低势垒
  （0.037/0.042 eV）落在已报道最低势垒的可比水平、且远优于母体系（0.120）。这是"机制唯象但可量化"的硬支撑。
- **工具**：**Origin**（面板 A：ln(σT) vs 1000/T，分段拟合 + 各样 Eₐ_high 注释；面板 B：Eₐ 条形对标）。
- **数据**：
  - 面板 A：同 Fig 3 的 `selected_rb_qc_v2.csv` / `wide_temperature_performance_summary.csv`
  - 面板 B：`experiments/three_pillars/pillar2_descriptor_qc/figure_data/ea_benchmark_table.csv`
- **现在可画**：✅。注意 CHITO 高温段无稳定 Arrhenius 区（Eₐ 标 N/A，勿强行拟合）。

### Fig 5 · 闭环 (R,N) 轨迹 + Pareto（数据，**现在骨架/等线 B 补全**，Origin）
- **为什么要**：Pillar 3 执行引擎的证据——真实跑过的 BO+LLM 闭环。诚实呈现单目标 8 试验轨迹（净改进 0，
  作"初步演示"）+ 冻结的多目标 MOBO+LLM 推荐配方在设计空间中的位置。**不过度声称收敛/发现**。
- **工具**：**Origin**（面板 A：目标函数 vs 试验序号；面板 B：(R,N) 设计空间散点 + 冻结推荐星标）。
- **数据**：
  - 轨迹：`V1.0-qianduan-mainline/stage1_optimization/output/attapulgite_aice/closed_loop_metrics.json`
  - 冻结推荐：`prospective_2026H2/line_B_mobo_closed_loop/official_recipe.json`
- **现在可画**：⚠️ 骨架可画（单目标轨迹 + 冻结推荐）。**线 B 回来**：补**原生多目标 Pareto 前沿**（升级为完整图）。

### Fig S1 · Pillar 2 QC（数据，**现在画**，Origin，补充信息）
- **为什么要**：回应审稿人对"厚度×材料族混淆"和"KK 干净度"的质疑——等几何对照下 Eₐ_high vs 厚度，
  逐温度 lin-KK 残差全部低于阈值。把稳健性证据放 SI，正文更聚焦。
- **工具**：**Origin**（面板 A：Eₐ_high vs 厚度散点；面板 B：逐温度 KK 残差 vs T）。
- **数据**：
  - `manuscript/figures/ea_vs_thickness.csv`
  - `manuscript/figures/kk_residual_per_temperature.csv`
  - `manuscript/figures/kk_rb_band_gating_table.csv`
- **现在可画**：✅。

### Fig S2 · 前瞻时间线（示意，**骨架现在/等实验填时间戳**，补充信息）
- **为什么要**：把"前瞻验证"做成可视证据链：文献检索（推理时点）→ 首次实验 → 多目标推荐冻结并 push 留时间戳。
  这是"做对了且证得硬"的图形化。
- **工具**：GPT→PPT（横向时间轴）。
- **数据**：时间戳来自线 A/B 的 `PREREGISTRATION.md` 与远端推送记录（`prospective_2026H2/...`）。
- **现在可画**：⚠️ 骨架可画。**线 A/B 回来**：填入**原生**推送时间戳。

---

## 三、执行顺序建议

1. **现在就做（不等实验）**：Fig 1、Fig 2（GPT→PPT）；Fig 3、Fig 4、Fig S1（Origin）。→ 这 5 张可让初稿"看起来像成稿"。
2. **现在画骨架、实验后升级**：Fig 5（补原生 Pareto）、Fig S2（填原生时间戳）。
3. 数据图统一在 Origin 里做风格一致（字体、配色、线宽、面板标号 A/B），与 Fig 1/2 的 PPT 风格协调。

## 四、一句话
**Fig 1/2 定身份（治理 + 数字↔物理），Fig 3/4 撑 Pillar 2 描述符，Fig 5 撑 Pillar 3 执行，Fig S1/S2 兜稳健性与前瞻纪律。**
现在能落地 5 张，剩 2 张等线 A/B。所有数据图的源 CSV/JSON 路径见上，均在仓库内、可复现。
