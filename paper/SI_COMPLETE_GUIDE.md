# Supporting Information 完整清单与状态说明

**更新日期**: 2026-02-09 v3  
**用途**: 跟踪所有SI材料的准备状态，明确主图-SI对应关系，避免重复

---

## 主图-SI对应关系与去重原则

**原则**: SI提供**方法细节、可复现性、可审计性**支撑，**不重复**主图已展示的内容。

| 主图 | 主图内容 | SI中**不放入**（与主图重复） | SI中**可放入**（补充细节） |
|------|----------|---------------------------|--------------------------|
| Fig 2(a) | 自适应温度采样 | — | S1 相变检测分数, S2 步长分布 |
| Fig 2(b) | Rb拟合R²对比 | — | S3 Rb vs T, S4 拟合方法占比, S5 Nyquist示例 |
| Fig 2(c)(d) | Arrhenius精度+雷达图 | — | S6a/b 分段对比(不同样品) |
| **Fig 3(c)** | **ΔEa分温区箱线图** | ~~Fig S16 限域箱线图~~（**已删除，与主图相同**） | S11 ΔEa vs T散点+线性拟合（连续视图，非箱线图） |
| Fig 3(a)(b)(d) | Arrhenius/BP/MN | — | Table S2-S5 数值详表 |
| Fig 4 | 报告质量雷达+条形 | — | SI Reports(Prompt/报告/评分标准) |

**已删除的冗余项**:
- ~~Fig S12~~: 单温210K预测面 → 已合并入Fig S15子图(b)
- ~~Fig S16~~: 限域效应箱线图 → **与主图Fig 3(c)完全相同**，不再入SI

---

## 状态图例
- ✅ **可直接使用** — 图像/数据内容完整，格式基本可用
- ⚠️ **需要格式调整** — 内容正确但需调整为AM投稿格式（字体/尺寸/分辨率）
- 🔲 **需要生成/补充** — 内容缺失，需从数据生成或从实验室获取
- 📝 **占位内容** — 已创建模板，标有`[PLACEHOLDER]`的内容需用真实数据替换

---

## 一、SI Figure 清单 (20张已有 + 3张待补充)

### 测量Agent与数据采集

| 编号 | 文件名 | 内容 | 状态 | 说明 |
|------|--------|------|------|------|
| Fig S1 | `FigS1_phase_jump_detection.png` | Phase Jump Score vs Measurement Index | ⚠️ 需格式调整 | 支撑Fig 2(a) |
| Fig S2 | `FigS2_adaptive_step_size.png` | 自适应步长分布(粗测3K/精测1K) | ⚠️ 需格式调整 | 支撑Fig 2(a) |
| Fig S3 | `FigS3_rb_vs_temperature.png` | log₁₀Rb vs Temperature, Agent vs Baseline | ⚠️ 需格式调整 | 支撑Fig 2(b) |

**建议**: S1+S2可合并为Fig S1(a)(b)以节省篇幅

### EIS拟合方法

| 编号 | 文件名 | 内容 | 状态 | 说明 |
|------|--------|------|------|------|
| Fig S4 | `FigS4_fitting_methods_by_temperature.png` | 各温区拟合方法占比堆叠图 | ⚠️ 需格式调整 | 方法透明度 |
| Fig S5 | `FigS5_representative_nyquist_plots.png` | 3种Nyquist图(R-C/Double R-C/Warburg) | ⚠️ 需格式调整 | 方法示例 |

### Arrhenius分析对比

| 编号 | 文件名 | 内容 | 状态 | 说明 |
|------|--------|------|------|------|
| Fig S6a | `FigS6a_arrhenius_agent_4seg.png` | Agent 4段Arrhenius(Ea=0.171/0.298/0.476/0.998) | ⚠️ 需格式调整 | 与主图Fig 3a**不同样品**，展示分段能力对比 |
| Fig S6b | `FigS6b_arrhenius_baseline_2seg.png` | Baseline 2段(Ea=0.311/0.905) | ⚠️ 需格式调整 | 同上 |

### ML模型验证

| 编号 | 文件名 | 内容 | 状态 | 说明 |
|------|--------|------|------|------|
| Fig S7 | `FigS7_s60_baseline_performance.png` | S60综合性能 | ✅ 可直接使用 | 模型透明度 |
| Fig S7a | `FigS7a_s60_pred_vs_obs.png` | S60预测vs实测 | ✅ 可直接使用 | 支撑Fig 3 |
| Fig S7b | `FigS7b_s60_residual_distribution.png` | S60残差分布 | ✅ 可直接使用 | 模型透明度 |
| Fig S8a | `FigS8a_s8_pred_vs_obs.png` | S8预测vs实测 | ✅ 可直接使用 | 支撑Fig 3 |
| Fig S8b | `FigS8b_s8_residual_vs_temp.png` | S8残差vs温度 | ✅ 可直接使用 | 模型透明度 |
| Fig S9a | `FigS9a_gbr_feature_importance.png` | GBR特征重要性 | ✅ 可直接使用 | ML可解释性 |
| Fig S9b | `FigS9b_permutation_importance.png` | 排列重要性 | ✅ 可直接使用 | ML可解释性 |
| Fig S10a | `FigS10a_cv_distribution.png` | CV R²分布 | ✅ 可直接使用 | 模型鲁棒性 |
| Fig S10b | `FigS10b_learning_curves.png` | 学习曲线 | ✅ 可直接使用 | 模型鲁棒性 |

### 扩展科学分析（不含主图重复内容）

| 编号 | 文件名 | 内容 | 状态 | 说明 |
|------|--------|------|------|------|
| Fig S11 | `FigS11_delta_ea_vs_T.png` | ΔEa vs T散点+线性拟合 | ✅ 可直接使用 | **补充**Fig 3(c)：展示连续ΔEa(T)趋势与slope，主图为分温区箱线图 |
| Fig S13 | `FigS13_correlation_matrix.png` | 特征相关性热力图 | ✅ 可直接使用 | 数据探索 |
| Fig S14 | `FigS14_partial_dependence.png` | 偏依赖图(T/R/N对Ea) | ✅ 可直接使用 | ML可解释性 |
| Fig S15 | `FigS15_multi_temp_surfaces.png` | Ea(R,N)多温度预测面(6温) | ✅ 可直接使用 | 最优配方可视化，含T=210K子图(b) |

> **不纳入SI**: `FigS_model_comparison_pred_obs.png` 为S7a+S8a的并排版，与S7a/S8a重复，不单独入SI。

### 待补充的SI Figure

| 编号 | 内容 | 状态 | 说明 |
|------|------|------|------|
| Fig S_hw | 硬件实物照片(温控+CHI+样品) | 🔲 需拍照 | 可后续补充 |
| Fig S_ui | 平台UI截图(Dashboard/Monitor等) | 🔲 需截图 | 可后续补充 |
| Fig S_timeline | Agent推理时间线甘特图 | 🔲 需生成 | 可从JSON日志生成 |

---

## 二、SI Table 清单

| 编号 | 文件 | 内容 | 状态 |
|------|------|------|------|
| Table S1 | `TableS1_material_parameters.csv` | 材料参数总表(含S8各样品R/N) | ✅ 已从output+material_config生成 |
| Table S2 | `TableS2_confinement_effect_by_temperature.csv` | ΔEa分温区统计 | ✅ 数据完整 |
| Table S3 | `TableS3_model_parameters.csv` | ML模型参数 | ✅ 数据完整 |
| Table S4 | `TableS4_meyer_neldel_results.csv` | MN结果(含双来源对比) | ✅ 数据完整 |
| Table S5 | `TableS5_cross_material_transfer.csv` | 跨材料迁移 | ✅ 数据完整 |
| Table S6 | `TableS6_agent_reasoning_log.csv` | Agent推理日志 | ✅ 数据完整 |
| Table S7 | `TableS7_report_evaluation_scores.csv` | 报告评分表 | ✅ 数据完整 |
| Table S8 | `TableS8_event_types.csv` | 事件类型映射 | ✅ 数据完整 |

---

## 三、SI Notes (算法详解)

| 编号 | 文件 | 内容 | 状态 |
|------|------|------|------|
| Note 1 | `SI_Note1_Rb_fitting_methods.md` | 多策略Rb拟合(5种策略+参数+公式) | ✅ 基于代码撰写 |
| Note 2 | `SI_Note2_Arrhenius_segmentation.md` | Arrhenius分段(滑窗+F检验+AIC) | ✅ 基于代码撰写 |
| Note 3 | `SI_Note3_experimental_methods.md` | 实验方法与硬件配置 | 📝 含PLACEHOLDER |
| Note 4 | `SI_Note4_phase_transition_detection.md` | 相变检测与自适应采样 | ✅ 基于代码撰写 |

---

## 四、SI Reports

### 报告质量对比实验设计说明

Figure 4的对比实验中，5个模型接收的Prompt**不同**：

| 模型 | Prompt文件 | 知识库 | ML定量结果 | Agent推理上下文 |
|------|-----------|--------|-----------|---------------|
| DeepSeek-R1 | `SI_Prompt_baseline_no_kb.txt` | ❌ | ❌ | ❌ |
| Gemini-2.5-Pro | 同上 | ❌ | ❌ | ❌ |
| GPT-5.2-Pro | 同上 | ❌ | ❌ | ❌ |
| Qwen | 同上 | ❌ | ❌ | ❌ |
| **Agent-Enhanced** | `SI_Prompt_S8_enhanced.txt` | ✅ | ✅ | ✅ |

这正是Agent架构的价值所在：通过ReAct推理调用ML工具获得**定量证据**，并结合**结构化知识库**，使最终报告的Data Utilization维度达到满分10.0。

### SI Reports文件清单

| 文件 | 内容 | 用途 |
|------|------|------|
| `SI_Prompt_baseline_no_kb.txt` | 4个基线模型接收的Prompt(**无**知识库、无ML结果) | 对比实验透明 |
| `SI_Prompt_S8_enhanced.txt` | Agent-Enhanced接收的Prompt(含知识库+ML结果, 16,038 chars) | 方法透明 |
| `SI_Report_S8_agent_react_full.html` | Agent-Enhanced最终输出的完整HTML报告(556KB) | 核心证据 |
| `SI_Report_S8_agent_analysis.md` | Agent-Enhanced分析Markdown版 | 供审稿人文本审查 |
| `SI_Agent_execution_log.json` | Agent完整执行日志(6次Thought-Action-Observation) | 核心证据 |
| `SI_Scoring_Rubric.md` | 评分标准(7维度+权重) | 评估透明 |

---

## 五、主论文 Table (2张)

| 文件 | 内容 | 建议位置 |
|------|------|---------|
| `MainTable1_agent_vs_baseline_performance.csv` | Agent vs Baseline性能 | Results Part 1 |
| `MainTable2_key_scientific_findings.csv` | 核心科学发现汇总 | Results/Discussion |

---

## 六、GPT写作包

| 文件 | 用途 |
|------|------|
| **`GPT_PAPER_WRITING_PACKAGE.md`** | **提供给GPT的自包含写作指导(配合4张主图)** |
| `INTEGRATED_SYSTEM_GUIDE.md` | 项目完整技术指南(更详细但非GPT专用) |

---

## 七、数据一致性说明

项目存在两次独立运行结果（Agent v2 + 传统Pipeline），核心结论完全一致。**主图上标注的数值为论文权威来源**。详见`INTEGRATED_SYSTEM_GUIDE.md`附录A。

| 数值 | 主图(Agent v2) | JSON(Pipeline) | 用哪个 |
|------|---------------|----------------|--------|
| MN n点 | 123 | 121 | **123 (主图)** |
| MN R² | 0.9809 | 0.9859 | **0.9809 (主图)** |
| S8高温E_MN | ~0.031 | 0.027 | **注明范围** |
| S60 R² | 0.896 | 0.903 | **注明范围** |

---

## 八、待办行动清单

### 高优先级
- [ ] 格式调整 Fig S1-S6(调整字体/尺寸为AM格式)
- [ ] 合并子图: S1+S2→S1(a)(b), S6a+S6b→S6(a)(b)
- [ ] 补充SI Note 3中的`[PLACEHOLDER]`内容(硬件型号/制备方法)

### 中优先级
- [ ] 补充Table S1中S8各样品详细R/N值
- [ ] 生成Fig S_timeline(Agent推理甘特图)
- [ ] 拍摄硬件实物照片(Fig S_hw)

### 低优先级
- [ ] UI界面截图(Fig S_ui)
- [ ] 关键代码片段附录

### 已完成/不再需要
- ~~Fig S12~~ 已删除(与S15子图b重复)
- ~~Fig S16~~ 已删除(与主图Fig 3(c)完全相同)
