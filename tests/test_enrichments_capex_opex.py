"""Unit tests for src/hk_ipo/enrichments/capex_opex.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_dimension_and_version():
    from hk_ipo.enrichments.capex_opex import DIMENSION, VERSION

    assert DIMENSION == "capex_opex"
    assert isinstance(VERSION, int)
    assert VERSION >= 1


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


# ── CR-001: single-ticker path must not drop prior enrichment data ────────


def test_capex_opex_preserves_prior_enrichments(tmp_path: Path):
    """Single-ticker path must load from enriched_dir when available.

    Bug: calling run() with a ticker that already has enriched data would
    load from categorized_dir only, silently losing prior enrichment blocks
    (geo, country, etc.) when saving back to enriched_dir.
    """
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.capex_opex import run as capex_opex_run

    cat = tmp_path / "categorized"
    cat.mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()

    # Raw categorized record (no enrichments)
    raw_record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build a factory",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory.",
            },
        ],
    }
    save_enriched(raw_record, cat, "01234")

    # Simulate that another enrichment (e.g., geo) has already run
    enriched_record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build a factory",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory.",
            },
        ],
        "enrichments": {
            "geo": {"version": 1, "by_use_id": {"use_001": "mainland"}},
        },
    }
    save_enriched(enriched_record, enr, "01234")

    # Run capex_opex for the ticker — must preserve prior enrichment data
    capex_opex_run(cat, enr, ticker="01234")

    loaded = json.loads((enr / "01234.json").read_text(encoding="utf-8"))
    assert "geo" in loaded["enrichments"], (
        "CR-001 regression: prior 'geo' enrichment was silently dropped"
    )
    assert loaded["enrichments"]["geo"]["by_use_id"]["use_001"] == "mainland"
    assert "capex_opex" in loaded["enrichments"]


# ── CR-002: tests for run() function and CLI ───────────────────────────────


def test_capex_opex_run_integrates(tmp_path: Path):
    """run() with a single ticker must enrich and save the record."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.capex_opex import DIMENSION
    from hk_ipo.enrichments.capex_opex import run as capex_opex_run

    cat = tmp_path / "categorized"
    cat.mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()

    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build factory equipment",
                "category_raw": "factory construction",
                "percentage": 100.0,
                "source_text": "We will build a factory with equipment.",
            },
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")

    capex_opex_run(cat, enr, ticker="01234")

    loaded = json.loads((enr / "01234.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"][DIMENSION]
    assert block["version"] >= 1
    assert block["by_use_id"]["use_001"] == "capex"


def test_capex_opex_idempotent(tmp_path: Path):
    """Re-running run() with same inputs must produce the same result."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.capex_opex import run as capex_opex_run

    cat = tmp_path / "categorized"
    cat.mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()

    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Working capital",
                "category_raw": "working capital",
                "percentage": 100.0,
                "source_text": "For working capital.",
            },
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")

    first = capex_opex_run(cat, enr, ticker="01234")
    second = capex_opex_run(cat, enr, ticker="01234")
    assert first == second


def test_capex_opex_all_files(tmp_path: Path):
    """run(all_files=True) must process all tickers and return results."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.capex_opex import run as capex_opex_run

    cat = tmp_path / "categorized"
    cat.mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()

    for tk in ("01234", "05678"):
        record = {
            "hk_ticker": tk,
            "company_name_en": f"Co {tk}",
            "schema_version": "2.0",
            "uses": [
                {
                    "use_id": "use_001",
                    "description": "Build factory",
                    "category_raw": "factory construction",
                    "percentage": 100.0,
                    "source_text": "We will build a factory.",
                },
            ],
            "enrichments": {},
        }
        save_enriched(record, cat, tk)

    results = capex_opex_run(cat, enr, all_files=True)
    assert isinstance(results, dict)
    assert set(results.keys()) == {"01234", "05678"}
    assert (enr / "01234.json").exists()
    assert (enr / "05678.json").exists()
    assert results["01234"]["by_use_id"]["use_001"] == "capex"


def test_capex_opex_all_files_falls_back_empty_enriched(tmp_path: Path):
    """all_files must fall back to categorized_dir when enriched_dir is empty."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.capex_opex import run as capex_opex_run

    cat = tmp_path / "categorized"
    cat.mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()  # exists but empty

    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Buy equipment",
                "category_raw": "equipment purchase",
                "percentage": 100.0,
                "source_text": "We will buy equipment.",
            },
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")

    results = capex_opex_run(cat, enr, all_files=True)
    assert isinstance(results, dict)
    assert len(results) == 1
    assert results["01234"]["by_use_id"]["use_001"] == "capex"


# ── CR-003: morphological variant gaps ──────────────────────────────────────
# Each test isolates a single morphological variant so that the target word
# is the ONLY keyword match across all three categories.  Failure mode: the
# bare-stem regex misses the inflected form and the default "capex" is returned
# (or a wrong category is matched by an unintended keyword leak).


def test_financial_repayment_morphology():
    """repayment must match financial (bare stem \brepay\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "repayment plan",
                "category_raw": "use of funds",
                "source_text": "For the repayment plan.",
            }
        )
        == "financial"
    )


def test_financial_repaying_morphology():
    """repaying must match financial (bare stem \brepay\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "repaying creditors",
                "category_raw": "use of funds",
                "source_text": "For repaying existing creditors.",
            }
        )
        == "financial"
    )


def test_financial_bonds_plural():
    """bonds must match financial (bare stem \bbond\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "corporate bonds",
                "category_raw": "fund utilization",
                "source_text": "To issue corporate bonds.",
            }
        )
        == "financial"
    )


def test_financial_refinancing():
    """refinancing must match financial (bare stem \brefinanc\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "refinancing plan",
                "category_raw": "use of proceeds",
                "source_text": "For refinancing purposes.",
            }
        )
        == "financial"
    )


def test_capex_facility_morphology():
    """facility / facilities must match capex (bare stem \bfacilit\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "storage facilities",
                "category_raw": "logistics",
                "source_text": "To develop storage facilities.",
            }
        )
        == "capex"
    )


def test_financial_loans_plural():
    """loans must match financial (bare stem \bloan\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "outstanding loans",
                "category_raw": "funding allocation",
                "source_text": "To settle outstanding loans.",
            }
        )
        == "financial"
    )


def test_financial_leveraged():
    """leveraged must match financial (bare stem \bleverage\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "leveraged structure",
                "category_raw": "funding",
                "source_text": "A leveraged capital structure.",
            }
        )
        == "financial"
    )


def test_capex_buildings():
    """buildings must match capex (bare stem \bbuild\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "office buildings",
                "category_raw": "development",
                "source_text": "To develop office buildings.",
            }
        )
        == "capex"
    )


def test_capex_acquiring():
    """acquiring must match capex (bare stem \bacqui\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "acquiring technology",
                "category_raw": "development",
                "source_text": "For acquiring technology.",
            }
        )
        == "capex"
    )


def test_capex_purchasing():
    """purchasing must match capex (bare stem \bpurchase\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "purchasing technology",
                "category_raw": "procurement",
                "source_text": "For purchasing technology assets.",
            }
        )
        == "capex"
    )


def test_capex_renovating():
    """renovating must match capex (bare stem \brenovation\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "renovating premises",
                "category_raw": "development",
                "source_text": "For renovating company premises.",
            }
        )
        == "capex"
    )


def test_opex_salaries():
    """salaries must match opex (bare stem \bsalary\b cannot)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "staff salaries",
                "category_raw": "compensation",
                "source_text": "To pay staff salaries.",
            }
        )
        == "opex"
    )


def test_capex_opex_enrich_one_callable(tmp_path: Path):
    """_enrich_one must be a module-level function callable without run()."""
    from hk_ipo.enrichments.capex_opex import _enrich_one

    enr = tmp_path / "enriched"
    enr.mkdir()
    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Repay bank loan",
                "category_raw": "debt repayment",
                "percentage": 100.0,
                "source_text": "We will repay our bank loan.",
            },
        ],
        "enrichments": {},
    }
    block = _enrich_one(record, enr)
    assert block["version"] >= 1
    assert block["by_use_id"]["use_001"] == "financial"


# ── CR-004: multi-word regex final-word plural gaps ────────────────────────
# Each test isolates a multi-word keyword whose final word can pluralize.
# The original regexes required a \b word boundary immediately after the
# singular form, causing a miss when the final word is pluralized
# (e.g. "operating expenses", "marketing campaigns", "data centers").
# Texts are carefully crafted so the target phrase is the ONLY keyword
# across all three categories — a wrong classification reveals the gap.


def test_opex_operating_expenses_plural():
    """operating expenses must match opex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "operating expenses" — no opex catch-all like "general purposes".
    assert (
        classify_capex_opex(
            {
                "description": "cover operating expenses",
                "category_raw": "fund allocation",
                "source_text": "The proceeds will cover operating expenses for the firm.",
            }
        )
        == "opex"
    )


def test_opex_marketing_campaigns_plural():
    """marketing campaigns must match opex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    assert (
        classify_capex_opex(
            {
                "description": "marketing campaigns",
                "category_raw": "promotion",
                "source_text": "Funds allocated to marketing campaigns for our products.",
            }
        )
        == "opex"
    )


def test_capex_data_centers_plural():
    """data centers must match capex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "data centers" — remove "build", "develop", "infrastructure".
    assert (
        classify_capex_opex(
            {
                "description": "data centers",
                "category_raw": "technology program",
                "source_text": "The firm will set up new data centers for the region.",
            }
        )
        == "capex"
    )


def test_capex_buildings_regex_actually_matches():
    """buildings must match capex (previous regex build(ing|s)? could not)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "buildings" — no construct/equipment/infrastructure/etc.
    # Pre-fix this returns capex via default fallback (regex never actually
    # matched "buildings").  Post-fix the capex regex must actively match.
    assert (
        classify_capex_opex(
            {
                "description": "office buildings project",
                "category_raw": "development plan",
                "source_text": "To pursue an office buildings initiative.",
            }
        )
        == "capex"
    )


def test_opex_sales_forces_plural():
    """sales forces must match opex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "sales forces" — remove "expand" (capex keyword).
    assert (
        classify_capex_opex(
            {
                "description": "sales forces",
                "category_raw": "operations plan",
                "source_text": "To strengthen our sales forces across regions.",
            }
        )
        == "opex"
    )


def test_opex_sales_teams_plural():
    """sales teams must match opex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "sales teams" — remove "hiring" (opex keyword).
    assert (
        classify_capex_opex(
            {
                "description": "sales teams",
                "category_raw": "operations plan",
                "source_text": "To organize new sales teams for our products.",
            }
        )
        == "opex"
    )


def test_capex_new_stores_plural():
    """new stores must match capex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "new stores" — remove "expansion" (capex keyword).
    assert (
        classify_capex_opex(
            {
                "description": "new stores",
                "category_raw": "growth plan",
                "source_text": "To open new stores across the market.",
            }
        )
        == "capex"
    )


def test_capex_new_branches_plural():
    """new branches must match capex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "new branches" — remove "expansion".
    assert (
        classify_capex_opex(
            {
                "description": "new branches",
                "category_raw": "growth plan",
                "source_text": "For opening new branches across the region.",
            }
        )
        == "capex"
    )


def test_capex_new_offices_plural():
    """new offices must match capex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "new offices" — remove "expansion".
    assert (
        classify_capex_opex(
            {
                "description": "new offices",
                "category_raw": "growth plan",
                "source_text": "For opening new offices across the city.",
            }
        )
        == "capex"
    )


def test_capex_manufacturing_plants_plural():
    """manufacturing plants must match capex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "manufacturing plants" — remove "construct", "facility".
    assert (
        classify_capex_opex(
            {
                "description": "manufacturing plants",
                "category_raw": "production plan",
                "source_text": "To establish manufacturing plants for our products.",
            }
        )
        == "capex"
    )


def test_capex_manufacturing_lines_plural():
    """manufacturing lines must match capex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "manufacturing lines" — remove "facility".
    assert (
        classify_capex_opex(
            {
                "description": "manufacturing lines",
                "category_raw": "production plan",
                "source_text": "To establish manufacturing lines for the company.",
            }
        )
        == "capex"
    )


def test_capex_r_and_d_centers_plural():
    """R&D centers must match capex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "R&D centers" — remove "build".
    assert (
        classify_capex_opex(
            {
                "description": "R&D centers",
                "category_raw": "research plan",
                "source_text": "To set up new R&D centers for our research programs.",
            }
        )
        == "capex"
    )


def test_capex_r_and_d_labs_plural():
    """R&D labs must match capex (singular regex misses plural)."""
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    # Isolate "R&D labs" — remove "develop".
    assert (
        classify_capex_opex(
            {
                "description": "R&D labs",
                "category_raw": "research plan",
                "source_text": "To set up R&D labs for the firm.",
            }
        )
        == "capex"
    )


# ── CR-005: fit-out multi-word final-plural gap ─────────────────────────────


def test_capex_fit_outs_hyphen_plural():
    """fit-outs (hyphenated plural) must match capex."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW, classify_capex_opex

    # Isolate "fit-outs" — remove "renovation", "construction", etc.
    assert (
        classify_capex_opex(
            {
                "description": "retail fit-outs",
                "category_raw": "interior works",
                "source_text": "For the completion of retail fit-outs.",
            }
        )
        == "capex"
    )
    assert _CAPEX_KW.search("fit-outs") is not None  # CR-007: verify active match


def test_capex_fit_outs_space_plural():
    """fit outs (space-separated plural) must match capex."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW, classify_capex_opex

    # Isolate "fit outs" — remove "renovation", "construction", etc.
    assert (
        classify_capex_opex(
            {
                "description": "office fit outs",
                "category_raw": "interior works",
                "source_text": "For completing office fit outs.",
            }
        )
        == "capex"
    )
    assert _CAPEX_KW.search("fit outs") is not None  # CR-007: verify active match


# ── CR-006: installations plural gap ────────────────────────────────────────


def test_capex_installations_plural():
    """installations must match capex (installation+s plural missing)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW, classify_capex_opex

    # Isolate "installations" — remove "equipment", "machinery", etc.
    assert (
        classify_capex_opex(
            {
                "description": "new installations",
                "category_raw": "asset program",
                "source_text": "For new installations at our sites.",
            }
        )
        == "capex"
    )
    assert _CAPEX_KW.search("installations") is not None  # CR-007: verify active match


# ── CR-007: CAPEX regex match verification (prevent default-fallback passes) ─


def test_capex_regex_actively_matches_buildings():
    """_CAPEX_KW must actively match 'buildings' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("buildings") is not None


def test_capex_regex_actively_matches_facility():
    """_CAPEX_KW must actively match 'facility' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("facility") is not None


def test_capex_regex_actively_matches_facilities():
    """_CAPEX_KW must actively match 'facilities' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("facilities") is not None


def test_capex_regex_actively_matches_acquiring():
    """_CAPEX_KW must actively match 'acquiring' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("acquiring") is not None


def test_capex_regex_actively_matches_purchasing():
    """_CAPEX_KW must actively match 'purchasing' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("purchasing") is not None


def test_capex_regex_actively_matches_renovating():
    """_CAPEX_KW must actively match 'renovating' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("renovating") is not None


def test_capex_regex_actively_matches_data_centers():
    """_CAPEX_KW must actively match 'data centers' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("data centers") is not None


def test_capex_regex_actively_matches_new_stores():
    """_CAPEX_KW must actively match 'new stores' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("new stores") is not None


def test_capex_regex_actively_matches_new_branches():
    """_CAPEX_KW must actively match 'new branches' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("new branches") is not None


def test_capex_regex_actively_matches_new_offices():
    """_CAPEX_KW must actively match 'new offices' (not just default fallback)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("new offices") is not None


def test_capex_regex_actively_matches_manufacturing_plants():
    """_CAPEX_KW must actively match 'manufacturing plants'."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("manufacturing plants") is not None


def test_capex_regex_actively_matches_manufacturing_lines():
    """_CAPEX_KW must actively match 'manufacturing lines'."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("manufacturing lines") is not None


def test_capex_regex_actively_matches_r_and_d_centers():
    """_CAPEX_KW must actively match 'R&D centers'."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("R&D centers") is not None


def test_capex_regex_actively_matches_r_and_d_labs():
    """_CAPEX_KW must actively match 'R&D labs'."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("R&D labs") is not None


# ── CR-008: remaining morphological gaps ──────────────────────────────────────


def test_capex_warehousing_gerund():
    """warehousing must match capex (warehouse(s|ing)? cannot backtrack)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW, classify_capex_opex

    # Isolate "warehousing" — remove "build", "facility", "construction", etc.
    text = "The project involves warehousing and logistics."
    assert _CAPEX_KW.search(text) is not None, (
        "CR-008: warehouse(s|ing)? cannot match 'warehousing' (gerund drops 'e')"
    )
    assert (
        classify_capex_opex(
            {
                "description": "warehousing project",
                "category_raw": "logistics",
                "source_text": text,
            }
        )
        == "capex"
    )


def test_opex_advertised_past():
    """advertised must match opex (advertis(e|ing|ements?)? missing 'ed')."""
    from hk_ipo.enrichments.capex_opex import _OPEX_KW, classify_capex_opex

    # Isolate "advertised" — remove "marketing", "sales", etc.
    text = "Funds were used for advertised promotions."
    assert _OPEX_KW.search(text) is not None, (
        "CR-008: advertis(e|ing|ements?)? cannot match 'advertised' (missing 'ed' alternation)"
    )
    assert (
        classify_capex_opex(
            {
                "description": "advertised promotions",
                "category_raw": "marketing spend",
                "source_text": text,
            }
        )
        == "opex"
    )


# ── CR-009: remaining morphological gaps (construct, rent, matur) ────────────


def test_capex_constructions_plural():
    """constructions must match capex (construct(ion|ing|ed|s)? cannot match
    'constructions' — requires 'ions?' alternation for two-level suffix)."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW, classify_capex_opex

    # Isolate "constructions" — remove "factory", "build", etc.
    text = "The plan covers campus constructions."
    assert _CAPEX_KW.search(text) is not None, (
        "CR-009: construct(ion|ing|ed|s)? cannot match 'constructions' "
        "(plural of construction needs two suffix levels)"
    )
    assert (
        classify_capex_opex(
            {
                "description": "campus constructions",
                "category_raw": "capital program",
                "source_text": text,
            }
        )
        == "capex"
    )


def test_opex_rentals_plural():
    """rentals must match opex (rent(al|ing|s|ed)? cannot match 'rentals'
    — requires 'als?' alternation for two-level suffix)."""
    from hk_ipo.enrichments.capex_opex import _OPEX_KW, classify_capex_opex

    # Isolate "rentals" — remove "lease", "payroll", etc.
    text = "The funds cover equipment rentals."
    assert _OPEX_KW.search(text) is not None, (
        "CR-009: rent(al|ing|s|ed)? cannot match 'rentals' "
        "(plural of rental needs two suffix levels)"
    )
    assert (
        classify_capex_opex(
            {
                "description": "equipment rentals",
                "category_raw": "operations spend",
                "source_text": text,
            }
        )
        == "opex"
    )


def test_financial_matured_morphology():
    """matured must match financial (matur(e|ing|ity) missing 'ed'
    alternation for past tense)."""
    from hk_ipo.enrichments.capex_opex import _FINANCIAL_KW, classify_capex_opex

    # Isolate "matured" — remove "debt", "loan", "bond", "note", etc.
    text = "The matured obligations require settlement."
    assert _FINANCIAL_KW.search(text) is not None, (
        "CR-009: matur(e|ing|ity) cannot match 'matured' (missing 'ed' alternation for past tense)"
    )
    assert (
        classify_capex_opex(
            {
                "description": "matured obligations",
                "category_raw": "debt service",
                "source_text": text,
            }
        )
        == "financial"
    )


# ── CR-009: regex-active guards ───────────────────────────────────────────────


def test_capex_regex_actively_matches_constructions():
    """_CAPEX_KW must actively match 'constructions'."""
    from hk_ipo.enrichments.capex_opex import _CAPEX_KW

    assert _CAPEX_KW.search("constructions") is not None


def test_opex_regex_actively_matches_rentals():
    """_OPEX_KW must actively match 'rentals'."""
    from hk_ipo.enrichments.capex_opex import _OPEX_KW

    assert _OPEX_KW.search("rentals") is not None


def test_financial_regex_actively_matches_matured():
    """_FINANCIAL_KW must actively match 'matured'."""
    from hk_ipo.enrichments.capex_opex import _FINANCIAL_KW

    assert _FINANCIAL_KW.search("matured") is not None


# ── CR-011: classification priority order ─────────────────────────────────────
# The classifier MUST respect priority: financial > opex > capex.
# When keywords from multiple categories co-occur in one item, the
# higher-priority category must win.
# These tests include CR-007 guards (regex-level assertion) for every
# keyword used, so a wrong classification cannot be masked by an
# accidental keyword leak.


def test_priority_opex_over_capex():
    """Opex keywords must override capex keywords (opex > capex)."""
    from hk_ipo.enrichments.capex_opex import (
        _CAPEX_KW,
        _OPEX_KW,
        classify_capex_opex,
    )

    # "working capital" = opex, "construct" = capex -> result must be opex
    assert _OPEX_KW.search("working capital") is not None
    assert _CAPEX_KW.search("construct") is not None
    assert (
        classify_capex_opex(
            {
                "description": "working capital for construction projects",
                "category_raw": "general purposes",
                "source_text": ("Proceeds will fund working capital and construct new facilities."),
            }
        )
        == "opex"
    )


def test_priority_financial_over_opex():
    """Financial keywords must override opex keywords (financial > opex)."""
    from hk_ipo.enrichments.capex_opex import (
        _FINANCIAL_KW,
        _OPEX_KW,
        classify_capex_opex,
    )

    # "repay loan" = financial, "working capital" = opex -> result must be financial
    assert _FINANCIAL_KW.search("repay loan") is not None
    assert _OPEX_KW.search("working capital") is not None
    assert (
        classify_capex_opex(
            {
                "description": "repay bank loan and supplement working capital",
                "category_raw": "fund allocation",
                "source_text": (
                    "Proceeds to repay outstanding bank loan and provide working capital."
                ),
            }
        )
        == "financial"
    )


def test_priority_financial_over_all():
    """Financial must override both opex and capex when all three co-occur."""
    from hk_ipo.enrichments.capex_opex import (
        _CAPEX_KW,
        _FINANCIAL_KW,
        _OPEX_KW,
        classify_capex_opex,
    )

    # "repay debt" = financial, "working capital" = opex, "construct" = capex
    assert _FINANCIAL_KW.search("repay debt") is not None
    assert _OPEX_KW.search("working capital") is not None
    assert _CAPEX_KW.search("construct") is not None
    assert (
        classify_capex_opex(
            {
                "description": "repay debt, working capital, and construct plant",
                "category_raw": "mixed allocation",
                "source_text": (
                    "Proceeds to repay existing debt, "
                    "fund working capital, and construct a new plant."
                ),
            }
        )
        == "financial"
    )


# ── CR-012: rent regex missing simple plural "rents" ─────────────────────────


def test_opex_rents_plural():
    """rents must match opex (rent(als?|ing|ed)? misses simple plural)."""
    from hk_ipo.enrichments.capex_opex import _OPEX_KW, classify_capex_opex

    # Isolate "rents" — remove "lease", "payroll", "salary", etc.
    text = "The firm pays rents for several properties."
    assert _OPEX_KW.search(text) is not None, (
        "CR-012: rent(als?|ing|ed)? cannot match 'rents' (missing simple plural alternation)"
    )
    assert (
        classify_capex_opex(
            {
                "description": "property rents",
                "category_raw": "operational costs",
                "source_text": text,
            }
        )
        == "opex"
    )


def test_opex_regex_actively_matches_rents():
    """_OPEX_KW must actively match 'rents' (CR-007 guard)."""
    from hk_ipo.enrichments.capex_opex import _OPEX_KW

    assert _OPEX_KW.search("rents") is not None


# ── CR-010: CLI __main__ entrypoint coverage ──────────────────────────────────


def test_cli_single_file_passes(tmp_path: Path, monkeypatch) -> None:
    """CLI with a single file path must enrich and save."""
    import json as _json
    import runpy
    import sys

    from hk_ipo import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CATEGORIZED_DIR", tmp_path / "categorized")

    (tmp_path / "categorized").mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()

    record: dict[str, object] = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build factory equipment",
                "category_raw": "factory construction",
                "percentage": 100.0,
                "source_text": "We will build a factory with equipment.",
            },
        ],
        "enrichments": {},
    }
    inf = tmp_path / "input.json"
    inf.write_text(_json.dumps(record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["capex_opex", str(inf)]
    try:
        runpy.run_module("hk_ipo.enrichments.capex_opex", run_name="__main__")
    finally:
        sys.argv = old_argv

    out_file = enr / "01234.json"
    assert out_file.exists(), "CLI must write enriched output"
    result: dict[str, object] = _json.loads(out_file.read_text(encoding="utf-8"))
    enrichments = result["enrichments"]  # type: ignore[index]
    assert "capex_opex" in enrichments  # type: ignore[operator]
    block = enrichments["capex_opex"]  # type: ignore[index]
    assert block["by_use_id"]["use_001"] == "capex"  # type: ignore[index]


def test_cli_missing_file_errors(tmp_path: Path, monkeypatch) -> None:
    """CLI with a nonexistent file path must print error and exit 1."""
    import runpy
    import sys

    from hk_ipo import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    (tmp_path / "enriched").mkdir()

    nonexistent = tmp_path / "nonexistent.json"

    old_argv = sys.argv.copy()
    sys.argv = ["capex_opex", str(nonexistent)]
    try:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("hk_ipo.enrichments.capex_opex", run_name="__main__")
        assert exc_info.value.code == 1, "CLI must exit with code 1 when input file not found"
    finally:
        sys.argv = old_argv


def test_cli_no_args_errors(monkeypatch) -> None:
    """CLI with no arguments must fail due to mutually-exclusive group."""
    import runpy
    import sys

    from hk_ipo import config

    monkeypatch.setattr(config, "DATA_DIR", __import__("pathlib").Path("/tmp"))

    old_argv = sys.argv.copy()
    sys.argv = ["capex_opex"]  # no positional, no --all
    try:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("hk_ipo.enrichments.capex_opex", run_name="__main__")
        assert exc_info.value.code != 0, (
            "CLI must fail when no argument provided (mutually-exclusive group)"
        )
    finally:
        sys.argv = old_argv


def test_cli_all_flag_runs(tmp_path: Path, monkeypatch) -> None:
    """CLI --all flag must process all tickers in categorized_dir."""
    import json as _json
    import runpy
    import sys

    from hk_ipo import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CATEGORIZED_DIR", tmp_path / "categorized")

    cat_dir = tmp_path / "categorized"
    cat_dir.mkdir()
    enr_dir = tmp_path / "enriched"
    enr_dir.mkdir()

    for tk in ("01234", "05678"):
        record: dict[str, object] = {
            "hk_ticker": tk,
            "company_name_en": f"Co {tk}",
            "schema_version": "2.0",
            "uses": [
                {
                    "use_id": "use_001",
                    "description": "Build factory",
                    "category_raw": "factory construction",
                    "percentage": 100.0,
                    "source_text": "We will build a factory.",
                },
            ],
            "enrichments": {},
        }
        (cat_dir / f"{tk}.json").write_text(_json.dumps(record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["capex_opex", "--all"]
    try:
        runpy.run_module("hk_ipo.enrichments.capex_opex", run_name="__main__")
    finally:
        sys.argv = old_argv

    for tk in ("01234", "05678"):
        out_path = enr_dir / f"{tk}.json"
        assert out_path.exists(), f"CLI --all must produce {tk}.json"
        result = _json.loads(out_path.read_text(encoding="utf-8"))
        assert "capex_opex" in result["enrichments"]


def test_cli_force_flag(tmp_path: Path, monkeypatch) -> None:
    """CLI --force must re-run even when existing enrichment has current version.

    CR-013: Uses version=VERSION (1) with an intentionally wrong tag ("opex"
    for a capex item).  Without --force the idempotency check would skip
    re-processing and preserve the wrong tag.  With --force the classifier
    must re-run and correct the tag to "capex".
    """
    import json as _json
    import runpy
    import sys

    from hk_ipo import config
    from hk_ipo.enrichments.capex_opex import VERSION

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CATEGORIZED_DIR", tmp_path / "categorized")

    (tmp_path / "categorized").mkdir()
    enr_dir = tmp_path / "enriched"
    enr_dir.mkdir()

    record: dict[str, object] = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build factory equipment",
                "category_raw": "factory construction",
                "percentage": 100.0,
                "source_text": "We will build a factory with equipment.",
            },
        ],
        "enrichments": {
            "capex_opex": {
                "version": VERSION,  # current version — idempotency would skip without --force
                "by_use_id": {"use_001": "opex"},  # intentionally wrong tag
            },
        },
    }
    inf = tmp_path / "input.json"
    inf.write_text(_json.dumps(record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["capex_opex", str(inf), "--force"]
    try:
        runpy.run_module("hk_ipo.enrichments.capex_opex", run_name="__main__")
    finally:
        sys.argv = old_argv

    out_file = enr_dir / "01234.json"
    assert out_file.exists()
    result = _json.loads(out_file.read_text(encoding="utf-8"))
    block = result["enrichments"]["capex_opex"]
    # force should run classify_capex_opex, which correctly tags as capex
    assert block["by_use_id"]["use_001"] == "capex", (
        "--force must re-run classifier and correct the wrong 'opex' tag"
    )
    assert block["version"] == VERSION


# ── CR-015: KeyError guard on missing use_id ──────────────────────────────


def test_missing_use_id_no_key_error():
    """_enrich_one must not raise KeyError when a use item is missing use_id."""
    import shutil
    import tempfile
    from pathlib import Path

    from hk_ipo.enrichments.capex_opex import _enrich_one

    record = {
        "hk_ticker": "TEST01",
        "uses": [
            {"description": "Build factory", "category_raw": "", "source_text": ""},
            {"use_id": "u2", "description": "general corp", "category_raw": "", "source_text": ""},
        ],
    }
    enriched_dir = Path(tempfile.mkdtemp())
    try:
        _enrich_one(record, enriched_dir)
    except KeyError:
        assert False, "should not raise KeyError for missing use_id"
    finally:
        shutil.rmtree(enriched_dir, ignore_errors=True)


# ── CR-016: None-value guard (str(item.get(key, "")) → str(item.get(key) or "")) ──


def test_none_field_values_not_injected():
    """None values must be treated as empty strings, not as literal 'None'.

    CR-016: str(item.get(key, "")) produces str(None) = "None" when key exists
    with value None. The fix: str(item.get(key) or ""). This test verifies
    that None field values produce the same classification as empty strings.
    """
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    item_none = {"description": None, "category_raw": None, "source_text": None}
    item_empty = {"description": "", "category_raw": "", "source_text": ""}
    assert classify_capex_opex(item_none) == classify_capex_opex(item_empty)


def test_none_field_values_with_real_keyword():
    """None values must not prevent matching a real keyword from another field.

    Even with description=None, a real keyword in source_text must still match.
    """
    from hk_ipo.enrichments.capex_opex import classify_capex_opex

    item = {"description": None, "category_raw": "debt repayment", "source_text": None}
    assert classify_capex_opex(item) == "financial"


# ── SR-002: CLI preserves prior enrichments ────────────────────────────────


def test_cli_preserves_prior_enrichments(tmp_path: Path, monkeypatch) -> None:
    """CLI single-file path must not silently drop prior enrichment blocks.

    SR-002 / CR-001: The CLI __main__ block was loading from the user-
    specified categorized file, bypassing the enriched_dir check that run()
    performs.  If enriched data already exists for the ticker, the CLI must
    load from enriched_dir to preserve prior enrichment blocks (geo, country,
    etc.).
    """
    import json as _json
    import runpy
    import sys

    from hk_ipo import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CATEGORIZED_DIR", tmp_path / "categorized")

    cat_dir = tmp_path / "categorized"
    cat_dir.mkdir()
    enr_dir = tmp_path / "enriched"
    enr_dir.mkdir()

    ticker = "01234"

    # Step 1: Write a raw categorized record (no enrichments)
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build a factory",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory.",
            },
        ],
    }
    cat_file = cat_dir / f"{ticker}.json"
    cat_file.write_text(_json.dumps(raw_record), encoding="utf-8")

    # Step 2: Pre-populate enriched_dir with prior enrichment (simulating
    # that another enrichment like geo has already run)
    enriched_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build a factory",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory.",
            },
        ],
        "enrichments": {
            "geo": {"version": 1, "by_use_id": {"use_001": "mainland"}},
        },
    }
    enr_file = enr_dir / f"{ticker}.json"
    enr_file.write_text(_json.dumps(enriched_record), encoding="utf-8")

    # Step 3: Run CLI with the categorized file path — must load from
    # enriched_dir (which already exists) to preserve prior geo enrichment.
    # Use the categorized file as the input path.
    input_file = tmp_path / "input.json"
    input_file.write_text(_json.dumps(raw_record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["capex_opex", str(input_file)]
    try:
        runpy.run_module("hk_ipo.enrichments.capex_opex", run_name="__main__")
    finally:
        sys.argv = old_argv

    # Step 4: Verify that prior enrichment (geo) was preserved
    result = _json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in result["enrichments"], (
        "SR-002 regression: prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert result["enrichments"]["geo"]["by_use_id"]["use_001"] == "mainland"
    assert "capex_opex" in result["enrichments"], "capex_opex enrichment must also be present"


# ── CR-013: idempotency without force ──────────────────────────────────────


def test_cli_idempotent_without_force(tmp_path: Path, monkeypatch) -> None:
    """CLI without --force must not re-process when version matches VERSION.

    CR-013 companion: With version == VERSION and a correct tag already
    persisted in enriched_dir, running the CLI without --force must
    preserve the block unchanged — the idempotency check prevents
    re-processing.  This verifies that --force semantics are isolated
    (the idempotency check, not a version mismatch, controls the
    decision).
    """
    import json as _json
    import runpy
    import sys

    from hk_ipo import config
    from hk_ipo.enrichments.capex_opex import VERSION

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CATEGORIZED_DIR", tmp_path / "categorized")

    (tmp_path / "categorized").mkdir()
    enr_dir = tmp_path / "enriched"
    enr_dir.mkdir()

    # Pre-populate enriched_dir with a record that has capex_opex at the
    # current version.  The idempotency check must skip re-processing.
    enriched_record: dict[str, object] = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "General working capital",
                "category_raw": "working capital",
                "percentage": 100.0,
                "source_text": "For general working capital and opex.",
            },
        ],
        "enrichments": {
            "capex_opex": {
                "version": VERSION,
                "by_use_id": {"use_001": "opex"},  # correct tag
            },
        },
    }
    enr_file = enr_dir / "01234.json"
    enr_file.write_text(_json.dumps(enriched_record), encoding="utf-8")

    # Write a categorized record WITHOUT capex_opex enrichment.
    # SR-002 fix: CLI loads from enriched_dir because enriched file
    # already exists.
    raw_record: dict[str, object] = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "General working capital",
                "category_raw": "working capital",
                "percentage": 100.0,
                "source_text": "For general working capital and opex.",
            },
        ],
    }
    inf = tmp_path / "input.json"
    inf.write_text(_json.dumps(raw_record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["capex_opex", str(inf)]  # no --force
    try:
        runpy.run_module("hk_ipo.enrichments.capex_opex", run_name="__main__")
    finally:
        sys.argv = old_argv

    # After CLI run, the enriched file must still contain the original
    # block — the idempotency check prevents re-processing and the
    # result is saved via _enrich_one even on the idempotency path
    # (the record was loaded from enriched_dir, processed, and
    # re-saved with the same content).
    result = _json.loads(enr_file.read_text(encoding="utf-8"))
    block = result["enrichments"]["capex_opex"]
    # Without --force and with version == VERSION, the block must be
    # preserved as-is — the classifier must not re-run.
    assert block["by_use_id"]["use_001"] == "opex", (
        "Without --force, existing correct tag must be preserved"
    )
    assert block["version"] == VERSION, "Without --force, version must be unchanged"
