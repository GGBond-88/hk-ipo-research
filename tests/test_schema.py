"""Tests for src/hk_ipo/schema.py — schema definitions and validation helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hk_ipo.schema import (
    CATEGORY_L1_MAP,
    CATEGORY_L2,
    ExtractionRecord,
    UseItem,
    validate_extraction,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _valid_meituan_dict() -> dict:
    """A valid Meituan-like extraction dict that should pass schema validation."""
    total = 31123.0
    return {
        "company_file": "ltn20180907011.pdf",
        "section_source": "ltn20180907011.json",
        "hk_ticker": "3690",
        "document_date": "2018-09-07",
        "model_used": "deepseek/deepseek-v4-pro",
        "extraction_timestamp": "2024-01-01T00:00:00",
        "total_net_proceeds_hkd_million": total,
        "currency": "HKD",
        "uses": [
            {
                "use_id": "use_001",
                "parent_id": None,
                "category": "R&D and technology",
                "category_proposed": None,
                "category_raw": "upgrade technology",
                "amount_hkd_million": round(total * 0.35, 2),
                "percentage": 35.0,
                "description": "Tech upgrades and R&D.",
                "source_text": "approximately 35%...",
            },
            {
                "use_id": "use_002",
                "parent_id": None,
                "category": "Product development",
                "category_proposed": None,
                "category_raw": "develop new services and products",
                "amount_hkd_million": round(total * 0.35, 2),
                "percentage": 35.0,
                "description": "New services and products.",
                "source_text": "approximately 35%...",
            },
            {
                "use_id": "use_003",
                "parent_id": None,
                "category": "Acquisitions and investments",
                "category_proposed": None,
                "category_raw": "acquisitions or investments",
                "amount_hkd_million": round(total * 0.20, 2),
                "percentage": 20.0,
                "description": "Selective acquisitions.",
                "source_text": "approximately 20%...",
            },
            {
                "use_id": "use_004",
                "parent_id": None,
                "category": "Working capital",
                "category_proposed": None,
                "category_raw": "working capital and general corporate purposes",
                "amount_hkd_million": round(total * 0.10, 2),
                "percentage": 10.0,
                "description": "Working capital.",
                "source_text": "approximately 10%...",
            },
        ],
        "validation_preview": {
            "percentage_sum": 100.0,
            "top_level_count": 4,
            "total_items_count": 4,
        },
    }


# ── Tests: CATEGORY_L2 ────────────────────────────────────────────────────────

class TestCategoryL2:
    def test_has_exactly_8_entries(self):
        assert len(CATEGORY_L2) == 8

    def test_contains_expected_categories(self):
        expected = {
            "R&D and technology",
            "Product development",
            "Sales and marketing",
            "Manufacturing expansion",
            "Production capacity",
            "Working capital",
            "Acquisitions and investments",
            "Overseas expansion",
        }
        assert set(CATEGORY_L2) == expected

    def test_no_duplicates(self):
        assert len(CATEGORY_L2) == len(set(CATEGORY_L2))


# ── Tests: CATEGORY_L1_MAP ───────────────────────────────────────────────────

class TestCategoryL1Map:
    def test_all_l2_categories_appear_in_map_keys(self):
        for l2 in CATEGORY_L2:
            assert l2 in CATEGORY_L1_MAP, f"{l2!r} missing from CATEGORY_L1_MAP"

    def test_map_has_exactly_8_entries(self):
        assert len(CATEGORY_L1_MAP) == 8

    def test_values_are_valid_l1_labels(self):
        valid_l1 = {
            "Growth & Expansion",
            "Technology & Product",
            "Commercial",
            "Corporate",
        }
        for l2, l1 in CATEGORY_L1_MAP.items():
            assert l1 in valid_l1, f"L1 label {l1!r} for {l2!r} is not a known L1"

    def test_growth_expansion_entries(self):
        assert CATEGORY_L1_MAP["Overseas expansion"] == "Growth & Expansion"
        assert CATEGORY_L1_MAP["Manufacturing expansion"] == "Growth & Expansion"
        assert CATEGORY_L1_MAP["Production capacity"] == "Growth & Expansion"
        assert CATEGORY_L1_MAP["Acquisitions and investments"] == "Growth & Expansion"

    def test_technology_product_entries(self):
        assert CATEGORY_L1_MAP["R&D and technology"] == "Technology & Product"
        assert CATEGORY_L1_MAP["Product development"] == "Technology & Product"

    def test_commercial_entry(self):
        assert CATEGORY_L1_MAP["Sales and marketing"] == "Commercial"

    def test_corporate_entry(self):
        assert CATEGORY_L1_MAP["Working capital"] == "Corporate"


# ── Tests: validate_extraction ────────────────────────────────────────────────

class TestValidateExtraction:
    def test_passes_on_valid_meituan_dict(self):
        data = _valid_meituan_dict()
        result = validate_extraction(data)
        assert isinstance(result, ExtractionRecord)
        assert result.hk_ticker == "3690"
        assert len(result.uses) == 4

    def test_raises_validation_error_when_category_is_invalid(self):
        data = _valid_meituan_dict()
        data["uses"][0]["category"] = "NotACategory"
        data["uses"][0]["category_proposed"] = None  # must be absent for validation to fire
        with pytest.raises(ValidationError):
            validate_extraction(data)

    def test_returns_extraction_record_instance(self):
        data = _valid_meituan_dict()
        result = validate_extraction(data)
        assert isinstance(result, ExtractionRecord)


# ── Tests: UseItem ────────────────────────────────────────────────────────────

class TestUseItem:
    def _valid_use(self, **overrides) -> dict:
        base = {
            "use_id": "use_001",
            "parent_id": None,
            "category": "Working capital",
            "category_proposed": None,
            "category_raw": "working capital",
            "amount_hkd_million": 1000.0,
            "percentage": 10.0,
            "description": "General working capital.",
            "source_text": "approximately 10%...",
        }
        base.update(overrides)
        return base

    def test_rejects_unknown_category_when_category_proposed_is_absent(self):
        """category not in CATEGORY_L2 without category_proposed → ValidationError."""
        data = self._valid_use(category="Completely made up", category_proposed=None)
        with pytest.raises(ValidationError) as exc_info:
            UseItem.model_validate(data)
        assert "CATEGORY_L2" in str(exc_info.value) or "not in" in str(exc_info.value)

    def test_accepts_none_category_when_category_proposed_is_set(self):
        """category=None with category_proposed set → allowed (intentional no-match)."""
        data = self._valid_use(category=None, category_proposed="Some novel use")
        item = UseItem.model_validate(data)
        assert item.category is None
        assert item.category_proposed == "Some novel use"

    def test_accepts_valid_category_without_proposed(self):
        data = self._valid_use(category="R&D and technology", category_proposed=None)
        item = UseItem.model_validate(data)
        assert item.category == "R&D and technology"

    def test_accepts_valid_category_with_proposed(self):
        """Closest-match label + proposed label → both accepted."""
        data = self._valid_use(
            category="Working capital",
            category_proposed="IPO expenses and listing costs",
        )
        item = UseItem.model_validate(data)
        assert item.category == "Working capital"
        assert item.category_proposed == "IPO expenses and listing costs"

    def test_all_l2_categories_are_accepted(self):
        from hk_ipo.schema import CATEGORY_L2
        for cat in CATEGORY_L2:
            data = self._valid_use(category=cat, category_proposed=None)
            item = UseItem.model_validate(data)
            assert item.category == cat
