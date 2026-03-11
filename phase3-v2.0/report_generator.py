# -*- coding: utf-8 -*-
"""
Full Report Generator (HTML with embedded images and Python-rendered formulas)

Merges the enhanced deep analysis text + Phase3 ML figures + quantitative
data tables into a single self-contained HTML report (paper-like format).

All LaTeX formulas are converted to HTML+CSS on the Python side,
so the report works fully offline with no CDN dependencies.

Version: 2.2
Date: 2026-02-06
"""

import json
import base64
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


# ================================================================
# Public API
# ================================================================

def generate_full_report(
    analysis_md_path: Path,
    phase3v2_output_dir: Path,
    output_path: Path,
    material: str = "S8",
    agent_log: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate a comprehensive HTML report.

    Args:
        analysis_md_path:    Path to the enhanced deep analysis MD file
        phase3v2_output_dir: Phase3 v2.0 output directory (images + JSON)
        output_path:         Where to write the HTML report
        material:            Material ID
        agent_log:           Optional agent execution metadata (mode, thought_log, tools_called, etc.)

    Returns:
        Output file path as a string
    """
    analysis_md = analysis_md_path.read_text(encoding="utf-8")
    ml_data = _load_ml_data(phase3v2_output_dir)
    images = _load_images(phase3v2_output_dir)
    sections = _parse_md_sections(analysis_md)
    html = _build_html(material, sections, images, ml_data, agent_log)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


# ================================================================
# LaTeX → HTML converter (pure Python, no CDN)
# ================================================================

# Greek letter map
_GREEK = {
    "alpha": "\u03b1", "beta": "\u03b2", "gamma": "\u03b3", "delta": "\u03b4",
    "epsilon": "\u03b5", "zeta": "\u03b6", "eta": "\u03b7", "theta": "\u03b8",
    "iota": "\u03b9", "kappa": "\u03ba", "lambda": "\u03bb", "mu": "\u03bc",
    "nu": "\u03bd", "xi": "\u03be", "pi": "\u03c0", "rho": "\u03c1",
    "sigma": "\u03c3", "tau": "\u03c4", "phi": "\u03c6", "chi": "\u03c7",
    "psi": "\u03c8", "omega": "\u03c9",
    "Alpha": "\u0391", "Beta": "\u0392", "Gamma": "\u0393", "Delta": "\u0394",
    "Epsilon": "\u0395", "Theta": "\u0398", "Lambda": "\u039b", "Pi": "\u03a0",
    "Sigma": "\u03a3", "Phi": "\u03a6", "Psi": "\u03a8", "Omega": "\u03a9",
}

_OPERATORS = {
    "\\pm": "\u00b1", "\\mp": "\u2213", "\\times": "\u00d7", "\\cdot": "\u00b7",
    "\\leq": "\u2264", "\\geq": "\u2265", "\\neq": "\u2260", "\\approx": "\u2248",
    "\\infty": "\u221e", "\\rightarrow": "\u2192", "\\leftarrow": "\u2190",
    "\\Rightarrow": "\u21d2", "\\sim": "\u223c", "\\propto": "\u221d",
    "\\partial": "\u2202", "\\nabla": "\u2207",
}


def _find_brace_group(s: str, start: int) -> Tuple[str, int]:
    """
    Find the content inside matching braces starting at position `start`.
    s[start] must be '{'. Returns (content, end_index_inclusive).
    """
    if start >= len(s) or s[start] != "{":
        return ("", start)
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return (s[start + 1 : i], i)
    # Unmatched — return everything after {
    return (s[start + 1 :], len(s) - 1)


def _latex_to_html(latex: str) -> str:
    """
    Convert a LaTeX math expression to HTML with Unicode symbols and
    <sup>/<sub>/<span> tags.  Handles the formulas common in this project.
    """
    s = latex.strip()

    # ---- Pass 0a: \boxed{...} → bordered block ----
    while "\\boxed{" in s:
        idx = s.index("\\boxed{")
        content, end = _find_brace_group(s, idx + 6)
        inner = _latex_to_html(content)
        s = s[:idx] + f'<span class="math-boxed">{inner}</span>' + s[end + 1 :]

    # ---- Pass 0b: \mathrm{...} → upright text ----
    while "\\mathrm{" in s:
        idx = s.index("\\mathrm{")
        content, end = _find_brace_group(s, idx + 7)
        inner = _latex_to_html(content)
        s = s[:idx] + f'<span style="font-style:normal">{inner}</span>' + s[end + 1 :]

    # ---- Pass 1: \mathbf{...} → <b>...</b> ----
    while "\\mathbf{" in s:
        idx = s.index("\\mathbf{")
        content, end = _find_brace_group(s, idx + 7)
        inner = _latex_to_html(content)
        s = s[:idx] + f"<b>{inner}</b>" + s[end + 1 :]

    # ---- Pass 1b: \textbf{...} → <b>...</b> ----
    while "\\textbf{" in s:
        idx = s.index("\\textbf{")
        content, end = _find_brace_group(s, idx + 7)
        inner = _latex_to_html(content)
        s = s[:idx] + f"<b>{inner}</b>" + s[end + 1 :]

    # ---- Pass 2: \text{...} → plain text ----
    while "\\text{" in s:
        idx = s.index("\\text{")
        content, end = _find_brace_group(s, idx + 5)
        s = s[:idx] + content + s[end + 1 :]

    # ---- Pass 3: \frac{...}{...} → fraction ----
    while "\\frac{" in s:
        idx = s.index("\\frac{")
        num, end1 = _find_brace_group(s, idx + 5)
        den_start = end1 + 1
        if den_start < len(s) and s[den_start] == "{":
            den, end2 = _find_brace_group(s, den_start)
        else:
            den, end2 = ("?", den_start)
        num_html = _latex_to_html(num)
        den_html = _latex_to_html(den)
        frac_html = (
            f'<span class="frac">'
            f'<span class="frac-num">{num_html}</span>'
            f'<span class="frac-den">{den_html}</span>'
            f'</span>'
        )
        s = s[:idx] + frac_html + s[end2 + 1 :]

    # ---- Pass 4: Greek letters ----
    for name, char in sorted(_GREEK.items(), key=lambda x: -len(x[0])):
        s = s.replace(f"\\{name}", char)

    # ---- Pass 5: Operators ----
    for cmd, sym in _OPERATORS.items():
        s = s.replace(cmd, sym)

    # ---- Pass 6: Named functions ----
    for fn in ["ln", "log", "exp", "sin", "cos", "tan", "max", "min", "lim"]:
        s = s.replace(f"\\{fn}", f'<span class="math-fn">{fn}</span>')

    # ---- Pass 7: \quad, \, spacing ----
    s = s.replace("\\quad", " &ensp; ")
    s = s.replace("\\qquad", " &emsp; ")
    s = s.replace("\\,", " ")
    s = s.replace("\\;", " ")
    s = s.replace("\\ ", " ")

    # ---- Pass 7b: \left( \right) → plain brackets ----
    s = s.replace("\\left(", "(")
    s = s.replace("\\right)", ")")
    s = s.replace("\\left[", "[")
    s = s.replace("\\right]", "]")
    s = s.replace("\\left\\{", "{")
    s = s.replace("\\right\\}", "}")
    s = s.replace("\\left.", "")
    s = s.replace("\\right.", "")

    # ---- Pass 8: Superscript ^{...} and ^x ----
    while "^{" in s:
        idx = s.index("^{")
        content, end = _find_brace_group(s, idx + 1)
        inner = _latex_to_html(content)
        s = s[:idx] + f"<sup>{inner}</sup>" + s[end + 1 :]
    s = re.sub(r"\^([0-9a-zA-Z\u0370-\u03ff])", r"<sup>\1</sup>", s)

    # ---- Pass 9: Subscript _{...} and _x ----
    while "_{" in s:
        idx = s.index("_{")
        content, end = _find_brace_group(s, idx + 1)
        inner = _latex_to_html(content)
        s = s[:idx] + f"<sub>{inner}</sub>" + s[end + 1 :]
    s = re.sub(r"_([0-9a-zA-Z\u0370-\u03ff])", r"<sub>\1</sub>", s)

    # ---- Pass 10: Clean up remaining backslashes ----
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)

    return s


# ================================================================
# Data loading helpers
# ================================================================

def _load_ml_data(phase3_dir: Path) -> Dict[str, Any]:
    data = {}
    load_map = {
        "metrics": phase3_dir / "models" / "metrics.json",
        "confinement": phase3_dir / "confinement" / "summary.json",
        "meyer_neldel": phase3_dir / "meyer_neldel" / "summary.json",
        "cross_material": phase3_dir / "cross_material" / "summary.json",
    }
    for key, path in load_map.items():
        if path.exists():
            try:
                data[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return data


def _load_images(phase3_dir: Path) -> Dict[str, str]:
    images = {}
    image_files = {
        "delta_ea": phase3_dir / "confinement" / "delta_ea_plot.png",
        "meyer_neldel": phase3_dir / "meyer_neldel" / "meyer_neldel_s8.png",
    }
    for key, path in image_files.items():
        if path.exists():
            raw = path.read_bytes()
            images[key] = base64.b64encode(raw).decode("ascii")
    return images


# ================================================================
# Markdown parsing
# ================================================================

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


def _is_chinese_metadata(text: str) -> bool:
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return True
    cjk_lines = sum(1 for l in lines if _CJK_PATTERN.search(l))
    return cjk_lines > len(lines) * 0.4


def _parse_md_sections(md: str) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    current_title = ""
    current_body: List[str] = []

    for line in md.split("\n"):
        # Match both h1 (# ) and h2 (## ) as section headings
        if re.match(r"^#{1,2}\s", line):
            if current_title or current_body:
                body_text = "\n".join(current_body)
                if current_title or not _is_chinese_metadata(body_text):
                    sections.append({"title": current_title, "body": body_text})
            # Strip leading # symbols
            current_title = re.sub(r"^#+\s*", "", line).strip()
            current_body = []
        else:
            current_body.append(line)

    if current_title or current_body:
        body_text = "\n".join(current_body)
        if current_title or not _is_chinese_metadata(body_text):
            sections.append({"title": current_title, "body": body_text})

    return sections


# ================================================================
# Markdown → HTML conversion
# ================================================================

def _md_to_html_basic(md_text: str) -> str:
    lines = md_text.split("\n")
    html_lines: List[str] = []
    in_table = False
    in_list = False
    in_code = False
    in_formula_block = False
    formula_lines: List[str] = []
    formula_block_delim = ""  # "$$" or "\\["

    for line in lines:
        stripped = line.strip()

        # ─── Multi-line formula blocks: $$ ... $$ or \[ ... \] ───
        if stripped in ("$$", "\\[") and not in_formula_block:
            in_formula_block = True
            formula_block_delim = "\\]" if stripped == "\\[" else "$$"
            formula_lines = []
            continue
        if stripped == formula_block_delim and in_formula_block:
            in_formula_block = False
            formula_content = " ".join(formula_lines)
            html_lines.append(f'<div class="formula">{_latex_to_html(formula_content)}</div>')
            continue
        if in_formula_block:
            formula_lines.append(stripped)
            continue

        # Code blocks
        if stripped.startswith("```"):
            if in_code:
                html_lines.append("</code></pre>")
                in_code = False
            else:
                html_lines.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            html_lines.append(_escape_html(line))
            continue

        # Blank lines
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_table:
                html_lines.append("</tbody></table>")
                in_table = False
            html_lines.append("")
            continue

        # Single-line $$ formula
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            formula = stripped[2:-2].strip()
            html_lines.append(f'<div class="formula">{_latex_to_html(formula)}</div>')
            continue

        # Single-line \[...\] formula
        if stripped.startswith("\\[") and stripped.endswith("\\]") and len(stripped) > 4:
            formula = stripped[2:-2].strip()
            html_lines.append(f'<div class="formula">{_latex_to_html(formula)}</div>')
            continue

        # Tables
        if "|" in stripped and not stripped.startswith("$$"):
            cells = [c.strip() for c in stripped.split("|")]
            cells = [c for c in cells if c]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                html_lines.append('<table class="data-table"><thead><tr>')
                for c in cells:
                    html_lines.append(f"<th>{_inline_format(c)}</th>")
                html_lines.append("</tr></thead><tbody>")
                in_table = True
            else:
                html_lines.append("<tr>")
                for c in cells:
                    html_lines.append(f"<td>{_inline_format(c)}</td>")
                html_lines.append("</tr>")
            continue

        if in_table and "|" not in stripped:
            html_lines.append("</tbody></table>")
            in_table = False

        # #### sub-sub-headings
        if stripped.startswith("#### "):
            html_lines.append(f"<h5>{_inline_format(stripped[5:])}</h5>")
            continue

        # ### headings
        if stripped.startswith("### "):
            html_lines.append(f"<h4>{_inline_format(stripped[4:])}</h4>")
            continue

        # Unordered list
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            content = stripped[2:]
            indent_level = len(line) - len(line.lstrip())
            cls = ' class="nested"' if indent_level > 2 else ""
            html_lines.append(f"<li{cls}>{_inline_format(content)}</li>")
            continue

        if in_list and not (stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("  ")):
            html_lines.append("</ul>")
            in_list = False

        # Ordered list
        if re.match(r"^\d+\.\s", stripped):
            content = re.sub(r"^\d+\.\s", "", stripped)
            html_lines.append(f"<p class='numbered-item'>{_inline_format(content)}</p>")
            continue

        # Horizontal rule
        if stripped == "---":
            html_lines.append("<hr>")
            continue

        # Skip # top-level headings (handled by section parser)
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue

        # Default: paragraph
        html_lines.append(f"<p>{_inline_format(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_table:
        html_lines.append("</tbody></table>")

    return "\n".join(html_lines)


def _inline_format(text: str) -> str:
    """Process inline Markdown formatting including inline math."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)

    # Inline math: \(...\) → rendered HTML
    def _replace_paren_math(m):
        return f'<span class="math-inline">{_latex_to_html(m.group(1))}</span>'
    text = re.sub(r"\\\((.+?)\\\)", _replace_paren_math, text)

    # Inline math: $...$ → rendered HTML (avoid matching $$)
    def _replace_dollar_math(m):
        return f'<span class="math-inline">{_latex_to_html(m.group(1))}</span>'
    text = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", _replace_dollar_math, text)

    return text


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ================================================================
# HTML assembly
# ================================================================

def _build_html(material: str, sections, images, ml_data, agent_log=None) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    report_model = (agent_log or {}).get("report_model", "LLM")
    # Friendly display name
    _MODEL_DISPLAY = {
        "openai/gpt-5.2": "GPT-5.2",
        "anthropic/claude-opus-4.5": "Claude Opus 4.5",
        "anthropic/claude-sonnet-4": "Claude Sonnet 4",
    }
    report_model = _MODEL_DISPLAY.get(report_model, report_model)
    body_parts = []

    for i, sec in enumerate(sections):
        title = sec["title"]
        body_html = _md_to_html_basic(sec["body"])

        figure_html = ""
        title_lower = title.lower()
        # Insert delta_Ea figure near Arrhenius / activation energy / confinement sections
        _is_arrhenius_sec = (
            ("arrhenius" in title_lower and ("slope" in title_lower or "segment" in title_lower or "ea" in title_lower))
            or ("activation" in title_lower and "energy" in title_lower)
            or ("confinement" in title_lower and ("quanti" in title_lower or "delta" in title_lower or "ea" in title_lower))
        )
        if _is_arrhenius_sec:
            if "delta_ea" in images:
                figure_html = _figure_block(
                    images["delta_ea"],
                    "Figure 1. Confinement effect \u0394Ea = Ea(S8) \u2212 Ea(S60 predicted) as a function of "
                    "temperature. The negative slope (\u22122.15 \u00d7 10\u207b\u00b3 eV/K) indicates that the "
                    "confinement penalty diminishes at higher temperatures. Red line: linear fit; dashed line: \u0394Ea = 0.",
                    "fig-delta-ea"
                )
            if "meyer_neldel" in images:
                figure_html += _figure_block(
                    images["meyer_neldel"],
                    "Figure 2. Meyer-Neldel compensation plot: ln(\u03c3\u2080) vs Ea for S8 material. "
                    "The strong linear correlation (R\u00b2 = 0.981) indicates a compensation effect with "
                    "E_MN = 0.020 eV. The slope of 49.9 corresponds to 1/E_MN.",
                    "fig-meyer-neldel"
                )

        section_id = f"section-{i}"
        if title:
            body_parts.append(f'<section id="{section_id}">')
            body_parts.append(f'<h2>{_inline_format(title)}</h2>')
            body_parts.append(body_html)
            if figure_html:
                body_parts.append(figure_html)
            body_parts.append('</section>')
        else:
            body_parts.append(body_html)

    ml_summary = _build_ml_summary_table(ml_data)
    agent_section = _build_agent_process_section(agent_log) if agent_log else ""
    body_content = "\n".join(body_parts)

    # Determine mode label
    mode_label = "Pipeline" if not agent_log else agent_log.get("mode", "pipeline").capitalize()
    if mode_label.lower() == "react":
        mode_label = "ReAct Agent (LLM-driven autonomous reasoning)"
    else:
        mode_label = "Automated Pipeline"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{material} Enhanced Deep Mechanism Analysis Report</title>
<style>
{_get_css()}
</style>
</head>
<body>

<header class="report-header">
    <div class="header-content">
        <h1>{material} Material: Enhanced Deep Mechanism Analysis</h1>
        <p class="subtitle">Integrating EIS Experimental Data with ML Quantitative Modeling</p>
        <div class="meta">
            <span>Generated: {timestamp}</span>
            <span>Model: {report_model}</span>
            <span>Mode: {mode_label}</span>
        </div>
    </div>
</header>

<nav class="toc">
    <h3>Table of Contents</h3>
    <ol>
        {"<li><a href=" + '"#agent-process">Agent Analysis Process</a></li>' if agent_section else ""}
        <li><a href="#section-1">EIS Curve Morphology</a></li>
        <li><a href="#section-2">Arrhenius Slope Variations &amp; ML Analysis</a></li>
        <li><a href="#section-3">Temperature-Dependent Mechanisms</a></li>
        <li><a href="#section-4">Optimal R-N Predictions</a></li>
        <li><a href="#section-5">Experimental Recommendations</a></li>
        <li><a href="#section-6">Application Scenarios</a></li>
        <li><a href="#section-7">Conclusions</a></li>
        <li><a href="#ml-summary">Appendix: ML Modeling Summary</a></li>
    </ol>
</nav>

<main class="report-body">

{agent_section}

{body_content}

<section id="ml-summary">
    <h2>Appendix: ML Modeling Quantitative Summary</h2>
    {ml_summary}
</section>
</main>

<footer class="report-footer">
    <p>Report generated by Phase3 v2.0 Agent | Data: 41 samples, 123 Arrhenius segments | ML models: R&sup2; &gt; 0.79</p>
    <p>&copy; 2026 EIS Data Analysis System</p>
</footer>

</body>
</html>"""


def _figure_block(img_b64: str, caption: str, fig_id: str) -> str:
    return f"""
<figure id="{fig_id}" class="report-figure">
    <img src="data:image/png;base64,{img_b64}" alt="{fig_id}">
    <figcaption>{caption}</figcaption>
</figure>
"""


# Material identity mapping
_MAT_IDENTITY = {
    "S8":  ("Sepiolite + H\u2083PO\u2084", "0.5 nm pore"),
    "S14": ("Halloysite + H\u2083PO\u2084", "~15 nm tubular"),
    "S16": ("Bentonite + H\u2083PO\u2084", "~1.2 nm layered"),
    "S95": ("Sepiolite + H\u2082SO\u2084", "0.5 nm pore"),
    "S96": ("Bentonite + H\u2082SO\u2084", "~1.2 nm layered"),
    "S97": ("Halloysite + H\u2082SO\u2084", "~15 nm tubular"),
    "S6":  ("Sepiolite + Phytic acid", "0.5 nm pore"),
    "S13": ("Bentonite + Phytic acid", "~1.2 nm layered"),
    "S15": ("Kaolin + Phytic acid", "~0.7 nm layered"),
    "S12": ("Pure water", "no confinement"),
    "S60": ("Pure H\u2083PO\u2084 liquid", "bulk baseline"),
}


def _build_agent_process_section(agent_log: Dict[str, Any]) -> str:
    """Build the 'How This Report Was Generated' section."""
    if not agent_log:
        return ""

    mode = agent_log.get("mode", "pipeline")
    parts = [
        '<section id="agent-process">',
        '<h2>Agent Analysis Process</h2>',
        '<p>This report was generated by an autonomous AI agent that analyzed ',
        'Phase 1 experimental data and decided which ML analyses to perform.</p>',
    ]

    # Mode badge
    if mode == "react":
        parts.append(
            '<div class="agent-badge react">ReAct Agent &mdash; '
            'LLM-driven autonomous reasoning with iterative Thought &rarr; Action &rarr; Observation loop</div>'
        )
    else:
        parts.append(
            '<div class="agent-badge pipeline">Automated Pipeline &mdash; '
            'Rule-based sequential execution of analysis steps</div>'
        )

    # Tools called
    tools = agent_log.get("tools_called", [])
    if tools:
        parts.append("<h4>Analysis Steps Executed</h4>")
        parts.append('<div class="step-flow">')
        step_labels = {
            "explore_data": ("1", "Data Exploration", "Scan Phase 1 results, identify materials and data range"),
            "prepare_data": ("2", "Data Preparation", "Extract segment data from JSONs, build integrated CSV"),
            "train_models": ("3", "Model Training", "Train S60 baseline (Ridge) + S8 confinement (GBR) models"),
            "confinement_analysis": ("4", "Confinement Analysis", "Quantify \u0394Ea by temperature zone with statistical tests"),
            "meyer_neldel": ("5", "Meyer-Neldel", "Compensation effect analysis: ln(\u03c3\u2080) vs Ea"),
            "cross_material": ("6", "Cross-Material", "Transfer validation across different clay-acid systems"),
        }
        for tool in tools:
            num, label, desc = step_labels.get(tool, ("?", tool, ""))
            parts.append(
                f'<div class="step-card">'
                f'<div class="step-num">{num}</div>'
                f'<div class="step-info"><div class="step-label">{label}</div>'
                f'<div class="step-desc">{desc}</div></div>'
                f'</div>'
            )
        parts.append('</div>')

    # ReAct thought log
    thought_log = agent_log.get("thought_log", [])
    if thought_log:
        parts.append("<h4>Agent Reasoning Trace</h4>")
        parts.append('<div class="thought-log">')
        for entry in thought_log:
            iteration = entry.get("iteration", "?")
            action = entry.get("action", "?")
            thought = entry.get("thought", "")
            # Truncate very long thoughts
            if len(thought) > 500:
                thought = thought[:500] + "..."

            action_class = "finish" if action == "FINISH" else "tool"
            parts.append(
                f'<div class="thought-entry">'
                f'<div class="thought-header">'
                f'<span class="iter-badge">Iteration {iteration}</span>'
                f'<span class="action-badge {action_class}">{action}</span>'
                f'</div>'
                f'<div class="thought-text">{_escape_html(thought)}</div>'
                f'</div>'
            )
        parts.append('</div>')

    # Timing
    elapsed = agent_log.get("elapsed_seconds")
    iterations = agent_log.get("iterations")
    if elapsed or iterations:
        parts.append('<div class="agent-stats">')
        if iterations:
            parts.append(f'<span>Reasoning iterations: {iterations}</span>')
        parts.append(f'<span>Tools called: {len(tools)}</span>')
        if elapsed:
            parts.append(f'<span>Total time: {elapsed}s</span>')
        parts.append('</div>')

    parts.append('</section>')
    return "\n".join(parts)


def _build_ml_summary_table(ml_data: Dict) -> str:
    parts: List[str] = []

    metrics = ml_data.get("metrics", {})
    if metrics:
        s60 = metrics.get("s60", {})
        s8 = metrics.get("s8", {})
        delta = metrics.get("delta_Ea", {})
        parts.append("""
<h3>Model Performance</h3>
<table class="data-table">
<thead><tr><th>Model</th><th>R&sup2;</th><th>CV R&sup2;</th><th>MAE (eV)</th><th>n</th></tr></thead>
<tbody>""")
        if s60:
            parts.append(f"""<tr><td>S60 Baseline (Ridge)</td><td>{s60.get('r2',0):.4f}</td>
<td>{s60.get('cv_r2_mean',0):.4f} &plusmn; {s60.get('cv_r2_std',0):.4f}</td>
<td>{s60.get('mae_eV',0):.4f}</td><td>{s60.get('n_samples',0)}</td></tr>""")
        if s8:
            parts.append(f"""<tr><td>S8 Confinement (GBR)</td><td>{s8.get('r2',0):.4f}</td>
<td>{s8.get('cv_r2_mean',0):.4f} &plusmn; {s8.get('cv_r2_std',0):.4f}</td>
<td>{s8.get('mae_eV',0):.4f}</td><td>{s8.get('n_samples',0)}</td></tr>""")
        parts.append("</tbody></table>")

        if delta:
            parts.append(f"""
<p><strong>&Delta;Ea (S8 actual &minus; S60 predicted)</strong>: mean = {delta.get('mean',0):.4f} eV,
std = {delta.get('std',0):.4f} eV, range = [{delta.get('min',0):.4f}, {delta.get('max',0):.4f}] eV</p>""")

    conf = ml_data.get("confinement", {})
    if conf:
        parts.append("<h3>Confinement Effect by Temperature Zone</h3>")
        parts.append("""<table class="data-table">
<thead><tr><th>Temperature Zone</th><th>Mean &Delta;Ea (eV)</th><th>Std</th><th>95% CI</th><th>n</th></tr></thead>
<tbody>""")
        for key, label in [("overall", "Overall"), ("low_T_under_230K", "Low T (&lt;230K)"),
                           ("mid_T_230_270K", "Mid T (230&ndash;270K)"), ("high_T_over_270K", "High T (&gt;270K)")]:
            d = conf.get(key, {})
            if d and d.get("mean") is not None:
                ci_lo = d.get("ci_95_low")
                ci_hi = d.get("ci_95_high")
                ci_str = f"[{ci_lo:.4f}, {ci_hi:.4f}]" if ci_lo is not None else "&mdash;"
                parts.append(f"<tr><td>{label}</td><td>{d['mean']:.4f}</td>"
                             f"<td>{d.get('std',0):.4f}</td><td>{ci_str}</td><td>{d.get('n',0)}</td></tr>")
        parts.append("</tbody></table>")

        ttest = conf.get("low_vs_high_T_ttest", {})
        if ttest:
            sig = "significant" if ttest.get("significant_005") else "not significant"
            parts.append(f"<p><strong>Low vs High T t-test</strong>: t = {ttest.get('t_statistic',0):.3f}, "
                         f"p = {ttest.get('p_value',0):.2e} ({sig})</p>")

        linear = conf.get("delta_Ea_vs_T_linear_fit", {})
        if linear:
            parts.append(f"<p><strong>Linear trend</strong>: slope = {linear.get('slope_per_K',0):.6f} eV/K, "
                         f"R&sup2; = {linear.get('r_squared',0):.4f}</p>")

    mn = ml_data.get("meyer_neldel", {})
    if mn:
        parts.append("<h3>Meyer-Neldel Compensation Effect</h3>")
        parts.append("""<table class="data-table">
<thead><tr><th>System</th><th>E<sub>MN</sub> (eV)</th><th>R&sup2;</th><th>p-value</th><th>n</th></tr></thead>
<tbody>""")
        label_map = {"S8": "S8 Overall", "S60": "S60 Baseline",
                     "S8_high_T": "S8 High T (&ge;270K)", "S8_low_T": "S8 Low T (&lt;230K)"}
        for key in ["S8", "S60", "S8_high_T", "S8_low_T"]:
            d = mn.get(key, {})
            if d and d.get("E_MN_eV") is not None:
                parts.append(f"<tr><td>{label_map.get(key, key)}</td><td>{d['E_MN_eV']:.4f}</td>"
                             f"<td>{d.get('r_squared',0):.4f}</td><td>{d.get('p_value',0):.2e}</td>"
                             f"<td>{d.get('n_points',0)}</td></tr>")
        parts.append("</tbody></table>")

    cross = ml_data.get("cross_material", {})
    mats = cross.get("materials", {}) if cross else {}
    if mats:
        parts.append("<h3>Cross-Material Transfer Validation</h3>")
        parts.append("""<table class="data-table">
<thead><tr><th>Material</th><th>Composition</th><th>n</th><th>&alpha; (mean &plusmn; std)</th><th>MAE (eV)</th></tr></thead>
<tbody>""")
        for mat in sorted(mats.keys()):
            d = mats[mat]
            comp = _MAT_IDENTITY.get(mat, ("Unknown", ""))[0]
            parts.append(f"<tr><td>{mat}</td><td>{comp}</td><td>{d.get('n',0)}</td>"
                         f"<td>{d.get('mean_alpha',0):.3f} &plusmn; {d.get('std_alpha',0):.3f}</td>"
                         f"<td>{d.get('mae_eV',0):.4f}</td></tr>")
        parts.append("</tbody></table>")
        ov = cross.get("overall", {})
        if ov.get("mean_alpha_weighted"):
            parts.append(f"<p>Overall weighted &alpha; = {ov['mean_alpha_weighted']:.3f}</p>")

    return "\n".join(parts)


# ================================================================
# CSS
# ================================================================

def _get_css() -> str:
    return """
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.7;
    color: #2c3e50;
    background: #f5f5f5;
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
}

.report-header {
    background: linear-gradient(135deg, #1a5276, #2980b9);
    color: white;
    padding: 40px 30px;
    border-radius: 8px;
    margin-bottom: 30px;
}
.report-header h1 { font-size: 1.8em; margin-bottom: 8px; }
.report-header .subtitle { font-size: 1.1em; opacity: 0.9; margin-bottom: 12px; }
.report-header .meta { font-size: 0.85em; opacity: 0.8; }
.report-header .meta span { margin-right: 20px; }

.toc {
    background: white;
    padding: 20px 30px;
    border-radius: 8px;
    margin-bottom: 30px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}
.toc h3 { margin-bottom: 10px; color: #1a5276; }
.toc ol { padding-left: 20px; }
.toc li { margin: 4px 0; }
.toc a { color: #2980b9; text-decoration: none; }
.toc a:hover { text-decoration: underline; }

.report-body {
    background: white;
    padding: 30px 35px;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

section { margin-bottom: 35px; }
h2 {
    color: #1a5276;
    font-size: 1.4em;
    border-bottom: 2px solid #2980b9;
    padding-bottom: 6px;
    margin: 30px 0 15px 0;
}
h4 {
    color: #2c3e50;
    font-size: 1.1em;
    margin: 18px 0 8px 0;
}
p { margin: 8px 0; }
ul { padding-left: 24px; margin: 8px 0; }
li { margin: 4px 0; }
li.nested { margin-left: 20px; color: #555; }

.data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
    font-size: 0.92em;
}
.data-table th {
    background: #2980b9;
    color: white;
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
}
.data-table td {
    padding: 7px 12px;
    border-bottom: 1px solid #e0e0e0;
}
.data-table tr:nth-child(even) td { background: #f8f9fa; }
.data-table tr:hover td { background: #eaf2f8; }

.report-figure {
    margin: 25px 0;
    text-align: center;
    page-break-inside: avoid;
}
.report-figure img {
    max-width: 100%;
    border: 1px solid #ddd;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.report-figure figcaption {
    font-size: 0.88em;
    color: #555;
    margin-top: 8px;
    line-height: 1.5;
    text-align: left;
    padding: 0 20px;
    font-style: italic;
}

/* ---- Formula rendering (pure CSS, no JS) ---- */
.formula {
    background: #f8f9fa;
    padding: 14px 24px;
    margin: 16px 0;
    border-left: 3px solid #2980b9;
    text-align: center;
    font-family: 'Cambria Math', 'STIX Two Math', 'Latin Modern Math', 'Times New Roman', serif;
    font-size: 1.15em;
    letter-spacing: 0.02em;
    overflow-x: auto;
}
.math-inline {
    font-family: 'Cambria Math', 'STIX Two Math', 'Latin Modern Math', 'Times New Roman', serif;
    font-style: italic;
    letter-spacing: 0.01em;
}
.math-fn {
    font-style: normal;
    font-weight: normal;
    margin-right: 1px;
}

/* CSS fraction layout */
.frac {
    display: inline-flex;
    flex-direction: column;
    text-align: center;
    vertical-align: middle;
    margin: 0 3px;
    font-size: 0.92em;
}
.frac-num {
    border-bottom: 1.2px solid currentColor;
    padding: 0 4px 2px;
    line-height: 1.3;
}
.frac-den {
    padding: 2px 4px 0;
    line-height: 1.3;
}

/* Boxed formula */
.math-boxed {
    display: inline-block;
    border: 2px solid #2980b9;
    border-radius: 6px;
    padding: 8px 16px;
    margin: 8px 0;
    background: #eaf2f8;
    font-weight: bold;
}

.numbered-item {
    padding-left: 20px;
    text-indent: -8px;
}

strong { color: #1a5276; }

hr {
    border: none;
    border-top: 1px solid #e0e0e0;
    margin: 25px 0;
}

.report-footer {
    text-align: center;
    font-size: 0.85em;
    color: #888;
    padding: 20px;
    margin-top: 30px;
}

/* ---- Agent process section ---- */
.agent-badge {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.9em;
    font-weight: 600;
    margin: 10px 0 16px;
}
.agent-badge.react {
    background: linear-gradient(135deg, #e74c3c, #c0392b);
    color: white;
}
.agent-badge.pipeline {
    background: linear-gradient(135deg, #2980b9, #1a5276);
    color: white;
}

.step-flow {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 12px 0 20px;
}
.step-card {
    display: flex;
    align-items: center;
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 8px 14px;
    min-width: 200px;
    flex: 1 1 200px;
    transition: box-shadow 0.2s;
}
.step-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.step-num {
    width: 32px; height: 32px;
    background: #2980b9; color: white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.9em;
    margin-right: 10px; flex-shrink: 0;
}
.step-label { font-weight: 600; font-size: 0.92em; color: #1a5276; }
.step-desc { font-size: 0.8em; color: #666; margin-top: 2px; }

.thought-log { margin: 12px 0 20px; }
.thought-entry {
    border-left: 3px solid #e74c3c;
    padding: 10px 16px;
    margin: 8px 0;
    background: #fdf2f2;
    border-radius: 0 6px 6px 0;
}
.thought-header { margin-bottom: 6px; }
.iter-badge {
    background: #555; color: white;
    padding: 2px 8px; border-radius: 10px;
    font-size: 0.78em; font-weight: 600;
    margin-right: 8px;
}
.action-badge {
    padding: 2px 8px; border-radius: 10px;
    font-size: 0.78em; font-weight: 600;
}
.action-badge.tool { background: #2980b9; color: white; }
.action-badge.finish { background: #27ae60; color: white; }
.thought-text {
    font-size: 0.88em; color: #444;
    line-height: 1.5;
    white-space: pre-wrap;
}

.agent-stats {
    display: flex; gap: 20px;
    padding: 8px 0; margin-top: 8px;
    font-size: 0.85em; color: #666;
    border-top: 1px solid #eee;
}
.agent-stats span { font-weight: 500; }

@media print {
    body { max-width: 100%; padding: 0; background: white; }
    .report-header { page-break-after: always; }
    .report-figure { page-break-inside: avoid; }
    section { page-break-inside: avoid; }
}
"""
