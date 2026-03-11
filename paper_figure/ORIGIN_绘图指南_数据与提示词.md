# 使用 Origin 绘制 Figure 1 与 Figure 2 (S8) 的指南

## 一、数据文件位置

所有路径均相对于项目根目录 `V1.0-qianduan`，其下包含 `close` 文件夹。

### 图 1：Arrhenius 四段图（log σ vs 1000/T）

**数据文件：**
```
close/paper_figure/figure1_arrhenius_S8-3-9-3_4segments_data.csv
```

该 CSV 包含 **三个部分**（用空行和注释行 `# Part 1` 等分隔）：
- **Part 1 - 测量数据**：列名为 `1000_T_K_inv`, `T_K`, `T_C`, `sigma_S_cm`, `log10_sigma_mS_cm`
  - 绘图用：X = `1000_T_K_inv`，Y = `log10_sigma_mS_cm`
  - 顶部 X 轴（摄氏温度）可用 `T_C`
- **Part 2 - 四段拟合参数**：列名为 `segment`, `Ea_eV`, `ln_sigma0`, `T_low_K`, `T_high_K`, `r_squared`
  - 用于在图中画四条直线：每段用 Ea、ln_sigma0 和温区在 Arrhenius 坐标下算直线
  - 四段 Ea 约为：0.08, 0.16, 0.35, 0.90 eV
- **Part 3 - 断点**：一列 `breakpoint_1000_T_K_inv`（3 个数值）
  - 用于画三条垂直虚线，分隔四段

---

### 图 2：S8 断点温度分布（小提琴图）

**数据文件：**
```
close/paper_figure/figure2/figure2_violin_S8_data.csv
```

**列说明：**
| 列名 | 含义 |
|------|------|
| material | 固定为 S8 |
| sample_id | 样品编号 |
| breakpoint_index | 断点编号 1 / 2 / 3（对应 BP1, BP2, BP3） |
| temperature_K | 断点温度 (K) |
| total_segments | 该样品总段数（均为 4） |

绘图用：**X = breakpoint_index（分类：BP1, BP2, BP3）**，**Y = temperature_K**。每个 BP 有 21 个点。

---

## 二、给 GPT 的提示词（复制整段发送）

### 提示词 A：Arrhenius 四段图（Origin 逐步操作）

```
我需要在 Origin 里画一张 Arrhenius 图，具体要求如下。

【数据】
- 我有一个 CSV，路径是：close/paper_figure/figure1_arrhenius_S8-3-9-3_4segments_data.csv
- 文件里有多段：Part 1 是测量数据（1000_T_K_inv, T_K, T_C, sigma_S_cm, log10_sigma_mS_cm）；Part 2 是 4 段拟合参数（segment, Ea_eV, ln_sigma0, T_low_K, T_high_K, r_squared）；Part 3 是 3 个断点的 1000/T 值（breakpoint_1000_T_K_inv）。

【目标图】
- 类型：散点 + 分段直线 + 竖直虚线。
- 下 X 轴：1000/T (K⁻¹)，从左到右对应温度从高到低。
- 上 X 轴：T (°C)，与 1000/T 对应。
- Y 轴：log σ (mS·cm⁻¹)，即 CSV 里的 log10_sigma_mS_cm。
- 散点：用 Part 1 的 1000_T_K_inv 和 log10_sigma_mS_cm 画灰色/黑色点。
- 四条直线：根据 Part 2 的 4 段，每段在 (1000/T) 的 [T_high_K, T_low_K] 对应范围内，用 Ea_eV 和 ln_sigma0 计算 ln(σ)=ln_sigma0 - Ea_eV/(k_B*T)，再转换成 log10(σ_mS/cm) 画线段（或用 Origin 的线性拟合在每段数据上拟合）。四条线用不同颜色：粉红、绿、橙、紫。
- 三条竖直虚线：在 Part 3 的 3 个 breakpoint_1000_T_K_inv 处画竖直虚线，分隔四段。
- 图例标出每段 Ea（0.08, 0.16, 0.35, 0.90 eV）和 R²。

请按步骤说明：1）如何在 Origin 中导入该 CSV（若有多段，如何分别导入或分 sheet）；2）如何设置双 X 轴（下 1000/T，上 T°C）；3）如何画散点；4）如何根据拟合参数或分段数据画四条直线；5）如何加三条竖直虚线；6）如何加图例和标注。每步要具体到菜单或按钮名称（英文版 Origin 即可）。
```

---

### 提示词 B：S8 断点温度小提琴图（Origin 逐步操作）

```
我需要在 Origin 里画一张小提琴图（Violin Plot），只针对 S8 样品。

【数据】
- CSV 路径：close/paper_figure/figure2/figure2_violin_S8_data.csv
- 列：material, sample_id, breakpoint_index, temperature_K, total_segments
- breakpoint_index 取值为 1, 2, 3（对应 BP1, BP2, BP3）；temperature_K 是断点温度（单位 K）。每个 BP 有 21 个数据点。

【目标图】
- 图类型：Violin Plot（或 Box Plot + 分布形状）。
- X 轴：分类变量，三组 BP1、BP2、BP3（对应 breakpoint_index 1, 2, 3）。
- Y 轴：Temperature (K)，范围大约 195–295 K。
- 每个分类下显示该组 temperature_K 的分布（小提琴形状或箱线+密度），同一组用同一种颜色（例如粉红 #E91E63）。
- 图中标出每组的均值±标准差或中位数、四分位数，例如：BP1 273±7 K，BP2 250±9 K，BP3 221±9 K（n=21）。
- 标题：Temperature Distribution of Arrhenius Breakpoints (S8)。

请按步骤说明：1）如何在 Origin 中导入该 CSV；2）如何选择/设置 Violin Plot（若 Origin 没有 Violin，请用最接近的选项如箱线图+散点或分布图，并说明）；3）如何设置 X 为分类（BP1/BP2/BP3）、Y 为 temperature_K；4）如何设置颜色和添加统计量标注；5）如何添加标题和坐标轴标签。每步要具体到菜单或按钮名称（英文版 Origin）。
```

---

## 三、使用说明

1. **先确认路径**：在你自己电脑上打开 `close/paper_figure/` 和 `close/paper_figure/figure2/`，确认上述两个 CSV 存在；若项目不在 `V1.0-qianduan`，把提示词里的路径改成你的实际路径。
2. **复制提示词**：需要画 Arrhenius 图就复制「提示词 A」，需要画 S8 小提琴图就复制「提示词 B」。
3. **发给 GPT**：将复制的内容完整粘贴给 ChatGPT（或其它 GPT），请它按步骤写出在 Origin 中的具体操作（菜单、图形类型、坐标轴、图例等）。
4. **按步骤在 Origin 中操作**：跟着 GPT 的步骤在 Origin 里导入数据、选图类型、设置坐标轴和样式，即可复现两张图。

若 CSV 在 Origin 里需要分两次导入（例如 Part 1 和 Part 2 分开），可在提示词中补充一句：“若一个 CSV 里有多段，请说明如何分两次导入到不同 Sheet 或不同 Book。”
