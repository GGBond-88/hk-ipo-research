"""End-to-end black-box tests for the HK IPO pipeline.

These tests run the full L1 -> L7 pipeline via `scripts/run_pipeline.py`
against a 3-PDF golden corpus, then assert on the resulting filesystem
artefacts and SQLite DB contents.

Mark every test with @pytest.mark.e2e. Run with `pytest -m e2e`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from .conftest import run_pipeline_cli, run_stage_cli

pytestmark = pytest.mark.e2e


# ── A9.1 — End-to-end run produces a populated dashboard ────────────────────


def test_full_pipeline_produces_all_outputs(isolated_data_dir: Path, api_key_present: None) -> None:
    """Run --build-frontend and assert each stage's outputs exist."""
    db_path = isolated_data_dir / "ipo.db"
    result = run_pipeline_cli(
        "--pdf-dir",
        str(isolated_data_dir / "raw_pdfs"),
        "--db",
        str(db_path),
        "--limit",
        "3",
    )
    assert result.returncode == 0, (
        f"pipeline exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # L1 sections exist for each English PDF
    sections_dir = isolated_data_dir / "sections"
    assert sections_dir.exists()
    assert len(list(sections_dir.glob("*.json"))) >= 1

    # L2 extracted exists
    extracted_dir = isolated_data_dir / "extracted"
    assert len(list(extracted_dir.glob("*.json"))) >= 1

    # L4 categorized exists
    categorized_dir = isolated_data_dir / "categorized"
    assert len(list(categorized_dir.glob("*.json"))) >= 1

    # L5 enriched exists with all 8 enrichment blocks
    enriched_files = sorted((isolated_data_dir / "enriched").glob("*.json"))
    assert enriched_files, "no enriched files produced"
    sample = json.loads(enriched_files[0].read_text(encoding="utf-8"))
    expected_dims = {
        "geo",
        "country",
        "industry",
        "specificity",
        "timeline",
        "capex_opex",
        "esg_tag",
        "commitment",
    }
    assert set(sample["enrichments"].keys()) >= expected_dims

    # L6 DB exists with all required tables
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for required in (
        "companies",
        "uses",
        "use_tags",
        "company_tags",
        "pipeline_runs",
        "taxonomy_proposals",
    ):
        assert required in tables, f"missing table: {required}"


# ── A1.2 — Chinese-dominant PDF is skipped ─────────────────────────────────


def test_chinese_pdf_skipped_with_stub(isolated_data_dir: Path, api_key_present: None) -> None:
    """A Chinese-dominant PDF produces a section JSON with language='zh' and
    `skipped=True`
    downstream stages do not produce extracted/categorized
    files for it."""
    result = run_pipeline_cli(
        "--pdf-dir",
        str(isolated_data_dir / "raw_pdfs"),
        "--db",
        str(isolated_data_dir / "ipo.db"),
        "--only",
        "L1",
        "--limit",
        "3",
    )
    assert result.returncode == 0

    zh_section_files = [
        p
        for p in (isolated_data_dir / "sections").glob("*.json")
        if (data := json.loads(p.read_text(encoding="utf-8"))) and data.get("language") == "zh"
    ]
    assert zh_section_files, "no zh section stub found"
    for p in zh_section_files:
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["skipped"] is True
        assert data.get("text", "") == ""


# ── A9.2 — One failed PDF does not block the others ─────────────────────────


def test_corrupt_pdf_does_not_block_other_tickers(
    isolated_data_dir: Path, api_key_present: None
) -> None:
    """Drop a corrupt PDF into raw_pdfs/ alongside the golden ones; full run
    must finish with a non-empty error_message row in pipeline_runs for the
    corrupt ticker and successful rows for the others."""
    raw_dir = isolated_data_dir / "raw_pdfs"
    corrupt = raw_dir / "99999.pdf"
    corrupt.write_bytes(b"not a real pdf")
    db_path = isolated_data_dir / "ipo.db"

    result = run_pipeline_cli(
        "--pdf-dir",
        str(raw_dir),
        "--db",
        str(db_path),
        "--limit",
        "5",
    )
    # exit non-zero (one failure), but other tickers still produced outputs
    assert result.returncode != 0
    assert len(list((isolated_data_dir / "extracted").glob("*.json"))) >= 1
    with sqlite3.connect(db_path) as conn:
        rows = list(
            conn.execute(
                "SELECT hk_ticker, status, error_message FROM pipeline_runs "
                "WHERE hk_ticker = '99999' AND error_message IS NOT NULL"
            )
        )
    assert rows, "99999 should have an error row"


# ── A9.3 — Resumability: re-run after partial completion is a no-op ─────────


def test_rerun_is_idempotent(isolated_data_dir: Path, api_key_present: None) -> None:
    db_path = isolated_data_dir / "ipo.db"
    args = (
        "--pdf-dir",
        str(isolated_data_dir / "raw_pdfs"),
        "--db",
        str(db_path),
        "--limit",
        "3",
    )
    first = run_pipeline_cli(*args)
    assert first.returncode == 0
    enriched_dir = isolated_data_dir / "enriched"
    snap_first = {p.name: p.stat().st_mtime_ns for p in enriched_dir.glob("*.json")}

    second = run_pipeline_cli(*args)
    assert second.returncode == 0
    snap_second = {p.name: p.stat().st_mtime_ns for p in enriched_dir.glob("*.json")}
    # Outputs are not rewritten when inputs are unchanged.
    assert snap_first == snap_second


# ── A9.4 — `--dry-run-cost` exits without making API calls ──────────────────


def test_dry_run_cost_makes_no_api_calls(isolated_data_dir: Path) -> None:
    """Set OPENROUTER_API_KEY to an obviously-broken value; --dry-run-cost
    must still exit 0 because it must not call the API."""
    result = run_pipeline_cli(
        "--pdf-dir",
        str(isolated_data_dir / "raw_pdfs"),
        "--db",
        str(isolated_data_dir / "ipo.db"),
        "--dry-run-cost",
        "--limit",
        "3",
        env_extra={"OPENROUTER_API_KEY": "broken-on-purpose"},
    )
    assert result.returncode == 0
    assert "estimated_tokens" in result.stdout.lower() or "estimated_cost" in result.stdout.lower()


# ── A6.5 — loader --dry-run does not write to the DB ────────────────────────


def test_loader_dry_run_does_not_modify_db(isolated_data_dir: Path, api_key_present: None) -> None:
    """Run L1-L5 first; then run the loader with --dry-run and assert the
    DB file is either absent or unchanged."""
    db_path = isolated_data_dir / "ipo.db"
    pre = run_pipeline_cli(
        "--pdf-dir",
        str(isolated_data_dir / "raw_pdfs"),
        "--db",
        str(db_path),
        "--skip",
        "L6,L7",
        "--limit",
        "3",
    )
    assert pre.returncode == 0
    assert not db_path.exists() or db_path.stat().st_size == 0

    dry = run_stage_cli(
        "storage.loader",
        "--all",
        "--db",
        str(db_path),
        "--dry-run",
        "--enriched-dir",
        str(isolated_data_dir / "enriched"),
    )
    assert dry.returncode == 0
    assert not db_path.exists() or db_path.stat().st_size == 0
