# Task 016: L5 enrichment — commitment tool

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L5 enrichment tool classifies each use item as `committed` or `discretionary` based on language strength.
- **Tech Stack:** Python 3.10+, pytest.

## Task Objective

Implement `commitment.py`: classify each use item's commitment strength. Binding/contractual language (e.g., "has agreed to," "committed," "obligated") maps to `committed`; tentative/optional language ("may," "could," "subject to") maps to `discretionary`. Rules-based. Follow TDD.

This is Task 16 of 27.

---

**Files:**
- Create: `src/hk_ipo/enrichments/commitment.py`
- Create: `tests/test_enrichments_commitment.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrichments_commitment.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/commitment.py."""
from __future__ import annotations


def test_dimension_and_version():
    from hk_ipo.enrichments.commitment import DIMENSION, VERSION
    assert DIMENSION == "commitment"
    assert isinstance(VERSION, int)


def test_committed_firm_language():
    from hk_ipo.enrichments.commitment import classify_commitment
    item = {
        "description": "The Company has committed to invest HK$500 million.",
        "source_text": "We have committed HK$500 million and signed binding agreements.",
    }
    assert classify_commitment(item) == "committed"


def test_discretionary_tentative_language():
    from hk_ipo.enrichments.commitment import classify_commitment
    item = {
        "description": "The Company may consider acquisitions subject to market conditions.",
        "source_text": "We may pursue strategic acquisitions if conditions permit.",
    }
    assert classify_commitment(item) == "discretionary"


def test_committed_when_obligated():
    from hk_ipo.enrichments.commitment import classify_commitment
    item = {
        "description": "We are obligated under the loan agreement to repay within 3 years.",
        "source_text": "Mandatory repayment of HK$200 million under existing obligations.",
    }
    assert classify_commitment(item) == "committed"


def test_discretionary_contingent():
    from hk_ipo.enrichments.commitment import classify_commitment
    item = {
        "description": "Subject to board approval, we may allocate funds for expansion.",
        "source_text": "Any allocation is subject to board approval and market conditions.",
    }
    assert classify_commitment(item) == "discretionary"


def test_default_committed():
    from hk_ipo.enrichments.commitment import classify_commitment
    item = {"description": "Use for research.", "source_text": "Use for research."}
    assert classify_commitment(item) == "committed"
```

- [ ] **Step 2: Run; verify FAIL**

Run: `python -m pytest tests/test_enrichments_commitment.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/hk_ipo/enrichments/commitment.py`**

```python
"""L5 enrichment: commitment strength (committed vs discretionary).

Rules-based: checks source text for binding vs tentative language patterns.
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

DIMENSION = "commitment"
VERSION = 1

_COMMITTED_KW = re.compile(
    r"\b(committed|obligated|mandatory|binding|agreed|contracted"
    r"|signed|executed|irrevocable|guaranteed|covenant|undertak"
    r"|required\s+to|will\s+(invest|spend|allocate|use|deploy|repay)"
    r"|has\s+(committed|agreed|entered|signed)|shall\s+(invest|use))"
    r"\b",
    re.IGNORECASE,
)
_DISCRETIONARY_KW = re.compile(
    r"\b(may|might|could|subject\s+to|conditional|contingen"
    r"|discretionary|optional|if\s+(conditions?|market|approved|permitted)"
    r"|pending|at\s+(our|the)\s*(discretion|option)|proposed|intended"
    r"|expected|anticipated|planned|potential|possible)\b",
    re.IGNORECASE,
)


def classify_commitment(item: dict[str, Any]) -> str:
    text = " ".join([
        str(item.get("description", "")),
        str(item.get("source_text", "")),
    ])
    n_committed = len(_COMMITTED_KW.findall(text))
    n_discretionary = len(_DISCRETIONARY_KW.findall(text))
    if n_discretionary > n_committed:
        return "discretionary"
    return "committed"


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
            by_use_id[u["use_id"]] = classify_commitment(u)
        block = {"version": VERSION, "by_use_id": by_use_id}
        merge_enrichment_block(record, DIMENSION, block)
        tick = record.get("hk_ticker", "unknown")
        save_enriched(record, enriched_dir, tick)
        n_comm = sum(1 for v in by_use_id.values() if v == "committed")
        print(f"[commitment] {tick}: {n_comm}/{len(by_use_id)} uses committed")
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
    parser = argparse.ArgumentParser(description="L5 commitment enrichment")
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

Run: `python -m pytest tests/test_enrichments_commitment.py -v`

Expected: All tests pass.

- [ ] **Step 5: Run full suite (except e2e)**

Run: `python -m pytest -q --ignore=tests/e2e`
