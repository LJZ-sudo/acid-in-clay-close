# SI Note 3: Experimental Methods & Hardware Configuration

> ⚠️ **占位标记说明**: 标有 `[PLACEHOLDER]` 的内容为临时占位，需要用真实实验数据替换。标有 `[VERIFIED]` 的内容已从代码/数据中确认。

## 1. Hardware Configuration

### 1.1 Electrochemical Workstation

- **型号**: `[PLACEHOLDER: CHI型号，如CHI660E/CHI760E]`
- **EIS频率范围**: `[PLACEHOLDER: 如 1 Hz – 1 MHz]`
- **AC振幅**: `[PLACEHOLDER: 如 10 mV rms]`
- **数据采集点数**: `[PLACEHOLDER: 如每个频率扫描50个点]`

### 1.2 Temperature Control System

- **温控设备**: `[PLACEHOLDER: 型号，如Linkam HFS600E-PB4]`
- **温度范围**: 170 K – 300 K `[VERIFIED: 从数据范围确认]`
- **温控精度**: `[PLACEHOLDER: 如 ±0.1 K]`
- **降温速率**: `[PLACEHOLDER: 如 2 K/min]`
- **稳温等待时间**: `[PLACEHOLDER: 如 5 min per point]`

### 1.3 Sample Cell

- **电极材质**: `[PLACEHOLDER: 如不锈钢阻塞电极]`
- **电极面积**: S_cm2 = 3.919 cm² (S8), 0.196 cm² (S60) `[VERIFIED: 从material_params.py确认]`
- **样品厚度**: L_cm = 0.12 cm (S8), 0.7 cm (S60) `[VERIFIED: 从material_params.py确认]`

### 1.4 Communication Protocol

- **Agent→温控**: `[PLACEHOLDER: 如RS232/USB, SCPI协议]`
- **Agent→CHI**: `[PLACEHOLDER: 如COM端口, CHI SDK]`
- **数据传输格式**: JSON (测量数据) + CSV (汇总数据) `[VERIFIED: 从代码确认]`

## 2. Sample Preparation

### 2.1 S8 (Sepiolite + H₃PO₄)

- **海泡石来源**: `[PLACEHOLDER: 产地/供应商/纯度]`
- **H₃PO₄浓度**: `[PLACEHOLDER: wt%或mol/L]`
- **制备方法**: `[PLACEHOLDER: 浸渍/混合/干燥条件]`
- **R值范围**: 0.22 – 1.04 (酸水摩尔比) `[VERIFIED: 从integrated_data.csv确认]`
- **N值范围**: 1.0 – 7.0 (液固比) `[VERIFIED: 从material_params.py确认]`
- **总样品数**: 41 `[VERIFIED: 从Phase 1结果确认]`

### 2.2 S60 (Bulk H₃PO₄)

- **H₃PO₄浓度**: `[PLACEHOLDER: wt%]`
- **N = 0** (无黏土载体) `[VERIFIED]`
- **总样品数**: 17 `[VERIFIED]`

### 2.3 Cross-Material Samples

| 材料 | 黏土 | 酸 | 样品数 |
|------|------|-----|--------|
| S6 | 海泡石 | 植酸 | 20 segments `[VERIFIED]` |
| S14 | 埃洛石 | H₃PO₄ | 9 segments `[VERIFIED]` |
| S16 | 高岭石 | H₃PO₄ | 7 segments `[VERIFIED]` |
| S13 | `[PLACEHOLDER: 膨润土?]` | H₃PO₄ | 2 segments `[VERIFIED]` |
| S95-S97 | `[PLACEHOLDER]` | H₂SO₄ | 4+4+4 segments `[VERIFIED]` |

## 3. Measurement Protocol

### 3.1 Agent-Guided Protocol

- **初始温度**: ~300 K (室温附近) `[VERIFIED: 从数据确认]`
- **终止温度**: ~170-185 K `[VERIFIED: 从数据确认]`
- **粗测步长**: 3 K `[VERIFIED: 从Fig S2确认]`
- **精测步长**: 1 K `[VERIFIED: 从Fig S2确认]`
- **相变检测阈值**: Phase Jump Score > 0.2 `[VERIFIED: 从Fig S1确认]`
- **每次EIS测量前稳温时间**: `[PLACEHOLDER: 秒数]`
- **单样品典型测量点数**: ~47 `[VERIFIED: 从Fig 2a确认]`
- **单样品典型总耗时**: `[PLACEHOLDER: 如4-6小时]`

### 3.2 Baseline Protocol

- **固定步长**: 3 K (或更大) `[PLACEHOLDER: 确认]`
- **无相变检测**: 手动设置温度范围
- **典型测量点数**: ~20-25 `[VERIFIED: 从Fig 2a近似确认]`

## 4. Software Environment

- **Python版本**: `[PLACEHOLDER: 如3.10/3.11]`
- **关键库**: numpy, scipy, scikit-learn, matplotlib, pandas `[VERIFIED: 从代码确认]`
- **LLM API**: 
  - 决策模型: Claude Sonnet 4 (anthropic/claude-sonnet-4) `[VERIFIED: 从agent_log确认]`
  - 报告模型: GPT-5.2 (openai/gpt-5.2) `[VERIFIED: 从agent_log确认]`
- **前端框架**: React `[VERIFIED: 从FRONTEND_AGENT_GUIDE确认]`
- **后端框架**: `[PLACEHOLDER: 如FastAPI/Flask]`

## 5. 需要补充的图片

| 内容 | 用途 | 优先级 |
|------|------|--------|
| 硬件实物照片(温控+CHI+样品单元) | Fig S_hardware | 中 |
| 平台UI界面截图(4个页面) | Fig S_ui | 低 |
