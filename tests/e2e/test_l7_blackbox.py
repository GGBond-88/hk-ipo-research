"""Black-box tests for L7 dashboard export CLI (Task 019).

These tests invoke ``python -m hk_ipo.analysis.export`` via subprocess and
verify behaviour through exit codes, stdout/stderr, and output JSON files.
They do NOT import hk_ipo internals directly -- only the external DB schema
is known (via raw SQL), and all JSON outputs are validated against their
documented structure.
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
# Schema DDL (externally documented, NOT imported from hk_ipo internals)
# ---------------------------------------------------------------------------

_DDL_STATEMENTS: list[str] = [
    """CREATE TABLE IF NOT EXISTS companies (
        hk_ticker            TEXT PRIMARY KEY,
        company_name_en      TEXT NOT NULL,
        listing_date         TEXT,
        document_date        TEXT,
        industry_primary     TEXT,
        industry_source      TEXT,
        total_net_proceeds   REAL,
        currency             TEXT DEFAULT 'HKD',
        schema_version       TEXT NOT NULL,
        needs_human_review   INTEGER NOT NULL DEFAULT 0,
        review_reasons       TEXT,
        updated_at           TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS uses (
        use_id               TEXT NOT NULL,
        hk_ticker            TEXT NOT NULL REFERENCES companies(hk_ticker) ON DELETE CASCADE,
        parent_category      TEXT NOT NULL,
        main_category        TEXT NOT NULL,
        sub_category         TEXT,
        category_raw         TEXT,
        percentage           REAL NOT NULL,
        amount_hkd_million   REAL,
        description          TEXT,
        source_text          TEXT,
        PRIMARY KEY (hk_ticker, use_id)
    )""",
    """CREATE TABLE IF NOT EXISTS use_tags (
        hk_ticker            TEXT NOT NULL,
        use_id               TEXT NOT NULL,
        dimension            TEXT NOT NULL,
        value                TEXT NOT NULL,
        confidence           REAL,
        tool_version         INTEGER NOT NULL,
        PRIMARY KEY (hk_ticker, use_id, dimension, value),
        FOREIGN KEY (hk_ticker, use_id) REFERENCES uses(hk_ticker, use_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS company_tags (
        hk_ticker            TEXT NOT NULL,
        dimension            TEXT NOT NULL,
        value                TEXT NOT NULL,
        confidence           REAL,
        tool_version         INTEGER NOT NULL,
        PRIMARY KEY (hk_ticker, dimension, value)
    )""",
    """CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id               TEXT NOT NULL,
        hk_ticker            TEXT NOT NULL,
        stage                TEXT NOT NULL,
        status               TEXT NOT NULL,
        input_hash           TEXT,
        output_path          TEXT,
        error_message        TEXT,
        started_at           TEXT NOT NULL,
        finished_at          TEXT NOT NULL,
        PRIMARY KEY (run_id, hk_ticker, stage)
    )""",
    """CREATE TABLE IF NOT EXISTS taxonomy_proposals (
        proposed_label       TEXT NOT NULL,
        parent_category      TEXT NOT NULL,
        main_category        TEXT NOT NULL,
        occurrences          INTEGER NOT NULL DEFAULT 1,
        first_seen_ticker    TEXT,
        first_seen_at        TEXT NOT NULL,
        promoted             INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (proposed_label, parent_category, main_category)
    )""",
]


# ---------------------------------------------------------------------------
# Helper: run L7 CLI via subprocess
# ---------------------------------------------------------------------------


def _run_l7_cli(
    *args: str,
    cwd: Path | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m hk_ipo.analysis.export`` via subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.analysis.export", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or PROJECT_ROOT),
        env=dict(os.environ),
        check=False,
    )


# ---------------------------------------------------------------------------
# Helper: build a test DB with known data
# ---------------------------------------------------------------------------


def _create_empty_db(db_path: Path) -> sqlite3.Connection:
    """Create an empty SQLite DB with the full schema (no data rows)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    for ddl in _DDL_STATEMENTS:
        conn.execute(ddl)
    conn.commit()
    return conn


def _create_populated_db(db_path: Path) -> None:
    """Create a DB seeded with one company, two uses, and 13 use_tags."""
    conn = _create_empty_db(db_path)

    conn.execute("""
        INSERT INTO companies (hk_ticker, company_name_en, listing_date,
            industry_primary, industry_source, total_net_proceeds,
            schema_version, needs_human_review, updated_at)
        VALUES ('01234', 'Test Corp', '2024-07-12',
            'Software & Services', 'prospectus', 5000.0,
            '2.0', 0, '2026-01-01')
    """)

    for uid, parent, main, sub, pct, amt in [
        ("use_001", "Growth", "R&D and Technology", "Core product R&D", 60.0, 3000.0),
        ("use_002", "Working Capital", "General Working Capital", None, 40.0, 2000.0),
    ]:
        conn.execute(
            """
            INSERT INTO uses (use_id, hk_ticker, parent_category, main_category,
                sub_category, percentage, amount_hkd_million)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (uid, "01234", parent, main, sub, pct, amt),
        )

    tags: list[tuple[str, str, str, str]] = [
        ("01234", "use_001", "geo", "overseas"),
        ("01234", "use_001", "country", "SG"),
        ("01234", "use_001", "country", "CN"),
        ("01234", "use_001", "specificity", "specific"),
        ("01234", "use_001", "timeline", "0-12m"),
        ("01234", "use_001", "capex_opex", "opex"),
        ("01234", "use_001", "commitment", "committed"),
        ("01234", "use_002", "geo", "domestic_hk"),
        ("01234", "use_002", "specificity", "general"),
        ("01234", "use_002", "timeline", "12-24m"),
        ("01234", "use_002", "capex_opex", "capex"),
        ("01234", "use_002", "esg_tag", "green"),
        ("01234", "use_002", "commitment", "discretionary"),
    ]
    for ticker, use_id, dim, val in tags:
        conn.execute(
            """
            INSERT INTO use_tags (hk_ticker, use_id, dimension, value, tool_version)
            VALUES (?, ?, ?, ?, 1)
        """,
            (ticker, use_id, dim, val),
        )

    conn.commit()
    conn.close()


def _create_multi_company_db(db_path: Path) -> None:
    """Create a DB with two companies, multiple uses."""
    conn = _create_empty_db(db_path)

    conn.execute("""
        INSERT INTO companies (hk_ticker, company_name_en, listing_date,
            industry_primary, industry_source, total_net_proceeds,
            schema_version, needs_human_review, updated_at)
        VALUES ('01234', 'Company A', '2024-01-15',
            'Software & Services', 'prospectus', 3000.0,
            '2.0', 0, '2026-01-01')
    """)
    conn.execute("""
        INSERT INTO companies (hk_ticker, company_name_en, listing_date,
            industry_primary, industry_source, total_net_proceeds,
            schema_version, needs_human_review, updated_at)
        VALUES ('05678', 'Company B', '2024-06-01',
            'Software & Services', 'prospectus', 7000.0,
            '2.0', 0, '2026-02-01')
    """)

    for ticker, uid, parent, main, pct, amt in [
        ("01234", "use_001", "Growth", "R&D and Technology", 60.0, 1800.0),
        ("01234", "use_002", "Working Capital", "General Working Capital", 40.0, 1200.0),
        ("05678", "use_003", "Growth", "R&D and Technology", 50.0, 3500.0),
        ("05678", "use_004", "Growth", "Sales and Marketing", 50.0, 3500.0),
    ]:
        conn.execute(
            """
            INSERT INTO uses (use_id, hk_ticker, parent_category, main_category,
                sub_category, percentage, amount_hkd_million)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
        """,
            (uid, ticker, parent, main, pct, amt),
        )

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-001: --help output lists all flags
# ═══════════════════════════════════════════════════════════════════════════


def test_help_output_lists_all_flags() -> None:
    """--help must document --db and --out flags."""
    result = _run_l7_cli("--help")
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr={result.stderr[:400]}"
    )
    assert "--db" in result.stdout, f"--db missing from help: {result.stdout[:400]}"
    assert "--out" in result.stdout, f"--out missing from help: {result.stdout[:400]}"
    assert "L7" in result.stdout or "export" in result.stdout.lower(), (
        f"Help should mention L7/export: {result.stdout[:400]}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-002: Nonexistent DB exits non-zero with [ERROR]
# ═══════════════════════════════════════════════════════════════════════════


def test_nonexistent_db_exits_nonzero(tmp_path: Path) -> None:
    """Passing --db with a nonexistent file exits non-zero with [ERROR]."""
    nonexistent = tmp_path / "does_not_exist.db"
    out_dir = tmp_path / "output"

    result = _run_l7_cli("--db", str(nonexistent), "--out", str(out_dir))
    assert result.returncode != 0, (
        f"Expected non-zero exit for nonexistent DB, got {result.returncode}"
    )
    combined = result.stdout + result.stderr
    assert "[ERROR]" in combined, (
        f"Expected [ERROR] diagnostic: stdout={result.stdout[:400]} stderr={result.stderr[:400]}"
    )
    assert "Database not found" in combined or str(nonexistent) in combined, (
        f"Expected 'Database not found' message: {combined[:500]}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-003: Export against valid DB creates all expected output files
# ═══════════════════════════════════════════════════════════════════════════


def test_export_creates_all_output_files(tmp_path: Path) -> None:
    """A valid DB with one company produces exactly 8 file types on disk."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0, (
        f"export failed (rc={result.returncode})\nstderr={result.stderr[:500]}"
    )

    expected_files = [
        "manifest.json",
        "companies.json",
        "taxonomy.json",
        "time_series.json",
        "by_industry.json",
        "by_geo.json",
        "cross_dim.json",
    ]
    for fname in expected_files:
        path = out_dir / fname
        assert path.exists(), f"Missing output file: {fname}"

    sankey_dir = out_dir / "sankey"
    assert sankey_dir.is_dir(), "Missing sankey/ directory"
    assert (sankey_dir / "01234.json").exists(), "Missing sankey/01234.json"

    # stdout should mention [L7] for each file written
    assert "[L7]" in result.stdout, f"Expected [L7] prefix in stdout: {result.stdout[:400]}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-004: manifest.json has expected structure and content-derived timestamp
# ═══════════════════════════════════════════════════════════════════════════


def test_manifest_json_structure(tmp_path: Path) -> None:
    """manifest.json must contain generated_at, schema_version, company_count,
    and taxonomy_sha with correct types and values."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "generated_at" in manifest, "manifest.json missing 'generated_at'"
    assert "schema_version" in manifest, "manifest.json missing 'schema_version'"
    assert "company_count" in manifest, "manifest.json missing 'company_count'"
    assert "taxonomy_sha" in manifest, "manifest.json missing 'taxonomy_sha'"

    assert manifest["company_count"] == 1
    assert isinstance(manifest["schema_version"], str)
    assert len(manifest["schema_version"]) > 0
    assert isinstance(manifest["taxonomy_sha"], str)
    assert len(manifest["taxonomy_sha"]) > 0

    # generated_at should be the seeded updated_at value, not wall-clock time
    assert manifest["generated_at"] == "2026-01-01", (
        f"Expected content-derived generated_at='2026-01-01', got {manifest['generated_at']!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-005: companies.json has expected structure
# ═══════════════════════════════════════════════════════════════════════════


def test_companies_json_structure(tmp_path: Path) -> None:
    """companies.json must contain 'companies' list and 'count' field."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    companies_data = json.loads((out_dir / "companies.json").read_text(encoding="utf-8"))
    assert "companies" in companies_data
    assert "count" in companies_data
    assert companies_data["count"] == len(companies_data["companies"])
    assert companies_data["count"] == 1

    company = companies_data["companies"][0]
    assert company["hk_ticker"] == "01234"
    assert company["company_name_en"] == "Test Corp"
    assert company["listing_date"] == "2024-07-12"
    assert company["industry_primary"] == "Software & Services"
    assert company["total_net_proceeds"] == 5000.0
    assert "currency" in company
    assert "needs_human_review" in company
    assert isinstance(company["needs_human_review"], bool)


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-006: taxonomy.json has expected structure
# ═══════════════════════════════════════════════════════════════════════════


def test_taxonomy_json_structure(tmp_path: Path) -> None:
    """taxonomy.json must contain 'categories' (dict) and 'parent_order' (list)."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    taxonomy = json.loads((out_dir / "taxonomy.json").read_text(encoding="utf-8"))
    assert "categories" in taxonomy, "taxonomy.json missing 'categories'"
    assert "parent_order" in taxonomy, "taxonomy.json missing 'parent_order'"
    assert isinstance(taxonomy["categories"], dict)
    assert isinstance(taxonomy["parent_order"], list)
    assert len(taxonomy["parent_order"]) >= 1, "parent_order should not be empty"

    # parent_order should contain known parent category names
    parent_names = set(taxonomy["parent_order"])
    assert "Growth" in parent_names, f"Expected 'Growth' in parent_order, got: {parent_names}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-007: time_series.json has expected structure
# ═══════════════════════════════════════════════════════════════════════════


def test_time_series_json_structure(tmp_path: Path) -> None:
    """time_series.json must be a list, each entry with 'year' key."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    ts_data = json.loads((out_dir / "time_series.json").read_text(encoding="utf-8"))
    assert isinstance(ts_data, list), "time_series.json must be a list"
    assert len(ts_data) >= 1, "Should have at least one year of data"

    for entry in ts_data:
        assert "year" in entry, f"Missing 'year' key in time_series entry: {entry}"
        assert isinstance(entry["year"], str)
        # Every non-year key should have a numeric value
        for k, v in entry.items():
            if k != "year":
                assert isinstance(v, (int, float)), (
                    f"Value for '{k}' should be numeric, got {type(v)}: {v}"
                )


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-008: by_industry.json has expected structure
# ═══════════════════════════════════════════════════════════════════════════


def test_by_industry_json_structure(tmp_path: Path) -> None:
    """by_industry.json must be a dict, each industry with 'companies' and
    'parents' keys."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    industry_data = json.loads((out_dir / "by_industry.json").read_text(encoding="utf-8"))
    assert isinstance(industry_data, dict)
    assert "Software & Services" in industry_data

    sw = industry_data["Software & Services"]
    assert "companies" in sw, "industry entry missing 'companies'"
    assert "parents" in sw, "industry entry missing 'parents'"
    assert sw["companies"] == 1
    assert isinstance(sw["parents"], dict)

    # Verify parent categories from seeded data appear
    assert "Growth" in sw["parents"], (
        f"Expected 'Growth' in parents, got {list(sw['parents'].keys())}"
    )
    assert "Working Capital" in sw["parents"]


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-009: by_geo.json has expected structure
# ═══════════════════════════════════════════════════════════════════════════


def test_by_geo_json_structure(tmp_path: Path) -> None:
    """by_geo.json must be a dict with geo regions containing total_hkd_million
    and companies counts."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    geo_data = json.loads((out_dir / "by_geo.json").read_text(encoding="utf-8"))
    assert isinstance(geo_data, dict)

    # Seeded data has geo=overseas (use_001, 3000) and geo=domestic_hk (use_002, 2000)
    assert "overseas" in geo_data, f"Missing 'overseas' in by_geo: {list(geo_data.keys())}"
    assert "domestic_hk" in geo_data, f"Missing 'domestic_hk' in by_geo: {list(geo_data.keys())}"

    overseas = geo_data["overseas"]
    assert "total_hkd_million" in overseas
    assert "companies" in overseas
    assert overseas["companies"] == 1
    assert overseas["total_hkd_million"] == 3000.0

    domestic = geo_data["domestic_hk"]
    assert domestic["companies"] == 1
    assert domestic["total_hkd_million"] == 2000.0


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-010: cross_dim.json has expected structure with all 8 dimensions
# ═══════════════════════════════════════════════════════════════════════════


def test_cross_dim_json_structure(tmp_path: Path) -> None:
    """cross_dim.json must contain all 8 enrichment dimensions for client-side
    cross-filtering."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    cross_dim = json.loads((out_dir / "cross_dim.json").read_text(encoding="utf-8"))
    assert isinstance(cross_dim, list)
    assert len(cross_dim) == 2, f"Expected 2 uses, got {len(cross_dim)}"

    # Each use record must have all enrichment dimension keys
    required_keys = {
        "hk_ticker",
        "industry",
        "listing_date",
        "total_net_proceeds",
        "use_id",
        "parent_category",
        "percentage",
        "amount_hkd_million",
        "geo",
        "countries",
        "specificity",
        "timeline",
        "capex_opex",
        "esg_tag",
        "commitment",
    }
    for row in cross_dim:
        for key in required_keys:
            assert key in row, f"Missing key '{key}' in cross_dim row: {row['use_id']}"

    # Verify specific enrichment values from seeded data
    use1 = next(r for r in cross_dim if r["use_id"] == "use_001")
    assert use1["geo"] == "overseas"
    assert use1["specificity"] == "specific"
    assert use1["timeline"] == "0-12m"
    assert use1["capex_opex"] == "opex"
    assert use1["commitment"] == "committed"
    assert use1["esg_tag"] is None
    assert "SG" in use1["countries"], f"Expected SG in countries: {use1['countries']}"
    assert "CN" in use1["countries"], f"Expected CN in countries: {use1['countries']}"

    use2 = next(r for r in cross_dim if r["use_id"] == "use_002")
    assert use2["geo"] == "domestic_hk"
    assert use2["esg_tag"] == "green"
    assert use2["commitment"] == "discretionary"


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-011: sankey/<ticker>.json has expected structure
# ═══════════════════════════════════════════════════════════════════════════


def test_sankey_json_structure(tmp_path: Path) -> None:
    """Each sankey/<ticker>.json must have 'nodes', 'links', and
    'total_net_proceeds' keys."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    sankey = json.loads((out_dir / "sankey" / "01234.json").read_text(encoding="utf-8"))
    assert "nodes" in sankey, "sankey JSON missing 'nodes'"
    assert "links" in sankey, "sankey JSON missing 'links'"
    assert "total_net_proceeds" in sankey, "sankey JSON missing 'total_net_proceeds'"

    assert isinstance(sankey["nodes"], list)
    assert isinstance(sankey["links"], list)
    assert isinstance(sankey["total_net_proceeds"], (int, float))

    # Should have at least the root node and parent nodes
    node_names = {n["name"] for n in sankey["nodes"]}
    assert "Total Net Proceeds" in node_names, "Missing root sankey node"
    assert "Growth" in node_names, "Missing 'Growth' parent node"
    assert "Working Capital" in node_names, "Missing 'Working Capital' parent node"

    # total_net_proceeds should sum to the full amount
    assert sankey["total_net_proceeds"] == 5000.0, (
        f"Expected total_net_proceeds=5000.0, got {sankey['total_net_proceeds']}"
    )

    # Each link must have source, target, value
    for link in sankey["links"]:
        assert "source" in link
        assert "target" in link
        assert "value" in link
        assert isinstance(link["value"], (int, float))


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-012: Idempotent export produces byte-identical output
# ═══════════════════════════════════════════════════════════════════════════


def test_export_idempotent(tmp_path: Path) -> None:
    """Two consecutive L7 runs against an unchanged DB must produce byte-identical
    JSON output files."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    r1 = _run_l7_cli("--db", str(db_path), "--out", str(out1))
    assert r1.returncode == 0, f"First export failed: {r1.stderr[:400]}"

    r2 = _run_l7_cli("--db", str(db_path), "--out", str(out2))
    assert r2.returncode == 0, f"Second export failed: {r2.stderr[:400]}"

    for f in out1.glob("**/*.json"):
        rel = f.relative_to(out1)
        other = out2 / rel
        assert other.exists(), f"File missing from second export: {rel}"
        content1 = f.read_text(encoding="utf-8")
        content2 = other.read_text(encoding="utf-8")
        assert content1 == content2, (
            f"Non-identical output for {rel}:\n"
            f"--- first ---\n{content1[:200]}\n"
            f"--- second ---\n{content2[:200]}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-013: generated_at is stable across separated runs
# ═══════════════════════════════════════════════════════════════════════════


def test_generated_at_is_content_derived(tmp_path: Path) -> None:
    """generated_at must be derived from DB content (max updated_at), NOT from
    wall-clock time. Two runs at different times produce the same generated_at."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out1 = tmp_path / "out1"
    r1 = _run_l7_cli("--db", str(db_path), "--out", str(out1))
    assert r1.returncode == 0

    m1 = json.loads((out1 / "manifest.json").read_text(encoding="utf-8"))

    # Second run (would differ if generated_at used datetime.now())
    out2 = tmp_path / "out2"
    r2 = _run_l7_cli("--db", str(db_path), "--out", str(out2))
    assert r2.returncode == 0

    m2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))

    assert m1["generated_at"] == m2["generated_at"], (
        f"generated_at must be stable across runs: {m1['generated_at']!r} != {m2['generated_at']!r}"
    )
    # Should equal the seeded updated_at
    assert m1["generated_at"] == "2026-01-01", f"Expected '2026-01-01', got {m1['generated_at']!r}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-014: Empty database produces valid output
# ═══════════════════════════════════════════════════════════════════════════


def test_empty_database_produces_valid_output(tmp_path: Path) -> None:
    """Export against an empty DB (schema only, no rows) must succeed and produce
    valid JSON files with sensible defaults."""
    db_path = tmp_path / "empty.db"
    conn = _create_empty_db(db_path)
    conn.close()

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0, (
        f"Empty DB export failed (rc={result.returncode})\nstderr={result.stderr[:400]}"
    )

    # All flat files should still be produced
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "companies.json").exists()
    assert (out_dir / "taxonomy.json").exists()
    assert (out_dir / "time_series.json").exists()
    assert (out_dir / "by_industry.json").exists()
    assert (out_dir / "by_geo.json").exists()
    assert (out_dir / "cross_dim.json").exists()
    assert (out_dir / "sankey").is_dir()

    # manifest should reflect empty state with epoch placeholder
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["company_count"] == 0
    assert manifest["generated_at"] == "1970-01-01T00:00:00Z", (
        f"Empty DB should use epoch placeholder, got {manifest['generated_at']!r}"
    )

    # companies should have empty list
    companies_data = json.loads((out_dir / "companies.json").read_text(encoding="utf-8"))
    assert companies_data["companies"] == []
    assert companies_data["count"] == 0

    # time_series should be empty list
    ts_data = json.loads((out_dir / "time_series.json").read_text(encoding="utf-8"))
    assert ts_data == []

    # by_industry should be empty dict
    industry_data = json.loads((out_dir / "by_industry.json").read_text(encoding="utf-8"))
    assert industry_data == {}

    # sankey dir should be empty
    sankey_files = list((out_dir / "sankey").glob("*.json"))
    assert len(sankey_files) == 0, (
        f"Expected empty sankey dir, got {[f.name for f in sankey_files]}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-015: Multiple companies export correctly
# ═══════════════════════════════════════════════════════════════════════════


def test_multiple_companies_export(tmp_path: Path) -> None:
    """Export with multiple companies produces correct counts and per-ticker
    sankey files."""
    db_path = tmp_path / "test.db"
    _create_multi_company_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0, f"Multi-company export failed: {result.stderr[:400]}"

    # manifest should reflect 2 companies
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["company_count"] == 2

    # companies.json should have both
    companies_data = json.loads((out_dir / "companies.json").read_text(encoding="utf-8"))
    assert companies_data["count"] == 2
    tickers = {c["hk_ticker"] for c in companies_data["companies"]}
    assert tickers == {"01234", "05678"}

    # sankey files for both tickers
    assert (out_dir / "sankey" / "01234.json").exists()
    assert (out_dir / "sankey" / "05678.json").exists()

    # by_industry should show correct total (2 companies in Software & Services)
    industry_data = json.loads((out_dir / "by_industry.json").read_text(encoding="utf-8"))
    assert industry_data["Software & Services"]["companies"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-016: --out flag respects custom output directory
# ═══════════════════════════════════════════════════════════════════════════


def test_custom_output_directory(tmp_path: Path) -> None:
    """--out flag writes all JSON files to the specified directory."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    custom_out = tmp_path / "custom" / "nested" / "data"
    result = _run_l7_cli("--db", str(db_path), "--out", str(custom_out))
    assert result.returncode == 0, f"Custom out dir export failed: {result.stderr[:400]}"

    assert custom_out.is_dir(), "Output directory was not created"
    assert (custom_out / "manifest.json").exists()
    assert (custom_out / "companies.json").exists()
    assert (custom_out / "sankey" / "01234.json").exists()


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-017: cross_dim.json row order is deterministic
# ═══════════════════════════════════════════════════════════════════════════


def test_cross_dim_row_order_deterministic(tmp_path: Path) -> None:
    """cross_dim.json row order must be deterministic (ORDER BY ticker, use_id)
    to support byte-identical idempotent exports."""
    db_path = tmp_path / "test.db"
    _create_multi_company_db(db_path)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    _run_l7_cli("--db", str(db_path), "--out", str(out1))
    _run_l7_cli("--db", str(db_path), "--out", str(out2))

    cd1 = json.loads((out1 / "cross_dim.json").read_text(encoding="utf-8"))
    cd2 = json.loads((out2 / "cross_dim.json").read_text(encoding="utf-8"))

    assert cd1 == cd2, "cross_dim.json must be identical across runs"

    # Verify ordering: all use_001 rows (01234) before use_003 rows (05678)
    [r["use_id"] for r in cd1]
    tickers_seq = [r["hk_ticker"] for r in cd1]
    # 01234 rows must come before 05678 rows
    idx_05678_first = next(i for i, t in enumerate(tickers_seq) if t == "05678")
    # All 01234 must be before first 05678
    for i in range(idx_05678_first):
        assert tickers_seq[i] == "01234", (
            f"Expected 01234 before 05678 in cross_dim output: {tickers_seq}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-018: Exported JSON files are valid UTF-8 with proper indentation
# ═══════════════════════════════════════════════════════════════════════════


def test_exported_json_valid_utf8_indented(tmp_path: Path) -> None:
    """All exported JSON files must be valid UTF-8 and use 2-space indentation."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    for json_file in out_dir.glob("**/*.json"):
        raw = json_file.read_text(encoding="utf-8")
        # Re-parse and re-serialize with indent=2; compare raw text structure
        parsed = json.loads(raw)
        # Verify first data line is indented (indent=2)
        lines = raw.split("\n")
        non_empty = [ln for ln in lines if ln.strip()]
        if len(non_empty) > 2:
            # Second line should have 2-space indent (after opening brace)
            second = non_empty[1]
            assert second.startswith("  "), (
                f"{json_file.name}: expected 2-space indent, got: {second[:20]!r}"
            )
        # Verify it's valid JSON with all expected keys preserved
        reserialized = json.dumps(parsed, ensure_ascii=False, indent=2)
        reparsed = json.loads(reserialized)
        assert reparsed == parsed, f"{json_file.name}: round-trip parse/serialize mismatch"


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-019: Stdout mentions each output file and ticker count
# ═══════════════════════════════════════════════════════════════════════════


def test_stdout_reports_all_outputs(tmp_path: Path) -> None:
    """stdout must contain [L7] lines for each output file and a sankey summary."""
    db_path = tmp_path / "test.db"
    _create_populated_db(db_path)

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    stdout = result.stdout

    # Each flat file should have a [L7] line
    expected_files = [
        "manifest.json",
        "companies.json",
        "taxonomy.json",
        "time_series.json",
        "by_industry.json",
        "by_geo.json",
        "cross_dim.json",
    ]
    for fname in expected_files:
        assert f"[L7] {fname}" in stdout, f"Missing [L7] {fname} in stdout: {stdout[:500]}"

    # sankey summary line
    assert "[L7] sankey/" in stdout, f"Missing [L7] sankey/ summary in stdout: {stdout[:500]}"
    assert "1 tickers" in stdout, f"Expected '1 tickers' in sankey summary: {stdout[:500]}"


# ═══════════════════════════════════════════════════════════════════════════
# BB-L7-020: sankey --empty ticker produces consistent output with
#           total_net_proceeds key present
# ═══════════════════════════════════════════════════════════════════════════


def test_sankey_empty_ticker_consistent_structure(tmp_path: Path) -> None:
    """A ticker with company but no uses must produce sankey with nodes=[],
    links=[], total_net_proceeds=0.0 (not missing the key)."""
    db_path = tmp_path / "test.db"
    conn = _create_empty_db(db_path)
    conn.execute("""
        INSERT INTO companies (hk_ticker, company_name_en, listing_date,
            industry_primary, industry_source, total_net_proceeds,
            schema_version, needs_human_review, updated_at)
        VALUES ('99999', 'Empty Corp', '2024-03-01',
            'Financials', 'prospectus', 1000.0,
            '2.0', 0, '2026-01-01')
    """)
    conn.commit()
    conn.close()

    out_dir = tmp_path / "output"
    result = _run_l7_cli("--db", str(db_path), "--out", str(out_dir))
    assert result.returncode == 0

    sankey = json.loads((out_dir / "sankey" / "99999.json").read_text(encoding="utf-8"))
    assert sankey["nodes"] == []
    assert sankey["links"] == []
    assert "total_net_proceeds" in sankey, "Empty-case sankey must include total_net_proceeds key"
    assert sankey["total_net_proceeds"] == 0.0
