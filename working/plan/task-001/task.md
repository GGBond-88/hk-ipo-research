# Task 001: Project setup — directories, deps, taxonomy module

## Project Overview

- **Goal:** Build a CLI-driven data pipeline plus React dashboard that locates "Use of Proceeds" sections in HKEX prospectus PDFs, extracts each use with a two-pass LLM (flat extraction + hierarchical classification), enriches with eight tag dimensions, persists to SQLite, and renders interactive charts from pre-baked JSON.
- **Architecture:** Eight-stage CLI pipeline (L1 sectioning -> L2 flat extraction -> L3 validation -> L4 hierarchical categorize -> L5 enrichments -> L6 SQLite loader -> L7 JSON export -> React/Vite/ECharts dashboard). Each stage is independently runnable and idempotent. SQLite is source of truth; frontend reads pre-baked JSON only.
- **Tech Stack:** Python 3.10+, pydantic v2, pymupdf4llm, pdfplumber, OpenAI SDK + OpenRouter, SQLite (stdlib), pytest. Frontend: Vite + React + TypeScript + ECharts + Zustand + dayjs.

## Task Objective

Add new top-level data directories required by later stages, register a `taxonomy.py` module that exposes the closed Parent/Main vocabulary as a single source of truth, and pin new Python dependencies in `pyproject.toml`. This unblocks every later task that imports the taxonomy.

This is Task 1 of 27.

---

**Files:**
- Create: `src/hk_ipo/taxonomy.py`
- Create: `tests/test_taxonomy.py`
- Modify: `pyproject.toml`
- Create: `data/categorized/.gitkeep`
- Create: `data/enriched/.gitkeep`
- Create: `data/logs/.gitkeep`
- Create: `frontend/public/data/.gitkeep`
- Create: `frontend/public/data/sankey/.gitkeep`
- Create: `tests/fixtures/.gitkeep`

- [ ] **Step 1: Create the empty data directories with `.gitkeep` placeholders**

Run (PowerShell):
```powershell
$dirs = @(
  'data\categorized', 'data\enriched', 'data\logs',
  'frontend\public\data', 'frontend\public\data\sankey',
  'tests\fixtures'
)
foreach ($d in $dirs) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  if (-not (Test-Path "$d\.gitkeep")) { New-Item -ItemType File -Path "$d\.gitkeep" | Out-Null }
}
```

Expected: each directory exists and contains a zero-byte `.gitkeep`.

- [ ] **Step 2: Write a failing test for the taxonomy module**

Create `tests/test_taxonomy.py`:

```python
"""Unit tests for src/hk_ipo/taxonomy.py — closed Parent/Main vocabulary."""
from __future__ import annotations

import hashlib
import json

import pytest


def test_parent_categories_are_exactly_four():
    from hk_ipo.taxonomy import PARENT_CATEGORIES
    assert PARENT_CATEGORIES == [
        "Growth",
        "Financing",
        "Working Capital",
        "Others",
    ]


def test_parent_tree_has_all_four_parents():
    from hk_ipo.taxonomy import PARENT_TREE
    assert set(PARENT_TREE.keys()) == {"Growth", "Financing", "Working Capital", "Others"}


def test_growth_has_expected_mains():
    from hk_ipo.taxonomy import PARENT_TREE
    growth_mains = set(PARENT_TREE["Growth"].keys())
    expected = {
        "R&D and Technology",
        "Product Development",
        "Sales and Marketing",
        "Capacity Expansion",
        "Geographic Expansion",
        "Acquisitions and Strategic Investments",
        "Infrastructure and Network",
    }
    assert growth_mains == expected


def test_financing_has_expected_mains():
    from hk_ipo.taxonomy import PARENT_TREE
    fin_mains = set(PARENT_TREE["Financing"].keys())
    assert fin_mains == {"Debt Repayment", "Refinancing", "Interest Payments"}


def test_main_to_parent_map_is_consistent():
    from hk_ipo.taxonomy import MAIN_TO_PARENT, PARENT_TREE
    for parent, mains in PARENT_TREE.items():
        for main in mains:
            assert MAIN_TO_PARENT[main] == parent


def test_sub_categories_default_listed_for_growth_rd():
    from hk_ipo.taxonomy import PARENT_TREE
    subs = PARENT_TREE["Growth"]["R&D and Technology"]
    assert "Core product R&D" in subs
    assert "Platform / infrastructure R&D" in subs
    assert "Clinical / regulatory development" in subs


def test_taxonomy_sha_is_stable():
    from hk_ipo.taxonomy import PARENT_TREE, taxonomy_sha
    expected = hashlib.sha256(
        json.dumps(PARENT_TREE, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert taxonomy_sha() == expected
    # Recomputing yields the same digest
    assert taxonomy_sha() == taxonomy_sha()


def test_schema_version_is_two_dot_zero():
    from hk_ipo.taxonomy import SCHEMA_VERSION
    assert SCHEMA_VERSION == "2.0"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m pytest tests/test_taxonomy.py -v`
Expected: `ModuleNotFoundError: No module named 'hk_ipo.taxonomy'` (or all tests fail with import error).

- [ ] **Step 4: Implement `src/hk_ipo/taxonomy.py`**

```python
"""Closed Parent / Main / Sub taxonomy for HK IPO use-of-proceeds classification.

This module is the single source of truth for L4 categorization, L6 loader
referential checks, L7 dashboard export, and frontend display.

Parent categories are FIXED (4).
Main categories under each parent are FIXED (closed list).
Sub categories under each main are SUGGESTED defaults; L4 may emit new sub
labels for review (captured to data/taxonomy_proposals.csv).
"""
from __future__ import annotations

import hashlib
import json

SCHEMA_VERSION: str = "2.0"

PARENT_CATEGORIES: list[str] = [
    "Growth",
    "Financing",
    "Working Capital",
    "Others",
]

PARENT_TREE: dict[str, dict[str, list[str]]] = {
    "Growth": {
        "R&D and Technology": [
            "Core product R&D",
            "Platform / infrastructure R&D",
            "Clinical / regulatory development",
        ],
        "Product Development": [
            "New product launches",
            "Product enhancements",
        ],
        "Sales and Marketing": [
            "Brand and advertising",
            "Channel expansion",
            "Customer acquisition",
        ],
        "Capacity Expansion": [
            "New manufacturing facilities",
            "Capacity upgrades to existing sites",
            "Equipment and machinery",
        ],
        "Geographic Expansion": [
            "Overseas markets",
            "Mainland China expansion",
            "Specific region build-out",
        ],
        "Acquisitions and Strategic Investments": [
            "M&A",
            "Minority strategic investments",
            "Joint ventures",
        ],
        "Infrastructure and Network": [
            "Stores / branches",
            "Data centers and IT infrastructure",
            "Logistics and supply chain",
        ],
    },
    "Financing": {
        "Debt Repayment": [
            "Bank loan repayment",
            "Bond / note redemption",
        ],
        "Refinancing": [],
        "Interest Payments": [],
    },
    "Working Capital": {
        "General Working Capital": [],
        "Inventory Procurement": [],
        "Receivables / Payables Management": [],
        "Day-to-day Operations": [],
    },
    "Others": {
        "General Corporate Purposes": [],
        "Reserves / Contingencies": [],
        "Unallocated / Unspecified": [],
    },
}

MAIN_TO_PARENT: dict[str, str] = {
    main: parent
    for parent, mains in PARENT_TREE.items()
    for main in mains
}


def taxonomy_sha() -> str:
    """SHA-256 of canonical-JSON-serialised PARENT_TREE; used in manifest.json."""
    payload = json.dumps(PARENT_TREE, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_taxonomy.py -v`
Expected: 7 tests pass, no failures.

- [ ] **Step 6: Add new dependencies to `pyproject.toml`**

Edit the `[project]` section so `dependencies` reads:

```toml
dependencies = [
    "pymupdf4llm>=0.0.17",
    "pdfplumber>=0.11",
    "python-dotenv",
    "langextract>=1.0",
    "openai>=1.40",
    "pandas",
    "matplotlib",
    "langdetect>=1.0.9",
]
```

Rationale: `langdetect` is the language gate used by L1 in a later task. Other deps are unchanged.

- [ ] **Step 7: Install the new dependency**

Run: `pip install -e ".[dev]"`
Expected: `langdetect-1.0.9` (or newer) installs without errors. Existing deps unchanged.

- [ ] **Step 8: Run the full existing test suite to confirm no regression**

Run: `python -m pytest -q`
Expected: all previously-passing tests still pass; new taxonomy tests pass.

- [ ] **Step 9: Commit verification (manual review, do not push)**

Run: `git status`
Expected: new files under `src/hk_ipo/taxonomy.py`, `tests/test_taxonomy.py`, `data/*/.gitkeep`, `frontend/public/data/.gitkeep`, `tests/fixtures/.gitkeep`, and a modified `pyproject.toml`.
