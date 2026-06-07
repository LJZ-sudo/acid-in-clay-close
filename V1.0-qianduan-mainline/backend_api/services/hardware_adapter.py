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
RUNS_DIR = PROJECT_ROOT / "runs"


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
        self._agent_model: str = "deepseek-v3.1"
        self._fine_scan_window_C: float = 10.0  # mirror online_workflow default
        self._fine_scan_end_C: Optional[float] = None  # bottom of fine-scan band
        self._fine_trigger_T_C: Optional[float] = None  # 触发细扫时的温度，用于事件
        self._agent_decisions: List[Dict[str, Any]] = []

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

        import uuid
        self._run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        run_dir = RUNS_DIR / self._run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "evidence").mkdir(exist_ok=True)

        t_start = kwargs.get("t_start", 20.0)
        t_end = kwargs.get("t_end", -85.0)

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
                run_drt=False,
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
        bus_root = PROJECT_ROOT / "output" / "stage0_results"
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
        ao_dst_root = _ensure_within(PROJECT_ROOT / "data" / "ao" / ao_folder, PROJECT_ROOT / "data" / "ao", "ao_folder")
        stage0_results_dir = _ensure_within(
            PROJECT_ROOT / "output" / "ao_stage0_results" / ao_folder,
            PROJECT_ROOT / "output" / "ao_stage0_results",
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

            self._emit_event("AGENT_CALL_STARTED", {
                "step_idx": step_idx,
                "n_points": len(history),
                "has_api_key": bool(self._agent_api_key),
                "model": self._agent_model,
            })

            decision = analyze(
                agent_context={"measurement_history": history},
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
                "llm_called": bool(decision.get("llm_called", self._agent_api_key is not None)),
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
        return {
            "next_t": next_t,
            "abort": False,
            "in_fine_band": False,
            "is_reheat": False,
            "agent_suggested_next_C": next_C,   # kept for debugging / events
        }

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
