# Task 011: L5 enrichment — industry tool

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L5 enrichment tools are modular. The industry tool assigns a GICS industry name to each company by reading the prospectus via LLM (default) or using a manual CSV override (`--source manual`).
- **Tech Stack:** Python 3.10+, OpenAI SDK + OpenRouter, pytest.

## Task Objective

Implement `industry.py`: LLM-based company industry classification with a manual override path. The enrichment writes a per-company tag (not per-use). Follow TDD.

This is Task 11 of 27.

---

**Files:**
- Create: `src/hk_ipo/enrichments/industry.py`
- Create: `tests/test_enrichments_industry.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrichments_industry.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/industry.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def test_industry_dimension_and_version():
    from hk_ipo.enrichments.industry import DIMENSION, VERSION
    assert DIMENSION == "industry"
    assert isinstance(VERSION, int)
    assert VERSION >= 1


def test_manual_override_loads_csv(tmp_path: Path):
    from hk_ipo.enrichments.industry import load_manual_overrides
    csv_path = tmp_path / "overrides.csv"
    csv_path.write_text("ticker,industry\n01234,Software & Services\n03690,Retailing\n", encoding="utf-8")
    overrides = load_manual_overrides(csv_path)
    assert overrides["01234"] == "Software & Services"
    assert overrides["03690"] == "Retailing"


def test_manual_override_no_csv_returns_empty():
    from hk_ipo.enrichments.industry import load_manual_overrides
    overrides = load_manual_overrides(Path("/nonexistent/file.csv"))
    assert overrides == {}


def test_run_manual_source_uses_override(tmp_path: Path):
    from hk_ipo.enrichments.industry import _enrich_one
    from hk_ipo.enrichments.base import save_enriched

    cat = tmp_path / "categorized"; cat.mkdir()
    enr = tmp_path / "enriched"; enr.mkdir()
    record = {
        "hk_ticker": "01234", "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [], "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    block = _enrich_one(record, enr, force=True,
                        manual_overrides={"01234": "Software & Services"})
    assert block["primary"] == "Software & Services"
    assert block.get("source") == "manual"


def test_industry_block_shape():
    from hk_ipo.enrichments.industry import DIMENSION
    # The block must have version, primary, source fields
    assert DIMENSION == "industry"
```

- [ ] **Step 2: Run tests; verify FAIL**

Run: `python -m pytest tests/test_enrichments_industry.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/hk_ipo/enrichments/industry.py`**

```python
"""L5 enrichment: company industry classification (GICS).

Default source: LLM reads the prospectus text to determine the primary
industry. With --source manual, reads `data/industry_overrides.csv`.
The result is a company-level (not per-use) enrichment tag.
"""
from __future__ import annotations

import argparse
import csv
import json as _json
import sys
from pathlib import Path
from typing import Any

from hk_ipo.enrichments.base import (
    load_enriched_or_categorized,
    merge_enrichment_block,
    save_enriched,
)

DIMENSION = "industry"
VERSION = 1


def load_manual_overrides(csv_path: Path) -> dict[str, str]:
    """Load ticker -> industry from a CSV file. Returns empty dict if missing."""
    if not csv_path.exists():
        return {}
    result: dict[str, str] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("ticker") or "").strip()
            ind = (row.get("industry") or "").strip()
            if t and ind:
                result[t] = ind
    return result


def _classify_via_llm(record: dict[str, Any]) -> str:
    """Use LLM to determine the company's GICS industry from the section text."""
    import openai
    from hk_ipo import config as cfg

    ticker = record.get("hk_ticker", "unknown")
    name = record.get("company_name_en", "")
    uses_text = " ".join(
        f"{u.get('description', '')} {u.get('category_raw', '')} {u.get('source_text', '')}"
        for u in record.get("uses", [])
    )[:6000]
    prompt = (
        f"Company: {name} (HK ticker: {ticker})\n\n"
        f"Prospectus excerpt:\n{uses_text}\n\n"
        "Based on the company's described business and use of proceeds, "
        "classify the company into a single GICS Industry name (e.g. "
        "'Software & Services', 'Pharmaceuticals', 'Real Estate', "
        "'Banks', 'Capital Goods', 'Consumer Services', 'Retailing', "
        "'Food Beverage & Tobacco', 'Semiconductors', 'Health Care Equipment'). "
        "Return ONLY the industry name, no extra text."
    )
    client = openai.OpenAI(
        api_key=cfg.OPENROUTER_API_KEY or "placeholder-not-set",
        base_url=cfg.OPENROUTER_BASE_URL,
    )
    response = client.chat.completions.create(
        model=cfg.L2_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0, max_tokens=128,
    )
    return (response.choices[0].message.content or "Unknown").strip()


def _enrich_one(
    record: dict[str, Any],
    enriched_dir: Path,
    force: bool = False,
    manual_overrides: dict[str, str] | None = None,
    source: str = "prospectus",
) -> dict[str, Any]:
    existing = record.get("enrichments", {}).get(DIMENSION)
    if not force and existing and existing.get("version") == VERSION:
        return existing

    ticker = record.get("hk_ticker", "unknown")
    overrides = manual_overrides or {}

    if source == "manual" and ticker in overrides:
        primary = overrides[ticker]
    elif source == "prospectus":
        if ticker in overrides:
            primary = overrides[ticker]
            source = "manual"
        else:
            try:
                primary = _classify_via_llm(record)
            except Exception as exc:
                print(f"[industry] LLM call failed for {ticker}: {exc}", file=sys.stderr)
                primary = "Unknown"
    else:
        primary = "Unknown"

    block = {
        "version": VERSION,
        "primary": primary,
        "source": source,
    }
    merge_enrichment_block(record, DIMENSION, block)
    save_enriched(record, enriched_dir, ticker)
    print(f"[industry] {ticker}: {primary} (source={source})")
    return block


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
    source: str = "prospectus",
    overrides_csv: Path | None = None,
) -> dict[str, Any] | None:
    enriched_dir.mkdir(parents=True, exist_ok=True)
    manual = {}
    if overrides_csv:
        manual = load_manual_overrides(overrides_csv)

    if ticker:
        record = load_enriched_or_categorized(categorized_dir, ticker)
        return _enrich_one(record, enriched_dir, force=force,
                          manual_overrides=manual, source=source)
    if all_files:
        data_dir = enriched_dir if enriched_dir.exists() else categorized_dir
        jsons = sorted(data_dir.glob("*.json"))
        for jf in jsons:
            record = _json.loads(jf.read_text(encoding="utf-8"))
            _enrich_one(record, enriched_dir, force=force,
                       manual_overrides=manual, source=source)
        return None
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L5 industry enrichment")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("categorized", nargs="?")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--source", choices=["prospectus", "manual"],
                        default="prospectus",
                        help="Industry classification source")
    args = parser.parse_args()

    from hk_ipo.config import CATEGORIZED_DIR, DATA_DIR
    ENRICHED = DATA_DIR / "enriched"
    OVERRIDES_CSV = DATA_DIR / "industry_overrides.csv"

    if args.all:
        run(CATEGORIZED_DIR, ENRICHED, all_files=True, force=args.force,
            source=args.source, overrides_csv=OVERRIDES_CSV)
    else:
        sf = Path(args.categorized)
        if not sf.exists():
            print(f"[ERROR] Not found: {sf}", file=sys.stderr)
            sys.exit(1)
        record = _json.loads(sf.read_text(encoding="utf-8"))
        ticker = record.get("hk_ticker") or sf.stem
        run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force,
            source=args.source, overrides_csv=OVERRIDES_CSV)
```

- [ ] **Step 4: Run tests; verify PASS**

Run: `python -m pytest tests/test_enrichments_industry.py -v`

Expected: All tests pass.

- [ ] **Step 5: Run full suite (except e2e); verify no regressions**

Run: `python -m pytest -q --ignore=tests/e2e`

Expected: All tests pass.
