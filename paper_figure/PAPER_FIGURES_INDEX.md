# Paper Figures 总索引

本目录包含论文所需的所有图表文件。

---

## 📁 目录结构

```
paper_figure/
├── figure2/                          # Figure 2: 多样品变化点分布
│   ├── figure2_breakpoints_distribution.png
│   ├── figure2_breakpoints_distribution.pdf
│   ├── breakpoints_data.csv
│   ├── figure2_distribution_stats.csv
│   ├── README.md
│   └── FIGURE2_SUMMARY.txt
│
├── figure1_arrhenius_S8-3-2-1_3segments.png    # Figure 1: Arrhenius 图
├── figure1_arrhenius_S8-3-2-1_3segments.pdf
├── figure1_arrhenius_S8-3-2-1_3segments_data.csv
├── S8-3-2-1_3SEGMENTS_README.md
├── S8-3-2-1_MERGE_SUMMARY_CN.txt
│
├── ORIGIN_STEP_BY_STEP_CN.md        # Origin 教程
├── ORIGIN_QUICK_REFERENCE.txt
├── CSV_DATA_EXPLANATION_CN.txt
├── README.md                         # 总说明
└── PAPER_FIGURES_INDEX.md           # 本文件
```

---

## 📊 图表清单

### Figure 1: 典型样品 Arrhenius 图 ⭐⭐⭐

**文件位置**: `paper_figure/` (根目录)

| 文件 | 说明 |
|------|------|
| `figure1_arrhenius_S8-3-2-1_3segments.png` | 300 dpi 位图 |
| `figure1_arrhenius_S8-3-2-1_3segments.pdf` | 矢量图 |
| `figure1_arrhenius_S8-3-2-1_3segments_data.csv` | 35 个数据点 + 拟合参数 |

**内容**:
- **样品**: S8-3-2-1（海泡石 + H₃PO₄）
- **数据**: 35 个温度点，186-300 K
- **分段**: 3 段（原 4 段合并 1+2）
- **参数**: Ea = 0.26, 0.48, 1.00 eV, R² > 0.98

**特点**:
- ✅ 双横轴（1000/T 和 T(°C)）
- ✅ 三段拟合线（粉红、绿、橙）
- ✅ Ea 标注在线下方
- ✅ R² 值在左下角图例
- ✅ 数据点半透明（alpha=0.5）

---

### Figure 2: 多样品变化点温度分布 ⭐⭐⭐

**文件位置**: `paper_figure/figure2/`

| 文件 | 说明 |
|------|------|
| `figure2_breakpoints_distribution.png` | 300 dpi 位图 |
| `figure2_breakpoints_distribution.pdf` | 矢量图 |
| `breakpoints_data.csv` | 128 个变化点原始数据 |
| `figure2_distribution_stats.csv` | 按 5K 区间统计 |

**内容**:
- **样品**: S8（41 个）+ S60（17 个）
- **数据**: 128 个变化点
- **温度范围**: 180-280 K
- **关键发现**: 215 K 附近聚集 29 个（22.7%）

**特点**:
- ✅ 叠加直方图（S8 粉红 + S60 蓝色）
- ✅ 高亮 215 K 区域（橙色阴影）
- ✅ 标注样品数和关键统计
- ✅ 展示共性传导机制转变温度

---

## 📚 说明文档

### Figure 1 相关

| 文档 | 内容 | 推荐度 |
|------|------|--------|
| `S8-3-2-1_3SEGMENTS_README.md` | 详细说明（合并原理、参数、Origin） | ⭐⭐⭐⭐⭐ |
| `S8-3-2-1_MERGE_SUMMARY_CN.txt` | 中文快速参考（表格、公式） | ⭐⭐⭐⭐ |
| `ORIGIN_STEP_BY_STEP_CN.md` | Origin 分步教程（8000+ 字） | ⭐⭐⭐⭐⭐ |
| `ORIGIN_QUICK_REFERENCE.txt` | Origin 快速参考卡 | ⭐⭐⭐ |
| `CSV_DATA_EXPLANATION_CN.txt` | CSV 数据详解 | ⭐⭐⭐ |

### Figure 2 相关

| 文档 | 内容 | 推荐度 |
|------|------|--------|
| `figure2/README.md` | 详细说明（数据、图像、意义） | ⭐⭐⭐⭐⭐ |
| `figure2/FIGURE2_SUMMARY.txt` | 中文快速总结 | ⭐⭐⭐⭐ |

### 总体文档

| 文档 | 内容 | 推荐度 |
|------|------|--------|
| `README.md` | 总体说明（配色、样品对比） | ⭐⭐⭐⭐ |
| `PAPER_FIGURES_INDEX.md` | 本文档（文件索引） | ⭐⭐⭐ |

---

## 🎯 使用建议

### 论文写作流程

1. **插入图像**:
   - Figure 1: `figure1_arrhenius_S8-3-2-1_3segments.png`
   - Figure 2: `figure2_breakpoints_distribution.png`

2. **参考说明文档**:
   - Figure 1 → 阅读 `S8-3-2-1_3SEGMENTS_README.md`
   - Figure 2 → 阅读 `figure2/README.md`

3. **论文描述**:
   - 每个 README 都包含"论文描述建议"部分
   - 提供简洁版和详细版

4. **Origin 重绘**（如需微调）:
   - 使用 `ORIGIN_STEP_BY_STEP_CN.md`（详细）
   - 或 `ORIGIN_QUICK_REFERENCE.txt`（快速）

---

## 📊 两图对比

| 对比项 | Figure 1 | Figure 2 |
|--------|----------|----------|
| **类型** | Arrhenius 图（双轴） | 直方图（叠加） |
| **样品数** | 1 个（S8-3-2-1） | 58 个（S8+S60） |
| **数据点** | 35 个温度点 | 128 个变化点 |
| **温度范围** | 186-300 K | 180-280 K |
| **主要参数** | Ea (0.26/0.48/1.0 eV) | 变化点温度分布 |
| **关键发现** | 三段清晰机制 | 215 K 聚集（22.7%） |
| **物理意义** | 详细机制展示 | 共性规律识别 |
| **视角** | 深度（单样品） | 广度（多样品） |

**互补性**: 
- Figure 1 回答 **"怎么变"**（Ea 如何变化）
- Figure 2 回答 **"在哪变"**（温度分布规律）

---

## 🎨 配色方案统一

### Figure 1
- 数据点: 深灰蓝 #2c3e50 (alpha=0.5)
- Segment 1: 粉红 #E91E63
- Segment 2: 绿色 #4CAF50
- Segment 3: 橙色 #FF9800

### Figure 2
- S8: 粉红 #E91E63（与 Figure 1 一致）
- S60: 蓝色 #2196F3
- 高亮: 橙色（215 K 区域）

**设计考虑**: 
- S8 在两图中保持粉红色，便于识别
- 色盲友好（避免纯红绿组合）
- 高对比度，适合打印

---

## 📝 CSV 数据文件

### Figure 1 数据

**文件**: `figure1_arrhenius_S8-3-2-1_3segments_data.csv`

| 部分 | 内容 | 行数 |
|------|------|------|
| 第 1 部分 | 35 个数据点（T, σ, log σ） | 1-36 |
| 第 2 部分 | 3 段拟合参数（Ea, R²） | 39-42 |
| 第 3 部分 | 2 个边界点（1000/T） | 44-46 |

**用途**: Origin 重绘、数据验证

---

### Figure 2 数据

**文件 1**: `breakpoints_data.csv` (原始数据)

| 列名 | 说明 | 示例 |
|------|------|------|
| material | 材料类型 | S8, S60 |
| sample_id | 样品编号 | S8-3-2-1 |
| breakpoint_index | 变化点序号 | 1, 2, 3 |
| temperature_K | 温度 (K) | 258.07 |
| total_segments | 总段数 | 4 |

**行数**: 128 行（每个变化点一行）

**文件 2**: `figure2_distribution_stats.csv` (统计数据)

| 列名 | 说明 | 示例 |
|------|------|------|
| T_range_K | 温度区间 | 210-215 |
| T_center_K | 中心温度 | 212.5 |
| S8_count | S8 数量 | 7 |
| S60_count | S60 数量 | 2 |
| Total_count | 总数 | 9 |

**行数**: 20 行（每 5 K 一个区间）

**用途**: 统计分析、Origin 绘图

---

## 🔬 科学意义

### Figure 1 的价值
1. **典型性**: 展示清晰的三段 Arrhenius 行为
2. **代表性**: S8-3-2-1 拟合质量高（R² > 0.98）
3. **机制性**: 每段 Ea 对应不同传导机制
4. **教学性**: 清晰展示合并前后对比

### Figure 2 的价值
1. **统计性**: 58 个样品，128 个变化点
2. **共性**: 识别材料共性温度特征（215 K）
3. **对比性**: S8 vs S60 的差异与共同点
4. **预测性**: 为新样品提供参考温度范围

### 两图结合
- **个体 + 群体**: 既有深度也有广度
- **机制 + 规律**: 既解释原理也展示分布
- **定量 + 统计**: 既有精确值也有趋势
- **论文完整性**: 满足 AM 期刊要求

---

## ✅ 质量检查

### Figure 1
- [x] 数据点清晰可见（半透明）
- [x] 拟合线颜色突出（粉红、绿、橙）
- [x] Ea 标注不遮挡线条
- [x] R² 值在图例中清晰标注
- [x] 双横轴对齐正确
- [x] 删除异常点（186.55 K）
- [x] 分辨率 300 dpi
- [x] 提供矢量 PDF

### Figure 2
- [x] 两种材料区分明显
- [x] 215 K 区域高亮清晰
- [x] 样品数量标注完整
- [x] 统计数据准确
- [x] 直方图 bins 合理（5 K）
- [x] 图例位置合适
- [x] 分辨率 300 dpi
- [x] 提供矢量 PDF

---

## 📞 技术支持

### 图像问题
- **Figure 1**: 参考 `ORIGIN_STEP_BY_STEP_CN.md`
- **Figure 2**: 参考 `figure2/README.md`
- **配色**: 参考本文档"配色方案"部分

### 数据问题
- **CSV 格式**: 参考 `CSV_DATA_EXPLANATION_CN.txt`
- **统计方法**: 参考各图的 README
- **Origin 导入**: 参考 `ORIGIN_QUICK_REFERENCE.txt`

### 论文写作
- **图注建议**: 每个 README 都有"论文描述"部分
- **物理解释**: 参考 README 的"物理意义"部分
- **参数引用**: 直接使用 CSV 中的数值

---

## 🚀 快速导航

| 需求 | 推荐文档 |
|------|----------|
| 快速了解 Figure 1 | `S8-3-2-1_MERGE_SUMMARY_CN.txt` |
| 详细理解 Figure 1 | `S8-3-2-1_3SEGMENTS_README.md` |
| Origin 绘制 Figure 1 | `ORIGIN_STEP_BY_STEP_CN.md` |
| 快速了解 Figure 2 | `figure2/FIGURE2_SUMMARY.txt` |
| 详细理解 Figure 2 | `figure2/README.md` |
| 数据格式说明 | `CSV_DATA_EXPLANATION_CN.txt` |
| Origin 快速参考 | `ORIGIN_QUICK_REFERENCE.txt` |
| 总体概览 | 本文档 |

---

## 📈 后续工作建议

1. **Figure 3** (如需要):
   - Ea vs 配比（R 值）散点图
   - 展示组成-性能关系

2. **Figure 4** (如需要):
   - 不同材料对比（S8, S60, S04, S02）
   - 箱线图或小提琴图

3. **补充材料**:
   - 所有样品的 Arrhenius 图集
   - 详细的拟合参数表格

4. **数据验证**:
   - 交叉验证拟合参数
   - 敏感性分析

---

祝论文写作顺利！🎓✨

如有任何问题，请参考对应的 README 文档或联系技术支持。
