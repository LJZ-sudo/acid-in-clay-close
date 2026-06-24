"""Stage0 v2 分析层(M1/M2)。

只读 legacy 产物 + configs/ 冻结策略,产出 *_v2 并行结果,绝不改写冻结管线。
入口模块:
  versions               版本常量 / 配置哈希 / delta_report / legacy 冻结清单 (M0)
  raw_loader             复用 chi_parser 读原始 EIS 谱 (M1-1/M1-2/M1-5 共用)
  rb_method_invariance   Rb 全方法并行 + 方法不变性 (M1-1)
"""

from . import versions  # noqa: F401
