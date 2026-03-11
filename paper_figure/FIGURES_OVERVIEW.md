# 论文图表总览

所有图表已完成，符合AM期刊标准，配色统一，风格一致。

---

## 📊 图表列表

### Figure 1: 典型样品Arrhenius图 ⭐
**样品**: S8-3-9-3 (4段拟合)

**内容**:
- 双横轴：1000/T (K⁻¹) 和 T (°C)
- 纵轴：log σ (mS·cm⁻¹)
- 4段分段拟合线 + 原始数据点
- 每段标注Ea值和R²
- 3个变化点用虚线标注

**文件**:
```
✅ figure1_arrhenius_S8-3-9-3_4segments.png (512 lines)
✅ figure1_arrhenius_S8-3-9-3_4segments.pdf
✅ figure1_arrhenius_S8-3-9-3_4segments_data.csv
```

**配色**:
- Segment 1: #E91E63 (粉红), Ea=0.08 eV
- Segment 2: #4CAF50 (绿色), Ea=0.16 eV
- Segment 3: #FF9800 (橙色), Ea=0.35 eV
- Segment 4: #9C27B0 (紫色), Ea=0.90 eV

**科学意义**: 展示典型的多段Arrhenius行为，反映不同温度区间的质子传导机制

---

### Figure 2: 变化点温度分布 (Violin Plot) ⭐
**样品**: S8 + S60 (仅4段样品)

**内容**:
- Violin图展示变化点温度分布
- 3个变化点（BP1, BP2, BP3）
- 每个变化点显示数据密度和四分位数
- S8和S60并排对比

**文件**:
```
✅ figure2_violin_distribution.png (1440 lines)
✅ figure2_violin_distribution.pdf
✅ breakpoints_data.csv
```

**配色**:
- S8 (Sepiolite): #E91E63 (粉红), alpha=0.6
- S60 (Montmorillonite): #2196F3 (蓝色), alpha=0.6

**数据量**:
- S8: 63个变化点
- S60: 45个变化点
- 总计: 108个变化点（仅4段样品）

**科学意义**: 展示变化点温度分布特征，揭示材料的相变或传导机制转变规律

---

### Figure 3: 分段数分布 (百分比堆叠柱状图) ⭐
**样品**: S8 + S60 (所有有效样品)

**内容**:
- 百分比堆叠柱状图
- 横轴：S8 和 S60
- 纵轴：样品百分比
- 每个色块标注：分段数 + 计数 + 百分比

**文件**:
```
✅ figure3_segment_distribution.png (546 lines)
✅ figure3_segment_distribution.pdf
✅ segment_counts_data.csv
```

**配色** (与Figure 1对应):
- 2段: #4CAF50 (绿色), alpha=0.75
- 3段: #FF9800 (橙色), alpha=0.75
- 4段: #E91E63 (粉红), alpha=0.75 - **主导**

**统计数据**:
| 分段数 | S8 | S60 |
|--------|-----|-----|
| 2段 | 13 (35%) | 1 (6%) |
| 3段 | 3 (8%) | 0 (0%) |
| 4段 ⭐ | **21 (57%)** | **15 (94%)** |
| **总计** | **37** | **16** |

**关键发现**: 4段是主导分段数（S8: 57%, S60: 94%）

**科学意义**: 说明4段Arrhenius行为是这两种材料的典型特征

---

### Figure 4: Ea热力图 ⭐ **NEW**
**样品**: S8 (39个) + S60 (16个)

**内容**:
- 每种材料一张图，包含2个子图
- **左图**: 高温区域Ea（第1段）
- **右图**: 低温区域Ea（最后1段）
- 横轴：R值，纵轴：N值，色标：Ea (eV)
- 每个格子标注具体Ea数值

**文件**:

**S8 (Sepiolite)**:
```
✅ figure4_ea_heatmap_S8.png
✅ figure4_ea_heatmap_S8.pdf
```
- 样品数: 39
- N范围: 2-3
- R范围: 1-38
- 高温Ea: 0.030 - 0.504 eV
- 低温Ea: 0.192 - 1.147 eV

**S60 (Montmorillonite)**:
```
✅ figure4_ea_heatmap_S60.png
✅ figure4_ea_heatmap_S60.pdf
```
- 样品数: 16
- N范围: 1-2
- R范围: 1-14
- 高温Ea: 0.047 - 0.939 eV
- 低温Ea: 0.404 - 0.856 eV

**数据文件**:
```
✅ ea_heatmap_data.csv (所有样品的Ea数据)
```

**配色**: 蓝→白→红渐变色
- 蓝色：低Ea（导电性好）
- 红色：高Ea（导电性差）

**科学意义**: 
- 揭示N-R参数对Ea的影响规律
- 指导材料优化方向（寻找最低Ea的组合）
- 对比高温和低温区域的传导机制差异

---

## 🎨 统一配色方案

### 主色调
- **粉红 #E91E63**: 贯穿3张图，作为主要强调色
  - Figure 1: Segment 1
  - Figure 2: S8材料
  - Figure 3: 4段（主导）
  
- **绿色 #4CAF50**: Figure 1 Segment 2, Figure 3的2段
- **橙色 #FF9800**: Figure 1 Segment 3, Figure 3的3段
- **紫色 #9C27B0**: Figure 1 Segment 4
- **蓝色 #2196F3**: Figure 2 S60材料

### 设计原则
1. **一致性**: 相同的信息使用相同的颜色
2. **对比度**: 不同类别有明显区分
3. **专业性**: 符合AM期刊标准
4. **可读性**: 适合印刷和屏幕显示

---

## 📐 图像规格

| 图号 | 尺寸 (英寸) | DPI | 格式 |
|------|------------|-----|------|
| Figure 1 | 5.2 × 4.0 | 300 | PNG + PDF |
| Figure 2 | 10 × 6 | 300 | PNG + PDF |
| Figure 3 | 8 × 6 | 300 | PNG + PDF |
| Figure 4 (S8) | 14 × 5 | 300 | PNG + PDF |
| Figure 4 (S60) | 14 × 5 | 300 | PNG + PDF |

---

## 📂 文件结构

```
paper_figure/
├── figure1_arrhenius_S8-3-9-3_4segments.png
├── figure1_arrhenius_S8-3-9-3_4segments.pdf
├── figure1_arrhenius_S8-3-9-3_4segments_data.csv
├── figure2/
│   ├── figure2_violin_distribution.png
│   ├── figure2_violin_distribution.pdf
│   └── breakpoints_data.csv
├── figure3/
│   ├── figure3_segment_distribution.png
│   ├── figure3_segment_distribution.pdf
│   ├── segment_counts_data.csv
│   └── VERSION_COMPARISON.md
├── figure4/
│   ├── figure4_ea_heatmap_S8.png
│   ├── figure4_ea_heatmap_S8.pdf
│   ├── figure4_ea_heatmap_S60.png
│   ├── figure4_ea_heatmap_S60.pdf
│   ├── ea_heatmap_data.csv
│   └── README.md
├── FIGURE_COLOR_SCHEME.md
└── FIGURES_OVERVIEW.md (本文件)
```

---

## ✅ 完成检查清单

- [x] Figure 1: Arrhenius典型样品图
  - [x] S8-3-9-3样品（4段）
  - [x] Ea标签位置优化（无重叠）
  - [x] 拟合线与数据点完全重合
  - [x] 配色与后续图表统一
  
- [x] Figure 2: 变化点温度分布
  - [x] Violin图展示
  - [x] 仅使用4段样品
  - [x] S8 vs S60对比
  - [x] 配色统一
  
- [x] Figure 3: 分段数分布
  - [x] 百分比堆叠柱状图
  - [x] 突出4段主导地位
  - [x] 配色与Figure 1统一
  - [x] 标注清晰（计数+百分比）
  
- [x] Figure 4: Ea热力图
  - [x] S8和S60各一张图
  - [x] 高温和低温区域分开
  - [x] N-R参数热力图
  - [x] 数值标注清晰

---

## 🎯 使用建议

### 论文中的排版
- **正文**: Figure 1 (典型样品) + Figure 3 (分段数统计)
- **支持材料**: Figure 2 (变化点分布) + Figure 4 (Ea热力图)

### 讨论重点
1. **Figure 1**: 展示4段Arrhenius行为的典型特征
2. **Figure 2**: 分析变化点温度分布，讨论相变或机制转变
3. **Figure 3**: 强调4段是主导模式，支持Figure 1的代表性
4. **Figure 4**: 探讨材料参数对Ea的影响，指导优化方向

---

**创建时间**: 2026-02-03  
**版本**: v1.0  
**状态**: ✅ 全部完成
