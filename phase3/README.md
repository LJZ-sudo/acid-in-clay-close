# Phase 3：建模与科学分析（close 内闭环）

**数据来源**：仅使用 `close/output/phase1_results/*.json`（Phase 1 输出）  
**参考**：`close/output/phase2_reports/`、`close/output/deep_analysis/S8_deep_mechanism_analysis.md`（用于 ML-AI 验证）  
**输出**：`close/output/phase3_results/`

---

## 目标

1. **S60 基准模型**：Ea = f(R, T)，纯酸液“无限域”基线  
2. **S8 限域效应模型**：Ea = f(R, T, N) + 交互项  
3. **量化限域**：ΔEa = Ea(S8) − Ea(S60 预测)  
4. **科学验证**：ΔEa vs T/N、与 S8 深度报告对照、可选 Meyer-Neldel  
5. **论文产出**：图表、结果汇总、报告

---

## 步骤与执行顺序

```bash
# 在 close 目录下执行（或从项目根目录 python close/phase3/step1_data_preparation.py）
python phase3/step1_data_preparation.py   # 从 phase1_results 提取 segment 级数据
python phase3/step2_train_models.py        # 训练 S60 基线 + S8 限域模型（S60 含异常值剔除与正则）
python phase3/step3_confinement_analysis.py # ΔEa 分析、bootstrap 95%CI、低温 vs 高温显著性检验
python phase3/step4_ml_ai_validation.py   # ML 与 AI 报告交叉验证（方案 B：区间内 vs 区间外）
python phase3/step_meyer_neldel.py        # Meyer-Neldel 分析 ln(σ₀)–Ea
python phase3/step6_cross_material.py    # 跨材料验证（S8 模型迁移，α=Ea_实际/Ea_预测）
python phase3/step5_final_report.py      # 生成 Phase 3 汇总报告
```

或一次性运行：

```bash
python phase3/run_all.py
```

**可复现性**：运行命令、依赖、随机种子与预期输出见 `phase3/REPRODUCIBILITY.md`；依赖列表见 `phase3/requirements.txt`。

---

## 输出目录结构

```
close/output/phase3_results/
├── integrated_data.csv      # step1 输出：segment 级 (sample_id, material_type, R, N, T_avg_K, Ea_eV, ln_sigma0, ...)
├── models/
│   ├── s60_baseline.pkl     # step2：S60 模型
│   ├── s8_confinement.pkl   # step2：S8 模型
│   └── metrics.json        # step2：R²、ΔEa 范围等
├── confinement/
│   ├── delta_ea_by_T.csv    # step3：ΔEa vs T
│   ├── delta_ea_plot.png    # step3：ΔEa-T 图
│   └── summary.json
├── confinement/summary.json # step3：ΔEa 及 95%CI、低温 vs 高温 t 检验、ΔEa(T) 拟合
├── ml_ai_validation.json   # step4：区间内 vs 区间外 mean(Ea) 对照（方案 B）
├── meyer_neldel/            # step_meyer_neldel：E_MN、R²、ln(σ₀)–Ea 图
├── cross_material/          # step6：跨材料验证 summary.json、cross_material_details.csv
└── phase3_final_report.md  # step5：汇总报告
```
