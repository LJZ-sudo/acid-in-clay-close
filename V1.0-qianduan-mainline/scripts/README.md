# scripts/ — 治理审计脚本与报告

> 结构与逐文件状态文档（生成于 2026-07-05）。两个脚本均为**只读治理工具**，全部现役。

```
scripts/
├─ audit_hardware_write_paths.py   # ✅ 现役 · 硬件写路径审计：静态扫描主线，按角色分类
│                                  #   (OPERATOR_MANUAL / AUTONOMOUS_AGENT / ADAPTER_SINK / LEGACY_ONLINE ...)
│                                  #   冻结基线：hits=31，autonomous_bypass=0（LLM/Agent 无直达硬件路径）
│                                  #   输出 → reports/direct_hardware_call_report.{json,md}
│                                  #   有测试盯守：tests/test_mainline_audit_contract.py
├─ audit_mainline.py               # ✅ 现役 · 主线结构审计（模块清单/引用面盘点）
└─ reports/
   ├─ direct_hardware_call_report.json/.md  # 🧊 冻结产物 · 2026-07-05 prospective release 随附
   └─ ro-crate-metadata.json                # 🧊 冻结产物 · RO-Crate 1.1 复现清单（链接 configs 与报告，
                                            #   由 stage1_optimization/scientific_e2e/ro_crate.py 生成）
```

## 用法

```powershell
cd V1.0-qianduan-mainline
python scripts\audit_hardware_write_paths.py   # 重跑审计（改动任何硬件相关代码后必跑）
```

审计基线变化（hits 数或 bypass 数）意味着硬件调用面发生了实质变化，必须人工复核并更新契约测试后才能提交。
