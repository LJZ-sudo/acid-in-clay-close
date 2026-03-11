# Close项目数据流程与模块依赖关系

**版本**: v1.0 | **日期**: 2026-02-08

---

## 1. 整体数据流程图

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           CLOSE PROJECT DATA FLOW                          │
└───────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │   原始EIS数据     │
                              │  data/raw_eis/   │
                              │   (.DTA/.txt)    │
                              └────────┬─────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PHASE 1                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │ EIS解析     │ → │ Rb拟合      │ → │ σ计算       │ → │ Arrhenius   │   │
│  │ (频率,Z)    │    │ (圆弧拟合)  │    │ σ=L/(Rb·S)  │    │ (分段拟合)  │   │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘   │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          ▼
                              ┌──────────────────┐
                              │  Phase 1 输出    │
                              │ phase1_results/  │
                              │    (*.json)      │
                              │  Ea, σ₀, R², T  │
                              └────────┬─────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐
│      PHASE 2          │  │      PHASE 3          │  │   PHASE 3 v2.0        │
│                       │  │                       │  │   (Agent版本)         │
│  ┌─────────────────┐  │  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │
│  │ LLM API调用     │  │  │  │ S60基线模型     │  │  │  │ ReAct Agent    │  │
│  │ (Claude Opus)   │  │  │  │ (Ridge回归)     │  │  │  │ (工具调用)     │  │
│  └─────────────────┘  │  │  └─────────────────┘  │  │  └─────────────────┘  │
│          │            │  │          │            │  │          │            │
│          ▼            │  │          ▼            │  │          ▼            │
│  ┌─────────────────┐  │  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │
│  │ 机理分析报告    │  │  │  │ S8限域模型      │  │  │  │ 智能分析报告   │  │
│  │ (Markdown)      │  │  │  │ (GradientBoost) │  │  │  │ (HTML/JSON)    │  │
│  └─────────────────┘  │  │  └─────────────────┘  │  │  └─────────────────┘  │
│          │            │  │          │            │  │                       │
│          ▼            │  │          ▼            │  │                       │
│  ┌─────────────────┐  │  │  ┌─────────────────┐  │  │                       │
│  │ 配方推荐        │  │  │  │ ΔEa量化        │  │  │                       │
│  │ (最优R-N区间)   │  │  │  │ (限域效应)      │  │  │                       │
│  └─────────────────┘  │  │  └─────────────────┘  │  │                       │
│                       │  │          │            │  │                       │
│     phase2_reports/   │  │          ▼            │  │   phase3v2_results/   │
│     deep_analysis/    │  │  ┌─────────────────┐  │  │                       │
│                       │  │  │ 统计分析        │  │  │                       │
└───────────────────────┘  │  │ (CI, t检验)     │  │  └───────────────────────┘
            │              │  └─────────────────┘  │
            │              │          │            │
            │              │          ▼            │
            │              │  ┌─────────────────┐  │
            │              │  │ Meyer-Neldel    │  │
            │              │  │ (补偿分析)       │  │
            │              │  └─────────────────┘  │
            │              │          │            │
            │              │          ▼            │
            │              │  ┌─────────────────┐  │
            │              │  │ 跨材料验证      │  │
            │              │  │ (α指标)         │  │
            │              │  └─────────────────┘  │
            │              │          │            │
            │              │    phase3_results/    │
            │              └──────────┬────────────┘
            │                         │
            └────────────┬────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   ML-AI 交叉验证     │
              │  step4_ml_ai_        │
              │  validation.py       │
              │                      │
              │ AI推荐区间 vs ML预测 │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   最终汇总报告       │
              │  phase3_final_       │
              │  report.md           │
              └──────────────────────┘
```

---

## 2. 模块依赖关系

### 2.1 Phase 1 模块依赖

```
phase1/
├── run_batch.py
│   ├── step1_parse_eis.py
│   │   └── specific_conductance/data_processing.py
│   ├── step2_arrhenius_fit.py
│   │   └── auto_control/modules/arrhenius.py
│   └── config/material_params.py
│
specific_conductance/
├── main.py
│   ├── conductivity.py ─────────┐
│   ├── rb_fitting.py ──────────┤─→ utils/math_utils.py
│   └── data_processing.py ─────┘
│
auto_control/modules/
├── rb_fit.py
├── arrhenius.py
├── kk_validation.py
└── unified_eis_processor.py
```

### 2.2 Phase 2 模块依赖

```
phase2/
├── run_batch_reports.py
│   ├── utils/llm_api.py
│   │   └── config/api_config.py (API密钥)
│   ├── utils/prompts.py
│   └── output/phase1_results/*.json (输入)
│
├── run_s8_deep_analysis.py
│   ├── utils/llm_api.py
│   └── output/phase1_results/S8-*.json
│
run_phase2_complete.py
├── phase2/run_batch_reports.py
└── phase2/run_s8_deep_analysis.py
```

### 2.3 Phase 3 模块依赖

```
phase3/
├── run_all.py
│   ├── step1_data_preparation.py
│   │   └── output/phase1_results/*.json
│   │
│   ├── step2_train_models.py
│   │   ├── sklearn.linear_model.Ridge
│   │   ├── sklearn.ensemble.GradientBoostingRegressor
│   │   └── integrated_data.csv (step1输出)
│   │
│   ├── step3_confinement_analysis.py
│   │   ├── models/*.pkl (step2输出)
│   │   └── utils/math_utils.py (bootstrap, t-test)
│   │
│   ├── step4_ml_ai_validation.py
│   │   ├── output/phase2_reports/*.md (Phase 2输出)
│   │   └── models/*.pkl (step2输出)
│   │
│   ├── step_meyer_neldel.py
│   │   └── integrated_data.csv
│   │
│   ├── step6_cross_material.py
│   │   └── models/s8_confinement.pkl
│   │
│   └── step5_final_report.py
│       └── 所有步骤输出
```

### 2.4 Phase 3 v2.0 (Agent) 依赖

```
phase3-v2.0/
├── run_agent.py
│   ├── react_agent.py
│   │   ├── tools.py (工具定义)
│   │   ├── tool_schemas.py (工具schema)
│   │   └── enhanced_prompts.py
│   │
│   ├── agent.py (基础Agent)
│   │
│   └── report_generator.py
│       └── output/phase3v2_results/
```

---

## 3. 数据格式说明

### 3.1 原始EIS数据 (.DTA)

```
# 典型格式
FREQ      ZREAL     ZIMAG
1.0e6     100.5     -50.2
5.0e5     120.3     -80.5
...
```

### 3.2 Phase 1 输出 (JSON)

```json
{
  "sample_id": "S8-3-2-1",
  "material_type": "S8",
  "R": 0.3,
  "N": 2.5,
  "L_cm": 0.12,
  "S_cm2": 3.95,
  "segments": [
    {
      "segment_index": 0,
      "temperature_range_K": [213, 253],
      "T_avg_K": 233.0,
      "Ea_eV": 0.456,
      "ln_sigma0": 8.234,
      "R_squared": 0.982,
      "n_points": 5,
      "data_points": [
        {"T_K": 213, "sigma_S_cm": 1.2e-6},
        {"T_K": 223, "sigma_S_cm": 3.5e-6},
        ...
      ]
    }
  ]
}
```

### 3.3 Phase 3 integrated_data.csv

| 列名 | 类型 | 说明 |
|-----|------|------|
| sample_id | str | 样品ID |
| material_type | str | 材料类型 (S8/S60/...) |
| R | float | 酸水比 |
| N | float | 液固比 |
| segment_index | int | 分段索引 |
| T_avg_K | float | 平均温度 (K) |
| Ea_eV | float | 活化能 (eV) |
| ln_sigma0 | float | ln(前因子) |
| R_squared | float | 拟合R² |

### 3.4 Phase 3 模型输出 (metrics.json)

```json
{
  "s60_baseline": {
    "model_type": "Ridge",
    "alpha": 20,
    "features": ["R", "T"],
    "train_r2": 0.90,
    "cv_r2_mean": 0.89,
    "cv_r2_std": 0.03,
    "mae": 0.069,
    "n_samples": 59,
    "coefficients": {
      "intercept": 0.42,
      "R": -0.25,
      "T": -0.00035
    }
  },
  "s8_confinement": {
    "model_type": "GradientBoosting",
    "n_estimators": 100,
    "max_depth": 4,
    "features": ["R", "N", "T", "R*N", "R*T", "N*T"],
    "train_r2": 0.97,
    "cv_r2_mean": 0.81,
    "cv_r2_std": 0.05,
    "feature_importance": {
      "T": 0.35,
      "R": 0.28,
      "N": 0.20,
      "R*N": 0.10,
      "R*T": 0.04,
      "N*T": 0.03
    }
  }
}
```

---

## 4. 关键算法说明

### 4.1 Rb圆弧拟合

```python
# 最小二乘圆拟合
# 目标：从 (Z_real, Z_imag) 数据拟合圆心和半径

def fit_circle_least_squares(Z_real, Z_imag):
    """
    输入: Z_real[n], Z_imag[n] - EIS数据
    输出: Rb (体电阻), (x0, y0, r) (圆心和半径), R²
    
    数学原理:
    (Z' - x₀)² + (Z'' - y₀)² = r²
    
    线性化后最小二乘求解:
    A = [Z', Z'', 1]
    b = -(Z'² + Z''²)
    β = (AᵀA)⁻¹Aᵀb
    
    Rb = x₀ + r (圆与实轴右交点)
    """
```

### 4.2 Arrhenius分段拟合

```python
# Arrhenius方程: σ(T) = σ₀ · exp(-Ea/kᵦT)
# 对数形式: ln(σ) = ln(σ₀) - Ea/(kᵦT)

def arrhenius_fit(T_K, sigma_S_cm):
    """
    输入: T_K[] (温度), sigma_S_cm[] (电导率)
    输出: Ea (eV), ln_sigma0, R², 分段边界
    
    分段策略:
    - 低温: T < 230 K
    - 中温: 230 ≤ T < 270 K
    - 高温: T ≥ 270 K
    
    质量控制:
    - 每段 n ≥ 3
    - R² > 0.80
    - Ea ∈ [0.01, 1.5] eV
    """
```

### 4.3 ΔEa限域效应计算

```python
# ΔEa = Ea_S8_observed - Ea_S60_predicted

def calculate_delta_ea(df_s8, model_s60, scaler_s60):
    """
    输入: S8数据, S60模型, 标准化器
    输出: ΔEa数组
    
    步骤:
    1. 提取S8的[R, T]特征
    2. 用S60模型预测Ea_baseline
    3. ΔEa = Ea_S8 - Ea_S60_pred
    
    统计分析:
    - Bootstrap 95% CI
    - 低温 vs 高温 t检验
    - ΔEa(T) 线性拟合
    """
```

### 4.4 Meyer-Neldel补偿分析

```python
# 补偿关系: ln(σ₀) = A + B × Ea
# E_MN = 1/B (补偿能)
# T_MN = E_MN/kᵦ (补偿温度)

def meyer_neldel_fit(Ea_eV, ln_sigma0):
    """
    输入: Ea[], ln_sigma0[]
    输出: E_MN (eV), R², 斜率B
    
    物理意义:
    - E_MN ≈ 0.021 eV → T_MN ≈ 244 K
    - 在T_MN附近，不同Ea样品的σ相近
    """
```

---

## 5. 运行顺序与依赖检查

### 5.1 执行顺序

```
1. Phase 1 (必须首先运行)
   └─→ 生成 phase1_results/*.json

2. Phase 2 (依赖Phase 1)
   └─→ 需要 phase1_results/*.json
   └─→ 生成 phase2_reports/*.md

3. Phase 3 (依赖Phase 1和2)
   └─→ 需要 phase1_results/*.json
   └─→ step4需要 phase2_reports/*.md
   └─→ 生成 phase3_results/
```

### 5.2 依赖检查脚本

```python
# 示例: 检查Phase 3依赖
import os
import sys

def check_phase3_dependencies():
    required_files = [
        "output/phase1_results/",  # 必须存在
        "output/phase2_reports/",  # step4需要
    ]
    
    missing = []
    for f in required_files:
        if not os.path.exists(f):
            missing.append(f)
    
    if missing:
        print(f"缺少依赖: {missing}")
        print("请先运行 Phase 1 和 Phase 2")
        sys.exit(1)
    
    return True
```

---

## 6. 输出文件汇总

| 阶段 | 输出目录 | 主要文件 | 格式 |
|-----|---------|---------|------|
| Phase 1 | `output/phase1_results/` | `*_analysis_result.json` | JSON |
| Phase 2 | `output/phase2_reports/` | `*.md` | Markdown |
| Phase 2 | `output/deep_analysis/` | `S8_*.md`, `*.html` | MD/HTML |
| Phase 3 | `output/phase3_results/models/` | `*.pkl` | Pickle |
| Phase 3 | `output/phase3_results/confinement/` | `*.png`, `*.json` | PNG/JSON |
| Phase 3 | `output/phase3_results/meyer_neldel/` | `*.png`, `*.json` | PNG/JSON |
| Phase 3 | `output/phase3_results/cross_material/` | `*.json` | JSON |
| Phase 3 | `output/phase3_results/` | `phase3_final_report.md` | Markdown |

---

**文档结束**
