# configs/ — 冻结分析策略（M0）

> 这里放 **可版本化、可哈希、可冻结** 的分析策略。它们驱动 `analysis/stage0_v2/*`
> 的并行重算（M1/M2),**不改写** legacy 冻结管线(`stage0_measurement/*`、
> `code/stage0_processing/process_new_materials_stage0.py`、各 `official_recipe.json`)。

## 文件（2026-07-05 核查：全部现役，无遗留）

| 文件 | 用途 | 加载方 |
|---|---|---|
| `stage0_v2_policy.yaml` | Stage0 v2 分析总策略(Rb 不变性 / 序列异常 / 断点不确定度)，🧊 冻结 | `analysis/stage0_v2/versions.py::load_config()`（sha256 注入产物溯源块） |
| `rb_method_policy.yaml` | 四方法拟合参数 + 全方法并行的可用性判据，🧊 冻结 | 同上 |
| `evidence_admission_v2.yaml` | 证据准入矩阵(KK/QA/Rb 一致性 → 用途分级)，🧊 冻结 | 同上 + `stage0_measurement/modules/analysis/evidence_admission.py` |
| `objective_registry.yaml` | 训练目标 vs 审计目标的隔离与冻结哈希，🧊 冻结 | 同上 + `stage1_optimization/objectives/registry.py`（G7 守卫） |
| `dataset_registry.yaml` | 数据集注册表（experiments/data 下 lineA_*/lineB_* 的登记） | `analysis/stage0_v2/raw_loader.py` |
| `terminology_aliases.yaml` | 术语别名表（**故意不冻结**，随 WP1 迁移演进） | `tests/test_terminology_aliases.py` 等 |

## 纪律(铁律)

1. **先冻结再跑**:任何阈值改动前先 `git commit + push` 盖时间戳,再运行全量重算(防"看完结果调阈值")。
2. **哈希锚定**:每个 v2 产物的 manifest 都记录所用 config 的 sha256(见 `stage0_v2/versions.py`);
   config 改了哈希就变,重算结果可追溯到确切策略版本。
3. **不覆盖 legacy**:v2 产物一律带 `_v2` 后缀并产 `delta_report`,legacy 产物只读。
