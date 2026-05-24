"""Unit tests for src/hk_ipo/storage/loader.py."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from hk_ipo.storage.loader import dry_run_preview, process_all, process_single, upsert
from hk_ipo.storage.schema_sql import create_tables


def _sample_record() -> dict:
    return {
        "hk_ticker": "01234",
        "company_name_en": "Test Corp",
        "listing_date": "2024-07-12",
        "document_date": "2024-06-30",
        "schema_version": "2.0",
        "total_net_proceeds_hkd_million": 5000.0,
        "currency": "HKD",
        "language": "en",
        "industry_primary": "Software & Services",
        "industry_source": "prospectus",
        "needs_human_review": False,
        "review_reasons": [],
        "uses": [
            {
                "use_id": "use_001",
                "parent_category": "Growth",
                "main_category": "R&D and Technology",
                "sub_category": "Core product R&D",
                "category_raw": "research and development",
                "percentage": 60.0,
                "amount_hkd_million": 3000.0,
                "description": "R&D for core algorithms.",
                "source_text": "Approximately 60% or HK$3,000 million...",
            },
            {
                "use_id": "use_002",
                "parent_category": "Working Capital",
                "main_category": "General Working Capital",
                "sub_category": None,
                "category_raw": "working capital",
                "percentage": 40.0,
                "amount_hkd_million": 2000.0,
                "description": "General working capital.",
                "source_text": "Approximately 40% or HK$2,000 million...",
            },
        ],
        "enrichments": {
            "geo": {"version": 1, "by_use_id": {"use_001": "mainland", "use_002": "domestic_hk"}},
            "commitment": {
                "version": 1,
                "by_use_id": {"use_001": "committed", "use_002": "committed"},
            },
        },
    }


def test_upsert_inserts_company(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())
    row = conn.execute(
        "SELECT company_name_en, total_net_proceeds FROM companies WHERE hk_ticker = ?", ("01234",)
    ).fetchone()
    assert row is not None
    assert row[0] == "Test Corp"
    assert row[1] == 5000.0
    conn.close()


def test_upsert_inserts_uses(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())
    rows = list(
        conn.execute(
            "SELECT use_id, parent_category, main_category, percentage FROM uses "
            "WHERE hk_ticker = ? ORDER BY use_id",
            ("01234",),
        )
    )
    assert len(rows) == 2
    assert rows[0][0] == "use_001"
    assert rows[1][2] == "General Working Capital"
    conn.close()


def test_upsert_inserts_use_tags(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())
    tags = list(
        conn.execute(
            "SELECT use_id, dimension, value FROM use_tags WHERE hk_ticker = ?", ("01234",)
        )
    )
    assert len(tags) >= 2
    dims = {t[1] for t in tags}
    assert "geo" in dims
    assert "commitment" in dims
    conn.close()


def test_upsert_idempotent(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())

    # Capture full DB state after first upsert
    companies_1 = list(conn.execute("SELECT * FROM companies WHERE hk_ticker = ?", ("01234",)))
    uses_1 = list(
        conn.execute("SELECT * FROM uses WHERE hk_ticker = ? ORDER BY use_id", ("01234",))
    )
    tags_1 = list(
        conn.execute(
            "SELECT * FROM use_tags WHERE hk_ticker = ? ORDER BY use_id, dimension, value",
            ("01234",),
        )
    )

    upsert(conn, _sample_record())

    # Capture full DB state after second upsert
    companies_2 = list(conn.execute("SELECT * FROM companies WHERE hk_ticker = ?", ("01234",)))
    uses_2 = list(
        conn.execute("SELECT * FROM uses WHERE hk_ticker = ? ORDER BY use_id", ("01234",))
    )
    tags_2 = list(
        conn.execute(
            "SELECT * FROM use_tags WHERE hk_ticker = ? ORDER BY use_id, dimension, value",
            ("01234",),
        )
    )

    # Row counts must match
    assert len(uses_1) == len(uses_2)
    assert len(tags_1) == len(tags_2)

    # Full data must be byte-identical after idempotent upsert
    # (skip updated_at column which changes between runs)
    # companies: columns 0-11, index 11 is updated_at
    assert companies_1[0][:11] == companies_2[0][:11]
    assert uses_1 == uses_2
    assert tags_1 == tags_2

    conn.close()


def test_upsert_updates_changed_record(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())
    record2 = _sample_record()
    record2["company_name_en"] = "Updated Corp"
    upsert(conn, record2)

    name = conn.execute(
        "SELECT company_name_en FROM companies WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    assert name == "Updated Corp"
    conn.close()


def test_dry_run_does_not_modify_db(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    preview = dry_run_preview(_sample_record())
    assert "01234" in str(preview)
    # DB unchanged
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert n == 0
    conn.close()


# --- Additional tests for process_single / process_all / CLI (CR-004) ---


def test_process_single_loads_json_file(tmp_path: Path):
    db = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    json_file.write_text(json.dumps(_sample_record()), encoding="utf-8")

    process_single(json_file, db)

    conn = sqlite3.connect(str(db))
    row = conn.execute("SELECT COUNT(*) FROM companies WHERE hk_ticker = ?", ("01234",)).fetchone()
    assert row[0] == 1
    uses_count = conn.execute(
        "SELECT COUNT(*) FROM uses WHERE hk_ticker = ?", ("01234",)
    ).fetchone()
    assert uses_count[0] == 2
    conn.close()


def test_process_single_dry_run_does_not_modify_db(tmp_path: Path):
    db = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    json_file.write_text(json.dumps(_sample_record()), encoding="utf-8")

    process_single(json_file, db, dry_run=True)

    conn = sqlite3.connect(str(db))
    # DB file exists but should have no user tables (CR-010: create_tables
    # is not called in dry-run mode)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    assert len(tables) == 0
    conn.close()


def test_process_single_creates_db_dir(tmp_path: Path):
    db = tmp_path / "subdir" / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    json_file.write_text(json.dumps(_sample_record()), encoding="utf-8")

    process_single(json_file, db)

    assert db.exists()
    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert n == 1
    conn.close()


def test_process_single_invalid_json_raises(tmp_path: Path):
    db = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    json_file.write_text("not valid json", encoding="utf-8")

    with pytest.raises((json.JSONDecodeError, Exception)):
        process_single(json_file, db)


def test_process_single_missing_hk_ticker_raises(tmp_path: Path):
    db = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _sample_record()
    del record["hk_ticker"]
    json_file.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="hk_ticker"):
        process_single(json_file, db)


def test_process_single_missing_uses_raises(tmp_path: Path):
    db = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _sample_record()
    del record["uses"]
    json_file.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="uses"):
        process_single(json_file, db)


def test_process_all_loads_multiple_files(tmp_path: Path):
    db = tmp_path / "test.db"
    for i, ticker in enumerate(["01234", "56789"]):
        rec = _sample_record()
        rec["hk_ticker"] = ticker
        jf = tmp_path / f"{ticker}_enriched.json"
        jf.write_text(json.dumps(rec), encoding="utf-8")

    result = process_all(tmp_path, db)
    assert result["loaded"] == 2
    assert result["total"] == 2

    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(DISTINCT hk_ticker) FROM companies").fetchone()[0]
    assert n == 2
    conn.close()


def test_process_all_empty_directory(tmp_path: Path):
    db = tmp_path / "test.db"
    # tmp_path is empty
    result = process_all(tmp_path, db)
    assert result["loaded"] == 0
    assert result["total"] == 0


def test_process_all_dry_run_does_not_load(tmp_path: Path):
    db = tmp_path / "test.db"
    rec = _sample_record()
    jf = tmp_path / "01234_enriched.json"
    jf.write_text(json.dumps(rec), encoding="utf-8")

    result = process_all(tmp_path, db, dry_run=True)
    # In dry-run mode, loaded should not increment (CR-002 fix)
    assert result["loaded"] == 0

    conn = sqlite3.connect(str(db))
    # No user tables should exist (CR-010: dry-run skips create_tables)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    assert len(tables) == 0
    conn.close()


def test_process_all_partial_failure_continues(tmp_path: Path):
    db = tmp_path / "test.db"
    # Good file
    jf1 = tmp_path / "01234_enriched.json"
    jf1.write_text(json.dumps(_sample_record()), encoding="utf-8")
    # Bad file
    jf2 = tmp_path / "bad_enriched.json"
    jf2.write_text("invalid json", encoding="utf-8")

    result = process_all(tmp_path, db)

    # Only the good one loaded
    assert result["loaded"] == 1
    assert result["total"] == 2

    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM companies WHERE hk_ticker = ?", ("01234",)).fetchone()[0]
    assert n == 1
    conn.close()


# --- CLI tests using subprocess (CR-004) ---


def test_cli_single_file(tmp_path: Path):
    db = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    json_file.write_text(json.dumps(_sample_record()), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "hk_ipo.storage.loader", str(json_file), "--db", str(db)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert n == 1
    conn.close()


def test_cli_missing_file_exits_nonzero(tmp_path: Path):
    db = tmp_path / "test.db"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hk_ipo.storage.loader",
            str(tmp_path / "nonexistent.json"),
            "--db",
            str(db),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cli_dry_run_flag(tmp_path: Path):
    db = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    json_file.write_text(json.dumps(_sample_record()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hk_ipo.storage.loader",
            str(json_file),
            "--db",
            str(db),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # DB should be unmodified (CR-010: dry-run skips create_tables)
    conn = sqlite3.connect(str(db))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    assert len(tables) == 0
    conn.close()


def test_cli_all_flag(tmp_path: Path):
    db = tmp_path / "test.db"
    # Write multiple JSON files to the tmp_path to simulate enriched dir
    for i, ticker in enumerate(["01234", "56789"]):
        rec = _sample_record()
        rec["hk_ticker"] = ticker
        jf = tmp_path / f"{ticker}_enriched.json"
        jf.write_text(json.dumps(rec), encoding="utf-8")

    # Use the actual CLI --all flag with --enriched-dir (SR-002)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hk_ipo.storage.loader",
            "--all",
            "--db",
            str(db),
            "--enriched-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(DISTINCT hk_ticker) FROM companies").fetchone()[0]
    assert n == 2
    conn.close()


def test_cli_custom_db_path(tmp_path: Path):
    db = tmp_path / "custom" / "ipo.db"
    json_file = tmp_path / "01234_enriched.json"
    json_file.write_text(json.dumps(_sample_record()), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "hk_ipo.storage.loader", str(json_file), "--db", str(db)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert db.exists()

    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert n == 1
    conn.close()
