# front_half_v2 内置数据

> 2026-05-18 note: this README documents historical `front_half_v2` data
> conventions. For the current AiCE/Stage0 mainline directory classification,
> use `data/MANIFEST.md`.

- **`phase1_results/`**：从仓库 `output/phase1_results/` 复制的 **S8*** 与 **S60*** 的 `*_analysis_result.json`，供离线或与 manifest 无关时由 `io/manifest_resolver.py` 优先解析。
- **`phase2_reports/`**：历史/演示用机理报告副本；**runtime 默认不会**自动当作输入。若需参与 planning，请在 run 的 `manifest.json` 中设置 **`source_mechanism_report`** 指向具体文件，或使用 LLM 在 `experiment_data/history/<sample_id>/` 生成。

运行 `front_half_v2` 时，`project_root` 应为 **`V1.0-qianduan-mainline`**，以便路径  
`front_half_v2/data/...` 与 `config`、`phase2` 等模块一致可用。

若需追加样品：将对应 JSON/MD 放入上述子目录，文件名保持  
`<sample_id>_analysis_result.json` 与 `<sample_id>_mechanism_report.md`。

**材料说明与 R/N/L/S 定义**：推荐在 phase1 JSON 中含 ``material_description``、``parameter_definitions``（见 ``phase1_material_lexicon.json``），或运行  
``python -m front_half_v2.tools.enrich_phase1_metadata`` 批量注入。

**规范化输入预览**：``canonical_phase1_inputs/<sample_id>_canonical_input.json`` 由 ``extract_canonical_phase1_input`` 从对应 ``phase1_results`` 生成（v1.1 起不含 kk_validation / drt_analysis，原因见 ``front_half_v2/TODO_KK_DRT_REPAIR.md``），便于人工检查模板是否够用；与线上主 JSON 可能不同步时需重新批量导出。
