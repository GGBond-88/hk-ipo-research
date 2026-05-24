"""Unit tests for src/hk_ipo/enrichments/specificity.py."""

from __future__ import annotations

import json
from pathlib import Path


def test_dimension_and_version():
    from hk_ipo.enrichments.specificity import DIMENSION, VERSION

    assert DIMENSION == "specificity"
    assert isinstance(VERSION, int)


def test_specific_has_concrete_details():
    from hk_ipo.enrichments.specificity import classify_specificity

    item = {
        "description": "Construct a 200,000 sq ft semiconductor fabrication "
        "plant in Shenzhen with 5 production lines by Q4 2025.",
        "source_text": "We will invest HK$500 million to construct a 200,000 sq ft...",
    }
    assert classify_specificity(item) == "specific"


def test_general_has_non_concrete_description():
    from hk_ipo.enrichments.specificity import classify_specificity

    item = {
        "description": "For general working capital purposes.",
        "source_text": "Approximately 10% will be used for general working capital.",
    }
    assert classify_specificity(item) == "general"


def test_vague_is_very_unspecific():
    from hk_ipo.enrichments.specificity import classify_specificity

    item = {
        "description": "",
        "source_text": "",
    }
    assert classify_specificity(item) == "vague"


def test_run_integrates(tmp_path: Path):
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.specificity import run as spec_run

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
                "description": "Build a specific factory at a specific address.",
                "category_raw": "factory",
                "percentage": 100.0,
                "source_text": "We will build a factory at 123 Main Street.",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    spec_run(cat, enr, ticker="01234")
    loaded = json.loads((enr / "01234.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["specificity"]
    assert block["version"] >= 1
    assert block["by_use_id"]["use_001"] in ("specific", "general", "vague")


# ── CR-004: all_files, force, idempotency, and _enrich_one direct call ──────


def test_specificity_idempotent(tmp_path: Path):
    """Re-running with same inputs must return the same block."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.specificity import run as spec_run

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
                "category_raw": "R&D",
                "description": "R&D",
                "percentage": 100.0,
                "source_text": "We will do R&D.",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    first = spec_run(cat, enr, ticker="01234")
    second = spec_run(cat, enr, ticker="01234")
    assert first == second


def test_specificity_force_reprocesses(tmp_path: Path):
    """force=True must re-process even when enrichments already exist."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.specificity import run as spec_run

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
                "category_raw": "R&D",
                "description": "R&D",
                "percentage": 100.0,
                "source_text": "We will do R&D.",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")

    # First run: no enrichments yet
    first = spec_run(cat, enr, ticker="01234")
    assert first is not None

    # Second run with force=True: must return a block (not None from early exit)
    second = spec_run(cat, enr, ticker="01234", force=True)
    assert second is not None
    assert second["version"] >= 1
    assert "use_001" in second["by_use_id"]


def test_specificity_all_files_returns_results(tmp_path: Path):
    """all_files=True must return a dict keyed by ticker, not None."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.specificity import run as spec_run

    cat = tmp_path / "categorized"
    cat.mkdir()
    enr = tmp_path / "enriched"
    enr.mkdir()
    for i, ticker in enumerate(("01234", "05678"), start=1):
        record = {
            "hk_ticker": ticker,
            "company_name_en": f"Corp {i}",
            "schema_version": "2.0",
            "uses": [
                {
                    "use_id": f"use_{i:03d}",
                    "description": "Build a factory at 123 Main St.",
                    "category_raw": "factory",
                    "percentage": 100.0,
                    "source_text": "Build a factory at 123 Main Street.",
                }
            ],
            "enrichments": {},
        }
        save_enriched(record, cat, ticker)

    results = spec_run(cat, enr, all_files=True)
    assert isinstance(results, dict)
    assert len(results) == 2
    assert "01234" in results
    assert "05678" in results
    assert (enr / "01234.json").exists()
    assert (enr / "05678.json").exists()


def test_specificity_all_files_falls_back_empty_enriched(tmp_path: Path):
    """all_files must fall back to categorized_dir when enriched_dir has no JSON files."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.specificity import run as spec_run

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
                "description": "Build a factory at 123 Main St.",
                "category_raw": "factory",
                "percentage": 100.0,
                "source_text": "Build a factory at 123 Main Street.",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")

    results = spec_run(cat, enr, all_files=True)
    assert isinstance(results, dict)
    assert len(results) == 1


# ── CR-001: _enrich_one is module-level and directly testable ────────────────


def test_enrich_one_directly_callable(tmp_path: Path):
    """_enrich_one must be a module-level function callable without run()."""
    from hk_ipo.enrichments.specificity import _enrich_one

    enr = tmp_path / "enriched"
    enr.mkdir()
    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Construct a 200,000 sq ft factory in Q1 2025.",
                "category_raw": "factory construction",
                "percentage": 100.0,
                "source_text": "We will construct a factory.",
            }
        ],
        "enrichments": {},
    }
    block = _enrich_one(record, enr)
    assert block["version"] >= 1
    assert block["by_use_id"]["use_001"] in ("specific", "general", "vague")


# ── CR-003: regex boundary accuracy ─────────────────────────────────────────


def test_specificity_no_false_positive_substring():
    """Substring matches without word boundaries must not produce false classification."""
    from hk_ipo.enrichments.specificity import classify_specificity

    # "independent\s*third" pattern had no boundaries — make sure "xindependent thirdy"
    # or similar embedded matches don't trigger (this text has no real specificity)
    item = {
        "description": "The xindependent thirdy project will proceed.",
        "source_text": "We are working on xindependent thirdy project.",
    }
    result = classify_specificity(item)
    assert result in ("general", "vague"), f"Expected general/vague, got {result}"

    # "contingentx" must not match the tightened _GENERAL_MARKERS regex;
    # "contingentx" is not a valid English word and should not trigger "general"
    item2 = {
        "description": "The contingentx fund is used for operations.",
        "source_text": "",
    }
    result2 = classify_specificity(item2)
    assert result2 == "vague", f"Expected vague, got {result2}"

    # But proper "contingency" / "contingent" / "contingencies" should still match (general)
    item3 = {
        "description": "For contingent liabilities and general corporate purposes.",
        "source_text": "",
    }
    assert classify_specificity(item3) == "general"

    # And "independent third party" should still trigger specific when paired
    # with other evidence (single match alone may not hit the threshold)
    item4 = {
        "description": "Certified by independent third party inspectors with a Q4 2025 timeline.",
        "source_text": "",
    }
    assert classify_specificity(item4) == "specific"

    # CR-008: proprietary, patent, certification must have word boundaries
    # "patently" should not match "patent" as a substring
    item5 = {
        "description": "It is patently obvious that this is a routine project.",
        "source_text": "",
    }
    result5 = classify_specificity(item5)
    assert result5 in ("general", "vague"), f"Expected general/vague for 'patently', got {result5}"

    # "xproprietaryy" should not match "proprietary" as a substring
    item6 = {
        "description": "The xproprietaryy technology is used.",
        "source_text": "",
    }
    result6 = classify_specificity(item6)
    assert result6 in ("general", "vague"), (
        f"Expected general/vague for 'xproprietaryy', got {result6}"
    )

    # "xcertificationy" should not match "certification" as a substring
    item7 = {
        "description": "The xcertificationy process is underway.",
        "source_text": "",
    }
    result7 = classify_specificity(item7)
    assert result7 in ("general", "vague"), (
        f"Expected general/vague for 'xcertificationy', got {result7}"
    )


# ── CR-015: KeyError guard on missing use_id ──────────────────────────────


def test_missing_use_id_no_key_error():
    """_enrich_one must not raise KeyError when a use item is missing use_id."""
    import shutil
    import tempfile
    from pathlib import Path

    from hk_ipo.enrichments.specificity import _enrich_one

    record = {
        "hk_ticker": "TEST01",
        "uses": [
            {
                "description": "Build a factory at 123 Main St.",
                "category_raw": "",
                "source_text": "",
            },
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
    from hk_ipo.enrichments.specificity import classify_specificity

    item_none = {"description": None, "source_text": None}
    item_empty = {"description": "", "source_text": ""}
    assert classify_specificity(item_none) == classify_specificity(item_empty)


# ── CR-002: CLI single-file path must preserve prior enrichment blocks ──


def test_cli_preserves_prior_enrichments(tmp_path: Path, monkeypatch) -> None:
    """CLI single-file path must not silently drop prior enrichment blocks.

    If enriched data already exists for the ticker, the CLI must load from
    enriched_dir to preserve prior enrichment blocks (geo, country, etc.).
    Without this fix, running specificity CLI on a single file after other
    enrichments have run would silently discard all prior blocks.
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

    ticker = "07890"

    # Step 1: Write a raw categorized record (no enrichments)
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Q4 2025 timeline for Phase 1 floor 3 construction with proprietary technology certification.",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "Q4 2025 Phase 1 floor 3 construction",
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
                "description": "Q4 2025 timeline for Phase 1 floor 3 construction with proprietary technology certification.",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "Q4 2025 Phase 1 floor 3 construction",
            },
        ],
        "enrichments": {
            "geo": {"version": 1, "by_use_id": {"use_001": "domestic_hk"}},
        },
    }
    enr_file = enr_dir / f"{ticker}.json"
    enr_file.write_text(_json.dumps(enriched_record), encoding="utf-8")

    # Step 3: Run CLI with the categorized file path — must load from
    # enriched_dir (which already exists) to preserve prior geo enrichment.
    cat_input_file = tmp_path / "input.json"
    cat_input_file.write_text(_json.dumps(raw_record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["specificity", str(cat_input_file)]
    try:
        runpy.run_module("hk_ipo.enrichments.specificity", run_name="__main__")
    finally:
        sys.argv = old_argv

    # Step 4: Verify that prior enrichment (geo) was preserved
    result = _json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in result["enrichments"], (
        "CR-002 regression: prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert result["enrichments"]["geo"]["by_use_id"]["use_001"] == "domestic_hk"
    assert "specificity" in result["enrichments"], "specificity enrichment must also be present"
