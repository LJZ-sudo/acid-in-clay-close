# 集成相变点检测工作流系统使用说明

## 系统概述

本系统实现了完整的温控相变点检测和精细化测量工作流，集成了以下核心功能：

### 🔧 核心组件

1. **温控器模块** (`temp_controller.py`)
   - 串口通信控制
   - 温度设置与监控
   - 被动升温等待

2. **CHI测量模块** (`run_chi.py`)
   - 自动化CHI电化学工作站控制
   - EIS阻抗谱测量
   - 数据自动保存

3. **数据处理模块**
   - `plot_bode.py`: Bode图生成
   - `rb_fitting.py`: Rb值拟合分析
   - `data_processing.py`: 数据滤波和相变点检测

4. **集成工作流** (`integrated_workflow.py`)
   - 完整工作流协调
   - 相变点检测逻辑
   - 精细化测量控制

## 🚀 工作流程

### 1. 粗测阶段
- 从起始温度开始，按粗测步长降温
- 每个温度点进行EIS测量
- 实时分析数据，检测相变特征

### 2. 相变点检测
- **相位突变检测**: 分析EIS数据的相位变化
- **Rb拟合分析**: 通过圆弧拟合识别相变
- **电导率突变**: 监控电导率变化率

### 3. 精细化测量
- 发现相变点后，确定相变区间
- 升温到相变区上限
- 按精细步长在相变区间进行密集测量

### 4. 数据处理
- 自动生成Bode图
- 执行Rb值拟合
- 计算电导率
- 生成实验报告

## 📋 使用方法

### 后端API接口

#### 启动工作流
```bash
POST /api/workflow/start_phase_transition
```
参数：
- `port`: 串口号 (默认: COM3)
- `T_start`: 起始温度 (°C)
- `T_end`: 目标温度 (°C)
- `coarse_step`: 粗测步长 (°C)
- `fine_step`: 精细步长 (°C)
- `thickness`: 样品厚度 (m)
- `area`: 样品截面积 (m²)
- `material`: 测试材料名称
- `high_freq`: 最高频率 (Hz)
- `low_freq`: 最低频率 (Hz)
- `init_voltage`: 初始电压 (V)

#### 获取状态
```bash
GET /api/workflow/status
```

#### 停止工作流
```bash
POST /api/workflow/stop
```

#### 导出数据
```bash
GET /api/workflow/export_data
```

#### 生成报告
```bash
POST /api/workflow/generate_report
```

### 前端界面

1. **温度控制页面**
   - 设置工作流参数
   - 启动/停止工作流
   - 实时状态监控

2. **工作流状态显示**
   - 当前温度
   - 测量次数
   - 相变点检测状态

3. **监控功能**
   - 实时数据监控
   - 状态更新
   - 数据导出

## ⚙️ 配置参数

### 温度控制参数
```python
workflow_config = {
    'port': 'COM3',           # 串口号
    'T_start': 20.0,          # 起始温度 (°C)
    'T_end': -30.0,           # 目标温度 (°C)
    'coarse_step': 10.0,      # 粗测步长 (°C)
    'fine_step': 3.0,         # 精细步长 (°C)
    'eps': 1.0,               # 温度误差容限 (°C)
    'thickness': 0.001,       # 样品厚度 (m)
    'area': 1e-4,             # 样品截面积 (m²)
}
```

### CHI测量参数
```python
chi_params = {
    "material": "Sample",      # 材料名称
    "highf": "10000",         # 最高频率 (Hz)
    "lowf": "1",              # 最低频率 (Hz)
    "initV": "0",             # 初始电压 (V)
    "text_confidence": 70,     # 文本识别置信度
    "delay": 0.1              # 操作延迟 (s)
}
```

## 📊 数据输出

### 文件结构
```
experiment_data/
├── eis_data/                 # EIS原始数据
├── bode_plots/              # Bode图
├── rb_fitting/              # Rb拟合图
├── conductivity/             # 电导率图
├── temperature_history.json  # 温度历史
├── measurement_history.json  # 测量历史
├── phase_transitions.json   # 相变点记录
└── experiment_report.json   # 实验报告
```

### 数据格式

#### 测量记录
```json
{
    "temperature": 20.0,
    "timestamp": 1640995200.0,
    "chi_result": {...},
    "eis_result": {...},
    "rb_result": {...},
    "conductivity": 1.23e-4,
    "phase_jump_detected": false
}
```

#### 相变点记录
```json
{
    "range": [10.0, -10.0],
    "detected_at": -5.0,
    "timestamp": 1640995200.0
}
```

## 🔍 相变点检测算法

### 1. 相位突变检测
```python
def detect_phase_jump(zreal, zimag, threshold=20):
    # 计算阻抗相位
    Z = zreal + 1j * zimag
    phase = np.angle(Z, deg=True)
    
    # 检测相位突变
    dphase = np.diff(phase)
    return np.any(np.abs(dphase) > threshold)
```

### 2. Rb拟合分析
```python
def calculate_rb(zreal, zimag, temp, params):
    # 线性拟合
    if is_linear(zreal, zimag, threshold):
        return linear_fit(zreal, zimag)
    
    # 圆弧拟合
    if detect_circle_fit(zreal, zimag):
        return circle_fit(zreal, zimag)
    
    # 宽松线性拟合
    return relaxed_linear_fit(zreal, zimag)
```

### 3. 电导率突变检测
```python
def check_conductivity_jump(current, previous, threshold=0.5):
    if previous > 0:
        change_ratio = abs(current - previous) / previous
        return change_ratio > threshold
    return False
```

## 🛠️ 故障排除

### 常见问题

1. **串口连接失败**
   - 检查串口号是否正确
   - 确认设备已连接
   - 检查驱动程序

2. **CHI测量失败**
   - 确认CHI软件已启动
   - 检查模板图片路径
   - 验证测量参数

3. **相变点检测不准确**
   - 调整检测阈值
   - 检查数据质量
   - 优化滤波参数

4. **温度控制异常**
   - 检查温控器连接
   - 验证温度传感器
   - 调整控制参数

### 调试方法

1. **启用详细日志**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **检查工作流状态**
```bash
GET /api/workflow/health
```

3. **导出调试数据**
```bash
GET /api/workflow/export_data
```

## 📈 性能优化

### 1. 数据采集优化
- 使用多线程并行处理
- 优化串口通信频率
- 实现数据缓存机制

### 2. 算法优化
- 使用GPU加速计算
- 优化拟合算法
- 实现增量更新

### 3. 存储优化
- 压缩数据文件
- 实现数据分片
- 优化文件I/O

## 🔮 未来扩展

### 1. 机器学习集成
- 基于历史数据的相变点预测
- 自适应参数调整
- 智能异常检测

### 2. 云端集成
- 远程监控和控制
- 数据云端存储
- 多设备协同

### 3. 高级分析
- 多维度相变分析
- 材料特性预测
- 实验方案优化

## 📞 技术支持

如有问题，请检查：
1. 系统日志文件
2. 网络连接状态
3. 设备硬件状态
4. 软件版本兼容性

---

**版本**: 1.0.0  
**更新日期**: 2024年12月  
**作者**: 25862 