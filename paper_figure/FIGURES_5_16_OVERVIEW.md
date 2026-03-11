# Paper Figures 5-16 总览

本文档总结 `close/paper_figure/figure5-16/` 文件夹中为 AM 期刊生成的图表。

---

## 📊 图表清单

### 主题一：ML Baseline vs Confined Model（机器学习参照系）

| Figure | 标题 | 内容 | 文件夹 |
|--------|------|------|--------|
| **Figure 5** | S60 Baseline Performance | Ea_pred vs Ea_obs 散点图 + 残差分布 | `figure5/` |
| **Figure 6** | S8 Confined Performance | 同上，按温度着色 | `figure6/` |
| **Figure 7** | Feature Importance | GBR 特征重要性 + Permutation Importance | `figure7/` |
| **Figure 8** | CV Stability | K-Fold 分数分布 + Learning Curve | `figure8/` |

### 主题二：ΔEa(T) 核心主图（限域强度首次定量）

| Figure | 标题 | 内容 | 文件夹 |
|--------|------|------|--------|
| **Figure 9** | ΔEa vs T Linear Fit | 线性拟合 + 95% CI + 温区着色 | `figure9/` |
| **Figure 10** | Temperature Boxplot | 低温/高温箱线图 + Bootstrap CI + t/p/d | `figure10/` |
| **Figure 11** | ΔEa Distribution | 直方图 + KDE + 偏度/峰度分析 | `figure11/` |
| **Figure 12** | Residual Diagnostics | Q-Q Plot + Residual vs Fitted + Scale-Location | `figure12/` |

### 主题三：Meyer-Neldel Compensation（统一动力学）

| Figure | 标题 | 内容 | 文件夹 |
|--------|------|------|--------|
| **Figure 13** | S8 Meyer-Neldel | ln(σ₀) vs Ea（分温区/分机制段） | `figure13/` |
| **Figure 14** | S60 Meyer-Neldel | S60 单独 + S8/S60 对比 | `figure14/` |
| **Figure 15** | E_MN / T_MN Comparison | 条形图 + 误差棒 | `figure15/` |
| **Figure 16** | Entropy-Enthalpy Schematic | 熵-焓补偿物理含义示意 | `figure16/` |

---

## 🎨 统一配色方案

### 材料颜色
| 材料 | 颜色代码 | 说明 |
|------|---------|------|
| S8 (Sepiolite) | `#E91E63` | 粉红色 |
| S60 (Montmorillonite) | `#2196F3` | 蓝色 |

### 温区颜色
| 温区 | 颜色代码 | 温度范围 |
|------|---------|---------|
| High T | `#E53935` | ≥270 K |
| Mid T | `#43A047` | 230-270 K |
| Low T | `#1E88E5` | <230 K |

### 其他元素
- 拟合线: `#D32F2F` (深红)
- 参考线: `#757575` (深灰)
- 95% CI 填充: `#BBDEFB` (浅蓝)

---

## 📁 文件结构

```
paper_figure/
├── am_style_config.py          # 统一样式配置
├── generate_all_figures.py     # 一键生成脚本
├── FIGURES_5_16_OVERVIEW.md    # 本文档
│
├── figure5/                    # ML - S60 Baseline
│   ├── plot_s60_baseline_performance.py
│   ├── figure5_s60_baseline_performance.png/pdf
│   └── figure5_data.csv
│
├── figure6/                    # ML - S8 Confined
│   ├── plot_s8_confined_performance.py
│   ├── figure6_s8_confined_performance.png/pdf
│   └── figure6_data.csv
│
├── figure7/                    # Feature Importance
│   ├── plot_feature_importance.py
│   ├── figure7_feature_importance.png/pdf
│   └── figure7_importance_data.csv
│
├── figure8/                    # CV Stability
│   ├── plot_cv_stability.py
│   ├── figure8_cv_stability.png/pdf
│   ├── figure8_cv_scores.csv
│   └── figure8_learning_curve.csv
│
├── figure9/                    # ΔEa vs T
│   ├── plot_delta_ea_vs_T.py
│   ├── figure9_delta_ea_vs_T.png/pdf
│   ├── figure9_data.csv
│   └── figure9_fit_line.csv
│
├── figure10/                   # Temperature Boxplot
│   ├── plot_temp_boxplot.py
│   ├── figure10_temp_boxplot.png/pdf
│   ├── figure10_statistics.csv
│   └── figure10_test_results.json
│
├── figure11/                   # ΔEa Distribution
│   ├── plot_delta_ea_distribution.py
│   ├── figure11_delta_ea_distribution.png/pdf
│   ├── figure11_distribution_stats.csv
│   └── figure11_temp_region_stats.csv
│
├── figure12/                   # Residual Diagnostics
│   ├── plot_residual_diagnostics.py
│   ├── figure12_residual_diagnostics.png/pdf
│   ├── figure12_residual_data.csv
│   └── figure12_diagnostics.json
│
├── figure13/                   # S8 Meyer-Neldel
│   ├── plot_meyer_neldel_s8.py
│   ├── figure13_meyer_neldel_s8.png/pdf
│   ├── figure13_s8_mn_data.csv
│   └── figure13_fit_results.json
│
├── figure14/                   # S60 Meyer-Neldel
│   ├── plot_meyer_neldel_s60.py
│   ├── figure14_meyer_neldel_s60.png/pdf
│   ├── figure14_s60_mn_data.csv
│   └── figure14_comparison_results.json
│
├── figure15/                   # E_MN / T_MN
│   ├── plot_emn_tmn_comparison.py
│   ├── figure15_emn_tmn_comparison.png/pdf
│   └── figure15_emn_tmn_data.csv
│
└── figure16/                   # Entropy-Enthalpy Schematic
    ├── plot_entropy_enthalpy_schematic.py
    ├── figure16_entropy_enthalpy_schematic.png/pdf
    └── README.md
```

---

## 🚀 使用方法

### 一键生成所有图表

```bash
cd close/paper_figure
python generate_all_figures.py
```

### 单独生成某个图表

```bash
cd close/paper_figure/figure5
python plot_s60_baseline_performance.py
```

---

## 📐 AM 期刊标准

### 字体规格
- 字体：Arial / Helvetica / DejaVu Sans
- 坐标轴标签：11pt
- 标题：12pt, Bold
- 图例：9pt
- 统计框：9pt, Monospace

### 图像尺寸
- 单面板：5 × 4 英寸
- 双面板：10-12 × 4-5 英寸
- DPI：300

### 输出格式
- PNG：论文投稿用
- PDF：矢量格式（高质量印刷）
- CSV：原始数据（供 Origin 等软件使用）

---

## 📊 科学叙事逻辑

### Part 1: ML 模型验证 (Figure 5-8)

```
Figure 5-6: "ML 模型能准确预测 Ea 吗？"
    → S60 R² = 0.90, S8 R² = 0.97
    ↓
Figure 7: "哪些特征最重要？"
    → 温度 T 主导，交互项 T×N 次之
    ↓
Figure 8: "模型稳定吗？"
    → CV R² 稳定，无明显过拟合
```

### Part 2: 限域效应定量 (Figure 9-12)

```
Figure 9: "限域效应 ΔEa 如何随温度变化？"
    → 负斜率：低温时限域效应更强
    ↓
Figure 10: "低温和高温有显著差异吗？"
    → t 检验 p < 0.001，Cohen's d 显著
    ↓
Figure 11: "ΔEa 分布是什么样的？"
    → 正偏态，低温尾巴长
    ↓
Figure 12: "线性拟合假设合理吗？"
    → Q-Q 图验证正态性
```

### Part 3: 统一动力学规律 (Figure 13-16)

```
Figure 13-14: "Meyer-Neldel 补偿存在吗？"
    → S8 和 S60 都遵循 ln(σ₀) ~ Ea 线性关系
    ↓
Figure 15: "E_MN 和 T_MN 有什么物理意义？"
    → E_MN ≈ 20 meV, T_MN ≈ 230 K
    ↓
Figure 16: "熵-焓补偿的物理本质是什么？"
    → 高能垒 ↔ 高构型熵
```

---

## ✅ 质量检查清单

### 通用检查
- [ ] 字体一致（Arial）
- [ ] 配色符合 AM 标准
- [ ] 坐标轴标签清晰
- [ ] 图例位置合理
- [ ] 统计信息框不遮挡数据
- [ ] 300 DPI 输出

### 统计检查
- [ ] 显著性标注正确（\* p<0.05, \*\* p<0.01, \*\*\* p<0.001）
- [ ] 误差棒/CI 计算正确
- [ ] 样本量 n 标注

---

**最后更新**: 2026-02-03
**配色方案版本**: v1.0
