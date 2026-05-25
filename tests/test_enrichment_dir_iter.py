"""Regression test for the L5 dir-selection bug (2026-05-25 audit).

Before the fix, each enrichment's batch mode chose between enriched_dir
OR categorized_dir based on whether enriched_dir had any files. The
presence of even ONE stale enriched file caused NEW tickers in
categorized_dir to be silently skipped.

This test verifies the corrected behavior:
- All categorized tickers are iterated.
- Pre-existing enriched files are preferred per-ticker (preserves
  prior enrichment dimensions).
"""

from __future__ import annotations

import json
from pathlib import Path

from hk_ipo.enrichments.base import iter_records_for_enrichment


def _write(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def test_iter_yields_all_categorized_even_when_enriched_has_files(tmp_path: Path) -> None:
    cat = tmp_path / "categorized"
    enr = tmp_path / "enriched"

    # Three tickers in categorized
    _write(cat / "00001.json", {"hk_ticker": "00001", "uses": [{"use_id": "u1"}]})
    _write(cat / "00002.json", {"hk_ticker": "00002", "uses": [{"use_id": "u1"}]})
    _write(cat / "00003.json", {"hk_ticker": "00003", "uses": [{"use_id": "u1"}]})

    # One stale enriched file — the pre-fix bug would only yield this one
    _write(
        enr / "00001.json",
        {"hk_ticker": "00001", "uses": [{"use_id": "u1"}],
         "enrichments": {"geo": {"version": 1}}},
    )

    yielded = list(iter_records_for_enrichment(cat, enr))
    tickers = sorted(t for t, _ in yielded)
    assert tickers == ["00001", "00002", "00003"], (
        f"Expected all 3 categorized tickers, got {tickers}"
    )


def test_iter_prefers_enriched_record_when_present(tmp_path: Path) -> None:
    cat = tmp_path / "categorized"
    enr = tmp_path / "enriched"

    _write(cat / "00001.json", {"hk_ticker": "00001", "uses": [{"use_id": "u1"}]})
    # Enriched version already has a prior dimension block — must be preserved
    _write(
        enr / "00001.json",
        {"hk_ticker": "00001", "uses": [{"use_id": "u1"}],
         "enrichments": {"geo": {"version": 1, "by_use_id": {"u1": "overseas"}}}},
    )

    yielded = dict(iter_records_for_enrichment(cat, enr))
    rec = yielded["00001"]
    assert rec.get("enrichments", {}).get("geo", {}).get("by_use_id") == {"u1": "overseas"}, (
        "Should load enriched version (with prior dims), not bare categorized"
    )


def test_iter_falls_back_to_categorized_when_no_enriched(tmp_path: Path) -> None:
    cat = tmp_path / "categorized"
    enr = tmp_path / "enriched"
    enr.mkdir()  # empty dir

    _write(cat / "00042.json", {"hk_ticker": "00042", "uses": []})
    yielded = list(iter_records_for_enrichment(cat, enr))
    assert len(yielded) == 1
    assert yielded[0][0] == "00042"


def test_iter_handles_empty_enriched_dir_that_doesnt_exist(tmp_path: Path) -> None:
    cat = tmp_path / "categorized"
    enr = tmp_path / "enriched"  # doesn't exist yet

    _write(cat / "00001.json", {"hk_ticker": "00001", "uses": []})
    yielded = list(iter_records_for_enrichment(cat, enr))
    assert len(yielded) == 1
