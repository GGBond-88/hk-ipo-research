"""Single source of truth for HK IPO Research schema definitions.

Assumptions:
  - pydantic v2 is used (model_validate, not parse_obj)
  - category field on UseItem is Optional[str] with a validator that checks
    membership in CATEGORY_L2 when not None and category_proposed is not set
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, model_validator

# ── Version ───────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0"

# ── Level-1 and Level-2 category definitions ──────────────────────────────────

# Exactly 4 L1 categories, each with fixed sub-categories (L2).
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

# Flat list of all Level-2 category strings (8 total).
CATEGORY_L2: list[str] = [
    sub for subs in CATEGORY_L1_TREE.values() for sub in subs
]

# Dict mapping each L2 label → its L1 parent label.
CATEGORY_L1_MAP: dict[str, str] = {
    sub: l1
    for l1, subs in CATEGORY_L1_TREE.items()
    for sub in subs
}

# ── Cross-cutting tag type aliases (structural, not runtime-enforced) ─────────
# These are plain type aliases to document intent. Validation is handled by
# Pydantic models below where applicable.

# GeoScope: Literal["domestic", "overseas", "both"]
# GeoTargets: list[str]  — free-form country/region names
# TargetIndustries: list[str]
# HeadcountPlan: Optional[int]
# AssetType: Optional[str]

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


class UseItem(BaseModel):
    """A single use-of-proceeds line item extracted by L2."""

    use_id: str
    parent_id: Optional[str] = None
    # category must be in CATEGORY_L2 when not None AND category_proposed is absent.
    # When category_proposed is set, category may be the closest-match label OR None.
    category: Optional[str] = None
    category_proposed: Optional[str] = None
    category_raw: str = ""
    amount_hkd_million: Optional[float] = None
    percentage: Optional[float] = None
    description: str = ""
    source_text: str = ""

    @model_validator(mode="after")
    def validate_category_membership(self) -> "UseItem":
        """Enforce CATEGORY_L2 membership when category is set.

        Skips the check when category_proposed is also set (intentional
        'no match' items where the LLM used the closest standard label
        alongside a free-form proposed label).
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


# ── Helper ────────────────────────────────────────────────────────────────────

def validate_extraction(data: dict[str, Any]) -> ExtractionRecord:
    """Validate a raw extraction dict against ExtractionRecord schema.

    Raises pydantic.ValidationError if the data does not conform.
    """
    return ExtractionRecord.model_validate(data)
