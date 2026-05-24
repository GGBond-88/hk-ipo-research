"""Unit tests for src/hk_ipo/enrichments/timeline.py."""

from __future__ import annotations

from pathlib import Path


def test_dimension_and_version():
    from hk_ipo.enrichments.timeline import DIMENSION, VERSION

    assert DIMENSION == "timeline"
    assert isinstance(VERSION, int)


def test_short_term_0_12m():
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "We expect to complete within 12 months from listing.",
        "source_text": "Expected completion within 12 months.",
    }
    assert classify_timeline(item) == "0-12m"


def test_medium_term_12_24m():
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Deployment expected over the next 18 months.",
        "source_text": "Over the next 18 to 24 months.",
    }
    assert classify_timeline(item) == "12-24m"


def test_long_term_24_36m():
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Three-year deployment plan for the new facility.",
        "source_text": "Enterprise expansion over 3 years.",
    }
    assert classify_timeline(item) == "24-36m"


def test_very_long_36m_plus():
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Long-term investment to be deployed over 5 years.",
        "source_text": "Deployment over the next 5 years.",
    }
    assert classify_timeline(item) == "36m+"


def test_unspecified_no_timeline():
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "General purposes.",
        "source_text": "",
    }
    assert classify_timeline(item) == "unspecified"


def test_hyphenated_12_month_is_short_term():
    """Hyphenated '12-month' should match same as '12 months'."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "We expect to complete the 12-month project.",
        "source_text": "12-month timeline.",
    }
    assert classify_timeline(item) == "0-12m"


def test_hyphenated_5_year_is_very_long():
    """Hyphenated '5-year' should match as 36m+."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Strategic roadmap.",
        "source_text": "5-year strategic deployment plan.",
    }
    assert classify_timeline(item) == "36m+"


def test_hyphenated_3_year_is_long_term():
    """Hyphenated '3-year' should match as 24-36m."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Facility upgrade.",
        "source_text": "3-year facility upgrade program.",
    }
    assert classify_timeline(item) == "24-36m"


def test_hyphenated_2_year_is_medium_term():
    """Hyphenated '2-year' should match as 12-24m."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Technology refresh.",
        "source_text": "2-year technology refresh cycle.",
    }
    assert classify_timeline(item) == "12-24m"


def test_spelled_out_word_numbers():
    """Spelled-out 'two', 'three', 'four', 'five' years match correctly."""
    from hk_ipo.enrichments.timeline import classify_timeline

    assert (
        classify_timeline({"description": "Two years deployment.", "source_text": ""}) == "12-24m"
    )
    assert classify_timeline({"description": "Three years plan.", "source_text": ""}) == "24-36m"
    assert classify_timeline({"description": "Four years horizon.", "source_text": ""}) == "36m+"
    assert classify_timeline({"description": "Five years expansion.", "source_text": ""}) == "36m+"


# ── CR-007 tests: hyphenated qualitative forms ──────────────────────────


def test_hyphenated_very_long_qualitative():
    """Hyphenated 'very-long' should match 36m+ (CR-007 fix)."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "",
        "source_text": "This is a very-long term strategic investment.",
    }
    assert classify_timeline(item) == "36m+"


def test_hyphenated_extended_horizon():
    """Hyphenated 'extended-horizon' should match 36m+ (CR-007 fix)."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "",
        "source_text": "Extended-horizon deployment plan spanning many years.",
    }
    assert classify_timeline(item) == "36m+"


# ── CR-008 tests: word boundaries on numeric patterns ───────────────────


def test_yearly_not_matched_as_year():
    """'within a yearly' should not match 'within a year' pattern (CR-008)."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Repayment within a yearly cycle without a defined timeline.",
        "source_text": "",
    }
    assert classify_timeline(item) == "unspecified"


def test_model_not_matched_as_mo():
    """'model' should not match '12 mo' pattern without word boundary (CR-008)."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Using a new 12 model framework.",
        "source_text": "",
    }
    assert classify_timeline(item) == "unspecified"


def test_first_yearbook_not_matched():
    """'first yearbook' should not match 'first year' (CR-008)."""
    from hk_ipo.enrichments.timeline import classify_timeline

    item = {
        "description": "Published the first yearbook.",
        "source_text": "",
    }
    assert classify_timeline(item) == "unspecified"


# ── CR-006 tests: CLI single-file mode uses loaded record ───────────────


def test__enrich_one_processes_arbitrary_record(tmp_path):
    """_enrich_one should process any record without reloading (CR-006 fix)."""
    from hk_ipo.enrichments.timeline import DIMENSION, _enrich_one

    enriched_dir = tmp_path / "enriched"
    record = {
        "hk_ticker": "09999",
        "uses": [
            {
                "use_id": "u1",
                "description": "Deploy within 12 months.",
                "source_text": "12 month plan.",
            },
            {"use_id": "u2", "description": "Working capital.", "source_text": ""},
        ],
    }
    result = _enrich_one(record, enriched_dir, DIMENSION, force=True, ticker="09999")
    assert result["version"] == 1
    assert result["by_use_id"] == {"u1": "0-12m", "u2": "unspecified"}
    # Verify output file was saved
    output_file = enriched_dir / "09999.json"
    assert output_file.exists()


def test_run_ticker_mode_uses_categorized_fallback(tmp_path):
    """run() in ticker mode should load from categorized_dir if not in enriched (CR-006)."""
    import json

    from hk_ipo.enrichments.timeline import run

    categorized_dir = tmp_path / "categorized"
    enriched_dir = tmp_path / "enriched"
    categorized_dir.mkdir()
    test_record = {
        "hk_ticker": "08888",
        "uses": [
            {"use_id": "u1", "description": "Within 18 months.", "source_text": ""},
        ],
    }
    (categorized_dir / "08888.json").write_text(json.dumps(test_record), encoding="utf-8")

    result = run(categorized_dir, enriched_dir, ticker="08888", force=True)
    assert result is not None
    assert result["by_use_id"] == {"u1": "12-24m"}


# ── CR-015: KeyError guard on missing use_id ──────────────────────────────


def test_missing_use_id_no_key_error():
    """_enrich_one must not raise KeyError when a use item is missing use_id."""
    import shutil
    import tempfile

    from hk_ipo.enrichments.timeline import DIMENSION, _enrich_one

    record = {
        "hk_ticker": "TEST01",
        "uses": [
            {"description": "Deploy within 12 months.", "source_text": ""},
            {"use_id": "u2", "description": "general corp", "source_text": ""},
        ],
    }
    enriched_dir = Path(tempfile.mkdtemp())
    try:
        _enrich_one(record, enriched_dir, DIMENSION)
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
    from hk_ipo.enrichments.timeline import classify_timeline

    item_none = {"description": None, "source_text": None}
    item_empty = {"description": "", "source_text": ""}
    assert classify_timeline(item_none) == classify_timeline(item_empty)


# ── CR-001: CLI single-file path must preserve prior enrichment blocks ──


def test_cli_preserves_prior_enrichments(tmp_path: Path, monkeypatch) -> None:
    """CLI single-file path must not silently drop prior enrichment blocks.

    If enriched data already exists for the ticker, the CLI must load from
    enriched_dir to preserve prior enrichment blocks (geo, country, etc.).
    Without this fix, running timeline CLI on a single file after other
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

    ticker = "01234"

    # Step 1: Write a raw categorized record (no enrichments)
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build a factory within 12 months",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory within 12 months.",
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
                "description": "Build a factory within 12 months",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory within 12 months.",
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
    cat_input_file = tmp_path / "input.json"
    cat_input_file.write_text(_json.dumps(raw_record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["timeline", str(cat_input_file)]
    try:
        runpy.run_module("hk_ipo.enrichments.timeline", run_name="__main__")
    finally:
        sys.argv = old_argv

    # Step 4: Verify that prior enrichment (geo) was preserved
    result = _json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in result["enrichments"], (
        "CR-001 regression: prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert result["enrichments"]["geo"]["by_use_id"]["use_001"] == "mainland"
    assert "timeline" in result["enrichments"], (
        "timeline enrichment must also be present"
    )
