# Pillar 2 — Cooling-resilient pathway continuity descriptor

本目录汇总 Pillar 2 的"QC-gated EIS 证据 + 基准条件审计 + 表格 / 图数据"，
对应论文创新点 **"冷却-鲁棒的通路连续性描述符"**：以 LRS 为正向验证、CHITO 为边界验证。

> 数据来源：从 stage0 EIS QC 与基准对照流程**抽取**而来的最小必要证据。
> 计算管线代码仍在 `V1.0-qianduan-mainline/stage0_measurement/` 与
> `V1.0-qianduan-mainline/stage2_statistics/` 中；本目录只保留 QC-gated 结果。

---

## 子目录与文件

### `eis_qc_v2/` — QC-gated EIS 证据
- `eis_qc_v2_summary.json` / `.md` — 三级 QC（几何、温度序、Rb 拟合）通过率与样本筛选总结
- `geometry_audit_v2.csv` — 几何审计明细（厚度、A、几何 σ）
- `temperature_sequence_audit_v2.csv` — 温度序审计（升降温内插一致性、滞后）
- `selected_rb_qc_v2.csv` — manual vs auto Rb 拟合对照 + QC pass / hold flag
- `sample_qc_summary_v2.csv` — 样本级 QC pass 矩阵
- `stage0_eis_qc_diagnostics_v2.csv` / `.json` — 与 stage0 工具链同步的 QC 诊断
- `representative_nyquist_index_v2.csv` — 代表性 Nyquist 谱索引
- `representative_nyquist/` — 6 张代表性 Nyquist 源数据（CS / Tm-20°C / Tm-38°C / Tp-1°C / Tm-21°C / Tm-39°C / Tp-0°C）

### `benchmark_condition_audit/` — 基准条件审计
- `benchmark_condition_audit.csv` / `_report.{json,md}` — 与文献基准比较时各条件差异（温度区间、湿度、厚度、电极）的逐项审计

### `figure_data/` — 论文图源数据
- `ea_benchmark_table.csv` — LRS Ea 对文献基准表数据（用于 Figure 4 / 5）
- `wide_temperature_performance_summary.csv` — 宽温区性能汇总（条带图源数据）

### `tables/` — 论文表数据
- `final_benchmark_table.csv` — 最终基准表（Conductivity / Ea / T 区间 / 引文）

---

## 与代码主体的关系

本目录是 **"已经过 QC 闸门的证据快照"**：

- 上游：`V1.0-qianduan-mainline/stage0_measurement/` 的 EIS 测量 + KK-RB 拟合
- 中游：`V1.0-qianduan-mainline/stage2_statistics/main_agent.py` 的统计 V2 管线
- 下游：本目录的 csv / json 直接被论文图表 / 表格引用

如需重新生成 QC 证据，按上述路径重跑 stage0 → stage2 即可。本目录不应被
任何代码自动写入（避免循环引用）。
