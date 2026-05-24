"""Black-box tests for L6 SQLite loader CLI (Task 018).

These tests invoke ``python -m hk_ipo.storage.loader`` via subprocess and
verify behaviour through exit codes, stdout/stderr, and SQLite database
contents.  They do NOT import hk_ipo internals directly.

The L6 loader does not require an API key -- it only loads enriched JSON
files into SQLite.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------


def _enriched_record(
    hk_ticker: str = "01234",
    company_name: str = "Test Corp",
    total_proceeds: float = 5000.0,
    uses: list[dict] | None = None,
    enrichments: dict | None = None,
) -> dict:
    """Build a valid enriched record matching the external enriched JSON spec."""
    if uses is None:
        uses = [
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
        ]
    if enrichments is None:
        enrichments = {
            "geo": {"version": 1, "by_use_id": {"use_001": "mainland", "use_002": "domestic_hk"}},
            "commitment": {
                "version": 1,
                "by_use_id": {"use_001": "committed", "use_002": "committed"},
            },
        }
    return {
        "hk_ticker": hk_ticker,
        "company_name_en": company_name,
        "listing_date": "2024-07-12",
        "document_date": "2024-06-30",
        "schema_version": "2.0",
        "total_net_proceeds_hkd_million": total_proceeds,
        "currency": "HKD",
        "language": "en",
        "industry_primary": "Software & Services",
        "industry_source": "prospectus",
        "needs_human_review": False,
        "review_reasons": [],
        "uses": uses,
        "enrichments": enrichments,
    }


def _run_l6_cli(
    *args: str,
    cwd: Path | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Invoke L6 module CLI via subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.storage.loader", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or PROJECT_ROOT),
        env=dict(os.environ),
        check=False,
    )


# ═══════════════════════════════════════════════════════════════════════════
# BB-001: --help output lists all flags
# ═══════════════════════════════════════════════════════════════════════════


def test_help_output_lists_all_flags() -> None:
    """--help must document --all, --db, --dry-run, --enriched-dir."""
    result = _run_l6_cli("--help")
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr={result.stderr[:400]}"
    )
    assert "--all" in result.stdout, f"--all missing from help: {result.stdout[:400]}"
    assert "--db" in result.stdout, f"--db missing from help: {result.stdout[:400]}"
    assert "--dry-run" in result.stdout, f"--dry-run missing from help: {result.stdout[:400]}"
    assert "--enriched-dir" in result.stdout, (
        f"--enriched-dir missing from help: {result.stdout[:400]}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BB-002: Missing required arguments exits non-zero
# ═══════════════════════════════════════════════════════════════════════════


def test_missing_required_arg_exits_nonzero() -> None:
    """Calling with neither --all nor a positional file must exit non-zero."""
    result = _run_l6_cli()
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-003: Nonexistent single file exits non-zero with [ERROR]
# ═══════════════════════════════════════════════════════════════════════════


def test_nonexistent_file_exits_nonzero(tmp_path: Path) -> None:
    """Single-file mode with nonexistent file exits non-zero with [ERROR]."""
    db_path = tmp_path / "test.db"
    result = _run_l6_cli(
        str(tmp_path / "nonexistent.json"),
        "--db",
        str(db_path),
    )
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
    assert "[ERROR]" in (result.stdout + result.stderr), (
        f"Expected [ERROR] diagnostic: stdout={result.stdout[:300]} stderr={result.stderr[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BB-004: Single file loads data into companies table
# ═══════════════════════════════════════════════════════════════════════════


def test_single_file_loads_company(tmp_path: Path) -> None:
    """A single enriched JSON file loads company data into the companies table."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234", company_name="Test Corp", total_proceeds=5000.0)
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert result.returncode == 0, (
        f"exit={result.returncode}\nstdout={result.stdout[:400]}\nstderr={result.stderr[:400]}"
    )

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT company_name_en, total_net_proceeds, hk_ticker FROM companies WHERE hk_ticker = ?",
        ("01234",),
    ).fetchone()
    conn.close()

    assert row is not None, "Company row not found"
    assert row[0] == "Test Corp", f"Expected 'Test Corp', got {row[0]}"
    assert row[1] == 5000.0, f"Expected 5000.0, got {row[1]}"
    assert row[2] == "01234"


# ═══════════════════════════════════════════════════════════════════════════
# BB-005: Single file loads uses table
# ═══════════════════════════════════════════════════════════════════════════


def test_single_file_loads_uses(tmp_path: Path) -> None:
    """A single enriched JSON file loads use-of-proceeds rows into the uses table."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234")
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert result.returncode == 0

    conn = sqlite3.connect(str(db_path))
    rows = list(
        conn.execute(
            "SELECT use_id, parent_category, main_category, percentage "
            "FROM uses WHERE hk_ticker = ? ORDER BY use_id",
            ("01234",),
        )
    )
    conn.close()

    assert len(rows) == 2, f"Expected 2 uses, got {len(rows)}"
    assert rows[0][0] == "use_001"
    assert rows[0][1] == "Growth"
    assert rows[1][2] == "General Working Capital"


# ═══════════════════════════════════════════════════════════════════════════
# BB-006: Single file loads use_tags table
# ═══════════════════════════════════════════════════════════════════════════


def test_single_file_loads_use_tags(tmp_path: Path) -> None:
    """A single enriched JSON file loads enrichment tags into the use_tags table."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234")
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert result.returncode == 0

    conn = sqlite3.connect(str(db_path))
    tags = list(
        conn.execute(
            "SELECT use_id, dimension, value FROM use_tags "
            "WHERE hk_ticker = ? ORDER BY use_id, dimension",
            ("01234",),
        )
    )
    conn.close()

    assert len(tags) >= 2, f"Expected at least 2 tags, got {len(tags)}"
    dims = {t[1] for t in tags}
    assert "geo" in dims, f"Expected 'geo' dimension, got {dims}"
    assert "commitment" in dims, f"Expected 'commitment' dimension, got {dims}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-007: --all loads multiple enriched files
# ═══════════════════════════════════════════════════════════════════════════


def test_all_loads_multiple_files(tmp_path: Path) -> None:
    """--all --enriched-dir loads every .json file in the directory."""
    db_path = tmp_path / "test.db"
    enriched_dir = tmp_path / "enriched"
    enriched_dir.mkdir()

    for ticker in ("01234", "56789", "99999"):
        rec = _enriched_record(ticker, company_name=f"Company {ticker}")
        (enriched_dir / f"{ticker}_enriched.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_l6_cli(
        "--all",
        "--db",
        str(db_path),
        "--enriched-dir",
        str(enriched_dir),
    )
    assert result.returncode == 0, (
        f"exit={result.returncode}\nstdout={result.stdout[:400]}\nstderr={result.stderr[:400]}"
    )
    assert "L6 complete" in result.stdout, f"Expected 'L6 complete' summary: {result.stdout[:400]}"

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(DISTINCT hk_ticker) FROM companies").fetchone()[0]
    assert count == 3, f"Expected 3 companies, got {count}"
    uses_count = conn.execute("SELECT COUNT(*) FROM uses").fetchone()[0]
    assert uses_count == 6, f"Expected 6 uses (3*2), got {uses_count}"
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# BB-008: --all with empty directory produces [WARN]
# ═══════════════════════════════════════════════════════════════════════════


def test_all_empty_dir_produces_warn(tmp_path: Path) -> None:
    """--all with an empty enriched directory produces [WARN] and exits 0."""
    db_path = tmp_path / "test.db"
    enriched_dir = tmp_path / "enriched"
    enriched_dir.mkdir()

    result = _run_l6_cli(
        "--all",
        "--db",
        str(db_path),
        "--enriched-dir",
        str(enriched_dir),
    )
    assert result.returncode == 0, f"Empty dir should exit 0, got {result.returncode}"
    combined = result.stdout + result.stderr
    assert "[WARN]" in combined, (
        f"Expected [WARN] diagnostic: stdout={result.stdout[:300]} stderr={result.stderr[:300]}"
    )
    assert "No enriched JSON" in combined, f"Expected 'No enriched JSON' message: {combined[:400]}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-009: --dry-run single file does not modify DB
# ═══════════════════════════════════════════════════════════════════════════


def test_dry_run_single_does_not_modify_db(tmp_path: Path) -> None:
    """--dry-run with a single file prints preview, does not write to DB."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234")
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path), "--dry-run")
    assert result.returncode == 0, f"exit={result.returncode}\nstderr={result.stderr[:400]}"
    assert "[DRY-RUN]" in result.stdout, f"Expected [DRY-RUN] in stdout: {result.stdout[:300]}"
    assert "01234" in result.stdout, f"Expected ticker in preview: {result.stdout[:300]}"

    # DB file should either not exist or have no user tables
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        conn.close()
        assert len(tables) == 0, (
            f"DB should have no user tables after dry-run, got: {[t[0] for t in tables]}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# BB-010: --dry-run --all does not modify DB
# ═══════════════════════════════════════════════════════════════════════════


def test_dry_run_all_does_not_modify_db(tmp_path: Path) -> None:
    """--dry-run --all prints previews, does not write to DB."""
    db_path = tmp_path / "test.db"
    enriched_dir = tmp_path / "enriched"
    enriched_dir.mkdir()

    for ticker in ("01234", "56789"):
        rec = _enriched_record(ticker)
        (enriched_dir / f"{ticker}_enriched.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_l6_cli(
        "--all",
        "--db",
        str(db_path),
        "--enriched-dir",
        str(enriched_dir),
        "--dry-run",
    )
    assert result.returncode == 0

    # DB should have no user tables
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        conn.close()
        assert len(tables) == 0, (
            f"DB should have no user tables after dry-run, got: {[t[0] for t in tables]}"
        )

    # Should mention dry-run in output
    combined = result.stdout + result.stderr
    assert "dry-run" in combined.lower(), f"Expected dry-run mention: {combined[:400]}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-011: Idempotency -- loading same record twice yields identical DB state
# ═══════════════════════════════════════════════════════════════════════════


def test_idempotent_load_yields_identical_db(tmp_path: Path) -> None:
    """Loading the same enriched JSON twice produces byte-identical DB state
    (excluding updated_at which changes between runs)."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234")
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # First load
    r1 = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert r1.returncode == 0

    conn = sqlite3.connect(str(db_path))
    cols_companies = [c[1] for c in conn.execute("PRAGMA table_info(companies)").fetchall()]
    # Skip updated_at (last column)
    companies_1 = [
        tuple(row[: len(cols_companies) - 1])  # exclude updated_at
        for row in conn.execute("SELECT * FROM companies ORDER BY hk_ticker")
    ]
    uses_1 = list(conn.execute("SELECT * FROM uses ORDER BY hk_ticker, use_id"))
    use_tags_1 = list(
        conn.execute("SELECT * FROM use_tags ORDER BY hk_ticker, use_id, dimension, value")
    )
    conn.close()

    # Second load (same file)
    r2 = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert r2.returncode == 0

    conn = sqlite3.connect(str(db_path))
    companies_2 = [
        tuple(row[: len(cols_companies) - 1])  # exclude updated_at
        for row in conn.execute("SELECT * FROM companies ORDER BY hk_ticker")
    ]
    uses_2 = list(conn.execute("SELECT * FROM uses ORDER BY hk_ticker, use_id"))
    use_tags_2 = list(
        conn.execute("SELECT * FROM use_tags ORDER BY hk_ticker, use_id, dimension, value")
    )
    conn.close()

    # Row counts must match
    assert len(companies_1) == len(companies_2)
    assert len(uses_1) == len(uses_2)
    assert len(use_tags_1) == len(use_tags_2)

    # Full data must be identical (excluding updated_at)
    assert companies_1 == companies_2, (
        f"Companies differ: first={companies_1}, second={companies_2}"
    )
    assert uses_1 == uses_2, "Uses differ between loads"
    assert use_tags_1 == use_tags_2, "use_tags differ between loads"


# ═══════════════════════════════════════════════════════════════════════════
# BB-012: Loading updated record reflects changes in DB
# ═══════════════════════════════════════════════════════════════════════════


def test_updated_record_reflects_in_db(tmp_path: Path) -> None:
    """When a record's data changes, re-loading updates the DB accordingly."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"

    # First load
    record1 = _enriched_record("01234", company_name="Original Corp")
    json_file.write_text(json.dumps(record1, ensure_ascii=False), encoding="utf-8")
    r1 = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert r1.returncode == 0

    conn = sqlite3.connect(str(db_path))
    name1 = conn.execute(
        "SELECT company_name_en FROM companies WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    assert name1 == "Original Corp"
    conn.close()

    # Second load with updated data
    record2 = _enriched_record("01234", company_name="Updated Corp", total_proceeds=6000.0)
    json_file.write_text(json.dumps(record2, ensure_ascii=False), encoding="utf-8")
    r2 = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert r2.returncode == 0

    conn = sqlite3.connect(str(db_path))
    name2 = conn.execute(
        "SELECT company_name_en FROM companies WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    proceeds = conn.execute(
        "SELECT total_net_proceeds FROM companies WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    conn.close()

    assert name2 == "Updated Corp", f"Expected 'Updated Corp', got {name2}"
    assert proceeds == 6000.0, f"Expected 6000.0, got {proceeds}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-013: --db flag creates DB at custom path
# ═══════════════════════════════════════════════════════════════════════════


def test_custom_db_path_creates_db(tmp_path: Path) -> None:
    """--db flag creates the SQLite database at the specified path."""
    db_path = tmp_path / "custom" / "subdir" / "ipo.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234")
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert result.returncode == 0, f"exit={result.returncode}\nstderr={result.stderr[:400]}"
    assert db_path.exists(), f"DB not created at {db_path}"

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    assert count == 1


# ═══════════════════════════════════════════════════════════════════════════
# BB-014: DB contains all required tables after loading
# ═══════════════════════════════════════════════════════════════════════════

_REQUIRED_TABLES = {
    "companies",
    "uses",
    "use_tags",
    "company_tags",
    "pipeline_runs",
    "taxonomy_proposals",
}


def test_db_contains_all_required_tables(tmp_path: Path) -> None:
    """After loading a record, the SQLite DB contains all 6 required tables."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234")
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert result.returncode == 0

    conn = sqlite3.connect(str(db_path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()

    for required in sorted(_REQUIRED_TABLES):
        assert required in tables, f"Missing required table: {required}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-015: Output on stdout contains ticker and use count after load
# ═══════════════════════════════════════════════════════════════════════════


def test_stdout_contains_loading_info(tmp_path: Path) -> None:
    """Successful load prints [L6] with ticker and use count on stdout."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234")
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert result.returncode == 0

    assert "[L6]" in result.stdout, f"Expected [L6] prefix in stdout: {result.stdout[:300]}"
    assert "01234" in result.stdout, f"Expected ticker '01234' in stdout: {result.stdout[:300]}"
    assert "uses" in result.stdout.lower(), (
        f"Expected 'uses' mention in stdout: {result.stdout[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BB-016: Invalid JSON produces [ERROR] on stderr in --all mode
# ═══════════════════════════════════════════════════════════════════════════


def test_all_partial_failure_reports_error_on_stderr(tmp_path: Path) -> None:
    """--all with a mix of valid and invalid JSON files reports [ERROR]
    on stderr for the invalid file, while continuing to process others."""
    db_path = tmp_path / "test.db"
    enriched_dir = tmp_path / "enriched"
    enriched_dir.mkdir()

    # Good file
    (enriched_dir / "good_enriched.json").write_text(
        json.dumps(_enriched_record("01234"), ensure_ascii=False), encoding="utf-8"
    )
    # Bad file
    (enriched_dir / "bad_enriched.json").write_text("not valid json", encoding="utf-8")

    result = _run_l6_cli(
        "--all",
        "--db",
        str(db_path),
        "--enriched-dir",
        str(enriched_dir),
    )
    assert result.returncode == 0, (
        f"Partial failure should not cause non-zero exit in --all mode. exit={result.returncode}"
    )

    # [ERROR] must be on stderr
    assert "[ERROR]" in result.stderr, f"[ERROR] missing from stderr: stderr={result.stderr[:400]}"
    assert "bad_enriched.json" in result.stderr, (
        f"Expected bad file name on stderr: {result.stderr[:400]}"
    )

    # Good file should still have been loaded
    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM companies WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    conn.close()
    assert count == 1, "Good file should still have been loaded"


# ═══════════════════════════════════════════════════════════════════════════
# BB-017: Multiple tickers maintain isolation in DB
# ═══════════════════════════════════════════════════════════════════════════


def test_multiple_tickers_isolated(tmp_path: Path) -> None:
    """Loading multiple tickers keeps their data correctly scoped by ticker
    with no cross-contamination."""
    db_path = tmp_path / "test.db"

    # Load ticker A
    json_a = tmp_path / "a_enriched.json"
    rec_a = _enriched_record(
        "00001",
        company_name="Company A",
        uses=[
            {
                "use_id": "use_a",
                "parent_category": "Growth",
                "main_category": "Tech",
                "sub_category": None,
                "category_raw": "tech",
                "percentage": 100.0,
                "amount_hkd_million": 1000.0,
                "description": "A uses.",
                "source_text": "...",
            }
        ],
        enrichments={"geo": {"version": 1, "by_use_id": {"use_a": "mainland"}}},
    )
    json_a.write_text(json.dumps(rec_a, ensure_ascii=False), encoding="utf-8")
    _run_l6_cli(str(json_a), "--db", str(db_path))

    # Load ticker B
    json_b = tmp_path / "b_enriched.json"
    rec_b = _enriched_record(
        "00002",
        company_name="Company B",
        uses=[
            {
                "use_id": "use_b",
                "parent_category": "Working Capital",
                "main_category": "WC",
                "sub_category": None,
                "category_raw": "wc",
                "percentage": 100.0,
                "amount_hkd_million": 2000.0,
                "description": "B uses.",
                "source_text": "...",
            }
        ],
        enrichments={"commitment": {"version": 1, "by_use_id": {"use_b": "committed"}}},
    )
    json_b.write_text(json.dumps(rec_b, ensure_ascii=False), encoding="utf-8")
    _run_l6_cli(str(json_b), "--db", str(db_path))

    conn = sqlite3.connect(str(db_path))

    # Each company exists
    companies = conn.execute(
        "SELECT hk_ticker, company_name_en FROM companies ORDER BY hk_ticker"
    ).fetchall()
    assert len(companies) == 2
    assert companies[0] == ("00001", "Company A")
    assert companies[1] == ("00002", "Company B")

    # Uses are scoped correctly
    uses_a = conn.execute("SELECT use_id FROM uses WHERE hk_ticker = ?", ("00001",)).fetchall()
    assert len(uses_a) == 1 and uses_a[0][0] == "use_a"

    uses_b = conn.execute("SELECT use_id FROM uses WHERE hk_ticker = ?", ("00002",)).fetchall()
    assert len(uses_b) == 1 and uses_b[0][0] == "use_b"

    # Tags are scoped correctly
    tags_a = conn.execute(
        "SELECT dimension FROM use_tags WHERE hk_ticker = ?", ("00001",)
    ).fetchall()
    assert {t[0] for t in tags_a} == {"geo"}

    tags_b = conn.execute(
        "SELECT dimension FROM use_tags WHERE hk_ticker = ?", ("00002",)
    ).fetchall()
    assert {t[0] for t in tags_b} == {"commitment"}

    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# BB-018: Re-loading with fewer uses removes old uses (delete-then-insert)
# ═══════════════════════════════════════════════════════════════════════════


def test_reload_with_fewer_uses_removes_old_uses(tmp_path: Path) -> None:
    """When a record is re-loaded with fewer uses than before, old uses are
    deleted and new ones are inserted (per-ticker delete-then-insert)."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"

    # First load with 2 uses
    record1 = _enriched_record("01234")
    json_file.write_text(json.dumps(record1, ensure_ascii=False), encoding="utf-8")
    r1 = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert r1.returncode == 0

    conn = sqlite3.connect(str(db_path))
    initial_count = conn.execute(
        "SELECT COUNT(*) FROM uses WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    conn.close()
    assert initial_count == 2

    # Second load with only 1 use
    record2 = _enriched_record(
        "01234",
        uses=[
            {
                "use_id": "use_new",
                "parent_category": "Growth",
                "main_category": "New Category",
                "sub_category": None,
                "category_raw": "new",
                "percentage": 100.0,
                "amount_hkd_million": 5000.0,
                "description": "New single use.",
                "source_text": "...",
            }
        ],
        enrichments={},
    )
    json_file.write_text(json.dumps(record2, ensure_ascii=False), encoding="utf-8")
    r2 = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert r2.returncode == 0

    conn = sqlite3.connect(str(db_path))
    final_count = conn.execute(
        "SELECT COUNT(*) FROM uses WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    final_use_id = conn.execute(
        "SELECT use_id FROM uses WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    conn.close()

    assert final_count == 1, f"Expected 1 use after re-load, got {final_count}"
    assert final_use_id == "use_new", f"Expected use_new, got {final_use_id}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-019: Empty uses list loads company with zero uses
# ═══════════════════════════════════════════════════════════════════════════


def test_empty_uses_loads_company_only(tmp_path: Path) -> None:
    """An enriched record with an empty uses list still loads the company row
    but inserts no uses or use_tags rows."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234", uses=[], enrichments={})
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path))
    assert result.returncode == 0, f"exit={result.returncode}\nstderr={result.stderr[:400]}"

    conn = sqlite3.connect(str(db_path))
    company = conn.execute(
        "SELECT hk_ticker FROM companies WHERE hk_ticker = ?", ("01234",)
    ).fetchone()
    uses_count = conn.execute(
        "SELECT COUNT(*) FROM uses WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    tags_count = conn.execute(
        "SELECT COUNT(*) FROM use_tags WHERE hk_ticker = ?", ("01234",)
    ).fetchone()[0]
    conn.close()

    assert company is not None, "Company row should exist"
    assert uses_count == 0, f"Expected 0 uses, got {uses_count}"
    assert tags_count == 0, f"Expected 0 tags, got {tags_count}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-020: --enriched-dir flag works with --all
# ═══════════════════════════════════════════════════════════════════════════


def test_enriched_dir_flag_uses_custom_directory(tmp_path: Path) -> None:
    """--enriched-dir flag directs --all to load from the specified directory."""
    db_path = tmp_path / "test.db"
    custom_dir = tmp_path / "custom_enriched"
    custom_dir.mkdir()

    rec = _enriched_record("01234")
    (custom_dir / "01234_enriched.json").write_text(
        json.dumps(rec, ensure_ascii=False), encoding="utf-8"
    )

    result = _run_l6_cli(
        "--all",
        "--db",
        str(db_path),
        "--enriched-dir",
        str(custom_dir),
    )
    assert result.returncode == 0, (
        f"exit={result.returncode}\nstdout={result.stdout[:400]}\nstderr={result.stderr[:400]}"
    )

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    assert count == 1, f"Expected 1 company loaded from custom dir, got {count}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-021: --all summary reports correct loaded/total counts
# ═══════════════════════════════════════════════════════════════════════════


def test_all_summary_reports_correct_counts(tmp_path: Path) -> None:
    """--all final summary line reports correct 'loaded' and 'total' counts."""
    db_path = tmp_path / "test.db"
    enriched_dir = tmp_path / "enriched"
    enriched_dir.mkdir()

    # 3 good files + 1 bad
    for ticker in ("00001", "00002", "00003"):
        rec = _enriched_record(ticker)
        (enriched_dir / f"{ticker}_enriched.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8"
        )
    (enriched_dir / "bad.json").write_text("invalid json {", encoding="utf-8")

    result = _run_l6_cli(
        "--all",
        "--db",
        str(db_path),
        "--enriched-dir",
        str(enriched_dir),
    )
    assert result.returncode == 0

    combined = result.stdout + result.stderr
    assert "L6 complete" in combined, f"Expected 'L6 complete' summary: {combined[:400]}"
    # Should show 3 loaded of 4 total (one failed)
    assert "3 loaded" in combined, f"Expected '3 loaded': {combined[:400]}"
    assert "4 total" in combined, f"Expected '4 total': {combined[:400]}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-022: Dry-run preview includes use and tag counts
# ═══════════════════════════════════════════════════════════════════════════


def test_dry_run_preview_includes_use_and_tag_counts(tmp_path: Path) -> None:
    """--dry-run preview must show the number of uses and tags that would be loaded."""
    db_path = tmp_path / "test.db"
    json_file = tmp_path / "01234_enriched.json"
    record = _enriched_record("01234")
    # 2 uses, 4 enrichment tags
    json_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l6_cli(str(json_file), "--db", str(db_path), "--dry-run")
    assert result.returncode == 0

    assert "uses=2" in result.stdout, f"Expected 'uses=2' in preview: {result.stdout[:300]}"
    assert "tags=4" in result.stdout, f"Expected 'tags=4' in preview: {result.stdout[:300]}"
