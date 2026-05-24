"""L7 dashboard export: SQLite -> pre-baked JSON aggregates.

Writes under frontend/public/data/:
  manifest.json, companies.json, taxonomy.json, time_series.json,
  by_industry.json, by_geo.json, cross_dim.json, sankey/<ticker>.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from hk_ipo.logging_setup import get_logger
from hk_ipo.schema import SCHEMA_VERSION

logger = get_logger(__name__)
from hk_ipo.storage.queries import (
    BY_GEO,
    BY_INDUSTRY_COMPANY_COUNT,
    BY_INDUSTRY_PARENT_BREAKDOWN,
    COMPANIES_LIST,
    COMPANIES_MAX_UPDATED_AT,
    COMPANIES_OVERVIEW,
    COMPANIES_ROW_COUNT,
    COMPANY_TAGS_INDUSTRY,
    CROSS_DIM_USE_TAGS,
    CROSS_DIM_USES,
    SANKEY_USES_BY_TICKER,
    TIME_SERIES_BY_YEAR,
)
from hk_ipo.taxonomy import PARENT_CATEGORIES, PARENT_TREE, taxonomy_sha


def export_manifest(conn: sqlite3.Connection) -> dict[str, Any]:
    """Build the manifest payload.

    PR-016 fix (A7.4 — byte-identical reruns): `generated_at` is derived
    from the content of the DB (max companies.updated_at) rather than
    wall-clock time. Two L7 runs against an unchanged DB therefore
    produce byte-identical manifest.json output, even when the runs are
    seconds (or days) apart. When the DB is empty, fall back to the
    epoch placeholder so the field remains stable.
    """
    n = conn.execute(COMPANIES_ROW_COUNT).fetchone()[0]
    max_updated = conn.execute(COMPANIES_MAX_UPDATED_AT).fetchone()[0]
    if max_updated:
        generated_at = str(max_updated)
    else:
        generated_at = "1970-01-01T00:00:00Z"
    return {
        "generated_at": generated_at,
        "schema_version": SCHEMA_VERSION,
        "company_count": n,
        "taxonomy_sha": taxonomy_sha(),
    }


def export_companies(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(COMPANIES_OVERVIEW).fetchall()
    companies = [
        {
            "hk_ticker": r[0],
            "company_name_en": r[1],
            "listing_date": r[2],
            "document_date": r[3],
            "industry_primary": r[4],
            "industry_source": r[5],
            "total_net_proceeds": r[6],
            "currency": r[7],
            "needs_human_review": bool(r[8]),
        }
        for r in rows
    ]
    return {"companies": companies, "count": len(companies)}


def export_taxonomy() -> dict[str, Any]:
    return {"categories": PARENT_TREE, "parent_order": PARENT_CATEGORIES}


def export_sankey(conn: sqlite3.Connection, ticker: str) -> dict[str, Any]:
    rows = conn.execute(SANKEY_USES_BY_TICKER, (ticker,)).fetchall()
    if not rows:
        return {"nodes": [], "links": [], "total_net_proceeds": 0.0}

    nodes: list[dict[str, Any]] = [{"name": "Total Net Proceeds"}]
    links: list[dict[str, Any]] = []
    parent_set: dict[str, int] = {}
    # Track link indices for CR-003 (parent) and CR-009 (main, sub) accumulation
    parent_link_idx: dict[str, int] = {}
    main_link_idx: dict[str, int] = {}
    sub_link_idx: dict[str, int] = {}

    total = sum(r[3] or 0 for r in rows)

    for parent, main, sub, amt in rows:
        if parent not in parent_set:
            parent_set[parent] = len(nodes)
            nodes.append({"name": parent})
            link_idx = len(links)
            parent_link_idx[parent] = link_idx
            links.append(
                {
                    "source": "Total Net Proceeds",
                    "target": parent,
                    "value": round(amt or 0, 1),
                }
            )
        else:
            # CR-003: accumulate additional amounts to the existing parent link
            links[parent_link_idx[parent]]["value"] += round(amt or 0, 1)
        main_key = f"{parent}/{main}"
        main_idx = None
        for idx, n in enumerate(nodes):
            if n["name"] == main_key:
                main_idx = idx
                break
        if main_idx is None:
            main_idx = len(nodes)
            nodes.append({"name": main_key})
            link_idx = len(links)
            main_link_idx[main_key] = link_idx
            links.append(
                {
                    "source": parent,
                    "target": main_key,
                    "value": round(amt or 0, 1),
                }
            )
        else:
            # CR-009: accumulate additional amounts to the existing main link
            links[main_link_idx[main_key]]["value"] += round(amt or 0, 1)
        if sub:
            sub_key = f"{parent}/{main}/{sub}"
            sub_node_idx = None
            for idx, n in enumerate(nodes):
                if n["name"] == sub_key:
                    sub_node_idx = idx
                    break
            if sub_node_idx is None:
                nodes.append({"name": sub_key})
                sub_link_idx[sub_key] = len(links)
                links.append(
                    {
                        "source": main_key,
                        "target": sub_key,
                        "value": round(amt or 0, 1),
                    }
                )
            else:
                # CR-009: accumulate additional amounts to the existing sub link
                links[sub_link_idx[sub_key]]["value"] += round(amt or 0, 1)

    return {"nodes": nodes, "links": links, "total_net_proceeds": round(total, 1)}


def export_time_series(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(TIME_SERIES_BY_YEAR).fetchall()
    by_year: dict[str, dict[str, float]] = {}
    for date_str, parent, pct in rows:
        year = (date_str or "")[:4]
        if not year:
            continue
        if year not in by_year:
            by_year[year] = {}
        by_year[year][parent] = by_year[year].get(parent, 0) + round(pct or 0, 2)

    return [{"year": y, **parents} for y, parents in sorted(by_year.items())]


def export_by_industry(conn: sqlite3.Connection) -> dict[str, Any]:
    # CR-001: Query company count per industry separately from parent breakdown
    count_rows = conn.execute(BY_INDUSTRY_COMPANY_COUNT).fetchall()
    industry_n: dict[str, int] = {r[0]: r[1] for r in count_rows}

    # CR-004b/CR-006: Removed unused columns (hk_ticker, total_amt) and bare
    # column not in GROUP BY
    rows = conn.execute(BY_INDUSTRY_PARENT_BREAKDOWN).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for ind, parent, pct in rows:
        if ind not in result:
            result[ind] = {"companies": industry_n.get(ind, 0), "parents": {}}
        result[ind]["parents"][parent] = round(pct or 0, 2)
    return result


def export_by_geo(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(BY_GEO).fetchall()
    return {r[0]: {"total_hkd_million": round(r[1] or 0, 1), "companies": r[2]} for r in rows}


def export_cross_dim(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(CROSS_DIM_USES).fetchall()

    # Fetch ALL 8 enrichment dimensions per use for client-side cross-filtering
    tag_rows = conn.execute(CROSS_DIM_USE_TAGS).fetchall()

    # Also fetch company-level tags (industry is already on companies row)
    company_tag_rows = conn.execute(COMPANY_TAGS_INDUSTRY).fetchall()
    company_industry_override: dict[str, str] = {}
    for ticker, _dim, val in company_tag_rows:
        company_industry_override[ticker] = val

    tags_by_use: dict[tuple[str, str], dict[str, list[str]]] = {}
    for ticker, use_id, dim, val in tag_rows:
        key = (ticker, use_id)
        if key not in tags_by_use:
            tags_by_use[key] = {}
        tags_by_use[key].setdefault(dim, []).append(val)

    result: list[dict[str, Any]] = []
    for r in rows:
        ticker, use_id = r[0], r[4]
        tags = tags_by_use.get((ticker, use_id), {})

        # Scalar enrichment values
        geo_val = tags.get("geo", [None])[0]
        specificity_val = tags.get("specificity", [None])[0]
        timeline_val = tags.get("timeline", [None])[0]
        capex_opex_val = tags.get("capex_opex", [None])[0]
        esg_tag_val = tags.get("esg_tag", [None])[0]
        commitment_val = tags.get("commitment", [None])[0]

        # Country list (comma-separated for client-side .includes() check)
        country_list = tags.get("country", [])
        countries_val = ",".join(sorted(country_list)) if country_list else None

        # Company-level industry (use tag override if available)
        industry_val = company_industry_override.get(ticker) or r[1]

        result.append(
            {
                "hk_ticker": ticker,
                "industry": industry_val,
                "listing_date": r[2],
                "total_net_proceeds": r[3],
                "use_id": use_id,
                "parent_category": r[5],
                "percentage": r[6],
                "amount_hkd_million": r[7],
                "geo": geo_val,
                "countries": countries_val,
                "specificity": specificity_val,
                "timeline": timeline_val,
                "capex_opex": capex_opex_val,
                "esg_tag": esg_tag_val,
                "commitment": commitment_val,
            }
        )
    return result


def export_all(
    conn: sqlite3.Connection,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sankey_dir = output_dir / "sankey"
    sankey_dir.mkdir(parents=True, exist_ok=True)

    tickers = [r[0] for r in conn.execute(COMPANIES_LIST).fetchall()]

    exports: list[tuple[Path, Any]] = [
        (output_dir / "manifest.json", export_manifest(conn)),
        (output_dir / "companies.json", export_companies(conn)),
        (output_dir / "taxonomy.json", export_taxonomy()),
        (output_dir / "time_series.json", export_time_series(conn)),
        (output_dir / "by_industry.json", export_by_industry(conn)),
        (output_dir / "by_geo.json", export_by_geo(conn)),
        (output_dir / "cross_dim.json", export_cross_dim(conn)),
    ]

    for path, data in exports:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("%s", path.name)

    for ticker in tickers:
        sankey_data = export_sankey(conn, ticker)
        (sankey_dir / f"{ticker}.json").write_text(
            json.dumps(sankey_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    logger.info("sankey/ %s tickers", len(tickers))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L7: export SQLite to dashboard JSON")
    parser.add_argument("--db", default="data/ipo.db")
    parser.add_argument("--out", default="frontend/public/data")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        sys.exit(1)

    out_dir = Path(args.out)
    conn = sqlite3.connect(str(db_path))
    try:
        export_all(conn, out_dir)
    finally:
        conn.close()
