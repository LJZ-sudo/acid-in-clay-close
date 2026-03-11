# Close项目快速启动指南

**版本**: v1.0 | **日期**: 2026-02-08

---

## 1. 项目简介

Close是一个**EIS电化学阻抗谱数据分析**的完整解决方案，实现了：
- **Phase 1**: 原始数据 → Arrhenius分析
- **Phase 2**: AI机理分析
- **Phase 3**: ML建模与闭环验证

---

## 2. 快速开始（5分钟）

### 2.1 环境检查

```bash
cd f:\proton\eis\V2.0\Acid in clay (2)\Acid in clay\V1.0-qianduan\close

# 检查Python环境
python --version  # 需要 Python 3.9+

# 安装依赖
pip install -r phase3/requirements.txt
```

### 2.2 一键运行全流程

```bash
# Phase 1: EIS数据处理
python phase1/run_batch.py --all

# Phase 2: AI分析（需要API密钥）
python run_phase2_complete.py

# Phase 3: ML建模
python phase3/run_all.py
```

---

## 3. 分阶段运行

### Phase 1: 数据处理

```bash
# 单个样品
python phase1/run_batch.py --sample S8-3-2-1

# 指定材料
python phase1/run_batch.py --material S8

# 输出位置
output/phase1_results/*.json
```

### Phase 2: AI分析

```bash
# 配置API密钥
# 编辑 config/api_config.py

# 运行AI分析
python run_phase2_complete.py

# 输出位置
output/phase2_reports/*.md
output/deep_analysis/S8_*.md
```

### Phase 3: ML建模

```bash
# 分步运行
python phase3/step1_data_preparation.py   # 数据准备
python phase3/step2_train_models.py        # 模型训练
python phase3/step3_confinement_analysis.py # 限域分析
python phase3/step4_ml_ai_validation.py   # ML-AI验证
python phase3/step_meyer_neldel.py        # 补偿分析
python phase3/step6_cross_material.py     # 跨材料验证
python phase3/step5_final_report.py       # 生成报告

# 或一键运行
python phase3/run_all.py

# 输出位置
output/phase3_results/
```

---

## 4. 核心文件索引

### 配置文件
| 文件 | 用途 |
|-----|------|
| `config/material_params.py` | R, N参数（26种组合） |
| `config/api_config.py` | OpenRouter API密钥 |
| `config/analysis_config.py` | 分析参数阈值 |

### 输入数据
| 位置 | 内容 |
|-----|------|
| `data/raw_eis/` | EIS原始数据 |
| `data/材料数据说明.xlsx` | 材料参数Excel |

### 输出结果
| 位置 | 内容 |
|-----|------|
| `output/phase1_results/` | Arrhenius分析JSON |
| `output/phase2_reports/` | AI机理报告 |
| `output/phase3_results/` | ML模型和统计结果 |
| `output/deep_analysis/` | S8深度分析 |

---

## 5. 关键参数

| 参数 | 符号 | 定义 | 范围 |
|-----|------|------|------|
| 酸水比 | R | n(H₃PO₄)/n(H₂O) | 0-1.04 |
| 液固比 | N | 液相/吸附剂质量 | 1-7 |
| 活化能 | Ea | 传导能垒 | 0.1-1.0 eV |

---

## 6. 常见问题

### Q1: API调用失败？
```bash
# 检查API密钥配置
cat config/api_config.py
# 确保OPENROUTER_API_KEY有效
```

### Q2: Phase 1输出为空？
```bash
# 检查原始数据路径
dir data\raw_eis\S8\
```

### Q3: Phase 3模型性能差？
```bash
# 检查Phase 1数据质量
# 确保R²>0.80的segment足够
```

---

## 7. 详细文档

- **完整分析报告**: `paper/CLOSE_PROJECT_ANALYSIS_REPORT.md`
- **综合指南**: `docs/CLOSE_PROJECT_COMPREHENSIVE_GUIDE.md`
- **论文写作**: `paper_figure/PAPER_FIGURES_INDEX.md`

---

## 8. 项目结构速览

```
close/
├── auto_control/     # 自动控制
├── config/           # 配置文件
├── data/             # 原始数据
├── phase1/           # Phase 1代码
├── phase2/           # Phase 2代码
├── phase3/           # Phase 3代码
├── output/           # 输出结果
├── paper_figure/     # 论文图表
├── paper/            # 论文相关
└── docs/             # 文档
```

---

**祝研究顺利！** 
