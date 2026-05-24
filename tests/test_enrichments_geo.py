"""Unit tests for src/hk_ipo/enrichments/geo.py — geographic scope tag."""

from __future__ import annotations

from pathlib import Path


def test_geo_dimension_and_version():
    from hk_ipo.enrichments.geo import DIMENSION, VERSION

    assert DIMENSION == "geo"
    assert isinstance(VERSION, int)
    assert VERSION >= 1


def test_geo_classify_all_domestic():
    from hk_ipo.enrichments.geo import classify_geo

    result = classify_geo(
        item={
            "description": "Expand our Hong Kong office.",
            "category_raw": "Hong Kong office expansion",
            "source_text": "We will expand our Hong Kong office.",
        },
        company_name="Example HK Holdings Ltd.",
    )
    assert result == "domestic_hk"


def test_geo_classify_mainland():
    from hk_ipo.enrichments.geo import classify_geo

    result = classify_geo(
        item={
            "description": "Expand our factory in mainland China.",
            "category_raw": "mainland China factory expansion",
            "source_text": "We plan to expand our factory in Guangdong.",
        },
        company_name="Example HK Holdings Ltd.",
    )
    assert result == "mainland"


def test_geo_classify_overseas():
    from hk_ipo.enrichments.geo import classify_geo

    result = classify_geo(
        item={
            "description": "Expand into the US and European markets.",
            "category_raw": "overseas market expansion",
            "source_text": "We plan to enter the US and European markets.",
        },
        company_name="Example HK Holdings Ltd.",
    )
    assert result == "overseas"


def test_geo_run_integrates(tmp_path: Path):
    from hk_ipo.enrichments.base import load_enriched_or_categorized, save_enriched
    from hk_ipo.enrichments.geo import run as geo_run

    categorized = tmp_path / "categorized"
    enriched = tmp_path / "enriched"
    categorized.mkdir()
    enriched.mkdir()

    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "category_raw": "R&D in Shenzhen",
                "description": "R&D center in Shenzhen",
                "percentage": 100.0,
                "source_text": "We will build an R&D center in Shenzhen.",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record, categorized, "01234")
    geo_run(categorized, enriched, ticker="01234")
    result = load_enriched_or_categorized(
        enriched if (enriched / "01234.json").exists() else categorized, "01234"
    )
    assert result["enrichments"]["geo"]["version"] >= 1
    assert "use_001" in result["enrichments"]["geo"]["by_use_id"]


def test_geo_idempotent(tmp_path: Path):
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.geo import run as geo_run

    categorized = tmp_path / "categorized"
    enriched = tmp_path / "enriched"
    categorized.mkdir()
    enriched.mkdir()

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
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.geo import run as geo_run

    categorized = tmp_path / "categorized"
    enriched = tmp_path / "enriched"
    categorized.mkdir()
    enriched.mkdir()

    # Two tickers in the bare categorized dir
    for tk in ("01234", "05678"):
        record = {
            "hk_ticker": tk,
            "company_name_en": f"Co {tk}",
            "schema_version": "2.0",
            "uses": [
                {
                    "use_id": "use_001",
                    "category_raw": "R&D in Shenzhen",
                    "description": "R&D in Shenzhen",
                    "percentage": 100.0,
                    "source_text": "We will do R&D in Shenzhen.",
                }
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


# ── CR-015: KeyError guard on missing use_id ──────────────────────────────


def test_missing_use_id_no_key_error():
    """_enrich_one must not raise KeyError when a use item is missing use_id."""
    import shutil
    import tempfile
    from pathlib import Path

    from hk_ipo.enrichments.geo import _enrich_one

    record = {
        "hk_ticker": "TEST01",
        "uses": [
            {"description": "Expand into Japan", "category_raw": "", "source_text": ""},
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
    from hk_ipo.enrichments.geo import classify_geo

    item_none = {"description": None, "category_raw": None, "source_text": None}
    item_empty = {"description": "", "category_raw": "", "source_text": ""}
    assert classify_geo(item_none) == classify_geo(item_empty)


def test_none_field_values_with_real_keyword():
    """None values must not prevent matching a real geo keyword from another field.

    Even with description=None, a real keyword in source_text must still match.
    """
    from hk_ipo.enrichments.geo import classify_geo

    item = {"description": None, "category_raw": "Shenzhen factory", "source_text": None}
    assert classify_geo(item) == "mainland"


# ── CR-002: CLI single-file path must preserve prior enrichment blocks ──


def test_cli_preserves_prior_enrichments(tmp_path: Path, monkeypatch) -> None:
    """CLI single-file path must not silently drop prior enrichment blocks.

    If enriched data already exists for the ticker, the CLI must load from
    enriched_dir to preserve prior enrichment blocks (country, etc.).
    Without this fix, running geo CLI on a single file after other
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

    ticker = "05678"

    # Step 1: Write a raw categorized record (no enrichments)
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build a factory in Shenzhen",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory in Shenzhen, China.",
            },
        ],
    }
    cat_file = cat_dir / f"{ticker}.json"
    cat_file.write_text(_json.dumps(raw_record), encoding="utf-8")

    # Step 2: Pre-populate enriched_dir with prior enrichment (simulating
    # that another enrichment like country has already run)
    enriched_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build a factory in Shenzhen",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory in Shenzhen, China.",
            },
        ],
        "enrichments": {
            "country": {"version": 1, "countries": ["CN"], "by_use_id": {"use_001": ["CN"]}},
        },
    }
    enr_file = enr_dir / f"{ticker}.json"
    enr_file.write_text(_json.dumps(enriched_record), encoding="utf-8")

    # Step 3: Run CLI with the categorized file path — must load from
    # enriched_dir (which already exists) to preserve prior country enrichment.
    cat_input_file = tmp_path / "input.json"
    cat_input_file.write_text(_json.dumps(raw_record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["geo", str(cat_input_file)]
    try:
        runpy.run_module("hk_ipo.enrichments.geo", run_name="__main__")
    finally:
        sys.argv = old_argv

    # Step 4: Verify that prior enrichment (country) was preserved
    result = _json.loads(enr_file.read_text(encoding="utf-8"))
    assert "country" in result["enrichments"], (
        "CR-002 regression: prior 'country' enrichment was silently dropped by CLI single-file path"
    )
    assert result["enrichments"]["country"]["countries"] == ["CN"]
    assert "geo" in result["enrichments"], "geo enrichment must also be present"
