# -*- coding: utf-8 -*-
"""
一键生成 Figure 5-16 所有图表

运行方式：
    python generate_all_figures.py

生成内容：
    - Figure 5: S60 Baseline Model Performance
    - Figure 6: S8 Confined Model Performance  
    - Figure 7: Feature Importance / SHAP
    - Figure 8: CV Stability
    - Figure 9: ΔEa vs T Linear Fit
    - Figure 10: Low/High Temperature Boxplot
    - Figure 11: ΔEa Distribution
    - Figure 12: Residual Diagnostics
    - Figure 13: S8 Meyer-Neldel
    - Figure 14: S60 Meyer-Neldel
    - Figure 15: E_MN / T_MN Comparison
    - Figure 16: Entropy-Enthalpy Schematic

所有图表遵循 AM (Advanced Materials) 期刊标准
"""

import os
import sys
import subprocess
from pathlib import Path
import time

PAPER_FIGURE_DIR = Path(__file__).resolve().parent
CLOSE_ROOT = PAPER_FIGURE_DIR.parent

# 图表脚本列表
FIGURE_SCRIPTS = [
    ('figure5', 'plot_s60_baseline_performance.py', 'S60 Baseline Performance'),
    ('figure6', 'plot_s8_confined_performance.py', 'S8 Confined Performance'),
    ('figure7', 'plot_feature_importance.py', 'Feature Importance'),
    ('figure8', 'plot_cv_stability.py', 'CV Stability'),
    ('figure9', 'plot_delta_ea_vs_T.py', 'ΔEa vs Temperature'),
    ('figure10', 'plot_temp_boxplot.py', 'Temperature Boxplot'),
    ('figure11', 'plot_delta_ea_distribution.py', 'ΔEa Distribution'),
    ('figure12', 'plot_residual_diagnostics.py', 'Residual Diagnostics'),
    ('figure13', 'plot_meyer_neldel_s8.py', 'S8 Meyer-Neldel'),
    ('figure14', 'plot_meyer_neldel_s60.py', 'S60 Meyer-Neldel'),
    ('figure15', 'plot_emn_tmn_comparison.py', 'E_MN/T_MN Comparison'),
    ('figure16', 'plot_entropy_enthalpy_schematic.py', 'Entropy-Enthalpy Schematic'),
]


def build_subprocess_env():
    """确保子进程在 standalone 布局下也能解析 close/paper_figure 路径。"""
    env = os.environ.copy()
    pythonpath_entries = [str(CLOSE_ROOT), str(PAPER_FIGURE_DIR)]
    existing = env.get("PYTHONPATH", "")
    if existing:
        pythonpath_entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_script(folder, script, description):
    """运行单个绘图脚本"""
    script_path = PAPER_FIGURE_DIR / folder / script
    
    if not script_path.exists():
        print(f"  [SKIP] {folder}/{script} not found")
        return False
    
    print(f"\n{'='*60}")
    print(f"Generating: {description}")
    print(f"Script: {folder}/{script}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            cwd=str(script_path.parent),
            timeout=120,
            env=build_subprocess_env(),
        )
        
        if result.returncode == 0:
            print(f"  [SUCCESS] {description}")
            # 显示输出的最后几行
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines[-10:]:
                    print(f"    {line}")
            return True
        else:
            print(f"  [ERROR] {description}")
            print(f"  Return code: {result.returncode}")
            if result.stderr:
                print(f"  Error: {result.stderr[:500]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {description} (>120s)")
        return False
    except Exception as e:
        print(f"  [EXCEPTION] {description}: {e}")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("AM Paper Figures Generator (Figure 5-16)")
    print("=" * 70)
    print(f"\nOutput directory: {PAPER_FIGURE_DIR}")
    print(f"Close root: {CLOSE_ROOT}")
    print(f"Total figures: {len(FIGURE_SCRIPTS)}")
    
    start_time = time.time()
    
    success_count = 0
    failed_list = []
    
    for folder, script, description in FIGURE_SCRIPTS:
        if run_script(folder, script, description):
            success_count += 1
        else:
            failed_list.append(f"{folder}/{script}")
    
    elapsed = time.time() - start_time
    
    # 汇总报告
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total: {len(FIGURE_SCRIPTS)}")
    print(f"  Success: {success_count}")
    print(f"  Failed: {len(failed_list)}")
    print(f"  Time: {elapsed:.1f}s")
    
    if failed_list:
        print(f"\n  Failed scripts:")
        for f in failed_list:
            print(f"    - {f}")
    
    print("\n" + "=" * 70)
    print("Output locations:")
    for folder, script, description in FIGURE_SCRIPTS:
        fig_dir = PAPER_FIGURE_DIR / folder
        print(f"  {folder}/: {description}")
    
    print("\n[Generation Complete]")
    
    return 0 if not failed_list else 1


if __name__ == '__main__':
    raise SystemExit(main())
