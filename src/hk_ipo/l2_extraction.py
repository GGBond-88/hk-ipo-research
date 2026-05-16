"""L2 提取层：调用 LLM（langextract + OpenRouter）将 L1 输出的章节 Markdown 文本
结构化提取为每个资金用途项目的 JSON 记录。

层级结构：
  - top-level 项（Approximately/approximately，无 (i)/(a) 前缀）→ parent_id = null
  - inline sub-items（上级 bullet 正文里的 (i)(ii)(iii)，无独立金额）
    → 通过 inline_sub_items 属性传递，post-processing 展开，parent_id 指向父项
  - indented sub-bullets（独立缩进行，带 (i)(ii)(iii)，有独立金额）
    → 直接作为独立 Extraction，parent_id 指向父项

子项 parent_id 由 post-processing 用状态机分配，LLM 无需知道 use_id。

输入：data/sections/<stem>.json
输出：data/extracted/<stem>.json  /  .error.json（失败时）
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import langextract as lx
import openai
from langextract.factory import ModelConfig
from pydantic import ValidationError

from hk_ipo import config
from hk_ipo.schema import CATEGORY_L2, validate_extraction

logger = logging.getLogger(__name__)


# ── Prompt ───────────────────────────────────────────────────────────────────

def _build_prompt() -> str:
    """Build the extraction prompt dynamically from CATEGORY_L2 (single source of truth)."""
    category_list = "\n".join(f'                        "{c}"' for c in CATEGORY_L2)
    return f"""\
Extract top-level use-of-proceeds items from the IPO prospectus section.
Read ONLY from the bullet list. Skip Markdown table rows (lines starting with |).

TOP-LEVEL items are bullets at the LEFTMOST margin — they start with "- Approximately"
or "- approximately" with NO leading spaces. Lines that begin with spaces (indented)
are sub-items that belong to their parent bullet; do NOT extract them separately.

COMPLETENESS: Extract ALL top-level bullets. Do not stop early. A typical section
has 2–8 top-level items. Two different items may share the same percentage value —
extract each one separately.

► extraction_text MUST be the COMPLETE bullet paragraph — include ALL sentences
  of that bullet, not just the first sentence.
  Stop at the next "- Approximately"/"- approximately" line at the left margin.

► Skip any inline sub-enumerations "(i) X, (ii) Y" — do NOT extract them as
  separate items.

FOR EACH top-level item, produce a use_of_proceeds_item with attributes:
  percentage        : numeric % string without sign, e.g. "35.0"
                      Use "null" only if no percentage figure appears.
  amount_hkd_million: HK$ millions string, e.g. "10893.0"
                      Use "null" only if genuinely absent.
  category          : short normalised label, choose best fit from:
{category_list}
  category_proposed : if no category fits well, put the raw label here and set
                      category to the closest standard match above
  category_raw      : verbatim use-description phrase from source
  description       : 1–2 sentence summary, max 200 chars\
"""


_PROMPT = _build_prompt()


# ── Few-shot example texts ────────────────────────────────────────────────────

# ── Example 1 : CATL (2 top-level, no sub-items — clean baseline) ─────────
_EX1_B1 = (
    "Approximately 90% or HK$27,646.1 million will be used to advance the construction "
    "of Phase I and II of our Hungary project. The designed annual production capacity of "
    "Phase I and II is 34 GWh and 38 GWh respectively, totalling 72 GWh for EV batteries. "
    "The total investment is expected to be no more than EUR7.3 billion."
)
_EX1_B2 = (
    "Approximately 10% or HK$3,071.8 million will be used for working capital and other "
    "general corporate purposes."
)
_EX1_TEXT = (
    "We estimate that we will receive net proceeds of approximately HK$30,717.9 million. "
    "We currently intend to apply these net proceeds for the following purposes:\n\n"
    f"- {_EX1_B1}\n"
    f"- {_EX1_B2}\n"
)

# ── Example 2 : Meituan (complete multi-sentence paragraphs + inline sub-items)
# Key teaching points:
#   (a) extraction_text = the FULL paragraph, not just the first sentence
#   (b) inline (i)(ii)(iii) go into inline_sub_items attribute as "X; Y; Z"
#   (c) different top-level items get different categories
_EX2_B1 = (
    "approximately 35% (approximately HK$10,893 million) to upgrade our technology "
    "and enhance our research and development capabilities. Our efforts include hiring "
    "computer programming experts, scientists and other talents, expanding our intellectual "
    "property portfolio both domestically and internationally, and further investing in our "
    "IT infrastructure and AI technologies. We intend to fund several major R&D projects "
    "involving (i) data analytics, (ii) machine learning and (iii) driverless delivery "
    "system. The results of these R&D projects will be applied in our products and services."
)
_EX2_B2 = (
    "approximately 35% (approximately HK$10,893 million) to develop new services and "
    "products. We intend to develop, among others, (i) merchant enabling systems and "
    "technologies, which provide cloud-based ERP systems and smart payment solutions to "
    "merchants; (ii) on-demand delivery of non-restaurant food; and "
    "(iii) restaurant supply chain services, which provide raw material procurement and "
    "logistics services to restaurants."
)
_EX2_B3 = (
    "approximately 20% (approximately HK$6,225 million) to selectively pursue acquisitions "
    "or investments in assets and businesses which are complementary to our business and "
    "are in line with our strategies. We intend to continue to identify, invest in and "
    "incubate promising companies that can expand the services we offer."
)
_EX2_B4 = (
    "approximately 10% (approximately HK$3,112 million) for working capital and general "
    "corporate purposes."
)
_EX2_TEXT = (
    "We estimate that we will receive net proceeds of approximately HK$31,123 million. "
    "We intend to use the net proceeds for the following purposes:\n\n"
    f"- {_EX2_B1}\n"
    f"- {_EX2_B2}\n"
    f"- {_EX2_B3}\n"
    f"- {_EX2_B4}\n"
)

# ── Example 3 : Indented sub-bullets with independent financial figures ───────
# Key teaching point: (i)(ii)(iii) as SEPARATE indented lines → item_level="sub",
# each with its own percentage and amount.
_EX3_TOP1 = (
    "Approximately 71.4%, or HK$1,526.9 million, is expected to be used to expand "
    "our overall production capacity and upgrade our production lines, including new "
    "plants, production lines, and equipment purchases."
)
_EX3_TOP2 = (
    "Approximately 11.6%, or HK$248.4 million, is expected to be used for research "
    "and development and product innovation to maintain our competitive advantage."
)
_EX3_TOP3 = (
    "Approximately 8.1%, or HK$173.4 million, is expected to be used for working "
    "capital and general corporate purposes."
)
_EX3_TEXT = (
    "We estimate that we will receive net proceeds of approximately HK$2,141.0 million. "
    "We intend to use the proceeds for the following purposes:\n\n"
    f"- {_EX3_TOP1}\n"
    f"- {_EX3_TOP2}\n"
    f"- {_EX3_TOP3}\n"
)


def _build_examples() -> list[lx.data.ExampleData]:
    return [
        # ── Example 1 : CATL, no sub-items ───────────────────────────────────
        lx.data.ExampleData(
            text=_EX1_TEXT,
            extractions=[
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX1_B1,
                    attributes={
                        "percentage": "90.0",
                        "amount_hkd_million": "27646.1",
                        "category": "Manufacturing expansion",
                        "category_raw": "advance the construction of Phase I and II of our Hungary project",
                        "description": "Build EV battery factory in Hungary with 72 GWh total capacity (Phase I 34 GWh + Phase II 38 GWh).",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX1_B2,
                    attributes={
                        "percentage": "10.0",
                        "amount_hkd_million": "3071.8",
                        "category": "Working capital",
                        "category_raw": "working capital and other general corporate purposes",
                        "description": "General working capital and corporate purposes.",
                    },
                ),
            ],
        ),
        # ── Example 2 : Meituan, full paragraphs + inline_sub_items ──────────
        lx.data.ExampleData(
            text=_EX2_TEXT,
            extractions=[
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX2_B1,
                    attributes={
                        "percentage": "35.0",
                        "amount_hkd_million": "10893.0",
                        "category": "R&D and technology",
                        "category_raw": "upgrade our technology and enhance our research and development capabilities",
                        "description": "Hire experts, expand IP portfolio, invest in IT and AI; fund R&D in data analytics, ML, and driverless delivery.",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX2_B2,
                    attributes={
                        "percentage": "35.0",
                        "amount_hkd_million": "10893.0",
                        "category": "Product development",
                        "category_raw": "develop new services and products",
                        "description": "Develop merchant enabling systems, on-demand food delivery, and restaurant supply chain services.",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX2_B3,
                    attributes={
                        "percentage": "20.0",
                        "amount_hkd_million": "6225.0",
                        "category": "Acquisitions and investments",
                        "category_raw": "selectively pursue acquisitions or investments in assets and businesses",
                        "description": "Identify, invest in, and incubate complementary companies aligned with business strategies.",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX2_B4,
                    attributes={
                        "percentage": "10.0",
                        "amount_hkd_million": "3112.0",
                        "category": "Working capital",
                        "category_raw": "working capital and general corporate purposes",
                        "description": "General working capital and corporate purposes.",
                    },
                ),
            ],
        ),
        # ── Example 3 : Indented sub-bullets with independent financials ──────
        lx.data.ExampleData(
            text=_EX3_TEXT,
            extractions=[
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX3_TOP1,
                    attributes={
                        "percentage": "71.4",
                        "amount_hkd_million": "1526.9",
                        "category": "Production capacity",
                        "category_raw": "expand our overall production capacity and upgrade our production lines",
                        "description": "Build/expand plants, install production lines, and purchase equipment across multiple countries.",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX3_TOP2,
                    attributes={
                        "percentage": "11.6",
                        "amount_hkd_million": "248.4",
                        "category": "R&D and technology",
                        "category_raw": "research and development and product innovation",
                        "description": "Develop new products, expand R&D team, and conduct product testing.",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="use_of_proceeds_item",
                    extraction_text=_EX3_TOP3,
                    attributes={
                        "percentage": "8.1",
                        "amount_hkd_million": "173.4",
                        "category": "Working capital",
                        "category_raw": "working capital and general corporate purposes",
                        "description": "General working capital and corporate purposes.",
                    },
                ),
            ],
        ),
    ]


# ── Model config ──────────────────────────────────────────────────────────────

def _build_model_config() -> ModelConfig:
    return ModelConfig(
        model_id=config.L2_TEXT_MODEL,
        provider="openai",
        provider_kwargs={
            "api_key": config.OPENROUTER_API_KEY,
            "base_url": config.OPENROUTER_BASE_URL,
            "default_headers": {
                "HTTP-Referer": "https://github.com/hk-ipo-research",
                "X-Title": "HK IPO Research",
            },
        },
    )


# ── Text cleaning ─────────────────────────────────────────────────────────────

_TABLE_LINE_RE = re.compile(r"^\s*\|")
_PAGE_MARKER_RE = re.compile(r"^[\s–—-]*\d{1,4}[\s–—-]*$")
# Matches the leading "  - " (2+ spaces then dash+space) of an indented sub-bullet.
# We neutralise these by removing the dash so the LLM cannot confuse them with
# top-level bullets.
_INDENTED_BULLET_RE = re.compile(r"^(\s{2,})-\s", re.MULTILINE)


def _clean_section_text(text: str) -> str:
    """Remove Markdown table rows and page-number footers; collapse blank lines.

    Also converts indented sub-bullets ("   - approximately X%") to plain
    continuation prose ("     approximately X%") so the LLM cannot mistake
    them for independent top-level extraction targets.
    """
    cleaned = []
    for line in text.splitlines():
        s = line.strip()
        if _TABLE_LINE_RE.match(s):
            continue
        if _PAGE_MARKER_RE.match(s) and len(s) < 20:
            continue
        cleaned.append(line)
    result = "\n".join(cleaned)
    # Neutralise indented sub-bullet dashes: "   - " → "     "
    result = _INDENTED_BULLET_RE.sub(r"\1  ", result)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


# ── Total proceeds extraction ─────────────────────────────────────────────────

_PROCEEDS_RE = re.compile(
    r"net\s+proceeds[^.]{0,200}?(?:approximately\s+)?HK\$([\d,]+(?:\.\d+)?)\s*million",
    re.IGNORECASE | re.DOTALL,
)


def _extract_total_proceeds(text: str) -> tuple[float | None, str]:
    m = _PROCEEDS_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "")), "HKD"
    return None, "HKD"


# ── Source text completion ────────────────────────────────────────────────────

_NEXT_TOP_BULLET_RE = re.compile(
    r"\n- (?:Approximately|approximately)\s", re.IGNORECASE
)
_MD_HEADING_RE = re.compile(r"\n#{1,4}\s+|\n\*\*[A-Z]")


def _extend_source_text(extraction_text: str, full_text: str) -> str:
    """Extend a (possibly truncated) extraction_text to the full bullet paragraph.

    Finds the extraction_text in full_text, then extends rightward to the
    next top-level bullet start, the next Markdown heading, or end of text.
    """
    if not extraction_text:
        return extraction_text
    anchor = extraction_text[:60].strip()
    pos = full_text.find(anchor)
    if pos == -1:
        return extraction_text  # can't locate; keep as-is

    search_start = pos + len(anchor)
    # Find the nearest boundary: next top-level bullet OR next Markdown heading
    candidates: list[int] = []
    m_bullet = _NEXT_TOP_BULLET_RE.search(full_text, search_start)
    if m_bullet:
        candidates.append(m_bullet.start())
    m_heading = _MD_HEADING_RE.search(full_text, search_start)
    if m_heading:
        candidates.append(m_heading.start())
    end = min(candidates) if candidates else len(full_text)

    full_para = full_text[pos:end].strip()
    # Strip trailing page markers like "– 394 –"
    full_para = re.sub(r"\s*[–—-]{1,3}\s*\d+\s*[–—-]{1,3}\s*$", "", full_para).strip()
    return full_para or extraction_text


# ── Retry wrapper ─────────────────────────────────────────────────────────────

# Only retry on transient network / API errors; let programming errors through.
_RETRYABLE = (openai.APIError, httpx.HTTPError, TimeoutError, ConnectionError)


def _run_with_retry(fn: Any, max_retries: int = 3) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  [RETRY] attempt {attempt + 1} failed ({exc!r}). Waiting {wait}s…")
                time.sleep(wait)
        # Programming errors (ValueError, AttributeError, etc.) propagate immediately.
    raise last_exc  # type: ignore[misc]


# ── Result parsing ────────────────────────────────────────────────────────────

def _safe_float_or_none(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("null", "", "none", "n/a"):
        return None
    try:
        return float(s.replace(",", "").replace("%", ""))
    except (ValueError, TypeError):
        return None


def _parse_extractions(
    doc: lx.data.AnnotatedDocument, full_text: str
) -> list[dict[str, Any]]:
    """Convert langextract output to top-level uses list.

    - Only top-level items (with at least one financial figure) are kept.
    - source_text is extended to the full bullet paragraph.
    """
    uses: list[dict[str, Any]] = []

    for ext in doc.extractions:
        if ext.extraction_class != "use_of_proceeds_item":
            continue
        attrs = ext.attributes or {}

        # Drop items with neither percentage nor amount (spurious extractions).
        if _safe_float_or_none(attrs.get("percentage")) is None and \
                _safe_float_or_none(attrs.get("amount_hkd_million")) is None:
            continue

        use_id = f"use_{len(uses) + 1:03d}"
        source_text = _extend_source_text(ext.extraction_text or "", full_text)

        uses.append(
            {
                "use_id": use_id,
                "parent_id": None,
                "category": attrs.get("category", ""),
                "category_proposed": attrs.get("category_proposed") or None,
                "category_raw": attrs.get("category_raw", ""),
                "amount_hkd_million": _safe_float_or_none(attrs.get("amount_hkd_million")),
                "percentage": _safe_float_or_none(attrs.get("percentage")),
                "description": attrs.get("description", ""),
                "source_text": source_text,
            }
        )

    return uses


# ── Core extraction ───────────────────────────────────────────────────────────

def extract_section(section_data: dict[str, Any]) -> dict[str, Any]:
    """Run LLM extraction on an L1 section dict; return the L2 output dict."""
    text = _clean_section_text(section_data["text"])
    total_proceeds, currency = _extract_total_proceeds(text)

    # Metadata populated by L1; warn once if keys are absent (stale L1 output)
    hk_ticker: str | None = section_data.get("hk_ticker")
    document_date: str | None = section_data.get("document_date")
    if hk_ticker is None and document_date is None:
        print("  [WARN] hk_ticker/document_date missing — re-run L1 to populate")

    doc: lx.data.AnnotatedDocument = _run_with_retry(
        lambda: lx.extract(
            text_or_documents=text,
            prompt_description=_PROMPT,
            examples=_build_examples(),
            config=_build_model_config(),
        )
    )

    uses = _parse_extractions(doc, text)

    top_uses = [u for u in uses if u["parent_id"] is None]
    pct_sum = round(sum(u["percentage"] or 0 for u in top_uses), 1)

    result = {
        "company_file": section_data["company_file"],
        "section_source": Path(section_data["company_file"]).stem + ".json",
        "hk_ticker": hk_ticker,
        "document_date": document_date,
        "model_used": config.L2_TEXT_MODEL,
        "extraction_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "total_net_proceeds_hkd_million": total_proceeds,
        "currency": currency,
        "uses": uses,
        "validation_preview": {
            "percentage_sum": pct_sum,
            "top_level_count": len(top_uses),
            "total_items_count": len(uses),
        },
    }

    # Schema validation — log WARNING on failure but do not crash.
    try:
        validate_extraction(result)
    except ValidationError as exc:
        logger.warning(
            "[WARN] Schema validation failed for %s: %s",
            section_data.get("company_file", "?"),
            exc,
        )

    return result


# ── File I/O ──────────────────────────────────────────────────────────────────

def process_single(section_file: Path, extracted_dir: Path) -> dict[str, Any]:
    extracted_dir.mkdir(parents=True, exist_ok=True)
    section_data = json.loads(section_file.read_text(encoding="utf-8"))
    stem = section_file.stem
    out_path = extracted_dir / f"{stem}.json"
    err_path = extracted_dir / f"{stem}.error.json"

    print(f"\n→ {section_file.name}")
    try:
        result = extract_section(section_data)
    except Exception as exc:
        err_payload = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "section_file": str(section_file),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        err_path.write_text(json.dumps(err_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [ERROR] {exc}")
        print(f"  → error written to: {err_path.name}")
        raise

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    vp = result["validation_preview"]
    print(f"  top-level   : {vp['top_level_count']} items")
    print(f"  total items : {vp['total_items_count']} (incl. sub-items)")
    print(f"  pct sum     : {vp['percentage_sum']}%")
    print(f"  total HK$M  : {result['total_net_proceeds_hkd_million']}")
    print(f"  → saved to  : {out_path.name}")
    return result


def process_all(sections_dir: Path, extracted_dir: Path) -> None:
    jsons = sorted(sections_dir.glob("*.json"))
    if not jsons:
        print(f"[WARN] No JSON files found in {sections_dir}")
        return
    succeeded = failed = 0
    for jf in jsons:
        try:
            process_single(jf, extracted_dir)
            succeeded += 1
        except Exception as exc:
            failed += 1
            print(f"  [SKIP] {jf.name}: {exc}")
    print(f"\nL2 complete: {succeeded} succeeded, {failed} failed")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="L2: structure Use of Proceeds via LLM (langextract + OpenRouter)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--single", metavar="FILENAME",
                       help="Process one file from data/sections/ by name")
    group.add_argument("--all", action="store_true",
                       help="Process all files in data/sections/")
    args = parser.parse_args()

    from hk_ipo.config import EXTRACTED_DIR, SECTIONS_DIR

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    if args.single:
        sf = SECTIONS_DIR / args.single
        if not sf.exists():
            import sys
            print(f"[ERROR] Not found: {sf}")
            sys.exit(1)
        process_single(sf, EXTRACTED_DIR)
    elif args.all:
        process_all(SECTIONS_DIR, EXTRACTED_DIR)
    else:
        parser.error(
            "Specify --single <filename.json> or --all. "
            "Explicit choice required to avoid unintended API calls."
        )
