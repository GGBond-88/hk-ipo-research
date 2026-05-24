# Task 009: L5 enrichment base contract + geo tool

## Project Overview

- **Goal:** Build a CLI-driven data pipeline plus React dashboard that locates "Use of Proceeds" sections in HKEX prospectus PDFs, extracts each use with a two-pass LLM (flat extraction + hierarchical classification), enriches with eight tag dimensions, persists to SQLite, and renders interactive charts from pre-baked JSON.
- **Architecture:** Eight-stage CLI pipeline. L5 enrichment tools are modular and independent — each reads `data/categorized/<ticker>.json`, writes only its own `enrichments.<dim>` block, and is idempotent.
- **Tech Stack:** Python 3.10+, pydantic v2, OpenAI SDK + OpenRouter, pytest.

## Task Objective

Create the shared enrichment base contract (`base.py`) and implement the first enrichment tool: `geo.py` (tags each use as `domestic_hk`, `mainland`, or `overseas`). Both follow TDD.

This is Task 9 of 27.

---

**Files:**
- Create: `src/hk_ipo/enrichments/__init__.py`
- Create: `src/hk_ipo/enrichments/base.py`
- Create: `src/hk_ipo/enrichments/geo.py`
- Create: `tests/test_enrichments_base.py`
- Create: `tests/test_enrichments_geo.py`

- [ ] **Step 1: Create `src/hk_ipo/enrichments/__init__.py`**

Empty marker:

```python
"""L5 enrichment tools — one module per dimension."""
```

- [ ] **Step 2: Write the failing test for `base.py`**

Create `tests/test_enrichments_base.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/base.py — enrichment runner contract."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_enrichment_runner_interface_defined():
    """The base module must export an EnrichmentRunner protocol/class."""
    from hk_ipo.enrichments.base import EnrichmentRunner
    assert callable(getattr(EnrichmentRunner, "run", None)) is False  # abstract


def test_load_enriched_or_categorized_loads_json_bare_dir(tmp_path: Path):
    """When caller passes a bare directory containing <ticker>.json,
    load_enriched_or_categorized must find and load it."""
    from hk_ipo.enrichments.base import load_enriched_or_categorized

    data = {"hk_ticker": "01234", "uses": []}
    cf = tmp_path / "01234.json"
    cf.write_text(json.dumps(data), encoding="utf-8")

    result = load_enriched_or_categorized(tmp_path, "01234")
    assert result["hk_ticker"] == "01234"


def test_load_enriched_or_categorized_loads_from_categorized_subdir(tmp_path: Path):
    """When caller passes a parent directory with a 'categorized' subdir, load from it."""
    from hk_ipo.enrichments.base import load_enriched_or_categorized

    (tmp_path / "categorized").mkdir()
    (tmp_path / "categorized" / "01234.json").write_text(
        json.dumps({"hk_ticker": "01234", "uses": [], "source": "categorized"}),
        encoding="utf-8",
    )
    result = load_enriched_or_categorized(tmp_path, "01234")
    assert result["source"] == "categorized"


def test_load_enriched_or_categorized_prefers_enriched_over_categorized(tmp_path: Path):
    """When both subdirs contain the ticker, the enriched/ copy wins."""
    from hk_ipo.enrichments.base import load_enriched_or_categorized

    (tmp_path / "enriched").mkdir()
    (tmp_path / "categorized").mkdir()
    (tmp_path / "enriched" / "01234.json").write_text(
        json.dumps({"hk_ticker": "01234", "uses": [], "source": "enriched"}),
        encoding="utf-8",
    )
    (tmp_path / "categorized" / "01234.json").write_text(
        json.dumps({"hk_ticker": "01234", "uses": [], "source": "categorized"}),
        encoding="utf-8",
    )
    result = load_enriched_or_categorized(tmp_path, "01234")
    assert result["source"] == "enriched"


def test_merge_enrichment_block_adds_new_dim(tmp_path: Path):
    from hk_ipo.enrichments.base import merge_enrichment_block

    record = {"enrichments": {}}
    merge_enrichment_block(record, "geo", {"version": 1, "by_use_id": {}})
    assert record["enrichments"]["geo"] == {"version": 1, "by_use_id": {}}


def test_merge_enrichment_block_overwrites_old_version():
    from hk_ipo.enrichments.base import merge_enrichment_block

    record = {"enrichments": {"geo": {"version": 1, "by_use_id": {"use_001": "domestic_hk"}}}}
    merge_enrichment_block(record, "geo", {"version": 2, "by_use_id": {"use_001": "overseas"}})
    assert record["enrichments"]["geo"]["version"] == 2
    assert record["enrichments"]["geo"]["by_use_id"]["use_001"] == "overseas"


def test_save_enriched_writes_json(tmp_path: Path):
    from hk_ipo.enrichments.base import save_enriched

    record = {"hk_ticker": "01234", "enrichments": {"geo": {"version": 1}}}
    save_enriched(record, tmp_path, "01234")
    out = tmp_path / "01234.json"
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["enrichments"]["geo"]["version"] == 1
```

- [ ] **Step 3: Run base tests; verify FAIL**

Run: `python -m pytest tests/test_enrichments_base.py -v`

Expected: `ModuleNotFoundError: No module named 'hk_ipo.enrichments.base'`

- [ ] **Step 4: Implement `src/hk_ipo/enrichments/base.py`**

```python
"""Shared enrichment runner contract and file I/O helpers.

Each L5 enrichment tool:
  - Reads data/categorized/<ticker>.json (or data/enriched/<ticker>.json if
    a previous enrichment already wrote it).
  - Adds or updates ONLY its own `enrichments.<dim>` block.
  - Writes the result to data/enriched/<ticker>.json.
  - Is idempotent: re-running with the same inputs produces the same outputs.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class EnrichmentRunner(Protocol):
    """Protocol for individual enrichment tool modules."""

    DIMENSION: str
    VERSION: int

    def run(self, record: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single record. Returns the enrichment block to merge."""
        ...


def load_enriched_or_categorized(
    data_dir: Path, ticker: str,
) -> dict[str, Any]:
    """Load the most recent record for `ticker`.

    Lookup order:
      1) <data_dir>/enriched/<ticker>.json
      2) <data_dir>/categorized/<ticker>.json
      3) <data_dir>/<ticker>.json   (bare directory — e.g. when caller
         passes the enriched_dir or categorized_dir directly).
    """
    candidates = [
        data_dir / "enriched" / f"{ticker}.json",
        data_dir / "categorized" / f"{ticker}.json",
        data_dir / f"{ticker}.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"No record for ticker {ticker} in {data_dir}")


def merge_enrichment_block(
    record: dict[str, Any],
    dimension: str,
    block: dict[str, Any],
) -> None:
    """Set or overwrite record['enrichments'][dimension] with `block`."""
    if "enrichments" not in record:
        record["enrichments"] = {}
    record["enrichments"][dimension] = block


def save_enriched(
    record: dict[str, Any],
    enriched_dir: Path,
    ticker: str,
) -> None:
    """Write the enriched record to data/enriched/<ticker>.json."""
    enriched_dir.mkdir(parents=True, exist_ok=True)
    out_path = enriched_dir / f"{ticker}.json"
    out_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

- [ ] **Step 5: Run base tests; verify PASS**

Run: `python -m pytest tests/test_enrichments_base.py -v`

Expected: All 7 tests pass (interface, bare-dir load, categorized-subdir load, enriched-precedence, merge-new, merge-overwrite, save).

- [ ] **Step 6: Write the failing test for `geo.py`**

Create `tests/test_enrichments_geo.py`:

```python
"""Unit tests for src/hk_ipo/enrichments/geo.py — geographic scope tag."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def test_geo_dimension_and_version():
    from hk_ipo.enrichments.geo import DIMENSION, VERSION
    assert DIMENSION == "geo"
    assert isinstance(VERSION, int)
    assert VERSION >= 1


def test_geo_classify_all_domestic():
    from hk_ipo.enrichments.geo import classify_geo
    result = classify_geo(
        item={"description": "Expand our Hong Kong office.",
              "category_raw": "Hong Kong office expansion",
              "source_text": "We will expand our Hong Kong office."},
        company_name="Example HK Holdings Ltd.",
    )
    assert result == "domestic_hk"


def test_geo_classify_mainland():
    from hk_ipo.enrichments.geo import classify_geo
    result = classify_geo(
        item={"description": "Expand our factory in mainland China.",
              "category_raw": "mainland China factory expansion",
              "source_text": "We plan to expand our factory in Guangdong."},
        company_name="Example HK Holdings Ltd.",
    )
    assert result == "mainland"


def test_geo_classify_overseas():
    from hk_ipo.enrichments.geo import classify_geo
    result = classify_geo(
        item={"description": "Expand into the US and European markets.",
              "category_raw": "overseas market expansion",
              "source_text": "We plan to enter the US and European markets."},
        company_name="Example HK Holdings Ltd.",
    )
    assert result == "overseas"


def test_geo_run_integrates(tmp_path: Path):
    from hk_ipo.enrichments.geo import run as geo_run
    from hk_ipo.enrichments.base import save_enriched, load_enriched_or_categorized

    categorized = tmp_path / "categorized"
    enriched = tmp_path / "enriched"
    categorized.mkdir()
    enriched.mkdir()

    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {"use_id": "use_001", "category_raw": "R&D in Shenzhen",
             "description": "R&D center in Shenzhen", "percentage": 100.0,
             "source_text": "We will build an R&D center in Shenzhen."}
        ],
        "enrichments": {},
    }
    save_enriched(record, categorized, "01234")
    geo_run(categorized, enriched, ticker="01234")
    result = load_enriched_or_categorized(enriched if (enriched / "01234.json").exists() else categorized, "01234")
    assert result["enrichments"]["geo"]["version"] >= 1
    assert "use_001" in result["enrichments"]["geo"]["by_use_id"]


def test_geo_idempotent(tmp_path: Path):
    from hk_ipo.enrichments.geo import run as geo_run
    from hk_ipo.enrichments.base import save_enriched

    categorized = tmp_path / "categorized"
    enriched = tmp_path / "enriched"
    categorized.mkdir(); enriched.mkdir()

    record = {
        "hk_ticker": "01234", "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {"use_id": "use_001", "category_raw": "R&D",
             "description": "R&D", "percentage": 100.0,
             "source_text": "We will do R&D."}
        ],
        "enrichments": {},
    }
    save_enriched(record, categorized, "01234")
    first = geo_run(categorized, enriched, ticker="01234")
    second = geo_run(categorized, enriched, ticker="01234")
    assert first == second


def test_geo_run_all_files_processes_bare_categorized_dir(tmp_path: Path):
    """PR-014 / PR-015 regression: run(all_files=True) must:
      1) NOT raise NameError on `json` (module-level import required), and
      2) Find files in the bare categorized_dir (callers pass it directly,
         not a parent containing a categorized/ subdir).
    """
    from hk_ipo.enrichments.geo import run as geo_run
    from hk_ipo.enrichments.base import save_enriched

    categorized = tmp_path / "categorized"
    enriched = tmp_path / "enriched"
    categorized.mkdir()
    enriched.mkdir()

    # Two tickers in the bare categorized dir
    for tk in ("01234", "05678"):
        record = {
            "hk_ticker": tk, "company_name_en": f"Co {tk}",
            "schema_version": "2.0",
            "uses": [
                {"use_id": "use_001", "category_raw": "R&D in Shenzhen",
                 "description": "R&D in Shenzhen", "percentage": 100.0,
                 "source_text": "We will do R&D in Shenzhen."}
            ],
            "enrichments": {},
        }
        save_enriched(record, categorized, tk)

    # Must not raise; must process both tickers
    results = geo_run(categorized, enriched, all_files=True)
    assert isinstance(results, dict)
    assert set(results.keys()) == {"01234", "05678"}
    assert (enriched / "01234.json").exists()
    assert (enriched / "05678.json").exists()
```

- [ ] **Step 7: Run geo tests; verify FAIL**

Run: `python -m pytest tests/test_enrichments_geo.py -v`

Expected: `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 8: Implement `src/hk_ipo/enrichments/geo.py`**

```python
"""L5 enrichment: geographic scope tag (domestic_hk / mainland / overseas).

Maps each use item to one of three geographic scopes by scanning the item's
text fields for keywords. No LLM call — this is a rules-based tagger.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from hk_ipo.enrichments.base import (
    load_enriched_or_categorized,
    merge_enrichment_block,
    save_enriched,
)

DIMENSION = "geo"
VERSION = 1

# ── Keyword sets ───────────────────────────────────────────────────────────

_MAINLAND_KW = re.compile(
    r"\b(mainland\s*china|china|prc|shenzhen|guangdong|beijing|shanghai"
    r"|guangzhou|chengdu|hangzhou|wuhan|nanjing|tianjin|chongqing"
    r"|中国|中华|内地)\b",
    re.IGNORECASE,
)

_OVERSEAS_KW = re.compile(
    r"\b(overseas|international|global|abroad|foreign"
    r"|united states|america|europe|european|southeast asia|asean"
    r"|japan|korea|india|australia|singapore|vietnam|thailand"
    r"|indonesia|malaysia|philippines|uk|germany|france|canada"
    r"|海外|国际|欧洲|东南亚"
    r"|美国|日本|韩国)\b",
    re.IGNORECASE,
)

_DOMESTIC_KW = re.compile(
    r"\b(hong\s*kong|hk|hongkong|香港)\b",
    re.IGNORECASE,
)


def classify_geo(
    item: dict[str, Any],
    company_name: str = "",
) -> str:
    """Classify a use item as domestic_hk, mainland, or overseas."""
    text = " ".join([
        str(item.get("description", "")),
        str(item.get("category_raw", "")),
        str(item.get("source_text", "")),
    ])

    overseas = bool(_OVERSEAS_KW.search(text))
    mainland = bool(_MAINLAND_KW.search(text))
    domestic = bool(_DOMESTIC_KW.search(text))

    if overseas and not mainland:
        return "overseas"
    if mainland and not overseas:
        return "mainland"
    if domestic and not overseas and not mainland:
        return "domestic_hk"
    if overseas and mainland:
        return "overseas"  # both → overseas (broader scope)
    # No strong signal — default to domestic_hk for HK-listed companies
    return "domestic_hk"


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    """Run geo enrichment on one ticker or all."""
    enriched_dir.mkdir(parents=True, exist_ok=True)

    if ticker:
        record = load_enriched_or_categorized(categorized_dir, ticker)
        return _enrich_one(record, enriched_dir, force=force)
    if all_files:
        # PR-015 fix: callers pass categorized_dir as the BARE directory
        # containing <ticker>.json files (not a parent with categorized/
        # subdir). Prefer enriched_dir when it has files, else fall back
        # to categorized_dir. This matches the pattern used by the other
        # seven enrichment tools (country, specificity, etc.).
        jsons = sorted((enriched_dir if enriched_dir.exists() and
                        any(enriched_dir.glob("*.json"))
                        else categorized_dir).glob("*.json"))
        results = {}
        for jf in jsons:
            record = json.loads(jf.read_text(encoding="utf-8"))
            tick = record.get("hk_ticker") or jf.stem
            results[tick] = _enrich_one(record, enriched_dir, force=force)
        return results
    return None


def _enrich_one(
    record: dict[str, Any],
    enriched_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    existing = record.get("enrichments", {}).get(DIMENSION)
    if not force and existing and existing.get("version") == VERSION:
        return existing

    ticker = record.get("hk_ticker") or "unknown"
    company = record.get("company_name_en", "")
    by_use_id: dict[str, str] = {}
    for u in record.get("uses", []):
        by_use_id[u["use_id"]] = classify_geo(u, company)

    block = {"version": VERSION, "by_use_id": by_use_id}
    merge_enrichment_block(record, DIMENSION, block)
    save_enriched(record, enriched_dir, ticker)
    print(f"[geo] {ticker}: {len(by_use_id)} uses tagged")
    return block


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L5 geo enrichment")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("categorized", nargs="?", help="Path to categorized JSON file")
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
        record = json.loads(sf.read_text(encoding="utf-8"))
        ticker = record.get("hk_ticker") or sf.stem
        _enrich_one(record, ENRICHED, force=args.force)
```

- [ ] **Step 9: Run geo tests; verify PASS**

Run: `python -m pytest tests/test_enrichments_geo.py -v`

Expected: All tests pass.

- [ ] **Step 10: Run full test suite (except e2e); verify no regressions**

Run: `python -m pytest -q --ignore=tests/e2e`

Expected: All tests pass.
