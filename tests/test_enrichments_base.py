"""Unit tests for src/hk_ipo/enrichments/base.py — enrichment runner contract."""

from __future__ import annotations

import json
from pathlib import Path


def test_enrichment_runner_interface_defined():
    """The base module must export an EnrichmentRunner protocol/class."""
    from typing import Protocol as _Protocol

    from hk_ipo.enrichments.base import EnrichmentRunner

    # EnrichmentRunner must be a Protocol defining the run interface
    assert issubclass(EnrichmentRunner, _Protocol)
    assert hasattr(EnrichmentRunner, "run")


def test_load_enriched_or_categorized_loads_json_bare_dir(tmp_path: Path):
    """When caller passes a bare directory containing <ticker>.json,
    load_enriched_or_categorized must find and load it."""
    from hk_ipo.enrichments.base import load_enriched_or_categorized

    data = {"hk_ticker": "01234", "uses": []}
    cf = tmp_path / "01234.json"
    cf.write_text(json.dumps(data), encoding="utf-8")

    result = load_enriched_or_categorized(tmp_path, "01234")
    assert result["hk_ticker"] == "01234"


def test_load_enriched_or_categorized_loads_from_categorized_subdir(tmp_path: Path):
    """When caller passes a parent directory with a 'categorized' subdir, load from it."""
    from hk_ipo.enrichments.base import load_enriched_or_categorized

    (tmp_path / "categorized").mkdir()
    (tmp_path / "categorized" / "01234.json").write_text(
        json.dumps({"hk_ticker": "01234", "uses": [], "source": "categorized"}),
        encoding="utf-8",
    )
    result = load_enriched_or_categorized(tmp_path, "01234")
    assert result["source"] == "categorized"


def test_load_enriched_or_categorized_prefers_enriched_over_categorized(tmp_path: Path):
    """When both subdirs contain the ticker, the enriched/ copy wins."""
    from hk_ipo.enrichments.base import load_enriched_or_categorized

    (tmp_path / "enriched").mkdir()
    (tmp_path / "categorized").mkdir()
    (tmp_path / "enriched" / "01234.json").write_text(
        json.dumps({"hk_ticker": "01234", "uses": [], "source": "enriched"}),
        encoding="utf-8",
    )
    (tmp_path / "categorized" / "01234.json").write_text(
        json.dumps({"hk_ticker": "01234", "uses": [], "source": "categorized"}),
        encoding="utf-8",
    )
    result = load_enriched_or_categorized(tmp_path, "01234")
    assert result["source"] == "enriched"


def test_merge_enrichment_block_adds_new_dim(tmp_path: Path):
    from hk_ipo.enrichments.base import merge_enrichment_block

    record = {"enrichments": {}}
    merge_enrichment_block(record, "geo", {"version": 1, "by_use_id": {}})
    assert record["enrichments"]["geo"] == {"version": 1, "by_use_id": {}}


def test_merge_enrichment_block_overwrites_old_version():
    from hk_ipo.enrichments.base import merge_enrichment_block

    record = {"enrichments": {"geo": {"version": 1, "by_use_id": {"use_001": "domestic_hk"}}}}
    merge_enrichment_block(record, "geo", {"version": 2, "by_use_id": {"use_001": "overseas"}})
    assert record["enrichments"]["geo"]["version"] == 2
    assert record["enrichments"]["geo"]["by_use_id"]["use_001"] == "overseas"


def test_save_enriched_writes_json(tmp_path: Path):
    from hk_ipo.enrichments.base import save_enriched

    record = {"hk_ticker": "01234", "enrichments": {"geo": {"version": 1}}}
    save_enriched(record, tmp_path, "01234")
    out = tmp_path / "01234.json"
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["enrichments"]["geo"]["version"] == 1
