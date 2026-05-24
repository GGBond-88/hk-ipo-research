# Task 013: L5 enrichment — timeline tool

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L5 enrichment tool classifies each use item's deployment timeline into a 5-bucket scheme.
- **Tech Stack:** Python 3.10+, pytest.

## Task Objective

Implement `timeline.py`: classify each use item as `0-12m`, `12-24m`, `24-36m`, `36m+`, or `unspecified` based on textual mentions of deployment horizons. Rules-based (no LLM). Follow TDD.

This is Task 13 of 27.

---

**Files:**
- Create: `src/hk_ipo/enrichments/timeline.py`
- Create: `tests/test_enrichments_timeline.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrichments_timeline.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/timeline.py."""
from __future__ import annotations

from pathlib import Path


def test_dimension_and_version():
    from hk_ipo.enrichments.timeline import DIMENSION, VERSION
    assert DIMENSION == "timeline"
    assert isinstance(VERSION, int)


def test_short_term_0_12m():
    from hk_ipo.enrichments.timeline import classify_timeline
    item = {
        "description": "We expect to complete within 12 months from listing.",
        "source_text": "Expected completion within 12 months.",
    }
    assert classify_timeline(item) == "0-12m"


def test_medium_term_12_24m():
    from hk_ipo.enrichments.timeline import classify_timeline
    item = {
        "description": "Deployment expected over the next 18 months.",
        "source_text": "Over the next 18 to 24 months.",
    }
    assert classify_timeline(item) == "12-24m"


def test_long_term_24_36m():
    from hk_ipo.enrichments.timeline import classify_timeline
    item = {
        "description": "Three-year deployment plan for the new facility.",
        "source_text": "Enterprise expansion over 3 years.",
    }
    assert classify_timeline(item) == "24-36m"


def test_very_long_36m_plus():
    from hk_ipo.enrichments.timeline import classify_timeline
    item = {
        "description": "Long-term investment to be deployed over 5 years.",
        "source_text": "Deployment over the next 5 years.",
    }
    assert classify_timeline(item) == "36m+"


def test_unspecified_no_timeline():
    from hk_ipo.enrichments.timeline import classify_timeline
    item = {
        "description": "General purposes.",
        "source_text": "",
    }
    assert classify_timeline(item) == "unspecified"
```

- [ ] **Step 2: Run tests; verify FAIL**

Run: `python -m pytest tests/test_enrichments_timeline.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/hk_ipo/enrichments/timeline.py`**

```python
"""L5 enrichment: deployment timeline (0-12m / 12-24m / 24-36m / 36m+ / unspecified).

Rules-based: scans text for month/year horizons and phrases like "near-term,"
"medium-term," "long-term."
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

DIMENSION = "timeline"
VERSION = 1

_SHORT_TERM_RE = re.compile(
    r"\b(12\s*month|within\s*(a|1)\s*year|first\s*year"
    r"|near[\s-]term|short[\s-]term|immediate|6\s*month"
    r"|12\s*mo)",
    re.IGNORECASE,
)
_MEDIUM_TERM_RE = re.compile(
    r"\b(18\s*month|24\s*month|2\s*year|two\s*year"
    r"|medium[\s-]term|mid[\s-]term|1[3-9]\s*month"
    r"|2[0-4]\s*month)",
    re.IGNORECASE,
)
_LONG_TERM_RE = re.compile(
    r"\b(3\s*year|three\s*year|36\s*month|2[5-9]\s*month"
    r"|3[0-6]\s*month|long[\s-]term)",
    re.IGNORECASE,
)
_VERY_LONG_RE = re.compile(
    r"\b(4\s*year|four\s*year|5\s*year|five\s*year"
    r"|[4-9]\s*year|\d{2}\s*year|37\+?\s*month"
    r"|very\s*long|extended\s*(period|horizon|timeline))",
    re.IGNORECASE,
)


def classify_timeline(item: dict[str, Any]) -> str:
    text = " ".join([
        str(item.get("description", "")),
        str(item.get("source_text", "")),
    ])
    if _SHORT_TERM_RE.search(text):
        return "0-12m"
    if _MEDIUM_TERM_RE.search(text):
        return "12-24m"
    if _LONG_TERM_RE.search(text):
        return "24-36m"
    if _VERY_LONG_RE.search(text):
        return "36m+"
    return "unspecified"


def run(
    categorized_dir: Path, enriched_dir: Path,
    ticker: str | None = None, all_files: bool = False, force: bool = False,
) -> dict[str, Any] | None:
    enriched_dir.mkdir(parents=True, exist_ok=True)

    def _do(record: dict[str, Any]) -> dict[str, Any]:
        existing = record.get("enrichments", {}).get(DIMENSION)
        if not force and existing and existing.get("version") == VERSION:
            return existing
        by_use_id: dict[str, str] = {}
        for u in record.get("uses", []):
            by_use_id[u["use_id"]] = classify_timeline(u)
        block = {"version": VERSION, "by_use_id": by_use_id}
        merge_enrichment_block(record, DIMENSION, block)
        tick = record.get("hk_ticker", "unknown")
        save_enriched(record, enriched_dir, tick)
        print(f"[timeline] {tick}: {len(by_use_id)} uses tagged")
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
    parser = argparse.ArgumentParser(description="L5 timeline enrichment")
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

Run: `python -m pytest tests/test_enrichments_timeline.py -v`

Expected: All tests pass.

- [ ] **Step 5: Run full suite (except e2e)**

Run: `python -m pytest -q --ignore=tests/e2e`
