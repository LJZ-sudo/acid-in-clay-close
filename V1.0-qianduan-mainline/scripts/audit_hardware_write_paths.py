#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""硬件写路径审计（WP0 / P0-5,只读）。

目的：为 B 轨"取得系统权威性"提供**真实的旁路清单**。它扫描主线源码里所有会
**改变真实样品/仪器状态**的调用点(enqueue_command / 驱动构造 / set_temperature /
trigger_measurement / dispatch 等),按调用方位置分类,重点标出**自主路径直连硬件**
(绕过未来的 SciTX 事务协调器)的位置。

分类(按调用方文件路径,非硬编码结果——扫描发现什么报什么):
  AUTONOMOUS_AGENT   自主决策环(routers/agent*.py)直连硬件 = **旁路风险**(应改走 SciTX)
  OPERATOR_MANUAL    人工控制端点(routers/control.py)——允许,但应产生 HumanOverrideEvent
  ADAPTER_SINK       HardwareAdapter 实现层(hardware_adapter.py)——硬件网关本体
  LEGACY_ONLINE      人工启动的在线测量脚本(run_online.py / controllers/*)——允许
  HARNESS_SHADOW     scientific_harness/*——shadow/事务层(dispatch 指向 ShadowInstrument,非真硬件)
  DRIVER_DEFINITION  驱动/自动化类定义(modules/hardware|automation/*)——类本身,非调用
  TEST               测试代码
  OTHER              其它

退出码:默认只报告(exit 0)。`--strict` 时,若存在 allowlist 之外的 AUTONOMOUS_AGENT
旁路点,则 exit 1(供 WP4 cutover 后作 CI 门;当前阶段预期会报告 agent.py 的旁路,
属已知待治理项,不应在 enforce 前用 strict 阻断 CI)。

只读;不修改任何项目状态。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]   # V1.0-qianduan-mainline/
DEFAULT_OUT_DIR = PROJECT_ROOT / "scripts" / "reports"

EXCLUDED_DIRS = {
    ".git", ".pytest_cache", "__pycache__", "node_modules", "dist", "build",
    "archive", "backups", "codex", ".venv", "venv", "output", "outputs", "runs",
}

# 会改变真实样品/仪器状态的写原语(token, 正则)。只匹配"调用/构造",不匹配 import/字符串注释行。
HW_WRITE_PATTERNS = [
    ("enqueue_command",       re.compile(r"\.enqueue_command\s*\(")),
    ("set_temperature",       re.compile(r"\.set_temperature\s*\(")),
    ("trigger_measurement",   re.compile(r"\.trigger_measurement\s*\(")),
    ("hw_start",              re.compile(r"\bhw\.start\s*\(")),
    ("hw_stop",               re.compile(r"\bhw\.stop\s*\(")),
    ("TemperatureDriver_ctor", re.compile(r"\bTemperatureDriver\s*\(")),
    ("ChiExecutor_ctor",      re.compile(r"\bChiExecutor\s*\(")),
    ("instrument_dispatch",   re.compile(r"\.dispatch\s*\(")),
]

# 默认 allowlist:自主模式下允许直连硬件的文件(相对主线根的 posix 路径片段)。
# 当前为空——目标是 WP1 后只允许唯一的 Instrument Gateway。把已知网关/适配层显式登记,
# 这样 strict 模式只对"自主决策环直连硬件"报警。
DEFAULT_ALLOWLIST: List[str] = [
    # "backend_api/services/instrument_gateway.py",  # 待 WP1 建立后启用
]


def _classify(rel_posix: str) -> str:
    p = rel_posix
    name = p.rsplit("/", 1)[-1]
    if name.startswith("test_") or "/tests/" in p:
        return "TEST"
    if p.endswith("backend_api/routers/agent.py") or p.endswith("backend_api/routers/agents.py"):
        return "AUTONOMOUS_AGENT"
    if p.endswith("backend_api/routers/control.py"):
        return "OPERATOR_MANUAL"
    if p.endswith("backend_api/services/hardware_adapter.py"):
        return "ADAPTER_SINK"
    if "scientific_harness/" in p:
        return "HARNESS_SHADOW"
    if (
        p.endswith("stage0_measurement/run_online.py")
        or p.endswith("stage0_measurement/b_track_live_driver.py")
        or "stage0_measurement/controllers/" in p
    ):
        return "LEGACY_ONLINE"
    if "modules/hardware/" in p or "modules/automation/" in p:
        return "DRIVER_DEFINITION"
    return "OTHER"


def _iter_py_files(root: Path):
    for path in root.rglob("*.py"):
        parts = set(path.relative_to(root).parts)
        if parts & EXCLUDED_DIRS:
            continue
        yield path


def scan(root: Path) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    for path in _iter_py_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            stripped = line.lstrip()
            # 跳过纯注释行与 import 行(只统计真实调用/构造)
            if stripped.startswith("#") or stripped.startswith("import ") or stripped.startswith("from "):
                continue
            for token, rx in HW_WRITE_PATTERNS:
                if rx.search(line):
                    hits.append({
                        "file": rel,
                        "line": lineno,
                        "token": token,
                        "code": line.strip()[:200],
                        "role": _classify(rel),
                    })
    return hits


def build_report(hits: List[Dict[str, Any]], allowlist: List[str]) -> Dict[str, Any]:
    by_role: Dict[str, int] = {}
    for h in hits:
        by_role[h["role"]] = by_role.get(h["role"], 0) + 1
    bypass = [
        h for h in hits
        if h["role"] == "AUTONOMOUS_AGENT" and not any(h["file"].endswith(a) for a in allowlist)
    ]
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "n_hits": len(hits),
        "by_role": dict(sorted(by_role.items())),
        "autonomous_bypass_count": len(bypass),
        "autonomous_bypass_sites": bypass,
        "allowlist": allowlist,
        "hits": hits,
        "note": (
            "autonomous_bypass = 自主决策环直连硬件、绕过 SciTX 的位置;WP4 cutover 后应清零。"
            "其余角色(OPERATOR_MANUAL/ADAPTER_SINK/LEGACY_ONLINE/HARNESS_SHADOW/DRIVER_DEFINITION)"
            "属允许或非真硬件路径。"
        ),
    }


def to_markdown(rep: Dict[str, Any]) -> str:
    lines = [
        "# 硬件写路径审计报告（direct hardware call report）",
        "",
        f"- 生成时间：{rep['generated_at']}",
        f"- 命中总数：{rep['n_hits']}",
        f"- **自主旁路点（应清零）：{rep['autonomous_bypass_count']}**",
        "",
        "## 角色分布",
        "",
        "| 角色 | 命中数 |",
        "|---|---|",
    ]
    for role, n in rep["by_role"].items():
        lines.append(f"| {role} | {n} |")
    lines += ["", "## 自主旁路点（AUTONOMOUS_AGENT,绕过 SciTX）", ""]
    if rep["autonomous_bypass_sites"]:
        lines += ["| 文件 | 行 | token | 代码 |", "|---|---|---|---|"]
        for h in rep["autonomous_bypass_sites"]:
            lines.append(f"| {h['file']} | {h['line']} | {h['token']} | `{h['code']}` |")
    else:
        lines.append("（无）")
    lines += ["", "## 全部命中", "", "| 文件 | 行 | token | 角色 |", "|---|---|---|---|"]
    for h in rep["hits"]:
        lines.append(f"| {h['file']} | {h['line']} | {h['token']} | {h['role']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="审计主线中改变真实样品/仪器状态的写路径(只读)。")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="报告输出目录")
    ap.add_argument("--strict", action="store_true",
                    help="存在 allowlist 外的自主旁路点时 exit 1(供 WP4 后作 CI 门)")
    ap.add_argument("--allow", action="append", default=None,
                    help="追加 allowlist 文件路径片段(可多次)")
    args = ap.parse_args()

    allowlist = list(DEFAULT_ALLOWLIST) + list(args.allow or [])
    hits = scan(PROJECT_ROOT)
    rep = build_report(hits, allowlist)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "direct_hardware_call_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "direct_hardware_call_report.md").write_text(to_markdown(rep), encoding="utf-8")

    print(f"[audit_hardware_write_paths] hits={rep['n_hits']} "
          f"autonomous_bypass={rep['autonomous_bypass_count']} → {out_dir}")
    for role, n in rep["by_role"].items():
        print(f"  {role:18s} {n}")
    if rep["autonomous_bypass_sites"]:
        print("  自主旁路点:")
        for h in rep["autonomous_bypass_sites"]:
            print(f"    {h['file']}:{h['line']}  {h['token']}  {h['code']}")

    if args.strict and rep["autonomous_bypass_count"] > 0:
        print("STRICT: 存在自主旁路点,exit 1", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
