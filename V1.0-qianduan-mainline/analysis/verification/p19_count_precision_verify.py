# -*- coding: utf-8 -*-
"""P19 验证(P13-F):测试计数/文档精度 —— 可复核的真实 pytest 计数。

纠正此前"410 测试"的模糊表述:发表/文档应区分
  - **pytest collected items**(实际执行项,含 @parametrize 展开);
  - **`def test_` 源函数数**(不含 parametrize 展开)。

做法:
  1. 对 `tests/` + `backend_api/tests/` + `stage3_mechanism/tests/` 跑 `pytest --collect-only`;
  2. 逐目录核对 collected 之和 = 总量;
  3. 统计 `def test_` 源函数数 + parametrize 展开差;
  4. 断言 `test_live_seed_adapter.py` 专用单测存在且可 collect。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve()
MAIN = next(_p for _p in HERE.parents if _p.name == "V1.0-qianduan-mainline")
DIRS = ["tests", "backend_api/tests", "stage3_mechanism/tests"]

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def _collect_count(path: str) -> int:
    cp = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", path],
        cwd=str(MAIN), capture_output=True, text=True, encoding="utf-8",
    )
    m = re.search(r"(\d+) tests? collected", cp.stdout + cp.stderr)
    if not m:
        raise RuntimeError(f"collect failed for {path}: {cp.stdout}\n{cp.stderr}")
    return int(m.group(1))


def _def_test_count(path: str) -> int:
    root = MAIN / path
    n = 0
    for fp in root.rglob("test_*.py"):
        text = fp.read_text(encoding="utf-8")
        n += len(re.findall(r"^\s*def test_", text, re.MULTILINE))
    return n


def main():
    print("=" * 74)
    print("P19:测试计数/文档精度 —— 可复核 pytest 计数")
    print("=" * 74)

    per_dir = {d: _collect_count(d) for d in DIRS}
    total_collected = _collect_count(".")
    sum_dirs = sum(per_dir.values())
    def_total = sum(_def_test_count(d) for d in DIRS)
    parametrize_delta = total_collected - def_total

    print(f"pytest collected (全仓): {total_collected}")
    print(f"  tests/: {per_dir['tests']}")
    print(f"  backend_api/tests/: {per_dir['backend_api/tests']}")
    print(f"  stage3_mechanism/tests/: {per_dir['stage3_mechanism/tests']}")
    print(f"def test_ 源函数: {def_total}")
    print(f"@parametrize 展开增量: {parametrize_delta}")

    check("三目录 collected 之和 = 全仓 collected", sum_dirs == total_collected,
          f"sum={sum_dirs} total={total_collected}")
    check("parametrize 展开增量可解释(>0 且 ≤10)", 0 < parametrize_delta <= 10,
          f"delta={parametrize_delta}")
    check("def test_ 数 < collected(文档须区分二者)", def_total < total_collected,
          f"def={def_total} collected={total_collected}")

    live_test = MAIN / "stage3_mechanism/tests/test_live_seed_adapter.py"
    check("live_seed_adapter 专用单测文件存在", live_test.exists(), str(live_test))
    live_n = _collect_count("stage3_mechanism/tests/test_live_seed_adapter.py")
    check("live_seed_adapter 单测可被 pytest collect(≥1)", live_n >= 1, f"collected={live_n}")

    # 快照写入 epistemic_out 供文档引用(可复核产物)
    out = MAIN.parent / "research" / "results" / "epistemic_out" / "test_count_snapshot.json"
    out.parent.mkdir(exist_ok=True)
    import json
    snapshot = {
        "pytest_collected_total": total_collected,
        "pytest_collected_by_dir": per_dir,
        "def_test_functions": def_total,
        "parametrize_expansion_delta": parametrize_delta,
        "canonical_phrase": (
            f"{total_collected} pytest collected items "
            f"({def_total} def test_ + {parametrize_delta} @parametrize expansions)"
        ),
        "live_seed_adapter_dedicated_test": str(live_test.relative_to(MAIN)),
    }
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    check("test_count_snapshot.json 落盘(文档可引用)", out.exists(), str(out))

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   ({snapshot['canonical_phrase']})")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
