# AGENTS.md — Stage3 架构约束（Cursor / Codex 代理必读）

## 最高约束
本项目以 `stage3-SDL.md` 为最高架构标准。所有代码修改必须符合 SDL 规范。

## 目录规范
- **新代码**：只写入 `src/s8_stage3/`
- **旧代码**：只保留在 `legacy/`，不再修改
- **prompt**：只存放在 `src/s8_stage3/prompts/*.md`，禁止内联在 Python 文件中

## 架构规则

### 架构推理链顺序（不可跳级）
```
S01 数据审计 → S02 片段重建 → S03 证据 → S04 假说 →
S05 文献(机理) → S06 机理仲裁 → S06b 设计原则 →
S07 描述符 → S08 文献(材料) → S09 家族/实例 →
S10 排名 → S12 登记 → S13 验证绑定 → S14 claim 审计 → S11 报告
```

当前代码主线说明：
- 当前默认执行链以 Stage2 canonical `stage3_seed.json` 为入口，不默认执行 S01/S02。
- 默认 `Pipeline.run_from_seed()` 从 `Stage3SeedBundle` 开始运行 S03/S04/S05/S06/S06b/S07/S08/S09/S10/S12/S13/S14/S11。
- S01/S02 代码存在，但当前不在默认 pipeline 中调用。
- Real 模式由 `adapters/stage2_seed_adapter.py` 负责把 Stage2 五件套转换为 `Stage3SeedBundle`。
- 如需启用 S01/S02，必须同步修改 `orchestrator/pipeline.py`、测试和本文档。

### 材料名泄漏规则
- **S01–S07**：严禁出现具体材料名（lotus、PVA、凹凸棒土、海泡石等）
- **S08**：允许 family 级材料类名（多糖类、黏土类等）
- **S09–S11**：允许具体 instance 名称

### Family 与 Instance 必须分离
- S09 先生成 families，再由 families 实例化为 instances
- Top List 中 lotus-related route 必须通过描述符匹配自然出现，不得上游先验

### EIS 约束
- EIS 形貌结果只能作为启发式证据
- 禁止：`EIS proves/confirms...`、`等效电路已确定`
- 必须带免责脚注（见 SDL §4.2）

### 输出要求
- 每个 step 必须落盘结构化 JSON
- 落盘前必须通过 schema_validator 校验
- S03–S07 输出必须通过 no_leakage_checker

## 禁止事项
1. 业务代码直接发 HTTP 请求（统一走 llm_gateway）
2. agent Python 文件中写大段内联 prompt
3. 在上游 step prompt 中塞具体材料配方
4. 跨级输出（S05 不能直接给排名结论）
5. 让 LLM 直接消化完整 CSV
