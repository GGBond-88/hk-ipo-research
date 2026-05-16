"""L1 分段层：从港股 IPO 招股书 PDF 中定位并提取 "Use of Proceeds" 章节。

定位策略（按优先级）：
  1. TOC（书签）—— PyMuPDF get_toc()，精确可靠
  2. 正则回退 —— pymupdf4llm 转 Markdown 后用正则匹配章节标题

提取内容：
  - 文本：pymupdf4llm 转 Markdown（保留表格结构）
  - 表格：pdfplumber 独立抽取（结构化二维列表）

输出：data/sections/<stem>.json，每份 PDF 一个文件。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pdfplumber
import pymupdf
import pymupdf4llm

# ── 章节标题匹配正则 ─────────────────────────────────────────────────────────
_SECTION_RE = re.compile(
    r"(?:future\s+plans?\s+and\s+)?use\s+of\s+proceeds",
    re.IGNORECASE,
)

# Markdown 标题行（# / ## / ### …）或加粗标题行（** … **）
_MD_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)", re.MULTILINE)
# pymupdf4llm 有时把章节标题输出为加粗段落而非 # 标题，单独捕获
_MD_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*\s*$", re.MULTILINE)

# ── Cover-page metadata regex ────────────────────────────────────────────────
_TICKER_RE = re.compile(r"[Ss]tock\s+[Cc]ode[\s:：]+(\d{4,5})", re.IGNORECASE)
_DATE_COVER_RE = re.compile(
    r"(\d{1,2})\s+"
    r"(January|February|March|April|May|June|July|August"
    r"|September|October|November|December)\s+(\d{4})",
    re.IGNORECASE,
)
_MONTHS_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}
_DATE_FILENAME_RE = re.compile(r"(\d{4})(\d{2})(\d{2})")


def _parse_date_from_filename(filename: str) -> str | None:
    """Return ISO date from embedded YYYYMMDD in filenames like ltn20180907011."""
    m = _DATE_FILENAME_RE.search(filename)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        if 2000 <= int(y) <= 2099 and 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{mo}-{d}"
    return None


def _ticker_from_markdown(cover_md: str) -> str | None:
    """Return HK stock ticker from cover-page markdown, or None."""
    m = _TICKER_RE.search(cover_md)
    return m.group(1).strip() if m else None


def _date_from_markdown(cover_md: str, filename: str) -> str | None:
    """Return ISO document date from cover markdown; fall back to filename."""
    matches = list(_DATE_COVER_RE.finditer(cover_md))
    if matches:
        dm = matches[-1]
        return f"{dm.group(3)}-{_MONTHS_MAP[dm.group(2).lower()]}-{int(dm.group(1)):02d}"
    return _parse_date_from_filename(filename)


def _extract_ticker(doc: pymupdf.Document) -> str | None:
    """Read first 3 pages and return HK stock ticker, or None."""
    pages = list(range(min(3, doc.page_count)))
    return _ticker_from_markdown(pymupdf4llm.to_markdown(doc, pages=pages))


def _extract_document_date(doc: pymupdf.Document, filename: str) -> str | None:
    """Read first 3 pages and return ISO document date; fall back to filename."""
    pages = list(range(min(3, doc.page_count)))
    return _date_from_markdown(pymupdf4llm.to_markdown(doc, pages=pages), filename)


def _matches_section_title(title: str) -> bool:
    """判断字符串是否是 Use of Proceeds 章节标题（大小写不敏感）。

    匹配：
      "USE OF PROCEEDS" / "Use of Proceeds" / "use of proceeds"
      "FUTURE PLANS AND USE OF PROCEEDS"（及其大小写变体）
    不匹配：
      "Use of Proceeds Summary"（子章节干扰项，含 Summary 后缀）
      "Application of Proceeds"（近义但措辞不同）
      空字符串
    """
    if not title or not title.strip():
        return False
    # 必须整体匹配：标题内容与正则完全对应，不能只是包含一个子串
    # 用 fullmatch 而非 search，防止 "Use of Proceeds Summary" 误匹配
    return bool(re.fullmatch(
        r"(?:future\s+plans?\s+and\s+)?use\s+of\s+proceeds",
        title.strip(),
        re.IGNORECASE,
    ))


# ── TOC 纯逻辑 ────────────────────────────────────────────────────────────────

def _locate_in_toc_list(
    toc: list[list], page_count: int
) -> tuple[str, int, int] | None:
    """从 TOC 列表中定位目标章节的起止页（1-based）。

    参数格式与 PyMuPDF get_toc() 一致：[[level, title, page_1based], ...]
    返回 (section_title, start_page, end_page)，找不到返回 None。
    """
    if not toc:
        return None

    target_idx: int | None = None
    for i, (_, title, _page) in enumerate(toc):
        if _matches_section_title(title):
            target_idx = i
            break

    if target_idx is None:
        return None

    target_lvl, target_title, start_page = toc[target_idx]

    end_page = page_count  # 默认到文档末尾
    for lvl, _, page in toc[target_idx + 1 :]:
        if lvl <= target_lvl:
            end_page = page - 1
            break

    return target_title, start_page, end_page


# ── TOC 定位（PDF 包装层） ─────────────────────────────────────────────────────

def _locate_via_toc(doc: pymupdf.Document) -> tuple[str, int, int] | None:
    """从 PDF 书签中找到目标章节的起止页（1-based）。"""
    return _locate_in_toc_list(doc.get_toc(), doc.page_count)


# ── Regex 纯逻辑 ──────────────────────────────────────────────────────────────

def _locate_in_markdown(
    md_text: str, total_pages: int
) -> tuple[str, int, int] | None:
    """在 Markdown 全文中定位目标章节，估算起止页（1-based）。

    同时识别两种标题格式：
      - Markdown 标题：## FUTURE PLANS AND USE OF PROCEEDS
      - 加粗段落：**FUTURE PLANS AND USE OF PROCEEDS**
    返回 (section_title, start_page, end_page)，找不到返回 None。
    """
    # 收集所有标题候选：(char_pos, level, title_text)
    # level: # 标题用 1-4，加粗段落用 level=1（视为顶级）
    candidates: list[tuple[int, int, str]] = []
    for m in _MD_HEADING_RE.finditer(md_text):
        candidates.append((m.start(), len(m.group(1)), m.group(2).strip()))
    for m in _MD_BOLD_RE.finditer(md_text):
        # 加粗标题只在没有被 # 标题覆盖时补充（避免重复）
        pos = m.start()
        if not any(abs(c[0] - pos) < 5 for c in candidates):
            candidates.append((pos, 1, m.group(1).strip()))
    candidates.sort(key=lambda x: x[0])

    target_idx: int | None = None
    for i, (_pos, _lvl, title) in enumerate(candidates):
        if _matches_section_title(title):
            target_idx = i
            break

    if target_idx is None:
        return None

    target_pos, target_level, section_title = candidates[target_idx]
    total_chars = len(md_text)

    def char_to_page(pos: int) -> int:
        if total_chars == 0:
            return 1
        return max(1, round(pos / total_chars * total_pages))

    start_page = char_to_page(target_pos)

    end_page = total_pages
    for pos, lvl, _ in candidates[target_idx + 1 :]:
        if lvl <= target_level:
            end_page = max(start_page, char_to_page(pos) - 1)
            break

    return section_title, start_page, end_page


# ── 正则回退定位（PDF 包装层） ────────────────────────────────────────────────

def _locate_via_regex(doc: pymupdf.Document) -> tuple[str, int, int] | None:
    """把全文转 Markdown，用正则找章节标题行，估算起止页（1-based）。"""
    md_full = pymupdf4llm.to_markdown(doc)
    return _locate_in_markdown(md_full, doc.page_count)


# ── 文本提取 ──────────────────────────────────────────────────────────────────

def _extract_text(doc: pymupdf.Document, start_page: int, end_page: int) -> str:
    """用 pymupdf4llm 提取指定页范围（1-based）的 Markdown 文本。"""
    # pymupdf4llm.to_markdown 接受 0-based 页码列表
    pages = list(range(start_page - 1, end_page))
    return pymupdf4llm.to_markdown(doc, pages=pages)


# ── 表格提取 ──────────────────────────────────────────────────────────────────

def _extract_tables(pdf_path: str, start_page: int, end_page: int) -> list[dict[str, Any]]:
    """用 pdfplumber 提取指定页范围（1-based）内的所有表格。

    每张表格返回 {page, table_index, headers, rows}。
    """
    results: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(start_page - 1, end_page):  # pdfplumber 0-based
            if page_num >= len(pdf.pages):
                break
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                if not table:
                    continue
                # 首行当表头；空单元格替换为空字符串
                rows = [[cell or "" for cell in row] for row in table]
                headers = rows[0] if rows else []
                results.append(
                    {
                        "page": page_num + 1,  # 1-based
                        "table_index": t_idx,
                        "headers": headers,
                        "rows": rows[1:],
                    }
                )
    return results


# ── 主入口函数 ────────────────────────────────────────────────────────────────

def extract_use_of_proceeds(pdf_path: str) -> dict[str, Any]:
    """从指定 PDF 中提取 Use of Proceeds 章节，返回结构化字典。

    字典结构：
        company_file      : PDF 文件名（不含路径）
        section_title     : 章节标题原文
        start_page        : 起始页（1-based）
        end_page          : 结束页（1-based）
        text              : Markdown 格式章节全文
        tables            : pdfplumber 提取的表格列表
        extraction_method : "toc" | "regex"

    找不到章节时抛出 ValueError。
    """
    doc = pymupdf.open(pdf_path)
    try:
        hk_ticker = _extract_ticker(doc)
        document_date = _extract_document_date(doc, Path(pdf_path).name)

        result = _locate_via_toc(doc)
        method = "toc"
        if result is None:
            result = _locate_via_regex(doc)
            method = "regex"
        if result is None:
            raise ValueError(f"Cannot locate 'Use of Proceeds' section in {pdf_path}")

        section_title, start_page, end_page = result
        text = _extract_text(doc, start_page, end_page)
    finally:
        doc.close()

    tables = _extract_tables(pdf_path, start_page, end_page)

    return {
        "company_file": Path(pdf_path).name,
        "hk_ticker": hk_ticker,
        "document_date": document_date,
        "section_title": section_title,
        "start_page": start_page,
        "end_page": end_page,
        "text": text,
        "tables": tables,
        "extraction_method": method,
    }


def process_all(raw_dir: Path, sections_dir: Path) -> None:
    """处理 raw_dir 下所有 PDF，结果写入 sections_dir。"""
    pdfs = sorted(raw_dir.glob("*.pdf"))
    if not pdfs:
        print(f"[WARN] No PDF files found in {raw_dir}")
        return

    for pdf_path in pdfs:
        print(f"\n→ {pdf_path.name}")
        try:
            data = extract_use_of_proceeds(str(pdf_path))
        except ValueError as e:
            print(f"  [WARN] {e}")
            continue
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            continue

        out_path = sections_dir / f"{pdf_path.stem}.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        word_count = len(data["text"].split())
        print(f"  method      : {data['extraction_method']}")
        print(f"  section     : {data['section_title']!r}")
        print(f"  ticker      : {data['hk_ticker']}")
        print(f"  date        : {data['document_date']}")
        print(f"  pages       : {data['start_page']}–{data['end_page']}")
        print(f"  text words  : {word_count:,}")
        print(f"  tables found: {len(data['tables'])}")
        print(f"  → saved to  : {out_path.name}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Allow running as: python -m hk_ipo.l1_sectioning [raw_dir] [sections_dir]
    from hk_ipo.config import RAW_PDFS_DIR, SECTIONS_DIR

    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_PDFS_DIR
    sections_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else SECTIONS_DIR
    sections_dir.mkdir(parents=True, exist_ok=True)

    process_all(raw_dir, sections_dir)
