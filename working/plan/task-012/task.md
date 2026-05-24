# Task 012: L5 enrichment — specificity tool

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L5 enrichment tools are modular. The specificity tool classifies each use item as `specific`, `general`, or `vague` based on description detail.
- **Tech Stack:** Python 3.10+, pytest.

## Task Objective

Implement `specificity.py`: a rules-based classifier that scores each use item's description and source_text for specificity. Follow TDD.

This is Task 12 of 27.

---

**Files:**
- Create: `src/hk_ipo/enrichments/specificity.py`
- Create: `tests/test_enrichments_specificity.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrichments_specificity.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/specificity.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_dimension_and_version():
    from hk_ipo.enrichments.specificity import DIMENSION, VERSION
    assert DIMENSION == "specificity"
    assert isinstance(VERSION, int)


def test_specific_has_concrete_details():
    from hk_ipo.enrichments.specificity import classify_specificity
    item = {
        "description": "Construct a 200,000 sq ft semiconductor fabrication "
                       "plant in Shenzhen with 5 production lines by Q4 2025.",
        "source_text": "We will invest HK$500 million to construct a 200,000 sq ft...",
    }
    assert classify_specificity(item) == "specific"


def test_general_has_non_concrete_description():
    from hk_ipo.enrichments.specificity import classify_specificity
    item = {
        "description": "For general working capital purposes.",
        "source_text": "Approximately 10% will be used for general working capital.",
    }
    assert classify_specificity(item) == "general"


def test_vague_is_very_unspecific():
    from hk_ipo.enrichments.specificity import classify_specificity
    item = {
        "description": "",
        "source_text": "",
    }
    assert classify_specificity(item) == "vague"


def test_run_integrates(tmp_path: Path):
    from hk_ipo.enrichments.specificity import run as spec_run
    from hk_ipo.enrichments.base import save_enriched

    cat = tmp_path / "categorized"; cat.mkdir()
    enr = tmp_path / "enriched"; enr.mkdir()
    record = {
        "hk_ticker": "01234", "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {"use_id": "use_001", "description": "Build a specific factory at a specific address.",
             "category_raw": "factory", "percentage": 100.0,
             "source_text": "We will build a factory at 123 Main Street."}
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    spec_run(cat, enr, ticker="01234")
    loaded = json.loads((enr / "01234.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["specificity"]
    assert block["version"] >= 1
    assert block["by_use_id"]["use_001"] in ("specific", "general", "vague")
```

- [ ] **Step 2: Run tests; verify FAIL**

Run: `python -m pytest tests/test_enrichments_specificity.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/hk_ipo/enrichments/specificity.py`**

```python
"""L5 enrichment: purpose specificity (specific / general / vague).

Rules-based classifier: scores each use item on presence of concrete details
(numbers, dates, locations, named entities) in description + source_text.
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

DIMENSION = "specificity"
VERSION = 1

# Indicators of specificity: numeric ranges, dates, proper nouns, compound details
_SPECIFICITY_MARKERS = re.compile(
    r"(\b\d{4}\b|\bQ[1-4]\b|\bsq[.]?\s*ft\b|\bsquare\s*meters?\b"
    r"|\bfloor\s*\d|\bfloors\b|\bphase\b|\bstage\b"
    r"|\baddress\b|\blocated\sin\b|\bunit\s*\d|\block-up\b"
    r"|independent\s*third|proprietary|patent|certification"
    r"|\btimeline\b|\bmilestone\b|\btarget\b|\bdeadline\b)",
    re.IGNORECASE,
)
_GENERAL_MARKERS = re.compile(
    r"(\bgeneral\b|\bworking\s*capital\b|\bcorporate\s*purposes?\b"
    r"|\bunspecified\b|\bdiscretionary\b|\bcontingen|\breserves?\b)",
    re.IGNORECASE,
)


def classify_specificity(item: dict[str, Any]) -> str:
    text = " ".join([
        str(item.get("description", "")),
        str(item.get("source_text", "")),
    ]).strip()
    if not text or len(text) < 10:
        return "vague"
    n_specific = len(_SPECIFICITY_MARKERS.findall(text))
    n_general = len(_GENERAL_MARKERS.findall(text))
    if n_specific >= 2:
        return "specific"
    if n_specific >= 1 and n_general == 0:
        return "specific"
    if n_general >= 1:
        return "general"
    # Heuristic: longer text usually more specific
    if len(text) > 300:
        return "specific"
    if len(text) > 100:
        return "general"
    return "vague"


def run(
    categorized_dir: Path, enriched_dir: Path,
    ticker: str | None = None, all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    enriched_dir.mkdir(parents=True, exist_ok=True)

    def _do(record: dict[str, Any]) -> dict[str, Any]:
        existing = record.get("enrichments", {}).get(DIMENSION)
        if not force and existing and existing.get("version") == VERSION:
            return existing
        by_use_id: dict[str, str] = {}
        for u in record.get("uses", []):
            by_use_id[u["use_id"]] = classify_specificity(u)
        block = {"version": VERSION, "by_use_id": by_use_id}
        merge_enrichment_block(record, DIMENSION, block)
        tick = record.get("hk_ticker", "unknown")
        save_enriched(record, enriched_dir, tick)
        print(f"[specificity] {tick}: {len(by_use_id)} uses tagged")
        return block

    if ticker:
        record = load_enriched_or_categorized(categorized_dir, ticker)
        return _do(record)
    if all_files:
        jsons = sorted((enriched_dir if enriched_dir.exists() else categorized_dir).glob("*.json"))
        for jf in jsons:
            record = _json.loads(jf.read_text(encoding="utf-8"))
            _do(record)
        return None
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L5 specificity enrichment")
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

Run: `python -m pytest tests/test_enrichments_specificity.py -v`

Expected: All tests pass.

- [ ] **Step 5: Run full suite (except e2e); verify no regressions**

Run: `python -m pytest -q --ignore=tests/e2e`

Expected: All tests pass.
