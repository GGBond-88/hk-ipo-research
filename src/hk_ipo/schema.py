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

CATEGORY_L2: list[str] = [sub for subs in CATEGORY_L1_TREE.values() for sub in subs]

CATEGORY_L1_MAP: dict[str, str] = {sub: l1 for l1, subs in CATEGORY_L1_TREE.items() for sub in subs}

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
      sub_category     — semi-open Sub vocabulary
      None or a free-form label
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
