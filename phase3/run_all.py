# -*- coding: utf-8 -*-
"""
Phase 3 一键运行：step1 → step2 → step3 → step4 → step5

在 close 目录下执行: python phase3/run_all.py
或从项目根目录: python close/phase3/run_all.py
"""

import sys
from pathlib import Path

CLOSE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLOSE_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run(name: str, module_name: str) -> int:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name,
        Path(__file__).resolve().parent / f"{module_name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


def main() -> int:
    print("=" * 60)
    print("Phase 3 全流程（仅 close 内数据）")
    print("=" * 60)
    steps = [
        ("step1_data_preparation", "step1_data_preparation"),
        ("step2_train_models", "step2_train_models"),
        ("step3_confinement_analysis", "step3_confinement_analysis"),
        ("step4_ml_ai_validation", "step4_ml_ai_validation"),
        ("step_meyer_neldel", "step_meyer_neldel"),
        ("step6_cross_material", "step6_cross_material"),
        ("step5_final_report", "step5_final_report"),
    ]
    for name, mod in steps:
        print("")
        code = run(name, mod)
        if code != 0:
            print(f"\n[FAIL] {mod} 返回 {code}")
            return code
    print("\n" + "=" * 60)
    print("Phase 3 全流程完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
