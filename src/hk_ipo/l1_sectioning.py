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

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from hk_ipo.logging_setup import get_logger

logger = get_logger(__name__)

import pdfplumber
import pymupdf
import pymupdf4llm
from langdetect import DetectorFactory, LangDetectException, detect_langs

DetectorFactory.seed = 0  # deterministic

# ── 文件名 Ticker 提取 ────────────────────────────────────────────────────────
_FILENAME_TICKER_RE = re.compile(r"^(\d{4,5})$")


def ticker_from_filename(path: str) -> str | None:
    """Return zero-padded 5-digit HK ticker from filename stem, or None."""
    stem = Path(path).stem
    m = _FILENAME_TICKER_RE.match(stem)
    return m.group(1).zfill(5) if m else None


def detect_language(text: str) -> str:
    """Classify text language. Returns one of: 'en', 'zh', 'mixed', 'unknown'.

    Rule:
      - 'en' if English share >= 80%
      - 'zh' if Chinese share >= 80%
      - 'mixed' if either is in (20%, 80%) and the other has at least 20%
      - 'unknown' otherwise (empty text, langdetect failure)
    """
    if not text or not text.strip():
        return "unknown"
    try:
        langs = detect_langs(text[:5000])  # cap to avoid huge inputs
    except LangDetectException:
        return "unknown"
    shares: dict[str, float] = {}
    for L in langs:
        code = "en" if str(L.lang) == "en" else ("zh" if str(L.lang).startswith("zh") else None)
        if code:
            shares[code] = shares.get(code, 0.0) + float(L.prob)
    en = shares.get("en", 0.0)
    zh = shares.get("zh", 0.0)
    if en >= 0.8:
        return "en"
    if zh >= 0.8:
        return "zh"
    if en >= 0.2 and zh >= 0.2:
        return "mixed"
    return "unknown"


# ── 章节标题匹配正则 ─────────────────────────────────────────────────────────
# Accepts these heading variants (case-insensitive):
#   - USE OF PROCEEDS
#   - USE OF NET PROCEEDS
#   - FUTURE PLANS AND USE OF (NET) PROCEEDS
#   - FUTURE PLANS AND USE OF (NET) PROCEEDS FROM THE GLOBAL OFFERING / PLACING / OFFERING
#   - REASONS FOR THE PLACING AND USE OF PROCEEDS
# Rejects:
#   - USE OF PROCEEDS SUMMARY (sub-section, would match prefix but fullmatch rejects)
#   - APPLICATION OF PROCEEDS (different wording)
_SECTION_TITLE_PATTERN = (
    r"(?:future\s+plans?\s+and\s+|reasons?\s+for\s+the\s+placing\s+and\s+)?"
    r"use\s+of\s+(?:net\s+)?proceeds"
    r"(?:\s+from\s+the\s+(?:global\s+offering|placing|offering))?"
)
_SECTION_RE = re.compile(_SECTION_TITLE_PATTERN, re.IGNORECASE)

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
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
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
    # Strip leading/trailing markdown emphasis (* and _) because
    # pymupdf4llm renders bold paragraph headings as "## **Title**",
    # and the `## ` markdown-heading regex captures "**Title**" with
    # literal asterisks in group(2).
    cleaned = title.strip().strip("*_").strip()
    return bool(
        re.fullmatch(
            _SECTION_TITLE_PATTERN,
            cleaned,
            re.IGNORECASE,
        )
    )


# ── TOC 纯逻辑 ────────────────────────────────────────────────────────────────


def _locate_in_toc_list(toc: list[list], page_count: int) -> tuple[str, int, int] | None:
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


def _locate_in_markdown(md_text: str, total_pages: int) -> tuple[str, int, int] | None:
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

    Strategy note: HK IPO use-of-proceeds tables are typically rendered
    as positionally-aligned text rather than ruled tables. pdfplumber's
    default ('lines'/'lines') therefore returns 0 tables. We try the
    default first (for tables that DO have visible lines), then fall
    back to text-alignment heuristic, which catches the line-less
    tables common in HK prospectuses.
    """
    results: list[dict[str, Any]] = []
    text_settings = {"vertical_strategy": "text", "horizontal_strategy": "text"}
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(start_page - 1, end_page):  # pdfplumber 0-based
            if page_num >= len(pdf.pages):
                break
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            # Fallback: if default strategy found nothing, try text-aligned
            if not tables:
                try:
                    tables = page.extract_tables(table_settings=text_settings) or []
                except Exception:
                    tables = []  # pdfplumber occasionally raises on edge layouts
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


# ── 内容哈希磁盘缓存 ─────────────────────────────────────────────────────────
# Cache lives at data/l1_cache/<sha256_first16>.json.  The cache dir is
# resolved lazily so tests can monkeypatch config.L1_CACHE_DIR freely.

_CACHE_DIR_ENV: Path | None = None  # override in tests via monkeypatch


def _cache_dir() -> Path:
    """Return the L1 cache directory (lazily resolved)."""
    if _CACHE_DIR_ENV is not None:
        return _CACHE_DIR_ENV
    from hk_ipo.config import L1_CACHE_DIR  # local import to avoid circular

    return L1_CACHE_DIR


def _pdf_content_hash(pdf_path: str) -> str:
    """Return the first 16 hex chars of the SHA-256 hash of the PDF bytes."""
    data = Path(pdf_path).read_bytes()
    return hashlib.sha256(data).hexdigest()[:16]


def _cache_path(content_hash: str) -> Path:
    return _cache_dir() / f"{content_hash}.json"


def _load_from_cache(content_hash: str) -> dict[str, Any] | None:
    """Return cached parse result for *content_hash*, or None on miss."""
    p = _cache_path(content_hash)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_to_cache(content_hash: str, result: dict[str, Any]) -> None:
    """Write *result* to the cache file for *content_hash*."""
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    _cache_path(content_hash).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 主入口函数 ────────────────────────────────────────────────────────────────


def extract_use_of_proceeds(pdf_path: str, *, force: bool = False) -> dict[str, Any]:
    """从指定 PDF 中提取 Use of Proceeds 章节，返回结构化字典。

    字典结构：
        company_file      : PDF 文件名（不含路径）
        section_title     : 章节标题原文
        start_page        : 起始页（1-based）
        end_page          : 结束页（1-based）
        text              : Markdown 格式章节全文
        tables            : pdfplumber 提取的表格列表
        extraction_method : "toc" | "regex" | "skipped"
        language          : "en" | "zh" | "mixed" | "unknown"
        skipped           : bool

    Content-hash cache: on non-force runs the function checks
    ``data/l1_cache/<sha256_first16>.json`` before invoking any PDF library.
    Pass ``force=True`` to skip the cache and always re-parse.

    找不到章节时抛出 ValueError。
    """
    # ── Content-hash cache check ────────────────────────────────────────────
    content_hash = _pdf_content_hash(pdf_path)
    if not force:
        cached = _load_from_cache(content_hash)
        if cached is not None:
            return cached

    doc = pymupdf.open(pdf_path)
    try:
        # Guard against corrupted PDFs that open but have 0 pages
        # (PyMuPDF reports "non-page object in page tree" but doesn't raise).
        # pymupdf4llm.to_markdown indexes page_filter[-1] and crashes
        # on an empty pages list — fail fast with a clear message instead.
        if doc.page_count == 0:
            raise ValueError(
                f"PDF has 0 pages (corrupted or non-page object in page tree): {pdf_path}"
            )

        # v2 — read a head sample to detect language; skip non-English with stub
        head_pages = list(range(min(5, doc.page_count)))
        head_md = pymupdf4llm.to_markdown(doc, pages=head_pages)
        language = detect_language(head_md)

        # v2 — derive ticker from filename FIRST (authoritative), fall back to cover
        filename_ticker = ticker_from_filename(pdf_path)
        cover_ticker = _ticker_from_markdown(head_md)
        hk_ticker = filename_ticker or (cover_ticker.zfill(5) if cover_ticker else None)
        document_date = _date_from_markdown(head_md, Path(pdf_path).name)

        if language == "zh":
            zh_result: dict[str, Any] = {
                "company_file": Path(pdf_path).name,
                "hk_ticker": hk_ticker,
                "document_date": document_date,
                "section_title": "",
                "start_page": 0,
                "end_page": 0,
                "text": "",
                "tables": [],
                "extraction_method": "skipped",
                "language": language,
                "skipped": True,
            }
            _save_to_cache(content_hash, zh_result)
            return zh_result

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

    final_result: dict[str, Any] = {
        "company_file": Path(pdf_path).name,
        "hk_ticker": hk_ticker,
        "document_date": document_date,
        "section_title": section_title,
        "start_page": start_page,
        "end_page": end_page,
        "text": text,
        "tables": tables,
        "extraction_method": method,
        "language": language,
        "skipped": False,
    }
    _save_to_cache(content_hash, final_result)
    return final_result


def process_all(
    raw_dir: Path,
    sections_dir: Path,
    limit: int | None = None,
    force: bool = False,
    all_files: bool = True,
) -> None:
    """处理 raw_dir 下所有 PDF，结果写入 sections_dir。

    Args:
        raw_dir: Directory containing PDF files.
        sections_dir: Directory to write JSON output.
        limit: If set, process at most this many PDFs.
        force: If True, overwrite existing output files.
        all_files: If True, filter to only filenames matching \\d{4,5}.pdf.
    """
    pdfs = sorted(raw_dir.glob("*.pdf"))
    if all_files:
        skipped = [p for p in pdfs if ticker_from_filename(p.name) is None]
        for p in skipped:
            logger.warning("filename does not match \\d{4,5}.pdf: %s", p.name)
        pdfs = [p for p in pdfs if ticker_from_filename(p.name) is not None]
    if limit is not None:
        pdfs = pdfs[:limit]
    if not pdfs:
        logger.warning("No PDF files to process in %s", raw_dir)
        return

    for pdf in pdfs:
        ticker = ticker_from_filename(pdf.name)
        if ticker is None:
            logger.warning(
                "Non-numeric filename, using stem as output name: %s", pdf.name
            )
            ticker = Path(pdf.name).stem
        out_path = sections_dir / f"{ticker}.json"
        if not force and out_path.exists():
            logger.info("%s exists; --force to re-run", out_path.name)
            continue
        try:
            data = extract_use_of_proceeds(str(pdf), force=force)
        # Broad except: outermost CLI batch loop guard — log and skip any
        # unexpected error so one bad PDF does not abort the entire run.
        except Exception as exc:
            logger.error("%s: %s", pdf.name, exc)
            continue
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("  -> %s (lang=%s, skipped=%s)", out_path.name, data.get('language'), data.get('skipped'))


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("pdf", nargs="?")
    p.add_argument("--force", action="store_true")
    p.add_argument("--limit", type=int)
    args = p.parse_args()

    from hk_ipo.config import RAW_PDFS_DIR, SECTIONS_DIR

    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    if args.all:
        process_all(RAW_PDFS_DIR, SECTIONS_DIR, limit=args.limit, force=args.force, all_files=True)
    else:
        data = extract_use_of_proceeds(args.pdf)
        ticker = data.get("hk_ticker") or "unknown"
        out = SECTIONS_DIR / f"{ticker}.json"
        if not args.force and out.exists():
            logger.warning("%s exists; --force to re-run", out.name)
        else:
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"-> {out}")  # intentional stdout
