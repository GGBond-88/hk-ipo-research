# Task 014: L5 enrichment — capex_opex tool

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L5 enrichment tool classifies each use item as `capex`, `opex`, or `financial`.
- **Tech Stack:** Python 3.10+, pytest.

## Task Objective

Implement `capex_opex.py`: classify each use item into capital expenditure, operational expenditure, or financial based on keyword patterns. Rules-based. Follow TDD.

This is Task 14 of 27.

---

**Files:**
- Create: `src/hk_ipo/enrichments/capex_opex.py`
- Create: `tests/test_enrichments_capex_opex.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrichments_capex_opex.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/capex_opex.py."""
from __future__ import annotations


def test_dimension_and_version():
    from hk_ipo.enrichments.capex_opex import DIMENSION, VERSION
    assert DIMENSION == "capex_opex"
    assert isinstance(VERSION, int)


def test_capex_factory_construction():
    from hk_ipo.enrichments.capex_opex import classify_capex_opex
    item = {
        "description": "Build a new manufacturing plant with equipment.",
        "category_raw": "manufacturing facility construction",
        "source_text": "We will construct a new plant and install machinery.",
    }
    assert classify_capex_opex(item) == "capex"


def test_opex_working_capital():
    from hk_ipo.enrichments.capex_opex import classify_capex_opex
    item = {
        "description": "General working capital for day-to-day opex.",
        "category_raw": "working capital",
        "source_text": "Approximately 10% for general working capital and opex.",
    }
    assert classify_capex_opex(item) == "opex"


def test_financial_debt_repayment():
    from hk_ipo.enrichments.capex_opex import classify_capex_opex
    item = {
        "description": "Repay outstanding bank loans and bonds.",
        "category_raw": "debt repayment",
        "source_text": "Approximately 20% to repay bank loans and redeem bonds.",
    }
    assert classify_capex_opex(item) == "financial"


def test_capex_r_and_d_equipment():
    from hk_ipo.enrichments.capex_opex import classify_capex_opex
    item = {
        "description": "Purchase R&D equipment and laboratory facilities.",
        "category_raw": "R&D equipment purchase",
        "source_text": "To purchase R&D equipment, servers, and lab equipment.",
    }
    assert classify_capex_opex(item) == "capex"


def test_default_capex_when_ambiguous():
    from hk_ipo.enrichments.capex_opex import classify_capex_opex
    item = {"description": "Something", "source_text": "Something."}
    assert classify_capex_opex(item) == "capex"
```

- [ ] **Step 2: Run; verify FAIL**

Run: `python -m pytest tests/test_enrichments_capex_opex.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/hk_ipo/enrichments/capex_opex.py`**

```python
"""L5 enrichment: CAPEX vs OPEX vs financial classification.

Rules-based keyword classifier for use-of-proceeds items.
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

DIMENSION = "capex_opex"
VERSION = 1

_FINANCIAL_KW = re.compile(
    r"\b(debt|repay|loan|bond|note|refinanc|interest|borrowing"
    r"|redemption|maturity|leverage)\b",
    re.IGNORECASE,
)
_OPEX_KW = re.compile(
    r"\b(working\s*capital|operating\s*expense|opex|payroll|salary"
    r"|wage|rent|lease|utility|marketing\s*campaign|advertising"
    r"|sales\s*force|sales\s*team|day[\s-]to[\s-]day|general\s*purposes?"
    r"|recruitment|hiring|training|maintenance(?!\s*(of|capital|new)))"
    r"\b",
    re.IGNORECASE,
)
_CAPEX_KW = re.compile(
    r"\b(construct|build|acqui(re|sition)|purchase|buy|install"
    r"|equipment|machinery|plant|facilit|factory|warehouse|property"
    r"|real\s*estate|land|data\s*center|server|hardware|infrastructure"
    r"|r\s*&\s*d\s*(center|facility|lab)|manufacturing\s*(plant|line|facility)"
    r"|expansion|upgrade|renovation|fit[\s-]out|new\s*(store|branch|office)"
    r"|fleet|vehicle|vessel)\b",
    re.IGNORECASE,
)


def classify_capex_opex(item: dict[str, Any]) -> str:
    text = " ".join([
        str(item.get("description", "")),
        str(item.get("category_raw", "")),
        str(item.get("source_text", "")),
    ])
    if _FINANCIAL_KW.search(text):
        return "financial"
    if _OPEX_KW.search(text):
        return "opex"
    if _CAPEX_KW.search(text):
        return "capex"
    return "capex"  # default: UoP is typically capex for IPOs


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
            by_use_id[u["use_id"]] = classify_capex_opex(u)
        block = {"version": VERSION, "by_use_id": by_use_id}
        merge_enrichment_block(record, DIMENSION, block)
        tick = record.get("hk_ticker", "unknown")
        save_enriched(record, enriched_dir, tick)
        print(f"[capex_opex] {tick}: {len(by_use_id)} uses tagged")
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
    parser = argparse.ArgumentParser(description="L5 capex_opex enrichment")
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

Run: `python -m pytest tests/test_enrichments_capex_opex.py -v`

- [ ] **Step 5: Run full suite (except e2e)**

Run: `python -m pytest -q --ignore=tests/e2e`
