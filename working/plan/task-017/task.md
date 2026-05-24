# Task 017: L6 SQLite schema

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L6 persists enriched records into SQLite. The schema defines all tables, indices, and foreign-key relationships.
- **Tech Stack:** Python 3.10+, sqlite3 (stdlib), pytest.

## Task Objective

Implement `storage/schema_sql.py` with the full SQLite DDL per spec section 4.2. Write tests verifying that all six tables, indices, and foreign-key cascades are created correctly. Follow TDD.

This is Task 17 of 27.

---

**Files:**
- Create: `src/hk_ipo/storage/__init__.py`
- Create: `src/hk_ipo/storage/schema_sql.py`
- Create: `tests/test_storage_schema.py`

- [ ] **Step 1: Create `src/hk_ipo/storage/__init__.py`**

```python
"""L6 storage layer: SQLite schema, loader, and helpers."""
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_storage_schema.py`:

```python
"""Unit tests for src/hk_ipo/storage/schema_sql.py."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def test_create_tables_creates_all_six():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    expected = {
        "companies", "uses", "use_tags", "company_tags",
        "pipeline_runs", "taxonomy_proposals",
    }
    assert tables >= expected
    conn.close()


def test_companies_has_required_columns():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
    for required in (
        "hk_ticker", "company_name_en", "listing_date", "document_date",
        "industry_primary", "industry_source", "total_net_proceeds",
        "currency", "schema_version", "needs_human_review",
        "review_reasons", "updated_at",
    ):
        assert required in cols, f"missing column: {required}"
    conn.close()


def test_uses_has_required_columns():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(uses)")}
    for required in (
        "use_id", "hk_ticker", "parent_category", "main_category",
        "sub_category", "category_raw", "percentage", "amount_hkd_million",
        "description", "source_text",
    ):
        assert required in cols, f"missing column: {required}"
    conn.close()


def test_use_tags_has_required_columns():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(use_tags)")}
    for required in ("hk_ticker", "use_id", "dimension", "value",
                      "confidence", "tool_version"):
        assert required in cols, f"missing column: {required}"
    conn.close()


def test_indices_created():
    from hk_ipo.storage.schema_sql import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    indices = {r[1] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )}
    assert indices >= {
        "idx_uses_parent", "idx_uses_main", "idx_use_tags_dim",
        "idx_company_tags_dim", "idx_companies_listing",
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
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "companies" in tables
    conn.close()
```

- [ ] **Step 3: Run tests; verify FAIL**

Run: `python -m pytest tests/test_storage_schema.py -v`

Expected: `ModuleNotFoundError` for `hk_ipo.storage.schema_sql`.

- [ ] **Step 4: Implement `src/hk_ipo/storage/schema_sql.py`**

```python
"""SQLite DDL for the HK IPO pipeline.

Defines the full schema per spec section 4.2:
  companies, uses, use_tags, company_tags, pipeline_runs, taxonomy_proposals
Plus the 6 required indices.
"""
from __future__ import annotations

import sqlite3

DDL_STATEMENTS: list[str] = [
    # ── companies ─────────────────────────────────────────────────────────
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

    # ── uses ──────────────────────────────────────────────────────────────
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

    # ── use_tags ──────────────────────────────────────────────────────────
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

    # ── company_tags ──────────────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS company_tags (
        hk_ticker            TEXT NOT NULL,
        dimension            TEXT NOT NULL,
        value                TEXT NOT NULL,
        confidence           REAL,
        tool_version         INTEGER NOT NULL,
        PRIMARY KEY (hk_ticker, dimension, value)
    )""",

    # ── pipeline_runs ─────────────────────────────────────────────────────
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

    # ── taxonomy_proposals ────────────────────────────────────────────────
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

INDEX_STATEMENTS: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_uses_parent        ON uses(parent_category)",
    "CREATE INDEX IF NOT EXISTS idx_uses_main          ON uses(parent_category, main_category)",
    "CREATE INDEX IF NOT EXISTS idx_use_tags_dim       ON use_tags(dimension, value)",
    "CREATE INDEX IF NOT EXISTS idx_company_tags_dim   ON company_tags(dimension, value)",
    "CREATE INDEX IF NOT EXISTS idx_companies_listing  ON companies(listing_date)",
    "CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry_primary)",
]


def create_tables(conn: sqlite3.Connection) -> None:
    """Execute all DDL statements on `conn`. Idempotent (IF NOT EXISTS)."""
    for ddl in DDL_STATEMENTS:
        conn.execute(ddl)
    for idx in INDEX_STATEMENTS:
        conn.execute(idx)
    conn.commit()
```

- [ ] **Step 5: Run tests; verify PASS**

Run: `python -m pytest tests/test_storage_schema.py -v`

Expected: All 7 tests pass.

- [ ] **Step 6: Run full suite (except e2e)**

Run: `python -m pytest -q --ignore=tests/e2e`
