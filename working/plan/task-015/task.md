# Task 015: L5 enrichment — esg_tag tool

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L5 enrichment tool tags use items with optional ESG labels (`green`, `social`, `governance`).
- **Tech Stack:** Python 3.10+, pytest.

## Task Objective

Implement `esg_tag.py`: tag use items that qualify as green, social, or governance. Optional -- many items will have no ESG tag. Rules-based keyword matching. Follow TDD.

This is Task 15 of 27.

---

**Files:**
- Create: `src/hk_ipo/enrichments/esg_tag.py`
- Create: `tests/test_enrichments_esg_tag.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrichments_esg_tag.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/esg_tag.py."""
from __future__ import annotations


def test_dimension_and_version():
    from hk_ipo.enrichments.esg_tag import DIMENSION, VERSION
    assert DIMENSION == "esg_tag"
    assert isinstance(VERSION, int)


def test_green_renewable_energy():
    from hk_ipo.enrichments.esg_tag import classify_esg
    item = {
        "description": "Invest in solar panel manufacturing and wind energy projects.",
        "category_raw": "renewable energy investment",
        "source_text": "We will invest in solar panel and wind energy.",
    }
    tags = classify_esg(item)
    assert "green" in tags


def test_social_healthcare():
    from hk_ipo.enrichments.esg_tag import classify_esg
    item = {
        "description": "Build affordable healthcare clinics in rural areas.",
        "category_raw": "healthcare expansion",
        "source_text": "Expanding affordable healthcare access.",
    }
    tags = classify_esg(item)
    assert "social" in tags


def test_governance_compliance():
    from hk_ipo.enrichments.esg_tag import classify_esg
    item = {
        "description": "Implement company-wide compliance and risk management systems.",
        "category_raw": "compliance systems",
        "source_text": "Strengthening compliance and governance frameworks.",
    }
    tags = classify_esg(item)
    assert "governance" in tags


def test_multiple_tags():
    from hk_ipo.enrichments.esg_tag import classify_esg
    item = {
        "description": "Green affordable housing project with governance oversight.",
        "category_raw": "sustainable affordable housing",
        "source_text": "Building green affordable housing with strong governance.",
    }
    tags = classify_esg(item)
    assert "green" in tags
    assert "social" in tags


def test_no_esg_tag():
    from hk_ipo.enrichments.esg_tag import classify_esg
    item = {
        "description": "General corporate purposes.",
        "category_raw": "general corporate purposes",
        "source_text": "For general corporate purposes.",
    }
    tags = classify_esg(item)
    assert tags == []
```

- [ ] **Step 2: Run; verify FAIL**

Run: `python -m pytest tests/test_enrichments_esg_tag.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/hk_ipo/enrichments/esg_tag.py`**

```python
"""L5 enrichment: ESG / sustainability tags (green / social / governance).

Optional per-use tags. An item may have 0, 1, 2, or all 3 tags.
Rules-based keyword matching.
"""
from __future__ import annotations

import argparse
import json as _json
import re
import sys
from pathlib import Path
from typing import Any

from hk_ipo.enrichments.base import (
    load_enriched_or_categorized, merge_enrichment_block, save_enriched,
)

DIMENSION = "esg_tag"
VERSION = 1

_GREEN_KW = re.compile(
    r"\b(green|renewable|solar|wind|clean\s*energy|carbon|carbon[\s-]neutral"
    r"|net[\s-]zero|emission|climate|sustainable|sustainability|environment"
    r"|recycling|waste[\s-]water|biodiversity|conservation|electric\s*vehicle"
    r"|ev\s|energy[\s-]efficien|pollution|eco[\s-]friendly|organic"
    r"|low[\s-]carbon|decarboni)\b",
    re.IGNORECASE,
)

_SOCIAL_KW = re.compile(
    r"\b(social|affordable\s*housing|healthcare|education|community"
    r"|public\s*health|inclusion|diversity|equity|access\s*to\s"
    r"|patient|hospital|clinic|school|university|vocational|training"
    r"|micro[\s-]finance|financial\s*inclusion|underserved|rural"
    r"|poverty|charit|philanthrop|welfare)\b",
    re.IGNORECASE,
)

_GOVERNANCE_KW = re.compile(
    r"\b(governance|compliance|regulatory|transparency|anti[\s-]corruption"
    r"|anti[\s-]bribery|ethics|accountability|audit|risk[\s-]management"
    r"|internal\s*control|shareholder\s*right|data\s*privacy|cybersecurity"
    r"|whistleblower)\b",
    re.IGNORECASE,
)


def classify_esg(item: dict[str, Any]) -> list[str]:
    text = " ".join([
        str(item.get("description", "")),
        str(item.get("category_raw", "")),
        str(item.get("source_text", "")),
    ])
    tags: list[str] = []
    if _GREEN_KW.search(text):
        tags.append("green")
    if _SOCIAL_KW.search(text):
        tags.append("social")
    if _GOVERNANCE_KW.search(text):
        tags.append("governance")
    return tags


def run(
    categorized_dir: Path, enriched_dir: Path,
    ticker: str | None = None, all_files: bool = False, force: bool = False,
) -> dict[str, Any] | None:
    enriched_dir.mkdir(parents=True, exist_ok=True)

    def _do(record: dict[str, Any]) -> dict[str, Any]:
        existing = record.get("enrichments", {}).get(DIMENSION)
        if not force and existing and existing.get("version") == VERSION:
            return existing
        by_use_id: dict[str, list[str]] = {}
        any_esg = False
        for u in record.get("uses", []):
            tags = classify_esg(u)
            by_use_id[u["use_id"]] = tags
            if tags:
                any_esg = True
        block = {"version": VERSION, "any_esg": any_esg, "by_use_id": by_use_id}
        merge_enrichment_block(record, DIMENSION, block)
        tick = record.get("hk_ticker", "unknown")
        save_enriched(record, enriched_dir, tick)
        esg_count = sum(1 for v in by_use_id.values() if v)
        print(f"[esg_tag] {tick}: {esg_count}/{len(by_use_id)} uses have ESG tags")
        return block

    if ticker:
        record = load_enriched_or_categorized(categorized_dir, ticker)
        return _do(record)
    if all_files:
        jsons = sorted((enriched_dir if enriched_dir.exists() else categorized_dir).glob("*.json"))
        for jf in jsons:
            _do(_json.loads(jf.read_text(encoding="utf-8")))
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L5 ESG tag enrichment")
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
            print(f"[ERROR] Not found: {sf}", file=sys.stderr); sys.exit(1)
        record = _json.loads(sf.read_text(encoding="utf-8"))
        ticker = record.get("hk_ticker") or sf.stem
        run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force)
```

- [ ] **Step 4: Run tests; verify PASS**

Run: `python -m pytest tests/test_enrichments_esg_tag.py -v`

- [ ] **Step 5: Run full suite (except e2e)**

Run: `python -m pytest -q --ignore=tests/e2e`
