import json
import os
import shutil
import subprocess
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

import matplotlib
import requests

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from auto_control.modules.arrhenius import (
    perform_arrhenius_analysis,
    generate_arrhenius_plot_data,
)

# ============================================================
# ⚠️ API Key 配置区域
# ============================================================
# 优先级: 环境变量 > 空字符串
# GitHub版本中不再保留任何真实硬编码密钥
# 推荐方式: 设置环境变量 OPENROUTER_API_KEY
#
# Windows设置环境变量:
#   set OPENROUTER_API_KEY=your_key_here
# 或在系统环境变量中永久设置
#
# Linux/Mac:
#   export OPENROUTER_API_KEY=your_key_here

def _get_api_config():
    """
    获取API配置，优先从环境变量读取
    """
    return {
        "openrouter_api_key": os.environ.get("OPENROUTER_API_KEY", ""),
        "openrouter_model": os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-4.5"),
        "fallback_model": os.environ.get("FALLBACK_MODEL", "anthropic/claude-3.7-sonnet"),
        "deepseek_api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
    }

# 保持向后兼容的全局变量
_config = _get_api_config()
OPENROUTER_API_KEY = _config["openrouter_api_key"]
OPENROUTER_MODEL = _config["openrouter_model"]
FALLBACK_MODEL = _config["fallback_model"]
DEEPSEEK_API_KEY = _config["deepseek_api_key"]
OPENAI_API_KEY = _config["openai_api_key"]
# ============================================================


def _load_report(report_path: str) -> Dict:
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_arrhenius_data(report: Dict) -> Tuple[List[Dict], List[Dict], bool]:
    arr = report.get("arrhenius_analysis", {}) or {}
    arrhenius_data = arr.get("arrhenius_data") or []
    segments = arr.get("segments") or []
    fallback_used = False

    if segments and arrhenius_data:
        return arrhenius_data, segments, fallback_used

    # fallback: 用成功点重新做一次分段分析（保持最小侵入）
    successful_points = report.get("successful_points", []) or []
    records = []
    for sp in successful_points:
        sigma = sp.get("conductivity_S_per_cm")
        temp_k = sp.get("temperature_K")
        if sigma and sigma > 0 and temp_k:
            records.append(
                {
                    "temperature_K": temp_k,
                    "temperature_C": sp.get("temperature_C"),
                    "rb_ohm": sp.get("rb_ohm"),
                    "conductivity_S_per_cm": sigma,
                }
            )

    if records:
        fallback_used = True
        analysis = perform_arrhenius_analysis(records, min_points=max(3, len(records)))
        arrhenius_data = analysis.get("arrhenius_data") or arrhenius_data
        segments = analysis.get("segments") or segments

    return arrhenius_data, segments, fallback_used


def _generate_conductivity_plot(
    report: Dict, output_dir: str
) -> Tuple[str, Dict]:
    """生成电导率vs温度 Arrhenius图 - 文献风格（双横坐标）"""
    arrhenius_data, segments, fallback_used = _build_arrhenius_data(report)

    # 提取数据
    temps_K = []
    temps_C = []
    sigma_S_cm = []
    import math

    print(f"[DEBUG] arrhenius_data 长度: {len(arrhenius_data)}")
    print(f"[DEBUG] segments 长度: {len(segments)}")

    for d in arrhenius_data:
        t_k = d.get("temperature_K")
        t_c = d.get("temperature_C")
        s_s_per_cm = d.get("conductivity_S_per_cm")
        
        if t_k is None or s_s_per_cm is None:
            continue
        if not (math.isfinite(t_k) and math.isfinite(s_s_per_cm)):
            continue
        if s_s_per_cm <= 0:
            continue
        
        temps_K.append(t_k)
        temps_C.append(t_c if t_c is not None else t_k - 273.15)
        sigma_S_cm.append(s_s_per_cm)
    
    print(f"[DEBUG] 提取到 {len(temps_K)} 个数据点")
    
    if not temps_K:
        print("[WARNING] 无正电导率数据，跳过绘图")
        return "", {"fallback_used": fallback_used, "segments": segments, "reason": "no_positive_sigma"}

    # 转换为numpy数组
    temps_K = np.array(temps_K, dtype=float)
    temps_C = np.array(temps_C, dtype=float)
    sigma_S_cm = np.array(sigma_S_cm, dtype=float)
    
    # 转换单位
    inv_T_1000 = 1000.0 / temps_K  # 1000/T (K^-1)
    sigma_mS_cm = sigma_S_cm * 1000  # S/cm -> mS/cm
    log_sigma = np.log10(sigma_mS_cm)  # log10(σ)
    
    print(f"[DEBUG] 温度范围: {temps_C.min():.1f} ~ {temps_C.max():.1f} °C")
    print(f"[DEBUG] 1000/T范围: {inv_T_1000.min():.2f} ~ {inv_T_1000.max():.2f} K^-1")
    print(f"[DEBUG] log(σ)范围: {log_sigma.min():.2f} ~ {log_sigma.max():.2f}")

    # 获取材料名称
    material_name = report.get("experiment_info", {}).get("material", "Sample")
    if not material_name or material_name == "Sample":
        # 尝试从其他位置获取
        material_name = report.get("material", "Sample")
    
    # === 文献风格绘图（双横坐标）===
    plt.rcParams['font.family'] = 'Arial'
    plt.rcParams['font.size'] = 12
    plt.rcParams['axes.linewidth'] = 1.5
    
    fig, ax1 = plt.subplots(figsize=(10, 8))
    
    # 设置背景
    ax1.set_facecolor('white')
    fig.patch.set_facecolor('white')

    # 排序数据（按1000/T从小到大）
    sort_idx = np.argsort(inv_T_1000)
    inv_T_sorted = inv_T_1000[sort_idx]
    log_sigma_sorted = log_sigma[sort_idx]
    temps_C_sorted = temps_C[sort_idx]
    temps_K_sorted = temps_K[sort_idx]
    sigma_mS_sorted = sigma_mS_cm[sort_idx]

    # 不同分段的marker样式和颜色 - 文献常用配色
    markers = ['*', 's', '^', 'o', 'D', 'p', 'v', 'h']
    colors = ['#E74C3C', '#27AE60', '#F39C12', '#3498DB', '#9B59B6', '#1ABC9C', '#E67E22', '#34495E']
    
    plotted_any = False
    
    if segments:
        for idx, seg in enumerate(segments):
            t_low, t_high = seg.get("T_range_C", (None, None))
            if t_low is None or t_high is None:
                continue
            
            t_k_min = min(t_low, t_high) + 273.15
            t_k_max = max(t_low, t_high) + 273.15
            
            mask = (temps_K_sorted >= t_k_min) & (temps_K_sorted <= t_k_max)
            n_points = np.sum(mask)
            print(f"[DEBUG] Segment {seg.get('segment')}: T=[{t_k_min:.1f}, {t_k_max:.1f}]K, {n_points} points")
            
            if np.any(mask):
                inv_T_seg = inv_T_sorted[mask]
                log_sigma_seg = log_sigma_sorted[mask]
                
                Ea = seg.get('Ea_kJ_per_mol', 0)
                
                # 绘制散点
                ax1.scatter(
                    inv_T_seg,
                    log_sigma_seg,
                    label=f"{material_name} (Ea={Ea:.1f} kJ/mol)" if idx == 0 else f"Segment {idx+1} (Ea={Ea:.1f} kJ/mol)",
                    color=colors[idx % len(colors)],
                    marker=markers[idx % len(markers)],
                    s=120,
                    edgecolors='white' if markers[idx % len(markers)] == '*' else 'black',
                    linewidths=1.0,
                    alpha=0.9,
                    zorder=10,
                )
                
                # 绘制Arrhenius拟合线（灰色虚线）
                if len(inv_T_seg) >= 2:
                    try:
                        from scipy.stats import linregress
                        slope, intercept, r_value, _, _ = linregress(inv_T_seg, log_sigma_seg)
                        
                        x_fit = np.linspace(inv_T_seg.min(), inv_T_seg.max(), 100)
                        y_fit = slope * x_fit + intercept
                        
                        ax1.plot(
                            x_fit,
                            y_fit,
                            color='gray',
                            linestyle='--',
                            linewidth=1.5,
                            alpha=0.7,
                            zorder=5,
                        )
                    except Exception as e:
                        print(f"[WARNING] 拟合线绘制失败: {e}")
                
                plotted_any = True
    else:
        # 没有分段信息，绘制所有点并做整体拟合
        ax1.scatter(
            inv_T_sorted, 
            log_sigma_sorted, 
            color='#E74C3C',
            s=120, 
            label=material_name, 
            marker='*',
            edgecolors='white',
            linewidths=1.0,
            alpha=0.9,
            zorder=10
        )
        
        # 整体线性拟合
        try:
            from scipy.stats import linregress
            slope, intercept, r_value, _, _ = linregress(inv_T_sorted, log_sigma_sorted)
            
            # 计算活化能 Ea
            R = 8.314  # J/(mol·K)
            Ea_J_mol = -slope * 2.303 * R * 1000
            Ea_kJ_mol = Ea_J_mol / 1000
            
            x_fit = np.linspace(inv_T_sorted.min(), inv_T_sorted.max(), 100)
            y_fit = slope * x_fit + intercept
            
            ax1.plot(x_fit, y_fit, 
                    color='gray', 
                    linestyle='--', 
                    linewidth=1.5,
                    alpha=0.7,
                    label=f'Linear fit (Ea={Ea_kJ_mol:.1f} kJ/mol)')
        except Exception as e:
            print(f"[WARNING] 整体拟合失败: {e}")
        
        plotted_any = True

    if not plotted_any:
        print("[WARNING] 没有绘制任何数据点")

    # === 底部X轴: 1000/T (K^-1) ===
    ax1.set_xlabel(r'$1000/T$ (K$^{-1}$)', fontsize=14, fontweight='bold')
    ax1.set_ylabel(r'log $\sigma$ (mS cm$^{-1}$)', fontsize=14, fontweight='bold')

    # 设置X轴范围
    x_margin = (inv_T_sorted.max() - inv_T_sorted.min()) * 0.1
    x_min = inv_T_sorted.min() - x_margin
    x_max = inv_T_sorted.max() + x_margin
    ax1.set_xlim(x_min, x_max)
    
    # 设置Y轴范围
    y_margin = (log_sigma_sorted.max() - log_sigma_sorted.min()) * 0.15
    y_min = log_sigma_sorted.min() - y_margin
    y_max = log_sigma_sorted.max() + y_margin
    ax1.set_ylim(y_min, y_max)

    # === 顶部X轴: T (°C) ===
    ax2 = ax1.twiny()
    ax2.set_xlim(ax1.get_xlim())
    
    # 计算温度刻度位置 - 选择典型温度值
    temp_min_C = temps_C_sorted.min()
    temp_max_C = temps_C_sorted.max()
    
    # 生成合理的温度刻度
    typical_temps = []
    for t in [60, 40, 20, 0, -20, -40, -60, -80, -100, -120]:
        if temp_min_C - 10 <= t <= temp_max_C + 10:
            typical_temps.append(t)
    
    if len(typical_temps) < 3:
        typical_temps = np.linspace(temp_min_C, temp_max_C, 5).astype(int).tolist()
    
    typical_temps = sorted(typical_temps, reverse=True)  # 从高温到低温
    typical_inv_T = [1000.0 / (t + 273.15) for t in typical_temps]
    
    ax2.set_xticks(typical_inv_T)
    ax2.set_xticklabels([f'{int(t)}' for t in typical_temps])
    ax2.set_xlabel(r'$T$ (°C)', fontsize=14, fontweight='bold')

    # 刻度样式
    ax1.tick_params(axis='both', which='major', labelsize=12, width=1.5, length=6, direction='in')
    ax1.tick_params(axis='both', which='minor', width=1.0, length=3, direction='in')
    ax2.tick_params(axis='x', which='major', labelsize=12, width=1.5, length=6, direction='in')

    # 网格
    ax1.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.4, color='gray')

    # 图例
    handles, labels = ax1.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax1.legend(by_label.values(), by_label.keys(), 
              loc='upper right', 
              framealpha=0.95, 
              edgecolor='gray',
              fontsize=10)
    
    # 标题
    ax1.set_title(f'Arrhenius Plot - {material_name}', fontsize=16, fontweight='bold', pad=35)
    
    # 边框加粗
    for spine in ax1.spines.values():
        spine.set_linewidth(1.5)
    for spine in ax2.spines.values():
        spine.set_linewidth(1.5)

    plt.tight_layout()

    # 保存图表
    plot_path = os.path.join(output_dir, "conductivity_plot.png")
    plt.savefig(plot_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    print(f"[SUCCESS] Arrhenius图已保存: {plot_path}")
    return plot_path, {"fallback_used": fallback_used, "segments": segments}


def _fmt(val, fmt_str=".2f", default="N/A"):
    if val is None:
        return default
    try:
        return format(val, fmt_str)
    except Exception:
        return str(val)


def _generate_analysis_markdown(
    report: Dict,
    plot_path: str,
    plot_meta: Dict,
    output_dir: str,
) -> str:
    lines = []
    summary = report.get("summary", {})
    config = report.get("configuration", {})
    arrhenius = report.get("arrhenius_analysis", {}) or {}
    arrhenius_data, segments, _ = _build_arrhenius_data(report)
    failed = report.get("failed_points", []) or []
    success_points = report.get("successful_points", []) or []

    lines.append("# 实验报告（打包版）")
    lines.append("")
    lines.append("## 概览")
    lines.append(f"- 总测量点: {summary.get('total_measurements', 0)}")
    lines.append(
        f"- 成功: {summary.get('successful_measurements', 0)} "
        f"({summary.get('success_rate', 0)*100:.1f}%)"
    )
    lines.append(f"- 失败: {summary.get('failed_measurements', 0)}")
    lines.append(f"- 电导率单位: S/cm（绘图同单位）")
    lines.append("")

    lines.append("## 实验配置")
    for k, v in config.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 分段 Arrhenius 概览")
    if segments:
        lines.append("| 分段 | Ea (kJ/mol) | σ₀ (S/cm) | 温区 (°C) | 数据点 |")
        lines.append("|------|-------------|-----------|-----------|--------|")
        for seg in segments:
            t_range = seg.get("T_range_C") or ("?", "?")
            lines.append(
                f"| {seg.get('segment')} | "
                f"{_fmt(seg.get('Ea_kJ_per_mol'), '.2f')} | "
                f"{_fmt(seg.get('sigma0_S_per_cm'), '.2e')} | "
                f"{_fmt(t_range[0], '.1f')}~{_fmt(t_range[1], '.1f')} | "
                f"{seg.get('data_points', 'N/A')} |"
            )
    else:
        msg = arrhenius.get("message", "无分段信息")
        lines.append(f"- 无分段结果：{msg}")
    lines.append("")

    lines.append("## 数据点概览（成功）")
    if success_points:
        lines.append("| 温度 (°C) | Rb (Ω) | σ (S/cm) | 拟合质量 | 文件 |")
        lines.append("|-----------|--------|-----------|----------|------|")
        for sp in success_points:
            lines.append(
                f"| {_fmt(sp.get('temperature_C'), '.1f')} | "
                f"{_fmt(sp.get('rb_ohm'), '.2f')} | "
                f"{_fmt(sp.get('conductivity_S_per_cm'), '.4e')} | "
                f"{_fmt(sp.get('fit_quality'), '.4f')} | "
                f"`{sp.get('raw_data_path', '')}` |"
            )
    else:
        lines.append("- 无成功点")
    lines.append("")

    lines.append("## 失败/异常点")
    if failed:
        lines.append("| 温度 (°C) | 原因 | 文件 |")
        lines.append("|-----------|------|------|")
        for fp in failed:
            lines.append(
                f"| {_fmt(fp.get('temperature_C'), '.1f')} | "
                f"{fp.get('failure_reason', 'N/A')} | "
                f"`{fp.get('raw_data_path', '')}` |"
            )
    else:
        lines.append("- 无失败点")
    lines.append("")

    if plot_path:
        lines.append("## 可视化")
        lines.append(f"![conductivity]({os.path.basename(plot_path)})")
        if plot_meta.get("fallback_used"):
            lines.append("\n> 分段信息使用了回退算法（无原始分段时自动推断）")

    analysis_path = os.path.join(output_dir, "analysis_report.md")
    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return analysis_path


def _generate_ai_report(analysis_md: str, output_dir: str) -> Optional[str]:
    # 优先使用配置区域的 key，如果为空则尝试环境变量
    openrouter_key = OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY")
    api_key = DEEPSEEK_API_KEY or OPENAI_API_KEY or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    output_path = os.path.join(output_dir, "ai_report.md")

    if not (openrouter_key or api_key):
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# AI 评述\n\n未生成：请在 report_bundle.py 顶部配置区域填入 API Key，或设置环境变量。\n")
        print("⚠️ AI评述跳过：未提供 API Key")
        return output_path

    prompt = (
        "请基于以下实验分析Markdown，总结关键发现、分段Arrhenius结果、拟合质量，"
        "指出异常与改进建议，保持简洁的技术写作风格。\n\n" + analysis_md
    )

    try:
        if openrouter_key:
            url = "https://openrouter.ai/api/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/eis-analysis",
                "X-Title": "EIS Analysis Report Generator",
            }
            
            # ✅ 使用配置的主模型和备用模型
            primary_model = OPENROUTER_MODEL or os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-4.5")
            fallback_model = FALLBACK_MODEL or "anthropic/claude-3.7-sonnet"
            
            payload = {
                "model": primary_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.15,  # ✅ 优化temperature
                "max_tokens": 4000,
            }
            
            print(f"🔄 正在调用 OpenRouter API")
            print(f"   主模型: {primary_model}")
            print(f"   备用模型: {fallback_model}")
            
            # ✅ 尝试主模型
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=180)
                resp.raise_for_status()
                data = resp.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    print(f"✅ 主模型 {primary_model} 生成成功")
                else:
                    raise ValueError(f"API 返回格式异常: {data}")
                    
            except Exception as e:
                print(f"⚠️ 主模型 {primary_model} 失败: {e}")
                print(f"🔄 切换到备用模型 {fallback_model}...")
                
                # ✅ 使用备用模型重试
                payload["model"] = fallback_model
                resp = requests.post(url, headers=headers, json=payload, timeout=180)
                resp.raise_for_status()
                data = resp.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    print(f"✅ 备用模型 {fallback_model} 生成成功")
                else:
                    raise ValueError(f"备用模型API返回格式异常: {data}")
        else:
            import openai  # type: ignore

            client = openai.OpenAI(api_key=api_key)
            model = os.environ.get("DEEPSEEK_MODEL", "gpt-4o-mini")
            print(f"🔄 正在调用 OpenAI/DeepSeek API (model={model})...")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = resp.choices[0].message.content

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# AI 评述\n\n")
            f.write(content or "（无内容）")
        print(f"✅ AI评述已生成: {output_path}")
        return output_path
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.text
        except:
            pass
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# AI 评述\n\n生成失败：{e}\n\n详细信息：\n```\n{error_detail}\n```\n")
        print(f"⚠️ AI评述失败: {e}")
        if error_detail:
            print(f"   详细错误: {error_detail[:200]}")
        return output_path
    except Exception as e:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# AI 评述\n\n生成失败：{e}\n")
        print(f"⚠️ AI评述失败: {e}")
        import traceback
        traceback.print_exc()
        return output_path


def _export_pdf_from_md(md_path: str, output_dir: str) -> Optional[str]:
    latex_cmd = shutil.which("xelatex") or shutil.which("pdflatex")
    if not latex_cmd:
        print("⚠️ 未检测到 LaTeX（xelatex/pdflatex），跳过 PDF 导出")
        return None

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    def _escape_tex(text: str) -> str:
        escape_map = {
            "#": r"\#",
            "$": r"\$",
            "%": r"\%",
            "&": r"\&",
            "_": r"\_",
        }
        for k, v in escape_map.items():
            text = text.replace(k, v)
        return text

    tex_content = r"""\documentclass[12pt]{article}
\usepackage{geometry}
\usepackage{hyperref}
\usepackage{graphicx}
\usepackage{longtable}
\usepackage{float}
\geometry{margin=1in}
\begin{document}
\title{实验报告（打包版）}
\author{Auto Control}
\date{\today}
\maketitle
\begin{verbatim}
""" + _escape_tex(md_content) + r"""
\end{verbatim}
\end{document}
"""

    tex_path = os.path.join(output_dir, "analysis_report.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    pdf_path = os.path.join(output_dir, "report.pdf")
    try:
        subprocess.run(
            [latex_cmd, "-interaction=nonstopmode", tex_path],
            cwd=output_dir,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # 输出文件可能位于 output_dir 下
        generated_pdf = os.path.join(output_dir, "analysis_report.pdf")
        if os.path.exists(generated_pdf):
            os.replace(generated_pdf, pdf_path)
        print(f"✅ PDF已导出: {pdf_path}")
        return pdf_path
    except subprocess.CalledProcessError as e:
        print(f"⚠️ PDF导出失败: {e}")
        return None


def _generate_comprehensive_mechanism_report(
    report: Dict,
    analysis_md_content: str,
    output_dir: str,
    language: str = 'zh-CN',
) -> Optional[str]:
    """
    生成完整的机理分析报告（整合AI评述和下一步实验建议）
    
    Args:
        report: 实验报告数据
        analysis_md_content: 分析Markdown内容
        output_dir: 输出目录
        language: 输出语言 ('zh-CN' 或 'en-US')
    """
    output_path = os.path.join(output_dir, "mechanism_report.md")
    
    # 获取 API Key
    openrouter_key = OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY")
    api_key = DEEPSEEK_API_KEY or OPENAI_API_KEY or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    
    if not (openrouter_key or api_key):
        print("⚠️ 机理分析报告跳过：未提供 API Key")
        return None
    
    # 注意：此prompt仅用于非OpenRouter的备用API调用
    # 主要逻辑使用下面try块中的增强版prompt
    prompt = f"""你是电化学专家。基于以下实验数据生成机理分析报告。
    
实验数据：
{analysis_md_content}

请包含：1.数据质量评估 2.Arrhenius分析 3.机理推断 4.异常分析 5.文献对比 6.实验建议"""

    try:
        if openrouter_key:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/eis-analysis",
                "X-Title": "Mechanism Analysis Report Generator",
            }
            
            # ✅ 使用配置的主模型
            primary_model = OPENROUTER_MODEL or os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-4.5")
            fallback_model = FALLBACK_MODEL or "anthropic/claude-3.7-sonnet"
            
            # ✅ 增强版Prompt - 包含领域知识约束和输出规范
            system_prompt = """你是一位资深的电化学和固态离子导体领域专家。
你的分析必须严格基于实验数据，遵循以下专业规范。

## 领域知识参考（用于对比分析，非绝对标准）

### 活化能(Ea)典型范围参考
| 电解质类型 | Ea范围(kJ/mol) | Ea范围(eV) | 典型传导机理 |
|-----------|---------------|-----------|-------------|
| 液态有机电解质 | 10-25 | 0.10-0.26 | 离子溶剂化迁移 |
| 聚合物电解质(>Tg) | 30-60 | 0.31-0.62 | 链段运动耦合 |
| 聚合物电解质(<Tg) | 60-100 | 0.62-1.04 | 离子跳跃 |
| 石榴石型(LLZO等) | 25-45 | 0.26-0.47 | 晶格空位跳跃 |
| 硫化物(Li₆PS₅Cl等) | 15-35 | 0.16-0.36 | 软晶格振动 |
| NASICON型 | 25-40 | 0.26-0.41 | 三维通道传导 |

### 数据质量评判标准
- R² ≥ 0.99: 优秀（线性关系极好，可用于精确定量）
- R² 0.95-0.99: 良好（适合定量分析）
- R² 0.90-0.95: 可接受（需讨论偏差原因）
- R² < 0.90: 需特别关注（可能存在机理转变或测量问题）

### 异常现象物理意义
- 电导率/Rb突变(>3倍): 可能为相变、玻璃化转变(Tg)或结晶
- 低温区拟合质量下降: 常见于高阻抗测量限制或接近Tg
- Arrhenius图斜率突变: 传导机理可能发生转变

## 分析原则
1. 所有结论必须引用具体实验数值作为依据
2. 使用"基于数据推断"而非"可能"、"也许"等模糊表述
3. 对于不确定的推断，明确标注"需进一步验证"
4. 禁止脱离数据的空泛描述"""

            user_content = f"""## 实验分析数据

{analysis_md_content}

---

## 请生成包含以下部分的机理分析报告

### 1. 实验概况与数据质量评估
- 量化统计：总测量点数、成功率、各R²等级分布
- 数据亮点和需关注的问题点
- 与上述"数据质量评判标准"对比评价

### 2. 电导率温度依赖性分析
- 分析log(σ) vs 1000/T的整体趋势
- 解释分段Arrhenius行为的物理意义
- 各分段活化能(Ea)数值与上述"典型范围参考"对比

### 3. 离子传输机理推断
- 基于Ea数值推断可能的主导传导机理
- 分析是否存在温度依赖的机理转变
- 讨论指前因子(σ₀)的物理意义

### 4. 异常现象深度分析
- 列出所有R²<0.95的数据点及其温度
- 逐一分析可能原因（对照"异常现象物理意义"）
- 提出验证方法

### 5. 与典型体系对比
- 与至少3种典型固态电解质体系对比（使用上述参考表格）
- 明确本材料的性能定位
- 评估潜在应用场景

### 6. 下一步实验建议（必须具体可操作）
按优先级排列，每条建议必须包含：
- 【优先级】: 立即/短期/长期
- 【具体参数】: 温度范围、频率、时间等具体数值
- 【预期收获】: 该实验能回答什么问题

建议方向包括但不限于：
- 温度范围优化（捕捉Tg或相变）
- EIS频率范围调整
- DSC/XRD等补充表征
- 样品制备改进

---

## 输出格式要求
- 使用Markdown格式
- 数值必须保留有效位数（Ea: X.XX kJ/mol, σ: X.XX×10⁻ⁿ S/cm, R²: 0.XXXX）
- 文献对比使用表格形式
- 建议部分使用编号列表，标注优先级"""
            
            # ✅ 语言指令：根据language参数添加输出语言要求
            if language == 'en-US':
                language_instruction = """

## LANGUAGE REQUIREMENT
**IMPORTANT: Please write your ENTIRE response in English.**
Use standard scientific English terminology for all sections including:
- Electrochemical terms (activation energy, ionic conductivity, impedance, etc.)
- Analysis sections and conclusions
- Experimental suggestions and recommendations
- Table headers and content
Do NOT use any Chinese characters in your response."""
                user_content += language_instruction
            
            # ✅ 优化参数：降低temperature提高一致性，增加max_tokens确保报告完整
            payload = {
                "model": primary_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.15,  # ✅ 降低temperature，提高科学分析的一致性
                "max_tokens": 8000,   # ✅ 增加token限制，确保长报告完整
            }
            
            print(f"🔄 正在生成完整机理分析报告")
            print(f"   主模型: {primary_model}")
            print(f"   备用模型: {fallback_model}")
            
            # ✅ 尝试主模型
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=300)
                resp.raise_for_status()
                data = resp.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    print(f"✅ 主模型 {primary_model} 生成成功")
                else:
                    raise ValueError(f"API 返回格式异常: {data}")
                    
            except Exception as e:
                print(f"⚠️ 主模型 {primary_model} 失败: {e}")
                print(f"🔄 切换到备用模型 {fallback_model}...")
                
                # ✅ 使用备用模型重试
                payload["model"] = fallback_model
                resp = requests.post(url, headers=headers, json=payload, timeout=300)
                resp.raise_for_status()
                data = resp.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    print(f"✅ 备用模型 {fallback_model} 生成成功")
                else:
                    raise ValueError(f"备用模型API返回格式异常: {data}")
        else:
            import openai  # type: ignore
            client = openai.OpenAI(api_key=api_key)
            model = os.environ.get("DEEPSEEK_MODEL", "gpt-4o-mini")
            print(f"🔄 正在生成完整机理分析报告 (model={model})...")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000,
            )
            content = resp.choices[0].message.content

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# 完整机理分析报告\n\n")
            f.write(f"*生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            f.write("---\n\n")
            f.write(content or "（无内容）")
        
        print(f"✅ 完整机理分析报告已生成: {output_path}")
        return output_path
        
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.text
        except:
            pass
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# 完整机理分析报告\n\n生成失败：{e}\n\n详细信息：\n```\n{error_detail}\n```\n")
        print(f"⚠️ 机理分析报告生成失败: {e}")
        if error_detail:
            print(f"   详细错误: {error_detail[:200]}")
        return output_path
    except Exception as e:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# 完整机理分析报告\n\n生成失败：{e}\n")
        print(f"⚠️ 机理分析报告生成失败: {e}")
        import traceback
        traceback.print_exc()
        return output_path


def bundle_report(
    report_json_path: str,
    output_dir: str,
    enable_ai_eval: bool = False,
    enable_pdf: bool = False,
) -> Dict:
    if not os.path.exists(report_json_path):
        print(f"⚠️ 未找到报告文件: {report_json_path}")
        return {}

    report = _load_report(report_json_path)
    os.makedirs(output_dir, exist_ok=True)

    plot_path, plot_meta = _generate_conductivity_plot(report, output_dir)
    analysis_md_path = _generate_analysis_markdown(report, plot_path, plot_meta, output_dir)

    # 读取 analysis_md 内容供后续使用
    analysis_md_content = ""
    if analysis_md_path and os.path.exists(analysis_md_path):
        with open(analysis_md_path, "r", encoding="utf-8") as f:
            analysis_md_content = f.read()

    # 生成完整的机理分析报告（整合AI评述和下一步建议）
    mechanism_report_path = None
    if enable_ai_eval:
        mechanism_report_path = _generate_comprehensive_mechanism_report(
            report, analysis_md_content, output_dir
        )

    pdf_path = None
    if enable_pdf:
        pdf_path = _export_pdf_from_md(analysis_md_path, output_dir)

    return {
        "analysis_report": analysis_md_path,
        "conductivity_plot": plot_path,
        "mechanism_report": mechanism_report_path,  # 完整机理分析报告
        "pdf_path": pdf_path,
    }


# ============================================================
# 数据预处理增强模块
# ============================================================

def preprocess_experiment_data(report: Dict) -> Dict[str, Any]:
    """
    预处理实验数据，计算统计信息供LLM分析使用
    """
    stats_data = {
        "total_points": 0,
        "successful_points": 0,
        "success_rate": 0.0,
        "temperature_range": {"min_C": None, "max_C": None, "min_K": None, "max_K": None},
        "conductivity_range": {"min": None, "max": None, "avg": None, "std": None},
        "r_squared_distribution": {"excellent": 0, "good": 0, "acceptable": 0, "poor": 0},
        "r_squared_stats": {"min": None, "max": None, "avg": None, "median": None},
        "anomaly_points": [],
        "segments_summary": [],
    }
    
    # 提取测量点
    measurements = report.get("successful_points", []) or []
    all_points = report.get("all_measurements", measurements)
    
    stats_data["total_points"] = len(all_points)
    stats_data["successful_points"] = len(measurements)
    stats_data["success_rate"] = len(measurements) / len(all_points) if all_points else 0.0
    
    if not measurements:
        return stats_data
    
    # 温度范围
    temps_C = [m.get("temperature_C", 0) for m in measurements if m.get("temperature_C") is not None]
    temps_K = [m.get("temperature_K", 0) for m in measurements if m.get("temperature_K") is not None]
    if temps_C:
        stats_data["temperature_range"]["min_C"] = min(temps_C)
        stats_data["temperature_range"]["max_C"] = max(temps_C)
    if temps_K:
        stats_data["temperature_range"]["min_K"] = min(temps_K)
        stats_data["temperature_range"]["max_K"] = max(temps_K)
    
    # 电导率统计
    conductivities = [m.get("conductivity_S_per_cm", 0) for m in measurements 
                      if m.get("conductivity_S_per_cm") and m.get("conductivity_S_per_cm") > 0]
    if conductivities:
        stats_data["conductivity_range"]["min"] = min(conductivities)
        stats_data["conductivity_range"]["max"] = max(conductivities)
        stats_data["conductivity_range"]["avg"] = sum(conductivities) / len(conductivities)
        if len(conductivities) > 1:
            stats_data["conductivity_range"]["std"] = float(np.std(conductivities))
    
    # R²分布统计
    r_squareds = [m.get("R_squared", m.get("r_squared", 0)) for m in measurements 
                  if m.get("R_squared") or m.get("r_squared")]
    for r2 in r_squareds:
        if r2 >= 0.99:
            stats_data["r_squared_distribution"]["excellent"] += 1
        elif r2 >= 0.95:
            stats_data["r_squared_distribution"]["good"] += 1
        elif r2 >= 0.90:
            stats_data["r_squared_distribution"]["acceptable"] += 1
        else:
            stats_data["r_squared_distribution"]["poor"] += 1
            # 记录异常点
            point = next((m for m in measurements if m.get("R_squared") == r2 or m.get("r_squared") == r2), None)
            if point:
                stats_data["anomaly_points"].append({
                    "temperature_C": point.get("temperature_C"),
                    "r_squared": r2,
                    "reason": "R² < 0.90"
                })
    
    if r_squareds:
        stats_data["r_squared_stats"]["min"] = min(r_squareds)
        stats_data["r_squared_stats"]["max"] = max(r_squareds)
        stats_data["r_squared_stats"]["avg"] = sum(r_squareds) / len(r_squareds)
        stats_data["r_squared_stats"]["median"] = float(np.median(r_squareds))
    
    # 分段摘要
    arr_analysis = report.get("arrhenius_analysis", {}) or {}
    segments = arr_analysis.get("segments", []) or []
    for seg in segments:
        stats_data["segments_summary"].append({
            "segment": seg.get("segment", ""),
            "temp_range_K": f"{seg.get('T_min_K', 0):.1f}-{seg.get('T_max_K', 0):.1f}",
            "Ea_kJ_mol": seg.get("Ea_kJ_per_mol"),
            "Ea_eV": seg.get("Ea_kJ_per_mol", 0) / 96.485 if seg.get("Ea_kJ_per_mol") else None,
            "R_squared": seg.get("R_squared"),
            "n_points": seg.get("n_points"),
        })
    
    return stats_data


def generate_analysis_charts(report: Dict, output_dir: str) -> Dict[str, str]:
    """
    生成分析图表（R²分布图、电导率趋势图、活化能对比图）
    """
    chart_paths = {}
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    measurements = report.get("successful_points", []) or []
    arr_analysis = report.get("arrhenius_analysis", {}) or {}
    segments = arr_analysis.get("segments", []) or []
    
    # 1. R²分布饼图
    try:
        r_squareds = [m.get("R_squared", m.get("r_squared", 0)) for m in measurements 
                      if m.get("R_squared") or m.get("r_squared")]
        if r_squareds:
            dist = {"Excellent (>=0.99)": 0, "Good (0.95-0.99)": 0, 
                    "Acceptable (0.90-0.95)": 0, "Poor (<0.90)": 0}
            for r2 in r_squareds:
                if r2 >= 0.99:
                    dist["Excellent (>=0.99)"] += 1
                elif r2 >= 0.95:
                    dist["Good (0.95-0.99)"] += 1
                elif r2 >= 0.90:
                    dist["Acceptable (0.90-0.95)"] += 1
                else:
                    dist["Poor (<0.90)"] += 1
            
            # 过滤掉为0的类别
            labels = [k for k, v in dist.items() if v > 0]
            sizes = [v for v in dist.values() if v > 0]
            colors = ['#2ecc71', '#3498db', '#f39c12', '#e74c3c'][:len(labels)]
            
            if sizes:
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax.set_title('R-squared Distribution', fontsize=14)
                ax.axis('equal')
                
                r2_chart_path = os.path.join(output_dir, "r_squared_distribution.png")
                plt.savefig(r2_chart_path, dpi=150, bbox_inches='tight')
                plt.close()
                chart_paths["r_squared_distribution"] = r2_chart_path
                print(f"[Chart] R-squared distribution saved: {r2_chart_path}")
    except Exception as e:
        print(f"[Chart] R-squared distribution generation failed: {e}")
    
    # 2. 电导率温度趋势图
    try:
        temps = [m.get("temperature_C") for m in measurements if m.get("temperature_C") is not None]
        conds = [m.get("conductivity_S_per_cm") for m in measurements if m.get("conductivity_S_per_cm")]
        
        if temps and conds and len(temps) == len(conds):
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(temps, conds, c='#3498db', alpha=0.7, s=50)
            ax.set_xlabel('Temperature (C)', fontsize=12)
            ax.set_ylabel('Conductivity (S/cm)', fontsize=12)
            ax.set_title('Conductivity vs Temperature', fontsize=14)
            ax.set_yscale('log')
            ax.grid(True, alpha=0.3)
            
            trend_chart_path = os.path.join(output_dir, "conductivity_trend.png")
            plt.savefig(trend_chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            chart_paths["conductivity_trend"] = trend_chart_path
            print(f"[Chart] Conductivity trend saved: {trend_chart_path}")
    except Exception as e:
        print(f"[Chart] Conductivity trend generation failed: {e}")
    
    # 3. 活化能对比柱状图（多段对比）
    try:
        if segments and len(segments) > 0:
            seg_names = [f"Segment {s.get('segment', i+1)}" for i, s in enumerate(segments)]
            ea_values = [s.get("Ea_kJ_per_mol", 0) for s in segments]
            r2_values = [s.get("R_squared", 0) for s in segments]
            
            fig, ax1 = plt.subplots(figsize=(10, 6))
            
            x = np.arange(len(seg_names))
            width = 0.35
            
            bars1 = ax1.bar(x - width/2, ea_values, width, label='Ea (kJ/mol)', color='#3498db')
            ax1.set_ylabel('Activation Energy (kJ/mol)', fontsize=12, color='#3498db')
            ax1.tick_params(axis='y', labelcolor='#3498db')
            
            ax2 = ax1.twinx()
            bars2 = ax2.bar(x + width/2, r2_values, width, label='R-squared', color='#2ecc71')
            ax2.set_ylabel('R-squared', fontsize=12, color='#2ecc71')
            ax2.tick_params(axis='y', labelcolor='#2ecc71')
            ax2.set_ylim(0, 1.05)
            
            ax1.set_xlabel('Segments', fontsize=12)
            ax1.set_title('Activation Energy Comparison by Segments', fontsize=14)
            ax1.set_xticks(x)
            ax1.set_xticklabels(seg_names)
            
            # 添加数值标签
            for bar in bars1:
                height = bar.get_height()
                ax1.annotate(f'{height:.1f}',
                           xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points",
                           ha='center', va='bottom', fontsize=9)
            
            fig.legend(loc='upper right', bbox_to_anchor=(0.9, 0.95))
            
            ea_chart_path = os.path.join(output_dir, "activation_energy_comparison.png")
            plt.savefig(ea_chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            chart_paths["activation_energy_comparison"] = ea_chart_path
            print(f"[Chart] Activation energy comparison saved: {ea_chart_path}")
    except Exception as e:
        print(f"[Chart] Activation energy comparison generation failed: {e}")
    
    return chart_paths


# ============================================================
# 多轮对话模块
# ============================================================

class AIConversationManager:
    """AI多轮对话管理器 - SQLite持久化"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认存储在experiment_data目录下
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(base_dir, "experiment_data", "ai_conversations.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化SQLite数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 会话表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                experiment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                context TEXT,
                material_info TEXT
            )
        """)
        
        # 消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        
        conn.commit()
        conn.close()
        print(f"[AI Conversation] Database initialized: {self.db_path}")
    
    def create_conversation(self, experiment_id: str, initial_context: str = None) -> str:
        """创建新会话"""
        import uuid
        conv_id = f"conv_{uuid.uuid4().hex[:8]}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (id, experiment_id, context) VALUES (?, ?, ?)",
            (conv_id, experiment_id, initial_context)
        )
        conn.commit()
        conn.close()
        
        return conv_id
    
    def get_conversation(self, conv_id: str) -> Dict:
        """获取会话信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        conv = cursor.fetchone()
        
        if not conv:
            conn.close()
            return None
        
        cursor.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conv_id,)
        )
        messages = cursor.fetchall()
        
        conn.close()
        
        return {
            "id": conv[0],
            "experiment_id": conv[1],
            "created_at": conv[2],
            "updated_at": conv[3],
            "context": conv[4],
            "material_info": conv[5],
            "messages": [{"role": m[0], "content": m[1], "created_at": m[2]} for m in messages]
        }
    
    def get_conversations_by_experiment(self, experiment_id: str) -> List[Dict]:
        """获取实验的所有会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, created_at, updated_at FROM conversations WHERE experiment_id = ? ORDER BY updated_at DESC",
            (experiment_id,)
        )
        convs = cursor.fetchall()
        conn.close()
        
        return [{"id": c[0], "created_at": c[1], "updated_at": c[2]} for c in convs]
    
    def add_message(self, conv_id: str, role: str, content: str):
        """添加消息到会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conv_id, role, content)
        )
        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conv_id,)
        )
        
        conn.commit()
        conn.close()
    
    def update_material_info(self, conv_id: str, material_info: str):
        """更新材料信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE conversations SET material_info = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (material_info, conv_id)
        )
        conn.commit()
        conn.close()


def chat_with_ai(
    conversation_id: str,
    user_message: str,
    experiment_context: str = None,
    history_comparison: List[Dict] = None,
    language: str = 'zh-CN',
) -> str:
    """
    多轮对话接口 - 支持上下文和历史对比
    
    Args:
        conversation_id: 会话ID
        user_message: 用户消息
        experiment_context: 当前实验的上下文信息
        history_comparison: 历史实验对比数据
        language: 输出语言 ('zh-CN' 或 'en-US')
    
    Returns:
        AI回复内容
    """
    manager = AIConversationManager()
    conversation = manager.get_conversation(conversation_id)
    
    if not conversation:
        if language == 'en-US':
            return "Conversation does not exist, please create a conversation first."
        return "会话不存在，请先创建会话。"
    
    # 构建对话历史
    messages = []
    
    # System prompt - 根据语言选择
    if language == 'en-US':
        system_content = """You are a senior expert in electrochemistry and solid-state ionic conductors.
You are having a multi-turn conversation with researchers to help them analyze experimental data.

## Your Responsibilities
1. Answer professional questions about electrochemical experiments
2. Analyze experimental data and provide professional interpretations
3. Give targeted suggestions based on material information and preparation methods provided by users
4. Compare historical experimental data and summarize patterns

## Conversation Style
- Professional but friendly
- Conclusions must be supported by data
- Give specific actionable suggestions
- Use Markdown format for replies
- ALWAYS respond in English"""
    else:
        system_content = """你是一位资深的电化学和固态离子导体领域专家。
你正在与研究人员进行多轮对话，帮助他们分析实验数据。

## 你的职责
1. 回答关于电化学实验的专业问题
2. 分析实验数据并给出专业解读
3. 根据用户提供的材料信息和制备方法，给出更有针对性的建议
4. 对比历史实验数据，总结规律

## 对话风格
- 专业但友好
- 结论必须有数据支撑
- 给出具体可操作的建议
- 使用Markdown格式回复"""
    
    # 添加实验上下文
    if experiment_context:
        system_content += f"\n\n## 当前实验数据概览\n{experiment_context}"
    
    # 添加材料信息（如果有）
    if conversation.get("material_info"):
        system_content += f"\n\n## 材料信息\n{conversation['material_info']}"
    
    # 添加历史对比信息
    if history_comparison:
        system_content += "\n\n## 历史实验对比数据\n"
        for i, hist in enumerate(history_comparison):
            system_content += f"\n### 历史实验 {i+1}: {hist.get('experiment_id', 'Unknown')}\n"
            system_content += f"- 活化能: {hist.get('Ea_kJ_mol', 'N/A')} kJ/mol\n"
            system_content += f"- 温度范围: {hist.get('temp_range', 'N/A')}\n"
            system_content += f"- 最高电导率: {hist.get('max_conductivity', 'N/A')} S/cm\n"
    
    messages.append({"role": "system", "content": system_content})
    
    # 添加历史消息
    for msg in conversation.get("messages", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # 添加当前用户消息
    messages.append({"role": "user", "content": user_message})
    
    # 保存用户消息
    manager.add_message(conversation_id, "user", user_message)
    
    # 调用API
    config = _get_api_config()
    openrouter_key = config["openrouter_api_key"]
    
    if not openrouter_key:
        return "API Key未配置，无法进行对话。"
    
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/eis-analysis",
            "X-Title": "EIS Analysis Chat",
        }
        
        # 多轮对话使用更快的模型
        model = config.get("fallback_model", "anthropic/claude-3.7-sonnet")
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,  # 对话模式稍高温度
            "max_tokens": 2000,
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            ai_response = data["choices"][0]["message"]["content"]
            
            # 保存AI回复
            manager.add_message(conversation_id, "assistant", ai_response)
            
            return ai_response
        else:
            return "API返回格式异常，请稍后重试。"
            
    except Exception as e:
        print(f"[Chat] Error: {e}")
        return f"对话失败: {str(e)}"


# ============================================================
# 历史数据对比模块
# ============================================================

def load_history_experiments(history_dir: str, exp_ids: List[str] = None) -> List[Dict]:
    """
    加载历史实验数据用于对比
    
    Args:
        history_dir: 历史数据目录
        exp_ids: 要加载的实验ID列表，为None则加载全部
    
    Returns:
        历史实验摘要列表
    """
    results = []
    
    if not os.path.exists(history_dir):
        return results
    
    # 获取所有实验目录
    if exp_ids:
        exp_dirs = [os.path.join(history_dir, eid) for eid in exp_ids]
    else:
        exp_dirs = [os.path.join(history_dir, d) for d in os.listdir(history_dir) 
                    if os.path.isdir(os.path.join(history_dir, d))]
    
    for exp_dir in exp_dirs:
        if not os.path.exists(exp_dir):
            continue
            
        report_file = os.path.join(exp_dir, "report.json")
        if not os.path.exists(report_file):
            continue
        
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                report = json.load(f)
            
            # 提取摘要信息
            arr_analysis = report.get("arrhenius_analysis", {}) or {}
            segments = arr_analysis.get("segments", []) or []
            measurements = report.get("successful_points", []) or []
            
            # 计算主要指标
            ea_values = [s.get("Ea_kJ_per_mol") for s in segments if s.get("Ea_kJ_per_mol")]
            conductivities = [m.get("conductivity_S_per_cm") for m in measurements 
                            if m.get("conductivity_S_per_cm") and m.get("conductivity_S_per_cm") > 0]
            temps = [m.get("temperature_C") for m in measurements if m.get("temperature_C") is not None]
            
            summary = {
                "experiment_id": os.path.basename(exp_dir),
                "timestamp": report.get("experiment_info", {}).get("start_time"),
                "Ea_kJ_mol": ea_values[0] if ea_values else None,
                "Ea_eV": ea_values[0] / 96.485 if ea_values else None,
                "temp_range": f"{min(temps):.1f}~{max(temps):.1f} C" if temps else None,
                "max_conductivity": max(conductivities) if conductivities else None,
                "min_conductivity": min(conductivities) if conductivities else None,
                "n_points": len(measurements),
                "n_segments": len(segments),
            }
            
            results.append(summary)
            
        except Exception as e:
            print(f"[History] Failed to load {exp_dir}: {e}")
            continue
    
    return results


def compare_experiments(current_report: Dict, history_experiments: List[Dict]) -> str:
    """
    生成实验对比分析
    
    Args:
        current_report: 当前实验报告
        history_experiments: 历史实验摘要列表
    
    Returns:
        对比分析Markdown文本
    """
    if not history_experiments:
        return "暂无历史实验数据可供对比。"
    
    # 当前实验摘要
    current_stats = preprocess_experiment_data(current_report)
    arr_analysis = current_report.get("arrhenius_analysis", {}) or {}
    segments = arr_analysis.get("segments", []) or []
    current_ea = segments[0].get("Ea_kJ_per_mol") if segments else None
    
    # 构建对比表格
    md = "## 实验对比分析\n\n"
    md += "| 实验 | 活化能 (kJ/mol) | 温度范围 | 最高电导率 (S/cm) | 数据点数 |\n"
    md += "|------|----------------|----------|------------------|----------|\n"
    
    # 当前实验
    temp_range = current_stats.get("temperature_range", {})
    md += f"| **当前** | {current_ea:.2f} | {temp_range.get('min_C', 'N/A')}~{temp_range.get('max_C', 'N/A')} C | "
    md += f"{current_stats['conductivity_range'].get('max', 'N/A'):.2e} | {current_stats['successful_points']} |\n"
    
    # 历史实验
    for hist in history_experiments:
        md += f"| {hist['experiment_id']} | "
        md += f"{hist.get('Ea_kJ_mol', 'N/A'):.2f} | " if hist.get('Ea_kJ_mol') else "N/A | "
        md += f"{hist.get('temp_range', 'N/A')} | "
        md += f"{hist.get('max_conductivity', 'N/A'):.2e} | " if hist.get('max_conductivity') else "N/A | "
        md += f"{hist.get('n_points', 'N/A')} |\n"
    
    # 统计分析
    all_ea = [current_ea] + [h.get("Ea_kJ_mol") for h in history_experiments if h.get("Ea_kJ_mol")]
    all_ea = [e for e in all_ea if e is not None]
    
    if len(all_ea) > 1:
        md += f"\n### 活化能统计\n"
        md += f"- 平均值: {np.mean(all_ea):.2f} kJ/mol\n"
        md += f"- 标准差: {np.std(all_ea):.2f} kJ/mol\n"
        md += f"- 范围: {min(all_ea):.2f} ~ {max(all_ea):.2f} kJ/mol\n"
        
        if current_ea:
            z_score = (current_ea - np.mean(all_ea)) / np.std(all_ea) if np.std(all_ea) > 0 else 0
            md += f"- 当前实验Z-score: {z_score:.2f}\n"
    
    return md
