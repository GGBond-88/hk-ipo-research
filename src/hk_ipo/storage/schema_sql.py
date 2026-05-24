"""SQLite DDL for the HK IPO pipeline.

Defines the full schema per spec section 4.2:
  companies, uses, use_tags, company_tags, pipeline_runs, taxonomy_proposals
Plus the 6 required indices.
"""

from __future__ import annotations

import sqlite3

DDL_STATEMENTS: list[str] = [
    # -- companies ---------------------------------------------------------
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
    # -- uses --------------------------------------------------------------
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
    # -- use_tags ----------------------------------------------------------
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
    # -- company_tags ------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS company_tags (
        hk_ticker            TEXT NOT NULL,
        dimension            TEXT NOT NULL,
        value                TEXT NOT NULL,
        confidence           REAL,
        tool_version         INTEGER NOT NULL,
        PRIMARY KEY (hk_ticker, dimension, value)
    )""",
    # -- pipeline_runs -----------------------------------------------------
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
    # -- taxonomy_proposals ------------------------------------------------
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
