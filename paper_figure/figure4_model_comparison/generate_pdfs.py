# -*- coding: utf-8 -*-
"""
Convert all model comparison HTML reports + agent reports to PDF.
Uses Edge headless --print-to-pdf (built-in on Windows 10/11).
"""
import os, subprocess, time
from pathlib import Path

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

SCRIPT_DIR = Path(__file__).resolve().parent
CLOSE_DIR = SCRIPT_DIR.parent.parent
MODEL_REPORTS_DIR = SCRIPT_DIR / "model_reports"
DEEP_DIR = CLOSE_DIR / "output" / "deep_analysis"

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# All HTML files to convert
JOBS = [
    (MODEL_REPORTS_DIR / "report_deepseek-r1.html",      "report_deepseek-r1.pdf",      "DeepSeek-R1"),
    (MODEL_REPORTS_DIR / "report_gemini-2.5-pro.html",    "report_gemini-2.5-pro.pdf",   "Gemini 2.5 Pro"),
    (MODEL_REPORTS_DIR / "report_gpt-5.2-pro.html",       "report_gpt-5.2-pro.pdf",      "GPT-5.2 Pro"),
    (MODEL_REPORTS_DIR / "report_qwen.html",              "report_qwen.pdf",             "Qwen (translated)"),
    (DEEP_DIR / "S8_full_report.html",                    "report_agent-pipeline.pdf",   "Agent-Enhanced (Pipeline)"),
    (DEEP_DIR / "S8_react_full_report.html",              "report_agent-react.pdf",      "Agent-Enhanced (ReAct)"),
]


def html_to_pdf_edge(html_path: Path, pdf_path: Path) -> bool:
    """Use Edge headless to convert HTML to PDF."""
    url = html_path.as_uri()
    cmd = [
        EDGE,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--print-to-pdf={pdf_path}",
        "--print-to-pdf-no-header",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=5000",
        url,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='replace',
        )
        return pdf_path.exists() and pdf_path.stat().st_size > 0
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        print(f"    Error: {e}")
        return False


def main():
    if not Path(EDGE).exists():
        print(f"ERROR: Edge not found at {EDGE}")
        return

    print(f"Using: {EDGE}")
    print(f"Output: {MODEL_REPORTS_DIR}\n")

    success = 0
    for src_html, pdf_name, desc in JOBS:
        if not src_html.exists():
            print(f"  SKIP  {desc}: {src_html.name} not found")
            continue

        out_pdf = MODEL_REPORTS_DIR / pdf_name
        print(f"  {desc}...", end="", flush=True)

        ok = html_to_pdf_edge(src_html, out_pdf)
        if ok:
            size_kb = out_pdf.stat().st_size / 1024
            print(f" OK ({size_kb:.0f} KB)")
            success += 1
        else:
            print(" FAILED")

        time.sleep(1)  # Brief pause between conversions

    print(f"\nDone! {success}/{len(JOBS)} PDFs generated.")
    print(f"Location: {MODEL_REPORTS_DIR}")


if __name__ == '__main__':
    main()
