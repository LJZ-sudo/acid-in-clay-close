# -*- coding: utf-8 -*-
"""Epistemic OS — GPT 三大原创方向的真实可计算对象。

- models           : 竞争温度模型(Arrhenius/VTF/Mott/Segmented)真实拟合 + 高斯预测分布。
- observability_certificate : 方案一 —— Fisher λ_min 可观测性 + JS 机制等价类 + 不可辨识性证书。
- min_discriminating_set    : 方案三 —— 最小判别实验集(加权集合覆盖)+ 编译失败→等价类。
- eprocess_falsification    : 方案二 —— anytime-valid e-process(Ville 控 type-I)+ 单位成本证伪价值。

全部在真实 σ(T) 数据上运算;不调 LLM;纯 numpy/scipy;绝不改 legacy。
"""
