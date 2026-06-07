# QP-S08-cold-cosolvent: 冷端共溶剂 / 抗冻电解质文献检索包

生成日期：2026-05-01  
目标：补齐 Top-list 中 glycerol / ethylene glycol / DES 的 D4 claim 缺口

## 1. 检索背景

当前 Stage3 Top-3 候选全部依赖甘油或乙二醇作为冷端抗冻共溶剂，但 S08 D4 claim pool 中：
- glycerol 零条结构化 claim
- ethylene glycol 零条
- DES 零条

需要补充 4-7 篇定向文献，使 evidence_support 从"先验推断"升级为"文献 grounded"。

## 2. 推荐检索词

### 组 A：glycerol 抗冻水凝胶/电解质（优先级最高）

```
glycerol antifreeze hydrogel electrolyte subzero ionic conductivity
glycerol water hydrogen bonding anti-freezing electrolyte low temperature
glycerol organohydrogel electrolyte supercapacitor subzero
anti-freezing hydrogel glycerol conductivity -20 -40 -60
starch PVA glycerol ionic hydrogel low temperature conductivity
chitosan glycerol conductive hydrogel anti-freezing
```

### 组 B：ethylene glycol 抗冻电解质（优先级高）

```
ethylene glycol antifreeze additive aqueous electrolyte low temperature
ethylene glycol zinc ion battery antifreeze conductivity
ethylene glycol aqueous supercapacitor subzero
propylene glycol antifreeze electrolyte conductivity
```

### 组 C：磷酸亚零度 / 磷酸膜低温质子传导（优先级高）

```
phosphoric acid subzero proton conductivity membrane
phosphoric acid doped membrane low temperature -30 conductivity
phosphoric acid water eutectic freezing point phase diagram
carbon dots phosphoric acid proton exchange membrane subzero
```

### 组 D：DES 质子传导（优先级中）

```
deep eutectic solvent proton conductor low temperature
choline chloride phosphoric acid ionic conductivity
choline chloride urea chitosan proton conductivity membrane
DES Nafion anhydrous proton conductivity
```

### 组 E：结合水/生物质高分子低温离子传导（优先级中）

```
bound water biopolymer electrolyte subzero conductivity
PVA chitosan starch anti-freezing ionic hydrogel
biopolymer hydrogel electrolyte supercapacitor low temperature
```

## 3. 推荐下载文献

以下是根据检索结果筛选的高相关文献，建议优先下载：

### P0 级（直接解锁 glycerol / 低温电导）

1. **"Unlocking ultra-low temperature performance: an anti-freezing, high-conductivity, biodegradable hydrogel electrolyte for supercapacitors down to -60 C"**
   - PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC12447293/
   - 关键数据：glycerol + 多糖 + ZnCl2，13.32 mS/cm @ -60 C
   - 覆盖 D1/D5 的 glycerol 低温锚点

2. **"Design Strategies for Anti-Freeze Electrolytes in Aqueous Energy Storage Devices at Low Temperatures"**
   - Wiley AFM 2024: https://advanced.onlinelibrary.wiley.com/doi/10.1002/adfm.202403616
   - 综述：glycerol/EG/盐/DES 的抗冻策略
   - 覆盖 D1/D5 设计框架

3. **"Enhancing proton conductivity at subzero temperature through constructing the well-ordered structure based on carbon dots"**
   - ScienceDirect: https://www.sciencedirect.com/science/article/abs/pii/S0376738822002836
   - 关键数据：磷酸/碳点膜 3.29e-3 S/cm @ -30 C
   - 直接覆盖 D4 磷酸亚零度锚点

4. **"Ethylene Glycol as an Antifreeze Additive and Corrosion Inhibitor for Aqueous Zinc-Ion Batteries"**
   - Wiley 2022: https://chemistry-europe.onlinelibrary.wiley.com/doi/10.1002/batt.202100420
   - 关键数据：EG 抗冻 + 低温电导
   - 覆盖 D1/D5 的 EG 低温锚点

### P1 级（补强 DES / 生物质 / 低温机理）

5. **"Effect of deep eutectic solvent in proton conduction and thermal behaviour of chitosan-based membrane"**
   - ScienceDirect: https://www.sciencedirect.com/science/article/abs/pii/S016773221832957X
   - 关键数据：ChCl:urea DES + chitosan 膜质子电导
   - 覆盖 D3/D7 DES 质子传导

6. **"Choline chloride-based deep eutectic solvents as electrolytes for wide temperature range supercapacitors"**
   - ScienceDirect: https://www.sciencedirect.com/science/article/abs/pii/S2352152X23015384
   - 关键数据：ChCl/PA DES 宽温区电导
   - 覆盖 DES 冷端可行性

7. **"Recent Advances in Biopolymer-Based Hydrogel Electrolytes for Flexible Supercapacitors"**
   - ACS Energy Letters 2024: https://pubs.acs.org/doi/10.1021/acsenergylett.3c02567
   - 综述：PVA/starch/chitosan + glycerol/盐的抗冻策略
   - 覆盖 D3/D6 bound water 与 biopolymer 证据

## 4. 下载后放置位置

```text
literature_workspace/01_manual_inbox/s08_materials/
```

## 5. 下载后运行命令

```powershell
cd V1.0-qianduan-mainline\stage3_mechanism

# ingest
python -m s8_stage3.orchestrator.run_stage3 --ingest-manual-papers --stage-target s08_materials

# rebuild cards
python -m s8_stage3.orchestrator.run_stage3 --rebuild-paper-cards --stage-target s08_materials --llm-mode live

# rebuild evidence tables
python -m s8_stage3.orchestrator.run_stage3 --rebuild-evidence-tables --stage-target s08_materials
```

## 6. 预期效果

补充后：
- glycerol 应至少有 2-3 条带量化锚点的 D4 claim（如 13.32 mS/cm @ -60 C）
- ethylene glycol 应至少有 1 条
- 磷酸亚零度应至少有 1 条
- DES 可选 1-2 条
- Top-list 的 `evidence_support` 分数应从 0.90 → 更高，glycerol 从"pending"变"supported"
