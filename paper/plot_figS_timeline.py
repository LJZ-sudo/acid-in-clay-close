#!/usr/bin/env python3
"""
Generate Fig S_timeline: Agent Reasoning Gantt Chart
Data source: SI_Agent_execution_log.json
Output: FigS_timeline.png in close/paper/
"""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from datetime import datetime

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_PATH = SCRIPT_DIR / "SI_reports" / "SI_Agent_execution_log.json"
OUT_PATH = SCRIPT_DIR / "SI_figure" / "FigS_timeline.png"


def parse_time(s: str) -> int:
    """Convert HH:MM:SS to seconds since midnight (for delta calc)."""
    h, m, s = map(int, s.split(":"))
    return h * 3600 + m * 60 + s


def extract_timeline(data: dict) -> list:
    """Extract Gantt bars: (label, start_s, duration_s, category)."""
    exec_log = data["execution_log"]
    thought_log = data.get("thought_log", [])

    # Get iteration start timestamps from "--- Iteration N/10 ---"
    iter_times = []
    t0 = None
    for entry in exec_log:
        msg = entry.get("message", "")
        if "--- Iteration" in msg:
            t_str = entry.get("time", "")
            if t_str:
                t_sec = parse_time(t_str)
                if t0 is None:
                    t0 = t_sec
                n = int(msg.split("Iteration")[1].split("/")[0].strip())
                iter_times.append((n, t_sec))

    # Get Report generation timestamps
    report_start = report_end = None
    for entry in exec_log:
        t_str = entry.get("time", "")
        if "Step 5:" in entry.get("message", ""):
            report_start = parse_time(t_str) if t_str else None
        if "Report generated!" in entry.get("message", ""):
            report_end = parse_time(t_str) if t_str else None

    bars = []
    action_map = {t["iteration"]: t["action"] for t in thought_log}

    for i in range(len(iter_times) - 1):
        n, t_start = iter_times[i]
        _, t_end = iter_times[i + 1]
        start_s = t_start - t0
        dur = t_end - t_start
        action = action_map.get(n, "?")
        if action == "FINISH":
            cat = "decision"
            label = "FINISH (decision)"
        else:
            cat = "tool"
            label = action
        bars.append((label, start_s, dur, cat))

    if report_start is not None and report_end is not None and t0 is not None:
        bars.append(
            ("Report generation", report_start - t0, report_end - report_start, "report")
        )

    return bars


def main():
    # Load log
    if not LOG_PATH.exists():
        print(f"Log not found: {LOG_PATH}")
        # Use hardcoded timeline from Table S6 + execution log summary
        bars = [
            ("1. prepare_data", 0, 5.3, "tool"),
            ("2. train_models", 5.3, 6.2, "tool"),
            ("3. confinement_analysis", 11.5, 6.0, "tool"),
            ("4. meyer_neldel", 17.5, 6.2, "tool"),
            ("5. cross_material", 23.7, 7.5, "tool"),
            ("6. FINISH (decision)", 31.2, 6.9, "decision"),
            ("7. Report generation", 38.1, 181.2, "report"),
        ]
    else:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        bars = extract_timeline(data)
        if not bars:
            # Fallback
            bars = [
                ("1. prepare_data", 0, 5.3, "tool"),
                ("2. train_models", 5.3, 6.2, "tool"),
                ("3. confinement_analysis", 11.5, 6.0, "tool"),
                ("4. meyer_neldel", 17.5, 6.2, "tool"),
                ("5. cross_material", 23.7, 7.5, "tool"),
                ("6. FINISH (decision)", 31.2, 6.9, "decision"),
                ("7. Report generation", 38.1, 181.2, "report"),
            ]

    # Add iteration numbers to tool labels
    iter_num = 1
    labeled_bars = []
    for label, start, dur, cat in bars:
        if cat == "tool":
            labeled_bars.append((f"{iter_num}. {label}", start, dur, cat))
            iter_num += 1
        elif cat == "decision":
            labeled_bars.append((f"{iter_num}. {label}", start, dur, cat))
            iter_num += 1
        else:
            labeled_bars.append((label, start, dur, cat))
    bars = labeled_bars

    # Colors by category
    colors = {"tool": "#4A90D9", "decision": "#7B68EE", "report": "#E67E22"}
    fig, ax = plt.subplots(figsize=(10, 4.5))
    y_pos = 0
    y_step = 1.2
    for label, start, dur, cat in reversed(bars):
        color = colors.get(cat, "#95A5A6")
        ax.barh(y_pos, dur, left=start, height=0.7, color=color, edgecolor="white", linewidth=0.5)
        # Label with duration
        ax.text(start + dur / 2, y_pos, f"{dur:.1f}s", ha="center", va="center", fontsize=9, color="white", weight="bold")
        ax.text(start - 2, y_pos, label, ha="right", va="center", fontsize=10)
        y_pos += y_step

    total_dur = max(start + dur for _, start, dur, _ in bars) if bars else 220
    ax.set_xlim(-55, total_dur + 10)
    ax.set_xlabel("Time from start (s)", fontsize=11)
    ax.set_ylabel("")
    ax.set_yticks([])
    ax.set_title("Agent Reasoning Timeline (ReAct Loop, S8 Analysis)", fontsize=12, weight="bold")
    ax.spines["left"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.grid(axis="x", alpha=0.3, linestyle="--")

    # Legend
    legend_items = [
        mpatches.Patch(color="#4A90D9", label="Tool execution"),
        mpatches.Patch(color="#7B68EE", label="Decision (FINISH)"),
        mpatches.Patch(color="#E67E22", label="Report generation"),
    ]
    ax.legend(handles=legend_items, loc="upper right", fontsize=9)

    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=300, bbox_inches="tight")
    print(f"Saved: {OUT_PATH}")
    plt.close()


if __name__ == "__main__":
    main()
