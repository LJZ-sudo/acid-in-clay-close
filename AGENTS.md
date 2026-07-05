# AGENTS.md — 项目上手与跨机器迁移说明（重生成 2026-06-24）

> 这是给 **Cursor / 编码 Agent** 自动读取的项目说明。任何机器上打开本仓库，先读本文件即可快速“知道在干什么”。
> 人类协作者也可以把它当作 onboarding。
> 本文件于 2026-06-24 按当前真实情况重生成（旧的 `PROJECT_SYSTEM_OVERVIEW_*0604` 与 `THREE_PILLARS_*0608` 已被 0622 系列文档取代）。

## 0. 一句话定位

这不是普通材料论文，也不是普通 agent 项目，而是一个 **物理 / QC / claim-governed 的 agentic materials discovery 项目**：用 Agent 在“数字世界 ↔ 物理世界”之间做质子导体（acid-in-clay / 凹凸棒土）的 EIS 闭环发现，核心是**证据约束 + 不过度声称**。

**双轨铁律（贯穿全程，两轨都必须做、并行推进、持续深化，不是二选一）**：
- **A 轨（材料 / EIS / 治理主线）**：M0–M2 分析硬化 + G1 湿实验 → 冲 **Tier B**。
- **B 轨（Scientific Agent 方法学）**：SciTX / E-Mem / PC-Skills 三大底层创新（WP0–WP5）→ 取得系统权威性、具备冲 **Tier S** 的真实证据。

三个创新点（pillars）：
1. **Evidence-constrained transfer agent** — 从 acid-in-clay evidence 到 biopolymer–clay membrane motif 的迁移推理。
2. **Cooling-resilient pathway continuity descriptor** — 低温通路连续性描述符（LRS 正验证，CHITO 边界验证）。
3. **Physics/QC-gated EIS-in-the-loop execution** — BO + LLM 真实闭环执行，**不**声称收敛、不声称“发现 LRS”、不事后改分。

## 1. 先读这些（canonical docs，单一真相源）

| 文档 | 作用 |
|---|---|
| `OPTIMIZATION_EXECUTION_PLAN_20260622.md` | ★ 可执行/可勾选/可验收的执行计划（双轨 + WP0–WP5 + 三阶段切换） |
| `PROJECT_SITUATION_REPORT_20260622.md` | 现状家底（对账真实数据，诚实评估） |
| `SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md` | 代码级架构（真实 `file::function` 追踪，ASCII 图） |
| `experiments/docs/PUBLICATION_READINESS.md` | 判档 / 发表就绪度（R0–R5 成熟度） |
| `experiments/docs/REAL_MACHINE_INTEGRATION_PLAN_20260622.md` | ★ 真机联调方案（跨机迁移 + 硬件入口 + Harness shadow + 密钥） |
| `INNOVATION_SKILLS_HARNESS_MEMORY_20260622.md` | 三大底层创新（SciTX/E-Mem/PC-Skills）设计说明 |
| `experiments/docs/TIER_S_MANUSCRIPT_DRAFT_20260622.md` | Tier S 手稿草案（脊柱：M0–M2 + 三 Demo） |
| `experiments/prospective/README.md` | 前瞻实验纪律（“冻结 → push 盖时间戳 → 才开始测量”） |
| `experiments/prospective/line_A_biopolymer_transfer/PREREGISTRATION.md` | 线 A（生物聚合物迁移）预注册 |
| `experiments/prospective/line_B_mobo_closed_loop/PREREGISTRATION.md` | 线 B（真实 MOBO+LLM 闭环）预注册 + 官方 recipe |
| `three_pillars/` | 三创新点的固化证据与执行引擎 |

> ⚠️ **聊天记录不跨机器**：过去与 Cursor/Agent 的对话存在本机 `~/.cursor/.../agent-transcripts/`，**不随 git 迁移**，也不入库（已 gitignore）。换机器后那段历史不在新机器上——靠本文件 + 上述文档承接上下文。

## 2. 仓库结构

```
acid-in-clay-close/
├─ AGENTS.md                                  # 本文件
├─ OPTIMIZATION_EXECUTION_PLAN_20260622.md    # ★ 执行计划（双轨 + WP0–WP5）
├─ PROJECT_SITUATION_REPORT_20260622.md       # 现状家底
├─ SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md # 代码级架构
├─ INNOVATION_SKILLS_HARNESS_MEMORY_20260622.md  # 三大底层创新设计
├─ research/                                  # ★ 输入/输出 home（数据、结果、文档、预注册；分析代码已并入主线 analysis/）
│  ├─ data/                                   # lineA_*/lineB_* 各批次实验数据（aggregated/arrhenius）
│  ├─ results/                                # v2 分析产物（rb_invariance / repro_floor_v2 / epistemic_out 等）
│  ├─ docs/                                   # PUBLICATION_READINESS / TIER_S 手稿 / 真机方案 等
│  ├─ prospective/                            # 前瞻预注册（线 A / 线 B，含 line_B official_recipe.json）
│  ├─ live/                                   # hw0..hw3 / watch_* 真机联调探针脚本（含串口写，刻意留在主线审计面之外）
│  └─ scientific_harness|memory|skills/       # 三 Demo 的输出产物
├─ manuscript/                                # 手稿构建（draft + build 脚本）
├─ three_pillars/                             # 三创新点证据 + pillar3 执行引擎/门禁
├─ archive/                                   # 历史/实验性代码归档（保留可追溯，不在主路径）
└─ V1.0-qianduan-mainline/                     # ★ 主线代码（最核心，唯一代码 home）
   ├─ backend_api/        # FastAPI 后端（端口 8000），routers/* 为只读看板 + 控制
   ├─ analysis/           # ★ 研究分析代码（原 research 代码包）：stage0_v2/ calibration/ evaluation/
   │                      #   epistemic/ regularity/ drt/ replay/ figures/ ablation/ analysis_scripts/
   │                      #   verification/(p2..p21/pH1..pH4) + natfig.py；读写仍指向 ../research/{data,results}
   ├─ frontend/           # React + Vite + Ant Design 驾驶舱（端口 5173）
   ├─ configs/            # ★ M0 冻结策略：rb_method_policy / evidence_admission_v2 / objective_registry / dataset_registry / terminology_aliases / stage0_v2_policy
   ├─ stage0_measurement/ # Stage0 测量 / 相检测 / CHI 数据接入（含 run_online.py --harness_mode）
   ├─ stage1_optimization/# Stage1 BO / MOBO(ParEGO/botorch) + LLM guardrail 闭环
   │   ├─ objectives/         # 目标注册表（assert_campaign_matches_role G7 守卫）
   │   ├─ agents/             # prompt_envelope / LLMCallBundle 溯源
   │   ├─ optimizers/         # 噪声感知 MOBO（BotorchMOBO=SingleTaskGP(train_Yvar)+qLogNEHVI）
   │   ├─ scientific_harness/ # B 轨 SciTX：admission/witness/transaction/action_gate（三重提交 + 唯一硬件入口）
   │   ├─ scientific_memory/  # B 轨 E-Mem：snapshots/root_dedup/bo_rebuilder/compression/history_bridge/bo_retrain_bridge
   │   ├─ scientific_skills/  # B 轨 PC-Skills：skills_eis/certificate_service/runtime/drift/revocation/registry
   │   └─ scientific_e2e/     # B 轨评测：demo_end_to_end（B0/B2/B4/B5 臂）+ ro_crate
   ├─ stage2_statistics/  # Stage2 统计 / 导出
   ├─ stage3_mechanism/   # Stage3 机理 / 文献 / claim 审计（有自己的 AGENTS.md）
   └─ scripts/            # audit_mainline.py（路径卫生）+ audit_hardware_write_paths.py（自主硬件旁路审计 --strict）
```

## 3. 跨机器迁移（推荐路径：git clone）

项目已托管在 GitHub。迁移 = 在新机器克隆 + 配置环境，**不要手工拷贝目录**（会带上本机绝对路径的历史产物且漏掉 .env 模板逻辑）。详见 `experiments/docs/REAL_MACHINE_INTEGRATION_PLAN_20260622.md`。

```bash
# 1) 克隆（远端是 SSH；当前工作分支是 remediation/tier3）
git clone git@github.com:LJZ-sudo/acid-in-clay-close.git
cd acid-in-clay-close
git checkout remediation/tier3

# 2) 后端依赖（按需逐 stage 安装；至少装 stage1 + 后端用到的）
python -m pip install -r V1.0-qianduan-mainline/stage1_optimization/requirements.txt
python -m pip install -r V1.0-qianduan-mainline/stage3_mechanism/requirements.txt
# 后端还需要 fastapi / uvicorn / python-socketio（若未在 requirements 内则单独装）
# B 轨真实多目标后端（可选）：botorch torch gpytorch
# 真机额外：pyserial（温控串口）+ CHI GUI 自动化依赖（pywinauto/pyautogui 之类，按实际 import 安装）

# 3) 配置密钥：从模板复制，再填入 OpenRouter key（.env 不入库）
copy V1.0-qianduan-mainline\stage1_optimization\.env.example V1.0-qianduan-mainline\stage1_optimization\.env
copy V1.0-qianduan-mainline\stage3_mechanism\.env.example V1.0-qianduan-mainline\stage3_mechanism\.env
# 编辑两个 .env，填 LLM_API_KEY（OpenRouter，来自 key.txt），模型默认 openai/gpt-5.4

# 4) 前端
cd V1.0-qianduan-mainline/frontend && npm install
```

### 启动（开发）
```bash
# 后端：在 V1.0-qianduan-mainline/ 下
python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000
# 前端：在 V1.0-qianduan-mainline/frontend/ 下（Vite 代理 /api、/socket.io 到 127.0.0.1:8000）
npm run dev   # http://127.0.0.1:5173
```

### 离线冒烟（不接硬件，确认代码可跑）
```bash
# 全量测试应 208 passed / 0 failed
python -m pytest V1.0-qianduan-mainline/tests V1.0-qianduan-mainline/backend_api/tests -q
# 自主硬件写路径审计应 autonomous_bypass=0（--strict exit 0）
python V1.0-qianduan-mainline/scripts/audit_hardware_write_paths.py --strict
```

### Git 推送（若网络封了 22 端口，走 443）
```bash
# 本仓库历史上遇到过 port 22 被防火墙重置，用 OpenSSH 的 443 通道：
GIT_SSH_COMMAND="ssh -p 443 -o HostName=ssh.github.com" git push
# Windows PowerShell: $env:GIT_SSH_COMMAND="ssh -p 443 -o HostName=ssh.github.com"; git push
```
新机器若用 SSH 远端，需先把该机器的 SSH 公钥加到 GitHub；或改用 HTTPS 远端。

## 4. 机器相关的东西（迁移时只需关心这些）

代码本身已**可移植**：根路径一律用 `Path(__file__)` 相对解析，campaign 存储用相对路径
（`stage1_optimization/campaigns/*.json` 里的 `storage.history_db` / `output_dir` 都是相对的）。
真正与机器绑定的只有下面几项，全部通过 **环境变量 / .env** 覆盖，**不要写死**：

| 项 | 默认 | 覆盖方式 | 何时需要 |
|---|---|---|---|
| OpenRouter API key | 无（必填） | `LLM_API_KEY`（在各 stage 的 `.env`） | 跑 LLM guardrail / 机理 |
| LLM 端点 / 模型 | `https://openrouter.ai/api/v1` · `openai/gpt-5.4`（Stage1）/ `gpt-5.2`（Stage0 phase_detect） | `LLM_BASE_URL` / `LLM_MODEL` / `PHASE_DETECT_MODEL` | 切模型时 |
| CHI 仪器数据目录 | `E:\chi_data` | `STAGE0_CHI_DATA_DIR` | **仅真机测量**；纯分析/复算用不到 |
| 离线数据目录 | 无 | `run_offline.py --data_dir <dir>` | 离线批处理 |

> - `LLMClient` 只读 `.env` 的 `LLM_API_KEY`，**不读 `key.txt`**（`key.txt` 仅供分析/出图脚本，已 gitignore）。
> - 三大 Demo（A/B/C）+ 端到端撤销演示是**纯软件、不调用 LLM**，所以没接 key 是对的；LLM 只在真机闭环（Stage1 Step5 / Stage3 / Stage0 在线相变）用到。
> - 历史产物里（`stage3_mechanism/outputs/**`、`stage2_statistics/exports/**`、各 `*_manifest.json`、旧 `next_experiment_recipe.json`）会出现 `C:\Users\JZ\...` 之类绝对路径——那是**过去运行的记录**，不影响在新机器上跑代码，可忽略。

## 5. 路径卫生 / 文档编码规则（写新代码必须遵守）

- **绝不**在代码/配置里写死绝对路径（`C:\Users\...`、`D:\...`、`/Users/...`）。
- 根目录统一：`PROJECT_ROOT = Path(__file__).resolve().parents[N]`，其余路径基于它拼。
- 需要机器特定位置时，走环境变量（见 §4），并在 `.env.example` 里给出占位。
- **文档编码**：`.md` 一律 UTF-8；**禁用 PowerShell `Get-Content | Set-Content` 改 CJK 文档**（会按系统码页有损重编码导致乱码）；编辑用专用工具（UTF-8）。
- 提交前可跑审计器检查残留写死路径：
  ```bash
  python V1.0-qianduan-mainline/scripts/audit_mainline.py
  python V1.0-qianduan-mainline/scripts/audit_hardware_write_paths.py --strict
  ```

## 6. 诚信 / claim 护栏（本项目的灵魂，勿违反）

- 闭环结果**无论收敛与否都如实报告**；未越过阈值就写“执行成功但未实现 Pareto 扩展（诚实 null）”。
- 前瞻性主张必须有 **git commit + push 时间戳** 在实验之前（见 `experiments/prospective/`）。
- 允许 / 禁止声称的边界写在各 PREREGISTRATION.md 与 `official_recipe.json`；
  **驾驶舱前端只展示“测量 + 实证留痕”**，声称类文字归到论文/预注册层（不放前端）。
- **12 条系统不变量**（B 轨权威性硬约束，写进代码）见 `OPTIMIZATION_EXECUTION_PLAN_20260622.md §4`：例如 Agent 不得直连 `hw.enqueue_command`、人工 override 必隔离留痕、未 Committed 观察不得进 BO、Instrument success 不得自动等价 PhysicalEffect=confirmed 等。
- 当前线 B 官方第一轮 recipe：raw MOBO `R=0.0285/N=0.9841` → LLM 修正 **`R=0.28/N=0.96`**
  （safety passed，见 `experiments/prospective/line_B_mobo_closed_loop/official_recipe.json`），尚未合成。

## 7. 当前进度速记（2026-06-24）

- **A 轨**：M0（冻结/版本化）、M1（8/8 分析门）、M2（5/5，含 botorch 真实后端）已完成；**唯一硬门 = G1 同配方重复湿实验 + 写作**（需实验台）。
- **B 轨**：WP0–WP5 已完成 —— 语义/审计、SciTX 2.0（C_M 用途·C_E 主张·多见证 C_P·EvidenceTransaction）、PC-Skills（6 Skill + 三层证书 + 漂移/撤销）、E-Mem（快照/根去重/失效→BO→**GP 重训**/压缩证书）、Cutover（ActionGate 唯一入口，**autonomous_bypass=0**）、端到端撤销演示（governed 严格优于 ungoverned）+ RO-Crate。
- **测试**：全量 **208 passed / 0 failed**。
- **决定性下一步**：**P1 真机故障对照（需 G1，软件替代不了）+ enforce 生产灰度**；B 轨剩余为 P2 纯代码工程项（可与 G1 并行）。详见执行计划 §9。

## 8. 常用入口速查

- 主线代码：`V1.0-qianduan-mainline/`
- Stage1 闭环（真实 MOBO+LLM）：`stage1_optimization/run_optimization_loop.py --optimizer mobo`
- 线 B 只读复现（不写库、不伪造 Stage0）：`stage1_optimization/line_b_guardrail_run.py`
- 在线测量（真机，带三重提交 shadow 旁路）：`stage0_measurement/run_online.py --harness_mode shadow`
- B 轨三 Demo：`scientific_harness/demo_a.py`、`scientific_memory/demo_b.py`、`scientific_skills/demo_c.py`
- B 轨端到端撤销演示：`scientific_e2e/demo_end_to_end.py`
- 后端只读溯源接口：`GET /api/provenance`（git 锚 + LLM + 线 B 官方 recipe）
- 审计 / 路径卫生：`scripts/audit_mainline.py`、`scripts/audit_hardware_write_paths.py --strict`
