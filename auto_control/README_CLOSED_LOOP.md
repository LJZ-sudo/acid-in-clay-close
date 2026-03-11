# 闭环流程快速开始

## 🚀 快速开始（5分钟）

### 步骤1：运行闭环分析

```cmd
cd D:\代码集\代码集
python auto_control\run_closed_loop.py --data-dir E:\chi_data --thickness 0.02 --area 1.5
```

### 步骤2：查看报告

```cmd
type experiment_data\report.json
type experiment_data\report.md
```

### 步骤3：检查失败点

```cmd
python -c "import json; report=json.load(open('experiment_data/report.json')); [print(f\"❌ T={fp['temperature_C']}°C: {fp['failure_reason']}\") for fp in report['failed_points']]"
```

---

## 📊 输出产物

| 文件 | 路径 | 说明 |
|------|------|------|
| **JSON报告** | `experiment_data/report.json` | 完整的结构化报告 |
| **Markdown报告** | `experiment_data/report.md` | 可读性强的报告 |
| **圆拟合图片** | `experiment_data/circle_fits/*.png` | 圆弧拟合图片 |

---

## ✅ 验收标准

### 1. 失败点可追溯
```cmd
python -c "import json; report=json.load(open('experiment_data/report.json')); print('\n'.join([f\"T={fp['temperature_C']}°C: {fp['failure_reason']} ({fp['raw_data_path']})\" for fp in report['failed_points']]))"
```

### 2. 无模拟数据污染
```cmd
grep -i "random\|模拟\|simulation" experiment_data/report.json
```
预期：无匹配

### 3. Arrhenius数据点要求
```cmd
python -c "import json; report=json.load(open('experiment_data/report.json')); arr=report['arrhenius_analysis']; print(f\"成功: {arr['success']}, 数据点: {arr['data_points']}, 消息: {arr['message']}\")"
```

### 4. raw_data_path映射完整
```cmd
python -c "import json; report=json.load(open('experiment_data/report.json')); print(f\"映射条目: {len(report['raw_data_mapping'])}个\")"
```

---

## 📚 详细文档

- **使用说明**: `docs/closed_loop_usage.md`
- **实施总结**: `docs/closed_loop_implementation_summary.md`
- **report.json结构**: `docs/report_schema_example.json`

---

## 🔧 常见问题

### Q: 找不到CHI数据文件？
```cmd
dir E:\chi_data\*.txt
```
如果目录不对，使用 `--data-dir` 指定正确路径。

### Q: Arrhenius分析失败（数据点不足）？
降低最少点数要求：
```cmd
python auto_control\run_closed_loop.py --data-dir E:\chi_data --min-points 3
```

### Q: 想先测试单个文件？
使用离线测试脚本：
```cmd
python tools\offline_rb_fitting_test.py --file "E:\chi_data\PSE-2_T25C_f0.1_1000000_V0.txt"
```

---

## 🎯 下一步

1. ✅ 运行闭环分析
2. ✅ 查看 report.json 和 report.md
3. ✅ 分析失败原因
4. ✅ 优化拟合参数（如果需要）
5. ✅ 集成到 integrated_temp_chi_controller.py（可选）

