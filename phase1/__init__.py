# -*- coding: utf-8 -*-
"""
Phase 1: 数据处理与Arrhenius分析
================================

流程:
1. step1_parse_eis.py    - 解析原始EIS文件
2. step2_arrhenius_fit.py - Arrhenius分段拟合  
3. step3_extract_features.py - 提取Ea, σ₀, 温度范围
4. step4_quality_filter.py - 数据质量过滤

输出:
- output/phase1_results/{sample_id}_analysis.json
"""
