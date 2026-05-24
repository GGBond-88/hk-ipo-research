# Task 018: L6 SQLite loader

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L6 loads enriched JSON into SQLite with transactional per-ticker upsert. Idempotent: loading the same enriched JSON twice yields byte-identical DB state.
- **Tech Stack:** Python 3.10+, sqlite3 (stdlib), pytest.

## Task Objective

Implement `storage/loader.py` with per-ticker transaction-based upsert, idempotency, `--dry-run`, and CLI interface. Delete-then-insert pattern for related rows (uses, use_tags, company_tags) per ticker. Follow TDD.

This is Task 18 of 27.

---

**Files:**
- Create: `src/hk_ipo/storage/loader.py`
- Create: `tests/test_storage_loader.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_storage_loader.py`:

```python
"""Unit tests for src/hk_ipo/storage/loader.py."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest


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
            "commitment": {"version": 1, "by_use_id": {"use_001": "committed", "use_002": "committed"}},
        },
    }


def test_upsert_inserts_company(tmp_path: Path):
    from hk_ipo.storage.loader import upsert
    from hk_ipo.storage.schema_sql import create_tables

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())
    row = conn.execute(
        "SELECT company_name_en, total_net_proceeds FROM companies WHERE hk_ticker = ?",
        ("01234",)
    ).fetchone()
    assert row is not None
    assert row[0] == "Test Corp"
    assert row[1] == 5000.0
    conn.close()


def test_upsert_inserts_uses(tmp_path: Path):
    from hk_ipo.storage.loader import upsert
    from hk_ipo.storage.schema_sql import create_tables

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())
    rows = list(conn.execute(
        "SELECT use_id, parent_category, main_category, percentage FROM uses "
        "WHERE hk_ticker = ? ORDER BY use_id", ("01234",)
    ))
    assert len(rows) == 2
    assert rows[0][0] == "use_001"
    assert rows[1][2] == "General Working Capital"
    conn.close()


def test_upsert_inserts_use_tags(tmp_path: Path):
    from hk_ipo.storage.loader import upsert
    from hk_ipo.storage.schema_sql import create_tables

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())
    tags = list(conn.execute(
        "SELECT use_id, dimension, value FROM use_tags WHERE hk_ticker = ?", ("01234",)
    ))
    assert len(tags) >= 2
    dims = {t[1] for t in tags}
    assert "geo" in dims
    assert "commitment" in dims
    conn.close()


def test_upsert_idempotent(tmp_path: Path):
    from hk_ipo.storage.loader import upsert
    from hk_ipo.storage.schema_sql import create_tables

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    upsert(conn, _sample_record())
    n_uses_1 = conn.execute("SELECT COUNT(*) FROM uses").fetchone()[0]
    n_tags_1 = conn.execute("SELECT COUNT(*) FROM use_tags").fetchone()[0]

    upsert(conn, _sample_record())
    n_uses_2 = conn.execute("SELECT COUNT(*) FROM uses").fetchone()[0]
    n_tags_2 = conn.execute("SELECT COUNT(*) FROM use_tags").fetchone()[0]

    assert n_uses_1 == n_uses_2
    assert n_tags_1 == n_tags_2
    conn.close()


def test_upsert_updates_changed_record(tmp_path: Path):
    from hk_ipo.storage.loader import upsert
    from hk_ipo.storage.schema_sql import create_tables

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
    from hk_ipo.storage.loader import upsert, dry_run_preview
    from hk_ipo.storage.schema_sql import create_tables

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    preview = dry_run_preview(conn, _sample_record())
    assert "01234" in str(preview)
    # DB unchanged
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert n == 0
    conn.close()
```

- [ ] **Step 2: Run tests; verify FAIL**

Run: `python -m pytest tests/test_storage_loader.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/hk_ipo/storage/loader.py`**

```python
"""L6 SQLite loader: idempotent upsert of enriched JSON into SQLite.

Per-ticker transactional upsert:
  1. DELETE all rows from uses, use_tags, company_tags for that ticker.
  2. INSERT new rows from the enriched record.
  3. UPSERT the companies row.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hk_ipo.storage.schema_sql import create_tables


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def upsert(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    """Upsert one enriched record in a single transaction."""
    ticker = record["hk_ticker"]
    conn.execute("PRAGMA foreign_keys = ON")

    # Delete existing rows for this ticker
    conn.execute("DELETE FROM uses WHERE hk_ticker = ?", (ticker,))
    conn.execute("DELETE FROM company_tags WHERE hk_ticker = ?", (ticker,))
    # use_tags cascade-deletes with uses

    # Upsert companies
    conn.execute("""
        INSERT INTO companies (
            hk_ticker, company_name_en, listing_date, document_date,
            industry_primary, industry_source,
            total_net_proceeds, currency, schema_version,
            needs_human_review, review_reasons, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(hk_ticker) DO UPDATE SET
            company_name_en = excluded.company_name_en,
            listing_date = excluded.listing_date,
            document_date = excluded.document_date,
            industry_primary = excluded.industry_primary,
            industry_source = excluded.industry_source,
            total_net_proceeds = excluded.total_net_proceeds,
            currency = excluded.currency,
            schema_version = excluded.schema_version,
            needs_human_review = excluded.needs_human_review,
            review_reasons = excluded.review_reasons,
            updated_at = excluded.updated_at
    """, (
        ticker,
        record.get("company_name_en", ""),
        record.get("listing_date"),
        record.get("document_date"),
        record.get("industry_primary"),
        record.get("industry_source"),
        record.get("total_net_proceeds_hkd_million"),
        record.get("currency", "HKD"),
        record.get("schema_version", "2.0"),
        1 if record.get("needs_human_review") else 0,
        json.dumps(record.get("review_reasons") or []),
        _now_iso(),
    ))

    # Insert uses
    for u in record.get("uses", []):
        conn.execute("""
            INSERT INTO uses (
                use_id, hk_ticker, parent_category, main_category,
                sub_category, category_raw, percentage,
                amount_hkd_million, description, source_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            u.get("use_id", ""),
            ticker,
            u.get("parent_category", ""),
            u.get("main_category", ""),
            u.get("sub_category"),
            u.get("category_raw"),
            u.get("percentage"),
            u.get("amount_hkd_million"),
            u.get("description"),
            u.get("source_text"),
        ))

    # Insert use_tags from enrichments
    enrichments = record.get("enrichments", {})
    for dim, block in enrichments.items():
        if not isinstance(block, dict):
            continue
        version = block.get("version", 1)
        by_use_id = block.get("by_use_id", {})

        # Company-level tags
        if dim == "industry":
            primary = block.get("primary")
            if primary:
                conn.execute("""
                    INSERT INTO company_tags (hk_ticker, dimension, value, confidence, tool_version)
                    VALUES (?, ?, ?, ?, ?)
                """, (ticker, dim, primary, None, version))
            continue

        for uid, values in by_use_id.items():
            vals = values if isinstance(values, list) else [values]
            for val in (v for v in vals if v):
                conn.execute("""
                    INSERT INTO use_tags (hk_ticker, use_id, dimension, value, confidence, tool_version)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ticker, uid, dim, val, None, version))

    conn.commit()


def dry_run_preview(conn: sqlite3.Connection, record: dict[str, Any]) -> str:
    """Return a human-readable preview of what would be upserted."""
    ticker = record["hk_ticker"]
    n_uses = len(record.get("uses", []))
    n_tags = sum(
        len(v) if isinstance(v, list) else (1 if v else 0)
        for dim, block in record.get("enrichments", {}).items()
        if isinstance(block, dict) and dim != "industry"
        for v in (block.get("by_use_id", {}).values())
    )
    return (
        f"[DRY-RUN] Would upsert ticker={ticker}: "
        f"company=1, uses={n_uses}, tags={n_tags}"
    )


def process_single(
    enriched_file: Path,
    db_path: Path,
    dry_run: bool = False,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    record = json.loads(enriched_file.read_text(encoding="utf-8"))
    conn = sqlite3.connect(str(db_path))
    try:
        create_tables(conn)
        if dry_run:
            print(dry_run_preview(conn, record))
        else:
            upsert(conn, record)
            print(f"[L6] {record.get('hk_ticker')}: {len(record.get('uses', []))} uses loaded")
    finally:
        conn.close()


def process_all(
    enriched_dir: Path,
    db_path: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    jsons = sorted(enriched_dir.glob("*.json"))
    if not jsons:
        print(f"[WARN] No enriched JSON files in {enriched_dir}")
        return {"loaded": 0, "total": 0}

    loaded = 0
    for jf in jsons:
        try:
            process_single(jf, db_path, dry_run=dry_run)
            loaded += 1
        except Exception as exc:
            print(f"[ERROR] {jf.name}: {exc}", file=sys.stderr)

    print(f"\nL6 complete: {loaded} loaded (of {len(jsons)} total)")
    return {"loaded": loaded, "total": len(jsons)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L6: load enriched JSON into SQLite")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("enriched", nargs="?", help="Path to enriched JSON file")
    parser.add_argument("--db", default="data/ipo.db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from hk_ipo.config import DATA_DIR
    ENRICHED_DIR = DATA_DIR / "enriched"
    db_path = Path(args.db)

    if args.all:
        process_all(ENRICHED_DIR, db_path, dry_run=args.dry_run)
    else:
        sf = Path(args.enriched)
        if not sf.exists():
            print(f"[ERROR] Not found: {sf}", file=sys.stderr)
            sys.exit(1)
        process_single(sf, db_path, dry_run=args.dry_run)
```

- [ ] **Step 4: Run tests; verify PASS**

Run: `python -m pytest tests/test_storage_loader.py -v`

Expected: All 6 tests pass.

- [ ] **Step 5: Run full suite (except e2e)**

Run: `python -m pytest -q --ignore=tests/e2e`
