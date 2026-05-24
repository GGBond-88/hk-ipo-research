"""Unit tests for src/hk_ipo/storage/schema_sql.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def test_create_tables_creates_all_six():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {
        "companies",
        "uses",
        "use_tags",
        "company_tags",
        "pipeline_runs",
        "taxonomy_proposals",
    }
    assert tables >= expected
    conn.close()


def test_companies_has_required_columns():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
    for required in (
        "hk_ticker",
        "company_name_en",
        "listing_date",
        "document_date",
        "industry_primary",
        "industry_source",
        "total_net_proceeds",
        "currency",
        "schema_version",
        "needs_human_review",
        "review_reasons",
        "updated_at",
    ):
        assert required in cols, f"missing column: {required}"
    conn.close()


def test_uses_has_required_columns():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(uses)")}
    for required in (
        "use_id",
        "hk_ticker",
        "parent_category",
        "main_category",
        "sub_category",
        "category_raw",
        "percentage",
        "amount_hkd_million",
        "description",
        "source_text",
    ):
        assert required in cols, f"missing column: {required}"
    conn.close()


def test_use_tags_has_required_columns():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(use_tags)")}
    for required in ("hk_ticker", "use_id", "dimension", "value", "confidence", "tool_version"):
        assert required in cols, f"missing column: {required}"
    conn.close()


def test_indices_created():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    indices = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert indices >= {
        "idx_uses_parent",
        "idx_uses_main",
        "idx_use_tags_dim",
        "idx_company_tags_dim",
        "idx_companies_listing",
        "idx_companies_industry",
    }
    conn.close()


def test_cascade_delete_company_removes_uses(tmp_path: Path):
    from hk_ipo.storage.schema_sql import create_tables

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    conn.execute(
        "INSERT INTO companies (hk_ticker, company_name_en, schema_version, updated_at) "
        "VALUES ('01234', 'Test Corp', '2.0', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO uses (use_id, hk_ticker, parent_category, main_category, percentage) "
        "VALUES ('use_001', '01234', 'Growth', 'R&D and Technology', 100.0)"
    )
    conn.commit()

    conn.execute("DELETE FROM companies WHERE hk_ticker = '01234'")
    rows = list(conn.execute("SELECT * FROM uses WHERE hk_ticker = '01234'"))
    assert rows == []
    conn.close()


def test_idempotent_create():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    create_tables(conn)  # second call must not fail
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "companies" in tables
    conn.close()
