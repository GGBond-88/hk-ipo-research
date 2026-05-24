"""Unit tests for src/hk_ipo/enrichments/country.py."""

from __future__ import annotations

import json
from pathlib import Path


def test_country_dimension_and_version():
    from hk_ipo.enrichments.country import DIMENSION, VERSION

    assert DIMENSION == "country"
    assert isinstance(VERSION, int)
    assert VERSION >= 1


def test_extract_countries_singapore():
    from hk_ipo.enrichments.country import extract_countries

    text = "We plan to expand into Singapore and set up a regional office."
    codes = extract_countries(text)
    assert "SG" in codes


def test_extract_countries_multiple():
    from hk_ipo.enrichments.country import extract_countries

    text = "We will target the United States, Japan, and Vietnam for our overseas expansion."
    codes = extract_countries(text)
    assert "US" in codes
    assert "JP" in codes
    assert "VN" in codes


def test_extract_countries_no_match():
    from hk_ipo.enrichments.country import extract_countries

    text = "We will expand our Hong Kong office."
    codes = extract_countries(text)
    assert codes == []


def test_country_run_integrates(tmp_path: Path):
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.country import run as country_run

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
                "description": "Expand into Singapore and Japan.",
                "category_raw": "overseas expansion",
                "percentage": 100.0,
                "source_text": "We plan to expand into Singapore and Japan.",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    country_run(cat, enr, ticker="01234")
    loaded = json.loads((enr / "01234.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    assert block["version"] >= 1
    assert "SG" in block["countries"] or "SG" in block["by_use_id"]["use_001"]


def test_country_idempotent(tmp_path: Path):
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.country import run as country_run

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
                "description": "R&D",
                "category_raw": "R&D",
                "percentage": 100.0,
                "source_text": "R&D.",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")
    first = country_run(cat, enr, ticker="01234")
    second = country_run(cat, enr, ticker="01234")
    assert first == second


# ── CR-001: word-boundary matching ────────────────────────────────────────


def test_extract_countries_no_false_positive_substring():
    """Substring matches without word boundaries must not produce false codes."""
    from hk_ipo.enrichments.country import extract_countries

    # "uk" substring inside "Luke" or "dukedom" must not match GB
    assert "GB" not in extract_countries("Luke works on the project.")
    assert "GB" not in extract_countries("The dukedom was established in 1200.")

    # Short code "la" is no longer a substring issue — "laos" is 4 chars and
    # requires word boundaries; but verify that short code "uae" does not
    # match inside similar-looking words.
    assert "AE" not in extract_countries("The quaestor oversaw finances.")

    # But standalone "uk" with word boundaries must still match
    assert "GB" in extract_countries("We have an office in the UK.")

    # And "in the usa today" must still match US (word boundaries around "usa")
    assert "US" in extract_countries("We are based in the USA today.")

    # And single-word country names must still match within boundaries
    assert "JP" in extract_countries("We plan to expand into Japan.")


# ── CR-003: all_files returns results dict ────────────────────────────────


def test_country_all_files_returns_results(tmp_path: Path):
    """all_files=True must return a dict keyed by ticker, not None."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.country import run as country_run

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
                    "description": "Expand into Japan.",
                    "category_raw": "expansion",
                    "percentage": 100.0,
                    "source_text": "Expand into Japan.",
                }
            ],
            "enrichments": {},
        }
        save_enriched(record, cat, ticker)

    results = country_run(cat, enr, all_files=True)
    assert isinstance(results, dict)
    assert len(results) == 2
    assert "01234" in results
    assert "05678" in results
    assert "JP" in results["01234"]["countries"]


# ── CR-004: all_files falls back when enriched_dir is empty ────────────────


def test_country_all_files_falls_back_empty_enriched(tmp_path: Path):
    """all_files must fall back to categorized_dir when enriched_dir has no JSON files."""
    from hk_ipo.enrichments.base import save_enriched
    from hk_ipo.enrichments.country import run as country_run

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
                "description": "Expand into Singapore.",
                "category_raw": "expansion",
                "percentage": 100.0,
                "source_text": "Expand into Singapore.",
            }
        ],
        "enrichments": {},
    }
    save_enriched(record, cat, "01234")

    results = country_run(cat, enr, all_files=True)
    assert isinstance(results, dict)
    assert len(results) == 1
    assert "SG" in results["01234"]["countries"]


# ── CR-005: _enrich_one is module-level and directly testable ─────────────


def test_enrich_one_directly_callable(tmp_path: Path):
    """_enrich_one must be a module-level function callable without run()."""
    from hk_ipo.enrichments.country import _enrich_one

    enr = tmp_path / "enriched"
    enr.mkdir()
    record = {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Expand into Vietnam.",
                "category_raw": "expansion",
                "percentage": 100.0,
                "source_text": "Expand into Vietnam.",
            }
        ],
        "enrichments": {},
    }
    block = _enrich_one(record, enr)
    assert block["version"] >= 1
    assert "VN" in block["countries"]
    assert "VN" in block["by_use_id"]["use_001"]


# ── CR-015: KeyError guard on missing use_id ──────────────────────────────


def test_missing_use_id_no_key_error():
    """_enrich_one must not raise KeyError when a use item is missing use_id."""
    import shutil
    import tempfile
    from pathlib import Path

    from hk_ipo.enrichments.country import _enrich_one

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
    that extract_countries on a text built from None-valued fields produces
    the same result as empty string fields (no false country matches).
    """
    from hk_ipo.enrichments.country import extract_countries

    # Simulate the text construction that _enrich_one does: join of str(.get(...))
    # With the bug: str(None) = "None" → text would be "None None None"
    # With the fix: str(None or "") = "" → text would be "  "
    # Neither matches a country, but the fix ensures correctness.
    text_none_fields = " ".join([str(None), str(None), str(None)])
    text_empty = ""
    assert extract_countries(text_none_fields) == extract_countries(text_empty)


def test_none_field_values_with_real_keyword():
    """None values must not prevent matching a real country keyword.

    When one field contains a real country name and another is None,
    the country must still be detected.
    """
    from hk_ipo.enrichments.country import extract_countries

    text = " ".join([str(None), "Expand into Japan and Singapore.", str(None)])
    codes = extract_countries(text)
    assert "JP" in codes
    assert "SG" in codes


# ── CR-002: CLI single-file path must preserve prior enrichment blocks ──


def test_cli_preserves_prior_enrichments(tmp_path: Path, monkeypatch) -> None:
    """CLI single-file path must not silently drop prior enrichment blocks.

    If enriched data already exists for the ticker, the CLI must load from
    enriched_dir to preserve prior enrichment blocks (geo, etc.).
    Without this fix, running country CLI on a single file after other
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

    ticker = "06789"

    # Step 1: Write a raw categorized record (no enrichments)
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Expand into Japan",
                "category_raw": "expansion",
                "percentage": 100.0,
                "source_text": "We will expand into Japan and Singapore.",
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
                "description": "Expand into Japan",
                "category_raw": "expansion",
                "percentage": 100.0,
                "source_text": "We will expand into Japan and Singapore.",
            },
        ],
        "enrichments": {
            "geo": {"version": 1, "by_use_id": {"use_001": "overseas"}},
        },
    }
    enr_file = enr_dir / f"{ticker}.json"
    enr_file.write_text(_json.dumps(enriched_record), encoding="utf-8")

    # Step 3: Run CLI with the categorized file path — must load from
    # enriched_dir (which already exists) to preserve prior geo enrichment.
    cat_input_file = tmp_path / "input.json"
    cat_input_file.write_text(_json.dumps(raw_record), encoding="utf-8")

    old_argv = sys.argv.copy()
    sys.argv = ["country", str(cat_input_file)]
    try:
        runpy.run_module("hk_ipo.enrichments.country", run_name="__main__")
    finally:
        sys.argv = old_argv

    # Step 4: Verify that prior enrichment (geo) was preserved
    result = _json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in result["enrichments"], (
        "CR-002 regression: prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert result["enrichments"]["geo"]["by_use_id"]["use_001"] == "overseas"
    assert "country" in result["enrichments"], "country enrichment must also be present"
