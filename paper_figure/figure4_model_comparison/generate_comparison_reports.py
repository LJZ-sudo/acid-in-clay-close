# -*- coding: utf-8 -*-
"""
Generate uniformly formatted HTML reports for each model's response.
V2 — complete rewrite with robust per-model parsing.

Models:
1. DeepSeek-R1  (deepseek.txt — clean Markdown)
2. Gemini-2.5-Pro  (gemini.txt — numbered sections, no # headings)
3. GPT-5.2-Pro  (GPT-pro.txt — clean Markdown with ## headings)
4. Qwen  (qianwen.pdf — Chinese, use original PDF directly)
"""

import os, re
from pathlib import Path

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

SCRIPT_DIR = Path(__file__).resolve().parent
CLOSE_DIR = SCRIPT_DIR.parent.parent
DEEP_DIR = CLOSE_DIR / "output" / "deep_analysis"

# ── CSS ──
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
:root {
  --primary: #1a73e8; --bg: #fafbfc; --card: #ffffff;
  --text: #1f2937; --text2: #6b7280; --border: #e5e7eb;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg); color: var(--text);
  line-height: 1.75; font-size: 15px;
  max-width: 900px; margin: 0 auto; padding: 40px 30px;
}
.report-header {
  background: linear-gradient(135deg, #1a237e 0%, #0d47a1 50%, #01579b 100%);
  color: white; padding: 40px; border-radius: 16px;
  margin-bottom: 30px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.report-header h1 { font-size: 22px; font-weight: 700; margin-bottom: 8px; line-height: 1.3; }
.report-header .subtitle { font-size: 14px; opacity: 0.85; margin-bottom: 16px; }
.meta-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px; margin-top: 16px;
}
.meta-item {
  background: rgba(255,255,255,0.12); padding: 8px 14px; border-radius: 8px; font-size: 13px;
}
.meta-item .label { opacity: 0.7; font-size: 11px; text-transform: uppercase; }
.meta-item .value { font-weight: 600; }
.section {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 28px 32px; margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
h2 {
  font-size: 18px; color: var(--primary); border-bottom: 2px solid var(--primary);
  padding-bottom: 8px; margin-bottom: 16px; font-weight: 700;
}
h3 { font-size: 15px; color: #374151; margin: 18px 0 10px 0; font-weight: 600; }
h4 { font-size: 14px; color: #4b5563; margin: 14px 0 8px 0; font-weight: 600; }
p { margin-bottom: 12px; text-align: justify; }
ul, ol { margin: 8px 0 12px 24px; }
li { margin-bottom: 6px; }
strong { color: #111827; }
.footer {
  text-align: center; color: var(--text2); font-size: 12px;
  padding: 20px; border-top: 1px solid var(--border); margin-top: 30px;
}
@media print {
  body { max-width: 100%; padding: 20px; }
  .section { break-inside: avoid; }
  .report-header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>"""


CN_TO_EN = {
    '材料物理中心': 'Materials Physics Center',
    '皇家化学学会出版部': 'RSC Publishing',
}


def inline_fmt(text: str) -> str:
    """Bold, italic, inline code, links; also translate Chinese citation names."""
    # Replace known Chinese citation names
    for cn, en in CN_TO_EN.items():
        text = text.replace(cn, en)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\[\d+\]', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def parse_deepseek(raw: str) -> list:
    """DeepSeek-R1: Markdown with ### **N. Title** headings."""
    sections = []
    current_title = "Abstract"
    current_body = []

    for line in raw.split('\n'):
        s = line.strip()
        if not s or s in ('---', '___'):
            continue

        # Section heading: ### **N. Title**  or  ### N. Title
        m = re.match(r'^###?\s*\*{0,2}\s*(\d+\.\s+.+?)\s*\*{0,2}\s*$', s)
        if m:
            if current_body:
                sections.append((current_title, '\n'.join(current_body)))
            current_title = re.sub(r'\*', '', m.group(1)).strip()
            current_body = []
            continue

        # Sub-heading: #### **N.N Title**
        m4 = re.match(r'^####\s*\*{0,2}\s*(.+?)\s*\*{0,2}\s*$', s)
        if m4:
            current_body.append(f'<h4>{inline_fmt(m4.group(1))}</h4>')
            continue

        # Bullet items
        if s.startswith('* ') or s.startswith('- '):
            current_body.append(f'<li>{inline_fmt(s[2:])}</li>')
            continue

        # Numbered sub-items (indented or within section)
        nm = re.match(r'^\d+\.\s+\*{0,2}(.+?)\*{0,2}$', s)
        if nm and not s.startswith('**Comprehensive') and not s.startswith('**Abstract'):
            current_body.append(f'<li>{inline_fmt(nm.group(1))}</li>')
            continue

        # Regular paragraph
        current_body.append(f'<p>{inline_fmt(s)}</p>')

    if current_body:
        sections.append((current_title, '\n'.join(current_body)))
    return sections


def parse_gemini(raw: str) -> list:
    """Gemini: numbered top-level sections, ________________ dividers, subsections N.M."""
    sections = []
    current_title = "Overview"
    current_body = []
    prev_was_divider = True  # first section has no divider before it

    lines = raw.split('\n')
    for i, line in enumerate(lines):
        orig = line
        s = line.strip()
        if not s:
            continue
        if s.startswith('________________'):
            prev_was_divider = True
            continue
        if s == '---':
            continue

        # Remove BOM
        if s.startswith('\ufeff'):
            s = s[1:]

        # Top-level section: "N. Title" — preceded by divider or is near start
        m = re.match(r'^(\d)\.\s+([A-Z].{10,})$', s)
        if m and (prev_was_divider or i < 3):
            if current_body:
                sections.append((current_title, '\n'.join(current_body)))
            current_title = f"{m.group(1)}. {m.group(2)}"
            current_body = []
            prev_was_divider = False
            continue

        prev_was_divider = False

        # Subsection: "N.M Title"
        m2 = re.match(r'^(\d+\.\d+)\s+(.+)$', s)
        if m2:
            current_body.append(f'<h3>{m2.group(1)} {m2.group(2)}</h3>')
            continue

        # "Works cited" — start references section
        if s.lower().startswith('works cited'):
            if current_body:
                sections.append((current_title, '\n'.join(current_body)))
            current_title = "References"
            current_body = []
            continue

        # Bullet list items (with possible leading spaces)
        sm = s.lstrip()
        if sm.startswith('* '):
            current_body.append(f'<li>{inline_fmt(sm[2:])}</li>')
            continue

        # Indented numbered items (sub-items within a section)
        if orig.startswith('   ') or orig.startswith('\t'):
            nm = re.match(r'^(\d+)\.\s+(.+)$', sm)
            if nm:
                current_body.append(f'<li>{inline_fmt(nm.group(2))}</li>')
                continue

        # Reference entries (start with number. and contain URL)
        ref_m = re.match(r'^(\d+)\.\s+(.+https?://.+)$', s)
        if ref_m:
            current_body.append(f'<li><small>{inline_fmt(ref_m.group(2))}</small></li>')
            continue

        # Regular paragraph
        current_body.append(f'<p>{inline_fmt(s)}</p>')

    if current_body:
        sections.append((current_title, '\n'.join(current_body)))
    return sections


def parse_gpt_pro(raw: str) -> list:
    """GPT-5.2-Pro: clean Markdown with ## headings and [N] references."""
    sections = []
    current_title = "Overview"
    current_body = []

    # Remove reference links at bottom
    lines = raw.split('\n')
    clean_lines = []
    for line in lines:
        if re.match(r'^\[\d+\]:\s*https?://', line.strip()):
            continue
        clean_lines.append(line)

    for line in clean_lines:
        s = line.strip()
        if not s or s == '---':
            continue
        # H2: ## Title
        m = re.match(r'^##\s+(.+)$', s)
        if m:
            if current_body:
                sections.append((current_title, '\n'.join(current_body)))
            current_title = re.sub(r'\*', '', m.group(1)).strip()
            current_body = []
            continue
        # H3: ### Title
        m3 = re.match(r'^###\s+(.+)$', s)
        if m3:
            current_body.append(f'<h3>{inline_fmt(m3.group(1))}</h3>')
            continue
        # H4: #### Title
        m4 = re.match(r'^####\s+(.+)$', s)
        if m4:
            current_body.append(f'<h4>{inline_fmt(m4.group(1))}</h4>')
            continue
        # H1: # Title
        m1 = re.match(r'^#\s+(.+)$', s)
        if m1:
            if current_body:
                sections.append((current_title, '\n'.join(current_body)))
            current_title = re.sub(r'\*', '', m1.group(1)).strip()
            current_body = []
            continue
        # List items
        if s.startswith('* '):
            current_body.append(f'<li>{inline_fmt(s[2:])}</li>')
            continue
        if s.startswith('- '):
            current_body.append(f'<li>{inline_fmt(s[2:])}</li>')
            continue
        # Numbered items
        nm = re.match(r'^(\d+)\.\s+(.+)$', s)
        if nm:
            current_body.append(f'<li>{inline_fmt(nm.group(2))}</li>')
            continue
        # Regular text
        if s.startswith('[') and s.endswith(']'):
            continue  # skip math blocks like [formula]
        current_body.append(f'<p>{inline_fmt(s)}</p>')

    if current_body:
        sections.append((current_title, '\n'.join(current_body)))
    return sections


def sections_to_html(sections: list) -> str:
    """Convert list of (title, body_html) to section divs."""
    parts = []
    for title, body in sections:
        # Wrap loose <li> tags in <ul>
        body = re.sub(r'(?<!<ul>)\n?(<li>(?:.|\n)*?</li>)\n?(?!</ul>)',
                      lambda m: '<ul>' + m.group(1) + '</ul>', body)
        # Clean up consecutive </ul><ul>
        body = body.replace('</ul><ul>', '')
        # Clean up empty paragraphs
        body = body.replace('<p></p>', '')
        parts.append(f'<div class="section">\n<h2>{inline_fmt(title)}</h2>\n{body}\n</div>')
    return '\n\n'.join(parts)


def build_html(model_name: str, model_tag: str, body_html: str, word_count: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Deep Mechanism Analysis - {model_name}</title>
{CSS}
</head>
<body>
<div class="report-header">
  <h1>Deep Mechanism Analysis Report:<br>S8 (Sepiolite + H&#8323;PO&#8324;) Proton Conductor</h1>
  <div class="subtitle">Comprehensive mechanistic analysis of proton conduction in phosphoric acid-activated sepiolite</div>
  <div class="meta-grid">
    <div class="meta-item"><div class="label">Model</div><div class="value">{model_name}</div></div>
    <div class="meta-item"><div class="label">Model Tag</div><div class="value">{model_tag}</div></div>
    <div class="meta-item"><div class="label">Material</div><div class="value">S8 (Sepiolite + H&#8323;PO&#8324;)</div></div>
    <div class="meta-item"><div class="label">Prompt</div><div class="value">No Knowledge Base (Scheme A)</div></div>
    <div class="meta-item"><div class="label">Word Count</div><div class="value">~{word_count}</div></div>
    <div class="meta-item"><div class="label">Evaluation ID</div><div class="value">EVAL-2026-02</div></div>
  </div>
</div>

{body_html}

<div class="footer">
  <p>Generated for model comparison evaluation &middot; S8 Deep Mechanism Analysis &middot; February 2026</p>
  <p>All models received the same input prompt (S8_deep_analysis_prompt_no_kb.txt)</p>
</div>
</body>
</html>"""


def count_words(text: str) -> int:
    en = len(re.findall(r'[a-zA-Z]+', text))
    cjk = len(re.findall(r'[\u4e00-\u9fff]', text))
    return en + cjk


def main():
    out_dir = SCRIPT_DIR / "model_reports"
    out_dir.mkdir(exist_ok=True)

    # ── DeepSeek-R1 ──
    ds_txt = (DEEP_DIR / 'deepseek.txt').read_text(encoding='utf-8')
    ds_sections = parse_deepseek(ds_txt)
    ds_html = sections_to_html(ds_sections)
    ds_wc = count_words(ds_txt)
    (out_dir / 'report_deepseek-r1.html').write_text(
        build_html('DeepSeek-R1', 'deepseek-r1', ds_html, ds_wc), encoding='utf-8')
    print(f"DeepSeek-R1: {len(ds_sections)} sections, {ds_wc} words")

    # ── Gemini 2.5 Pro ──
    gem_txt = (DEEP_DIR / 'gemini.txt').read_text(encoding='utf-8')
    gem_sections = parse_gemini(gem_txt)
    gem_html = sections_to_html(gem_sections)
    gem_wc = count_words(gem_txt)
    (out_dir / 'report_gemini-2.5-pro.html').write_text(
        build_html('Gemini 2.5 Pro', 'gemini-2.5-pro', gem_html, gem_wc), encoding='utf-8')
    print(f"Gemini-2.5-Pro: {len(gem_sections)} sections, {gem_wc} words")

    # ── GPT-5.2 Pro ──
    gpt_txt = (DEEP_DIR / 'GPT-pro.txt').read_text(encoding='utf-8')
    gpt_sections = parse_gpt_pro(gpt_txt)
    gpt_html = sections_to_html(gpt_sections)
    gpt_wc = count_words(gpt_txt)
    (out_dir / 'report_gpt-5.2-pro.html').write_text(
        build_html('GPT-5.2 Pro', 'gpt-5.2-pro', gpt_html, gpt_wc), encoding='utf-8')
    print(f"GPT-5.2-Pro: {len(gpt_sections)} sections, {gpt_wc} words")

    # ── Qwen ──
    # Qwen's report was manually translated to English in report_qwen.html.
    # Do NOT overwrite it here.
    qwen_path = out_dir / 'report_qwen.html'
    if qwen_path.exists():
        print(f"Qwen: English version already exists, skipping")
    else:
        print(f"Qwen: report_qwen.html not found — please create manually")

    print(f"\nAll reports saved to: {out_dir}")
    print("Open .html in browser → Ctrl+P → Save as PDF")
    print("For Qwen, use the original qianwen.pdf directly.")


if __name__ == '__main__':
    main()
