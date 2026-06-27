# 真机阶段交接说明 + 自举引导（HANDOFF + BOOTSTRAP，2026-06-26）

> **给新电脑上的 Cursor / 编码 Agent 的第一份、也是当前文件夹里唯一一份文件。**
>
> **你(Agent)现在的处境**:你被放在一台**与测试台/电化学工作站相连**的电脑上,当前工作文件夹里
> **只有这一份 `.md` 文档,项目代码还没下载**。聊天记录不跨机器,所以本文件就是你的全部初始上下文。
>
> **因此你的第一步不是读代码,而是按 §1.5「自举引导」把项目仓库 clone 进来**;克隆成功后,
> 本文件 §0 列的那些 canonical 文档才会出现在磁盘上,你再去下钻。
>
> **执行总顺序**:§1.5 自举克隆 → §0 读 canonical 文档 → §2 现状 → §4 第 0 步环境自检 → §4 第 1–4 步真机任务。
> 全程守 §6 诚信纪律。代码级细节去查 canonical 文档,不要臆造。

---

## 0. 先读这些（单一真相源，按顺序）

> ⚠️ **下表的文件在你完成 §1.5 自举克隆之前都还不存在**。克隆后它们位于
> `acid-in-clay-close/`(即仓库根)下,例如 `acid-in-clay-close/AGENTS.md`。**先做 §1.5,再回来读这些。**

| 文档 | 作用 |
|---|---|
| `AGENTS.md` | 项目总上手 + 跨机器迁移(克隆/装环境/启动/路径卫生) |
| **本文件** | 真机阶段要做什么、怎么做、交付什么 |
| `PROJECT_SITUATION_REPORT_20260622.md` | 现状家底(测了什么/没测什么/真实 vs 冻结清单/诚实局限) |
| `SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md` | 代码级 `file::function` 执行追踪 + 决策节点表 |
| `OPTIMIZATION_EXECUTION_PLAN_20260622.md` | 可勾选执行计划;**§10 = ESAS-OS 2.0 升级方案 + §10.4 Rb-ACT 五级接入门** |
| `_new_data_analysis/PUBLICATION_READINESS.md` | 发表就绪度判断 + 主张边界(可声称 vs 不可声称) |
| `prospective_2026H2/` | 前瞻实验纪律(冻结→push 盖时间戳→才开始测量)+ 线 A/线 B 预注册 |

---

## 1. 这是什么项目（一句话定位）

一个 **物理 / QC / claim-governed 的 agentic 材料发现项目**:在质子导体(酸-黏土 / 生物聚合物-黏土,凹凸棒土)上做
**EIS-only、表征受限条件下的"证据治理型半闭环自主发现"**。核心不是材料数字,而是**"只有传输数据时,自主 Agent 能可信地声称什么"**,并给出两条可测量边界:**复现地板(下界)** 与 **可辨识性天花板(上界)**。

**两条必须并行的工作轨(不是二选一)**:
- **A 轨 — 材料/EIS/治理主线**:已接近 Tier B 投稿,**唯一硬门是 G1 真机重复实验**(见 §4)。
- **B 轨 — Scientific Agent 方法学**:软件层已成体系(三件套 SciTX/E-Mem/PC-Skills + ESAS-OS 2.0 四个 v2 插件),
  **距 Tier S 还差真机故障对照证据**——这正是这台电脑要去攒的东西。

---

## 1.5 自举引导（你的第一步：把项目克隆进来）

> 当前文件夹里只有这份文档。**先把仓库 clone 到本文件夹下的子目录 `acid-in-clay-close/`**
> (git 不允许克隆进非空目录,所以用子目录,别克隆进".")。

```powershell
# 在“放着本文档的这个空文件夹”里执行：
# 1) 克隆(默认走 SSH;远端 = LJZ-sudo/acid-in-clay-close，工作分支 remediation/tier3)
git clone git@github.com:LJZ-sudo/acid-in-clay-close.git
cd acid-in-clay-close
git checkout remediation/tier3
git pull            # 确保拿到最新(含本轮 ESAS-OS 2.0 v2 与本交接文档)
```

**如果 clone 失败,按场景处理(详见 `AGENTS.md §3`):**
- **SSH 22 端口被墙/重置** → 走 OpenSSH 443 通道:
  ```powershell
  $env:GIT_SSH_COMMAND="ssh -p 443 -o HostName=ssh.github.com"; git clone git@github.com:LJZ-sudo/acid-in-clay-close.git
  ```
- **本机没配 SSH 公钥到 GitHub / 私有仓库** → 改用 HTTPS(会提示登录或用 Personal Access Token):
  ```powershell
  git clone https://github.com/LJZ-sudo/acid-in-clay-close.git
  ```
- 以上都不行 → **停下来告诉人类**:需要先把本机 SSH 公钥加到 GitHub,或提供 HTTPS 凭据。**不要绕路、不要伪造代码。**

**克隆成功的判据**:`acid-in-clay-close/AGENTS.md`、`acid-in-clay-close/V1.0-qianduan-mainline/` 等已出现在磁盘上。
此后所有命令的工作目录都在 `acid-in-clay-close/` 仓库内;本文档 §0 列的 canonical 文档也已可读。
**接着回到 §0 读文档,再做 §4 第 0 步环境自检。**

> 提示:U 盘里这份文档就是权威自举入口,自包含、足以引导你完成全部步骤。
> 若仓库根目录里也有同名 `HANDOFF_REAL_MACHINE_20260626.md`(已提交过的版本),内容应一致;
> 如有差异,以**更新日期较新**者为准。

---

## 2. 现在到哪了（真实状态，勿夸大）

- **科学主线 Stage0–Stage3 真实可运行**;A 轨 M0–M2 分析门已落地(纯代码,结果可复算)。
- **B 轨软件层全绿**:全量 **410 测试 passed**;自主硬件命令旁路已清零(`autonomous_bypass=0`);
  跨层失效闭环(Skill 撤销→E-Mem 失效→BO 视图重建→GP 重训)+ 端到端撤销演示已通过。
- **本轮(2026-06-24)新增 ESAS-OS 2.0 四个 v2 插件软件 v1**(+30 测试,均 shadow/旁挂、legacy 永不覆盖):
  1. 测量路径离线事务化 `stage1_optimization/scientific_harness/measurement_txn.py`
  2. Rb-ACT 动态 Rb 分析 Skill `stage0_measurement/rb_act/`(**仅 R0 离线 shadow + 合成验证;不改 legacy `rb_fitting.py`**)
  3. R²-Memory 角色隔离/可撤销/多轮记忆 `stage1_optimization/scientific_memory/agent_memory/`
  4. C³-Harness 收敛动作组合 `stage1_optimization/scientific_convergence/`(shadow 于 `termination_evaluator` 之上,**C³ 停 ⊆ legacy 停**)

> **诚实边界(必须始终守住)**:以上全是**软件层**(合成谱 / 历史夹具 / 离线 replay / 模拟器),**尚未经真机故障对照**。
> **不能用"软件 Demo / 测试通过"预支 Tier S。** 真机证据是软件替代不了的硬条件。

---

## 3. 下一步任务总览（这台电脑的使命）

**主线 = G1 真机重复实验(A 轨硬门)+ 同步开 Harness/Rb-ACT shadow 攒 B 轨真机证据。**
**不新增**除 G1 与后续凹凸棒土闭环之外的湿实验;破坏性故障注入一律用空载/参考电路/dummy,**绝不在 G1 贵重样品上做**。

执行顺序见 §4(第 0→4 步)。每一步的"门槛"过了才进下一步。

---

## 4. 真机执行步骤（照着做）

### 第 0 步 · 本机就位（纯软件，半天）

> 前提:你已完成 §1.5,当前在 `acid-in-clay-close/` 仓库根目录内。

```powershell
# 1) 依赖(至少 stage1 + 后端;真实多目标后端需 botorch)
python -m pip install -r V1.0-qianduan-mainline/stage1_optimization/requirements.txt
python -m pip install botorch torch

# 2) 密钥 + 机器相关路径(都走环境变量/.env，勿写死)
copy V1.0-qianduan-mainline\stage1_optimization\.env.example V1.0-qianduan-mainline\stage1_optimization\.env
#   编辑 .env 填 OpenRouter LLM_API_KEY(默认模型 openai/gpt-5.4)
$env:STAGE0_CHI_DATA_DIR="E:\chi_data"   # ← 改成本机 CHI 仪器数据目录

# 3) 冒烟自检(两条都要过才进真机)
cd V1.0-qianduan-mainline
python -m pytest -q                                   # 期望: 410 passed
python scripts/audit_hardware_write_paths.py --strict # 期望: autonomous_bypass=0, exit 0
```

**门槛**:`410 passed` 且审计 `exit 0`。不过就先修,别开测。

---

### 第 1 步 · G1 同配方重复（A 轨唯一硬门，决定档次）

> ⚠️ **开测前先盖时间戳**(前瞻纪律,见 §6):把本轮 G1 计划/允许声称写进
> `prospective_2026H2/line_B_mobo_closed_loop/`,然后 `git commit + push`,**push 成功后才开始测量**。

要测的配方(凹凸棒土,线 B):
- **主门**:`R=0.186 / N=1.029` **≥3 独立片**(独立制备 + 独立装夹,最好跨日期)
  → 给线 B **直接复现地板**,替换现在的"生物聚合物代理地板",去掉 Fig3 的 caveat。
- **续测**:`R=0.15 / N=1.03`、`R=0.12 / N=1.00` 各 1 片 → 判定"最优在参数域边缘还是内部"。

每片流程:
```powershell
# 在线测量(真机) 或 离线复算
python stage0_measurement/run_online.py --material LRS --harness_mode shadow ...
# 收口出 bundle(注意 bundle 由 run_closure_offline.py 生成，非 run_offline.py)
python stage0_measurement/run_closure_offline.py ...
```

**门槛/交付**:≥3 片主门 + 2 片续测,各出 `aggregated_results.json` + `stage0_result_bundle.json`;
更新线 B 直接复现地板(`LINE_B_LOCAL_DIRECT`)。

---

### 第 2 步 · G1 当天 Harness + Rb-ACT shadow 全开（B 轨攒真机证据，只记录不夺权）

- `run_online.py --harness_mode shadow`:`EvidenceTransaction` 旁路记录 C_P/C_M/C_E 对账 →
  `shadow_harness_log.jsonl`。**fail-safe,绝不影响 G1 测量。**
- **Rb-ACT R1 在线双跑**:同一条谱并行跑 legacy ↔ Rb-ACT,产 `delta_report`,**仍采用 legacy 值**
  (R1 不改数值链;五级门见 §5)。
- 把每片 bundle 喂离线 helper 验证准入语义:
  ```python
  # 在 stage1_optimization/ 下
  from scientific_harness.measurement_txn import submit_measurement_offline
  # 验证: 同 bundle 改谱质量 → U1–U6 准入随之变; 样品错配 → 全 REJECT、blind_retry=0
  ```

**门槛/交付**:`shadow_harness_log.jsonl` 事件完整、差异均可解释、对测量零影响。

---

### 第 3 步 · 自然故障对账（关键 Tier S 证据；**不破坏样品**）

- 收集真机**自然发生**的异常(ACK 延迟 / 文件落盘慢 / 偶发量程触顶 / 夹具松动重测),
  用 shadow 日志做**对账**:报"Harness 当时会挡住/标记哪些错误,与人工 oracle 是否一致"。
- 破坏性故障矩阵(校准失效 / 样品 ID 错配 / ACK 丢失等)继续用**空载 / 参考电路 / dummy cell**,
  **绝不在 G1 贵重样品上做破坏性注入。**

**门槛/交付**:`shadow_discrepancy_report`(自然故障命中 + 对账一致性)。

---

### 第 4 步 · canary → enforce 灰度 + Rb-ACT 逐级解锁（仅在前 3 步稳定后）

- 三阶段切换(自主硬件命令):`SHADOW → CANARY(参考电路/低风险 EIS)→ ENFORCE(正式)`。
  升级条件见 `OPTIMIZATION_EXECUTION_PLAN §5`。
- **Rb-ACT 五级接入门**(唯一会改写数值链的 v2,逐级解锁,见 §5):
  本机当前在 **R0**;真机后依次 R1 双跑 → R2 审计接入(进 C_M 不进 BO)→ R3 噪声接入(喂 `train_Yvar`,均值仍 legacy)→ R4 正式接入(预注册后)。

**门槛/交付**:每升一级前先 commit+push;`delta_report` 对真实 LRS 谱**无未解释翻转**。

---

## 5. Rb-ACT 五级接入门（务必逐级，勿跳）

| 级 | 接入方式 | 对结论的作用 | 解锁条件 |
|---|---|---|---|
| **R0** | 离线 shadow:历史/合成谱跑,产 delta,不影响任何产物 | 0(纯观察) | ✅ 已在本仓完成 |
| **R1** | 在线双跑:G1 当天与 legacy 并行记录,仍用 legacy 值 | 0(留痕) | R0 delta 可解释 |
| **R2** | 审计接入:弃权/分歧进 C_M 审计,**不进 BO** | 仅收紧准入,不改数值 | 合成验证 + 人工 oracle 一致 |
| **R3** | 噪声接入:把 Rb-ACT 方差喂 `train_Yvar`,**均值仍 legacy** | 改 BO 权重,不改历史 σ | 预注册 + 多批稳定 |
| **R4** | 正式接入:Rb-ACT 后验均值作主值(产 `*_v2`+delta) | 改数值链 | 真机覆盖率/校准达标 + 预注册 |

---

## 6. 诚信纪律（项目灵魂，违反即作废）

1. **前瞻盖戳**:改任何影响主张的参数/阈值、开任何前瞻测量前,先 `git commit + push` 盖时间戳
   (`prospective_2026H2`)。**push 成功后才动手测。**
2. **不过度声称**:EIS-only **硬封顶 C4**(不声称结构/因果/收敛/"LLM 独立发现 LRS")。
   可声称 vs 不可声称的边界见 `_new_data_analysis/PUBLICATION_READINESS.md §5`。
3. **诚实 null**:闭环结果无论收敛与否都如实报;未越阈值就写"执行成功但未实现 Pareto 扩展(诚实 null)"。
4. **legacy 永不覆盖**:任何 v2 升级一律产 `*_v2` 并行版 + `delta_report`;**绝不改写 `rb_fitting.py` /
   `termination_evaluator.py` 等 legacy**(本仓已验证它们零改动,请保持)。
5. **不造假、不写没用的代码**:每完成一个较大任务先审核(跑测试 + 看 delta),出问题及时反馈,禁止偏离主线。
6. **路径卫生**:绝不写死绝对路径(`C:\Users\...` 等);机器相关位置走环境变量(`STAGE0_CHI_DATA_DIR` 等)。
   提交前可跑 `python V1.0-qianduan-mainline/scripts/audit_mainline.py` 查残留写死路径。

---

## 7. 本阶段交付物清单（决定能否升档）

- [ ] `g1_transaction_manifest`:≥3 片主门 + 2 片续测,SHA256 链完整。
- [ ] 线 B **直接复现地板**(`LINE_B_LOCAL_DIRECT`),替换生物聚合物代理。
- [ ] `shadow_harness_log.jsonl` + `shadow_discrepancy_report`(Harness 对账 + 自然故障命中)。
- [ ] Rb-ACT `delta_report`(真实 LRS 谱,无未解释翻转)。
- [ ] (写作)把 G1 结果 + M0–M2 v2 写进 Methods/Results/SI,收口 G3 措辞、G5 出版工程。

---

## 8. 档次预期（诚实，给人看的，不写进代码主张）

- **A 轨**:G1 做完 + 写作收口 → **稳投 Tier B**(Comm. Chem./Mater.、CRPS、npj Comput. Mater.,IF 6–10);
  不做 G1 → 落 `Digital Discovery / MLST`(IF 4–6)。
- **B 轨**:**软件全绿 ≠ Tier S**。要够 Tier S(Nature Machine Intelligence / Matter)**必须有真机故障对照证据**
  (shadow 对账证明"挡住了真实发生的错误"+ enforce 真机灰度 + Rb-ACT 至少 R2/R3)。
- **发表策略**:首选拆两篇——A 轨先投 Tier B;B 轨以 A 轨真机为案例,待真机证据齐备冲 Tier S。

---

## 9. 常用命令速查

```powershell
# 全量测试(应 410 passed)
cd V1.0-qianduan-mainline ; python -m pytest -q
# 硬件写路径审计(应 autonomous_bypass=0, exit 0)
python scripts/audit_hardware_write_paths.py --strict
# B 轨端到端撤销演示
python -m scientific_e2e.demo_end_to_end           # 在 stage1_optimization/ 下
# ESAS-OS 2.0 v2 离线复算(纯代码，可无真机跑)
python -c "import sys;sys.path.insert(0,'stage1_optimization');from scientific_memory.agent_memory import bench;print(bench.run()['overall_ok'])"
python -c "import sys;sys.path.insert(0,'stage1_optimization');from scientific_convergence import bench;print(bench.run()['ok'])"
python -m pytest tests/test_rb_act.py tests/test_measurement_txn.py tests/test_r2_memory.py tests/test_c3_harness.py -q
# 后端 / 前端(看板，可选)
python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000
cd frontend ; npm install ; npm run dev            # http://127.0.0.1:5173
```

---

> **一句话给接手的 Agent**:本项目证据全真、负结果不藏、主张被代码护栏封顶。A 轨已到 Tier B 投稿线,
> **你这台机器的使命是把 G1 那组凹凸棒土同配方重复测出来,并在 G1 当天全开 Harness/Rb-ACT shadow 攒 B 轨真机证据**。
> 全程守 §6 诚信纪律:先 push 盖戳再测、不过度声称、legacy 永不覆盖、Rb-ACT 逐级过门。软件已就绪(410 测试),
> 缺的只有真机证据——而这正是软件替代不了、决定能否冲 Tier S 的东西。
