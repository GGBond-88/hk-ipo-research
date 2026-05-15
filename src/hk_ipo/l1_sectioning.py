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

# Markdown 标题行（# / ## / ### …）
_MD_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)", re.MULTILINE)


# ── TOC 定位 ──────────────────────────────────────────────────────────────────

def _locate_via_toc(doc: pymupdf.Document) -> tuple[str, int, int] | None:
    """从 PDF 书签中找到目标章节的起止页（1-based）。

    返回 (section_title, start_page_1based, end_page_1based)，找不到返回 None。
    """
    toc = doc.get_toc()  # [[level, title, page_1based], ...]
    if not toc:
        return None

    target_idx: int | None = None
    for i, (lvl, title, page) in enumerate(toc):
        if _SECTION_RE.search(title):
            target_idx = i
            break

    if target_idx is None:
        return None

    target_lvl, target_title, start_page = toc[target_idx]

    # 找同级或更高级的下一章节作为结束边界
    end_page = doc.page_count  # 默认到文档末尾
    for lvl, _, page in toc[target_idx + 1 :]:
        if lvl <= target_lvl:
            end_page = page - 1
            break

    return target_title, start_page, end_page


# ── 正则回退定位 ──────────────────────────────────────────────────────────────

def _locate_via_regex(doc: pymupdf.Document) -> tuple[str, int, int] | None:
    """把全文转 Markdown，用正则找章节标题行，估算起止页（1-based）。"""
    md_full = pymupdf4llm.to_markdown(doc)
    headings = list(_MD_HEADING_RE.finditer(md_full))

    target_idx: int | None = None
    for i, m in enumerate(headings):
        if _SECTION_RE.search(m.group(2)):
            target_idx = i
            break

    if target_idx is None:
        return None

    target_m = headings[target_idx]
    target_level = len(target_m.group(1))  # '#' 数量即层级
    section_title = target_m.group(2).strip()

    # 文本位置 → 估算页码（按字符偏移比例）
    total_chars = len(md_full)
    total_pages = doc.page_count

    def char_to_page(pos: int) -> int:
        return max(1, round(pos / total_chars * total_pages))

    start_page = char_to_page(target_m.start())

    # 找下一个同级或更高标题
    end_page = total_pages
    for m in headings[target_idx + 1 :]:
        if len(m.group(1)) <= target_level:
            end_page = char_to_page(m.start()) - 1
            break

    return section_title, max(1, start_page), max(start_page, end_page)


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
