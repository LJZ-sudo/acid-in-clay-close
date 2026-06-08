# AGENTS.md — 项目上手与跨机器迁移说明

> 这是给 **Cursor / 编码 Agent** 自动读取的项目说明。任何机器上打开本仓库，先读本文件即可快速“知道在干什么”。
> 人类协作者也可以把它当作 onboarding。

## 0. 一句话定位

这不是普通材料论文，也不是普通 agent 项目，而是一个 **物理 / QC / claim-governed 的 agentic materials discovery 项目**：用 Agent 在“数字世界 ↔ 物理世界”之间做质子导体（acid-in-clay / 凹凸棒土）的 EIS 闭环发现，核心是**证据约束 + 不过度声称**。

三个创新点（pillars）：
1. **Evidence-constrained transfer agent** — 从 acid-in-clay evidence 到 biopolymer–clay membrane motif 的迁移推理。
2. **Cooling-resilient pathway continuity descriptor** — 低温通路连续性描述符（LRS 正验证，CHITO 边界验证）。
3. **Physics/QC-gated EIS-in-the-loop execution** — BO + LLM 真实闭环执行，**不**声称收敛、不声称“发现 LRS”、不事后改分。

## 1. 先读这些（canonical docs，单一真相源）

| 文档 | 作用 |
|---|---|
| `PROJECT_SYSTEM_OVERVIEW_CODE_GROUNDED_20260604.md` | 代码级的整体系统架构总览 |
| `THREE_PILLARS_ANALYSIS_AND_WRITING_PLAN_20260608.md` | 三创新点 ↔ 代码/证据映射 + 子刊写作方案 |
| `prospective_2026H2/README.md` | 前瞻实验纪律（“冻结 → push 盖时间戳 → 才开始测量”） |
| `prospective_2026H2/line_A_biopolymer_transfer/PREREGISTRATION.md` | 线 A（生物聚合物迁移）预注册 |
| `prospective_2026H2/line_B_mobo_closed_loop/PREREGISTRATION.md` | 线 B（真实 MOBO+LLM 闭环）预注册 + 官方 recipe |
| `three_pillars/` | 三创新点的固化证据与执行引擎 |

> ⚠️ **聊天记录不跨机器**：过去与 Cursor/Agent 的对话存在本机 `~/.cursor/.../agent-transcripts/`，**不随 git 迁移**，也不入库（已 gitignore）。换机器后那段历史不在新机器上——靠本文件 + 上述文档承接上下文。

## 2. 仓库结构

```
acid-in-clay-close/
├─ AGENTS.md                      # 本文件
├─ PROJECT_SYSTEM_OVERVIEW_*.md   # 架构总览
├─ THREE_PILLARS_*.md             # 三创新点 + 写作方案
├─ prospective_2026H2/            # 前瞻预注册（线 A / 线 B），含 line_B official_recipe.json
├─ three_pillars/                 # 三创新点证据 + pillar3 执行引擎/门禁
└─ V1.0-qianduan-mainline/        # ★ 主线代码（最核心）
   ├─ backend_api/                # FastAPI 后端（端口 8000），routers/* 为只读看板 + 控制
   ├─ frontend/                   # React + Vite + Ant Design 驾驶舱（端口 5173）
   ├─ stage0_measurement/         # Stage0 测量 / 相检测 / CHI 数据接入
   ├─ stage1_optimization/        # Stage1 BO / MOBO(ParEGO) + LLM guardrail 闭环
   ├─ stage2_statistics/          # Stage2 统计 / 导出
   ├─ stage3_mechanism/           # Stage3 机理 / 文献 / claim 审计（有自己的 AGENTS.md）
   └─ scripts/audit_mainline.py   # 路径卫生 + 主线一致性审计器
```

## 3. 跨机器迁移（推荐路径：git clone）

项目已托管在 GitHub。迁移 = 在新机器克隆 + 配置环境，**不要手工拷贝目录**（会带上本机绝对路径的历史产物且漏掉 .env 模板逻辑）。

```bash
# 1) 克隆（远端是 SSH；当前工作分支是 remediation/tier3）
git clone git@github.com:LJZ-sudo/acid-in-clay-close.git
cd acid-in-clay-close
git checkout remediation/tier3

# 2) 后端依赖（按需逐 stage 安装；至少装 stage1 + 后端用到的）
python -m pip install -r V1.0-qianduan-mainline/stage1_optimization/requirements.txt
python -m pip install -r V1.0-qianduan-mainline/stage3_mechanism/requirements.txt
#   后端还需要 fastapi / uvicorn / python-socketio（若未在 requirements 内则单独装）

# 3) 配置密钥：从模板复制，再填入 OpenRouter key（.env 不入库）
copy V1.0-qianduan-mainline\stage1_optimization\.env.example V1.0-qianduan-mainline\stage1_optimization\.env
copy V1.0-qianduan-mainline\stage3_mechanism\.env.example   V1.0-qianduan-mainline\stage3_mechanism\.env
#   编辑两个 .env，填 LLM_API_KEY（OpenRouter），模型默认 openai/gpt-5.4

# 4) 前端
cd V1.0-qianduan-mainline/frontend && npm install
```

### 启动（开发）
```bash
# 后端：在 V1.0-qianduan-mainline/ 下
python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000
# 前端：在 V1.0-qianduan-mainline/frontend/ 下（Vite 代理 /api、/socket.io 到 127.0.0.1:8000）
npm run dev          # http://127.0.0.1:5173
```

### Git 推送（若网络封了 22 端口，走 443）
```bash
# 本仓库历史上遇到过 port 22 被防火墙重置，用 OpenSSH 的 443 通道：
GIT_SSH_COMMAND="ssh -p 443 -o HostName=ssh.github.com" git push
# Windows PowerShell:  $env:GIT_SSH_COMMAND="ssh -p 443 -o HostName=ssh.github.com"; git push
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

> 历史产物里（`stage3_mechanism/outputs/**`、`stage2_statistics/exports/**`、各 `*_manifest.json`、
> 旧 `next_experiment_recipe.json`）会出现 `C:\Users\JZ\...` 之类绝对路径——那是**过去运行的记录**，
> 不影响在新机器上跑代码，可忽略。

## 5. 路径卫生规则（写新代码必须遵守）

- **绝不**在代码/配置里写死绝对路径（`C:\Users\...`、`D:\...`、`/Users/...`）。
- 根目录统一：`PROJECT_ROOT = Path(__file__).resolve().parents[N]`，其余路径基于它拼。
- 需要机器特定位置时，走环境变量（见 §4），并在 `.env.example` 里给出占位。
- 提交前可跑审计器检查残留写死路径：
  ```bash
  python V1.0-qianduan-mainline/scripts/audit_mainline.py
  ```
  （它会扫描 `LEGACY_ROOT_MARKERS` 等遗留绝对路径并报告。）

## 6. 诚信 / claim 护栏（本项目的灵魂，勿违反）

- 闭环结果**无论收敛与否都如实报告**；未越过阈值就写“执行成功但未实现 Pareto 扩展（诚实 null）”。
- 前瞻性主张必须有 **git commit + push 时间戳** 在实验之前（见 `prospective_2026H2/`）。
- 允许 / 禁止声称的边界写在各 PREREGISTRATION.md 与 `official_recipe.json`；
  **驾驶舱前端只展示“测量 + 实证留痕”**，声称类文字归到论文/预注册层（不放前端）。
- 当前线 B 官方第一轮 recipe：raw MOBO `R=0.0285/N=0.9841` → LLM 修正 **`R=0.28/N=0.96`**
  （safety passed，见 `prospective_2026H2/line_B_mobo_closed_loop/official_recipe.json`），尚未合成。

## 7. 常用入口速查

- 主线代码：`V1.0-qianduan-mainline/`
- Stage1 闭环（真实 MOBO+LLM）：`stage1_optimization/run_optimization_loop.py --optimizer mobo`
- 线 B 只读复现（不写库、不伪造 Stage0）：`stage1_optimization/line_b_guardrail_run.py`
- 后端只读溯源接口：`GET /api/provenance`（git 锚 + LLM + 线 B 官方 recipe）
- 审计 / 路径卫生：`scripts/audit_mainline.py`
