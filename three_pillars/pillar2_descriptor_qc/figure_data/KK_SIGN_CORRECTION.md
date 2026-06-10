# KK 符号约定更正说明（2026-06-10）

## 摘要
在审稿前自查中发现：Kramers–Kronig（KK）一致性校验存在一处**复数阻抗符号约定 bug**，
导致历史 `n_kk_warning` 计数被系统性高估。修正后，全样品 EIS 谱 KK 一致性良好。
**本更正不改变任何科学数字**（Eₐ、σ 均由 Rb 过零点/相位拟合得到，与 KK 无关）。

## 根因
- 解析器 `stage0_measurement/modules/io_utils/chi_parser.py` 把数据文件第 3 列（`Z''`）
  **原样**读入 `z_imag`。该列即真实虚部 `Im(Z)`：容抗弧区为负、(高频)感抗尾为正。
- KK 校验 `modules/analysis/algorithms/kk_validation.py` 旧代码假设传入虚部是"正幅值"，
  用 `Z = Zr − jZi`，等于把每条谱翻成**反因果共轭**。lin-KK（impedance 库，Schönleber 2014）
  以因果 RC(Voigt) 串联拟合，无法拟合反因果谱 → 残差被系统性抬高 → 大量假警告。

## 修复（隔离，仅 KK 校验）
`kk_validation.py`：
1. 复数阻抗改为 `Z = Zr + 1j*Zi`（容性 Im(Z)<0，物理正确）。
2. 新增默认开启的高频感性尾 / 非物理负实部裁剪（`trim_inductive_tail=True`）。
3. details 增加 `sign_convention`、`n_inductive_trimmed` 溯源字段。
- **未改** `chi_parser.py`；**未改** Rb/σ/Arrhenius（它们不依赖 KK）。

## 实测影响（脚本可复现）
- `manuscript/figures/kk_diagnostic.py`：单谱三种处理对照。
- `manuscript/figures/kk_verify_all.py`：全样 220 条谱统计。
- 全样品 KK 警告（μ_median ≥ 0.2）：**修正前 133/220（60%）→ 修正后 0/220**。
- μ_median：修正前 ~0.21–0.28 → 修正后 ~0.005–0.012。

## 本文件 `wide_temperature_performance_summary.csv` 的更正
| sample | n_kk_warning（旧，bug） | n_kk_warning（修正后） |
|---|---|---|
| 2026.4.27CS | 19 | 0 |
| 2026.4.28CS | 14 | 0 |
| 2026.4.29CS | 24 | 0 |
| 2026.4.30CS | 6 | 0 |
| 2026.5.1CS | 4 | 0 |
| 2026.5.9CS | 27 | 0 |

`quality_caveat` 中涉及 KK 的措辞已相应更新；Rb 一致性相关 caveat 保留（独立 QC 轴，未受影响）。

## 关于冻结的 Stage0 产物
原始 `stage0_measurement` 下各 `aggregated_results.json` 的 `kk_warning` 布尔值
**早于本次修复**，按"冻结不动以保前瞻证据链"的原则保留原样；其 KK 字段应视为
pre-fix legacy。汇总层（本目录）与论文均采用修正后的计数。
