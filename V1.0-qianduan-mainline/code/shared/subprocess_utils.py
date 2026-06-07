"""Subprocess helper shared by replay runner scripts."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List


def run_command(cmd: List[str], cwd: Path, description: str, verbose: bool = False) -> Dict[str, Any]:
    print(f"\n{'=' * 70}")
    print(description)
    print(f"{'=' * 70}")

    if verbose:
        print(f"Command: {' '.join(cmd)}")
        print(f"Working directory: {cwd}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except Exception as exc:
        print(f"[ERROR] Failed to run command: {exc}")
        return {
            "success": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "cmd": cmd,
            "cwd": str(cwd),
        }

    if verbose or result.returncode != 0:
        print("\n--- STDOUT ---")
        print(result.stdout)
        if result.stderr:
            print("\n--- STDERR ---")
            print(result.stderr)

    success = result.returncode == 0
    print(f"[{'OK' if success else 'ERROR'}] {description} {'completed successfully' if success else 'failed'}")
    return {
        "success": success,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "cmd": cmd,
        "cwd": str(cwd),
    }

