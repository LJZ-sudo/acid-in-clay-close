# Paper Figures 总览（3张图完整版）

本文档总结 close/paper_figure/ 文件夹中为 AM 期刊生成的所有图表。

---

## 📊 图表清单（共3张）

### Figure 1: 典型样品 Arrhenius 图 ⭐
**位置**: `paper_figure/` (主文件夹)

**推荐文件**: `figure1_arrhenius_S8-3-2-1_3segments.png/pdf`

**内容**:
- 双横轴 Arrhenius 图
- 下横轴：1000/T (K⁻¹)，3-5.5，间隔 0.5
- 上横轴：T (°C)
- 纵轴：log σ (mS·cm⁻¹)
- 3 段线性拟合 + 数据点
- 每段标注 Ea 值（中间位置）
- 图例显示 R² 值

**样品**: S8-3-2-1（海泡石 + H₃PO₄）
- 原始 4 段合并为 3 段
- 35 个数据点（去除 1 个异常点）
- 温度范围：186.6-300.0 K

**拟合参数**:
- Segment 1: Ea = 0.256 eV, R² = 0.986（高温段）
- Segment 2: Ea = 0.475 eV, R² = 0.993（中温段）
- Segment 3: Ea = 0.998 eV, R² = 0.986（低温段）

**配色**: 粉红 #E91E63, 绿色 #4CAF50, 橙色 #FF9800

**文件**:
- `figure1_arrhenius_S8-3-2-1_3segments.png` (300 dpi)
- `figure1_arrhenius_S8-3-2-1_3segments.pdf` (矢量)
- `figure1_arrhenius_S8-3-2-1_3segments_data.csv` (数据)
- `S8-3-2-1_3SEGMENTS_README.md` (详细说明)
- `ORIGIN_STEP_BY_STEP_CN.md` (Origin 教程，8000字)
- `ORIGIN_QUICK_REFERENCE.txt` (快速参考卡)

---

### Figure 2: 变化点温度分布 ⭐
**位置**: `paper_figure/figure2/`

**推荐文件**: `figure2_violin_distribution.png/pdf`

**内容**:
- 小提琴图展示温度分布
- 按变化点序号分组：BP1, BP2, BP3
- S8 和 S60 并排对比
- 叠加真实数据点 + 中位数线 + 四分位数线
- 去除 215K 过度标注，聚焦分布特征

**数据统计**:
- 总计 128 个变化点（S8: 82, S60: 46）
- BP1（高温边界）: S8 260±19 K, S60 271±10 K
- BP2（中温边界）: S8 246±13 K, S60 247±11 K
- BP3（低温边界）: S8 221±9 K, S60 213±8 K

**关键发现**:
- 温度梯度清晰：BP1 > BP2 > BP3
- BP3 分布最集中（std 8-9 K，跨度 26-36 K）
- 低温段机制转变更具共性

**配色**: S8 粉红 #E91E63, S60 蓝色 #2196F3

**文件**:
- `figure2_violin_distribution.png` (300 dpi)
- `figure2_violin_distribution.pdf` (矢量)
- `figure2_violin_statistics.csv` (详细统计)
- `breakpoints_data.csv` (原始数据，128个变化点)
- `VIOLIN_VERSION_SUMMARY.md` (说明文档)

**备选版本**:
- V1: 直方图（叠加）
- V2: 条带图 + 箱线图
- V3: 按序号分组（带误差棒）

---

### Figure 3: Arrhenius 分段数分布 ⭐
**位置**: `paper_figure/figure3/`

**推荐文件**: `figure3_segment_distribution.png/pdf`

**内容**:
- 分组柱状图
- 横轴：分段数（2, 3, 4）
- 纵轴：样品数量
- S8 和 S60 并排对比
- 柱子上方标注样品数量

**数据统计**:
- 总计 53 个样品（过滤 0/1 段的低质量样品）
- S8: 37 样品（2段:13, 3段:3, 4段:21）
- S60: 16 样品（2段:1, 3段:0, 4段:15）

**关键发现**:
- **S60 高度一致**: 93.8% 为 4 段
- **S8 较多样化**: 56.8% 为 4 段，35.1% 为 2 段
- **3 段罕见**: 仅 8.1%（S8），S60 为 0
- 机制转变呈二元分布（简单 vs 复杂）

**物理意义**:
- 4 段 = 3 次机制转变（高温→中高温→中低温→低温）
- 2 段 = 1 次主要机制转变（Grotthuss ↔ Vehicle）
- S60 传导行为更规律，S8 样品间差异大

**配色**: S8 粉红 #E91E63, S60 蓝色 #2196F3

**文件**:
- `figure3_segment_distribution.png` (300 dpi)
- `figure3_segment_distribution.pdf` (矢量)
- `figure3_detailed_statistics.csv` (详细统计)
- `segment_counts_data.csv` (原始数据，58个样品)
- `README.md` (详细说明)
- `FIGURE3_SUMMARY.txt` (中文总结)

---

## 🎯 推荐使用组合

### 论文主图（3张）⭐⭐⭐

1. **Figure 1**: 典型样品微观分析
   - 展示单样品的 Arrhenius 拟合过程
   - 提取活化能 Ea 和 R²
   - 说明如何识别机制转变

2. **Figure 2**: 变化点温度统计
   - 展示 BP1/BP2/BP3 的温度分布
   - 揭示温度梯度和分布宽度
   - BP3 最集中，低温段更具共性

3. **Figure 3**: 分段数统计
   - 展示样品间一致性
   - S60 高度一致（94% 为 4 段）
   - S8 多样性大（57% 为 4 段，35% 为 2 段）

### 科学叙事逻辑

```
Figure 1: "这是一个典型样品的 3 段 Arrhenius 行为"
    ↓
Figure 2: "多样品的变化点温度有什么规律？"
          → BP1（高温）、BP2（中温）、BP3（低温）
          → BP3 分布最集中
    ↓
Figure 3: "多数样品是几段？一致性如何？"
          → S60 主要是 4 段（93.8%），高度一致
          → S8 更多样（4段 57%，2段 35%）
```

### 三张图的互补性

| 图表 | 视角 | 回答的问题 | 数据规模 |
|------|------|-----------|---------|
| **Figure 1** | 微观 | 单样品如何拟合？Ea 是多少？ | 1 样品，35 数据点 |
| **Figure 2** | 介观 | 变化点温度分布规律？ | 53 样品，128 变化点 |
| **Figure 3** | 宏观 | 样品间一致性如何？ | 53 样品，分段数统计 |

**组合效果**: 从**案例 → 温度规律 → 样品统计**，完整展示质子传导机制的层次性。

---

## 🎨 统一的视觉风格

### 配色方案
- **S8（凹凸棒石）**: 粉红色 #E91E63
- **S60（蒙脱石）**: 蓝色 #2196F3
- **拟合线（Figure 1）**: 粉红、绿色、橙色（鲜艳对比）

### 字体规格（AM 期刊风格）
- 字体: Arial / Helvetica / DejaVu Sans
- 坐标轴标签: 12 pt, 粗体
- 标题: 13 pt, 粗体
- X 轴刻度: 11 pt
- Y 轴刻度: 10 pt
- 图例: 10 pt
- 统计框: 8.5-9 pt

### 输出规格
- **PNG**: 300 dpi（论文投稿用）
- **PDF**: 矢量格式（高质量印刷）
- **CSV**: 原始数据（供 Origin 等软件使用）

---

## 📂 文件夹结构

```
paper_figure/
│
├── Figure 1 主文件
│   ├── figure1_arrhenius_S8-3-2-1_3segments.png          ⭐
│   ├── figure1_arrhenius_S8-3-2-1_3segments.pdf          ⭐
│   ├── figure1_arrhenius_S8-3-2-1_3segments_data.csv     ⭐
│   ├── S8-3-2-1_3SEGMENTS_README.md
│   ├── S8-3-2-1_MERGE_SUMMARY_CN.txt
│   ├── ORIGIN_STEP_BY_STEP_CN.md
│   ├── ORIGIN_QUICK_REFERENCE.txt
│   └── merge_segments_s8321.py
│
├── figure2/  (Figure 2)
│   ├── figure2_violin_distribution.png                   ⭐
│   ├── figure2_violin_distribution.pdf                   ⭐
│   ├── figure2_violin_statistics.csv                     ⭐
│   ├── breakpoints_data.csv
│   ├── VIOLIN_VERSION_SUMMARY.md
│   ├── FIGURE2_VERSIONS_COMPARISON.md
│   ├── plot_violin_distribution.py
│   └── (其他版本: V1, V2, V3)
│
├── figure3/  (Figure 3)
│   ├── figure3_segment_distribution.png                  ⭐
│   ├── figure3_segment_distribution.pdf                  ⭐
│   ├── figure3_detailed_statistics.csv                   ⭐
│   ├── segment_counts_data.csv
│   ├── README.md
│   ├── FIGURE3_SUMMARY.txt
│   ├── collect_segment_counts.py
│   └── plot_segment_distribution.py
│
└── 说明文档
    ├── README.md (原始 README)
    ├── FILE_INDEX.txt
    ├── PAPER_FIGURES_INDEX.md
    └── PAPER_FIGURES_OVERVIEW.md (本文档) ⭐
```

---

## 📊 数据来源

所有图表数据来自:
```
close/output/phase1_results/*.json
```

处理流程:
1. **Phase 1 Results** → 原始 Arrhenius 拟合结果（JSON 格式）
2. **Figure 1** → 选取 S8-3-2-1 样品，合并 Segment 1+2，生成 3 段图
3. **Figure 2** → 提取所有样品的变化点温度，按 BP1/BP2/BP3 分组统计
4. **Figure 3** → 统计所有样品的分段数，生成分布图

---

## 📝 论文描述建议

### Figure 1
> "Figure 1 展示了典型 S8 样品（S8-3-2-1）的 Arrhenius 图。样品在 186.6-300.0 K 温度范围内呈现 3 段线性行为，对应三个不同的质子传导机制：高温段（Ea = 0.256 eV）、中温段（Ea = 0.475 eV）和低温段（Ea = 0.998 eV）。拟合质量优秀（所有段 R² > 0.98），清晰展示了质子传导机制随温度的演化。"

### Figure 2
> "Figure 2 统计了 S8 和 S60 共 128 个 Arrhenius 变化点的温度分布。三个变化点呈现清晰的温度梯度：BP1（260-271 K）、BP2（246-247 K）、BP3（213-221 K）。值得注意的是，BP3 的分布最为集中（标准差 8-9 K，跨度 26-36 K），显著小于 BP1 和 BP2，表明低温段传导机制转变在不同粘土样品间具有更强的共性。"

### Figure 3
> "Figure 3 展示了 S8 和 S60 共 53 个样品的 Arrhenius 分段数分布。S60 表现出高度一致的 4 段行为（93.8%），说明蒙脱石材料具有规律的三次机制转变。相比之下，S8 表现出更大的多样性：56.8% 呈现 4 段行为，35.1% 呈现 2 段行为。这种差异可能源于凹凸棒石纤维束结构的不均匀性。"

---

## ✅ 质量检查清单

### Figure 1 ✓
- ✅ 双横轴正确（1000/T 和 T(°C)）
- ✅ 坐标轴范围正确（X: 3-5.5, Y: auto）
- ✅ 3 段拟合线清晰可见
- ✅ Ea 标注位置合适（不遮挡曲线）
- ✅ R² 显示在图例中
- ✅ 数据点透明度适中（0.5）
- ✅ 拟合线粗细合适（2.5）
- ✅ 字体大小一致（AM 风格）

### Figure 2 ✓
- ✅ 小提琴图形状清晰
- ✅ BP1/BP2/BP3 分组明确
- ✅ S8 和 S60 并排对比
- ✅ 中位数和四分位数线可见
- ✅ 去除 215K 过度标注
- ✅ 统计信息框清晰
- ✅ 字体大小一致

### Figure 3 ✓
- ✅ 柱状图清晰
- ✅ S8 和 S60 并排对比
- ✅ 柱子上方数字标注清晰
- ✅ X 轴标签简洁（2, 3, 4）
- ✅ 统计信息框位置合适
- ✅ 字体大小一致
- ✅ 配色与 Figure 2 一致

---

## 🔬 科学贡献

通过这三张图，我们完整展示了:

1. **单样品层面**（Figure 1）
   - 如何识别质子传导机制转变
   - 如何提取活化能 Ea
   - 典型的 3 段 Arrhenius 行为

2. **温度规律层面**（Figure 2）
   - 变化点的温度分布特征
   - BP1/BP2/BP3 的温度梯度
   - BP3（低温段）最集中，共性最强

3. **样品统计层面**（Figure 3）
   - S60 高度一致（94% 为 4 段）
   - S8 多样性大（4段 57%，2段 35%）
   - 揭示材料间差异

**整体贡献**: 从**微观案例**到**宏观统计**，系统揭示了粘土基质子导体的传导机制层次性和材料间差异。

---

## 📧 使用建议

1. **论文主文**
   - 引用所有 3 张图
   - Figure 1 → Results 部分（单样品分析）
   - Figure 2 → Results/Discussion（温度规律）
   - Figure 3 → Discussion（材料对比）

2. **补充材料**
   - 其他版本的 Figure 2（V1, V2, V3）
   - 更多样品的 Arrhenius 图
   - 详细的统计数据（CSV 文件）

3. **Origin 用户**
   - 使用 CSV 文件导入 Origin
   - 参考 `ORIGIN_STEP_BY_STEP_CN.md` 重新绘制
   - 可微调颜色、字体、标注位置

---

祝论文写作顺利！📊✨

如有任何问题或需要调整，请随时告知。
