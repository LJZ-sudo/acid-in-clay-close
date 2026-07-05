# -*- coding: utf-8 -*-
"""Hardware adapter — bridges FastAPI routes to Stage 0 measurement workflow.

Provides a singleton that wraps stage0_measurement hardware controllers
and exposes actions that the Control/Data/Agent routers call.

When no hardware is connected, operates in simulation mode with
synthetic data and SocketIO push events.  In both modes the adapter
calls *real* analysis code from stage0_measurement/modules/ for
Rb fitting, Arrhenius analysis, and phase-transition detection.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = PROJECT_ROOT.parent / "experiments" / "runs"

# G-2 真机故障注入合法类型(仅作用于**测量提交治理路径**的输入,绝不改温控/CHI 物理命令)。
# 诚实边界:提交路径 measurement_txn(经 ReplayInstrument)只忠实拦截**样品核对(C_P)**与
# **QA/计量门(M)**两类。
_INJECTABLE_FAULTS = {"SAMPLE_MISMATCH", "QA_FAIL"}
# H2:仪器**在线见证类**协议级故障(经 OnlineInstrumentWitness + 真实 EvidenceTransaction):
#   ACK 丢失/仪器卡住/文件未写或延迟/在线条码错配/校准过期。驱动边界软件注入,绝不碰物理安全。
#   物理破坏性故障(电极短接/断路、真样品损伤)仍须 dummy cell,不在此注入。
_PROTOCOL_FAULTS = {"ACK_LOSS", "INSTRUMENT_STUCK", "FILE_MISSING", "FILE_DELAY",
                    "SAMPLE_SWAP", "CALIBRATION_EXPIRED"}


def _ensure_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"{label} must stay within {root_resolved}: {resolved}") from exc
    return resolved


def _validate_path_token(value: Any, label: str, *, max_len: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > max_len:
        raise ValueError(f"{label} is too long")
    forbidden = set('/\\:*?"<>|[]')
    if text in {".", ".."} or any(ch in forbidden or ord(ch) < 32 for ch in text):
        raise ValueError(f"{label} contains unsafe path or glob characters: {text!r}")
    return text


def _resolve_stage1_path(value: Optional[str], base_dir: Path) -> Optional[Path]:
    if not value:
        return None
    path = Path(value)
    resolved = path if path.is_absolute() else (base_dir / path)
    return _ensure_within(resolved, PROJECT_ROOT, "Stage1 path")


def _load_stage1_campaign_runtime(
    campaign_slug: Optional[str] = None,
    campaign_config: Optional[str] = None,
    history_db_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    source_tag: Optional[str] = None,
) -> Dict[str, str]:
    stage1_root = PROJECT_ROOT / "stage1_optimization"
    raw_slug = _validate_path_token(campaign_slug or "attapulgite_aice_campaign", "campaign")
    slug = Path(raw_slug).stem if raw_slug.lower().endswith(".json") else raw_slug
    slug = _validate_path_token(slug, "campaign")
    config_path = _resolve_stage1_path(campaign_config, PROJECT_ROOT)
    if config_path is None:
        config_path = stage1_root / "campaigns" / f"{slug}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Stage1 campaign config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)
    storage = config.get("storage") or {}

    resolved_history = _resolve_stage1_path(
        history_db_path or storage.get("history_db"),
        stage1_root,
    )
    if resolved_history is None:
        resolved_history = stage1_root / "campaign_memory" / "history_db_attapulgite.json"

    resolved_output = _resolve_stage1_path(
        output_dir or storage.get("output_dir"),
        stage1_root,
    )
    if resolved_output is None:
        resolved_output = stage1_root / "output"

    return {
        "campaign_slug": slug,
        "campaign_config": str(config_path.resolve()),
        "history_db_path": str(resolved_history.resolve()),
        "output_dir": str(resolved_output.resolve()),
        "source_tag": source_tag or config.get("source_tag") or slug,
    }


def _read_llm_key_from_env_file() -> Optional[str]:
    """Fallback: read LLM_API_KEY from stage1_optimization/.env.

    The project已经在 ``stage1_optimization/.env`` 里维护了一份共用的
    ``LLM_API_KEY``（PoloAPI / DeepSeek）。phase_detect.py 默认读
    ``POLOAPI_KEY`` 环境变量；为了避免用户每次启动后端都手动 set，这里把
    那份 .env 文件再扫一遍当作兜底来源。
    """
    candidates = [
        PROJECT_ROOT / "stage1_optimization" / ".env",
        PROJECT_ROOT / ".env",
    ]
    for p in candidates:
        try:
            if not p.exists():
                continue
            for raw in p.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k in ("LLM_API_KEY", "POLOAPI_KEY") and v:
                    return v
        except Exception:
            continue
    return None


def _safe_import_point_pipeline():
    """Return ``analyze_eis_point`` from the real Stage0 analysis facade.

    The legacy path ``stage0_measurement.modules.measurement_pipeline`` never
    existed in this codebase; the correct module is
    ``stage0_measurement.modules.analysis.eis_pipeline``.
    """
    try:
        from stage0_measurement.modules.analysis.eis_pipeline import analyze_eis_point
        return analyze_eis_point
    except ImportError:
        return None


def _safe_import_phase_detector():
    """PhaseTransitionDetector was removed from the Stage0 refactor; agent-side
    decisions now handle phase logic.  Return None so the adapter no-ops."""
    return None


def _safe_import_analyze_experiment_state():
    """Return ``analyze_experiment_state`` (per-point LLM phase / decision Agent).

    Lives in ``stage0_measurement.modules.analysis.phase_detect`` and is the
    SAME function that ``OnlineExperimentWorkflow`` calls after each point.
    Returns ``None`` if the module can't be imported (e.g. openai not installed).
    """
    try:
        from stage0_measurement.modules.analysis.phase_detect import analyze_experiment_state
        return analyze_experiment_state
    except Exception as exc:  # noqa: BLE001
        print(f"[hardware_adapter] analyze_experiment_state import failed: {exc}")
        return None


def _fmt(num, fmt="{:.2f}", fallback="--"):
    """Safe formatter — never crashes on None / non-numeric."""
    if num is None:
        return fallback
    try:
        return fmt.format(float(num))
    except (TypeError, ValueError):
        return fallback


def _fmt_e(num, prec=2, fallback="--"):
    if num is None:
        return fallback
    try:
        return f"{float(num):.{prec}e}"
    except (TypeError, ValueError):
        return fallback


def _format_event_narrative(event_type: str, p: Dict[str, Any]):
    """Map (event_type, payload) → (level, agent, narrative message).

    Mirrors the rich human-readable backend logs of the legacy V1.0 stack:
    每个事件都生成一句带 emoji + 关键数字的中文摘要，前端 TerminalLog
    可以直接做关键字高亮（°C / Rb / R² / σ / 相变 / 熔断 / ……）。
    """
    p = p or {}

    def temp(key="temperature_C"):
        return _fmt(p.get(key), "{:.2f}")

    # ---------------- Temperature & stability ----------------
    if event_type == "SET_T":
        return "INFO", "TempCtrl", f"🌡 下发目标温度 {_fmt(p.get('target_temperature_C'), '{:.1f}')}°C  (step #{p.get('step_idx', '?')})"
    if event_type == "WAIT_STABLE_ARRIVAL_START":
        return "INFO", "TempCtrl", f"⏳ 等待到达 {_fmt(p.get('target_temperature_C'), '{:.1f}')}°C  (eps={_fmt(p.get('eps_C'), '{:.2f}')}, 超时 {p.get('timeout_s', '?')}s)"
    if event_type == "WAIT_STABLE_ARRIVED":
        return "SUCCESS", "TempCtrl", f"✅ 到达 {_fmt(p.get('target_temperature_C'), '{:.1f}')}°C  (实际 {_fmt(p.get('actual_temperature_C'), '{:.2f}')}°C，用时 {_fmt(p.get('arrival_seconds'), '{:.0f}')}s)"
    if event_type == "WAIT_STABLE_DRIFT":
        return "WARNING", "TempCtrl", f"⚠️ 温度漂移：实际 {_fmt(p.get('actual_temperature_C'), '{:.2f}')}°C 偏离目标 {_fmt(p.get('target_temperature_C'), '{:.1f}')}°C，稳定窗口重置"
    if event_type == "WAIT_STABLE_TIMEOUT":
        return "ERROR", "TempCtrl", f"❌ 到温超时：等了 {_fmt(p.get('elapsed_s'), '{:.0f}')}s 仍未到 {_fmt(p.get('target_temperature_C'), '{:.1f}')}°C  (当前 {_fmt(p.get('actual_temperature_C'), '{:.2f}')}°C)"
    if event_type == "WAIT_STABLE":
        ok = bool(p.get("stable"))
        prefix = "✅ 温度已稳定" if ok else "⚠️ 温度未稳定"
        return ("SUCCESS" if ok else "WARNING"), "TempCtrl", f"{prefix}  target={_fmt(p.get('target_temperature_C'), '{:.1f}')}°C  actual={_fmt(p.get('actual_temperature_C'), '{:.2f}')}°C  hold={_fmt(p.get('hold_seconds'), '{:.0f}')}s"
    if event_type == "TEMPERATURE_REACHED":
        return "DEBUG", "TempCtrl", f"🌡 温度 {_fmt(p.get('temperature'), '{:.2f}')}°C / target {_fmt(p.get('target'), '{:.1f}')}°C"
    if event_type == "COOL_TO_START_STARTED":
        return "INFO", "TempCtrl", f"❄ 起点降温：先把温箱降到 T_start = {_fmt(p.get('t_start_C'), '{:.1f}')}°C 再开始测量"
    if event_type == "COOL_TO_START_DONE":
        return "SUCCESS", "TempCtrl", f"✅ 起点降温完成：已到 T_start = {_fmt(p.get('t_start_C'), '{:.1f}')}°C  (实际 {_fmt(p.get('actual_C'), '{:.2f}')}°C，用时 {_fmt(p.get('arrival_seconds'), '{:.0f}')}s)"
    if event_type == "COOL_TO_START_FAILED":
        return "ERROR", "TempCtrl", f"❌ 起点降温失败：T_start = {_fmt(p.get('t_start_C'), '{:.1f}')}°C，当前 {_fmt(p.get('actual_C'), '{:.2f}')}°C，原因 {p.get('reason')}"
    if event_type == "REHEAT_SETTLE_STARTED":
        return "INFO", "TempCtrl", f"🔥 回温后增强稳定：先静等 {p.get('settle_seconds', '?')}s 热惰性，再做 ×{p.get('stability_multiplier', '?')} 长稳定验证"
    if event_type == "REHEAT_SETTLE_DONE":
        return "SUCCESS", "TempCtrl", f"✅ 回温热惰性完成，进入增强稳定检测 (duration={_fmt(p.get('extended_stability_duration_s'), '{:.0f}')}s)"

    # ---------------- CHI / EIS measurement ----------------
    if event_type == "EIS_RUN":
        return "INFO", "Stage0", f"⚡ 启动 EIS 测量  at {_fmt(p.get('temperature_C'), '{:.2f}')}°C  (step #{p.get('step_idx', '?')})"
    if event_type == "CHI_MEASUREMENT_STARTED":
        out_path = p.get("output_file") or r"E:\chi_data"
        return "INFO", "CHI", f"⚡ CHI 测量启动  at {_fmt(p.get('temperature_C'), '{:.2f}')}°C  保存路径: {out_path}"
    if event_type == "CHI_MEASUREMENT_COMPLETED":
        return "SUCCESS", "CHI", f"✅ CHI 测量完成  → {p.get('output_file', '--')}  ({p.get('n_points', '?')} 频点)"
    if event_type == "CHI_MEASUREMENT_FAILED":
        return "ERROR", "CHI", f"❌ CHI 测量失败  at {_fmt(p.get('temperature_C'), '{:.2f}')}°C：{p.get('error', '未知错误')}"
    if event_type == "Rb_FIT":
        return "INFO", "Stage0", f"Σ Rb 拟合：T={_fmt(p.get('temperature_C'), '{:.2f}')}°C  Rb={_fmt_e(p.get('rb_ohm'))} Ω  method={p.get('rb_method', '--')}  R²={_fmt(p.get('r_squared'), '{:.4f}')}  σ={_fmt_e(p.get('conductivity_S_cm'))} S/cm"
    if event_type == "QC_GRADE":
        grade = p.get("qc_grade", "--")
        emoji = {"A": "🅰️", "B": "🅱️", "C": "©️", "D": "❎"}.get(grade, "•")
        lvl = "SUCCESS" if grade == "A" else "INFO" if grade == "B" else "WARNING"
        return lvl, "Stage0", f"{emoji} QC 评级 = {grade}  (R²={_fmt(p.get('r_squared'), '{:.4f}')})"
    if event_type == "MEASUREMENT_COMPLETED":
        ok = bool(p.get("success"))
        if ok:
            return "SUCCESS", "Stage0", (
                f"📊 测量完成 [step #{p.get('step_idx', '?')}]  "
                f"T={temp()}°C  Rb={_fmt_e(p.get('rb_ohm'))} Ω  "
                f"σ={_fmt_e(p.get('conductivity_S_cm'))} S/cm  "
                f"R²={_fmt(p.get('r_squared'), '{:.4f}')}  QC={p.get('qc_grade', '--')}"
            )
        return "WARNING", "Stage0", f"⚠️ 测量未通过 [step #{p.get('step_idx', '?')}]  T={temp()}°C  reason: {p.get('failure_reason', '未知')}"
    if event_type == "MEASUREMENT_SKIPPED":
        return "WARNING", "Stage0", f"⏭ 跳过测量  target={_fmt(p.get('target_temperature_C'), '{:.1f}')}°C  actual={_fmt(p.get('actual_temperature_C'), '{:.2f}')}°C  原因: {p.get('reason')}"

    # ---------------- Agent decisions ----------------
    if event_type == "AGENT_CONFIG":
        return "INFO", "Agent", f"⚙ Agent 配置：model={p.get('model')}  has_api_key={p.get('has_api_key')}  fine_scan_window={p.get('fine_scan_window_C', '?')}°C"
    if event_type == "AGENT_CALL_STARTED":
        return "INFO", "Agent", f"🧠 调用 LLM 相变分析  (n_points={p.get('n_points', '?')}, model={p.get('model')})"
    if event_type == "AGENT_DECISION":
        action = p.get("action", "CONTINUE")
        emoji = {"CONTINUE": "▶", "FINE_GRAINED_SCAN": "🔍", "ABORT": "⛔"}.get(action, "•")
        lvl = "WARNING" if action == "ABORT" else "INFO"
        next_C = p.get("next_temp_target_C")
        conf = p.get("confidence")
        llm = "LLM" if p.get("llm_called") else "rule"
        tail = f"  → 下一点 {_fmt(next_C, '{:.2f}')}°C" if next_C is not None else ""
        warn_tail = ""
        if p.get("warnings"):
            warn_tail = f"  ⚠ {','.join(p['warnings'])}"
        return lvl, "Agent", f"{emoji} Agent 决策: {action} [{llm}]  conf={_fmt(conf, '{:.2f}')}{tail}{warn_tail}"
    if event_type == "AGENT_DECISION_FAILED":
        return "ERROR", "Agent", f"❌ Agent 决策失败 (step #{p.get('step_idx', '?')}): {p.get('error')}"
    if event_type == "AGENT_FINE_SCAN":
        trig = _fmt(p.get('trigger_temperature_C'), '{:.2f}')
        nxt = _fmt(p.get('next_temperature_C'), '{:.2f}')
        end = _fmt(p.get('fine_band_end_C'), '{:.2f}')
        return "INFO", "Agent", f"🔍 进入精细扫描  trigger={trig}°C  回温→{nxt}°C  fine_step=1°C  扫到 {end}°C 退出"
    if event_type == "AGENT_FINE_BAND_TICK":
        return "DEBUG", "Agent", f"· Fine band 进行中  规划 {_fmt(p.get('planned_temperature_C'), '{:.2f}')}°C → {_fmt(p.get('next_planned_temperature_C'), '{:.2f}')}°C  (trigger={_fmt(p.get('trigger_temperature_C'), '{:.2f}')}°C)"
    if event_type == "AGENT_FINE_BAND_EXIT":
        return "INFO", "Agent", f"↩ 退出精细扫描带，恢复粗步长扫描  当前 {_fmt(p.get('current_temperature_C'), '{:.2f}')}°C  (trigger={_fmt(p.get('trigger_temperature_C'), '{:.2f}')}°C)"
    if event_type == "AGENT_ABORT":
        return "ERROR", "Agent", f"⛔ Agent 终止运行：{p.get('reason', '原因未提供')}"
    if event_type == "AGENT_BACKTRACK":
        return "INFO", "Agent", f"⤺ Agent 回退 Δ={p.get('delta')}°C → {_fmt(p.get('new_temperature_C'), '{:.2f}')}°C (mode={p.get('mode')})"
    if event_type == "AGENT_RE_MEASURE":
        return "INFO", "Agent", f"↻ Agent 要求重测当前点 ({_fmt(p.get('temperature_C'), '{:.2f}')}°C)"
    if event_type == "AGENT_UNAVAILABLE":
        return "WARNING", "Agent", f"⚠️ Agent 不可用：{p.get('reason')}"
    if event_type == "PHASE_TRANSITION_DETECTED":
        return "WARNING", "Stage0", f"🚨 检测到相变  at {_fmt(p.get('temperature_C'), '{:.2f}')}°C / {_fmt(p.get('temperature_K'), '{:.2f}')}K"

    # ---------------- Arrhenius ----------------
    if event_type == "ARRHENIUS_UPDATED":
        return "INFO", "Stage0", f"∝ Arrhenius 在线更新  segments={p.get('n_segments', '--')}"
    if event_type == "STAGE0_GLOBAL_ARRHENIUS_STARTED":
        return "INFO", "Stage0", f"∝ 全局 Arrhenius 竞争模型启动 (n_valid={p.get('n_valid', '?')} 点)"
    if event_type == "STAGE0_GLOBAL_ARRHENIUS_COMPLETED":
        return "SUCCESS", "Stage0", (
            f"✅ 全局 Arrhenius 完成  best_model={p.get('best_model_type', '--')}  "
            f"segments={p.get('n_segments', '--')}  transitions(K)={p.get('transition_temps_K') or '[]'}  "
            f"confidence={_fmt(p.get('confidence'), '{:.2f}')}"
        )
    if event_type == "STAGE0_GLOBAL_ARRHENIUS_FAILED":
        return "ERROR", "Stage0", f"❌ 全局 Arrhenius 失败：{p.get('error')}"
    if event_type == "STAGE0_GLOBAL_ARRHENIUS_SKIPPED":
        return "INFO", "Stage0", f"· 全局 Arrhenius 跳过：{p.get('reason')}  (n={p.get('n_valid') or p.get('n_points')})"

    # ---------------- Safety fuses ----------------
    if event_type == "SAFETY_RB_FUSE":
        return "ERROR", "Safety", f"⚠️ Rb 熔断：Rb={_fmt_e(p.get('rb_ohm'))} Ω > 阈值 {_fmt_e(p.get('threshold'))} Ω，停止运行"
    if event_type == "SAFETY_CONDUCTIVITY_FUSE":
        return "ERROR", "Safety", f"⚠️ 电导率熔断：σ={_fmt_e(p.get('conductivity_S_cm'))} < 阈值 {_fmt_e(p.get('threshold'))} S/cm，停止运行"
    if event_type == "SAFETY_CONSECUTIVE_FAIL_FUSE":
        return "ERROR", "Safety", f"⚠️ 连续失败熔断：{p.get('consecutive_failures')} 次失败 ≥ 阈值 {p.get('threshold')}，停止运行"

    # ---------------- Resume / state ----------------
    if event_type == "RESUME_LOADED":
        return "SUCCESS", "Run", f"↻ 断点续测：已加载 {p.get('n_measurements')} 个旧测量点 + {p.get('n_agent_decisions')} 个 Agent 决策，scan_mode={p.get('scan_mode')}"
    if event_type == "RESUME_SKIPPED":
        return "INFO", "Run", f"· 断点续测跳过：{p.get('reason')}"
    if event_type == "RESUME_CONTINUE":
        return "INFO", "Run", f"▶ 续测：从 step #{p.get('from_step_idx')} 继续，下一点 {_fmt(p.get('next_target_C'), '{:.2f}')}°C"

    # ---------------- Finalize ----------------
    if event_type == "FINALIZE_REHEAT_STARTED":
        return "INFO", "Finalize", f"🛡 设备保护：开始回温到 {_fmt(p.get('target_C'), '{:.1f}')}°C"
    if event_type == "FINALIZE_REHEAT_DONE":
        return "SUCCESS", "Finalize", f"✅ 设备已回温到 {_fmt(p.get('target_C'), '{:.1f}')}°C，可以安全断电"
    if event_type == "FINALIZE_REHEAT_FAILED":
        return "ERROR", "Finalize", f"❌ 回温失败 (target={_fmt(p.get('target_C'), '{:.1f}')}°C)：{p.get('error', '未知错误')}  ⚠ 请手动检查温箱状态"
    if event_type == "FINALIZE_REHEAT_SKIPPED":
        return "INFO", "Finalize", f"· 回温步骤跳过：{p.get('reason')}"
    if event_type == "RUN_MANIFEST_WRITTEN":
        return "SUCCESS", "Run", f"📝 运行清单已写入 → {p.get('path')}"
    if event_type == "RUN_MANIFEST_FAILED":
        return "WARNING", "Run", f"⚠️ 运行清单写入失败：{p.get('error')}"

    # ---------------- Post-processing ----------------
    if event_type == "POST_PROCESSING_STARTED":
        return "INFO", "PostProc", f"⚙ 自动后处理启动  sample_id={p.get('sample_id')}  ao_folder={p.get('ao_folder')}"
    if event_type == "POST_PROCESSING_COPY_DONE":
        return "INFO", "PostProc", f"📁 文件复制完成  {p.get('n_files', '?')} 个 .txt + 材料制备.txt → {p.get('target_dir')}"
    if event_type == "STAGE0_STARTED":
        return "INFO", "Stage0", f"◐ Stage0 处理启动 → {p.get('command') or 'process_ao_stage0.py'}"
    if event_type == "STAGE0_COMPLETED":
        return "SUCCESS", "Stage0", f"✅ Stage0 处理完成"
    if event_type == "STAGE0_FAILED":
        return "ERROR", "Stage0", f"❌ Stage0 处理失败：{p.get('error') or ('exit_code=' + str(p.get('exit_code')))}"
    if event_type == "CLOSURE_REPORT_STARTED":
        return "INFO", "Closure", f"◐ 单样品 Closure 报告生成中（与 Stage1 BO 无关） use_llm={p.get('use_llm')}"
    if event_type == "CLOSURE_REPORT_COMPLETED":
        return "SUCCESS", "Closure", f"✅ Closure 已写入  llm={p.get('llm_used')}  → {p.get('path', '')}"
    if event_type == "CLOSURE_REPORT_FAILED":
        return "WARNING", "Closure", f"⚠️ Closure 自动生成失败（可稍后在报告页点「Rebuild (LLM)」）：{p.get('error', '')}"
    if event_type == "STAGE1_STARTED":
        return "INFO", "Stage1", f"◑ Stage1 BO 优化启动 → {p.get('command') or 'run_optimization_loop.py'}"
    if event_type == "STAGE1_COMPLETED":
        return "SUCCESS", "Stage1", f"✅ Stage1 优化完成  新 R/N 推荐已生成"
    if event_type == "STAGE1_FAILED":
        return "ERROR", "Stage1", f"❌ Stage1 优化失败：{p.get('error') or ('exit_code=' + str(p.get('exit_code')))}"
    if event_type == "STAGE1_SKIPPED":
        return "INFO", "Stage1", f"⏭ Stage1 BO 已跳过（冷启动 / 手动）：{p.get('reason', '')}"
    if event_type == "POST_PROCESSING_COMPLETED":
        if p.get("stage1_skipped"):
            return "SUCCESS", "PostProc", f"✅ Stage0 完成；Stage1 未运行（冷启动模式）"
        return "SUCCESS", "PostProc", f"✅ 自动后处理全流程完成"
    if event_type == "POST_PROCESSING_FAILED":
        return "ERROR", "PostProc", f"❌ 自动后处理失败：{p.get('error')}"

    # ---------------- Misc ----------------
    if event_type == "EVIDENCE_PACKAGE_SAVED":
        return "DEBUG", "Run", f"📦 证据包已保存  {p.get('evidence_id')}"
    if event_type == "EXPERIMENT_COMPLETED":
        return "SUCCESS", "Run", f"🎉 实验完成  sample={p.get('sample_id')}  共测 {p.get('total_measurements', 0)} 点  status={p.get('status')}"
    if event_type == "EXPERIMENT_STARTED":
        return "SUCCESS", "Run", f"🚀 实验启动  sample={p.get('sample_id')}"
    if event_type == "EXPERIMENT_STOPPED":
        return "WARNING", "Run", f"⏹ 实验被停止"
    if event_type == "HARDWARE_CONNECTED":
        return "SUCCESS", "Run", f"🔌 硬件已连接  port={p.get('port')}"
    if event_type == "HARDWARE_DISCONNECTED":
        return "INFO", "Run", f"🔌 硬件已断开"
    if event_type == "ERROR":
        return "ERROR", "Run", f"❌ 错误  T={_fmt(p.get('temperature_C'), '{:.2f}')}°C  {p.get('message')}"

    # Generic fallback — better than nothing.
    return "INFO", "Run", f"• {event_type}  {json.dumps(p, ensure_ascii=False)[:160]}"


class HardwareAdapter:
    """Adapter between the web API layer and the Stage 0 hardware layer."""

    def __init__(self):
        self._connected = False
        self._simulate = False
        self._running = False
        self._autonomous = False
        self._workflow = None
        self._thread: Optional[threading.Thread] = None
        self._events: List[Dict[str, Any]] = []
        self._current_temperature: Optional[float] = None
        self._target_temperature: Optional[float] = None
        self._measurements: List[Dict[str, Any]] = []
        self._sio_emit: Optional[Callable] = None
        self._sio_loop = None  # captured asyncio loop for thread-safe emits
        self._run_id: Optional[str] = None
        self._sample_id: Optional[str] = None
        self._step_size: float = 5.0
        self._fine_step: float = 1.0
        self._coarse_step: float = 5.0
        self._measurement_mode: str = "COARSE"
        self._phase_detector = None
        self._lock = threading.Lock()
        self._pending_command: Optional[Dict[str, Any]] = None
        # Optional sample geometry recorded at start(); used by Rb fitting when
        # provided, otherwise _do_rb_fitting falls back to its defaults.
        self._thickness_cm: Optional[float] = None
        self._area_cm2: Optional[float] = None
        # --- ESAS-OS 2.0 治理旁路（Phase 1，纯加法 / fail-safe / 默认开）---
        # 在 live 实时回路逐点接 shadow 三重提交 + Rb-ACT 双跑 + measurement_txn 准入,
        # 把原本只在离线脚本里的治理组件真正接到前端驱动的测量链路上。
        # 任何导入/执行失败都只记一条事件,绝不影响测量与入库。
        self._enable_harness: bool = True
        self._harness_recorder = None   # ShadowHarnessRecorder | None(惰性构建于首点)
        self._harness_fns = None        # 治理函数缓存;None=未尝试,False=不可用
        # --- ESAS-OS 2.0 R²-Memory（P2 真实接入 live 回路，纯加法 / fail-safe / 默认开）---
        # 每个真实测量点经写门进 AgentMemory（角色隔离 + 跨域守卫 + 多轮 RoundState），
        # 收尾做决策保持压缩证书。任何失败只记事件，绝不影响测量/入库。
        self._enable_memory: bool = True
        self._agent_memory = None       # AgentMemory | None(惰性构建于首点)
        self._memory_bridge = None      # live_memory_bridge 模块缓存;None=未试,False=不可用
        self._memory_foreign_id = None  # 跨域守卫外域项 id
        # --- ESAS-OS 2.0 C³-Harness（P2 真实接入 shadow，纯加法 / fail-safe / 默认开）---
        # 收集真实 Rb-ACT 计量不确定度(sigma_log10_total, dex) + 主动测量请求,
        # 收尾在 legacy "扫完即停" 之上 shadow 出收敛证书(C³ 只推迟、绝不更早停)。
        self._enable_c3: bool = True
        self._rbact_metro_dex: List[float] = []
        self._rbact_active_requests: List[str] = []
        # --- H4:Rb-ACT R4 激活模式。逐点累积 RbActResult,收尾据三条件门
        #     (rb_r4_activate + 预注册 gates_pass + 人审签核 token)决定是否旁产 σ_v2+delta。
        #     2026-07-05 起 flag 默认开(合同/审计/门检查每次 run 真实执行并落盘);
        #     缺签核 token 恒回退 legacy;legacy 永不覆盖。替换态须你签核。---
        self._rbact_results: List[Any] = []
        self._rb_r4_activate: bool = True
        self._rb_r4_signoff: Optional[str] = None
        # --- Stage3 机理推理链接 live（GPT 迁移发现愿景，fail-safe / 默认开）---
        # 收尾把真实全温区测量构造成 Stage3SeedBundle,真实 LLM 驱动
        # S03→S04→S06→S06b（证据→假设→机理仲裁→设计原则）。2026-07-05 起默认开
        # (创新点须默认真实运作;收尾仅 3-4 次 LLM 调用,无 key 时自动降级只记事件);
        # 失败只记事件,绝不影响测量/入库。
        self._enable_stage3_reasoning: bool = True
        # --- Epistemic OS（GPT 三大原创方向的可计算对象，fail-safe / 默认开 2026-07-05 起）---
        # 收尾对真实全温区 σ(T) 产出:不可辨识性证书(方案一,Fisher λ_min+JS 等价类)、
        # 最小判别实验集(方案三,集合覆盖+编译失败→等价类)、anytime-valid e-process 证伪
        # (方案二,Ville 控 type-I)+ 单位成本证伪价值。纯 numpy/scipy、不调 LLM;失败只记事件。
        self._enable_epistemic: bool = True
        # --- Gap2:可知性驱动内层主动选温(默认开 2026-07-05 起;advisory 纯计算零成本)。
        #     逐点据已测 σ(T) 竞争模型,计算"单位成本期望机制判别价值"最大的下一个温度,
        #     经 ActionGate 留痕后注入决策 prompt(advisory)。不夺用户固定物理阶梯,只提供受控建议。---
        self._enable_active_design: bool = True
        # --- P13-C:active_design 模式。canary=默认(2026-07-05 起,H3 真实执行):经 ActionGate
        #     在用户固定阶梯的**相邻候选间**微调下一 setpoint(硬护栏:不越阶梯包络、
        #     ±canary_max_steps×step 邻域、回温≤15K),越界/被拦即回退固定阶梯;
        #     advisory=仅注入 prompt(可显式降级)。绝不无人值守 enforce 夺权。---
        self._active_design_mode: str = "canary"
        # H3:canary 可执行邻域宽度(单位=固定阶梯 step)。默认 2(原为隐式 1),让 active_design
        #     在更多步产生实质微调;仍守阶梯包络 + 回温≤15K + ActionGate。clamp 到 [1,3]。
        self._canary_max_steps: int = 2
        self._t_start_C: Optional[float] = None   # 阶梯包络(canary 硬护栏用)
        self._t_end_C: Optional[float] = None
        self._last_epistemic_advisory: Optional[Dict[str, Any]] = None
        # --- Gap3/P13-B:多角色 LLM 证伪市场接 live 收尾(真 OpenRouter 调用 / fail-safe / 默认开
        #     2026-07-05 起——收尾 ~9 次 LLM 调用,成本远低于默认开的逐点 agent;无 key 自动降级)。
        #     收尾对真实 σ(T) 跑 Proposer/Falsifier/Auditor(真 LLM)+ Referee 确定性真实数据结算,
        #     严格适当评分更新信誉/资本。---
        self._enable_falsification_market: bool = True
        # --- ESAS-OS 2.0 measurement_txn 真门控（P3，纯加法 / fail-safe / 默认开）---
        # 逐点累积 entered_bo 准入,收尾切 committed/rejected 视图并据此过滤 Stage0 bundle,
        # 让下游 BO 只吃被准入的点(深冷/坏点不污染)。
        self._enable_commit_gate: bool = True
        # --- P13-D:测量提交路径的门控模式(shadow|canary|enforce)。仅作用于**测量提交**
        #     (是否让被拒点进 BO),**绝不门控温控/CHI 物理命令**(安全)。
        #     shadow=只记录裁决、被拒点仍进 BO(legacy 行为);canary/enforce=被拒点真挡出 BO。
        #     默认 enforce=与历史"总是过滤"行为一致(无回归)。---
        self._commit_gate_mode: str = "enforce"
        self._txn_rows: List[Dict[str, Any]] = []
        self._commit_rejected_T_C: List[float] = []
        # --- G-2:真机故障注入(opt-in,默认关)。**只作用于治理层输入**(样品核对/QA),
        #     让真实 measurement_txn 自然判 entered_bo=False → commit gate 挡出 BO;
        #     **绝不触碰温控/CHI 物理命令**(安全)。支持多条(dict 或 list of dict)。---
        self._inject_faults: List[Dict[str, Any]] = []
        self._fault_injections: List[Dict[str, Any]] = []
        # --- H2:在线仪器见证(默认开 2026-07-05 起;纯软件零成本)。每点用真实 CHI 文件 + 温控稳定
        #     + 仪器态经真实 EvidenceTransaction 推 C_P;支持协议/见证级故障注入(ACK_LOSS/
        #     INSTRUMENT_STUCK/FILE_MISSING/FILE_DELAY/SAMPLE_SWAP/CALIBRATION_EXPIRED),
        #     驱动边界软件注入,**绝不触碰样品/温控物理安全**。fail-safe;不改 legacy 入库。---
        self._enable_instrument_witness: bool = True
        self._instrument_witness_rows: List[Dict[str, Any]] = []
        self._protocol_faults: List[Dict[str, Any]] = []
        # CHI automation handle + per-run parameters (set in connect/start).
        self._chi_executor = None
        self._chi_params: Dict[str, Any] = {}
        self._chi_output_dir: Optional[Path] = None
        # Stability params:
        #   * stability_duration   — once within eps, must stay for this many
        #     seconds (with stability_check_interval polling) to count as
        #     stable.  Default 40s mirrors run_online.py.
        #   * stability_eps_C      — |actual - target| considered "at target".
        #   * stability_check_interval — how often to read the temperature
        #     during the post-arrival stability window.
        #   * cooling_timeout      — hard upper bound on the time we wait for
        #     a single temperature point to *arrive* at target (NOT including
        #     the stability window).  Default 30 min, matches run_online.py.
        self._stability_duration: float = 40.0
        self._stability_eps_C: float = 0.5
        self._stability_check_interval: float = 5.0
        self._cooling_timeout_s: float = 1800.0
        self._skip_on_unstable: bool = True  # skip CHI at a point if it never stabilises
        # Background temperature poller (runs whenever hardware is connected,
        # so the UI sees real-time temperature even before a run is started).
        self._poll_thread: Optional[threading.Thread] = None
        self._poll_stop = threading.Event()
        self._poll_interval_s: float = 2.0
        # Auto post-processing parameters (set in start()).
        self._ao_folder: Optional[str] = None
        self._auto_postprocess: bool = True
        self._run_stage1_after_stage0: bool = True
        self._campaign_config: Optional[str] = None
        self._campaign_slug: Optional[str] = None
        self._history_db_path: Optional[str] = None
        self._stage1_output_dir: Optional[str] = None
        self._source_tag: Optional[str] = None
        self._post_thread: Optional[threading.Thread] = None

        # Per-point Agent (LLM phase-transition decision) — mirrors
        # OnlineExperimentWorkflow._call_agent_decision().  Configurable
        # via start() kwargs and from POLOAPI_KEY env var.
        self._enable_agent_decision: bool = True
        self._agent_api_key: Optional[str] = None
        # 默认逐点决策模型:必须是合法 OpenRouter model ID(旧默认 "deepseek-v3.1" 非法,
        # 会导致每点 LLM 调用 400 → 静默回落规则决策,违背"真 LLM 进闭环")。
        self._agent_model: str = "openai/gpt-5.4"
        self._fine_scan_window_C: float = 10.0  # mirror online_workflow default
        self._fine_scan_end_C: Optional[float] = None  # bottom of fine-scan band
        self._fine_trigger_T_C: Optional[float] = None  # 触发细扫时的温度，用于事件
        self._agent_decisions: List[Dict[str, Any]] = []
        # --- ESAS-OS 2.0 ActionGate（P5）：自主 Agent 决策的唯一受控入口 ---
        # 之前 live 逐点 Agent 决策直接改 setpoint/scan_mode,绕过 ActionGate(bypass)。
        # 现在每个自主覆盖动作(FINE_GRAINED_SCAN/ABORT)先过 gate:shadow 行为不变、
        # enforce 下非 allowlist 动作 BLOCKED → 降级为安全默认(线性粗扫)。bypass 应归零。
        self._harness_mode: str = "shadow"   # shadow | canary | enforce(env SCITX_HARNESS_MODE 可覆盖)
        self._action_gate = None
        self._action_gate_bypass_count: int = 0
        self._action_gate_decisions: List[Dict[str, Any]] = []

        # ---- Safety guards (mirrors online_workflow defaults) ----
        # σ < threshold → stop run (sample is dead); Rb > 1e6 Ω → stop;
        # 3 consecutive measurement failures → stop.  Finalize reheat target
        # is critical: leaving the chamber at low temperature damages the
        # hardware.  Default 18°C matches run_online's _finalize_experiment.
        self._min_conductivity_threshold: float = 1e-8
        self._max_rb_ohm: float = 1e6
        self._max_consecutive_failures: int = 3
        self._consecutive_failures: int = 0
        self._finalize_reheat_C: float = 18.0
        # Enhanced stability check (after Agent-driven re-heat).
        # 用户反馈：回温物理上慢得多（半导体 TEC + 大热容样品台），
        # 旧默认 180s + 2× 稳定窗一共才 4 分钟左右，明显不够腔体真正热平衡。
        # 改成 600s（10 min）热惰性 + 3× 稳定窗（≈ 90s hold）。
        # 注意：盲 sleep 之后还会走 _wait_stable_temperature 主动等到位
        # （上限 _cooling_timeout_s = 30 min），所以总预算 ≈ 10 + 30 + 1.5 min。
        self._post_reheat_settle_s: float = 600.0
        self._stability_multiplier_after_reheat: float = 3.0
        # Persisted run-state for resume support.
        self._state_path: Optional[Path] = None
        self._resume_skip_initial_cool: bool = False
        # Global Arrhenius result generated at finalize.
        self._global_arrhenius: Optional[Dict[str, Any]] = None
        # Last incremental Arrhenius (≥5 pts) + overwritten by global finalize for API/UI.
        self._live_arrhenius_snapshot: Optional[Dict[str, Any]] = None

        PhaseDetectorCls = _safe_import_phase_detector()
        if PhaseDetectorCls:
            self._phase_detector = PhaseDetectorCls()

    def set_sio_emit(self, emit_fn: Callable):
        """Register the async SocketIO emit function for real-time pushes.

        Capture the *current* event loop here (this is invoked from the
        FastAPI lifespan startup which runs on the main loop).  Worker
        threads (measurement loop, temperature poller, post-processing)
        cannot call ``asyncio.get_running_loop()`` themselves, so we keep
        the loop reference around and dispatch coroutines onto it via
        ``run_coroutine_threadsafe``.
        """
        self._sio_emit = emit_fn
        import asyncio
        try:
            self._sio_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._sio_loop = None

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "simulate": self._simulate,
            "running": self._running,
            "autonomous": self._autonomous,
            "temperature": self._current_temperature,
            "target_temperature": self._target_temperature,
            "measurement_count": len(self._measurements),
            "run_id": self._run_id,
            "sample_id": self._sample_id,
            "step_size": self._step_size,
            "measurement_mode": self._measurement_mode,
        }

    def connect(self, port: str = "COM3", simulate: bool = False) -> Dict[str, Any]:
        """Open a real connection to the temperature controller (+ verify CHI deps).

        Hard-fails with a descriptive error on import / serial / driver issues.
        We intentionally do NOT silently fall back to simulation here: when the
        user clicks "Connect" on the hardware page, they want a real hardware
        link or a real error — not a synthetic data stream.
        """
        # The 'simulate' flag is kept in the signature for backward compat with
        # older callers / tests, but the UI now only exposes hardware mode.
        self._simulate = bool(simulate)
        if self._simulate:
            self._connected = True
            self._workflow = None
            self._emit_event("HARDWARE_CONNECTED", {"mode": "simulation"})
            return {"ok": True, "mode": "simulation"}

        # 1. Verify Stage0 hardware imports exist (correct path is `controllers`,
        #    plural; the old `controller.integrated_temp_chi_controller` symbol
        #    never existed in this codebase).
        try:
            from stage0_measurement.modules.hardware import TemperatureDriver
        except ImportError as exc:
            return {
                "ok": False,
                "error": (
                    "Failed to import TemperatureDriver from "
                    "stage0_measurement.modules.hardware. "
                    "Check pyserial is installed and the package layout is intact. "
                    f"Original ImportError: {exc}"
                ),
            }

        # 2. Verify CHI automation deps are importable (cv2, pyautogui, PIL).
        try:
            from stage0_measurement.modules.automation import ChiExecutor  # noqa: F401
        except ImportError as exc:
            return {
                "ok": False,
                "error": (
                    "Failed to import ChiExecutor from "
                    "stage0_measurement.modules.automation. "
                    "Likely missing one of: opencv-python, pyautogui, Pillow. "
                    f"Original ImportError: {exc}"
                ),
            }

        # 3. Actually open the serial port.  TemperatureDriver.__init__ calls
        #    _connect() and raises if the COM port is unavailable.
        try:
            self._workflow = TemperatureDriver(port=port)
        except Exception as exc:
            self._workflow = None
            return {
                "ok": False,
                "error": (
                    f"Failed to open temperature controller on {port}: {exc}. "
                    "Check the cable, that the port is not held by another "
                    "process, and that the controller is powered on."
                ),
            }

        # 4. Instantiate ChiExecutor (does not open CHI yet — it only stores
        #    config; CHI is opened lazily on the first execute_measurement).
        try:
            self._chi_executor = ChiExecutor()
        except Exception as exc:
            self._chi_executor = None
            # Roll back the serial port: leaving it half-open is worse than
            # bailing out cleanly.
            try:
                close_fn = getattr(self._workflow, "close", None)
                if callable(close_fn):
                    close_fn()
            except Exception:
                pass
            self._workflow = None
            return {
                "ok": False,
                "error": f"Failed to construct ChiExecutor: {exc}",
            }

        self._connected = True
        self._emit_event("HARDWARE_CONNECTED", {"mode": "real", "port": port})
        # Start polling so the front-end sees a live temperature immediately
        # after connect, without having to start a measurement run.
        self._start_temperature_poller()
        return {"ok": True, "mode": "real", "port": port}

    def disconnect(self) -> Dict[str, Any]:
        self.stop()
        # Order matters: clear _connected FIRST so the poller's while-loop
        # condition fails on its next wake-up; then signal stop and join the
        # thread; only then close the serial port.  Doing it this way avoids a
        # race where the poller is mid-read while we close the port.
        self._connected = False
        self._stop_temperature_poller()
        if self._workflow is not None:
            try:
                close_fn = getattr(self._workflow, "close", None)
                if callable(close_fn):
                    close_fn()
            except Exception:
                pass
        self._workflow = None
        self._current_temperature = None
        self._emit_event("HARDWARE_DISCONNECTED", {})
        return {"ok": True}

    # ---- Background temperature poller ----

    def _start_temperature_poller(self):
        """Start a daemon thread that reads the controller temperature every
        ``self._poll_interval_s`` seconds and pushes ``temperature_update``
        SocketIO events.  Idempotent."""
        if self._poll_thread is not None and self._poll_thread.is_alive():
            return
        self._poll_stop.clear()
        self._poll_thread = threading.Thread(
            target=self._temperature_poll_loop,
            name="hw-temperature-poller",
            daemon=True,
        )
        self._poll_thread.start()

    def _stop_temperature_poller(self):
        self._poll_stop.set()
        thread = self._poll_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        self._poll_thread = None

    def _temperature_poll_loop(self):
        """Polls the TemperatureDriver and emits TEMPERATURE_REACHED events.
        Skips silently when the driver is missing or returns an error."""
        while not self._poll_stop.is_set() and self._connected:
            if self._workflow is None or self._simulate:
                # In simulation mode the measurement loop manages temperature
                # state itself; nothing for us to do here.
                self._poll_stop.wait(self._poll_interval_s)
                continue
            try:
                res = self._workflow.read_temperature()
            except Exception as exc:
                # Don't spam events — only emit on first error transition.
                if self._current_temperature is not None:
                    self._emit_event("TEMPERATURE_READ_FAILED", {"error": str(exc)})
                self._current_temperature = None
                self._poll_stop.wait(self._poll_interval_s)
                continue

            if isinstance(res, dict) and res.get("success"):
                t_now = res.get("temperature")
                if t_now is not None:
                    try:
                        self._current_temperature = float(t_now)
                    except (TypeError, ValueError):
                        self._current_temperature = None
                    if self._current_temperature is not None:
                        # Frontend reads `temperature` or `current` from the
                        # payload (see MainLayout.getCurrentTemp).
                        self._emit_event("TEMPERATURE_REACHED", {
                            "temperature": self._current_temperature,
                            "current": self._current_temperature,
                            "target": self._target_temperature,
                            "target_temperature": self._target_temperature,
                            "source": "poller",
                        })
            self._poll_stop.wait(self._poll_interval_s)

    def start(self, sample_id: str = "unknown", **kwargs) -> Dict[str, Any]:
        sample_id = _validate_path_token(sample_id, "sample_id")
        resolved_ao_folder = _validate_path_token(
            kwargs.get("ao_folder") or self._derive_ao_folder(sample_id),
            "ao_folder",
        )
        explicit_state = kwargs.get("state_path")
        if explicit_state:
            state_path = Path(str(explicit_state))
            if not state_path.is_absolute():
                state_path = RUNS_DIR / state_path
            resolved_state_path = _ensure_within(state_path, RUNS_DIR, "state_path")
        else:
            resolved_state_path = None

        # Resolve campaign storage before marking the adapter as running.  If a
        # slug/path is invalid, start() should fail cleanly and leave the
        # adapter available for the next corrected request.
        with self._lock:
            if not self._connected:
                return {"ok": False, "error": "Not connected"}
            if self._running:
                return {"ok": False, "error": "Already running"}
            runtime = _load_stage1_campaign_runtime(
                campaign_slug=kwargs.get("campaign"),
                campaign_config=kwargs.get("campaign_config"),
                history_db_path=kwargs.get("history_db_path"),
                output_dir=kwargs.get("stage1_output_dir") or kwargs.get("output_dir"),
                source_tag=kwargs.get("source_tag"),
            )
            self._running = True

        self._sample_id = sample_id
        self._measurements.clear()
        self._global_arrhenius = None
        self._live_arrhenius_snapshot = None
        self._events.clear()
        # ESAS-OS 2.0:本次运行是否逐点旁路记录 shadow/Rb-ACT/txn(默认开;
        # enable_harness=False 时完全回到原 legacy 行为)。recorder 惰性构建于首点。
        self._enable_harness = bool(kwargs.get("enable_harness", True))
        self._harness_recorder = None
        # R²-Memory:本次运行是否逐点写入 AgentMemory(默认开;惰性构建于首点)。
        self._enable_memory = bool(kwargs.get("enable_memory", True))
        self._agent_memory = None
        self._memory_foreign_id = None
        # C³-Harness shadow:本次运行是否在收尾 shadow 收敛证书(默认开)。
        self._enable_c3 = bool(kwargs.get("enable_c3", True))
        self._rbact_metro_dex = []
        self._rbact_active_requests = []
        # 创新点默认开(2026-07-05 起):全部 fail-safe,无 key 时 LLM 类自动降级只记事件。
        self._enable_stage3_reasoning = bool(kwargs.get("enable_stage3_reasoning", True))
        self._enable_epistemic = bool(kwargs.get("enable_epistemic", True))
        self._enable_active_design = bool(kwargs.get("enable_active_design", True))
        _adm = str(kwargs.get("active_design_mode", "canary") or "canary").strip().lower()
        self._active_design_mode = _adm if _adm in ("advisory", "canary") else "canary"
        try:
            self._canary_max_steps = max(1, min(3, int(kwargs.get("canary_max_steps", 2))))
        except (TypeError, ValueError):
            self._canary_max_steps = 2
        self._enable_falsification_market = bool(kwargs.get("enable_falsification_market", True))
        # H4:Rb-ACT R4 激活模式(替换态,须三条件齐备才生效;flag 默认开,签核 token 须人给)。
        self._rbact_results = []
        self._rb_r4_activate = bool(kwargs.get("rb_r4_activate", True))
        _so = kwargs.get("rb_r4_signoff")
        self._rb_r4_signoff = str(_so) if _so else None
        # measurement_txn 真门控:本次运行是否切 committed 视图并过滤 bundle(默认开)。
        self._enable_commit_gate = bool(kwargs.get("enable_commit_gate", True))
        _cgm = str(kwargs.get("commit_gate_mode", "enforce") or "enforce").strip().lower()
        self._commit_gate_mode = _cgm if _cgm in ("shadow", "canary", "enforce") else "enforce"
        self._txn_rows = []
        self._commit_rejected_T_C = []
        # G-2:真机故障注入(opt-in)。inject_fault=dict 或 list of dict:
        #   {"type": "SAMPLE_MISMATCH"|"QA_FAIL", "at_step": <int>}。仅治理层,绝不改温控/CHI。
        _inj = kwargs.get("inject_fault")
        _inj_list = _inj if isinstance(_inj, list) else ([_inj] if isinstance(_inj, dict) else [])
        self._inject_faults = [
            {"type": str(d["type"]).upper(), "at_step": int(d.get("at_step", 0))}
            for d in _inj_list
            if isinstance(d, dict) and str(d.get("type", "")).upper() in _INJECTABLE_FAULTS
        ]
        self._fault_injections = []
        # H2:在线仪器见证(默认开 2026-07-05 起)+ 协议级故障注入(inject_fault 里 type∈_PROTOCOL_FAULTS 的条目)。
        self._enable_instrument_witness = bool(kwargs.get("enable_instrument_witness", True))
        self._instrument_witness_rows = []
        self._protocol_faults = [
            {"type": str(d["type"]).upper(), "at_step": int(d.get("at_step", 0))}
            for d in _inj_list
            if isinstance(d, dict) and str(d.get("type", "")).upper() in _PROTOCOL_FAULTS
        ]
        if self._protocol_faults:
            self._enable_instrument_witness = True  # 注了协议故障 → 自动开在线见证

        import uuid
        self._run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        run_dir = RUNS_DIR / self._run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "evidence").mkdir(exist_ok=True)

        t_start = kwargs.get("t_start", 20.0)
        t_end = kwargs.get("t_end", -85.0)
        # 记录阶梯包络(P13-C canary 硬护栏用:下一 setpoint 绝不越 [t_end, t_start])。
        try:
            self._t_start_C = float(t_start)
            self._t_end_C = float(t_end)
        except (TypeError, ValueError):
            self._t_start_C, self._t_end_C = None, None

        # Geometry / CHI / BO provenance — None when not provided.
        geometry = {
            "thickness_m": kwargs.get("thickness_m"),
            "area_m2": kwargs.get("area_m2"),
        }
        # Derive cm-units (Stage0 pipelines often expect cm/cm^2).
        if geometry["thickness_m"] is not None:
            try:
                geometry["thickness_cm"] = float(geometry["thickness_m"]) * 100.0
            except (TypeError, ValueError):
                geometry["thickness_cm"] = None
        if geometry["area_m2"] is not None:
            try:
                geometry["area_cm2"] = float(geometry["area_m2"]) * 1e4
            except (TypeError, ValueError):
                geometry["area_cm2"] = None
        # Cache on adapter so per-point Rb fitting can use real geometry.
        try:
            self._thickness_cm = geometry.get("thickness_cm")
            self._area_cm2 = geometry.get("area_cm2")
        except Exception:
            pass

        chi_settings = {
            "high_freq_Hz": kwargs.get("chi_high_freq_Hz"),
            "low_freq_Hz": kwargs.get("chi_low_freq_Hz"),
            "init_voltage_V": kwargs.get("chi_init_voltage_V"),
            "amplitude_mV": kwargs.get("chi_amplitude_mV"),
        }
        bo_provenance = {
            "R": kwargs.get("R"),
            "N": kwargs.get("N"),
            "campaign": kwargs.get("campaign"),
            "parent_sample_id": kwargs.get("parent_sample_id"),
            "material_note": kwargs.get("material_note"),
        }
        temperature_program = {
            "t_start_C": t_start,
            "t_end_C": t_end,
            "coarse_step_C": kwargs.get("coarse_step", 5.0),
            "fine_step_C": kwargs.get("fine_step", 1.0),
        }

        manifest = {
            "run_id": self._run_id,
            "sample_id": sample_id,
            "status": "running",
            "created_at": datetime.now().isoformat(),
            "mode": "simulation" if self._simulate else "real",
            "temperature_program": temperature_program,
            "geometry": geometry,
            "chi_settings": chi_settings,
            "bo_provenance": bo_provenance,
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # sample_summary.json — durable per-run snapshot consumed by Stage0 / front-end.
        sample_summary = {
            "schema_version": "1.0",
            "sample_id": sample_id,
            "run_id": self._run_id,
            "created_at": datetime.now().isoformat(),
            "mode": "simulation" if self._simulate else "real",
            "temperature_program": temperature_program,
            "geometry": geometry,
            "chi_settings": chi_settings,
            "bo_provenance": bo_provenance,
        }
        try:
            (run_dir / "sample_summary.json").write_text(
                json.dumps(sample_summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            self._emit_event("SAMPLE_SUMMARY_WRITE_FAILED", {"error": str(exc)})

        self._step_size = kwargs.get("step", kwargs.get("coarse_step", 5.0))
        self._coarse_step = self._step_size
        self._fine_step = kwargs.get("fine_step", 1.0)
        self._measurement_mode = "COARSE"

        # Build the CHI parameter template for this run.  Frontend values are
        # numeric; CHI's automation layer expects strings.  Fall back to the
        # stage0_measurement.config defaults when the UI didn't pass a value.
        try:
            from stage0_measurement import config as _stage0_cfg
            default_highf = _stage0_cfg.DEFAULT_CHI_HIGHF
            default_lowf = _stage0_cfg.DEFAULT_CHI_LOWF
            default_initV = _stage0_cfg.DEFAULT_CHI_INITV
            default_chi_data_dir = _stage0_cfg.DEFAULT_CHI_DATA_DIR
            default_template_dir = _stage0_cfg.DEFAULT_CHI_TEMPLATE_DIR
        except Exception:
            default_highf, default_lowf, default_initV = "1000000", "0.1", "0"
            default_chi_data_dir = str(PROJECT_ROOT / "stage0_measurement" / "data" / "chi_measurements")
            default_template_dir = str(PROJECT_ROOT / "stage0_measurement" / "controllers" / "templates")

        def _as_str(v, default):
            if v is None:
                return default
            try:
                # Keep integers integer-looking ('1000000' not '1000000.0').
                fv = float(v)
                if fv.is_integer():
                    return str(int(fv))
                return str(fv)
            except (TypeError, ValueError):
                return str(v)

        # CHI raw output stays in E:\chi_data (the long-standing instrument
        # convention).  Stage0 processing copies/imports from there into
        # data/ao/<sample_id>/ manually.  Allows STAGE0_CHI_DATA_DIR env var
        # override but keeps the bench default at E:\chi_data.
        chi_data_dir = os.environ.get("STAGE0_CHI_DATA_DIR") or r"E:\chi_data"
        try:
            os.makedirs(chi_data_dir, exist_ok=True)
        except Exception:
            # Don't fail start() just because the dir can't be created (e.g.
            # E: drive missing on a dev machine); ChiExecutor will surface
            # the real error if the path is unusable at measure time.
            pass
        chi_raw_dir = Path(chi_data_dir)
        self._chi_output_dir = chi_raw_dir

        self._chi_params = {
            "material": sample_id,
            "highf": _as_str(kwargs.get("chi_high_freq_Hz"), default_highf),
            "lowf": _as_str(kwargs.get("chi_low_freq_Hz"), default_lowf),
            "initV": _as_str(kwargs.get("chi_init_voltage_V"), default_initV),
            "your_position": str(chi_raw_dir),
            "template_dir": default_template_dir,
        }

        # Temperature-stability params (used by _wait_stable_temperature).
        try:
            self._stability_duration = float(kwargs.get("stability_duration", 40.0))
        except (TypeError, ValueError):
            self._stability_duration = 40.0
        try:
            self._stability_eps_C = float(kwargs.get("stability_eps_C", 0.5))
        except (TypeError, ValueError):
            self._stability_eps_C = 0.5
        try:
            self._stability_check_interval = float(kwargs.get("stability_check_interval", 5.0))
        except (TypeError, ValueError):
            self._stability_check_interval = 5.0
        try:
            self._cooling_timeout_s = float(kwargs.get("cooling_timeout", 1800.0))
        except (TypeError, ValueError):
            self._cooling_timeout_s = 1800.0
        self._skip_on_unstable = bool(kwargs.get("skip_on_unstable", True))

        # Auto post-processing — set in start() so we can call it cleanly
        # from _real_measurement_loop after EXPERIMENT_COMPLETED.  Default
        # ao_folder is today's date in YYYY.M.D format (matches data/ao layout
        # in the handoff doc, e.g. "2026.5.11").
        ao_folder = resolved_ao_folder
        self._ao_folder = ao_folder
        self._auto_postprocess = bool(kwargs.get("auto_postprocess", True))
        self._run_stage1_after_stage0 = bool(kwargs.get("run_stage1_after_stage0", True))
        self._campaign_slug = runtime["campaign_slug"]
        self._campaign_config = runtime["campaign_config"]
        self._history_db_path = runtime["history_db_path"]
        self._stage1_output_dir = runtime["output_dir"]
        self._source_tag = runtime["source_tag"]

        # ----- Per-point LLM Agent (phase-transition decision) -----
        self._enable_agent_decision = bool(kwargs.get("enable_agent_decision", True))
        self._agent_api_key = (
            kwargs.get("agent_api_key")
            or os.environ.get("POLOAPI_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or _read_llm_key_from_env_file()
            or None
        )
        self._agent_model = kwargs.get("agent_model") or self._agent_model
        try:
            self._fine_scan_window_C = float(kwargs.get("fine_scan_window_C", 10.0))
        except (TypeError, ValueError):
            self._fine_scan_window_C = 10.0
        self._fine_scan_end_C = None
        self._agent_decisions = []
        # ActionGate:模式 shadow|canary|enforce(显式 kwarg > env SCITX_HARNESS_MODE > shadow)。
        import os as _os
        _hm = (kwargs.get("harness_mode") or _os.environ.get("SCITX_HARNESS_MODE") or "shadow")
        self._harness_mode = str(_hm).strip().lower()
        if self._harness_mode not in ("shadow", "canary", "enforce"):
            self._harness_mode = "shadow"
        self._action_gate = None
        self._action_gate_bypass_count = 0
        self._action_gate_decisions = []
        self._consecutive_failures = 0
        self._global_arrhenius = None
        self._live_arrhenius_snapshot = None

        # ----- Safety / finalize knobs -----
        def _flt(key: str, default: float) -> float:
            try:
                return float(kwargs.get(key, default))
            except (TypeError, ValueError):
                return default
        self._min_conductivity_threshold = _flt("min_conductivity_threshold", 1e-8)
        self._max_rb_ohm = _flt("max_rb_ohm", 1e6)
        try:
            self._max_consecutive_failures = int(kwargs.get("max_consecutive_failures", 3))
        except (TypeError, ValueError):
            self._max_consecutive_failures = 3
        self._finalize_reheat_C = _flt("finalize_reheat_C", 18.0)
        self._post_reheat_settle_s = _flt("post_reheat_settle_s", 600.0)
        self._stability_multiplier_after_reheat = _flt("stability_multiplier_after_reheat", 3.0)

        # ----- Resume / state-persistence -----
        # ``state_path`` defaults to ``runs/<run_id>/online_experiment_state.json``
        # so each run has its own file; pass an explicit one to resume.
        self._state_path = resolved_state_path or (
            RUNS_DIR / (self._run_id or "_default") / "online_experiment_state.json"
        )
        self._resume_skip_initial_cool = bool(kwargs.get("resume", False))
        if self._resume_skip_initial_cool:
            self._load_state_snapshot()

        self._emit_event("AGENT_CONFIG", {
            "enable_agent_decision": self._enable_agent_decision,
            "has_api_key": bool(self._agent_api_key),
            "model": self._agent_model,
            "fine_scan_window_C": self._fine_scan_window_C,
        })

        self._emit_event("EXPERIMENT_STARTED", {
            "sample_id": sample_id,
            "run_id": self._run_id,
            "chi_params": self._chi_params,
            "chi_output_dir": str(chi_raw_dir),
            "campaign": self._campaign_slug,
            "history_db": self._history_db_path,
            "output_dir": self._stage1_output_dir,
        })

        if self._simulate:
            t_start = kwargs.get("t_start", 20.0)
            t_end = kwargs.get("t_end", -85.0)
            self._thread = threading.Thread(
                target=self._simulate_measurement_loop,
                args=(sample_id, t_start, t_end),
                daemon=True,
            )
            self._thread.start()
        else:
            self._thread = threading.Thread(
                target=self._real_measurement_loop,
                args=(sample_id, kwargs),
                daemon=True,
            )
            self._thread.start()

        return {
            "ok": True,
            "sample_id": sample_id,
            "run_id": self._run_id,
            "campaign": self._campaign_slug,
            "history_db": self._history_db_path,
            "output_dir": self._stage1_output_dir,
        }

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            was_running = self._running
            self._running = False
        if was_running:
            self._emit_event("EXPERIMENT_STOPPED", {
                "total_measurements": len(self._measurements),
            })
            self._finalize_run("stopped")
            thread = self._thread
            if thread is not None and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=3.0)
        return {"ok": True}

    def set_temperature(self, target: float) -> Dict[str, Any]:
        self._target_temperature = target
        self._emit_event("TEMPERATURE_SET", {"target": target})
        if self._workflow and not self._simulate:
            try:
                # TemperatureDriver.set_temperature returns a status dict.
                res = self._workflow.set_temperature(target)
                if isinstance(res, dict) and not res.get("success", True):
                    return {"ok": False, "error": res.get("error", "set_temperature failed")}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": True, "target": target}

    def get_temperature(self) -> Dict[str, Any]:
        if self._workflow and not self._simulate:
            try:
                # TemperatureDriver.read_temperature returns a dict.
                res = self._workflow.read_temperature()
                if isinstance(res, dict) and res.get("success"):
                    self._current_temperature = res.get("temperature")
            except Exception:
                pass
        return {"temperature": self._current_temperature, "target": self._target_temperature, "unit": "celsius"}

    def trigger_measurement(self) -> Dict[str, Any]:
        """Trigger a single EIS measurement at current temperature (simulation or real)."""
        if not self._connected:
            return {"ok": False, "error": "Not connected"}
        if self._simulate:
            t = self._current_temperature or 20.0
            result = self._do_simulated_measurement(self._sample_id or "unknown", t, len(self._measurements))
            return {"ok": True, "measurement": result}

        if self._chi_executor is None or not self._chi_params:
            return {
                "ok": False,
                "error": (
                    "CHI not configured: call /api/control/start at least once "
                    "for this run so material/frequency/output_dir are known."
                ),
            }

        t_actual = self._current_temperature if self._current_temperature is not None else 20.0
        # 文件名用设定目标温（与降温档一致）；Rb/记录仍用实测腔温
        t_label = self._target_temperature if self._target_temperature is not None else t_actual
        step_idx = len(self._measurements)
        chi_result = self._trigger_chi_measurement(t_label, step_idx, chamber_actual_C=t_actual)
        if not chi_result.get("success") or chi_result.get("frequencies") is None:
            return {"ok": False, "error": chi_result.get("error", "CHI measurement failed")}
        rb_result = self._do_rb_fitting(
            chi_result["frequencies"], chi_result.get("z_real", []),
            chi_result.get("z_imag", []), t_actual,
        )
        measurement = {
            "sample_id": self._sample_id or "unknown",
            "step_idx": step_idx,
            "temperature_C": round(t_actual, 2),
            "temperature_K": round(t_actual + 273.15, 2),
            "rb_ohm": rb_result.get("rb_ohm"),
            "conductivity_S_cm": rb_result.get("conductivity_S_per_cm"),
            "fit_method": rb_result.get("rb_method", "unknown"),
            "r_squared": rb_result.get("fit_quality"),
            "raw_eis_file": chi_result.get("output_file"),
            "success": rb_result.get("success", False),
            "failure_reason": rb_result.get("failure_reason"),
            "timestamp": datetime.now().isoformat(),
        }
        self._measurements.append(measurement)

        # --- ESAS-OS 2.0 治理旁路（Phase 1，纯加法/fail-safe/默认开）---
        # 单点路径("Measure Now")也逐点接 shadow + Rb-ACT + txn,推 3 个治理事件,
        # 与 _real_measurement_loop 同源。整体失败只记 HARNESS_GOVERNANCE_ERROR,
        # 绝不影响入库与返回。这样前端单点 live 也能在「治理」Tab 看到真实裁决。
        if self._enable_harness and chi_result.get("success") and chi_result.get("frequencies") is not None:
            try:
                self._run_point_governance(
                    step_idx=step_idx,
                    T_C=measurement["temperature_C"],
                    freq=chi_result.get("frequencies"),
                    zr=chi_result.get("z_real"),
                    zi=chi_result.get("z_imag"),
                    eis_result=(rb_result.get("raw") if isinstance(rb_result, dict) else None),
                    rb_result=rb_result,
                )
            except Exception as exc:  # noqa: BLE001
                self._emit_event("HARNESS_GOVERNANCE_ERROR",
                                 {"step_idx": step_idx, "error": str(exc)})

        if self._enable_memory:
            self._run_point_memory(
                step_idx=step_idx,
                T_C=measurement["temperature_C"],
                rb_ohm=measurement.get("rb_ohm"),
                sigma_S_cm=measurement.get("conductivity_S_cm"),
                qc_grade=measurement.get("failure_reason") or ("ok" if measurement.get("success") else "fail"),
                governance_verdict="single_point",
            )

        self._emit_event("MEASUREMENT_COMPLETED", measurement)
        return {"ok": True, "measurement": measurement}

    def enqueue_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Queue an agent command for the measurement loop to consume.

        Supported commands:
        - RE_MEASURE: repeat measurement at current temperature
        - BACKTRACK: go back `backtrack_delta` degrees and re-scan in FINE mode
        - TRIGGER_FINE_SCAN: switch to fine step size
        """
        with self._lock:
            self._pending_command = {"command": command, "params": params or {}}
        self._emit_event("AGENT_COMMAND_QUEUED", {"command": command, "params": params or {}})
        return {"ok": True, "command": command}

    def _consume_command(self) -> Optional[Dict[str, Any]]:
        """Pop the pending command (thread-safe). Returns None if empty."""
        with self._lock:
            cmd = self._pending_command
            self._pending_command = None
        return cmd

    def apply_policy(self, mode: str = None, fine_step: float = None, coarse_step: float = None) -> Dict[str, Any]:
        """Apply measurement policy changes (step size, fine/coarse mode)."""
        if mode:
            self._measurement_mode = mode.upper()
        if fine_step is not None:
            self._fine_step = fine_step
        if coarse_step is not None:
            self._coarse_step = coarse_step

        if self._measurement_mode == "FINE":
            self._step_size = self._fine_step
        else:
            self._step_size = self._coarse_step

        self._emit_event("POLICY_CHANGED", {
            "mode": self._measurement_mode,
            "step_size": self._step_size,
            "fine_step": self._fine_step,
            "coarse_step": self._coarse_step,
        })
        return {"ok": True, "mode": self._measurement_mode, "step_size": self._step_size}

    def get_events(self, since: int = 0) -> List[Dict[str, Any]]:
        return self._events[since:]

    def get_measurements(self) -> List[Dict[str, Any]]:
        return self._measurements

    def get_live_arrhenius_snapshot(self) -> Optional[Dict[str, Any]]:
        """Global-finalize Arrhenius snapshot only (no per-point incremental fit)."""
        return self._live_arrhenius_snapshot

    def get_global_arrhenius(self) -> Optional[Dict[str, Any]]:
        return self._global_arrhenius

    # --- Internal helpers ---

    def _emit_event(self, event_type: str, payload: Dict[str, Any]):
        # Build a human-readable narrative + log level, mirroring the old
        # V1.0 frontend_web `log` events (✅/⚠️/❌ + 中文 + 关键数字).
        level, agent, message = _format_event_narrative(event_type, payload)
        event = {
            "type": event_type,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "seq": len(self._events),
            "level": level,
            "agent": agent,
            "message": message,
            "payload": payload,
        }
        self._events.append(event)

        if self._run_id:
            events_file = RUNS_DIR / self._run_id / "events.jsonl"
            try:
                with open(events_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception:
                pass

        if self._sio_emit:
            try:
                sio_event_map = {
                    "TEMPERATURE_REACHED": "temperature_update",
                    "TEMPERATURE_SET": "temperature_update",
                    "MEASUREMENT_COMPLETED": "measurement_complete",
                    "MEASUREMENT_SKIPPED": "thought_chain_event",
                    "PHASE_TRANSITION_DETECTED": "phase_transition",
                    "EXPERIMENT_STARTED": "status_change",
                    "EXPERIMENT_STOPPED": "status_change",
                    "EXPERIMENT_COMPLETED": "status_change",
                    "HARDWARE_CONNECTED": "status_change",
                    "HARDWARE_DISCONNECTED": "status_change",
                    "RB_FIT_COMPLETED": "measurement_complete",
                    "ARRHENIUS_UPDATED": "thought_chain_event",
                    "POLICY_CHANGED": "status_change",
                    # Thought-chain visibility: surface the wait/measure stages
                    # so the cockpit's chain panel is not silent.
                    "SET_T": "thought_chain_event",
                    "WAIT_STABLE_ARRIVAL_START": "thought_chain_event",
                    "WAIT_STABLE_ARRIVED": "thought_chain_event",
                    "WAIT_STABLE_TIMEOUT": "thought_chain_event",
                    "WAIT_STABLE_DRIFT": "thought_chain_event",
                    "WAIT_STABLE": "thought_chain_event",
                    "EIS_RUN": "thought_chain_event",
                    "CHI_MEASUREMENT_STARTED": "thought_chain_event",
                    "CHI_MEASUREMENT_COMPLETED": "thought_chain_event",
                    "CHI_MEASUREMENT_FAILED": "thought_chain_event",
                    # Post-processing pipeline progress (Stage0 + Stage1).
                    "POST_PROCESSING_STARTED": "thought_chain_event",
                    "POST_PROCESSING_COPY_DONE": "thought_chain_event",
                    "STAGE0_STARTED": "thought_chain_event",
                    "STAGE0_COMPLETED": "thought_chain_event",
                    "STAGE0_FAILED": "thought_chain_event",
                    "CLOSURE_REPORT_STARTED": "thought_chain_event",
                    "CLOSURE_REPORT_COMPLETED": "thought_chain_event",
                    "CLOSURE_REPORT_FAILED": "thought_chain_event",
                    "STAGE1_STARTED": "thought_chain_event",
                    "STAGE1_SKIPPED": "thought_chain_event",
                    "STAGE1_COMPLETED": "thought_chain_event",
                    "STAGE1_FAILED": "thought_chain_event",
                    "POST_PROCESSING_COMPLETED": "thought_chain_event",
                    "POST_PROCESSING_FAILED": "thought_chain_event",
                    # Per-point Agent (LLM phase decision) visibility.
                    "AGENT_CONFIG": "thought_chain_event",
                    "AGENT_CALL_STARTED": "thought_chain_event",
                    "AGENT_DECISION": "thought_chain_event",
                    "AGENT_DECISION_FAILED": "thought_chain_event",
                    "AGENT_FINE_SCAN": "thought_chain_event",
                    "AGENT_FINE_BAND_TICK": "thought_chain_event",
                    "AGENT_FINE_BAND_EXIT": "thought_chain_event",
                    "AGENT_ABORT": "thought_chain_event",
                    "AGENT_UNAVAILABLE": "thought_chain_event",
                    "AGENT_RE_MEASURE": "thought_chain_event",
                    "AGENT_BACKTRACK": "thought_chain_event",
                    # Resume / state snapshots
                    "RESUME_LOADED": "thought_chain_event",
                    "RESUME_SKIPPED": "thought_chain_event",
                    # Safety guards
                    "SAFETY_CONDUCTIVITY_FUSE": "thought_chain_event",
                    "SAFETY_RB_FUSE": "thought_chain_event",
                    "SAFETY_CONSECUTIVE_FAIL_FUSE": "thought_chain_event",
                    # Start-of-run cool to T_start
                    "COOL_TO_START_STARTED": "thought_chain_event",
                    "COOL_TO_START_DONE": "thought_chain_event",
                    "COOL_TO_START_FAILED": "thought_chain_event",
                    # Finalize (reheat + global Arrhenius + manifest)
                    "FINALIZE_REHEAT_STARTED": "thought_chain_event",
                    "FINALIZE_REHEAT_DONE": "thought_chain_event",
                    "FINALIZE_REHEAT_FAILED": "thought_chain_event",
                    "FINALIZE_REHEAT_SKIPPED": "thought_chain_event",
                    "STAGE0_GLOBAL_ARRHENIUS_STARTED": "thought_chain_event",
                    "STAGE0_GLOBAL_ARRHENIUS_COMPLETED": "thought_chain_event",
                    "STAGE0_GLOBAL_ARRHENIUS_FAILED": "thought_chain_event",
                    "STAGE0_GLOBAL_ARRHENIUS_SKIPPED": "thought_chain_event",
                    "RUN_MANIFEST_WRITTEN": "thought_chain_event",
                    "RUN_MANIFEST_FAILED": "thought_chain_event",
                    # Post-reheat enhanced stability
                    "REHEAT_SETTLE_STARTED": "thought_chain_event",
                    "REHEAT_SETTLE_DONE": "thought_chain_event",
                }
                sio_name = sio_event_map.get(event_type)
                import asyncio
                merged_payload = {**event, **payload}
                loop = self._sio_loop
                if loop is None:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None

                # Decide which socket channels to dispatch on.  Every
                # meaningful event ALSO goes to ``thought_chain_event`` so the
                # cockpit's chain panel and Raw Log see the full narrative
                # (with our human-readable ``message`` / ``level`` / ``agent``
                # fields).  Without this mirror the chain only sees a
                # handful of event types and the rest stays invisible —
                # which is what made every row look the same.
                channels = []
                if sio_name:
                    channels.append(sio_name)
                # High-frequency channels we don't want to spam the chain with.
                _CHAIN_SKIP = {
                    "TEMPERATURE_REACHED", "TEMPERATURE_SET",
                }
                if event_type not in _CHAIN_SKIP and "thought_chain_event" not in channels:
                    channels.append("thought_chain_event")

                if loop is not None and loop.is_running():
                    for ch in channels:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                self._sio_emit(ch, merged_payload),
                                loop,
                            )
                        except Exception as exc:  # noqa: BLE001
                            print(f"[hardware_adapter] sio emit dispatch failed: {exc}")
                else:
                    print(
                        f"[hardware_adapter] sio emit dropped (no loop): "
                        f"event={event_type} channels={channels}"
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"[hardware_adapter] sio emit error: {exc}")

    def _save_evidence(self, step_idx: int, evidence: Dict[str, Any]):
        """Save an evidence package to the run's evidence directory."""
        if not self._run_id:
            return
        evidence_dir = RUNS_DIR / self._run_id / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        fname = f"EP-{self._sample_id or 'unknown'}-{step_idx:04d}.json"
        try:
            (evidence_dir / fname).write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _finalize_run(self, status: str):
        if not self._run_id:
            return
        manifest_file = RUNS_DIR / self._run_id / "manifest.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                manifest["status"] = status
                manifest["finished_at"] = datetime.now().isoformat()
                manifest["total_measurements"] = len(self._measurements)
                manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            except Exception:
                pass

    # ----------------------------------------------------------------
    # Resume / state snapshot
    # ----------------------------------------------------------------

    def _save_state_snapshot(self) -> None:
        """Persist a minimal run-state snapshot to ``self._state_path``.

        Stores everything required to resume after a crash / power-cycle:
        sample_id, run_id, current cooling target/step, scan mode, all
        measurements collected so far, all Agent decisions, and which
        fine-scan band (if any) is active.  Mirrors what
        ``OnlineExperimentWorkflow.persist_checkpoint`` writes.
        """
        if not self._state_path:
            return
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot = {
                "schema_version": 1,
                "saved_at": datetime.now().isoformat(),
                "sample_id": self._sample_id,
                "run_id": self._run_id,
                "current_temperature_C": self._current_temperature,
                "target_temperature_C": self._target_temperature,
                "step_size_C": self._step_size,
                "fine_step_C": self._fine_step,
                "coarse_step_C": self._coarse_step,
                "scan_mode": self._measurement_mode,
                "fine_scan_end_C": self._fine_scan_end_C,
                "measurements": self._measurements,
                "agent_decisions": self._agent_decisions,
                "consecutive_failures": self._consecutive_failures,
            }
            tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
            tmp_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            tmp_path.replace(self._state_path)
        except Exception as exc:  # noqa: BLE001
            print(f"[hardware_adapter] state snapshot save failed: {exc}")

    def _load_state_snapshot(self) -> None:
        """Load the snapshot referenced by ``self._state_path`` (if any).

        Populates measurements / decisions / scan mode so the loop can
        pick up where it left off.  Silent no-op if file is missing or
        invalid — we'd rather start a fresh run than crash.
        """
        if not self._state_path or not self._state_path.exists():
            self._emit_event("RESUME_SKIPPED", {
                "reason": "no_state_file",
                "state_path": str(self._state_path) if self._state_path else None,
            })
            return
        try:
            snapshot = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            self._emit_event("RESUME_SKIPPED", {
                "reason": f"state_load_failed: {exc}",
                "state_path": str(self._state_path),
            })
            return

        self._measurements = list(snapshot.get("measurements") or [])
        self._agent_decisions = list(snapshot.get("agent_decisions") or [])
        self._consecutive_failures = int(snapshot.get("consecutive_failures") or 0)
        self._fine_scan_end_C = snapshot.get("fine_scan_end_C")
        mode = snapshot.get("scan_mode")
        if isinstance(mode, str):
            self._measurement_mode = mode.upper()
        try:
            if snapshot.get("step_size_C") is not None:
                self._step_size = float(snapshot["step_size_C"])
        except (TypeError, ValueError):
            pass
        self._emit_event("RESUME_LOADED", {
            "state_path": str(self._state_path),
            "n_measurements": len(self._measurements),
            "n_agent_decisions": len(self._agent_decisions),
            "scan_mode": self._measurement_mode,
        })

    # ----------------------------------------------------------------
    # Finalize: reheat + global Arrhenius + manifest
    # ----------------------------------------------------------------

    def _finalize_reheat(self, target_C: Optional[float] = None) -> None:
        """Drive the chamber back to a safe room-temperature setpoint.

        CRITICAL: leaving the controller at deep-sub-zero damages the
        hardware.  This is invoked from EVERY exit path of the
        measurement loop (success / abort / exception / stop).
        """
        if target_C is None:
            target_C = self._finalize_reheat_C
        try:
            if self._workflow and not self._simulate:
                self._emit_event("FINALIZE_REHEAT_STARTED", {"target_C": target_C})
                res = self._workflow.set_temperature(target_C)
                ok = isinstance(res, dict) and res.get("success", True)
                self._emit_event("FINALIZE_REHEAT_DONE" if ok else "FINALIZE_REHEAT_FAILED", {
                    "target_C": target_C,
                    "driver_response": res if isinstance(res, dict) else None,
                })
            else:
                self._emit_event("FINALIZE_REHEAT_SKIPPED", {
                    "target_C": target_C,
                    "reason": "no_workflow_or_simulate",
                })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("FINALIZE_REHEAT_FAILED", {
                "target_C": target_C,
                "error": str(exc),
            })

    def _run_global_arrhenius(self) -> Optional[Dict[str, Any]]:
        """Run the offline competitive-Arrhenius analysis on the full set.

        Same call as ``OnlineExperimentWorkflow._finalize_experiment``:
        feeds successful (T, σ) pairs into ``analyze_arrhenius_series``,
        emits STAGE0 events, and stores result on ``self._global_arrhenius``.
        """
        if len(self._measurements) < 5:
            self._emit_event("STAGE0_GLOBAL_ARRHENIUS_SKIPPED", {
                "reason": "insufficient_points",
                "n_points": len(self._measurements),
            })
            return None
        try:
            from stage0_measurement.modules.analysis.algorithms.arrhenius import (
                analyze_arrhenius_series,
            )
        except Exception as exc:  # noqa: BLE001
            self._emit_event("STAGE0_GLOBAL_ARRHENIUS_FAILED", {
                "error": f"import_failed: {exc}",
            })
            return None
        records = []
        for m in self._measurements:
            sigma = m.get("conductivity_S_cm")
            T_K = m.get("temperature_K")
            if T_K is None and m.get("temperature_C") is not None:
                T_K = m["temperature_C"] + 273.15
            if sigma is None or T_K is None or not (sigma > 0):
                continue
            records.append({
                "success": True,
                "temperature_K": T_K,
                "conductivity_s_per_cm": sigma,
            })
        if len(records) < 5:
            self._emit_event("STAGE0_GLOBAL_ARRHENIUS_SKIPPED", {
                "reason": "insufficient_valid_points",
                "n_valid": len(records),
            })
            return None
        try:
            self._emit_event("STAGE0_GLOBAL_ARRHENIUS_STARTED", {
                "n_valid": len(records),
            })
            result = analyze_arrhenius_series(
                records,
                min_points=5,
                min_segment_points=4,
                aic_improvement_threshold=5.0,
            )
        except Exception as exc:  # noqa: BLE001
            self._emit_event("STAGE0_GLOBAL_ARRHENIUS_FAILED", {"error": str(exc)})
            return None
        self._global_arrhenius = result
        if isinstance(result, dict) and result.get("success"):
            self._record_live_arrhenius_snapshot(result, source="global_finalize", step_idx=None)
        self._emit_event("STAGE0_GLOBAL_ARRHENIUS_COMPLETED", {
            "best_model_type": result.get("best_model_type") if isinstance(result, dict) else None,
            "n_segments": result.get("n_segments") if isinstance(result, dict) else None,
            "transition_temps_K": result.get("transition_temps_K") if isinstance(result, dict) else None,
            "confidence": result.get("confidence") if isinstance(result, dict) else None,
            "success": bool(isinstance(result, dict) and result.get("success")),
        })
        return result

    def _write_run_manifest(self, status: str, error: Optional[str] = None) -> None:
        """Write a top-level manifest summarising the run (parallel to the
        per-run runs/<run_id>/manifest.json that already exists).

        Mirrors run_online.py's ``write_run_manifest`` semantics but stays
        inside the run directory rather than the project root.
        """
        if not self._run_id:
            return
        try:
            manifest_path = RUNS_DIR / self._run_id / "online_run_manifest.json"
            phase_prompt_sha = None
            try:
                from stage0_measurement.modules.analysis.phase_detect import (
                    get_system_prompt_sha256,
                )
                phase_prompt_sha = get_system_prompt_sha256()
            except Exception:  # noqa: BLE001
                pass
            manifest = {
                "mode": "online_web",
                "sample_id": self._sample_id,
                "run_id": self._run_id,
                "status": status,
                "error": error,
                "finished_at": datetime.now().isoformat(),
                "n_measurements": len(self._measurements),
                "n_agent_decisions": len(self._agent_decisions),
                "thickness_cm": self._thickness_cm,
                "area_cm2": self._area_cm2,
                "chi_params": self._chi_params,
                "stability_params": {
                    "duration_s": self._stability_duration,
                    "eps_C": self._stability_eps_C,
                    "check_interval_s": self._stability_check_interval,
                    "cooling_timeout_s": self._cooling_timeout_s,
                },
                "safety_thresholds": {
                    "min_conductivity_S_cm": self._min_conductivity_threshold,
                    "max_rb_ohm": self._max_rb_ohm,
                    "max_consecutive_failures": self._max_consecutive_failures,
                },
                "agent": {
                    "enabled": self._enable_agent_decision,
                    "model": self._agent_model,
                    "has_api_key": bool(self._agent_api_key),
                    "phase_prompt_sha256": phase_prompt_sha,
                    "fine_scan_window_C": self._fine_scan_window_C,
                },
                "global_arrhenius": self._global_arrhenius,
                "state_path": str(self._state_path) if self._state_path else None,
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            self._emit_event("RUN_MANIFEST_WRITTEN", {"path": str(manifest_path)})
        except Exception as exc:  # noqa: BLE001
            self._emit_event("RUN_MANIFEST_FAILED", {"error": str(exc)})

    def _enhanced_wait_after_reheat(self, target: float, step_idx: int) -> Dict[str, Any]:
        """After Agent-driven re-heating, wait for thermal inertia to settle
        (long pause + stricter stability check) before the next CHI run.

        Mirrors OnlineExperimentWorkflow.`_wait_for_stable_enhanced`.
        """
        self._emit_event("REHEAT_SETTLE_STARTED", {
            "target_temperature_C": target,
            "settle_seconds": self._post_reheat_settle_s,
            "stability_multiplier": self._stability_multiplier_after_reheat,
            "step_idx": step_idx,
        })
        # Crude but adequate: just sleep the thermal-inertia window.
        slept = 0.0
        chunk = 5.0
        while self._running and slept < self._post_reheat_settle_s:
            time.sleep(min(chunk, self._post_reheat_settle_s - slept))
            slept += chunk
        if not self._running:
            return {"stable": False, "reason": "run_stopped",
                    "actual_temperature_C": self._current_temperature or target,
                    "target_temperature_C": target,
                    "arrival_seconds": 0.0, "hold_seconds": 0.0}
        # Now run a stricter stability check by temporarily lengthening
        # ``stability_duration`` by ``stability_multiplier_after_reheat``.
        orig_duration = self._stability_duration
        try:
            self._stability_duration = orig_duration * max(self._stability_multiplier_after_reheat, 1.0)
            self._emit_event("REHEAT_SETTLE_DONE", {
                "target_temperature_C": target,
                "extended_stability_duration_s": self._stability_duration,
                "step_idx": step_idx,
            })
            return self._wait_stable_temperature(target, step_idx)
        finally:
            self._stability_duration = orig_duration

    def _do_rb_fitting(self, frequencies, z_real, z_imag, temperature_C, thickness=None, area=None):
        """Call the real Stage0 single-point pipeline (QA + KK + Rb + DRT).

        Returns a dict normalized to the keys the rest of the adapter expects:
        ``success``, ``rb_ohm``, ``conductivity_S_per_cm``, ``rb_method``,
        ``fit_quality``, ``failure_reason``.
        """
        import numpy as np

        if thickness is None:
            thickness = self._thickness_cm if self._thickness_cm is not None else 0.1
        if area is None:
            area = self._area_cm2 if self._area_cm2 is not None else 1.96

        analyze = _safe_import_point_pipeline()
        if analyze is None:
            return {"success": False, "failure_reason": "eis_pipeline.analyze_eis_point not available"}

        try:
            raw = analyze(
                np.asarray(frequencies, dtype=float),
                np.asarray(z_real, dtype=float),
                np.asarray(z_imag, dtype=float),
                temperature_C=float(temperature_C),
                thickness_cm=float(thickness),
                area_cm2=float(area),
                run_rb=True,
                run_quality=True,
                run_kk=True,
            )
        except Exception as exc:
            return {"success": False, "failure_reason": f"analyze_eis_point raised: {exc}"}

        rb_block = (raw or {}).get("rb_result") or {}
        success = bool(raw and raw.get("success") and rb_block.get("rb_ohm") is not None)
        return {
            "success": success,
            "status": (raw or {}).get("status"),
            "rb_ohm": rb_block.get("rb_ohm"),
            "conductivity_S_per_cm": rb_block.get("conductivity_s_per_cm"),
            "rb_method": rb_block.get("method") or rb_block.get("rb_method"),
            "fit_quality": rb_block.get("fit_quality") or rb_block.get("r_squared"),
            "kk_warning": bool((raw or {}).get("kk_warning")),
            "failure_reason": (
                (raw or {}).get("error")
                or (rb_block.get("error") if isinstance(rb_block, dict) else None)
                or (None if success else "rb_fit_failed")
            ),
            "raw": raw,
        }

    def _record_live_arrhenius_snapshot(
        self,
        arr_result: Dict[str, Any],
        *,
        source: str,
        step_idx: Optional[int] = None,
    ) -> None:
        """Keep the latest successful Arrhenius fit for the Analysis page (GET /data/arrhenius/realtime)."""
        if not isinstance(arr_result, dict) or not arr_result.get("success"):
            return
        self._live_arrhenius_snapshot = {
            "success": True,
            "source": source,
            "updated_at_step": step_idx,
            "n_segments": arr_result.get("n_segments", 1),
            "segments": arr_result.get("segments") or [],
            "transition_temps_K": arr_result.get("transition_temps_K") or [],
            "confidence": arr_result.get("confidence"),
            "best_model_type": arr_result.get("best_model_type"),
            "n_points_used": arr_result.get("n_points_used"),
        }

    def _do_simulated_measurement(self, sample_id: str, t: float, step_idx: int) -> Dict:
        """Run a single simulated measurement with REAL analysis if available."""
        self._current_temperature = t
        self._target_temperature = t

        self._emit_event("SET_T", {
            "target_temperature_C": t,
            "step_idx": step_idx,
            "delta_T": self._step_size,
        })

        self._emit_event("WAIT_STABLE", {
            "actual_temperature_C": t + random.uniform(-0.3, 0.3),
            "target_temperature_C": t,
            "stable": True,
        })

        n_freq = 60
        freq = [10 ** (i * 6.0 / (n_freq - 1)) for i in range(n_freq)]
        rb_true = 50.0 + abs(t - 20) * 8 + (abs(t) ** 1.5 if t < -30 else 0)
        rb_true *= random.uniform(0.94, 1.06)
        z_real = [rb_true + rb_true * 0.5 / (1 + (f / 1e4) ** 2) + random.gauss(0, rb_true * 0.01) for f in freq]
        z_imag = [-rb_true * 0.5 * (f / 1e4) / (1 + (f / 1e4) ** 2) + random.gauss(0, rb_true * 0.01) for f in freq]

        rb_result = self._do_rb_fitting(freq, z_real, z_imag, t)

        if rb_result.get("success"):
            rb_ohm = rb_result.get("rb_ohm", rb_true)
            conductivity = rb_result.get("conductivity_S_per_cm", 0.12 / (rb_true * 3.92))
            fit_method = rb_result.get("rb_method", "semicircle")
            r2 = rb_result.get("fit_quality", 0.995)
        else:
            rb_ohm = round(rb_true, 2)
            conductivity = round(0.12 / (rb_true * 3.92), 10) if rb_true > 0 else 0
            fit_method = "semicircle" if t > -40 else "x_intercept"
            r2 = random.uniform(0.993, 0.999) if t > -60 else random.uniform(0.980, 0.995)

        qc_grade = "A" if r2 > 0.997 else ("B" if r2 > 0.993 else ("C" if r2 > 0.98 else "D"))

        measurement = {
            "sample_id": sample_id,
            "step_idx": step_idx,
            "temperature_C": round(t, 2),
            "temperature_K": round(t + 273.15, 2),
            "rb_ohm": round(float(rb_ohm), 4),
            "conductivity_S_cm": round(float(conductivity), 10),
            "fit_method": fit_method,
            "r_squared": round(float(r2), 4),
            "qc_grade": qc_grade,
            "timestamp": datetime.now().isoformat(),
        }
        self._measurements.append(measurement)

        self._emit_event("Rb_FIT", {
            "step_idx": step_idx,
            "rb_ohm": measurement["rb_ohm"],
            "rb_method": fit_method,
            "r_squared": measurement["r_squared"],
            "conductivity_S_cm": measurement["conductivity_S_cm"],
            "temperature_C": measurement["temperature_C"],
        })

        self._emit_event("QC_GRADE", {
            "step_idx": step_idx,
            "qc_grade": qc_grade,
            "r_squared": measurement["r_squared"],
            "critic_grade": qc_grade,
        })

        self._emit_event("MEASUREMENT_COMPLETED", measurement)

        evidence = {
            "evidence_id": f"EP-{sample_id}-{step_idx:04d}",
            "evidence_type": "measurement",
            "step_idx": step_idx,
            "sample_id": sample_id,
            "timestamp": measurement["timestamp"],
            "payload": measurement,
        }
        self._save_evidence(step_idx, evidence)
        self._emit_event("EVIDENCE_PACKAGE_SAVED", {"evidence_id": evidence["evidence_id"], "step_idx": step_idx})

        if self._phase_detector:
            try:
                is_phase = self._phase_detector.add_point(measurement)
                if is_phase:
                    self._emit_event("PHASE_TRANSITION_DETECTED", {
                        "temperature_C": t,
                        "temperature_K": round(t + 273.15, 2),
                        "criteria": "phase_detector",
                    })
                    self.apply_policy(mode="FINE")
            except Exception:
                pass

        # 不在测量循环中跑分段 Arrhenius（不准且误导）；仅 _run_global_arrhenius 结束后拟合并写快照。

        return measurement

    def _simulate_measurement_loop(self, sample_id: str, t_start: float = 20.0, t_end: float = -85.0):
        """Simulate a cooling measurement loop using real analysis modules.

        After each measurement the loop checks for pending agent commands:
        - RE_MEASURE  → repeat at the same temperature
        - BACKTRACK   → jump back by backtrack_delta (default 10°C) and switch to FINE
        - TRIGGER_FINE_SCAN → switch step size to fine without changing temperature
        """
        t = t_start
        step_idx = 0
        backtrack_default_delta = 10.0

        while self._running and t >= t_end:
            self._do_simulated_measurement(sample_id, t, step_idx)
            time.sleep(0.8)
            step_idx += 1

            cmd = self._consume_command()
            if cmd:
                action = cmd["command"]
                params = cmd.get("params", {})

                if action == "RE_MEASURE":
                    self._emit_event("AGENT_RE_MEASURE", {"temperature_C": t, "step_idx": step_idx})
                    continue

                if action == "BACKTRACK":
                    delta = params.get("backtrack_delta", backtrack_default_delta)
                    t = min(t + delta, t_start)
                    self.apply_policy(mode="FINE")
                    self._emit_event("AGENT_BACKTRACK", {
                        "new_temperature_C": t,
                        "delta": delta,
                        "mode": "FINE",
                    })
                    continue

                if action == "TRIGGER_FINE_SCAN":
                    self.apply_policy(mode="FINE")
                    self._emit_event("AGENT_FINE_SCAN", {"temperature_C": t})

            t -= self._step_size

        self._running = False
        self._emit_event("EXPERIMENT_COMPLETED", {
            "sample_id": sample_id,
            "total_measurements": len(self._measurements),
        })
        self._finalize_run("completed")

    # ============================================================
    # Auto post-processing pipeline (Stage0 + Stage1)
    # ============================================================

    @staticmethod
    def _derive_ao_folder(sample_id: str) -> str:
        """Derive ``data/ao/<name>/`` used for CHI copy + Stage0.

        Uses ``{YYYY.M.D}__{sanitized_sample_id}`` so **multiple samples on the
        same calendar day** never share one folder (avoids clobbering
        ``材料制备.txt`` and mixed Stage0 bundles).  If ``sample_id`` embeds a
        date (e.g. ``ATA-2026-5-11-...``), that date becomes the prefix;
        otherwise today's date is used.
        """
        import re
        sid = (sample_id or "").strip() or "unknown"
        m = re.search(r"(\d{4})[-.](\d{1,2})[-.](\d{1,2})", sid)
        if m:
            date_key = f"{m.group(1)}.{int(m.group(2))}.{int(m.group(3))}"
        else:
            now = datetime.now()
            date_key = f"{now.year}.{now.month}.{now.day}"
        slug = re.sub(r'[<>:"/\\|?*\s]+', "_", sid)
        slug = slug.strip("._") or "unknown"
        if len(slug) > 120:
            slug = slug[:120]
        return f"{date_key}__{slug}"

    def run_post_processing(
        self,
        sample_id: Optional[str] = None,
        ao_folder: Optional[str] = None,
        campaign_config: Optional[str] = None,
        history_db_path: Optional[str] = None,
        source_tag: Optional[str] = None,
        stage1_output_dir: Optional[str] = None,
        async_run: bool = False,
        run_stage1: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Run the full Stage0 + Stage1 pipeline for a finished experiment.

        Steps:
        1. Copy ``E:\\chi_data\\<sample_id>*_T*.txt`` -> ``data/ao/<ao_folder>/``
        2. Copy ``E:\\chi_data\\材料制备.txt`` (or ``<sample_id>_材料制备.txt``) -> same dir
        3. Run ``process_ao_stage0.py`` → bundle under ``output/ao_stage0_results/<ao_folder>/``
        4. Generate **Closure** (single-sample LLM summary; independent of Stage1 BO)
        5. Optionally run ``run_optimization_loop.py`` (Stage1) when ``run_stage1`` is True

        Emits ``POST_PROCESSING_*``, ``STAGE0_*``, ``CLOSURE_REPORT_*``, and ``STAGE1_*``
        events so the front-end can render progress. Returns the final summary dict
        (or a stub with the thread handle when ``async_run``).
        """
        sample_id = _validate_path_token(sample_id or self._sample_id or "unknown", "sample_id")
        ao_folder = _validate_path_token(
            ao_folder or self._ao_folder or self._derive_ao_folder(sample_id),
            "ao_folder",
        )
        runtime = _load_stage1_campaign_runtime(
            campaign_slug=self._campaign_slug,
            campaign_config=campaign_config or self._campaign_config,
            history_db_path=history_db_path or self._history_db_path,
            output_dir=stage1_output_dir or self._stage1_output_dir,
            source_tag=source_tag or self._source_tag,
        )
        campaign_config = runtime["campaign_config"]
        history_db_path = runtime["history_db_path"]
        stage1_output_dir = runtime["output_dir"]
        source_tag = runtime["source_tag"]
        rs1 = self._run_stage1_after_stage0 if run_stage1 is None else bool(run_stage1)

        if async_run:
            if self._post_thread is not None and self._post_thread.is_alive():
                return {"ok": False, "error": "Post-processing already running"}
            self._post_thread = threading.Thread(
                target=self._run_post_processing_sync,
                args=(
                    sample_id,
                    ao_folder,
                    campaign_config,
                    history_db_path,
                    stage1_output_dir,
                    source_tag,
                    rs1,
                ),
                name="hw-postprocess",
                daemon=True,
            )
            self._post_thread.start()
            return {
                "ok": True,
                "started": True,
                "sample_id": sample_id,
                "ao_folder": ao_folder,
                "history_db": history_db_path,
                "output_dir": stage1_output_dir,
            }

        return self._run_post_processing_sync(
            sample_id, ao_folder, campaign_config, history_db_path, stage1_output_dir, source_tag, rs1,
        )

    def _apply_commit_gate_to_bundle(self, stage0_results_dir: Path) -> Optional[Dict[str, Any]]:
        """P3 真门控:用 commit_gate 据 rejected 温度过滤 bundle 的 eis_points。
        原 bundle 备份为 .full.json,门控后写回原路径供 Stage1 消费。fail-safe。"""
        bundle_path = stage0_results_dir / "stage0_result_bundle.json"
        if not bundle_path.exists():
            return None
        try:
            import sys as _sys
            p = str(PROJECT_ROOT / "stage1_optimization")
            if p not in _sys.path:
                _sys.path.insert(0, p)
            from scientific_harness.commit_gate import filter_bundle_eis_points
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            res = filter_bundle_eis_points(bundle, self._commit_rejected_T_C)
            if res["n_dropped"] > 0:
                backup = stage0_results_dir / "stage0_result_bundle.full.json"
                if not backup.exists():
                    backup.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
                bundle_path.write_text(json.dumps(res["bundle"], ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("COMMIT_GATE_BUNDLE", {
                "n_before": res["n_before"], "n_after": res["n_after"],
                "n_dropped": res["n_dropped"], "dropped_T_C": res["dropped_T_C"],
            })
            return {"n_before": res["n_before"], "n_after": res["n_after"],
                    "n_dropped": res["n_dropped"], "dropped_T_C": res["dropped_T_C"]}
        except Exception as exc:  # noqa: BLE001
            self._emit_event("COMMIT_GATE_ERROR", {"stage": "bundle", "error": str(exc)})
            return None

    def _write_rbact_noise_for_stage1(self, stage0_results_dir: Path) -> None:
        """P4 Rb-ACT R3:把本配方真实 Rb-ACT 计量不确定度(median/max dex)写到 bundle 目录旁,
        供 run_optimization_loop 摄取为 objective_variance(噪声感知 GP train_Yvar)。fail-safe。"""
        if not self._rbact_metro_dex:
            return
        try:
            import sys as _sys
            p = str(PROJECT_ROOT / "stage1_optimization")
            if p not in _sys.path:
                _sys.path.insert(0, p)
            from scientific_harness.rbact_noise_bridge import write_rbact_noise
            metro = sorted(self._rbact_metro_dex)
            med = metro[len(metro) // 2]
            out = write_rbact_noise(stage0_results_dir, med, len(metro), u_dex_max=metro[-1])
            self._emit_event("RBACT_NOISE_PERSISTED", {
                "rbact_u_total_dex_median": med, "rbact_u_total_dex_max": metro[-1],
                "n_points": len(metro), "path": out,
            })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("RBACT_NOISE_ERROR", {"error": str(exc)})

    def _sync_closure_report_to_sample_bus(self, stage0_results_dir: Path) -> None:
        """Copy closure_report.json next to bundle under output/stage0_results/<sample_id>/."""
        import json
        import shutil

        bundle_path = stage0_results_dir / "stage0_result_bundle.json"
        closure_path = stage0_results_dir / "closure_report.json"
        if not bundle_path.exists() or not closure_path.exists():
            return
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        except Exception:
            return
        bid = str(bundle.get("sample_id") or "").strip()
        if not bid:
            return
        bus_root = PROJECT_ROOT.parent / "experiments" / "output" / "stage0_results"
        dest_dir = bus_root / bid
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(closure_path, dest_dir / "closure_report.json")

    def _try_run_closure_after_stage0(self, stage0_results_dir: Path, ao_dst_root: Path) -> None:
        """Generate SampleClosureReport after Stage0 (independent of Stage1 BO / cold start)."""
        import os
        import sys

        if os.environ.get("CLOSURE_AFTER_STAGE0", "1").strip().lower() in ("0", "false", "no"):
            return

        bundle_path = stage0_results_dir / "stage0_result_bundle.json"
        if not bundle_path.exists():
            return

        closure_path = stage0_results_dir / "closure_report.json"
        if closure_path.exists():
            self._sync_closure_report_to_sample_bus(stage0_results_dir)
            return

        stage0_root = PROJECT_ROOT / "stage0_measurement"
        if str(stage0_root) not in sys.path:
            sys.path.insert(0, str(stage0_root))

        user_prep_path = ao_dst_root / "user_prep.json"
        if not user_prep_path.exists():
            user_prep_path = None

        use_llm = os.environ.get("CLOSURE_AUTO_USE_LLM", "true").strip().lower() not in ("0", "false", "no")

        bundle_sid = ""
        try:
            import json as _json

            bundle_sid = str(
                _json.loads(bundle_path.read_text(encoding="utf-8")).get("sample_id") or ""
            ).strip()
        except Exception:
            bundle_sid = ""

        self._emit_event("CLOSURE_REPORT_STARTED", {
            "bundle": str(bundle_path),
            "use_llm": use_llm,
            "sample_id": bundle_sid or None,
        })
        try:
            from modules.closure.closure_agent import run_closure_for_bundle_path  # type: ignore

            report, out = run_closure_for_bundle_path(
                bundle_path,
                output_path=closure_path,
                user_prep_path=user_prep_path,
                use_llm=use_llm,
                run_id=self._run_id,
            )
            self._emit_event("CLOSURE_REPORT_COMPLETED", {
                "path": str(out),
                "llm_used": bool(report.meta.llm_used),
                "sample_id": report.meta.sample_id,
            })
        except Exception as exc:
            self._emit_event("CLOSURE_REPORT_FAILED", {
                "error": str(exc),
                "sample_id": bundle_sid or None,
            })
            return

        self._sync_closure_report_to_sample_bus(stage0_results_dir)

    def _run_post_processing_sync(
        self,
        sample_id: str,
        ao_folder: str,
        campaign_config: str,
        history_db_path: str,
        stage1_output_dir: str,
        source_tag: str,
        run_stage1: bool = True,
    ) -> Dict[str, Any]:
        import shutil
        import subprocess
        import sys

        sample_id = _validate_path_token(sample_id, "sample_id")
        ao_folder = _validate_path_token(ao_folder, "ao_folder")
        campaign_config_path = _ensure_within(Path(campaign_config), PROJECT_ROOT, "campaign_config")
        history_db = _ensure_within(Path(history_db_path), PROJECT_ROOT, "history_db_path")
        stage1_output_dir = _ensure_within(Path(stage1_output_dir), PROJECT_ROOT, "stage1_output_dir")
        chi_src_root = Path(os.environ.get("STAGE0_CHI_DATA_DIR") or r"E:\chi_data")
        ao_dst_root = _ensure_within(PROJECT_ROOT.parent / "experiments" / "raw" / "ao" / ao_folder, PROJECT_ROOT.parent / "experiments" / "raw" / "ao", "ao_folder")
        stage0_results_dir = _ensure_within(
            PROJECT_ROOT.parent / "experiments" / "output" / "ao_stage0_results" / ao_folder,
            PROJECT_ROOT.parent / "experiments" / "output" / "ao_stage0_results",
            "stage0_results_dir",
        )

        summary: Dict[str, Any] = {
            "ok": False,
            "sample_id": sample_id,
            "ao_folder": ao_folder,
            "ao_dst": str(ao_dst_root),
            "chi_src": str(chi_src_root),
            "copied_files": [],
            "stage0": None,
            "stage1": None,
            "recipe": None,
            "history_db": str(history_db),
            "output_dir": str(stage1_output_dir),
            "errors": [],
        }
        self._emit_event("POST_PROCESSING_STARTED", {
            "sample_id": sample_id,
            "ao_folder": ao_folder,
            "chi_src": str(chi_src_root),
            "ao_dst": str(ao_dst_root),
        })

        # ---- Step 1: copy CHI .txt files matching this sample ----
        try:
            ao_dst_root.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            summary["errors"].append(f"mkdir failed: {exc}")
            self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
            return summary

        if not chi_src_root.exists():
            summary["errors"].append(f"CHI source dir not found: {chi_src_root}")
            self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
            return summary

        # Match both <sample_id>_T...txt and <sample_id>*_T...txt (CHI appends
        # _#1 / _#2 to disambiguate filename collisions).
        copied: List[str] = []
        try:
            patterns = [f"{sample_id}_T*.txt", f"{sample_id}*_T*.txt"]
            seen = set()
            for pat in patterns:
                for src in chi_src_root.glob(pat):
                    if src.name in seen:
                        continue
                    seen.add(src.name)
                    dst = ao_dst_root / src.name
                    shutil.copy2(src, dst)
                    copied.append(str(dst))
            summary["copied_files"] = copied
        except Exception as exc:
            summary["errors"].append(f"copy failed: {exc}")

        # Copy materials prep stub.  Prefer per-sample variant if present.
        prep_candidates = [
            chi_src_root / f"{sample_id}_材料制备.txt",
            chi_src_root / "材料制备.txt",
        ]
        prep_copied = None
        for prep in prep_candidates:
            if prep.exists():
                try:
                    dst = ao_dst_root / "材料制备.txt"
                    shutil.copy2(prep, dst)
                    prep_copied = str(dst)
                    break
                except Exception as exc:
                    summary["errors"].append(f"prep copy failed: {exc}")
        summary["materials_prep"] = prep_copied

        self._emit_event("POST_PROCESSING_COPY_DONE", {
            "n_eis_files": len(copied),
            "materials_prep": prep_copied,
            "ao_dst": str(ao_dst_root),
        })

        if not copied:
            summary["errors"].append(
                f"No EIS .txt files matched '{sample_id}*_T*.txt' in {chi_src_root}. "
                "Make sure ChiExecutor wrote files and the sample_id matches."
            )
            self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
            return summary
        if prep_copied is None:
            summary["errors"].append(
                f"No 材料制备.txt found in {chi_src_root}. Stage0 needs it to parse R/N/geometry."
            )
            self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
            return summary

        # ---- Step 2: Stage0 processing ----
        stage0_script = PROJECT_ROOT / "code" / "stage0_processing" / "process_ao_stage0.py"
        self._emit_event("STAGE0_STARTED", {"script": str(stage0_script), "folder": ao_folder})
        try:
            cp = subprocess.run(
                [
                    sys.executable, str(stage0_script),
                    "--folder", ao_folder,
                    "--sample_id", sample_id or "",
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=600,
            )
            summary["stage0"] = {
                "returncode": cp.returncode,
                "stdout_tail": (cp.stdout or "")[-2000:],
                "stderr_tail": (cp.stderr or "")[-2000:],
                "results_dir": str(stage0_results_dir),
            }
            if cp.returncode != 0:
                summary["errors"].append(f"Stage0 exited with code {cp.returncode}")
                self._emit_event("STAGE0_FAILED", summary["stage0"])
                self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
                self._write_post_log(summary)
                return summary
            self._emit_event("STAGE0_COMPLETED", summary["stage0"])
            # P3/P13-D 真门控:据 entered_bo rejected 温度过滤 bundle 的 eis_points,
            # 让下游 Stage1 BO/Arrhenius 只吃被准入的点(深冷/坏点不污染)。fail-safe。
            # P13-D:仅 canary/enforce 真过滤;shadow=只记录裁决、被拒点仍进 BO(legacy 行为)。
            if self._enable_commit_gate and self._commit_rejected_T_C:
                if self._commit_gate_enforces():
                    gate_info = self._apply_commit_gate_to_bundle(stage0_results_dir)
                    if gate_info:
                        gate_info["commit_gate_mode"] = self._commit_gate_mode
                        summary["commit_gate"] = gate_info
                else:
                    # shadow:只记录"若 enforce 会挡哪些点",不真过滤(被拒点仍进 BO)。
                    summary["commit_gate"] = {
                        "commit_gate_mode": "shadow",
                        "applied": False,
                        "would_reject_T_C": list(self._commit_rejected_T_C),
                        "note": "shadow=record-only;被拒点仍进 BO(legacy 行为),未真过滤",
                    }
                    self._emit_event("COMMIT_GATE_SHADOW", {
                        "commit_gate_mode": "shadow",
                        "would_reject_T_C": list(self._commit_rejected_T_C),
                    })
            # P4 Rb-ACT R3:把本配方真实计量不确定度(median sigma_log10_total)落到
            # bundle 目录旁,供 Stage1 摄取为 objective_variance(噪声感知 GP train_Yvar)。
            self._write_rbact_noise_for_stage1(stage0_results_dir)
        except subprocess.TimeoutExpired:
            summary["errors"].append("Stage0 timed out after 600s")
            self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
            self._write_post_log(summary)
            return summary
        except Exception as exc:
            summary["errors"].append(f"Stage0 launch failed: {exc}")
            self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
            self._write_post_log(summary)
            return summary

        # Single-sample Closure (LLM narrative when API key present) — not part of Stage1 BO.
        self._try_run_closure_after_stage0(stage0_results_dir, ao_dst_root)

        if not run_stage1:
            self._emit_event("STAGE1_SKIPPED", {
                "reason": "run_stage1_after_stage0=False (cold start / manual)",
                "sample_id": sample_id,
            })
            summary["stage1"] = {"skipped": True, "reason": "run_stage1_after_stage0=False"}
            summary["recipe"] = {
                "path": None,
                "payload": None,
                "note": "Stage1 BO 未运行；冷启动积累数据后可在 /control/postprocess 手动开启 Stage1",
            }
            summary["ok"] = True
            self._emit_event("POST_PROCESSING_COMPLETED", {
                "sample_id": sample_id,
                "ao_folder": ao_folder,
                "stage0_results_dir": str(stage0_results_dir),
                "stage1_skipped": True,
            })
            self._write_post_log(summary)
            return summary

        # ---- Step 3: Stage1 optimization (campaign memory + next recipe) ----
        stage1_script = PROJECT_ROOT / "stage1_optimization" / "run_optimization_loop.py"
        stage1_cmd = [
            sys.executable, str(stage1_script),
            "--campaign_config", str(campaign_config_path),
            "--stage0_results_dir", str(stage0_results_dir),
            "--db_path", str(history_db),
            "--output_dir", str(stage1_output_dir),
            "--mode", "real",
            "--source_tag", source_tag,
        ]
        self._emit_event("STAGE1_STARTED", {"cmd": stage1_cmd})
        try:
            cp = subprocess.run(
                stage1_cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=600,
            )
            summary["stage1"] = {
                "returncode": cp.returncode,
                "stdout_tail": (cp.stdout or "")[-2000:],
                "stderr_tail": (cp.stderr or "")[-2000:],
                "output_dir": str(stage1_output_dir),
            }
            if cp.returncode != 0:
                summary["errors"].append(f"Stage1 exited with code {cp.returncode}")
                self._emit_event("STAGE1_FAILED", summary["stage1"])
                self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
                self._write_post_log(summary)
                return summary
            self._emit_event("STAGE1_COMPLETED", summary["stage1"])
        except subprocess.TimeoutExpired:
            summary["errors"].append("Stage1 timed out after 600s")
            self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
            self._write_post_log(summary)
            return summary
        except Exception as exc:
            summary["errors"].append(f"Stage1 launch failed: {exc}")
            self._emit_event("POST_PROCESSING_FAILED", {"error": summary["errors"][-1]})
            self._write_post_log(summary)
            return summary

        # ---- Step 4: load the new recipe so the UI can show it ----
        recipe_path = stage1_output_dir / "next_experiment_recipe.json"
        recipe_payload = None
        if recipe_path.exists():
            try:
                recipe_payload = json.loads(recipe_path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                summary["errors"].append(f"recipe read failed: {exc}")
        summary["recipe"] = {
            "path": str(recipe_path),
            "payload": recipe_payload,
        }

        summary["ok"] = True
        self._emit_event("POST_PROCESSING_COMPLETED", {
            "sample_id": sample_id,
            "ao_folder": ao_folder,
            "stage0_results_dir": str(stage0_results_dir),
            "stage1_output_dir": str(stage1_output_dir),
            "recipe_path": str(recipe_path),
            "recipe_R": (recipe_payload or {}).get("recipe", {}).get("recommended_parameters", {}).get("R") if recipe_payload else None,
            "recipe_N": (recipe_payload or {}).get("recipe", {}).get("recommended_parameters", {}).get("N") if recipe_payload else None,
        })
        self._write_post_log(summary)
        return summary

    def _write_post_log(self, summary: Dict[str, Any]):
        """Persist the post-processing summary under runs/<run_id>/ for audit."""
        if not self._run_id:
            return
        try:
            log_file = RUNS_DIR / self._run_id / "post_processing.json"
            log_file.write_text(
                json.dumps(summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _wait_stable_temperature(self, target: float, step_idx: int) -> Dict[str, Any]:
        """Two-phase wait for the controller to reach AND stay at ``target``.

        Phase 1 — Arrival:
            Poll until |actual - target| <= eps, but no longer than
            ``cooling_timeout``.  Emits TEMPERATURE_REACHED-style updates
            roughly once per check (the background poller does this too, but
            we want it in the WAIT_STABLE event log as well).

        Phase 2 — Stability hold:
            Once at target, keep reading every ``stability_check_interval``
            seconds for ``stability_duration`` total.  If the temperature
            drifts back outside eps during that window, restart Phase 2.

        Returns
        -------
        ``{"stable": bool, "reason": str | None, "actual_temperature_C": float,
            "target_temperature_C": float, "arrival_seconds": float,
            "hold_seconds": float}``

        The measurement loop should NOT proceed to CHI when ``stable`` is False.
        """
        eps = max(self._stability_eps_C, 0.1)
        check_interval = max(self._stability_check_interval, 1.0)
        hold_duration = max(self._stability_duration, 5.0)
        arrival_deadline = time.time() + max(self._cooling_timeout_s, check_interval)
        t_start_wait = time.time()
        last_t: float = self._current_temperature if self._current_temperature is not None else target

        # ---------- Phase 1: wait for arrival ----------
        self._emit_event("WAIT_STABLE_ARRIVAL_START", {
            "target_temperature_C": target,
            "eps_C": eps,
            "timeout_s": self._cooling_timeout_s,
            "step_idx": step_idx,
        })
        while self._running and time.time() < arrival_deadline:
            if not self._workflow:
                # Without a real driver we cannot verify arrival; treat as
                # unstable so the caller knows to skip CHI.
                return {
                    "stable": False,
                    "reason": "no_workflow",
                    "actual_temperature_C": target,
                    "target_temperature_C": target,
                    "arrival_seconds": 0.0,
                    "hold_seconds": 0.0,
                }
            try:
                res = self._workflow.read_temperature()
            except Exception as exc:
                res = {"success": False, "error": str(exc)}
            if isinstance(res, dict) and res.get("success"):
                t_now = res.get("temperature")
                if t_now is not None:
                    try:
                        last_t = float(t_now)
                    except (TypeError, ValueError):
                        pass
                    else:
                        self._current_temperature = last_t
                        if abs(last_t - target) <= eps:
                            break
            time.sleep(check_interval)
        else:
            # Loop exited via ``while`` condition (timeout) without ``break``.
            elapsed = time.time() - t_start_wait
            self._emit_event("WAIT_STABLE_TIMEOUT", {
                "target_temperature_C": target,
                "actual_temperature_C": last_t,
                "elapsed_s": elapsed,
                "step_idx": step_idx,
                "phase": "arrival",
            })
            return {
                "stable": False,
                "reason": "arrival_timeout",
                "actual_temperature_C": last_t,
                "target_temperature_C": target,
                "arrival_seconds": elapsed,
                "hold_seconds": 0.0,
            }

        # If the run was stopped while waiting, bail out cleanly.
        if not self._running:
            return {
                "stable": False,
                "reason": "run_stopped",
                "actual_temperature_C": last_t,
                "target_temperature_C": target,
                "arrival_seconds": time.time() - t_start_wait,
                "hold_seconds": 0.0,
            }

        arrival_seconds = time.time() - t_start_wait
        self._emit_event("WAIT_STABLE_ARRIVED", {
            "target_temperature_C": target,
            "actual_temperature_C": last_t,
            "arrival_seconds": arrival_seconds,
            "step_idx": step_idx,
        })

        # ---------- Phase 2: stability hold ----------
        hold_start = time.time()
        hold_deadline = hold_start + hold_duration
        last_drift_msg = None
        while self._running and time.time() < hold_deadline:
            time.sleep(check_interval)
            try:
                res = self._workflow.read_temperature()
            except Exception as exc:
                res = {"success": False, "error": str(exc)}
            if isinstance(res, dict) and res.get("success"):
                t_now = res.get("temperature")
                if t_now is not None:
                    try:
                        last_t = float(t_now)
                    except (TypeError, ValueError):
                        continue
                    self._current_temperature = last_t
                    if abs(last_t - target) > eps:
                        last_drift_msg = f"drifted to {last_t:.2f}°C (target {target:.2f}, eps {eps})"
                        self._emit_event("WAIT_STABLE_DRIFT", {
                            "target_temperature_C": target,
                            "actual_temperature_C": last_t,
                            "step_idx": step_idx,
                        })
                        # Reset the hold window — must be stable for the full
                        # duration without any out-of-band reads.
                        hold_start = time.time()
                        hold_deadline = hold_start + hold_duration

        hold_seconds = time.time() - hold_start
        stable = self._running and abs(last_t - target) <= eps and hold_seconds >= hold_duration - 0.5

        self._emit_event("WAIT_STABLE", {
            "actual_temperature_C": last_t,
            "target_temperature_C": target,
            "stable": stable,
            "step_idx": step_idx,
            "arrival_seconds": arrival_seconds,
            "hold_seconds": hold_seconds,
            "reason": None if stable else (last_drift_msg or "hold_window_incomplete"),
        })
        return {
            "stable": stable,
            "reason": None if stable else (last_drift_msg or "hold_window_incomplete"),
            "actual_temperature_C": last_t,
            "target_temperature_C": target,
            "arrival_seconds": arrival_seconds,
            "hold_seconds": hold_seconds,
        }

    def _epistemic_next_action(self, step_idx: int) -> Optional[Dict[str, Any]]:
        """Gap2 内层主动选温:据已测 σ(T) 竞争模型,算"单位成本期望机制判别价值"
        最大的下一个温度。返回 advisory dict(供 prompt 注入 + 事件留痕),或 None。

        诚实边界:这是**受控建议**,不夺用户固定物理阶梯;真正的 setpoint 仍由
        _apply_agent_decision 据固定策略决定。候选集 = 已测温区内未覆盖的网格 +
        当前最冷点之下若干步(可达下一档),让选择器能"回填可疑相变区"或"加速深冷"。
        """
        if not self._enable_active_design:
            return None
        try:
            import sys as _sys
            import numpy as np
            repo = Path(__file__).resolve().parents[3]   # acid-in-clay-close
            nda = str(repo / "V1.0-qianduan-mainline" / "analysis")
            if nda not in _sys.path:
                _sys.path.insert(0, nda)
            from epistemic import active_design as _ad

            pts = []
            for m in self._measurements:
                if not m.get("success"):
                    continue
                T_K = m.get("temperature_K")
                T_C = m.get("temperature_C")
                if T_K is None and T_C is not None:
                    T_K = T_C + 273.15
                sig = m.get("conductivity_S_cm")
                if T_K is None or sig is None or sig <= 0:
                    continue
                pts.append((float(T_K), float(np.log(sig))))
            if len(pts) < 4:
                return None
            T_obs = [p[0] for p in pts]; y_obs = [p[1] for p in pts]

            # 候选温度:已测温区内 1K 网格(未测点)+ 当前最冷之下 step×{1..6}。
            tmin, tmax = min(T_obs), max(T_obs)
            grid = set()
            tt = tmin
            while tt <= tmax:
                grid.add(round(tt, 1)); tt += 1.0
            step = max(float(self._step_size), 1.0)
            for k in range(1, 7):
                grid.add(round(tmin - k * step, 1))
            measured = {round(t, 1) for t in T_obs}
            cands = sorted(c for c in grid if round(c, 1) not in measured)
            if not cands:
                return None

            choice = _ad.select_next_temperature(T_obs, y_obs, cands)
            if choice is None:
                return None
            advisory = {
                "recommended_next_temp_K": choice.next_T_K,
                "recommended_next_temp_C": choice.next_T_K - 273.15,
                "value_per_cost": choice.value_per_cost,
                "raw_discrimination_value": choice.raw_value,
                "cost": choice.cost,
                "n_competing_mechanisms": choice.n_competing,
                "model_posterior": choice.posterior,
                "sigma_meas": choice.sigma_meas,
                "top5_candidates": choice.ranking[:5],
                "rationale": choice.rationale,
            }
            # 过 ActionGate 留痕(advisory 命令,enforce 下不在 allowlist → 仅建议不执行)。
            gate = self._ensure_action_gate()
            gate_status = "unavailable"
            if gate:
                try:
                    from scientific_harness.action_gate import ActionProposal
                    prop = ActionProposal(command="EPISTEMIC_DESIGN_ADVISORY",
                                          source="autonomous",
                                          rationale=choice.rationale[:200],
                                          params={"step_idx": step_idx,
                                                  "next_temp_K": choice.next_T_K})
                    gd = gate.submit(prop)
                    gate_status = f"{gd.mode}:{gd.decision}:dispatched={gd.dispatched}"
                except Exception:
                    gate_status = "gate_error"
            advisory["gate_status"] = str(gate_status)
            advisory["step_idx"] = step_idx
            self._last_epistemic_advisory = advisory   # P13-C canary 微调用最新建议
            self._emit_event("EPISTEMIC_NEXT_ACTION", {
                "step_idx": step_idx,
                "n_points": len(pts),
                **advisory,
                "timestamp": datetime.now().isoformat(),
            })
            return advisory
        except Exception as exc:  # noqa: BLE001
            self._emit_event("EPISTEMIC_NEXT_ACTION_FAILED", {
                "step_idx": step_idx, "error": str(exc),
            })
            return None

    def _call_agent_decision(self, step_idx: int) -> Optional[Dict[str, Any]]:
        """Per-point LLM phase / decision Agent.

        Mirrors ``OnlineExperimentWorkflow._call_agent_decision``: builds the
        same ``measurement_history`` shape (objects with ``success``,
        ``rb_ohm``, ``temperature_K``, ``fit_quality``, ``kk_warning``) and
        invokes ``analyze_experiment_state``.

        The function itself decides whether the LLM is actually called:
        - <5 valid points          → burn-in, no LLM call
        - hard rule (jump / accel) → no LLM call, deterministic FINE_GRAINED_SCAN
        - no API key               → no LLM call, rule-only fallback
        - otherwise                → real LLM call

        Returns the decision dict, or ``None`` if disabled / errored.
        """
        if not self._enable_agent_decision:
            return None

        analyze = _safe_import_analyze_experiment_state()
        if analyze is None:
            self._emit_event("AGENT_UNAVAILABLE", {
                "reason": "analyze_experiment_state import failed",
                "step_idx": step_idx,
            })
            return None

        try:
            from types import SimpleNamespace
            history = []
            for m in self._measurements:
                T_C = m.get("temperature_C")
                T_K = m.get("temperature_K")
                if T_K is None and T_C is not None:
                    T_K = T_C + 273.15
                history.append(SimpleNamespace(
                    success=bool(m.get("success", False)),
                    rb_ohm=m.get("rb_ohm"),
                    temperature_C=T_C,
                    temperature_K=T_K,
                    fit_quality=m.get("r_squared") or m.get("fit_quality"),
                    kk_warning=bool(m.get("kk_warning", False)),
                    conductivity_S_per_cm=m.get("conductivity_S_cm"),
                ))

            # ESAS-OS 2.0:把"agent 大脑"真正接进闭环 —— 决策 prompt 注入
            #   (a) R²-Memory 经治理角色投影,(b) C³-Harness 收敛证书快照。
            #   两者均 fail-safe;构建失败不影响 LLM 调用本身。
            memory_projection = self._memory_projection_for_prompt()
            convergence = self._c3_snapshot()
            # Gap2:可知性驱动的下一步温度建议(advisory,已过 ActionGate 留痕)。
            design_advisory = self._epistemic_next_action(step_idx)

            self._emit_event("AGENT_CALL_STARTED", {
                "step_idx": step_idx,
                "n_points": len(history),
                "has_api_key": bool(self._agent_api_key),
                "model": self._agent_model,
                "memory_injected": bool(memory_projection),
                "convergence_injected": bool(convergence),
                "active_design_injected": bool(design_advisory),
                "design_recommended_next_C": (design_advisory or {}).get("recommended_next_temp_C"),
                "n_memory_items": (memory_projection or {}).get("n_in_domain_memory"),
                "convergence_recommended_action": (convergence or {}).get("recommended_action"),
            })

            agent_context = {"measurement_history": history}
            if memory_projection:
                agent_context["memory_projection"] = memory_projection
            if convergence:
                agent_context["convergence"] = convergence
            if design_advisory:
                agent_context["active_design"] = design_advisory

            decision = analyze(
                agent_context=agent_context,
                api_key=self._agent_api_key,
                model=self._agent_model,
                use_hardcoded_triggers=False,
            )

            decision = decision or {}
            action = decision.get("action", "CONTINUE")
            params = decision.get("action_params") or {}
            reasoning = decision.get("reasoning", "")
            confidence = decision.get("confidence")
            warnings = decision.get("warnings") or []

            next_K = params.get("next_temp_target_K")
            try:
                next_C = (float(next_K) - 273.15) if next_K is not None else None
            except (TypeError, ValueError):
                next_C = None
            self._emit_event("AGENT_DECISION", {
                "step_idx": step_idx,
                "action": action,
                "next_temp_target_K": next_K,
                "next_temp_target_C": next_C,
                "step_size_K": params.get("step_size_K"),
                "confidence": confidence,
                "data_quality": decision.get("data_quality"),
                "reasoning": reasoning,
                "warnings": warnings,
                # 诚实标记:只信 phase_detect 显式返回的 llm_called(真实成功调用才 True);
                # 不再用"有 api_key"兜底推断(fe3/fe4b 曾因此把规则回退误报成 LLM 调用)。
                "llm_called": bool(decision.get("llm_called", False)),
                "rule_triggered": decision.get("rule_triggered"),
                "model": self._agent_model,
                "n_points": len(history),
                "timestamp": datetime.now().isoformat(),
            })

            self._agent_decisions.append({
                "step_idx": step_idx,
                "timestamp": datetime.now().isoformat(),
                "decision": decision,
            })
            return decision

        except Exception as exc:  # noqa: BLE001
            self._emit_event("AGENT_DECISION_FAILED", {
                "step_idx": step_idx,
                "error": str(exc),
            })
            return None

    # ------------------------------------------------------------------
    # ESAS-OS 2.0 ActionGate（P5）—— 自主 Agent 决策的唯一受控入口。
    #   把"自主覆盖动作"映射成受控命令过 gate;enforce 下非 allowlist → BLOCKED。
    #   不变量:任何自主覆盖动作都经过 gate(bypass=0);override 与自主隔离留痕。
    # ------------------------------------------------------------------
    # 自主 Agent action → ActionGate 受控命令名(CONTINUE=安全默认,无需门控)。
    _AGENT_ACTION_TO_COMMAND = {
        "FINE_GRAINED_SCAN": "TRIGGER_FINE_SCAN",   # ∈ allowlist → enforce 放行
        "ABORT": "AGENT_ABORT",                      # ∉ allowlist → enforce BLOCKED(需人工)
    }

    def _ensure_action_gate(self):
        """惰性构建 per-run ActionGate(enqueue_fn 仅留痕,实际执行由 loop 据 dispatched 决定)。"""
        if self._action_gate is not None:
            return self._action_gate
        try:
            import sys as _sys
            base = Path(__file__).resolve().parents[2]
            p = str(base / "stage1_optimization")
            if p not in _sys.path:
                _sys.path.insert(0, p)
            from scientific_harness.action_gate import (
                ActionGate, ALLOWED_AUTONOMOUS_COMMANDS)

            def _noop_enqueue(command, params=None):
                # gate 的"下发"在本适配器里等价于"允许 loop 应用该自主动作";
                # 真正的 setpoint/scan 改动仍由 _apply_agent_decision 执行。
                return True

            # P13-C:把受硬护栏约束的 canary 选温命令并入 allowlist(canary/enforce 下可放行);
            # 该命令仅在通过"单步邻域 + 阶梯包络 + 回温≤15K"预检后才提交,故是低风险动作。
            allowed = ALLOWED_AUTONOMOUS_COMMANDS | {"EPISTEMIC_CANARY_SETPOINT"}
            self._action_gate = ActionGate(_noop_enqueue, mode=self._harness_mode,
                                           allowed=allowed)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("ACTION_GATE_UNAVAILABLE", {"error": str(exc)})
            self._action_gate = False
        return self._action_gate

    def _gate_agent_decision(self, decision: Optional[Dict[str, Any]], step_idx: int) -> Optional[Dict[str, Any]]:
        """把自主覆盖动作过 ActionGate。BLOCKED → 降级为 CONTINUE(安全默认)。
        CONTINUE/空决策直接放行(本就是默认)。整体 fail-safe:出错则原样返回。"""
        if not decision:
            return decision
        action = decision.get("action", "CONTINUE")
        command = self._AGENT_ACTION_TO_COMMAND.get(action)
        if command is None:
            return decision  # CONTINUE 等默认动作不经 gate(非自主覆盖)
        gate = self._ensure_action_gate()
        if not gate:
            # gate 不可用 → 记一次 bypass(诚实),仍按原决策执行(fail-safe)。
            self._action_gate_bypass_count += 1
            self._emit_event("ACTION_GATE_BYPASS", {"step_idx": step_idx, "action": action})
            return decision
        try:
            from scientific_harness.action_gate import ActionProposal
            prop = ActionProposal(command=command, source="autonomous",
                                  rationale=str(decision.get("reasoning") or "")[:200],
                                  params={"step_idx": step_idx})
            gd = gate.submit(prop)
            rec = {"step_idx": step_idx, "action": action, "command": command,
                   "mode": gd.mode, "decision": gd.decision, "dispatched": gd.dispatched}
            self._action_gate_decisions.append(rec)
            self._emit_event("ACTION_GATE_DECISION", rec)
            if not gd.dispatched:
                # enforce/canary 下被拦截 → 降级为安全默认(线性粗扫,不 abort/不细扫)。
                self._emit_event("ACTION_GATE_BLOCKED", {
                    "step_idx": step_idx, "action": action, "command": command,
                    "mode": gd.mode, "downgraded_to": "CONTINUE",
                })
                return {"action": "CONTINUE", "reasoning": f"action_gate_blocked:{action}"}
            return decision
        except Exception as exc:  # noqa: BLE001
            self._action_gate_bypass_count += 1
            self._emit_event("ACTION_GATE_ERROR", {"step_idx": step_idx, "error": str(exc)})
            return decision

    def _apply_agent_decision(
        self,
        decision: Optional[Dict[str, Any]],
        current_t: float,
        step_idx: int,
        planned_t: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Translate an Agent decision into next-step temperature + step size.

        Parameters
        ----------
        current_t : float
            The actual measured chamber temperature for this step (used by
            FINE_GRAINED_SCAN safety rails).
        planned_t : float, optional
            The previously-requested setpoint (the loop's ``t`` variable).
            CONTINUE actions use ``planned_t - step_size`` so the temperature
            grid stays a clean 3°C ladder instead of drifting with chamber
            settling error.  Falls back to ``current_t`` when not provided.

        Returns a dict with:
          - next_t       : float, target temperature (°C) for the next setpoint
          - abort        : bool, whether the loop should stop
          - in_fine_band : bool, whether we entered / are inside a fine band
          - is_reheat    : bool, whether we are deliberately heating up (the
                            next iteration should use the enhanced settle
                            workflow with extra thermal-inertia wait).
        """
        # The "ladder anchor" — always step DOWN from the previously-planned
        # setpoint, not from the drifted actual temperature.
        anchor_t = planned_t if planned_t is not None else current_t

        # Default behaviour when no Agent / decision: linear coarse step down.
        if not decision:
            return {
                "next_t": anchor_t - self._step_size,
                "abort": False,
                "in_fine_band": False,
                "is_reheat": False,
            }

        action = decision.get("action", "CONTINUE")
        params = decision.get("action_params") or {}
        next_K = params.get("next_temp_target_K")
        step_K = params.get("step_size_K")
        next_C: Optional[float] = None
        if next_K is not None:
            try:
                next_C = float(next_K) - 273.15
            except (TypeError, ValueError):
                next_C = None

        if action == "ABORT":
            return {"next_t": current_t, "abort": True, "in_fine_band": False, "is_reheat": False}

        if action == "FINE_GRAINED_SCAN":
            # 用户固定策略（2026-05-12 改）：
            #   - LLM 只负责判断"是否要细扫"，不读它给的 next_temp_target_K / step_size_K
            #   - 回温目标 = 触发点温度 + 10°C（硬编码，不再动态调节）
            #   - 细扫步长 = 1°C（不允许 LLM 改）
            #   - 细扫带底 = 触发点温度本身，即一直密集采样到原触发点为止，
            #     之后下一个粗扫点 = 触发点 - coarse_step（例如 -25 → -28）
            trigger_T = anchor_t if planned_t is not None else current_t
            next_C = trigger_T + 10.0
            self._fine_step = 1.0
            self.apply_policy(mode="FINE")
            self._fine_scan_end_C = trigger_T
            self._fine_trigger_T_C = trigger_T
            is_reheat = True  # +10°C 一定是回温
            llm_suggested_C: Optional[float] = None
            if next_K is not None:
                try:
                    llm_suggested_C = float(next_K) - 273.15
                except (TypeError, ValueError):
                    llm_suggested_C = None
            self._emit_event("AGENT_FINE_SCAN", {
                "step_idx": step_idx,
                "trigger_temperature_C": trigger_T,
                "next_temperature_C": next_C,
                "fine_step": self._fine_step,
                "fine_band_end_C": self._fine_scan_end_C,
                "is_reheat": is_reheat,
                "policy": "fixed_+10C_reheat_1C_step",
                "llm_suggested_next_C": llm_suggested_C,
                "llm_suggested_step_K": step_K,
            })
            return {
                "next_t": next_C,
                "abort": False,
                "in_fine_band": True,
                "is_reheat": is_reheat,
            }

        # CONTINUE (or unknown) — anchor to the previously-planned setpoint
        # to keep a clean 3°C ladder (18, 15, 12, 9, 6, 3, 0, -3, ...).
        # We deliberately IGNORE the Agent's next_temp_target_K here: in the
        # rule-fallback path the phase_detect helper computes
        # ``measured_T_K - 3`` which compounds chamber-settling drift; in
        # the LLM path "CONTINUE" simply means "keep cooling at step_size",
        # so the explicit target is redundant.  Only FINE_GRAINED_SCAN and
        # ABORT need an explicit target.
        if step_K:
            try:
                self._step_size = float(step_K)
            except (TypeError, ValueError):
                pass
        next_t = anchor_t - self._step_size
        # P13-C:canary 模式下,据 active_design 建议在固定阶梯相邻候选间微调(经 ActionGate + 硬护栏)。
        fixed_next_t = next_t
        canary_t = self._active_design_canary_nudge(fixed_next_t, anchor_t, step_idx)
        is_reheat = False
        if canary_t is not None:
            next_t = canary_t
            is_reheat = canary_t > anchor_t + 1e-6   # 微调回填到更暖点 = 回温
        return {
            "next_t": next_t,
            "abort": False,
            "in_fine_band": False,
            "is_reheat": is_reheat,
            "agent_suggested_next_C": next_C,   # kept for debugging / events
            "canary_applied": canary_t is not None,
            "fixed_ladder_next_C": fixed_next_t,
        }

    def _active_design_canary_nudge(self, fixed_next_t: float, anchor_t: float,
                                    step_idx: int) -> Optional[float]:
        """P13-C:canary 模式据 active_design 最新建议,在固定阶梯的**相邻候选间**微调下一 setpoint。
        经 ActionGate 放行才生效;越硬护栏(单步邻域 / 阶梯包络 / 回温≤15K)或被拦即回退固定阶梯(None)。
        advisory 模式恒返回 None(行为完全不变)。"""
        if self._active_design_mode != "canary":
            return None
        adv = self._last_epistemic_advisory
        if not adv:
            return None
        try:
            rec_C = adv.get("recommended_next_temp_C")
            if rec_C is None:
                return None
            rec_C = round(float(rec_C), 1)
            step = max(float(self._step_size), 1.0)
            max_steps = max(1, int(getattr(self, "_canary_max_steps", 2)))
            neigh = step * max_steps
            reasons = []
            # 硬护栏 1:邻域(只在固定阶梯点 ±max_steps×step 内微调,禁止大跳)。H3:默认 ±2 step。
            if abs(rec_C - fixed_next_t) > neigh + 1e-6:
                reasons.append(f"not_adjacent(|{rec_C}-{fixed_next_t}|>{neigh})")
            # 硬护栏 2:阶梯包络(不越 [t_end, t_start])
            lo = self._t_end_C if self._t_end_C is not None else -1e9
            hi = self._t_start_C if self._t_start_C is not None else 1e9
            if not (min(lo, hi) - 1e-6 <= rec_C <= max(lo, hi) + 1e-6):
                reasons.append(f"out_of_envelope([{lo},{hi}])")
            # 硬护栏 3:回温≤15K(相对 anchor 不得升温超过 15℃)
            if rec_C - anchor_t > 15.0 + 1e-6:
                reasons.append(f"reheat>15K({rec_C - anchor_t:.1f})")
            # 需实质移动(否则无需微调)
            if abs(rec_C - fixed_next_t) < 0.5:
                reasons.append("no_meaningful_move")
            if reasons:
                self._emit_event("EPISTEMIC_CANARY_SKIPPED", {
                    "step_idx": step_idx, "rec_C": rec_C,
                    "fixed_next_t": fixed_next_t, "reasons": reasons})
                return None
            # 通过预检 → 过 ActionGate(canary/enforce 按 allowlist 放行;shadow 照常留痕)
            gate = self._ensure_action_gate()
            if not gate:
                self._action_gate_bypass_count += 1
                self._emit_event("ACTION_GATE_BYPASS",
                                 {"step_idx": step_idx, "action": "EPISTEMIC_CANARY_SETPOINT"})
                return None
            from scientific_harness.action_gate import ActionProposal
            prop = ActionProposal(
                command="EPISTEMIC_CANARY_SETPOINT", source="autonomous",
                rationale=f"active_design nudge {fixed_next_t}->{rec_C}"[:200],
                params={"step_idx": step_idx, "rec_C": rec_C, "fixed_next_t": fixed_next_t})
            gd = gate.submit(prop)
            rec_dec = {"step_idx": step_idx, "action": "EPISTEMIC_CANARY_SETPOINT",
                       "command": "EPISTEMIC_CANARY_SETPOINT", "mode": gd.mode,
                       "decision": gd.decision, "dispatched": gd.dispatched}
            self._action_gate_decisions.append(rec_dec)
            self._emit_event("ACTION_GATE_DECISION", rec_dec)
            if not gd.dispatched:
                self._emit_event("EPISTEMIC_CANARY_BLOCKED", {
                    "step_idx": step_idx, "rec_C": rec_C, "fixed_next_t": fixed_next_t,
                    "mode": gd.mode, "downgraded_to": "fixed_ladder"})
                return None
            self._emit_event("EPISTEMIC_CANARY_SETPOINT", {
                "step_idx": step_idx, "fixed_next_t": fixed_next_t,
                "canary_next_t": rec_C, "delta_C": round(rec_C - fixed_next_t, 2),
                "mode": gd.mode, "value_per_cost": adv.get("value_per_cost")})
            return rec_C
        except Exception as exc:  # noqa: BLE001
            self._emit_event("EPISTEMIC_CANARY_ERROR", {"step_idx": step_idx, "error": str(exc)})
            return None

    def _trigger_chi_measurement(
        self,
        filename_temperature_C: float,
        step_idx: int,
        *,
        chamber_actual_C: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Drive the CHI GUI via ChiExecutor; return raw EIS arrays + file path.

        ``filename_temperature_C`` is written into the CHI save name (``T…``)
        so it matches the programmed setpoint ladder.  ``chamber_actual_C`` is
        optional metadata for events (defaults to the same value).

        Returns a dict with keys: success, frequencies, z_real, z_imag,
        output_file, error.  The caller is responsible for Rb fitting.
        """
        actual_meta = chamber_actual_C if chamber_actual_C is not None else filename_temperature_C
        if self._chi_executor is None or not self._chi_params:
            return {
                "success": False,
                "frequencies": None,
                "z_real": None,
                "z_imag": None,
                "output_file": None,
                "error": "ChiExecutor not initialized; reconnect hardware before starting.",
            }

        self._emit_event("CHI_MEASUREMENT_STARTED", {
            "step_idx": step_idx,
            "temperature_C": filename_temperature_C,
            "chamber_actual_C": actual_meta,
            "chi_params": self._chi_params,
        })
        try:
            chi_result = self._chi_executor.execute_measurement(
                chi_params=self._chi_params,
                output_dir=self._chi_params.get("your_position"),
                current_temperature_C=filename_temperature_C,
            )
        except Exception as exc:
            self._emit_event("CHI_MEASUREMENT_FAILED", {
                "step_idx": step_idx,
                "error": str(exc),
            })
            return {
                "success": False,
                "frequencies": None,
                "z_real": None,
                "z_imag": None,
                "output_file": None,
                "error": str(exc),
            }

        self._emit_event(
            "CHI_MEASUREMENT_COMPLETED" if chi_result.get("success") else "CHI_MEASUREMENT_FAILED",
            {
                "step_idx": step_idx,
                "output_file": chi_result.get("output_file"),
                "error": chi_result.get("error"),
                "n_points": (
                    len(chi_result["frequencies"]) if chi_result.get("frequencies") is not None else 0
                ),
            },
        )
        return chi_result

    # ------------------------------------------------------------------
    # ESAS-OS 2.0 治理旁路（Phase 1）—— 纯加法 / fail-safe / 默认开。
    #   把 shadow 三重提交、Rb-ACT 双跑、measurement_txn 逐点准入接到 live 回路,
    #   并经 _emit_event 推 3 个新事件(SHADOW_VERDICT/RBACT_DECISION/TXN_ADMISSION)。
    #   设计铁律:① 不改 legacy 测量/入库路径;② 任一步失败只记事件、绝不抛回主回路。
    # ------------------------------------------------------------------
    def _ensure_harness_fns(self):
        """惰性导入治理函数;成功返回 dict,失败缓存 False 并返回 None(不重试、不抛错)。"""
        if self._harness_fns is not None:
            return self._harness_fns or None
        try:
            import sys as _sys
            base = Path(__file__).resolve().parents[2]  # V1.0-qianduan-mainline
            for sub in ("stage0_measurement", "stage1_optimization"):
                p = str(base / sub)
                if p not in _sys.path:
                    _sys.path.insert(0, p)
            from rb_act import analyze_spectrum, ABSTAIN
            from scientific_harness.measurement_txn import submit_measurement_offline
            from scientific_harness.shadow import ShadowHarnessRecorder
            self._harness_fns = {
                "analyze_spectrum": analyze_spectrum,
                "ABSTAIN": ABSTAIN,
                "submit_measurement_offline": submit_measurement_offline,
                "ShadowHarnessRecorder": ShadowHarnessRecorder,
            }
            return self._harness_fns
        except Exception as exc:  # noqa: BLE001
            self._harness_fns = False
            try:
                self._emit_event("HARNESS_UNAVAILABLE", {"error": str(exc)})
            except Exception:
                pass
            return None

    def _build_harness_recorder(self):
        """构造 ShadowHarnessRecorder(每运行一个,落盘到 runs/<run_id>/shadow_harness)。"""
        fns = self._ensure_harness_fns()
        if not fns or not self._run_id:
            return None
        try:
            out_dir = str(RUNS_DIR / self._run_id / "shadow_harness")
            rec = fns["ShadowHarnessRecorder"](out_dir=out_dir, sample_id=self._sample_id or "unknown")
            self._emit_event("HARNESS_SHADOW_STARTED", {"out_dir": out_dir})
            return rec
        except Exception as exc:  # noqa: BLE001
            self._emit_event("HARNESS_UNAVAILABLE", {"error": f"shadow init: {exc}"})
            return None

    def _maybe_inject_governance_fault(self, step_idx, bundle):
        """G-2:真机故障注入(opt-in)。**只改治理层输入**(样品核对 id / QA 状态 / 几何),
        让真实 measurement_txn 自然判 entered_bo=False;**绝不触碰温控/CHI 物理命令**(安全)。

        返回 (expected_sample_id, injected_desc|None)。未注入时 expected 取 None(=bundle sample_id)。
        """
        inj = next((d for d in self._inject_faults
                    if int(d.get("at_step", -1)) == int(step_idx)), None)
        if not inj:
            return None, None
        ftype = inj["type"]
        expected_sid = None
        try:
            if ftype == "SAMPLE_MISMATCH":
                # 传入与 bundle 不符的 expected id → C_P unknown → 全 REJECT(样品来源核对失败)。
                expected_sid = f"{bundle.get('sample_id', 'unknown')}__FAULT_MISMATCH"
            elif ftype == "QA_FAIL":
                # 标记该点 QA 失败 → _valid_points 过滤 → qa_failed=True → 不进 BO。
                for ep in bundle.get("eis_points", []):
                    ep["status"] = "legacy_failure"
                    ep["quality_flags"] = list(ep.get("quality_flags") or []) + ["legacy_failure"]
            injected = {"type": ftype, "at_step": int(step_idx), "layer": "governance_only",
                        "note": "仅治理层注入;温控/CHI 未受影响"}
            self._emit_event("FAULT_INJECTED", injected)
            return expected_sid, injected
        except Exception as exc:  # noqa: BLE001
            self._emit_event("HARNESS_GOVERNANCE_ERROR",
                             {"stage": "fault_injection", "step_idx": step_idx, "error": str(exc)})
            return None, None

    def _run_point_governance(self, *, step_idx, T_C, freq, zr, zi, eis_result, rb_result,
                              output_file=None, chamber_actual_C=None, setpoint_C=None):
        """逐点治理旁路(shadow + Rb-ACT + txn + H2 在线仪器见证)。整体 fail-safe,绝不影响测量。"""
        fns = self._ensure_harness_fns()
        if not fns:
            return
        import numpy as _np
        import math as _math
        thickness = self._thickness_cm if self._thickness_cm is not None else 0.1
        area = self._area_cm2 if self._area_cm2 is not None else 1.96
        T_K = float(T_C) + 273.15
        try:
            f = _np.asarray(freq, dtype=float)
            zrr = _np.asarray(zr, dtype=float)
            zii = _np.asarray(zi, dtype=float)
        except Exception:  # noqa: BLE001
            return

        # (a) shadow 三重提交旁路 —— 用 per-point 计数增量判定本点是否一致。
        if self._harness_recorder is None:
            self._harness_recorder = self._build_harness_recorder()
        rec = self._harness_recorder
        if rec is not None and eis_result is not None:
            try:
                n0, a0 = rec._n, rec._n_agree
                rec.record(eis_result, freq=f, z_real=zrr, z_imag=zii, temperature_K=T_K)
                agreed = (rec._n - n0 == 1) and (rec._n_agree - a0 == 1)
                self._emit_event("SHADOW_VERDICT", {
                    "step_idx": step_idx, "temperature_C": T_C,
                    "agree": bool(agreed),
                    "n_points": rec._n,
                    "agreement_rate": (rec._n_agree / rec._n) if rec._n else None,
                    "blind_retry_count": rec._n_blind_retry,
                })
            except Exception as exc:  # noqa: BLE001
                self._emit_event("HARNESS_GOVERNANCE_ERROR",
                                 {"stage": "shadow", "step_idx": step_idx, "error": str(exc)})

        # (b) Rb-ACT 双跑(REPORT/ABSTAIN + |Δlog10 Rb| + 未解释翻转)。
        admission_signals: Dict[str, Any] = {}
        try:
            r = fns["analyze_spectrum"](f, zrr, zii, thickness_cm=thickness, area_cm2=area)
            legacy_rb = getattr(r, "legacy_rb_ohm", None)
            rbact_rb = getattr(r.posterior, "rb_ohm", None) if getattr(r, "posterior", None) else None
            delta = None
            if r.decision != fns["ABSTAIN"] and legacy_rb and rbact_rb and legacy_rb > 0 and rbact_rb > 0:
                delta = abs(_math.log10(rbact_rb) - _math.log10(legacy_rb))
            admission_signals = dict(getattr(r, "admission_signals", {}) or {})
            # H4:累积完整 RbActResult(含 legacy_rb / 后验 rb / u_dex),供收尾 R4 激活构 σ_v2+delta。
            try:
                if getattr(r, "temperature_K", None) is None:
                    r.temperature_K = T_K
                self._rbact_results.append(r)
            except Exception:  # noqa: BLE001
                pass
            # 真实计量不确定度(dex)+ 主动测量请求 —— 喂 C³-Harness。
            u_total_dex = None
            post = getattr(r, "posterior", None)
            if post is not None:
                u_total_dex = getattr(post, "sigma_log10_total", None)
            active_acts = [str(getattr(a, "action", a)) for a in (getattr(r, "active_requests", None) or [])]
            if isinstance(u_total_dex, (int, float)):
                self._rbact_metro_dex.append(float(u_total_dex))
            for _a in active_acts:
                if _a not in self._rbact_active_requests:
                    self._rbact_active_requests.append(_a)
            self._emit_event("RBACT_DECISION", {
                "step_idx": step_idx, "temperature_C": T_C,
                "decision": str(r.decision),
                "rbact_rb_ohm": rbact_rb, "legacy_rb_ohm": legacy_rb,
                "abs_dlog10_rb": delta,
                "unexplained_flip": bool(delta is not None and delta > 0.30),
                "u_total_dex": u_total_dex,
                "active_requests": active_acts,
            })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("HARNESS_GOVERNANCE_ERROR",
                             {"stage": "rb_act", "step_idx": step_idx, "error": str(exc)})

        # (c) measurement_txn 逐点准入(U1–U6 / entered_bo / blind_retry)。
        try:
            raw = rb_result.get("raw") if isinstance(rb_result, dict) else None
            kk_res = None
            if isinstance(raw, dict):
                kk_res = (raw.get("kk_result") or {}).get("mu_median")
            bundle = {
                "sample_id": self._sample_id or "unknown",
                "geometry": {"thickness_cm": thickness, "area_cm2": area},
                "file_hashes": {f"live_step_{step_idx}": "live"},
                "eis_points": [{
                    "T_K": T_K,
                    "status": (rb_result.get("status") if isinstance(rb_result, dict) else None) or "OK",
                    "kk_residual": kk_res,
                    "rb_ohm": rb_result.get("rb_ohm") if isinstance(rb_result, dict) else None,
                    "rb_method": rb_result.get("rb_method") if isinstance(rb_result, dict) else None,
                }],
                "arrhenius": {},
            }
            # G-2:真机故障注入(opt-in)——仅改治理层输入,让真实 txn 自然判拒(entered_bo=False)。
            expected_sid, injected = self._maybe_inject_governance_fault(step_idx, bundle)
            txn = fns["submit_measurement_offline"](
                bundle, rb_act_signals=admission_signals, expected_sample_id=expected_sid)
            adm = {str(getattr(k, "name", k)): v["status"] for k, v in txn.use_admissions.items()}
            self._txn_rows.append({
                "step_idx": step_idx, "T_C": T_C,
                "entered_bo": bool(txn.entered_bo), "admissions": adm,
                **({"injected_fault": injected} if injected else {}),
            })
            self._emit_event("TXN_ADMISSION", {
                "step_idx": step_idx, "temperature_C": T_C,
                "entered_bo": txn.entered_bo,
                "blind_retry_count": txn.blind_retry_count,
                "admissions": adm,
                **({"injected_fault": injected} if injected else {}),
            })
            if injected:
                # G-2 验收锚点:注入的坏点必须被治理拦截(不得进 BO)。真机后置验证器据此核对。
                caught = not bool(txn.entered_bo)
                rec = {"step_idx": step_idx, "T_C": T_C, "fault": injected,
                       "entered_bo": bool(txn.entered_bo), "caught": caught}
                self._fault_injections.append(rec)
                self._emit_event("FAULT_INJECTION_RESULT", rec)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("HARNESS_GOVERNANCE_ERROR",
                             {"stage": "txn", "step_idx": step_idx, "error": str(exc)})

        # (d) H2 在线仪器见证:用真实 CHI 文件 + 温控稳定 + 仪器态经真实 EvidenceTransaction 推 C_P;
        #     支持协议级故障注入。opt-in;fail-safe;与 legacy 入库/上面 (c) 提交路径解耦。
        if self._enable_instrument_witness:
            self._run_instrument_witness(
                step_idx=step_idx, T_C=T_C,
                admission_signals=admission_signals,
                output_file=output_file, chamber_actual_C=chamber_actual_C,
                setpoint_C=setpoint_C, rb_result=rb_result)

    def _run_instrument_witness(self, *, step_idx, T_C, admission_signals,
                               output_file, chamber_actual_C, setpoint_C, rb_result):
        """H2:用**真实在线见证**(真 CHI 文件 sha256 + 温控稳定 + 仪器态)经真实
        EvidenceTransaction 推 C_P → C_M → entered_bo。支持协议级故障注入(驱动边界软件注入,
        绝不碰样品/温控物理安全)。落 `_instrument_witness_rows`,收尾写 summary。fail-safe。"""
        try:
            import sys as _sys
            p = str(PROJECT_ROOT / "stage1_optimization")
            if p not in _sys.path:
                _sys.path.insert(0, p)
            from scientific_harness.instrument_witness import submit_measurement_online
        except Exception as exc:  # noqa: BLE001
            self._emit_event("INSTRUMENT_WITNESS_UNAVAILABLE", {"error": str(exc)})
            return
        try:
            thickness = self._thickness_cm if self._thickness_cm is not None else 0.1
            area = self._area_cm2 if self._area_cm2 is not None else 1.96
            raw = rb_result.get("raw") if isinstance(rb_result, dict) else None
            kk_res = None
            if isinstance(raw, dict):
                kk_res = (raw.get("kk_result") or {}).get("mu_median")
            status = (rb_result.get("status") if isinstance(rb_result, dict) else None) or "OK"
            rb_ohm = rb_result.get("rb_ohm") if isinstance(rb_result, dict) else None
            rb_method = rb_result.get("rb_method") if isinstance(rb_result, dict) else None
            # 从本点真实量构造 measurement_signals(与提交路径同源字段)。
            signals = {
                "qa_failed": bool(str(status).upper() not in ("OK", "")),
                "kk_mu_median": kk_res, "kk_testable": kk_res is not None,
                "uncertainty_status": "QUANTIFIED" if (area > 0 and thickness > 0) else "UNKNOWN",
                "geometry_valid": bool(area > 0 and thickness > 0),
                "rb_method_success": rb_ohm is not None,
                "ecm_fallback": (rb_method == "equivalent_circuit"),
                "n_series_points": 1,
            }
            # 协议级故障注入(本步命中才注)。
            inj = next((d for d in self._protocol_faults
                        if int(d.get("at_step", -1)) == int(step_idx)), None)
            fault = inj["type"] if inj else None
            txn = submit_measurement_online(
                sample_id=self._sample_id or "unknown",
                output_file=output_file,
                measurement_signals=signals,
                chi_success=True,
                chamber_actual_C=chamber_actual_C, setpoint_C=setpoint_C,
                rb_act_signals=admission_signals, protocol_fault=fault)
            adm = {str(getattr(k, "name", k)): v["status"] for k, v in txn.use_admissions.items()}
            row = {
                "step_idx": step_idx, "T_C": T_C,
                "c_p": txn.physical_occurred, "entered_bo": bool(txn.entered_bo),
                "reconciled": bool(txn.reconciled), "blind_retry_count": txn.blind_retry_count,
                "admissions": adm,
                **({"protocol_fault": fault} if fault else {}),
            }
            self._instrument_witness_rows.append(row)
            self._emit_event("INSTRUMENT_WITNESS", row)
            if fault:
                # 验收锚点:注入的见证类坏点必须被拦(不进 BO),且 blind_retry=0。
                caught = (not bool(txn.entered_bo)) or (fault == "ACK_LOSS")
                self._emit_event("PROTOCOL_FAULT_RESULT", {
                    "step_idx": step_idx, "T_C": T_C, "fault": fault,
                    "c_p": txn.physical_occurred, "entered_bo": bool(txn.entered_bo),
                    "blind_retry_count": txn.blind_retry_count, "caught": caught,
                    "note": ("ACK_LOSS 例外:文件在则应仍 confirmed(先核对、禁盲目重试);"
                             "其余见证类故障应不进 BO。"),
                })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("HARNESS_GOVERNANCE_ERROR",
                             {"stage": "instrument_witness", "step_idx": step_idx, "error": str(exc)})

    def _finalize_instrument_witness(self):
        """H2 收尾:落 runs/<id>/instrument_witness_summary.json(在线见证 + 协议故障验收锚点)。fail-safe。"""
        if not self._enable_instrument_witness or not self._instrument_witness_rows:
            return
        try:
            rows = list(self._instrument_witness_rows)
            faulted = [r for r in rows if r.get("protocol_fault")]
            # 验收:见证类故障(除 ACK_LOSS)全不进 BO;ACK_LOSS 应仍 confirmed(先核对)。
            def _ok(r):
                if r.get("protocol_fault") == "ACK_LOSS":
                    return r.get("c_p") == "confirmed" and r.get("blind_retry_count") == 0
                return r.get("entered_bo") is False and r.get("blind_retry_count") == 0
            summary = {
                "requested_protocol_faults": list(self._protocol_faults),
                "n_points": len(rows),
                "n_faults_injected": len(faulted),
                "n_faults_handled": sum(1 for r in faulted if _ok(r)),
                "all_faults_handled": bool(faulted and all(_ok(r) for r in faulted)),
                "any_blind_retry": bool(any(r.get("blind_retry_count", 0) for r in rows)),
                "witness_rows": rows,
                "note": ("H2 在线仪器见证:见证来自真实 CHI 文件 + 温控稳定 + 仪器态;"
                         "协议级故障为驱动边界软件注入,温控/CHI 物理命令未受影响。"),
            }
            if self._run_id:
                out = RUNS_DIR / self._run_id / "instrument_witness_summary.json"
                out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("INSTRUMENT_WITNESS_SUMMARY", {
                "n_points": summary["n_points"],
                "n_faults_injected": summary["n_faults_injected"],
                "n_faults_handled": summary["n_faults_handled"],
                "all_faults_handled": summary["all_faults_handled"],
                "any_blind_retry": summary["any_blind_retry"],
            })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("HARNESS_GOVERNANCE_ERROR",
                             {"stage": "instrument_witness_finalize", "error": str(exc)})

    # ------------------------------------------------------------------
    # ESAS-OS 2.0 R²-Memory（P2）—— 把 AgentMemory 真正接到 live 回路。
    #   ① 不改 legacy 测量/入库;② 任一步失败只记事件、绝不抛回主回路。
    # ------------------------------------------------------------------
    def _ensure_memory(self):
        """惰性导入 live_memory_bridge + 构建 AgentMemory(每运行一个)+ 装跨域守卫。
        成功返回 bridge 模块;失败缓存 False 并返回 None(不重试、不抛错)。"""
        if self._memory_bridge is False:
            return None
        if self._memory_bridge is None:
            try:
                import sys as _sys
                base = Path(__file__).resolve().parents[2]  # V1.0-qianduan-mainline
                p = str(base / "stage1_optimization")
                if p not in _sys.path:
                    _sys.path.insert(0, p)
                from scientific_memory import live_memory_bridge as _bridge
                self._memory_bridge = _bridge
            except Exception as exc:  # noqa: BLE001
                self._memory_bridge = False
                try:
                    self._emit_event("MEMORY_UNAVAILABLE", {"error": str(exc)})
                except Exception:
                    pass
                return None
        if self._agent_memory is None:
            try:
                self._agent_memory = self._memory_bridge.new_campaign_memory()
                self._memory_foreign_id = self._memory_bridge.install_cross_domain_guard(self._agent_memory)
                self._emit_event("MEMORY_STARTED", {"foreign_guard_id": self._memory_foreign_id})
            except Exception as exc:  # noqa: BLE001
                self._memory_bridge = False
                self._emit_event("MEMORY_UNAVAILABLE", {"error": f"init: {exc}"})
                return None
        return self._memory_bridge

    def _run_point_memory(self, *, step_idx, T_C, rb_ohm, sigma_S_cm, qc_grade, governance_verdict):
        """逐点把真实测量写入 R²-Memory(经写门 + RoundState)。整体 fail-safe。"""
        bridge = self._ensure_memory()
        if not bridge:
            return
        try:
            res = bridge.record_point(
                self._agent_memory,
                step_idx=int(step_idx),
                sample_id=self._sample_id or "unknown",
                T_C=T_C, rb_ohm=rb_ohm, sigma_S_cm=sigma_S_cm,
                qc_grade=qc_grade, governance_verdict=governance_verdict,
            )
            self._emit_event("MEMORY_POINT", {"step_idx": step_idx, **res})
        except Exception as exc:  # noqa: BLE001
            self._emit_event("MEMORY_ERROR", {"step_idx": step_idx, "error": str(exc)})

    def _finalize_memory(self):
        """收尾:多轮一致性 + 跨域守卫 + 决策保持压缩证书,落 runs/<id>/agent_memory_summary.json。"""
        if not self._enable_memory or self._agent_memory is None or not self._memory_bridge:
            return
        try:
            summary = self._memory_bridge.finalize(
                self._agent_memory,
                sample_id=self._sample_id or "unknown",
                foreign_item_id=self._memory_foreign_id,
            )
            if self._run_id:
                out = RUNS_DIR / self._run_id / "agent_memory_summary.json"
                out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("MEMORY_FINALIZE", summary)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("MEMORY_ERROR", {"stage": "finalize", "error": str(exc)})

    def _memory_projection_for_prompt(self) -> Optional[Dict[str, Any]]:
        """把 R²-Memory 的治理角色投影取出,供 agent 决策 prompt 注入。

        这是 R²-Memory **被 agent 真正消费** 的读路径(此前只有"写"接进了 live):
        agent 看到的是经写门/用途门/来源域守卫后的视图,且外域参照带
        ``usable_as_training_label=False``。整体 fail-safe:不可用 → None。
        """
        bridge = self._ensure_memory()
        if not bridge or self._agent_memory is None:
            return None
        try:
            return bridge.read_projection(self._agent_memory, max_items=10)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("MEMORY_ERROR", {"stage": "projection", "error": str(exc)})
            return None

    def _c3_snapshot(self) -> Optional[Dict[str, Any]]:
        """逐点 C³-Harness 收敛证书快照,供 agent 决策 prompt 注入。

        与收尾 ``_finalize_c3`` 同源(都走 ``shadow_convergence``),但这里 legacy
        verdict 取 "continue"(扫描进行中),据已累计的 Rb-ACT 计量不确定度 + 复现地板
        给出 recommended_action / delta_vs_legacy,让 LLM 在"继续/收敛"上对齐治理层。
        整体 fail-safe:不可用 → None。
        """
        if not self._enable_c3:
            return None
        try:
            import sys as _sys
            base = Path(__file__).resolve().parents[2]
            p = str(base / "stage1_optimization")
            if p not in _sys.path:
                _sys.path.insert(0, p)
            from scientific_convergence import shadow_convergence
        except Exception:
            return None
        try:
            metro = sorted(self._rbact_metro_dex)
            metro_med = metro[len(metro) // 2] if metro else 0.0
            termination = {
                "verdict": "continue", "triggered_by": [],
                "convergence": {}, "progress": {}, "budget": {},
            }
            cert = shadow_convergence(
                termination,
                metrological_uncertainty_dex=float(metro_med),
                repro_replicates_have=1,
                repro_replicates_required=3,
                claim_stability=1.0,
                rb_act_active_requests=list(self._rbact_active_requests),
            )
            d = cert.to_dict()
            return {
                "recommended_action": d.get("recommended_action"),
                "delta_vs_legacy": d.get("delta_vs_legacy"),
                "reasons": d.get("reasons"),
                "metrological_uncertainty_dex_median": metro_med,
                "reproducibility": {"have": 1, "required": 3},
                "active_requests": list(self._rbact_active_requests),
                "n_rbact_points": len(metro),
            }
        except Exception as exc:  # noqa: BLE001
            self._emit_event("C3_UNAVAILABLE", {"stage": "snapshot", "error": str(exc)})
            return None

    # ------------------------------------------------------------------
    # Stage3 机理推理链接 live（GPT 迁移发现愿景）—— 收尾真实 LLM 驱动
    #   证据(S03) → 假设(S04,真 LLM) → 文献(S05) → 机理仲裁(S06,真 LLM)
    #   → 可迁移设计原则(S06b,真 LLM)。opt-in / fail-safe,绝不影响测量与入库。
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_rn_from_sample(sample_id: Optional[str]):
        """从样品名解析 R/N(如 ATP-R0.186-N1.029-...)。解析不到返回 (None, None)。"""
        import re as _re
        if not sample_id:
            return None, None
        r = _re.search(r"R([0-9]*\.?[0-9]+)", sample_id)
        n = _re.search(r"N([0-9]*\.?[0-9]+)", sample_id)
        return (float(r.group(1)) if r else None, float(n.group(1)) if n else None)

    def _run_stage3_reasoning(self, loop_status: str):
        """收尾把真实全温区测量喂进 stage3 机理推理链(真实 LLM)。落
        runs/<id>/stage3_mechanism/。整体 fail-safe:任何失败只记事件。"""
        if not self._enable_stage3_reasoning:
            return
        try:
            import sys as _sys
            base = Path(__file__).resolve().parents[2]  # V1.0-qianduan-mainline
            s3_src = str(base / "stage3_mechanism" / "src")
            if s3_src not in _sys.path:
                _sys.path.insert(0, s3_src)
            from s8_stage3.adapters.live_seed_adapter import (
                build_seed_from_live, run_mechanism_reasoning,
            )
        except Exception as exc:  # noqa: BLE001
            self._emit_event("STAGE3_REASONING_UNAVAILABLE", {"error": str(exc)})
            return

        # LLM 配置:与 phase_detect / stage1 同一把 OpenRouter key。
        api_key = self._agent_api_key or _read_llm_key_from_env_file()
        if not api_key:
            self._emit_event("STAGE3_REASONING_SKIPPED", {"reason": "no LLM api key"})
            return
        base_url = os.environ.get("LLM_BASE_URL") or "https://openrouter.ai/api/v1"
        model = os.environ.get("LLM_MODEL") or "openai/gpt-5.4"

        try:
            points = []
            for m in self._measurements:
                if not m.get("success"):
                    continue
                T_C = m.get("temperature_C")
                T_K = m.get("temperature_K")
                if T_K is None and T_C is not None:
                    T_K = T_C + 273.15
                sigma = m.get("conductivity_S_cm") or m.get("sigma_S_cm")
                if T_K is None or sigma is None:
                    continue
                points.append({
                    "T_C": T_C, "T_K": T_K, "rb_ohm": m.get("rb_ohm"),
                    "sigma_S_cm": sigma, "qc_grade": m.get("qc_grade"),
                    "r_squared": m.get("r_squared"),
                })
            if len(points) < 5:
                self._emit_event("STAGE3_REASONING_SKIPPED",
                                 {"reason": f"too few points ({len(points)})"})
                return

            arr = self._global_arrhenius if isinstance(self._global_arrhenius, dict) else None
            transitions = (arr or {}).get("transition_temps_K") or []
            R, N = self._parse_rn_from_sample(self._sample_id)

            self._emit_event("STAGE3_REASONING_STARTED", {
                "n_points": len(points), "n_transitions": len(transitions),
                "R": R, "N": N, "model": model,
            })

            seed = build_seed_from_live(
                points, sample_id=self._sample_id or "unknown",
                R=R if R is not None else 0.0, N=N if N is not None else 0.0,
                transitions_K=transitions, arrhenius=arr,
            )
            out_dir = (RUNS_DIR / self._run_id / "stage3_mechanism") if self._run_id else (base.parent / "experiments" / "outputs" / "stage3_live_tmp")
            info = run_mechanism_reasoning(
                seed, out_dir, api_key=api_key, base_url=base_url, model=model,
                llm_mode="live", literature_mode="api", enable_cache=False,
            )
            summary = {k: info[k] for k in (
                "output_dir", "literature_status", "n_llm_calls", "n_real_llm_calls",
                "real_call_models", "real_call_steps", "n_evidence_cards", "n_hypotheses",
                "selected_hypothesis_id", "mechanism_label", "n_design_principles",
                "step_results",
            )}
            if self._run_id:
                out = RUNS_DIR / self._run_id / "stage3_reasoning_summary.json"
                out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("STAGE3_REASONING_COMPLETED", summary)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("STAGE3_REASONING_ERROR", {"error": str(exc)})

    # ------------------------------------------------------------------
    # Epistemic OS（GPT 三大原创方向的可计算对象）—— 收尾对真实 σ(T) 真实运算。
    #   方案一 不可辨识性证书 / 方案三 最小判别实验集 / 方案二 anytime-valid e-process。
    #   纯 numpy/scipy、不调 LLM;opt-in / fail-safe(失败只记事件,绝不影响测量/入库)。
    # ------------------------------------------------------------------
    def _run_epistemic(self, loop_status: str):
        if not self._enable_epistemic:
            return
        try:
            import sys as _sys
            import math as _math
            repo = Path(__file__).resolve().parents[3]   # acid-in-clay-close
            nda = str(repo / "V1.0-qianduan-mainline" / "analysis")
            if nda not in _sys.path:
                _sys.path.insert(0, nda)
            from epistemic import observability_certificate as _OC
            from epistemic import min_discriminating_set as _MDS
            from epistemic import eprocess_falsification as _EF
            import numpy as _np
        except Exception as exc:  # noqa: BLE001
            self._emit_event("EPISTEMIC_UNAVAILABLE", {"error": str(exc)})
            return
        try:
            T, S = [], []
            for m in self._measurements:
                if not m.get("success"):
                    continue
                tk = m.get("temperature_K")
                if tk is None and m.get("temperature_C") is not None:
                    tk = m["temperature_C"] + 273.15
                sg = m.get("conductivity_S_cm") or m.get("sigma_S_cm")
                if tk and sg and sg > 0:
                    T.append(float(tk)); S.append(float(sg))
            if len(T) < 6:
                self._emit_event("EPISTEMIC_SKIPPED", {"reason": f"too few points ({len(T)})"})
                return
            T = _np.array(T); y = _np.log(_np.array(S))
            o = _np.argsort(T); T, y = T[o], y[o]

            out_dir = (RUNS_DIR / self._run_id / "epistemic") if self._run_id else \
                (repo / "experiments" / "outputs" / "epistemic_live_tmp")
            cert = _OC.build_certificate(T, y, delta=0.05, label=self._sample_id or "live")
            _OC.write_certificate(cert, out_dir / "observability_certificate.json")
            mds = _MDS.build_min_discriminating_set(T, y, delta=0.05, label=self._sample_id or "live")
            _MDS.write_result(mds, out_dir / "min_discriminating_set.json")
            ef = _EF.run_falsification_on_sigmaT(T, y, alpha=0.05, holdout_frac=0.45,
                                                 label=self._sample_id or "live", n_type_i_sims=8000)
            _EF.write_result(ef, out_dir / "eprocess_falsification.json")

            summary = {
                "n_points": int(len(T)),
                "aic_best_model": cert.get("aic_best_model"),
                "equivalence_classes": cert.get("equivalence_classes"),
                "n_unidentifiable_pairs": cert.get("n_unidentifiable_pairs"),
                "min_set_status": mds.get("compilation", {}).get("status"),
                "min_set_T_C": mds.get("minimal_set", {}).get("exact_optimal", {}).get("action_T_C"),
                "eprocess_crossed": ef.get("eprocess", {}).get("crossed"),
                "eprocess_log_E_max": ef.get("eprocess", {}).get("log_E_max"),
                "anytime_valid_ok": ef.get("type_i_control", {}).get("anytime_valid_ok"),
                "claim_escalation_allowed": ef.get("claim_escalation_allowed"),
                "output_dir": str(out_dir),
            }
            if self._run_id:
                (RUNS_DIR / self._run_id / "epistemic_summary.json").write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("EPISTEMIC_CERTIFICATE_COMPLETED", summary)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("EPISTEMIC_ERROR", {"error": str(exc)})

    # ------------------------------------------------------------------
    # Epistemic OS（阻抗级正问题 P13-A）—— 收尾对真实 EIS 谱做谱级机制辨识。
    #   把 GPT 的 impedance_forward_operator 从离线接进 live 收尾:对本 run 真机谱
    #   拟合三竞争等效电路(single_bulk/bulk_electrode/two_population),给 AIC 权重
    #   / Fisher λ_min 谱级可观测性 / 被动性,并与 σ(T) 层证书互证机制类别。
    #   纯 numpy/scipy、不调 LLM;复用 _enable_epistemic 开关;fail-safe(失败只记事件)。
    # ------------------------------------------------------------------
    def _run_epistemic_impedance(self, loop_status: str):
        if not self._enable_epistemic:
            return
        try:
            import sys as _sys
            repo = Path(__file__).resolve().parents[3]   # acid-in-clay-close
            nda = str(repo / "V1.0-qianduan-mainline" / "analysis")
            if nda not in _sys.path:
                _sys.path.insert(0, nda)
            from epistemic import impedance_models as _IM
            import numpy as _np
        except Exception as exc:  # noqa: BLE001
            self._emit_event("EPISTEMIC_IMPEDANCE_UNAVAILABLE", {"error": str(exc)})
            return
        try:
            # 收集有真机谱(freq/z_real/z_imag)的成功点。
            spectra = []
            for m in self._measurements:
                if not m.get("success"):
                    continue
                f = m.get("frequencies"); zr = m.get("z_real"); zi = m.get("z_imag")
                if not (f and zr and zi) or len(f) < 10:
                    continue
                spectra.append({
                    "T_C": m.get("temperature_C"), "rb_ohm": m.get("rb_ohm"),
                    "f": _np.asarray(f, float), "zr": _np.asarray(zr, float),
                    "zi": _np.asarray(zi, float), "qc": m.get("qc_grade"),
                })
            if len(spectra) < 5:
                self._emit_event("EPISTEMIC_IMPEDANCE_SKIPPED",
                                 {"reason": f"too few spectra ({len(spectra)})"})
                return
            spectra.sort(key=lambda s: (s["T_C"] if s["T_C"] is not None else 0.0))

            def _bulk_R(fit):
                th = fit.theta
                if fit.model == "two_population":
                    return float(th[1] + th[4])
                return float(th[1])

            rows = []
            n_passive = n_finite = n_goodfit = n_lam = 0
            per_T_best = []
            for s in spectra:
                fits = _IM.fit_all_mechanisms(s["f"], s["zr"], s["zi"])
                w = _IM.aic_weights(fits)
                best = max(w, key=lambda k: (w[k] if _np.isfinite(w[k]) else -1.0))
                bf = fits[best]
                rb_best = _bulk_R(bf)
                if bf.ok and _np.isfinite(rb_best):
                    n_finite += 1
                if all(f.passive for f in fits.values() if f.ok):
                    n_passive += 1
                if bf.ok and _np.isfinite(bf.weighted_resid_rms) and bf.weighted_resid_rms < 0.35:
                    n_goodfit += 1
                if _np.isfinite(bf.lambda_min):
                    n_lam += 1
                per_T_best.append((s["T_C"], best))
                rows.append({
                    "T_C": s["T_C"], "qc": s["qc"], "rb_measured": s["rb_ohm"],
                    "best_mechanism": best, "best_bulk_R": rb_best,
                    "best_wrms": bf.weighted_resid_rms, "best_lambda_min": bf.lambda_min,
                    "best_cond": bf.condition_number, "best_invariants": bf.invariants,
                    "aic_weights": {k: (round(v, 3) if _np.isfinite(v) else None)
                                    for k, v in w.items()},
                })

            # 体相 R 趋势一致性(诚实:绝对量级在电极阻塞下弱可辨识,只看秩相关)。
            rho = None
            try:
                from scipy.stats import spearmanr
                pairs = [(r["rb_measured"], r["best_bulk_R"]) for r in rows
                         if r["rb_measured"] and r["best_bulk_R"]
                         and r["rb_measured"] > 0 and r["best_bulk_R"] > 0]
                if len(pairs) >= 4:
                    rho, _p = spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
                    rho = float(rho)
            except Exception:  # noqa: BLE001
                rho = None

            coldest = sorted([x for x in per_T_best if x[0] is not None],
                             key=lambda x: x[0])[:3]
            cold_multi = sum(1 for (_t, b) in coldest
                             if b in ("two_population", "bulk_electrode"))
            distinct = sorted({b for (_t, b) in per_T_best})

            # 谱级稳健可辨识量:冷端 vs 暖端最优机制体相 R 的量级(相变致总阻抗上升)。
            # 绝对体相 R 在电极阻塞下弱可辨识(见 note),但冷/暖端量级差异稳健可见。
            def _med(vals):
                v = sorted(x for x in vals if x is not None and _np.isfinite(x) and x > 0)
                return float(v[len(v) // 2]) if v else None
            warm_R = _med([r["best_bulk_R"] for r in rows
                           if r["T_C"] is not None and r["T_C"] > -10.0])
            cold_R = _med([r["best_bulk_R"] for r in rows
                           if r["T_C"] is not None and r["T_C"] < -40.0])
            cold_gt_warm = bool(warm_R and cold_R and cold_R > warm_R)

            out_dir = (RUNS_DIR / self._run_id / "epistemic") if self._run_id else \
                (repo / "experiments" / "outputs" / "epistemic_live_tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            detail = {
                "n_spectra": len(spectra),
                "T_C_range": [rows[0]["T_C"], rows[-1]["T_C"]],
                "n_passive": n_passive, "n_finite_bulkR": n_finite,
                "n_goodfit_wrms_lt_0p35": n_goodfit, "n_finite_lambda_min": n_lam,
                "bulkR_vs_measured_spearman_rho": rho,
                "bulkR_median_warm": warm_R, "bulkR_median_cold": cold_R,
                "cold_bulkR_gt_warm": cold_gt_warm,
                "cold3_best_mechanisms": [(round(t, 1), b) for (t, b) in coldest],
                "distinct_mechanisms": distinct,
                "note": ("谱级绝对体相 R 在电极阻塞下弱可辨识(R∥CPE 向纯 CPE 简并);"
                         "故不强求逐点秩相关达高值——只如实报告 ρ(方向一致)。"
                         "谱级稳健可辨识的是冷/暖端体相 R 量级差(相变致总阻抗上升)。"
                         "绝对量级以 reverse_zero_crossing 为准;本分析仅收尾运行,不参与逐点控制。"),
                "fits": rows,
            }
            (out_dir / "impedance_summary.json").write_text(
                json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

            summary = {
                "n_spectra": len(spectra),
                "T_C_range": [rows[0]["T_C"], rows[-1]["T_C"]],
                "n_passive": n_passive,
                "n_goodfit_wrms_lt_0p35": n_goodfit,
                "n_finite_lambda_min": n_lam,
                "bulkR_vs_measured_spearman_rho": rho,
                "bulkR_median_warm": warm_R, "bulkR_median_cold": cold_R,
                "cold_bulkR_gt_warm": cold_gt_warm,
                "cold3_best_mechanisms": [b for (_t, b) in coldest],
                "distinct_mechanisms": distinct,
                "cold_prefers_multi_arc": bool(cold_multi >= 2),
                "output_dir": str(out_dir),
            }
            self._emit_event("EPISTEMIC_IMPEDANCE", summary)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("EPISTEMIC_IMPEDANCE_ERROR", {"error": str(exc)})

    # ------------------------------------------------------------------
    # 多角色 LLM 证伪市场接 live 收尾（Gap3 / P13-B）—— 真 OpenRouter 调用。
    #   收尾对本 run 真实 σ(T) 跑 Proposer/Falsifier/Auditor(真 LLM)+ Referee 确定性真实数据结算,
    #   严格适当评分(EpistemicAccount)更新信誉/资本;过度自信稻草人对照应被证伪、信誉下跌。
    #   opt-in(_enable_falsification_market,因真 LLM 有成本);fail-safe(失败只记事件,绝不影响入库)。
    # ------------------------------------------------------------------
    def _run_falsification_market(self, loop_status: str):
        if not self._enable_falsification_market:
            return
        try:
            import sys as _sys
            repo = Path(__file__).resolve().parents[3]   # acid-in-clay-close
            nda = str(repo / "V1.0-qianduan-mainline" / "analysis")
            skills = str(repo / "V1.0-qianduan-mainline" / "stage1_optimization")
            for p in (nda, skills):
                if p not in _sys.path:
                    _sys.path.insert(0, p)
            from epistemic import falsification_market as _FM
            import numpy as _np
        except Exception as exc:  # noqa: BLE001
            self._emit_event("FALSIFICATION_MARKET_UNAVAILABLE", {"error": str(exc)})
            return
        try:
            T, S = [], []
            for m in self._measurements:
                if not m.get("success"):
                    continue
                tk = m.get("temperature_K")
                if tk is None and m.get("temperature_C") is not None:
                    tk = m["temperature_C"] + 273.15
                sg = m.get("conductivity_S_cm") or m.get("sigma_S_cm")
                if tk and sg and sg > 0:
                    T.append(float(tk)); S.append(float(sg))
            if len(T) < 8:
                self._emit_event("FALSIFICATION_MARKET_SKIPPED",
                                 {"reason": f"too few points ({len(T)})"})
                return
            T = _np.asarray(T, float); y = _np.log(_np.asarray(S, float))

            client = _FM.LLMClient()
            if not client.available:
                self._emit_event("FALSIFICATION_MARKET_SKIPPED",
                                 {"reason": "no LLM_API_KEY (.env) — 真 LLM 不可用,诚实跳过"})
                return

            market = _FM.run_market(T, y, client=client, n_seed=6, n_rounds=4,
                                    include_strawman=True)

            out_dir = (RUNS_DIR / self._run_id / "epistemic") if self._run_id else \
                (repo / "experiments" / "outputs" / "epistemic_live_tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "falsification_market.json").write_text(
                json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8")

            rep = market.get("reputation", {})
            llm_agent = next((a for a in rep if a.startswith("LLM_Proposer")), None)
            straw = "Strawman_Overconfident"
            summary = {
                "llm_used": market.get("llm_used"),
                "n_real_llm_calls": len(market.get("llm_calls", [])),
                "real_call_roles": sorted({c.get("role") for c in market.get("llm_calls", [])}),
                "reputation": rep,
                "brier": market.get("brier"),
                "domain_T_range": market.get("domain_T_range"),
                "overconfident_strawman_beaten": bool(
                    llm_agent and straw in rep
                    and rep.get(llm_agent, 0.0) > rep.get(straw, 1.0)),
                "output_dir": str(out_dir),
            }
            self._emit_event("MARKET_SETTLED", summary)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("FALSIFICATION_MARKET_ERROR", {"error": str(exc)})

    # ------------------------------------------------------------------
    # ESAS-OS 2.0 C³-Harness（P2）—— 在 legacy "扫完即停" 之上 shadow 收敛证书。
    #   不变量:C³ 的"停" ⊆ legacy 的"停"(只推迟、绝不更早停);默认只记录不夺权。
    # ------------------------------------------------------------------
    def _finalize_c3(self, loop_status: str):
        """收尾 shadow 收敛证书:喂真实 Rb-ACT 计量不确定度(median sigma_log10_total)+
        复现地板(单片 → required 3 未满)+ 主动测量请求。落 runs/<id>/c3_convergence_certificate.json。"""
        if not self._enable_c3:
            return
        try:
            import sys as _sys
            base = Path(__file__).resolve().parents[2]
            p = str(base / "stage1_optimization")
            if p not in _sys.path:
                _sys.path.insert(0, p)
            from scientific_convergence import shadow_convergence
        except Exception as exc:  # noqa: BLE001
            self._emit_event("C3_UNAVAILABLE", {"error": str(exc)})
            return
        try:
            metro = sorted(self._rbact_metro_dex)
            metro_med = metro[len(metro) // 2] if metro else 0.0
            # legacy:扫完所有设定点 → 可结束(loop_can_end);否则不结束。
            legacy_verdict = "loop_can_end" if loop_status == "completed" else "continue"
            termination = {
                "verdict": legacy_verdict,
                "triggered_by": ["stage0_sweep_complete"] if legacy_verdict == "loop_can_end" else [],
                "convergence": {}, "progress": {}, "budget": {},
            }
            cert = shadow_convergence(
                termination,
                metrological_uncertainty_dex=float(metro_med),
                repro_replicates_have=1,        # 单次全温区扫描 = 1 独立片(诚实:within-run)
                repro_replicates_required=3,    # between-specimen 0.252 dex 复现地板需 ≥3
                claim_stability=1.0,            # live 无 claim_graph 投影 → 默认 1
                rb_act_active_requests=list(self._rbact_active_requests),
            )
            d = cert.to_dict()
            d["evidence"] = {
                "n_rbact_points": len(metro),
                "metrological_uncertainty_dex_median": metro_med,
                "metrological_uncertainty_dex_max": (metro[-1] if metro else None),
                "rb_act_active_requests": list(self._rbact_active_requests),
                "loop_status": loop_status,
            }
            if self._run_id:
                out = RUNS_DIR / self._run_id / "c3_convergence_certificate.json"
                out.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            # H1:把真实计量证据落到 campaign 输出目录,供**随后的 Stage1 终止聚合**
            #   (evaluate_termination 自动加载 output_dir/c3_evidence.json)真消费 → C³
            #   在证据不足时单调安全地推迟停机。fail-safe;legacy verdict 永不改。
            try:
                if self._stage1_output_dir:
                    ev_dir = Path(self._stage1_output_dir)
                    ev_dir.mkdir(parents=True, exist_ok=True)
                    c3_evidence = {
                        "metrological_uncertainty_dex": metro_med,
                        "repro_replicates_have": 1,
                        "repro_replicates_required": 3,
                        "claim_stability": 1.0,
                        "rb_act_active_requests": list(self._rbact_active_requests),
                        "source_run_id": self._run_id,
                    }
                    (ev_dir / "c3_evidence.json").write_text(
                        json.dumps(c3_evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as _exc:  # noqa: BLE001
                self._emit_event("C3_ERROR", {"stage": "evidence_persist", "error": str(_exc)})
            self._emit_event("C3_SHADOW_CERTIFICATE", {
                "recommended_action": d["recommended_action"],
                "delta_vs_legacy": d["delta_vs_legacy"],
                "c3_stop": d["c3_stop"], "legacy_stop": d["legacy_stop"],
                "consistent_with_legacy": d["consistent_with_legacy"],
                "reasons": d["reasons"],
                "metro_dex_median": metro_med,
            })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("C3_ERROR", {"stage": "finalize", "error": str(exc)})

    def _finalize_rb_r4_activation(self):
        """H4 收尾:据三条件门(rb_r4_activate + 预注册 gates_pass + 人审签核)决定是否旁产
        σ_v2 + delta 喂 BO。缺任一条件恒回退 legacy;legacy 永不覆盖。落
        runs/<id>/rb_act_r4_activation.json。fail-safe。"""
        if not self._rbact_results:
            return
        try:
            import sys as _sys
            p = str(PROJECT_ROOT / "stage0_measurement")
            if p not in _sys.path:
                _sys.path.insert(0, p)
            import rb_act as _RB
        except Exception as exc:  # noqa: BLE001
            self._emit_event("RB_R4_UNAVAILABLE", {"error": str(exc)})
            return
        try:
            thickness = self._thickness_cm if self._thickness_cm is not None else 0.1
            area = self._area_cm2 if self._area_cm2 is not None else 1.96
            contract = _RB.build_r4_prereg_contract(
                sample_id=self._sample_id, note="H4 live 收尾激活审计")
            audit = _RB.audit_series(self._rbact_results, contract=contract)
            act = _RB.build_activation(
                self._rbact_results, contract=contract, audit=audit,
                rb_r4_activate=self._rb_r4_activate, human_signoff=self._rb_r4_signoff,
                thickness_cm=thickness, area_cm2=area)
            if self._run_id:
                out = RUNS_DIR / self._run_id / "rb_act_r4_activation.json"
                out.write_text(json.dumps(
                    {"contract": contract, "audit": audit, "activation": act},
                    ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("RB_R4_ACTIVATION", {
                "rb_r4_active": act["rb_r4_active"],
                "reasons": act["reasons"],
                "gates_pass": act["gates_pass"],
                "n_points": act["n_points"], "n_paired": act["n_paired"],
                "legacy_overwritten": act["legacy_overwritten"],
                "spearman_legacy_vs_v2": act["spearman_legacy_vs_v2"],
                "median_abs_delta_log10_sigma": act["median_abs_delta_log10_sigma"],
                "bo_not_degraded": act["bo_not_degraded"],
            })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("HARNESS_GOVERNANCE_ERROR",
                             {"stage": "rb_r4_activation_finalize", "error": str(exc)})

    # ------------------------------------------------------------------
    # ESAS-OS 2.0 measurement_txn 真门控（P3）—— entered_bo 从"只记事件"升级为真门控。
    #   收尾切 committed/rejected;rejected_T_C 在 post-processing 过滤 Stage0 bundle。
    # ------------------------------------------------------------------
    def _commit_gate_enforces(self) -> bool:
        """P13-D:测量提交路径是否真门控(挡被拒点出 BO)。
        canary/enforce=真挡;shadow=只记录不挡(legacy 行为)。**只影响测量提交,绝不影响温控/CHI。**"""
        return self._commit_gate_mode in ("canary", "enforce")

    def _finalize_fault_injection(self):
        """G-2 真机故障注入收尾:落 runs/<id>/fault_injection_summary.json(验收锚点)。fail-safe。
        验收 = 每个注入的坏点都被治理拦截(caught=True/entered_bo=False),且被 commit gate 剔出 BO。"""
        try:
            recs = list(self._fault_injections)
            n = len(recs)
            n_caught = sum(1 for r in recs if r.get("caught"))
            summary = {
                "requested": list(self._inject_faults),
                "n_injected": n,
                "n_caught": n_caught,
                "all_caught": bool(n > 0 and n_caught == n),
                "any_entered_bo": bool(any(r.get("entered_bo") for r in recs)),
                "injections": recs,
                "note": ("G-2 真机故障注入:仅治理层输入被改,温控/CHI 物理命令未受影响;"
                         "验收=注入坏点全被治理拦截且未进 BO。"),
            }
            if self._run_id:
                out = RUNS_DIR / self._run_id / "fault_injection_summary.json"
                out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("FAULT_INJECTION_SUMMARY", {
                "n_injected": n, "n_caught": n_caught,
                "all_caught": summary["all_caught"], "any_entered_bo": summary["any_entered_bo"],
            })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("HARNESS_GOVERNANCE_ERROR",
                             {"stage": "fault_injection_finalize", "error": str(exc)})

    def _finalize_commit_gate(self):
        """据逐点 entered_bo 切 committed/rejected 视图,落 runs/<id>/committed_measurements.json。"""
        if not self._enable_commit_gate or not self._txn_rows:
            return
        try:
            import sys as _sys
            base = Path(__file__).resolve().parents[2]
            p = str(base / "stage1_optimization")
            if p not in _sys.path:
                _sys.path.insert(0, p)
            from scientific_harness.commit_gate import build_committed_view
        except Exception as exc:  # noqa: BLE001
            self._emit_event("COMMIT_GATE_UNAVAILABLE", {"error": str(exc)})
            return
        try:
            view = build_committed_view(self._txn_rows)
            self._commit_rejected_T_C = list(view.get("rejected_T_C") or [])
            if self._run_id:
                out = RUNS_DIR / self._run_id / "committed_measurements.json"
                out.write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("COMMIT_GATE", {
                "n_total": view["n_total"], "n_committed": view["n_committed"],
                "n_rejected": view["n_rejected"],
                "rejected_T_C": view["rejected_T_C"],
                "commit_gate_mode": self._commit_gate_mode,
            })
        except Exception as exc:  # noqa: BLE001
            self._emit_event("COMMIT_GATE_ERROR", {"stage": "finalize", "error": str(exc)})

    def _real_measurement_loop(self, sample_id: str, kwargs: dict):
        """Real hardware measurement loop using Stage 0 controller + real analysis.

        After each measurement the loop checks for pending agent commands
        (RE_MEASURE, BACKTRACK, TRIGGER_FINE_SCAN) just like the simulation loop.
        """
        t_start = kwargs.get("t_start", 20.0)
        t_end = kwargs.get("t_end", -85.0)
        t = t_start
        step_idx = 0
        backtrack_default_delta = 10.0
        loop_status = "running"
        loop_error: Optional[str] = None
        next_is_reheat = False

        # ----- Resume: skip start-temperature cool down if state has points -----
        if self._resume_skip_initial_cool and self._measurements:
            try:
                last = self._measurements[-1]
                last_T = last.get("temperature_C")
                if last_T is not None:
                    t = float(last_T) - self._step_size
                    step_idx = int(last.get("step_idx") or len(self._measurements))
                    self._emit_event("RESUME_CONTINUE", {
                        "from_step_idx": step_idx,
                        "next_target_C": t,
                        "step_size": self._step_size,
                    })
            except Exception:  # noqa: BLE001
                pass
        else:
            # ----- Start-of-run cool to T_start (mirrors run_online.py) -----
            # Without this the first point at e.g. 26°C may run before the
            # chamber is at 26°C — exactly the "测试在到温前就开始了" bug.
            if self._workflow and not self._simulate:
                self._target_temperature = t_start
                self._emit_event("COOL_TO_START_STARTED", {"t_start_C": t_start})
                try:
                    set_res = self._workflow.set_temperature(t_start)
                except Exception as exc:  # noqa: BLE001
                    set_res = {"success": False, "error": str(exc)}
                # Even if the driver returns success, we still actively wait
                # for the chamber to actually arrive + stabilise at T_start.
                stability = self._wait_stable_temperature(t_start, -1)
                if not stability.get("stable"):
                    self._emit_event("COOL_TO_START_FAILED", {
                        "t_start_C": t_start,
                        "actual_C": stability.get("actual_temperature_C"),
                        "reason": stability.get("reason"),
                    })
                    if self._skip_on_unstable:
                        # Honour the user's "no bogus data" rule: stop the
                        # entire run rather than start measuring at the
                        # wrong temperature.
                        loop_status = "failed"
                        loop_error = "cool_to_start_failed"
                        self._running = False
                else:
                    self._emit_event("COOL_TO_START_DONE", {
                        "t_start_C": t_start,
                        "actual_C": stability.get("actual_temperature_C"),
                        "arrival_seconds": stability.get("arrival_seconds"),
                    })

        while self._running and t >= t_end:
            try:
                self._target_temperature = t

                if self._workflow:
                    set_res = self._workflow.set_temperature(t)
                    self._emit_event("SET_T", {
                        "target_temperature_C": t,
                        "step_idx": step_idx,
                        "driver_response": set_res if isinstance(set_res, dict) else None,
                    })
                else:
                    set_res = None

                # Wait for the controller to ACTUALLY reach and hold target
                # within eps for stability_duration seconds.  Returns a dict
                # describing whether stability was achieved.  When the last
                # Agent decision was a re-heat (FINE_GRAINED_SCAN going up),
                # use the enhanced settle path: thermal-inertia wait + 2x
                # stability window, mirroring run_online's _wait_for_stable_enhanced.
                if next_is_reheat:
                    stability = self._enhanced_wait_after_reheat(t, step_idx)
                    next_is_reheat = False
                else:
                    stability = self._wait_stable_temperature(t, step_idx)
                actual_t = stability["actual_temperature_C"]

                # Hard guard: never start a CHI measurement at the wrong
                # temperature.  This is the rule the user explicitly demanded.
                if not stability["stable"]:
                    self._emit_event("MEASUREMENT_SKIPPED", {
                        "step_idx": step_idx,
                        "target_temperature_C": t,
                        "actual_temperature_C": actual_t,
                        "reason": stability.get("reason"),
                    })
                    if self._skip_on_unstable:
                        # Move on to the next setpoint instead of looping
                        # forever at this one — but record the skip and DO
                        # NOT collect bogus EIS data.
                        t -= self._step_size
                        step_idx += 1
                        continue
                    else:
                        # Abort the whole run rather than corrupt the dataset.
                        self._running = False
                        break

                self._emit_event("EIS_RUN", {
                    "temperature_C": t,
                    "chamber_actual_C": actual_t,
                    "step_idx": step_idx,
                })

                # Drive CHI (real GUI automation): opens CHI if needed, starts
                # a measurement, waits, saves the .txt and returns parsed
                # frequency / Z' / Z" arrays.
                # 文件名 T 段用设定档 t；Rb/数据库仍用实测 actual_t
                chi_result = self._trigger_chi_measurement(t, step_idx, chamber_actual_C=actual_t)

                rb_ohm = None
                conductivity = None
                fit_method = "unknown"
                r2_val = None
                qc_grade = "UNKNOWN"
                rb_failure_reason: Optional[str] = None
                rb_result = None  # 治理旁路要用(含完整 eis_pipeline raw);失败时保持 None

                if chi_result.get("success") and chi_result.get("frequencies") is not None:
                    try:
                        rb_result = self._do_rb_fitting(
                            chi_result["frequencies"],
                            chi_result.get("z_real", []),
                            chi_result.get("z_imag", []),
                            actual_t,
                        )
                        if rb_result.get("success"):
                            rb_ohm = rb_result.get("rb_ohm")
                            conductivity = rb_result.get("conductivity_S_per_cm")
                            fit_method = rb_result.get("rb_method", "unknown")
                            r2_val = rb_result.get("fit_quality")
                            qc_grade = (
                                "A" if (r2_val or 0) > 0.997
                                else "B" if (r2_val or 0) > 0.993
                                else "C" if (r2_val or 0) > 0.98
                                else "D"
                            )
                        else:
                            rb_failure_reason = rb_result.get("failure_reason") or "rb_fit_failed"
                    except Exception as exc:
                        rb_failure_reason = f"rb_fit_exception: {exc}"
                else:
                    rb_failure_reason = chi_result.get("error") or "chi_measurement_failed"

                # Keep the raw EIS arrays so the Analysis page (and the
                # Monitor's Nyquist preview) can plot the actual spectrum
                # without going back to disk.  Coerce to plain Python lists
                # (numpy arrays don't round-trip through JSON).
                def _to_list(x):
                    if x is None:
                        return None
                    try:
                        return [float(v) for v in x]
                    except Exception:  # noqa: BLE001
                        return None
                freqs_list = _to_list(chi_result.get("frequencies"))
                zr_list = _to_list(chi_result.get("z_real"))
                zi_list = _to_list(chi_result.get("z_imag"))

                measurement = {
                    "sample_id": sample_id,
                    "step_idx": step_idx,
                    "temperature_C": round(actual_t, 2),
                    "temperature_K": round(actual_t + 273.15, 2),
                    "rb_ohm": rb_ohm,
                    "conductivity_S_cm": conductivity,
                    "fit_method": fit_method,
                    "r_squared": r2_val,
                    "qc_grade": qc_grade,
                    "raw_eis_file": chi_result.get("output_file"),
                    "success": bool(chi_result.get("success") and rb_ohm is not None),
                    "failure_reason": rb_failure_reason,
                    "timestamp": datetime.now().isoformat(),
                    "frequencies": freqs_list,
                    "z_real": zr_list,
                    "z_imag": zi_list,
                    "n_eis_points": len(freqs_list) if freqs_list else 0,
                }
                self._measurements.append(measurement)

                # --- ESAS-OS 2.0 治理旁路（Phase 1，纯加法/fail-safe/默认开）---
                # 仅在本点拿到成功谱时逐点接 shadow + Rb-ACT + txn,推 3 个治理事件。
                # 整体失败只记 HARNESS_GOVERNANCE_ERROR,绝不影响上面的入库与下面的安全熔断。
                if self._enable_harness and chi_result.get("success") and freqs_list:
                    try:
                        self._run_point_governance(
                            step_idx=step_idx,
                            T_C=measurement["temperature_C"],
                            freq=chi_result.get("frequencies"),
                            zr=chi_result.get("z_real"),
                            zi=chi_result.get("z_imag"),
                            eis_result=(rb_result.get("raw") if isinstance(rb_result, dict) else None),
                            rb_result=rb_result,
                            output_file=chi_result.get("output_file"),
                            chamber_actual_C=actual_t,
                            setpoint_C=t,
                        )
                    except Exception as exc:  # noqa: BLE001
                        self._emit_event("HARNESS_GOVERNANCE_ERROR",
                                         {"step_idx": step_idx, "error": str(exc)})

                self._emit_event("Rb_FIT", {
                    "step_idx": step_idx,
                    "rb_ohm": rb_ohm,
                    "rb_method": fit_method,
                    "r_squared": r2_val,
                    "conductivity_S_cm": conductivity,
                    "temperature_C": measurement["temperature_C"],
                })
                self._emit_event("QC_GRADE", {
                    "step_idx": step_idx,
                    "qc_grade": qc_grade,
                    "r_squared": r2_val,
                })
                if self._enable_memory and chi_result.get("success") and freqs_list:
                    self._run_point_memory(
                        step_idx=step_idx,
                        T_C=measurement["temperature_C"],
                        rb_ohm=rb_ohm,
                        sigma_S_cm=conductivity,
                        qc_grade=qc_grade,
                        governance_verdict="cooling_sweep",
                    )
                # Keep the SocketIO payload small — frequencies/z_real/z_imag
                # can be 60+ floats each; the Analysis page pulls them via
                # /api/data/measurements/{i}/eis instead.
                lite_measurement = {
                    k: v for k, v in measurement.items()
                    if k not in ("frequencies", "z_real", "z_imag")
                }
                self._emit_event("MEASUREMENT_COMPLETED", lite_measurement)

                # ----- Safety fuses (mirror run_online.py finalize triggers) -----
                if not measurement["success"]:
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= self._max_consecutive_failures:
                        self._emit_event("SAFETY_CONSECUTIVE_FAIL_FUSE", {
                            "step_idx": step_idx,
                            "consecutive_failures": self._consecutive_failures,
                            "threshold": self._max_consecutive_failures,
                            "reason": "consecutive_measurement_failures",
                        })
                        loop_status = "failed"
                        loop_error = "consecutive_measurement_failures"
                        self._running = False
                        self._save_state_snapshot()
                        break
                else:
                    self._consecutive_failures = 0

                if (
                    measurement.get("rb_ohm") is not None
                    and measurement["rb_ohm"] > self._max_rb_ohm
                ):
                    self._emit_event("SAFETY_RB_FUSE", {
                        "step_idx": step_idx,
                        "rb_ohm": measurement["rb_ohm"],
                        "threshold": self._max_rb_ohm,
                        "reason": "rb_above_threshold",
                    })
                    loop_status = "completed_fused"
                    loop_error = f"rb_above_threshold ({measurement['rb_ohm']:.2e} > {self._max_rb_ohm:.2e})"
                    self._running = False
                    self._save_state_snapshot()
                    break

                if (
                    measurement.get("conductivity_S_cm") is not None
                    and measurement["conductivity_S_cm"] < self._min_conductivity_threshold
                ):
                    self._emit_event("SAFETY_CONDUCTIVITY_FUSE", {
                        "step_idx": step_idx,
                        "conductivity_S_cm": measurement["conductivity_S_cm"],
                        "threshold": self._min_conductivity_threshold,
                        "reason": "conductivity_below_threshold",
                    })
                    loop_status = "completed_fused"
                    loop_error = (
                        f"conductivity_below_threshold "
                        f"({measurement['conductivity_S_cm']:.2e} < {self._min_conductivity_threshold:.2e})"
                    )
                    self._running = False
                    self._save_state_snapshot()
                    break

                # Persist a resume snapshot after every successful point.
                self._save_state_snapshot()

                evidence = {
                    "evidence_id": f"EP-{sample_id}-{step_idx:04d}",
                    "evidence_type": "measurement",
                    "step_idx": step_idx,
                    "sample_id": sample_id,
                    "timestamp": measurement["timestamp"],
                    "payload": measurement,
                }
                self._save_evidence(step_idx, evidence)
                self._emit_event("EVIDENCE_PACKAGE_SAVED", {"evidence_id": evidence["evidence_id"], "step_idx": step_idx})

                if self._phase_detector:
                    try:
                        is_phase = self._phase_detector.add_point(measurement)
                        if is_phase:
                            self._emit_event("PHASE_TRANSITION_DETECTED", {
                                "temperature_C": actual_t,
                                "temperature_K": round(actual_t + 273.15, 2),
                            })
                            self.apply_policy(mode="FINE")
                    except Exception:
                        pass

                # 不在测量循环中跑分段 Arrhenius；finalize 见 _run_global_arrhenius。

                # Manual operator commands (RE_MEASURE / BACKTRACK / fine) win
                # over the Agent — they are explicit human overrides.
                cmd = self._consume_command()
                handled_cmd = False
                if cmd:
                    action = cmd["command"]
                    params = cmd.get("params", {})

                    if action == "RE_MEASURE":
                        self._emit_event("AGENT_RE_MEASURE", {"temperature_C": t, "step_idx": step_idx})
                        continue

                    if action == "BACKTRACK":
                        delta = params.get("backtrack_delta", backtrack_default_delta)
                        t = min(t + delta, t_start)
                        self.apply_policy(mode="FINE")
                        self._emit_event("AGENT_BACKTRACK", {
                            "new_temperature_C": t,
                            "delta": delta,
                            "mode": "FINE",
                        })
                        step_idx += 1
                        handled_cmd = True

                    elif action == "TRIGGER_FINE_SCAN":
                        self.apply_policy(mode="FINE")
                        self._emit_event("AGENT_FINE_SCAN", {"temperature_C": t})

                if handled_cmd:
                    continue

                # ----- Per-point Agent decision (LLM phase analysis) -----
                # If we are already inside an Agent-imposed FINE_GRAINED_SCAN
                # band we keep silent (mirrors online_workflow's fine-scan
                # mute behaviour) and just step down with the fine step.
                #
                # 用户固定策略：细扫带 = [触发点 trigger_T,  trigger_T + 10]，
                # 每步 -1°C，直到规划温度 ``t`` <= trigger_T 时退出细扫；之后
                # 下一个粗扫点 = trigger_T - coarse_step（例：-25 → -28）。
                # 用规划 t 判定（而不是 actual_t）可以避开腔体噪声 → 不会因
                # 0.5°C 抖动提前退出 / 多扫一格。
                in_fine_band = (
                    self._fine_scan_end_C is not None
                    and t > self._fine_scan_end_C
                )
                if in_fine_band:
                    prev_t = t
                    next_t = t - self._fine_step
                    # 单调下降护栏：精细测量绝不允许设定温度反向回升。
                    if next_t >= prev_t:
                        next_t = prev_t - 1.0
                    self._emit_event("AGENT_FINE_BAND_TICK", {
                        "step_idx": step_idx,
                        "current_temperature_C": actual_t,
                        "planned_temperature_C": prev_t,
                        "next_planned_temperature_C": next_t,
                        "trigger_temperature_C": self._fine_scan_end_C,
                        "fine_step": self._fine_step,
                    })
                    t = next_t
                    step_idx += 1
                    continue

                # 刚刚走完最后一个细扫点（t <= trigger_T）—— 退出细扫带，
                # 恢复粗扫策略，让 LLM 重新评估接下来的粗扫节奏。
                if self._fine_scan_end_C is not None and t <= self._fine_scan_end_C:
                    self._emit_event("AGENT_FINE_BAND_EXIT", {
                        "step_idx": step_idx,
                        "current_temperature_C": actual_t,
                        "trigger_temperature_C": self._fine_scan_end_C,
                    })
                    self._fine_scan_end_C = None
                    self._fine_trigger_T_C = None
                    self.apply_policy(mode="COARSE")

                decision = self._call_agent_decision(step_idx)
                # ESAS-OS 2.0 P5:自主覆盖动作过 ActionGate(唯一受控入口)。
                # shadow → 行为不变;enforce → 非 allowlist 动作被拦,降级安全默认。
                decision = self._gate_agent_decision(decision, step_idx)
                # Pass BOTH the planned setpoint t and the actual chamber
                # temperature actual_t.  CONTINUE uses the planned t to keep
                # the temperature grid clean (3°C ladder); FINE_GRAINED_SCAN
                # uses actual_t for safety-rail re-heat math.
                outcome = self._apply_agent_decision(decision, actual_t, step_idx, planned_t=t)

                if outcome["abort"]:
                    self._emit_event("AGENT_ABORT", {
                        "step_idx": step_idx,
                        "reason": (decision or {}).get("reasoning"),
                    })
                    self._running = False
                    break

                t = outcome["next_t"]
                next_is_reheat = bool(outcome.get("is_reheat"))
                step_idx += 1

            except Exception as e:
                self._emit_event("ERROR", {
                    "message": str(e),
                    "temperature_C": t,
                })
                loop_status = "failed"
                loop_error = str(e)
                time.sleep(5)

        # ----- Finalize: ALWAYS run, no matter how we exited -----
        self._running = False
        if loop_status == "running":
            loop_status = "completed"

        # 0) R²-Memory 收尾(决策保持压缩证书 + 跨域守卫 + 多轮一致性);fail-safe。
        if self._enable_memory:
            self._finalize_memory()
        # 0b) C³-Harness 收尾 shadow 收敛证书(喂真实 Rb-ACT 不确定度 + 复现地板);fail-safe。
        if self._enable_c3:
            self._finalize_c3(loop_status)
        # 0c) measurement_txn 真门控:切 committed/rejected 视图(rejected_T_C 后续过滤 bundle);fail-safe。
        if self._enable_commit_gate:
            self._finalize_commit_gate()
        # 0c2) G-2 真机故障注入收尾:落 fault_injection_summary.json(注入类型 / 是否被拦 / 是否进 BO);fail-safe。
        if self._inject_faults:
            self._finalize_fault_injection()
        # 0c3) H2 在线仪器见证收尾:落 instrument_witness_summary.json(在线见证 + 协议故障验收);fail-safe。
        if self._enable_instrument_witness:
            self._finalize_instrument_witness()
        # 0c4) H4 Rb-ACT R4 激活收尾:三条件门决定是否旁产 σ_v2+delta(替换态,须人审);fail-safe。
        self._finalize_rb_r4_activation()
        # 0b2) Stage3 机理推理链(GPT 迁移发现):真实 LLM 驱动 证据→假设→机理→设计原则;opt-in/fail-safe。
        if self._enable_stage3_reasoning:
            self._run_stage3_reasoning(loop_status)
        # 0b3) Epistemic OS(GPT 三大原创方向):不可辨识性证书/最小判别实验集/anytime-valid e-process;opt-in/fail-safe。
        if self._enable_epistemic:
            self._run_epistemic(loop_status)
        # 0b4) Epistemic OS 阻抗级正问题(P13-A):对真机 EIS 谱做谱级机制辨识(AIC/Fisher λ_min/被动性);opt-in/fail-safe。
        if self._enable_epistemic:
            self._run_epistemic_impedance(loop_status)
        # 0b5) 多角色 LLM 证伪市场(P13-B):对真实 σ(T) 跑 Proposer/Falsifier/Auditor 真 LLM + Referee 真数据结算;opt-in/fail-safe。
        if self._enable_falsification_market:
            self._run_falsification_market(loop_status)
        # 0d) ActionGate 审计:自主覆盖动作过 gate 的统计 + bypass 计数(应为 0)。
        try:
            n_blocked = sum(1 for d in self._action_gate_decisions if not d.get("dispatched"))
            summary_gate = {
                "harness_mode": self._harness_mode,
                "n_gated_autonomous_actions": len(self._action_gate_decisions),
                "n_blocked": n_blocked,
                "bypass_count": self._action_gate_bypass_count,
            }
            if self._run_id:
                (RUNS_DIR / self._run_id / "action_gate_summary.json").write_text(
                    json.dumps({**summary_gate, "decisions": self._action_gate_decisions},
                               ensure_ascii=False, indent=2), encoding="utf-8")
            self._emit_event("ACTION_GATE_SUMMARY", summary_gate)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("ACTION_GATE_ERROR", {"stage": "finalize", "error": str(exc)})

        # 1) Offline global Arrhenius competitive model (same as offline pipeline)
        try:
            self._run_global_arrhenius()
        except Exception as exc:  # noqa: BLE001
            self._emit_event("STAGE0_GLOBAL_ARRHENIUS_FAILED", {"error": str(exc)})

        # 2) Reheat the chamber to a safe room-temperature setpoint — CRITICAL.
        try:
            self._finalize_reheat()
        except Exception as exc:  # noqa: BLE001
            self._emit_event("FINALIZE_REHEAT_FAILED", {"error": str(exc)})

        # 3) Run manifest (online_run_manifest.json with all metadata).
        try:
            self._write_run_manifest(loop_status, error=loop_error)
        except Exception as exc:  # noqa: BLE001
            self._emit_event("RUN_MANIFEST_FAILED", {"error": str(exc)})

        # 4) Final state snapshot (so a resume picks up the terminal state).
        self._save_state_snapshot()

        self._emit_event("EXPERIMENT_COMPLETED", {
            "sample_id": sample_id,
            "total_measurements": len(self._measurements),
            "status": loop_status,
            "error": loop_error,
        })
        self._finalize_run(loop_status)
        # Auto-trigger Stage0 + Stage1 post-processing if requested at start().
        if self._auto_postprocess:
            try:
                self.run_post_processing(sample_id=sample_id, async_run=True)
            except Exception as exc:
                self._emit_event("POST_PROCESSING_FAILED", {"error": str(exc)})


_adapter_instance: Optional[HardwareAdapter] = None


def get_hardware_adapter() -> HardwareAdapter:
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = HardwareAdapter()
    return _adapter_instance
