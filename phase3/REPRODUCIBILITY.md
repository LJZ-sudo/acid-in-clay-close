# Phase 3 可复现性说明（P2）

用于论文 SI 或代码库的“数据与代码可用性”说明，便于审稿与复现。

---

## 1. 运行命令

在 **close** 目录下执行（或从项目根目录指定 close 路径）：

```bash
# 一键运行全流程（推荐）
python phase3/run_all.py
```

或分步执行：

```bash
python phase3/step1_data_preparation.py   # 从 phase1_results 提取 segment 数据
python phase3/step2_train_models.py       # 训练 S60 基线 + S8 限域模型
python phase3/step3_confinement_analysis.py  # ΔEa 分析、bootstrap CI、显著性检验
python phase3/step4_ml_ai_validation.py   # ML–AI 区间对照
python phase3/step_meyer_neldel.py       # Meyer-Neldel 分析
python phase3/step6_cross_material.py   # 跨材料验证（S8 模型迁移）
python phase3/step5_final_report.py     # 生成汇总报告
```

**前提**：`close/output/phase1_results/` 下已有 `*_analysis_result.json`（Phase 1 输出）。

---

## 2. 环境与依赖

- **Python**：建议 3.8 及以上。
- **主要库**（见 `phase3/requirements.txt`）：
  - pandas
  - numpy
  - scikit-learn
  - matplotlib

安装示例：

```bash
pip install -r phase3/requirements.txt
```

若项目根目录已有统一 `requirements.txt`，可只安装上述四个库。

---

## 3. 随机种子

- **S8 限域模型**（GradientBoostingRegressor）：`random_state=42`（见 `step2_train_models.py`）。
- 其他步骤（bootstrap、KFold）未固定种子时，多次运行数值可能略有差异；若需完全一致，可在各脚本中为 `np.random` 与 `sklearn` 的 CV 设置相同种子。

---

## 4. 预期输出文件列表

运行成功后，`close/output/phase3_results/` 下应包含：

| 路径 | 说明 |
|------|------|
| `integrated_data.csv` | step1：segment 级数据 |
| `models/s60_baseline.pkl` | step2：S60 模型 |
| `models/s8_confinement.pkl` | step2：S8 模型 |
| `models/metrics.json` | step2：R²、CV R²、ΔEa 范围等 |
| `confinement/delta_ea_by_segment.csv` | step3：ΔEa 明细 |
| `confinement/delta_ea_plot.png` | step3：ΔEa–T 图 |
| `confinement/summary.json` | step3：ΔEa 及 95%CI、t 检验、ΔEa(T) 拟合 |
| `ml_ai_validation.json` | step4：区间内 vs 区间外 mean(Ea) 对照 |
| `meyer_neldel/summary.json` | step_meyer_neldel：E_MN、R²、p |
| `meyer_neldel/meyer_neldel_s8.png` | ln(σ₀)–Ea 图 |
| `cross_material/summary.json` | step6：跨材料 α=Ea_实际/Ea_预测 汇总 |
| `cross_material/cross_material_details.csv` | step6：跨材料明细 |
| `phase3_final_report.md` | step5：汇总报告 |

---

## 5. 数据来源

- 输入仅来自 **close 内**：`close/output/phase1_results/*_analysis_result.json`。
- 不依赖项目根目录下其他 EIS 或 phase2 输出；phase2 报告仅用于 step4 的 AI 推荐区间定义（可选）。

---

## 6. 版本记录（可选）

复现时建议记录：

- Python 版本（如 `python --version`）
- 主要库版本（如 `pip list | grep -E "pandas|numpy|scikit-learn|matplotlib"`）
- 运行日期与 `phase3_final_report.md` 生成时间

可将上述信息放入 SI 或补充材料“Data and Code Availability”小节。
