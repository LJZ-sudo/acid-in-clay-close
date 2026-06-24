# 真机联调方案(跨机迁移 + 硬件入口 + Harness shadow + 密钥)2026-06-22

> 面向"明天在**另一台真机电脑**上做联调":把本机代码搬过去 → 配环境/密钥 → 空载冒烟 → G1 同配方重复
> (带 M5-A 三重提交 shadow 旁路)→ 把 Demo A/B/C 从"软件"升级为"真实闭环验证"。
> 纪律(`prospective_2026H2`):**改任何会进前瞻校准的参数前,先 git commit+push 盖时间戳,再测量。**

---

## 0. 一句话

**用 git clone 搬代码(别手工拷贝)**;在真机配 `.env`(填 OpenRouter key 到 `LLM_API_KEY`)+ `STAGE0_CHI_DATA_DIR` + COM 串口;
先**空载/虚拟冒烟**确认链路,再做 G1 真实测量,并让 **M5-A Harness 以 shadow 旁路记录**(不夺仪器控制权)。

## 1. 跨机搬运:**git clone,不要手工拷贝**(AGENTS.md 明确)

手工拷贝会带上本机绝对路径历史产物、漏掉 `.env` 模板逻辑。正确做法:

**本机(先把本轮新代码提交并推送)**:
```bash
# 本轮新增:configs/、stage0_v2/、scientific_memory/、scientific_harness/、scientific_skills/、
#          objectives/、agents/prompt_envelope.py、evidence_admission.py、tests/* 等
git add -A
git commit -m "A-track M0-M2 hardening + B-track WP0-WP5 (SciTX/E-Mem/PC-Skills, 208 tests green)"
# 若 22 端口被封,走 443:
$env:GIT_SSH_COMMAND="ssh -p 443 -o HostName=ssh.github.com"; git push
```

**真机电脑**:
```bash
git clone git@github.com:LJZ-sudo/acid-in-clay-close.git
cd acid-in-clay-close
git checkout remediation/tier3        # 当前工作分支
```

> ⚠️ 若真机无法联网/无 GitHub 权限,只能拷贝:**用 U 盘拷整个仓库目录(含 .git)**,到真机 `git status` 确认完整;
> **务必在真机重新建 `.env`(见 §3),不要把本机 `.env` 拷过去**(机器相关 + 密钥不入库)。

## 2. 真机环境(硬件相关依赖)

```bash
# 分析/闭环核心(与本机一致)
python -m pip install -r V1.0-qianduan-mainline/stage1_optimization/requirements.txt
python -m pip install -r V1.0-qianduan-mainline/stage3_mechanism/requirements.txt
python -m pip install fastapi uvicorn python-socketio openai python-dotenv
python -m pip install numpy scipy pwlf impedance scikit-optimize scikit-learn pyyaml
# 真机额外:温控串口 + CHI GUI 自动化(run_online 依赖)
python -m pip install pyserial            # TemperatureDriver 串口
# ChiExecutor 是 CHI660E 上位机 GUI 自动化:确认其依赖(pywinauto/pyautogui 之类)按 modules/automation 实际 import 安装
```
- **必须在真机本地装好 CHI660E 工作站软件**,并确认 `--chi_template_dir` 指向其宏模板。
- 确认温控器 COM 口(设备管理器查,如 COM3)。

## 3. 密钥与机器相关项(全走 .env / 环境变量,**不硬编码**)

> **重要**:三大 Demo(A/B/C)是**纯软件、不调用 LLM**,所以现在没接 key 是对的。真机闭环里 LLM 只在
> **Stage1 Step5 策略规划 / Stage3 上游 S04–S08 / Stage0 在线相变(可选)** 用到,统一从 `.env` 读 `LLM_API_KEY`。

```bash
# Stage1(闭环 LLM 顾问)
copy V1.0-qianduan-mainline\stage1_optimization\.env.example V1.0-qianduan-mainline\stage1_optimization\.env
# Stage3(机理/文献 LLM)
copy V1.0-qianduan-mainline\stage3_mechanism\.env.example V1.0-qianduan-mainline\stage3_mechanism\.env
```
然后编辑两个 `.env`,把 `key.txt` 里的 OpenRouter key 填进 **`LLM_API_KEY`**(其余默认即可):
```
LLM_BASE_URL="https://openrouter.ai/api/v1"
LLM_API_KEY="sk-or-v1-<你的 key>"
LLM_MODEL="openai/gpt-5.4"
LLM_TEMPERATURE=0.0
```
- **`LLMClient` 只读 `.env` 的 `LLM_API_KEY`,不读 `key.txt`**(`key.txt` 仅供分析/出图脚本)。
- `key.txt` / `.env` 均已被 `.gitignore`(`key.txt`、`.env`、`*_key.txt`)→ **不会入库,安全**。
- 机器相关项:
  - `STAGE0_CHI_DATA_DIR`:真机 CHI 数据目录(默认 `E:\chi_data`)。`setx STAGE0_CHI_DATA_DIR "E:\chi_data"` 或在命令里 `--chi_data_dir`。
  - 自检:`python -c "import os;from openai import OpenAI;print('key set:', bool(os.getenv('LLM_API_KEY')))"`(在 stage1 目录、加载 .env 后)。

## 4. 联调顺序(从安全到真实,逐级放开)

**Step A — 离线复算冒烟(不接硬件,确认代码在真机能跑)**
```bash
# 全量测试应 208 passed / 0 failed(B 轨 WP0-WP5 + A 轨 M0-M2 全绿;两处先存失败已修复)
python -m pytest V1.0-qianduan-mainline/tests V1.0-qianduan-mainline/backend_api/tests -q
# 三个 Demo 应 acceptance_pass=True
python V1.0-qianduan-mainline/stage1_optimization/scientific_memory/demo_b.py
python V1.0-qianduan-mainline/stage1_optimization/scientific_harness/demo_a.py
python V1.0-qianduan-mainline/stage1_optimization/scientific_skills/demo_c.py
# (可选)端到端撤销演示 + 硬件写路径审计(应 autonomous_bypass=0)
python V1.0-qianduan-mainline/stage1_optimization/scientific_e2e/demo_end_to_end.py
python V1.0-qianduan-mainline/scripts/audit_hardware_write_paths.py --strict
```

**Step B — 硬件空载/哑元冒烟(接硬件,但不放真样品)**
- 温控:确认 COM 口能连、能读温度、能设温(空腔)。
- CHI:用哑元电池/空腔跑一次阻抗,确认 `--chi_data_dir` 下生成 txt、能被 `chi_parser` 解析。
- 跑一个**小温区**在线流程确认链路:
```bash
cd V1.0-qianduan-mainline/stage0_measurement
python run_online.py --material SMOKE --port COM3 --T_start 25 --T_end 15 ^
  --coarse_step 5 --chi_data_dir E:\chi_data --thickness 0.07 --area 1.96 ^
  --disable_auto_stop
```
- 后端驾驶舱(可选):`python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000` + 前端 `npm run dev`,在 `/control` 看温度/测量事件流。

**Step C — G1 真实测量(唯一湿实验门)+ M5-A Harness shadow**
- 配方:`R=0.186/N=1.029` 同配方 **+3 独立片**(直接复现地板);续测 `R=0.15/N=1.03`、`R=0.12/N=1.00`。
- **前瞻纪律**:新 R/N 进校准前先 `git commit+push` 盖时间戳;复现片如实标 retrospective。
- **Harness shadow(把 Demo A 升级为真实)**:G1 期间对每个测量点,把真实链路信息(命令下发/确认/超时/
  文件是否生成/温度日志/Stage0 准入)**旁路喂给** `scientific_harness.CommitController.process(...)`,记录
  "现有系统判定 vs 三重提交判定" 的差异 —— **不夺仪器控制权**。验收:G1 全程盲目重试=0、无效测量不进 BO。
  - 落地最简方式:在 `run_online` 的每点测量回调后,构造 `measurement={qa_failed,kk_mu_median,
    rb_method_spread_dex,uncertainty_status}`(Stage0 已算)+ 一个轻量 instrument 适配器(暴露
    `dispatch/query_output_file/query_instrument_state/query_sample_id/temp_equilibrated/calibration_valid`),
    调 `CommitController.process` 旁路记录到 JSON。先 shadow、不接管。

**Step D — 后续闭环(M4,可选,≥3 前瞻轮)**
```bash
cd V1.0-qianduan-mainline/stage1_optimization
python run_optimization_loop.py --optimizer mobo --mode real ^
  --campaign_config campaigns/attapulgite_aice_campaign.json --stage0_results_dir <G1输出目录>
```
- 噪声感知后端:G1 直接地板出来后,把 `optimizer_backend=noise_aware_skopt`(M2-3)接上,观测方差从
  `CROSS_SYSTEM_PROXY` 换 `LINE_B_LOCAL_DIRECT`。

## 5. 联调验收清单(把"软件 Demo"升级为"真实闭环验证")

- [ ] 真机 208 passed / 0 failed + 三 Demo acceptance_pass=True + `autonomous_bypass=0`。
- [ ] `.env` 的 `LLM_API_KEY` 生效(LLM 顾问能调通,temperature=0)。
- [ ] 空载冒烟:温控可设/读、CHI 出 txt 可解析。
- [ ] G1 同配方 ≥3 片:`history_db_attapulgite.json` 增 ≥3 trial;`LINE_B_LOCAL_DIRECT` 直接地板出炉。
- [ ] **Harness shadow 真机日志**:盲目重试=0、无效测量不进 BO、确认丢失能重建 → Demo A "真实版"。
- [ ] (G/记忆)把 G1 期间任一真实失效(如某点 KK FAIL / 文件缺失)灌进 `scientific_memory`,看主张是否自动降级 → Demo B "真实版"。
- [ ] 全程前瞻冻结 + git 时间戳留痕。

## 6. 风险与回滚

- **绝不让 shadow Harness 接管仪器**:首次联调只旁路记录;确认判定一致后再考虑接管(后续闭环)。
- **真机绝对路径**:只走 `STAGE0_CHI_DATA_DIR`/`--chi_data_dir`,代码内不写死(审计:`scripts/audit_mainline.py`)。
- **密钥**:只在真机 `.env`;不提交、不贴聊天、不写进任何 `*.md`/代码。
- **失败照实记**:任何点失败如实留痕(诚实 null 纪律),不补不改。
