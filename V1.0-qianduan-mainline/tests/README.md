# tests/ — 主线 pytest 套件（36 个文件）

> 结构与逐文件对照文档（生成于 2026-07-05）。
> 基线：仓库根（`acid-in-clay-close/`）下 `python -m pytest -q` 为 **443 passed, 2 skipped**（含 three_pillars 的 34 条）；
> 仅主线（本目录所在 `V1.0-qianduan-mainline/` 下运行）为 **409 passed, 2 skipped**（tests/ 232 + stage3 163 + backend_api 16）。

## 覆盖对照表

| 测试文件 | 覆盖对象 |
|---|---|
| test_stage0_bundle_kk_rb.py | stage0 EIS 管线：KK 校验 + Rb 拟合结果包 |
| test_stage0_rb_all_methods.py | stage0 Rb 四方法并行拟合 |
| test_stage0_sequence_anomalies.py | stage0 序列异常检测 |
| test_stage0_stage1_contracts.py | Stage0 → Stage1 数据契约 |
| test_evidence_admission.py | 证据准入（configs/evidence_admission_v2.yaml） |
| test_rb_act.py | stage0_measurement/rb_act（R0 影子阶梯） |
| test_stage1_mobo_wiring_contract.py | Stage1 MOBO 接线契约 |
| test_stage1_recipe_schema_contracts.py | Stage1 recipe schema |
| test_mobo_optimizer_tier3.py | optimizers/botorch_mobo_v2（qLogNEHVI） |
| test_noise_aware_mobo.py | 噪声感知 MOBO |
| test_objective_registry.py | objectives/registry + G7 守卫 |
| test_tier1_termination_lockdown.py | closed_loop/termination_evaluator 冻结行为回归 |
| test_scientific_harness.py / test_harness_admission.py / test_harness_transaction.py / test_harness_witness.py / test_measurement_txn.py / test_action_gate.py | SciTX 全套（准入/事务/见证人/动作门） |
| test_scientific_memory.py / test_emem_wp3.py / test_r2_memory.py / test_history_bridge_and_crate.py / test_bo_retrain_bridge.py | E-Mem 全套（主张图/R²-Memory/历史桥/BO 重训桥/RO-Crate） |
| test_scientific_skills.py / test_pc_skills.py | PC-Skills（证书/漂移/吊销/双账户） |
| test_c3_harness.py | scientific_convergence（C³ 影子收敛） |
| test_llm_call_bundle.py | agents/prompt_envelope（LLM 溯源封套） |
| test_e2e_demo.py | scientific_e2e/demo_end_to_end（B0/B2/B4/B5 臂） |
| test_conductivity_uncertainty.py | **analysis**.stage0_v2.conductivity_uncertainty |
| test_repro_floor_probability.py | **analysis**.stage0_v2.repro_floor_variance |
| test_policy_ablation.py | **analysis**.evaluation.policy_ablation |
| test_stage2_current_seed_contract.py | 🧊 stage2 exports/stage3_seed.json 的 hash 契约（产物漂移即红） |
| test_stage2_plots_tier2.py | stage2 出图 Tier-2 |
| test_v1v2_seed_path_isolation.py | V1/V2 seed 路径隔离 |
| test_mainline_audit_contract.py | 🧊 硬件审计契约（hits=31 / autonomous_bypass=0 基线盯守） |
| test_terminology_aliases.py | configs/terminology_aliases.yaml |

## 其他套件位置

- `backend_api/tests/`（4 个）：campaigns / hardware_adapter / pipeline / sensitivity_jobs 契约；
- `stage3_mechanism/tests/`（21 个，基线 73 条）：需 `PYTHONPATH=stage3_mechanism/src` 单独跑。

## 备注

- 标 🧊 的两个是"文件哈希契约"测试：受保护产物（stage3_seed.json、审计基线）一旦漂移即失败，属冻结纪律的自动化盯守。
- 3 个 `analysis.*` 测试证明 analysis/ 包并入主线后 import 路径正常。
