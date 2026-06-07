"""Paper Reader — 从 PDF/TXT/MD/JSON 文件提取结构化文本。

使用 PyMuPDF (fitz) 做 PDF 解析，是当前学术论文解析 F1 最高的规则引擎。
参考: "A Comparative Study of PDF Parsing Tools Across Diverse Document Categories" (2024)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".json"}


@dataclass
class ParsedPaper:
    """从单篇文献文件中解析出的结构化内容。"""
    source_path: str
    title: str = ""
    authors: str = ""
    year: int = 0
    abstract: str = ""
    sections: list[dict] = field(default_factory=list)  # [{"heading": str, "text": str}]
    full_text: str = ""
    tables: list[str] = field(default_factory=list)
    n_pages: int = 0
    parse_warnings: list[str] = field(default_factory=list)

    def summary_text(self, max_chars: int = 5000) -> str:
        """返回用于 LLM 输入的精简文本。"""
        parts = []
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.authors:
            parts.append(f"Authors: {self.authors}")
        if self.year:
            parts.append(f"Year: {self.year}")
        if self.abstract:
            parts.append(f"Abstract: {self.abstract[:1500]}")

        remaining = max_chars - sum(len(p) for p in parts)
        if remaining > 200 and self.sections:
            for sec in self.sections:
                heading = sec.get("heading", "")
                text = sec.get("text", "")
                chunk = f"\n## {heading}\n{text}" if heading else f"\n{text}"
                if len(chunk) > remaining:
                    parts.append(chunk[:remaining] + "...[truncated]")
                    break
                parts.append(chunk)
                remaining -= len(chunk)

        return "\n".join(parts)


def read_paper(path: Path) -> ParsedPaper:
    """统一入口：根据扩展名分发到对应解析器。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Paper file not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {SUPPORTED_EXTENSIONS}")

    if ext == ".pdf":
        return _read_pdf(path)
    elif ext == ".json":
        return _read_json(path)
    else:
        return _read_text(path)


def _read_pdf(path: Path) -> ParsedPaper:
    """使用 PyMuPDF 解析 PDF。"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is required for PDF reading. Install with: pip install PyMuPDF"
        )

    doc = fitz.open(str(path))
    n_pages = len(doc)
    all_blocks: list[dict] = []
    tables_text: list[str] = []

    for page_num in range(n_pages):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for block in blocks:
            if block.get("type") == 0:  # text block
                lines_text = []
                max_font_size = 0.0
                is_bold = False
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        lines_text.append(span.get("text", ""))
                        fs = span.get("size", 0)
                        if fs > max_font_size:
                            max_font_size = fs
                        if "bold" in span.get("font", "").lower():
                            is_bold = True
                text = " ".join(lines_text).strip()
                if text:
                    all_blocks.append({
                        "text": text,
                        "font_size": max_font_size,
                        "bold": is_bold,
                        "page": page_num,
                    })

        try:
            page_tables = page.find_tables()
            for table in page_tables:
                extracted = table.extract()
                if extracted:
                    rows = [" | ".join(str(c) if c else "" for c in row) for row in extracted]
                    tables_text.append("\n".join(rows))
        except Exception:
            pass

    doc.close()

    title, authors, year, abstract, sections = _structure_blocks(all_blocks)

    if not year:
        year = _extract_year(str(path.name))

    full_text = "\n\n".join(b["text"] for b in all_blocks)

    if not abstract and full_text:
        abs_match = re.search(
            r"(?:^|\n)\s*[Aa]bstract[:\s\-—]*\n?(.*?)(?=\n\s*(?:\d+\.?\s*)?[Ii]ntroduction|\n\s*[Kk]eywords|\Z)",
            full_text, re.DOTALL,
        )
        if abs_match:
            abstract = abs_match.group(1).strip()[:2000]

    warnings = []
    if n_pages == 0:
        warnings.append("PDF has 0 pages")
    if not title:
        warnings.append("Could not detect title from font sizes")

    return ParsedPaper(
        source_path=str(path),
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        sections=sections,
        full_text=full_text[:50000],
        tables=tables_text[:20],
        n_pages=n_pages,
        parse_warnings=warnings,
    )


def _structure_blocks(blocks: list[dict]) -> tuple[str, str, int, str, list[dict]]:
    """从文本块中推断 title、authors、abstract、sections。"""
    if not blocks:
        return "", "", 0, "", []

    font_sizes = [b["font_size"] for b in blocks if b["font_size"] > 0]
    if not font_sizes:
        return "", "", 0, "", [{"heading": "", "text": b["text"]} for b in blocks]

    max_fs = max(font_sizes)
    median_fs = sorted(font_sizes)[len(font_sizes) // 2]

    title = ""
    authors = ""
    year = 0
    abstract = ""
    sections: list[dict] = []
    current_heading = ""
    current_text_parts: list[str] = []

    abstract_started = False
    body_started = False

    for i, block in enumerate(blocks):
        text = block["text"]
        fs = block["font_size"]

        if not title and fs >= max_fs * 0.9 and len(text) > 5:
            title = text
            continue

        if title and not body_started and not abstract_started:
            if _looks_like_author_line(text):
                authors = text
                continue
            yr = _extract_year(text)
            if yr and not year:
                year = yr

        abstract_kw = re.match(r"^abstract[:\s]*(.*)", text, re.IGNORECASE)
        if abstract_kw and not abstract:
            rest = abstract_kw.group(1).strip()
            if rest:
                abstract = rest
            abstract_started = True
            continue

        if abstract_started and not abstract:
            abstract = text
            abstract_started = False
            continue

        is_heading = (
            (fs > median_fs * 1.15 and block["bold"])
            or (fs > median_fs * 1.3)
            or _is_section_heading(text)
        )

        if is_heading and len(text) < 200:
            if current_heading or current_text_parts:
                sections.append({
                    "heading": current_heading,
                    "text": " ".join(current_text_parts),
                })
            current_heading = text
            current_text_parts = []
            body_started = True
        else:
            current_text_parts.append(text)

    if current_heading or current_text_parts:
        sections.append({
            "heading": current_heading,
            "text": " ".join(current_text_parts),
        })

    return title, authors, year, abstract, sections


def _looks_like_author_line(text: str) -> bool:
    if len(text) > 500 or len(text) < 5:
        return False
    indicators = [",", "and ", "@", "university", "institute", "department",
                  "school", "college", "laboratory", "center", "centre",
                  "*", "†", "‡"]
    lower = text.lower()
    hits = sum(1 for ind in indicators if ind in lower)
    if hits >= 2:
        return True
    if "," in text and re.search(r"[A-Z]\.", text) and len(text) < 300:
        return True
    return False


def _extract_year(text: str) -> int:
    m = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
    if m:
        return int(m.group(1))
    return 0


_SECTION_PATTERNS = re.compile(
    r"^(\d+\.?\s+)?(introduction|background|methods?|methodology|results?"
    r"|discussion|conclusion|references|acknowledgment|experimental|materials and methods"
    r"|supplementary|supporting information)",
    re.IGNORECASE,
)


def _is_section_heading(text: str) -> bool:
    text = text.strip()
    if len(text) > 150:
        return False
    return bool(_SECTION_PATTERNS.match(text))


def _read_text(path: Path) -> ParsedPaper:
    """读取 TXT/MD 文件。"""
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")

    title = ""
    for line in lines[:5]:
        stripped = line.strip().lstrip("#").strip()
        if stripped and len(stripped) > 5:
            title = stripped
            break

    sections: list[dict] = []
    current_heading = ""
    current_parts: list[str] = []

    for line in lines:
        if line.startswith("#"):
            if current_heading or current_parts:
                sections.append({"heading": current_heading, "text": "\n".join(current_parts)})
            current_heading = line.lstrip("#").strip()
            current_parts = []
        else:
            current_parts.append(line)

    if current_heading or current_parts:
        sections.append({"heading": current_heading, "text": "\n".join(current_parts)})

    return ParsedPaper(
        source_path=str(path),
        title=title,
        sections=sections,
        full_text=content[:50000],
    )


def _read_json(path: Path) -> ParsedPaper:
    """读取 JSON 格式的论文数据。"""
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        return ParsedPaper(
            source_path=str(path),
            title=data.get("title", ""),
            authors=data.get("authors", ""),
            year=data.get("year", 0),
            abstract=data.get("abstract", ""),
            sections=data.get("sections", []),
            full_text=json.dumps(data, ensure_ascii=False)[:50000],
        )

    return ParsedPaper(
        source_path=str(path),
        full_text=json.dumps(data, ensure_ascii=False)[:50000],
    )


def read_papers_from_directory(
    directory: Path,
    extensions: Optional[set[str]] = None,
) -> list[ParsedPaper]:
    """批量读取目录下的所有文献文件。"""
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    exts = extensions or SUPPORTED_EXTENSIONS
    papers = []
    for f in sorted(directory.iterdir()):
        if f.suffix.lower() in exts and f.is_file():
            try:
                paper = read_paper(f)
                papers.append(paper)
                logger.info(f"[PaperReader] Parsed: {f.name} ({paper.n_pages} pages)")
            except Exception as e:
                logger.warning(f"[PaperReader] Failed to parse {f.name}: {e}")
    return papers
