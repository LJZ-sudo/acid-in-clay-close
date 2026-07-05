# P1 — DRT / 传输侧弛豫(真实结论:**DRT 不可行,诚实排除**)

> 生成:`drt_evolution.py`(纯读 `lineA_LRS_6.15_merged` 的真实原始 CHI 谱,经 stage0 `parse_chi_file` + `analyze_drt`)。
> 对应 `THREE_INNOVATIONS_CODE_GROUNDED_20260618.md` §9 的 **P1**。

## 运行
```bash
python _new_data_analysis/drt/drt_evolution.py
```
产物:`relaxation_evolution.json` / `relaxation_evolution.png`。

## 两个真实发现(均为负面,如实报告)

1. **标准 Tikhonov DRT 在本数据上不可靠**:59 个温度点,重构 **R² 全部 < 0**(范围 [−190.96, −0.18]),
   `0/59` 达到 R²>0.8。原因:低频是**电极阻塞型大容性尾**(|Z''| 高达 ~22 kΩ vs Z' ~5 kΩ),
   超出纯弛豫核能表示的范围;高频弧截断后 R² 反而更差(−34~−65),排除"截断可救"。
2. **模型无关弛豫频率也提不出**:`f_peak = argmax_f(−Z'')` 的弧顶,在 **57/59** 个点**无法检测**
   (谱在 −Z'' 上是单调尾型、无弧顶局部极大);仅有的 2 个"峰"恰好落在 P0 标记的 **物理坏点**上(异常谱形产生的假极大)。

## 结论(写论文按此)

- **P1 不依赖 DRT / 弛豫分析**。这正好用真实数据印证了 §1 的既定立场:
  *"不硬拟合单一等效电路,改用模型无关的 Rb + 分段 Ea + 转变温——绕开而非假装解决"*。
- 传输侧证据严格限定为 **Rb(实轴截距)+ σ + 分段 Arrhenius + 转变温**(这些在 P0 已确证跨批次可复现)。
- **不声称** DRT 弛豫机理 / 微观结构。

## 代码侧改动(架构接通 + QC 门,零行为回归)

- `stage0_measurement/modules/closure/closure_features.py`:把原先**写死**的 `drt_peaks=[]`
  改为 `_extract_drt_peaks(bundle)`——**带可靠性门(R²>0.8)**:
  - 当前 bundle 不带 drt / DRT 不可靠 → 返回 `[]`(**与原行为完全一致**,已单元验证)。
  - 未来若有可靠 DRT(R²>0.8)→ 峰自动经门流入。
- 即:接口接通了"线",但**门确保不可靠的 DRT 峰永远进不了 closure 卡**,符合项目 QC/不过度声称纪律。

## 诚实局限

- 该结论基于 LRS 6.15(藕粉)宽温谱;其它体系/更低起始频率(<0.1 Hz)可能不同,但**本篇数据范围内 DRT 不可用**。
- 这是一个**负面但有价值**的结果:它把"为什么用 Rb/Arrhenius 而非 DRT"从"作者选择"变成"**数据驱动的被迫且正确的选择**"。
