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

from hk_ipo.config import ENRICHED_DIR
from hk_ipo.logging_setup import get_logger
from hk_ipo.storage.schema_sql import create_tables

logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def upsert(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    """Upsert one enriched record in a single transaction."""
    ticker = record["hk_ticker"]
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("BEGIN TRANSACTION")
    try:
        # Delete existing rows for this ticker
        conn.execute("DELETE FROM uses WHERE hk_ticker = ?", (ticker,))
        conn.execute("DELETE FROM company_tags WHERE hk_ticker = ?", (ticker,))
        # use_tags cascade-deletes with uses

        # Upsert companies
        conn.execute(
            """
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
        """,
            (
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
            ),
        )

        # Insert uses
        for u in record.get("uses", []):
            # Coerce NULL on NOT NULL columns. Affects rare L2/L4 outputs:
            #   - percentage: None when only an amount is stated.
            #   - main_category: None when L4 LLM omits a category for a
            #     use whose categorization confidence is below threshold.
            # The .get(key, default) form returns the default only when
            # the key is absent; if the key exists with value None we
            # still get None, hence explicit `or` fallbacks below.
            pct = u.get("percentage")
            if pct is None:
                pct = 0.0
            parent_cat = u.get("parent_category") or ""
            main_cat = u.get("main_category") or ""
            conn.execute(
                """
                INSERT INTO uses (
                    use_id, hk_ticker, parent_category, main_category,
                    sub_category, category_raw, percentage,
                    amount_hkd_million, description, source_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    u.get("use_id", ""),
                    ticker,
                    parent_cat,
                    main_cat,
                    u.get("sub_category"),
                    u.get("category_raw"),
                    pct,
                    u.get("amount_hkd_million"),
                    u.get("description"),
                    u.get("source_text"),
                ),
            )

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
                    conn.execute(
                        """
                        INSERT INTO company_tags (
                            hk_ticker, dimension, value, confidence, tool_version
                        )
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (ticker, dim, primary, None, version),
                    )
                continue

            for uid, values in by_use_id.items():
                vals = values if isinstance(values, list) else [values]
                for val in (v for v in vals if v):
                    conn.execute(
                        """
                        INSERT INTO use_tags (
                            hk_ticker, use_id, dimension, value, confidence, tool_version
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (ticker, uid, dim, val, None, version),
                    )

        conn.execute("COMMIT")
    # Broad except: must rollback on ANY exception to prevent DB corruption
    # in the per-ticker transactional upsert, then re-raise.
    except Exception:
        conn.execute("ROLLBACK")
        raise


def dry_run_preview(record: dict[str, Any]) -> str:
    """Return a human-readable preview of what would be upserted."""
    ticker = record["hk_ticker"]
    n_uses = len(record.get("uses", []))
    n_tags = 0
    enrichments = record.get("enrichments", {})
    for dim, block in enrichments.items():
        if not isinstance(block, dict) or dim == "industry":
            continue
        for values in block.get("by_use_id", {}).values():
            vals = values if isinstance(values, list) else [values]
            n_tags += sum(1 for v in vals if v)
    return f"[DRY-RUN] Would upsert ticker={ticker}: company=1, uses={n_uses}, tags={n_tags}"


def process_single(
    enriched_file: Path,
    db_path: Path,
    dry_run: bool = False,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    record = json.loads(enriched_file.read_text(encoding="utf-8"))

    # Validate required fields
    if not isinstance(record, dict):
        raise ValueError(f"Expected JSON object, got {type(record).__name__}: {enriched_file}")
    if "hk_ticker" not in record or not record["hk_ticker"]:
        raise ValueError(f"Missing or empty 'hk_ticker' field in: {enriched_file}")
    if "uses" not in record or not isinstance(record.get("uses"), list):
        raise ValueError(f"Missing or invalid 'uses' field (must be a list) in: {enriched_file}")

    conn = sqlite3.connect(str(db_path))
    try:
        if dry_run:
            print(dry_run_preview(record))  # intentional stdout
        else:
            create_tables(conn)
            upsert(conn, record)
            logger.info("%s: %s uses loaded", record.get("hk_ticker"), len(record.get("uses", [])))
    finally:
        conn.close()


def process_all(
    enriched_dir: Path,
    db_path: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    jsons = sorted(enriched_dir.glob("*.json"))
    if not jsons:
        logger.warning("No enriched JSON files in %s", enriched_dir)
        return {"loaded": 0, "total": 0}

    loaded = 0
    for jf in jsons:
        try:
            process_single(jf, db_path, dry_run=dry_run)
            if not dry_run:
                loaded += 1
        except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
            logger.error("%s: %s", jf.name, exc)

    if dry_run:
        logger.info("L6 dry-run complete: %s file(s) previewed", len(jsons))
    else:
        logger.info("L6 complete: %s loaded (of %s total)", loaded, len(jsons))
    return {"loaded": loaded, "total": len(jsons)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L6: load enriched JSON into SQLite")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("enriched", nargs="?", help="Path to enriched JSON file")
    parser.add_argument("--db", default="data/ipo.db")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--enriched-dir",
        default=str(ENRICHED_DIR),
        help="Directory of enriched JSON files (with --all)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    enriched_dir = Path(args.enriched_dir)

    if args.all:
        process_all(enriched_dir, db_path, dry_run=args.dry_run)
    else:
        sf = Path(args.enriched)
        if not sf.exists():
            logger.error("Not found: %s", sf)
            sys.exit(1)
        process_single(sf, db_path, dry_run=args.dry_run)
