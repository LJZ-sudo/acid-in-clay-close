# 预注册 · E1 线 B「直接复现地板」（凹凸棒土同配方**回溯**重复）

状态：`ANALYSIS_PLAN_FROZEN`（本块冻结的是**分析方法 + 允许声称**；commit + push 后获服务器时间戳）
预注册者：JZ（执行 Agent 代写，待 JZ 确认后 push）
预注册日期：2026-06-27
对应 canonical 计划：`_new_data_analysis/E1_attapulgite_floor_plan.md`
硬化目标：补线 B 唯一硬缺口 —— 用**体系自身**直接复现地板替换生物聚合物 LRS 代理地板（去 §11.3 caveat）

---

## 0. ⚠ 性质声明（诚实，最重要）

本轮是 **回溯式（retrospective）复现地板测量**：重复的是**已存在的 campaign 最优配方 trial 1（R=0.186, N=1.029≈1.03）**，
**不是**新 R/N 前瞻探索点。

- 三批样品已于 **2026-06-24 ~ 2026-06-25** 完成合成 + 宽温 EIS 测量（见 §2），**早于本预注册时间戳**。
- 因此本块**不主张**"先冻结后测量"的前瞻顺序；它冻结的是 **后续分析方法与允许声称**，
  防止"看到地板数字后再调分析口径"。
- 严格的"先 push 盖戳→再合成"前瞻纪律（HANDOFF §6.1 / 本目录 `PREREGISTRATION.md` §8）
  **仍然适用于任何新 R/N 探索点**（如 E1 §4 的 R≈0.15/N≈1.03 等），那些必须经官方 MOBO+LLM 管线冻结后才合成。

---

## 1. 测量对象（同配方，独立制备 + 独立装夹，跨日期）

配方（三批一致，逐字取自各批 `材料制备.txt`）：`0.609 g 85% H₃PO₄ + 0.42 g 去离子水 + 1 g 凹凸棒土`，
即 **R = 0.186，N = 1.03**。面积均 1.96 cm²；厚度因独立压片而异（散布的真实来源）。

| 批次 | 数据文件夹 | 样品标识 | 厚度 (cm) | 面积 (cm²) | EIS 测量时段 | 宽温范围 |
|---|---|---|---|---|---|---|
| A | `E:\固态电解质\2026.6.24-2` | R0.186-N1.03-1 | 0.0712 | 1.96 | 2026-06-24 00:10→07:52 | +18 → −78 °C |
| B | `E:\固态电解质\2026.6.25-3` | R0.186-N1.03-3 | 0.0654 | 1.96 | 2026-06-24 14:56→22:35 | +19 → −80 °C |
| C | `E:\固态电解质\2026.6.26-1` | R0.186-N1.03-1 | 0.0564 | 1.96 | 2026-06-25 09:06→20:48 | +19 → −80 °C |

EIS 协议：CHI660E，1 MHz→0.1 Hz，Amplitude 0.005 V，Init E 0 V；逐温点（约 3 °C 步进）充分热平衡，两电极构型。
加上既有 campaign trial 1，合计 **≥4 次独立重复** → 可给 σ 散布的 std 与 p90。

> 数据指纹：每批所有 `R0.186*_T*_f0.1_*.txt` 谱文件的 SHA256 清单于 push 时随 `g1_transaction_manifest` 一并记录（§7）。

---

## 2. 冻结的分析方法（取自 E1 计划 §3，事前写死，不得事后改口径）

1. 每批走 Stage0 离线管线（`run_offline.py --chi_pattern "R0.186*.txt"`，逐批传各自 thickness/area）
   → `stage0_result_bundle.json` + `aggregated_results.json` + 分段 Arrhenius + σ(T) 表。
2. 对同配方重复，在**匹配温度**算 `|Δlog₁₀σ|`；分 **warm（≥ −20 °C）/ cold（< −20 °C）** 两段，
   各报**中位**与 **p90**。
3. 传播到 **combined_score 地板**（同 §11.3 方法）→ 得线 B 体系自身地板带 **`LINE_B_LOCAL_DIRECT`**，
   替换现行 `CROSS_SYSTEM_PROXY`（生物聚合物 LRS 代理，0.262 dex）。
4. 用直接地板重做 §11.3「顶端候选差 vs 地板」对照图，去掉"代理"caveat。
   **无论直接地板比代理更紧或更松，都如实报告，不预设方向。**

判定 / 验收门：≥3 次独立重复即给出可用 std；结论随数据走。

---

## 3. B 轨同步（离线，复用已测谱，不夺权）

既往三批为**离线既有数据**，无法补采"测量当天的 live `shadow_harness_log.jsonl`"；改以**离线 helper** 在同一批 bundle 上攒 B 轨证据：
- `scientific_harness.measurement_txn.submit_measurement_offline`：验证 U1–U6 准入语义（改谱质量→准入随之变；样品错配→全 REJECT、blind_retry=0）。
- Rb-ACT **R0 离线 shadow / R1 双跑**：在三批真实 LRS 谱上跑 legacy ↔ Rb-ACT，产 `delta_report`，**仍采用 legacy 值**（不改数值链；五级门见 HANDOFF §5）。
- legacy（`algorithms/rb_fitting.py`、`termination_evaluator.py`）**零改动**，所有 v2 产物均 `*_v2` + `delta_report` 并行。

---

## 4. 允许 / 禁止声称（EIS-only 硬封顶 C4）

- ✅ 允许：测得线 B 体系**自身**的复现地板（warm/cold 的 std、p90）；地板均匀性（若续做高 σ 点副测）；
  "顶端候选差 vs 直接地板"的诚实对照（无论结论方向）。
- ❌ 禁止：结构 / 因果 / 机制声称；"BO+LLM 发现了 LRS"；普适最优；用 EIS 反推相变机制；把回溯地板说成前瞻发现。

---

## 5. 留痕（已回填）

- [x] 本块冻结 commit hash：`e2bcbe9`（仅含本预注册；分析产物在随后的 commit）
- [x] push 时间（UTC+8，服务器盖戳）：`2026-06-27T21:11:21+08:00`（远端 `LJZ-sudo/acid-in-clay-close`，分支 `remediation/tier3`，`f215938..e2bcbe9`）
- [x] 三批谱文件 SHA256 清单 / `g1_transaction_manifest`：`V1.0-qianduan-mainline/output/e1_floor/g1_transaction_manifest.json`（109 条原始谱：A33 / B34 / C42）
- [x] 分析产物落盘路径：
  - `V1.0-qianduan-mainline/output/e1_floor/LINE_B_LOCAL_DIRECT.json`（直接复现地板）
  - `V1.0-qianduan-mainline/output/stage0_results/ATP-R0.186-N1.029-batch{A,B,C}-*/stage0_result_bundle.json` + `closure_report.json`
  - `V1.0-qianduan-mainline/output/e1_floor/rb_act_delta_report.json` + `b_track_measurement_txn_evidence.json`（B 轨离线证据）
  - 复算脚本：`_new_data_analysis/e1_floor_analysis.py`、`_new_data_analysis/e1_btrack_evidence.py`

## 6. 本轮结果摘要（诚实，含 null）

- **直接复现地板 `LINE_B_LOCAL_DIRECT`**（两两批次 `|Δlog10σ|`，3 片独立）：
  - WARM（T≥−20 °C）：median 0.106 / p90 0.146 dex → **比代理地板 0.262 紧**。
  - COLD（T<−20 °C）：median 0.158 / p90 **0.356** dex → **冷段 p90 超过代理 0.262（更松）**，重做 §11.3 对照时冷段判据更严（诚实限制，写入 Discussion）。
- 三批相变温度一致（256/254/257 K 与 226/222/227 K）；RT σ：0.0219 / 0.0162 / 0.0176 S/cm。
- **B 轨（离线，R0→R1）**：measurement_txn 准入语义符合预期（clean→进 BO、blind_retry=0；坏谱/样品错配→全 REJECT）；
  Rb-ACT R1 双跑 92 配对点 `|Δlog10 Rb|` median=p90=0.0000 dex、**0 未解释翻转**，弃权 17/109（增量价值在弃权+不确定度）；**legacy 数值链零改动**。
