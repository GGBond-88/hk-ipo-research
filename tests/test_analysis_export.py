"""Unit tests for src/hk_ipo/analysis/export.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hk_ipo.schema import SCHEMA_VERSION


def _setup_test_db(db_path: Path) -> None:
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    # Insert one company
    conn.execute("""
        INSERT INTO companies (hk_ticker, company_name_en, listing_date,
            industry_primary, industry_source, total_net_proceeds,
            schema_version, needs_human_review, updated_at)
        VALUES ('01234', 'Test Corp', '2024-07-12',
            'Software & Services', 'prospectus', 5000.0,
            '2.0', 0, '2026-01-01')
    """)
    # Insert two uses
    for uid, parent, main, pct, amt in [
        ("use_001", "Growth", "R&D and Technology", 60.0, 3000.0),
        ("use_002", "Working Capital", "General Working Capital", 40.0, 2000.0),
    ]:
        conn.execute(
            """
            INSERT INTO uses (
                use_id, hk_ticker, parent_category, main_category, percentage,
                amount_hkd_million
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (uid, "01234", parent, main, pct, amt),
        )
    # Insert tags for ALL 8 enrichment dimensions
    tags = [
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


def _setup_test_db_multi_company(db_path: Path) -> None:
    """Setup with 2 companies in same industry; one missing a parent category.

    Company 01234: uses only under "Working Capital" (alphabetically later)
    Company 05678: uses under both "Working Capital" AND "Growth" (alphabetically first)

    Without CR-001 fix, the "Growth" row (alphabetically first) encounters
    count=1 (only 05678) and sets industry count to 1 instead of true 2.

    Used to verify CR-001: company count is correct regardless of SQLite row order.
    """
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    # Two companies in same industry
    for ticker, name, date, updated in [
        ("01234", "Company A", "2024-01-15", "2026-01-01"),
        ("05678", "Company B", "2024-06-01", "2026-02-01"),
    ]:
        conn.execute(
            """
            INSERT INTO companies (hk_ticker, company_name_en, listing_date,
                industry_primary, industry_source, total_net_proceeds,
                schema_version, needs_human_review, updated_at)
            VALUES (?, ?, ?, 'Software & Services', 'prospectus', 3000.0,
                '2.0', 0, ?)
        """,
            (ticker, name, date, updated),
        )

    # 01234: uses only under "Working Capital" (count=1 in WC group)
    # 05678: uses under "Working Capital" AND "Growth" (count=2 in WC, 1 in Growth)
    # Without fix, "Growth" group (alphabetically first) sets count=1 instead of 2
    for ticker, uid, parent, main, pct, amt in [
        ("01234", "use_001", "Working Capital", "General Working Capital", 100.0, 3000.0),
        ("05678", "use_002", "Growth", "R&D and Technology", 60.0, 1800.0),
        ("05678", "use_003", "Working Capital", "General Working Capital", 40.0, 1200.0),
    ]:
        conn.execute(
            """
            INSERT INTO uses (
                use_id, hk_ticker, parent_category, main_category, percentage,
                amount_hkd_million
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (uid, ticker, parent, main, pct, amt),
        )

    conn.commit()
    conn.close()


def _setup_test_db_same_parent(db_path: Path) -> None:
    """Setup with 2 uses under same parent category for CR-003 sankey test."""
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    conn.execute("""
        INSERT INTO companies (hk_ticker, company_name_en, listing_date,
            industry_primary, industry_source, total_net_proceeds,
            schema_version, needs_human_review, updated_at)
        VALUES ('01234', 'Test Corp', '2024-07-12',
            'Software & Services', 'prospectus', 5000.0,
            '2.0', 0, '2026-01-01')
    """)

    # Two uses under same parent "Growth"
    for uid, parent, main, pct, amt in [
        ("use_001", "Growth", "R&D and Technology", 60.0, 3000.0),
        ("use_002", "Growth", "Sales and Marketing", 40.0, 2000.0),
    ]:
        conn.execute(
            """
            INSERT INTO uses (
                use_id, hk_ticker, parent_category, main_category, percentage,
                amount_hkd_million
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (uid, "01234", parent, main, pct, amt),
        )

    conn.commit()
    conn.close()


def test_export_companies_json(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_companies

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_companies(conn)
    conn.close()

    assert len(result["companies"]) == 1
    assert result["companies"][0]["hk_ticker"] == "01234"
    assert result["companies"][0]["company_name_en"] == "Test Corp"
    assert result["count"] == 1


def test_export_sankey_for_ticker(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_sankey

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_sankey(conn, "01234")
    conn.close()

    assert "nodes" in result
    assert "links" in result
    node_names = {n["name"] for n in result["nodes"]}
    assert "Total Net Proceeds" in node_names
    assert "Growth" in node_names
    assert "Working Capital" in node_names
    assert "Growth/R&D and Technology" in node_names


def test_export_time_series(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_time_series

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_time_series(conn)
    conn.close()

    assert isinstance(result, list)
    assert len(result) >= 1

    # CR-007: Validate output structure to prevent regressions
    year_entry = result[0]
    assert "year" in year_entry
    assert year_entry["year"] == "2024"
    # Should have at least one parent category key with a numeric value
    parent_values = {k: v for k, v in year_entry.items() if k != "year"}
    assert len(parent_values) >= 1
    assert "Growth" in parent_values
    assert isinstance(parent_values["Growth"], (int, float))
    assert parent_values["Growth"] == 60.0  # use_001 60%


def test_export_by_industry(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_by_industry

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_by_industry(conn)
    conn.close()

    assert "Software & Services" in result
    assert result["Software & Services"]["companies"] == 1


def test_export_by_geo(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_by_geo

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_by_geo(conn)
    conn.close()

    assert isinstance(result, dict)
    # CR-008: Validate actual geo regions and their aggregated data
    assert "overseas" in result, (
        f"Expected 'overseas' key in by_geo result, got keys: {list(result.keys())}"
    )
    assert "domestic_hk" in result, (
        f"Expected 'domestic_hk' key in by_geo result, got keys: {list(result.keys())}"
    )
    assert result["overseas"]["companies"] == 1
    assert result["overseas"]["total_hkd_million"] == 3000.0
    assert result["domestic_hk"]["companies"] == 1
    assert result["domestic_hk"]["total_hkd_million"] == 2000.0


def test_export_cross_dim(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_cross_dim

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_cross_dim(conn)
    conn.close()

    assert isinstance(result, list)
    assert len(result) >= 2  # two uses
    # Verify ALL 8 enrichment dimensions are present for client-side filtering
    use1 = next(r for r in result if r["use_id"] == "use_001")
    assert use1["geo"] == "overseas"
    assert "SG" in (use1["countries"] or "")
    assert "CN" in (use1["countries"] or "")
    assert use1["commitment"] == "committed"
    assert use1["specificity"] == "specific"
    assert use1["timeline"] == "0-12m"
    assert use1["capex_opex"] == "opex"
    assert use1["esg_tag"] is None  # no esg_tag on use_001

    use2 = next(r for r in result if r["use_id"] == "use_002")
    assert use2["geo"] == "domestic_hk"
    assert use2["commitment"] == "discretionary"
    assert use2["specificity"] == "general"
    assert use2["timeline"] == "12-24m"
    assert use2["capex_opex"] == "capex"
    assert use2["esg_tag"] == "green"


def test_export_manifest(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_manifest

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_manifest(conn)
    conn.close()

    assert "generated_at" in result
    assert "schema_version" in result
    assert result["company_count"] == 1
    # CR-002: schema_version must match the canonical SCHEMA_VERSION import
    assert result["schema_version"] == SCHEMA_VERSION


def test_export_manifest_generated_at_is_content_derived(tmp_path: Path) -> None:
    """PR-016 regression: generated_at must be derived from DB content
    (max companies.updated_at), not from datetime.now(), so two runs
    against an unchanged DB produce byte-identical manifest.json even
    when the runs are separated by time.

    Verify: (a) the value equals the seeded companies.updated_at

            (b) repeated calls return the same value.
    """
    from hk_ipo.analysis.export import export_manifest

    db = tmp_path / "test.db"
    _setup_test_db(db)  # seeds companies.updated_at = '2026-01-01'

    conn = sqlite3.connect(str(db))
    first = export_manifest(conn)
    second = export_manifest(conn)
    conn.close()

    assert first["generated_at"] == "2026-01-01"
    assert first["generated_at"] == second["generated_at"]


def test_full_export_writes_to_disk(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_all

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    out_dir = tmp_path / "output"
    export_all(conn, out_dir)
    conn.close()

    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "companies.json").exists()
    assert (out_dir / "taxonomy.json").exists()
    assert (out_dir / "time_series.json").exists()
    assert (out_dir / "by_industry.json").exists()
    assert (out_dir / "by_geo.json").exists()
    assert (out_dir / "cross_dim.json").exists()
    sankey_dir = out_dir / "sankey"
    assert sankey_dir.exists()
    assert (sankey_dir / "01234.json").exists()


def test_export_taxonomy_dedicated() -> None:
    """CR-012: verify export_taxonomy() output structure and content.
    Every public export function must have a dedicated test with
    structural assertions.  Validates keys, types, and data equality."""
    from hk_ipo.analysis.export import export_taxonomy
    from hk_ipo.taxonomy import PARENT_CATEGORIES, PARENT_TREE

    result = export_taxonomy()

    assert "categories" in result, "taxonomy.json must contain 'categories' key"
    assert "parent_order" in result, "taxonomy.json must contain 'parent_order' key"
    assert result["categories"] == PARENT_TREE, "categories must equal the canonical PARENT_TREE"
    assert result["parent_order"] == PARENT_CATEGORIES, (
        "parent_order must equal the canonical PARENT_CATEGORIES"
    )
    assert isinstance(result["categories"], dict)
    assert isinstance(result["parent_order"], list)
    assert len(result["parent_order"]) == 4  # Growth, Financing, Working Capital, Others


def test_export_manifest_empty_db(tmp_path: Path) -> None:
    """CR-013: empty-database fallback generated_at = "1970-01-01T00:00:00Z".
    When no companies exist, the else-branch in export_manifest must
    produce a stable epoch placeholder."""
    from hk_ipo.analysis.export import export_manifest
    from hk_ipo.storage.schema_sql import create_tables

    db = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    conn.commit()

    result = export_manifest(conn)
    conn.close()

    assert result["generated_at"] == "1970-01-01T00:00:00Z", (
        f"Empty DB: expected generated_at='1970-01-01T00:00:00Z', got {result['generated_at']!r}"
    )
    assert result["company_count"] == 0
    assert result["schema_version"] == SCHEMA_VERSION


def test_export_idempotent(tmp_path: Path) -> None:
    from hk_ipo.analysis.export import export_all

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    out1 = tmp_path / "out1"
    out1.mkdir()
    out2 = tmp_path / "out2"
    out2.mkdir()
    export_all(conn, out1)
    export_all(conn, out2)
    conn.close()

    for f in out1.glob("**/*.json"):
        rel = f.relative_to(out1)
        other = out2 / rel
        assert other.exists()
        assert f.read_text(encoding="utf-8") == other.read_text(encoding="utf-8")


# ── CR-001: export_by_industry company count independent of row order ────


def test_export_by_industry_company_count_consistent(tmp_path: Path) -> None:
    """CR-001: company count must be total distinct companies in the industry,
    not the count from the first parent-category group encountered.

    Company A has uses under Growth + Working Capital

    Company B has use only under Growth.
    Regardless of SQLite row order, count should be 2.
    """
    from hk_ipo.analysis.export import export_by_industry

    db = tmp_path / "test.db"
    _setup_test_db_multi_company(db)

    conn = sqlite3.connect(str(db))
    result = export_by_industry(conn)
    conn.close()

    assert "Software & Services" in result
    assert result["Software & Services"]["companies"] == 2
    # Also verify parent breakdown is correct
    assert "Growth" in result["Software & Services"]["parents"]
    assert "Working Capital" in result["Software & Services"]["parents"]


# ── CR-009: Sankey main-link and sub-link/node deduplication ──────────────


def _setup_test_db_sankey_dedup(db_path: Path) -> None:
    """CR-009: Two uses sharing same (parent, main, sub) triple.

    use_001: Growth / R&D and Technology / Core product R&D, 3000
    use_002: Growth / R&D and Technology / Core product R&D, 2000

    Without CR-009 fix:
      - Main-level: two links Growth→R&D and Technology (values 3000, 2000)
      - Sub-level: two nodes "Growth/R&D and Technology/Core product R&D"
        and two links to them

    After CR-009 fix:
      - Main-level: one link Growth→R&D and Technology (value 5000)
      - Sub-level: one node, one link (value 5000)
    """
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

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
        ("use_002", "Growth", "R&D and Technology", "Core product R&D", 40.0, 2000.0),
    ]:
        conn.execute(
            """
            INSERT INTO uses (use_id, hk_ticker, parent_category, main_category,
                sub_category, percentage, amount_hkd_million)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (uid, "01234", parent, main, sub, pct, amt),
        )

    conn.commit()
    conn.close()


def test_export_sankey_dedup_main_sub_links(tmp_path: Path) -> None:
    """CR-009: When multiple uses share the same (parent, main) pair or
    (parent, main, sub) triple, links and nodes must be deduplicated
    with accumulated values, not duplicated."""
    from hk_ipo.analysis.export import export_sankey

    db = tmp_path / "test.db"
    _setup_test_db_sankey_dedup(db)

    conn = sqlite3.connect(str(db))
    result = export_sankey(conn, "01234")
    conn.close()

    # Main-level dedup: exactly one link Growth→R&D with value 5000
    main_links = [
        ln
        for ln in result["links"]
        if ln["source"] == "Growth" and ln["target"] == "Growth/R&D and Technology"
    ]
    assert len(main_links) == 1, (
        f"CR-009: Expected 1 main-level link Growth→R&D, got {len(main_links)}"
    )
    assert main_links[0]["value"] == 5000.0, (
        f"CR-009: Expected main link value 5000.0, got {main_links[0]['value']}"
    )

    # Sub-level dedup: exactly one sub node
    sub_nodes = [
        n for n in result["nodes"] if n["name"] == "Growth/R&D and Technology/Core product R&D"
    ]
    assert len(sub_nodes) == 1, (
        f"CR-009: Expected 1 sub node, got {len(sub_nodes)} — duplicate nodes"
    )

    # Sub-level dedup: exactly one sub link with value 5000
    sub_links = [
        ln
        for ln in result["links"]
        if ln["source"] == "Growth/R&D and Technology"
        and ln["target"] == "Growth/R&D and Technology/Core product R&D"
    ]
    assert len(sub_links) == 1, (
        f"CR-009: Expected 1 sub-level link, got {len(sub_links)} — duplicate links"
    )
    assert sub_links[0]["value"] == 5000.0, (
        f"CR-009: Expected sub link value 5000.0, got {sub_links[0]['value']}"
    )

    # total_net_proceeds should be 5000 (sum of both uses)
    assert result["total_net_proceeds"] == 5000.0


# ── CR-003: Sankey parent-level link accumulation ────────────────────────


def test_export_sankey_accumulates_parent_value(tmp_path: Path) -> None:
    """CR-003: When multiple uses share the same parent, the parent-level
    Sankey link from 'Total Net Proceeds' should sum all use amounts,
    not just the first use's amount.

    use_001: Growth, R&D and Technology, 3000
    use_002: Growth, Sales and Marketing, 2000
    => parent-level link value = 5000
    """
    from hk_ipo.analysis.export import export_sankey

    db = tmp_path / "test.db"
    _setup_test_db_same_parent(db)

    conn = sqlite3.connect(str(db))
    result = export_sankey(conn, "01234")
    conn.close()

    # Find the parent-level link for "Growth"
    parent_link = next(
        (
            ln
            for ln in result["links"]
            if ln["source"] == "Total Net Proceeds" and ln["target"] == "Growth"
        ),
        None,
    )
    assert parent_link is not None, "Parent-level link to Growth not found"
    assert parent_link["value"] == 5000.0, (
        f"Expected parent link value 5000.0, got {parent_link['value']}"
    )

    # total_net_proceeds should also reflect the sum
    assert result["total_net_proceeds"] == 5000.0


# ── CR-005: Sankey empty ticker returns consistent structure ─────────────


def test_export_sankey_empty_ticker(tmp_path: Path) -> None:
    """CR-005: Sankey for a ticker with no uses must include
    'total_net_proceeds' key for consistent JSON structure."""
    from hk_ipo.analysis.export import export_sankey

    db = tmp_path / "test.db"
    _setup_test_db(db)

    # Ticker "99999" exists in companies but has no uses
    conn = sqlite3.connect(str(db))
    # Insert a company with no uses
    conn.execute("""
        INSERT INTO companies (hk_ticker, company_name_en, listing_date,
            industry_primary, industry_source, total_net_proceeds,
            schema_version, needs_human_review, updated_at)
        VALUES ('99999', 'Empty Corp', '2024-03-01',
            'Financials', 'prospectus', 1000.0,
            '2.0', 0, '2026-01-01')
    """)
    conn.commit()

    result = export_sankey(conn, "99999")
    conn.close()

    assert "nodes" in result
    assert "links" in result
    assert "total_net_proceeds" in result, (
        "CR-005: empty-case sankey must include total_net_proceeds key"
    )
    assert result["total_net_proceeds"] == 0.0
