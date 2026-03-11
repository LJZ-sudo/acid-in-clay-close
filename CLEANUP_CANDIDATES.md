# CLEANUP_CANDIDATES（2026 首批清理候选）

> 目的：把 `close/` 中“主线保留”和“可优先归档”的内容进一步具体化。  
> 原则：**先归档，后删除**。本文件中的 “可清理” 默认表示“优先移动到 archive_*”，不是建议立刻永久删除。

---

## 1. 绝对不要先动的内容

这些目录/文件是当前主线，先不要删，也不要随意移动：

- `auto_control/`
- `specific_conductance/`
- `config/`
- `data/`
- `phase3/`
- `paper/`
- `paper_figure/` 中真正用于生成主图的 `figure*/plot_*.py`、`*_data.csv`、`README.md`
- `docs/Draft_V2_1_En_REFS_V2.txt`
- `docs/SI-V1.1_FINAL.txt`
- `README.md`
- `PROJECT_MAP.md`

---

## 2. 第一批高置信候选（已执行删除）

这些文件从命名和用途上看，明显更像“调试/核对/临时验证脚本”，通常不会是长期主线入口。

### 2.1 `paper_figure/` 下的调试脚本

执行状态：

- 已删除

已处理文件：

- `paper_figure/debug_segments.py`
- `paper_figure/diagnose_fit_mismatch.py`
- `paper_figure/diagnose_fit_vs_data.py`
- `paper_figure/diagnose_full_range.py`
- `paper_figure/verify_final_fix.py`
- `paper_figure/verify_refit.py`

理由：

- 文件名明确指向 debug / diagnose / verify；
- 更像为某次图像修正服务的辅助脚本，而不是稳定主流程；
- 归档后不影响 `paper_figure/figure*/plot_*.py` 这些主绘图脚本。

### 2.2 根目录的测试脚本

执行状态：

- 已删除

已处理文件：

- `test_phase1.py`
- `test_phase2.py`
- `test_phase3.py`
- `test_single_sample.py`

理由：

- 这些脚本更偏“手工验证入口”，不是正式 pipeline 入口；
- 当前真正的主入口是 `auto_control/run_closed_loop.py`、`phase3/run_all.py`、`run_phase2_complete.py`；
- 若将来要重新验证，还可以从归档区找回。

---

## 3. 第二批中等置信候选（已执行删除）

这些文件大概率不是主线，但仍然可能承载一次重要修复记录。  
本轮已按“直接清理”策略执行删除。

执行状态：

- 已删除

已处理文件：

- `fix_rn_in_output.py`
- `fix_s60_conductivity_phase1.py`
- `check_rn_consistency.py`

原判断理由：

- 命名显示它们主要是一次性修复/一致性检查工具；
- 但这几个修复与 R/N 参数、S60 电导率等关键结论相关，历史价值还在；
- 原本更稳妥的做法是归档保留；当前已按用户要求直接删除。

---

## 4. 第三批低置信候选（暂时保留）

这些文件虽然看起来版本较多或可能较老，但当前还不能轻易判断“肯定没用”：

- `phase3-v2.0/` 整个目录
- `paper_figure/figure2/`、`figure3/`、`figure4/` 中的多个 `v2`, `v3` 脚本
- `output/phase2_reports/`、`output/phase3_results/` 中的历史结果
- `docs/` 下除当前草稿外的各类分析和定位文档

原因：

- 这部分可能仍和当前论文图、结果解释、版本对比相关；
- 需要你后续结合实际引用情况，再决定哪些移到 `archive_output/` 或 `archive_docs/`。

---

## 5. 推荐的实际清理顺序

### Step A：先建归档目录

建议手动新建：

- `archive_code/`
- `archive_output/`
- `archive_docs/`

### Step B：第一批已完成

第 2 节中的 10 个文件已删除。  
这是第一轮最不容易伤到主线的一步。

### Step C：跑一遍主线确认无影响

建议至少确认：

- `python phase3/run_all.py` 的入口说明仍然清晰；
- `auto_control/run_closed_loop.py` 没有依赖这些测试/调试脚本；
- `paper_figure/figure*/plot_*.py` 仍然都在。

### Step D：第二批已完成

`fix_* / check_*` 脚本已删除。

---

## 6. 当前结论

第一刀已经完成：

1. `paper_figure/debug/diagnose/verify` 这 6 个脚本  
2. 根目录 4 个 `test_*.py`

前两批脚本类清理已完成。  
下一步最值得继续处理的是：

1. `output/` 中旧版本结果与历史报告；
2. `paper_figure/figure2/3/4` 中明显重复的多版本绘图脚本；
3. `docs/` 中与当前实现不一致的旧分析说明文档。
