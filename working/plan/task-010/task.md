# Task 010: L5 enrichment — country tool

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L5 enrichment tools are modular. The country tool scans use-item text for ISO 2-letter country mentions and tags each item with a list of country codes.
- **Tech Stack:** Python 3.10+, pytest.

## Task Objective

Implement the `country.py` enrichment tool: scan each use item's text for country mentions, normalize to ISO 2-letter codes, and write the `enrichments.country` block. Follow TDD.

This is Task 10 of 27.

---

**Files:**
- Create: `src/hk_ipo/enrichments/country.py`
- Create: `tests/test_enrichments_country.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrichments_country.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/country.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_country_dimension_and_version():
    from hk_ipo.enrichments.country import DIMENSION, VERSION
    assert DIMENSION == "country"
    assert isinstance(VERSION, int)
    assert VERSION >= 1


def test_extract_countries_singapore():
    from hk_ipo.enrichments.country import extract_countries
    text = "We plan to expand into Singapore and set up a regional office."
    codes = extract_countries(text)
    assert "SG" in codes


def test_extract_countries_multiple():
    from hk_ipo.enrichments.country import extract_countries
    text = (
        "We will target the United States, Japan, and Vietnam "
        "for our overseas expansion."
    )
    codes = extract_countries(text)
    assert "US" in codes
    assert "JP" in codes
    assert "VN" in codes


def test_extract_countries_no_match():
    from hk_ipo.enrichments.country import extract_countries
    text = "We will expand our Hong Kong office."
    codes = extract_countries(text)
    assert codes == []


def test_country_run_integrates(tmp_path: Path):
    from hk_ipo.enrichments.country import run as country_run
    from hk_ipo.enrichments.base import save_enriched

    cat = tmp_path / "categorized"; cat.mkdir()
    enr = tmp_path / "enriched"; enr.mkdir()
    record = {
        "hk_ticker": "01234", "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {"use_id": "use_001", "description": "Expand into Singapore and Japan.",
             "category_raw": "overseas expansion", "percentage": 100.0,
             "source_text": "We plan to expand into Singapore and Japan."}
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    country_run(cat, enr, ticker="01234")
    loaded = json.loads((enr / "01234.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    assert block["version"] >= 1
    assert "SG" in block["countries"] or "SG" in block["by_use_id"]["use_001"]


def test_country_idempotent(tmp_path: Path):
    from hk_ipo.enrichments.country import run as country_run
    from hk_ipo.enrichments.base import save_enriched

    cat = tmp_path / "categorized"; cat.mkdir()
    enr = tmp_path / "enriched"; enr.mkdir()
    record = {
        "hk_ticker": "01234", "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {"use_id": "use_001", "description": "R&D", "category_raw": "R&D",
             "percentage": 100.0, "source_text": "R&D."}
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    first = country_run(cat, enr, ticker="01234")
    second = country_run(cat, enr, ticker="01234")
    assert first == second
```

- [ ] **Step 2: Run tests; verify FAIL**

Run: `python -m pytest tests/test_enrichments_country.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/hk_ipo/enrichments/country.py`**

```python
"""L5 enrichment: country mentions (ISO 2-letter codes).

Scans each use item's text fields for country/region mentions and normalizes
them to ISO 3166-1 alpha-2 codes.
"""
from __future__ import annotations

import argparse
import json as _json
import re
import sys
from pathlib import Path
from typing import Any

from hk_ipo.enrichments.base import (
    load_enriched_or_categorized,
    merge_enrichment_block,
    save_enriched,
)

DIMENSION = "country"
VERSION = 1

# ── Country name → ISO 3166-1 alpha-2 ─────────────────────────────────────

_COUNTRY_MAP: dict[str, str] = {
    "united states": "US", "america": "US", "usa": "US",
    "china": "CN", "mainland china": "CN", "prc": "CN",
    "japan": "JP", "korea": "KR", "south korea": "KR",
    "singapore": "SG", "vietnam": "VN", "thailand": "TH",
    "indonesia": "ID", "malaysia": "MY", "philippines": "PH",
    "india": "IN", "australia": "AU", "new zealand": "NZ",
    "united kingdom": "GB", "uk": "GB", "england": "GB",
    "germany": "DE", "france": "FR", "canada": "CA",
    "italy": "IT", "spain": "ES", "netherlands": "NL",
    "switzerland": "CH", "brazil": "BR", "mexico": "MX",
    "taiwan": "TW", "russia": "RU", "uae": "AE",
    "saudi arabia": "SA", "south africa": "ZA",
    "turkey": "TR", "poland": "PL", "sweden": "SE",
    "norway": "NO", "denmark": "DK", "finland": "FI",
    "belgium": "BE", "austria": "AT", "ireland": "IE",
    "portugal": "PT", "egypt": "EG", "israel": "IL",
    "pakistan": "PK", "bangladesh": "BD", "myanmar": "MM",
    "cambodia": "KH", "laos": "LA", "brunei": "BN",
    "hong kong": "HK",  # kept for completeness; geo tool handles HK specially
}


def extract_countries(text: str) -> list[str]:
    """Extract ISO 2-letter country codes from text. No duplicates."""
    text_lower = text.lower()
    found: set[str] = set()
    for name, code in sorted(_COUNTRY_MAP.items(), key=lambda x: -len(x[0])):
        if name in text_lower and code not in found:
            found.add(code)
    return sorted(found)


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    enriched_dir.mkdir(parents=True, exist_ok=True)

    def _do(record: dict[str, Any]) -> dict[str, Any]:
        existing = record.get("enrichments", {}).get(DIMENSION)
        if not force and existing and existing.get("version") == VERSION:
            return existing

        all_countries: set[str] = set()
        by_use_id: dict[str, list[str]] = {}
        for u in record.get("uses", []):
            combined = " ".join([str(u.get("description", "")),
                                 str(u.get("category_raw", "")),
                                 str(u.get("source_text", ""))])
            codes = extract_countries(combined)
            by_use_id[u["use_id"]] = codes
            all_countries.update(codes)

        tick = record.get("hk_ticker", "unknown")
        block = {
            "version": VERSION,
            "countries": sorted(all_countries),
            "by_use_id": by_use_id,
        }
        merge_enrichment_block(record, DIMENSION, block)
        save_enriched(record, enriched_dir, tick)
        print(f"[country] {tick}: {len(all_countries)} countries")
        return block

    if ticker:
        record = load_enriched_or_categorized(enriched_dir if (enriched_dir / f"{ticker}.json").exists() else categorized_dir, ticker)
        return _do(record)
    if all_files:
        jsons = sorted((enriched_dir if enriched_dir.exists() else categorized_dir).glob("*.json"))
        for jf in jsons:
            record = _json.loads(jf.read_text(encoding="utf-8"))
            _do(record)
        return None
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L5 country enrichment")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("categorized", nargs="?")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    from hk_ipo.config import CATEGORIZED_DIR, DATA_DIR
    ENRICHED = DATA_DIR / "enriched"

    if args.all:
        run(CATEGORIZED_DIR, ENRICHED, all_files=True, force=args.force)
    else:
        sf = Path(args.categorized)
        if not sf.exists():
            print(f"[ERROR] Not found: {sf}", file=sys.stderr)
            sys.exit(1)
        record = _json.loads(sf.read_text(encoding="utf-8"))
        ticker = record.get("hk_ticker") or sf.stem
        run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force)
```

- [ ] **Step 4: Run tests; verify PASS**

Run: `python -m pytest tests/test_enrichments_country.py -v`

Expected: All tests pass.

- [ ] **Step 5: Run full suite (except e2e); verify no regressions**

Run: `python -m pytest -q --ignore=tests/e2e`

Expected: All tests pass.
