"""L2 extraction layer: call LLM (direct OpenAI SDK + OpenRouter) to convert
L1 section Markdown text into structured JSON records for use-of-proceeds items.

Input:  data/sections/<stem>.json
Output: data/extracted/<stem>.json  /  .error.json (on failure)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import openai
from pydantic import ValidationError

from hk_ipo import config
from hk_ipo.schema import CATEGORY_L2, SCHEMA_VERSION, validate_extraction

logger = logging.getLogger(__name__)

# ── Module-level OpenAI client (created once at import time) ─────────────────

_openai_client = openai.OpenAI(
    api_key=config.OPENROUTER_API_KEY or "placeholder-not-set",
    base_url=config.OPENROUTER_BASE_URL,
)

# ── System prompt ─────────────────────────────────────────────────────────────

_CATEGORY_LIST = "\n".join(f'  - "{c}"' for c in CATEGORY_L2)

_SYSTEM_PROMPT = (
    "You are a financial data extraction assistant specialised in Hong Kong IPO prospectuses.\n"
    "\n"
    "## Task\n"
    "Extract use-of-proceeds data from the provided prospectus section and return it as JSON.\n"
    "\n"
    "## Output format (JSON, no markdown fences)\n"
    "{\n"
    '  "total_net_proceeds_hkd_million": <number or null>,\n'
    '  "uses": [\n'
    "    {\n"
    '      "category": "<one of the allowed categories or null>",\n'
    '      "category_proposed": "<free-form label if no category fits, else null>",\n'
    '      "category_raw": "<verbatim use-description phrase from source>",\n'
    '      "percentage": <number or null>,\n'
    '      "amount_hkd_million": <number or null>,\n'
    '      "description": "<1-2 sentence summary, max 200 chars>",\n'
    '      "source_text": "<complete paragraph from source for this use>"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "\n"
    "## Rules for total_net_proceeds_hkd_million\n"
    "- Use the BASE CASE only. Ignore over-allotment and conditional scenarios.\n"
    "- If multiple figures appear, take the largest non-conditional number.\n"
    "- Express in HK$ millions (e.g. HK$1,000 million -> 1000.0).\n"
    "\n"
    "## Rules for uses array\n"
    "- Extract TOP-LEVEL bullets only.\n"
    "  A top-level item starts with a bullet marker (`-`) at the LEFT margin "
    "(0-2 leading spaces).\n"
    "  Sub-items are indented (≥4 spaces) or are lettered (i)(ii)(iii) inside a bullet.\n"
    "  Each `- approximately X%` at the left margin is ONE top-level item; its entire paragraph\n"
    "  including all sub-bullets belongs in that item's source_text.\n"
    "  Do NOT create a separate entry for a sub-bullet or lettered clause.\n"
    "- source_text must be the COMPLETE paragraph for that bullet from the source.\n"
    "- category must be EXACTLY one of:\n"
    + _CATEGORY_LIST + "\n"
    "- If no category fits, set category_proposed to the raw label and set category to\n"
    "  the closest standard match above.\n"
    "- Extract ALL top-level items. Do not stop early.\n"
    "\n"
    "## Example (FICTIONAL numbers -- format only)\n"
    "Input text:\n"
    "  We estimate net proceeds of approximately HK$5,000 million.\n"
    "  - Approximately 60% or HK$3,000 million will be used for manufacturing expansion.\n"
    "  - Approximately 40% or HK$2,000 million will be used for working capital.\n"
    "\n"
    "Expected output:\n"
    "{\n"
    '  "total_net_proceeds_hkd_million": 5000.0,\n'
    '  "uses": [\n'
    "    {\n"
    '      "category": "Manufacturing expansion",\n'
    '      "category_proposed": null,\n'
    '      "category_raw": "manufacturing expansion",\n'
    '      "percentage": 60.0,\n'
    '      "amount_hkd_million": 3000.0,\n'
    '      "description": "Expand manufacturing capacity.",\n'
    '      "source_text": "Approximately 60% or HK$3,000 million will be used for manufacturing expansion."\n'  # noqa: E501
    "    },\n"
    "    {\n"
    '      "category": "Working capital",\n'
    '      "category_proposed": null,\n'
    '      "category_raw": "working capital",\n'
    '      "percentage": 40.0,\n'
    '      "amount_hkd_million": 2000.0,\n'
    '      "description": "General working capital and corporate purposes.",\n'
    '      "source_text": "Approximately 40% or HK$2,000 million will be used for working capital."\n'  # noqa: E501
    "    }\n"
    "  ]\n"
    "}\n"
    "\n"
    "The example uses FICTIONAL numbers to show format only. "
    "Do NOT copy example numbers into your output.\n"
)


# ── User prompt builder ───────────────────────────────────────────────────────

def _build_user_prompt(text: str) -> str:
    return f"Extract use-of-proceeds data from this HK IPO prospectus section:\n\n---\n{text}\n---"


# ── LLM call helpers ──────────────────────────────────────────────────────────

def _call_llm(text: str) -> dict[str, Any]:
    response = _openai_client.chat.completions.create(
        model=config.L2_TEXT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(text)},
        ],
        temperature=0.0,
        max_tokens=16384,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    if not raw.strip():
        raise ValueError("LLM returned empty response (possible context overflow)")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: extract first JSON object from the response
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"LLM response is not valid JSON: {raw[:200]!r}")


def _call_llm_with_prompt(user_content: str) -> dict[str, Any]:
    """Same as _call_llm but takes arbitrary user content (for correction retry)."""
    response = _openai_client.chat.completions.create(
        model=config.L2_TEXT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=16384,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    if not raw.strip():
        raise ValueError("LLM returned empty response (possible context overflow)")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"LLM response is not valid JSON: {raw[:200]!r}")


# ── Text cleaning ─────────────────────────────────────────────────────────────

_TABLE_LINE_RE = re.compile(r"^\s*\|")
_PAGE_MARKER_RE = re.compile(r"^[\s–—-]*\d{1,4}[\s–—-]*$")
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
    # Neutralise indented sub-bullet dashes: "   - " -> "     "
    result = _INDENTED_BULLET_RE.sub(r"\1  ", result)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


# ── Result helpers ────────────────────────────────────────────────────────────

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


def _parse_llm_output(data: dict[str, Any], company_file: str = "") -> list[dict[str, Any]]:
    uses: list[dict[str, Any]] = []
    for i, item in enumerate(data.get("uses", []), start=1):
        pct = _safe_float_or_none(item.get("percentage"))
        amt = _safe_float_or_none(item.get("amount_hkd_million"))
        if pct is None and amt is None:
            continue
        uses.append({
            "use_id": f"use_{i:03d}",
            "parent_id": None,
            "category": item.get("category") or None,
            "category_proposed": item.get("category_proposed") or None,
            "category_raw": str(item.get("category_raw") or ""),
            "amount_hkd_million": amt,
            "percentage": pct,
            "description": str(item.get("description") or ""),
            "source_text": str(item.get("source_text") or ""),
        })
    return uses


def _build_result(
    company_file: str,
    hk_ticker: str | None,
    document_date: str | None,
    total: float | None,
    uses: list[dict[str, Any]],
) -> dict[str, Any]:
    top_uses = [u for u in uses if u["parent_id"] is None]
    pct_sum = round(sum(u["percentage"] or 0 for u in top_uses), 1)
    return {
        "company_file": company_file,
        "section_source": Path(company_file).stem + ".json",
        "hk_ticker": hk_ticker,
        "document_date": document_date,
        "model_used": config.L2_TEXT_MODEL,
        "extraction_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "schema_version": SCHEMA_VERSION,
        "total_net_proceeds_hkd_million": total,
        "currency": "HKD",
        "uses": uses,
        "validation_preview": {
            "percentage_sum": pct_sum,
            "top_level_count": len(top_uses),
            "total_items_count": len(uses),
        },
    }


# ── Retry wrapper ─────────────────────────────────────────────────────────────

# Only retry on transient network / API errors; let programming errors through.
_RETRYABLE = (openai.APIError, httpx.HTTPError, TimeoutError, ConnectionError)


def _run_with_retry(fn: Any, max_retries: int = 5) -> Any:
    """Run fn(), retrying on transient errors with exponential backoff.

    Special handling for HTTP 429 (RateLimitError): if a Retry-After header
    is present, sleep exactly that many seconds instead of using backoff.
    For all other retryable errors, use exponential backoff (2^attempt seconds).
    max_retries defaults to 5.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except openai.RateLimitError as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                # Check for Retry-After header (present on some 429 responses)
                retry_after: float | None = None
                if hasattr(exc, "response") and exc.response is not None:
                    ra = exc.response.headers.get("Retry-After")
                    if ra is not None:
                        try:
                            retry_after = float(ra)
                        except (ValueError, TypeError):
                            retry_after = None
                wait = retry_after if retry_after is not None else 2 ** attempt
                print(
                    f"  [RETRY] 429 RateLimitError, attempt {attempt + 1}. "
                    f"Waiting {wait}s..."
                )
                time.sleep(wait)
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  [RETRY] attempt {attempt + 1} failed ({exc!r}). Waiting {wait}s...")
                time.sleep(wait)
        # Programming errors (ValueError, AttributeError, etc.) propagate immediately.
    raise last_exc  # type: ignore[misc]


# ── Core extraction ───────────────────────────────────────────────────────────

def extract_section(section_data: dict[str, Any]) -> dict[str, Any]:
    """Run LLM extraction on an L1 section dict; return the L2 output dict."""
    from hk_ipo.l3_validation import validate_record  # lazy to avoid circular import

    text = _clean_section_text(section_data["text"])
    company_file = section_data.get("company_file", "")
    hk_ticker = section_data.get("hk_ticker")
    document_date = section_data.get("document_date")

    if hk_ticker is None and document_date is None:
        print("  [WARN] hk_ticker/document_date missing -- re-run L1 to populate")

    # First LLM call
    raw = _run_with_retry(lambda: _call_llm(text))
    uses = _parse_llm_output(raw, company_file)
    total = _safe_float_or_none(raw.get("total_net_proceeds_hkd_million"))
    result = _build_result(company_file, hk_ticker, document_date, total, uses)

    # Schema validation (log warning but don't crash)
    try:
        validate_extraction(result)
    except ValidationError as exc:
        logger.warning("[WARN] Schema validation failed for %s: %s", company_file, exc)

    # Self-correction: run L3 checks; retry once if failed
    passed, errors, _ = validate_record(result)
    if not passed:
        correction_user = (
            _build_user_prompt(text)
            + "\n\nCORRECTION NEEDED -- your previous extraction had these validation errors:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\nPlease re-extract the data, fixing the issues above."
        )
        try:
            raw2 = _run_with_retry(lambda: _call_llm_with_prompt(correction_user))
            uses2 = _parse_llm_output(raw2, company_file)
            total2 = _safe_float_or_none(raw2.get("total_net_proceeds_hkd_million"))
            result = _build_result(company_file, hk_ticker, document_date, total2, uses2)
            try:
                validate_extraction(result)
            except ValidationError as exc:
                logger.warning(
                    "[WARN] Schema validation failed after correction for %s: %s",
                    company_file,
                    exc,
                )
            passed2, errors2, _ = validate_record(result)
            if not passed2:
                logger.warning(
                    "[WARN] Self-correction still failed for %s; marking needs_human_review",
                    company_file,
                )
                result["needs_human_review"] = True
                result["review_errors"] = errors2
        except Exception as exc:
            logger.warning("[WARN] Self-correction call failed for %s: %s", company_file, exc)
            result["needs_human_review"] = True

    return result


# ── File I/O ──────────────────────────────────────────────────────────────────

def process_single(
    section_file: Path,
    extracted_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Extract one section file; write output JSON.

    Parameters
    ----------
    section_file:   Path to the L1 section JSON.
    extracted_dir:  Directory to write the extracted output JSON.
    force:          If False (default), skip files whose output already exists.
    """
    extracted_dir.mkdir(parents=True, exist_ok=True)
    stem = section_file.stem
    out_path = extracted_dir / f"{stem}.json"
    err_path = extracted_dir / f"{stem}.error.json"

    # Resumability: skip if output already exists (unless --force).
    if not force and out_path.exists():
        print(f"[SKIP] already done: {out_path.name}")
        return json.loads(out_path.read_text(encoding="utf-8"))

    section_data = json.loads(section_file.read_text(encoding="utf-8"))

    print(f"\n-> {section_file.name}")
    try:
        result = extract_section(section_data)
    except Exception as exc:
        err_payload = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "section_file": str(section_file),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        err_path.write_text(
            json.dumps(err_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [ERROR] {exc}")
        print(f"  -> error written to: {err_path.name}")
        raise

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    vp = result["validation_preview"]
    print(f"  top-level   : {vp['top_level_count']} items")
    print(f"  total items : {vp['total_items_count']} (incl. sub-items)")
    print(f"  pct sum     : {vp['percentage_sum']}%")
    print(f"  total HK$M  : {result['total_net_proceeds_hkd_million']}")
    print(f"  -> saved to  : {out_path.name}")
    return result


def process_all(
    sections_dir: Path,
    extracted_dir: Path,
    max_workers: int = 6,
    force: bool = False,
) -> dict[str, Any]:
    """Extract all section JSON files in sections_dir using a thread pool.

    Each file's log output is captured into a string buffer and printed
    atomically to avoid interleaved output from concurrent workers.

    Parameters
    ----------
    sections_dir:   Directory containing L1 section JSON files.
    extracted_dir:  Directory to write extracted output JSON files.
    max_workers:    Thread pool size (default 6).
    force:          If True, re-process files even if output already exists.

    Returns
    -------
    Summary dict: {"succeeded": int, "failed": int, "skipped": int, "total": int}
    """
    jsons = sorted(sections_dir.glob("*.json"))
    if not jsons:
        print(f"[WARN] No JSON files found in {sections_dir}")
        return {"succeeded": 0, "failed": 0, "skipped": 0, "total": 0}

    succeeded = failed = skipped = 0

    def _process_one(jf: Path) -> tuple[str, bool, str]:
        """Process one file; return (filename, ok, log_output)."""
        buf = io.StringIO()
        out_path = extracted_dir / f"{jf.stem}.json"
        if not force and out_path.exists():
            buf.write(f"[SKIP] already done: {out_path.name}\n")
            return jf.name, True, buf.getvalue()

        buf.write(f"\n-> {jf.name}\n")
        try:
            section_data = json.loads(jf.read_text(encoding="utf-8"))
            result = extract_section(section_data)
            extracted_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            vp = result["validation_preview"]
            buf.write(f"  top-level   : {vp['top_level_count']} items\n")
            buf.write(f"  total items : {vp['total_items_count']} (incl. sub-items)\n")
            buf.write(f"  pct sum     : {vp['percentage_sum']}%\n")
            buf.write(f"  total HK$M  : {result['total_net_proceeds_hkd_million']}\n")
            buf.write(f"  -> saved to  : {out_path.name}\n")
            return jf.name, True, buf.getvalue()
        except Exception as exc:
            buf.write(f"  [ERROR] {exc}\n")
            return jf.name, False, buf.getvalue()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, jf): jf for jf in jsons}
        for future in concurrent.futures.as_completed(futures):
            filename, ok, log_output = future.result()
            print(log_output, end="")
            out_path = extracted_dir / f"{Path(filename).stem}.json"
            if not force and out_path.exists() and "[SKIP]" in log_output:
                skipped += 1
            elif ok:
                succeeded += 1
            else:
                failed += 1

    print(
        f"\nL2 complete: {succeeded} succeeded, {failed} failed, "
        f"{skipped} skipped (of {len(jsons)} total)"
    )
    return {"succeeded": succeeded, "failed": failed, "skipped": skipped, "total": len(jsons)}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="L2: structure Use of Proceeds via LLM (direct OpenAI SDK + OpenRouter)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--single", metavar="FILENAME",
                       help="Process one file from data/sections/ by name")
    group.add_argument("--all", action="store_true",
                       help="Process all files in data/sections/")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-process files even if output already exists",
    )
    parser.add_argument(
        "--workers", type=int, default=6, metavar="N",
        help="Number of parallel worker threads for --all (default 6)",
    )
    args = parser.parse_args()

    from hk_ipo.config import EXTRACTED_DIR, SECTIONS_DIR

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    if args.single:
        sf = SECTIONS_DIR / args.single
        if not sf.exists():
            import sys
            print(f"[ERROR] Not found: {sf}")
            sys.exit(1)
        process_single(sf, EXTRACTED_DIR, force=args.force)
    elif args.all:
        process_all(SECTIONS_DIR, EXTRACTED_DIR, max_workers=args.workers, force=args.force)
    else:
        parser.error(
            "Specify --single <filename.json> or --all. "
            "Explicit choice required to avoid unintended API calls."
        )
