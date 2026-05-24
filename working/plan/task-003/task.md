# Task 003: Schema v2.0 — extend schema.py and rename legacy L4

## Project Overview

- **Goal:** Build the eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L1 -> L2 -> L3 -> L4 hierarchical categorize -> L5 enrichments -> L6 SQLite loader -> L7 JSON export -> dashboard. Two-pass LLM extraction.
- **Tech Stack:** Python 3.10+, pydantic v2, OpenAI SDK, SQLite, Vite + React + ECharts.

## Task Objective

Bump `SCHEMA_VERSION` to `"2.0"`, add new fields (`parent_category`, `main_category`, `sub_category`, `category_proposed`, `language`) to the pydantic models, preserve the existing `CATEGORY_L2`/`CATEGORY_L1_TREE` constants for backwards compatibility with the legacy L4, and rename the existing matplotlib `l4_analysis.py` to `l4_legacy_analysis.py`. This unblocks L2/L3/L4 rewrites without breaking the 130 existing tests.

This is Task 3 of 27.

---

**Files:**
- Modify: `src/hk_ipo/schema.py`
- Rename: `src/hk_ipo/l4_analysis.py` -> `src/hk_ipo/l4_legacy_analysis.py`
- Modify: `tests/test_l4_analysis.py` (update import path only)
- Modify: `scripts/run_pipeline.py` (update import path only)
- Modify: `tests/test_schema.py` (add new tests for v2.0 fields)

- [ ] **Step 1: Write failing tests for new schema fields**

Append to `tests/test_schema.py` (do not modify existing tests):

```python
# ── v2.0 schema tests (Task 003) ─────────────────────────────────────────────

def test_schema_version_v2():
    from hk_ipo.schema import SCHEMA_VERSION
    assert SCHEMA_VERSION == "2.0"


def test_use_item_accepts_new_hierarchy_fields():
    from hk_ipo.schema import UseItem
    item = UseItem(
        use_id="use_001",
        parent_category="Growth",
        main_category="R&D and Technology",
        sub_category="Core product R&D",
        category_proposed=None,
        category_raw="research and development",
        percentage=35.0,
        amount_hkd_million=100.0,
        description="Develop core algorithms.",
        source_text="Approximately 35% ...",
    )
    assert item.parent_category == "Growth"
    assert item.main_category == "R&D and Technology"
    assert item.sub_category == "Core product R&D"


def test_use_item_v2_omits_old_category_field_validation():
    """The old `category` (CATEGORY_L2) validator must remain optional/no-op
    when not set — new pipeline does not populate it."""
    from hk_ipo.schema import UseItem
    item = UseItem(
        use_id="use_001",
        parent_category="Growth",
        main_category="R&D and Technology",
        category_raw="r&d",
        percentage=100.0,
    )
    assert item.category is None
    assert item.parent_category == "Growth"


def test_extraction_record_accepts_language_field():
    from hk_ipo.schema import ExtractionRecord
    rec = ExtractionRecord(
        company_file="01234.pdf",
        hk_ticker="01234",
        language="en",
        uses=[],
    )
    assert rec.language == "en"


def test_extraction_record_accepts_schema_version_field():
    from hk_ipo.schema import ExtractionRecord, SCHEMA_VERSION
    rec = ExtractionRecord(
        company_file="01234.pdf",
        hk_ticker="01234",
        schema_version=SCHEMA_VERSION,
        uses=[],
    )
    assert rec.schema_version == "2.0"


def test_legacy_category_l2_constants_still_importable():
    """Backwards-compat for the legacy L4 module and existing tests."""
    from hk_ipo.schema import CATEGORY_L1_MAP, CATEGORY_L2, CATEGORY_L1_TREE
    assert "R&D and technology" in CATEGORY_L2
    assert CATEGORY_L1_MAP["R&D and technology"] == "Technology & Product"
    assert "Technology & Product" in CATEGORY_L1_TREE
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_schema.py -v -k "v2 or new_hierarchy or language or legacy_category"`
Expected: All five new tests fail with `ValidationError` ("extra fields not permitted") or `AttributeError`. The `legacy_category_l2_constants_still_importable` test should pass (constants already exist).

- [ ] **Step 3: Update `src/hk_ipo/schema.py`**

Replace the existing file content:

```python
"""Single source of truth for HK IPO Research schema definitions.

v2.0 changes
------------
- SCHEMA_VERSION bumped from "1.0" to "2.0".
- UseItem gains `parent_category`, `main_category`, `sub_category` (set by L4).
- ExtractionRecord gains `language` ('en' | 'zh' | 'mixed') and `schema_version`.
- Legacy `CATEGORY_L2`, `CATEGORY_L1_TREE`, `CATEGORY_L1_MAP` are PRESERVED for
  backwards compatibility with `l4_legacy_analysis.py` and existing tests.
  New code should import from `hk_ipo.taxonomy` instead.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator

# ── Version ───────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "2.0"

# ── Legacy category definitions (DO NOT EXTEND — use hk_ipo.taxonomy) ────────

CATEGORY_L1_TREE: dict[str, list[str]] = {
    "Growth & Expansion": [
        "Overseas expansion",
        "Manufacturing expansion",
        "Production capacity",
        "Acquisitions and investments",
    ],
    "Technology & Product": [
        "R&D and technology",
        "Product development",
    ],
    "Commercial": [
        "Sales and marketing",
    ],
    "Corporate": [
        "Working capital",
    ],
}

CATEGORY_L2: list[str] = [
    sub for subs in CATEGORY_L1_TREE.values() for sub in subs
]

CATEGORY_L1_MAP: dict[str, str] = {
    sub: l1
    for l1, subs in CATEGORY_L1_TREE.items()
    for sub in subs
}

# ── Pydantic models ───────────────────────────────────────────────────────────


class SectionRecord(BaseModel):
    """Fields produced by L1 sectioning output."""

    company_file: str
    hk_ticker: Optional[str] = None
    document_date: Optional[str] = None
    section_title: str
    start_page: int
    end_page: int
    text: str
    tables: list[Any] = []
    extraction_method: str
    # v2 fields
    language: Optional[str] = None
    skipped: bool = False


class UseItem(BaseModel):
    """A single use-of-proceeds line item.

    v2 fields:
      parent_category  — closed Parent vocabulary (see hk_ipo.taxonomy)
      main_category    — closed Main vocabulary under parent_category
      sub_category     — semi-open Sub vocabulary; None or a free-form label
    """
    model_config = ConfigDict(extra="allow")  # tolerate transient fields

    use_id: str
    parent_id: Optional[str] = None
    # legacy fields
    category: Optional[str] = None
    category_proposed: Optional[str] = None
    category_raw: str = ""
    # v2 hierarchy fields
    parent_category: Optional[str] = None
    main_category: Optional[str] = None
    sub_category: Optional[str] = None
    # numerics
    amount_hkd_million: Optional[float] = None
    percentage: Optional[float] = None
    description: str = ""
    source_text: str = ""

    @model_validator(mode="after")
    def validate_legacy_category_membership(self) -> "UseItem":
        """Preserve the legacy CATEGORY_L2 check for backwards compatibility.

        New v2 pipeline does not set `category`, so the check is effectively
        a no-op for new records.
        """
        if self.category is not None and self.category_proposed is None:
            if self.category not in CATEGORY_L2:
                raise ValueError(
                    f"category {self.category!r} is not in CATEGORY_L2. "
                    f"Valid values: {CATEGORY_L2}. "
                    "Set category_proposed if no standard category fits."
                )
        return self


class ExtractionRecord(BaseModel):
    """Full L2 extraction output for one prospectus section."""

    model_config = ConfigDict(extra="allow")

    company_file: str
    section_source: Optional[str] = None
    hk_ticker: Optional[str] = None
    document_date: Optional[str] = None
    model_used: Optional[str] = None
    extraction_timestamp: Optional[str] = None
    total_net_proceeds_hkd_million: Optional[float] = None
    currency: str = "HKD"
    uses: list[UseItem] = []
    validation_preview: Optional[dict[str, Any]] = None
    # v2 fields
    schema_version: Optional[str] = None
    language: Optional[str] = None


# ── Helper ────────────────────────────────────────────────────────────────────

def validate_extraction(data: dict[str, Any]) -> ExtractionRecord:
    """Validate a raw extraction dict against ExtractionRecord schema."""
    return ExtractionRecord.model_validate(data)
```

- [ ] **Step 4: Run schema tests; verify all pass**

Run: `python -m pytest tests/test_schema.py -v`
Expected: all existing schema tests + 5 new v2 tests pass.

- [ ] **Step 5: Rename legacy L4 module**

Run (PowerShell):
```powershell
Move-Item src\hk_ipo\l4_analysis.py src\hk_ipo\l4_legacy_analysis.py
```

Update the docstring header at the top of `src/hk_ipo/l4_legacy_analysis.py` to read:

```python
"""L4 LEGACY analysis (matplotlib). Retired in v2.0 — kept only so existing
tests stay green. New L4 (hierarchical categorization) lives in
`src/hk_ipo/l4_categorize.py` and is built in Task 008.
"""
```

(Leave the rest of the file unchanged.)

- [ ] **Step 6: Update imports that reference the renamed module**

Edit `tests/test_l4_analysis.py` — change every `from hk_ipo.l4_analysis import` to `from hk_ipo.l4_legacy_analysis import`.

Edit `scripts/run_pipeline.py` — change `from hk_ipo.l4_analysis import run_analysis` to `from hk_ipo.l4_legacy_analysis import run_analysis`.

- [ ] **Step 7: Run the FULL test suite; assert no regressions**

Run: `python -m pytest -q --ignore=tests/e2e`
Expected: every previously-passing test still passes. Existing test count + 5 new schema tests now pass.

- [ ] **Step 8: Verify `scripts/run_pipeline.py` still imports cleanly**

Run: `python -c "import scripts.run_pipeline"` from project root.
Expected: no exception; legacy run_analysis is now imported from `l4_legacy_analysis`.
