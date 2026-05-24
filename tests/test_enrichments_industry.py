"""Unit tests for src/hk_ipo/enrichments/industry.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_industry_dimension_and_version():
    from hk_ipo.enrichments.industry import DIMENSION, VERSION

    assert DIMENSION == "industry"
    assert isinstance(VERSION, int)
    assert VERSION >= 1


def test_manual_override_loads_csv(tmp_path: Path):
    from hk_ipo.enrichments.industry import load_manual_overrides

    csv_path = tmp_path / "overrides.csv"
    csv_path.write_text(
        "ticker,industry\n01234,Software & Services\n03690,Retailing\n", encoding="utf-8"
    )
    overrides = load_manual_overrides(csv_path)
    assert overrides["01234"] == "Software & Services"
    assert overrides["03690"] == "Retailing"


def test_manual_override_no_csv_returns_empty():
    from hk_ipo.enrichments.industry import load_manual_overrides

    overrides = load_manual_overrides(Path("/nonexistent/file.csv"))
    assert overrides == {}


def test_run_manual_source_uses_override(tmp_path: Path):
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.industry import _enrich_one

    cat = tmp_path / "categorized"
    cat.mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()
    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    block = _enrich_one(record, enr, force=True, manual_overrides={"01234": "Software & Services"})
    assert block["primary"] == "Software & Services"
    assert block.get("source") == "manual"


def test_industry_block_shape():
    from hk_ipo.enrichments.industry import DIMENSION

    # The block must have version, primary, source fields
    assert DIMENSION == "industry"


# ── Task 020 CR-005 ───────────────────────────────────────────────────────


def test_run_all_files_returns_dict_not_none(tmp_path: Path):
    """industry.run(all_files=True) must return a dict keyed by ticker,
    matching the contract of all other enrichment modules (geo, country, etc.).
    Returning None prevents the orchestrator from distinguishing ok vs failed."""
    from hk_ipo.enrichments import industry
    from hk_ipo.enrichments.base import save_enriched

    cat = tmp_path / "categorized"
    cat.mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()

    record_a = {
        "hk_ticker": "00001",
        "company_name_en": "Alpha",
        "schema_version": "2.0",
        "uses": [
            {
                "description": "R&D for AI platform",
                "category_raw": "tech",
                "source_text": "invest in AI",
            }
        ],
        "enrichments": {},
    }
    record_b = {
        "hk_ticker": "00002",
        "company_name_en": "Beta",
        "schema_version": "2.0",
        "uses": [
            {
                "description": "Expand retail network",
                "category_raw": "retail",
                "source_text": "open new stores",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record_a, cat, "00001")
    save_enriched(record_b, cat, "00002")

    with patch("hk_ipo.enrichments.industry._classify_via_llm") as mock_llm:
        mock_llm.side_effect = ["Software & Services", "Retailing"]
        results = industry.run(cat, enr, all_files=True, force=True)

    assert isinstance(results, dict), f"Expected dict, got {type(results).__name__}"
    assert len(results) == 2
    assert "00001" in results
    assert "00002" in results
    assert results["00001"]["primary"] == "Software & Services"
    assert results["00002"]["primary"] == "Retailing"
