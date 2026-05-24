# Task 019: L7 dashboard export

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** L7 reads SQLite and writes pre-baked JSON aggregates for the React dashboard. Output files: manifest.json, companies.json, taxonomy.json, time_series.json, by_industry.json, by_geo.json, cross_dim.json, sankey/<ticker>.json.
- **Tech Stack:** Python 3.10+, sqlite3 (stdlib), pytest.

## Task Objective

Implement `analysis/export.py`: query SQLite for all tickers, produce aggregate JSON files under `frontend/public/data/`. Idempotent. Follow TDD.

This is Task 19 of 27.

---

**Files:**
- Create: `src/hk_ipo/analysis/__init__.py`
- Create: `src/hk_ipo/analysis/export.py`
- Create: `tests/test_analysis_export.py`

- [ ] **Step 1: Create `src/hk_ipo/analysis/__init__.py`**

```python
"""L7 analysis layer: SQLite -> pre-baked JSON for static dashboard."""
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_analysis_export.py`:

```python
"""Unit tests for src/hk_ipo/analysis/export.py."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


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
        conn.execute("""
            INSERT INTO uses (use_id, hk_ticker, parent_category, main_category, percentage, amount_hkd_million)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (uid, "01234", parent, main, pct, amt))
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
        conn.execute("""
            INSERT INTO use_tags (hk_ticker, use_id, dimension, value, tool_version)
            VALUES (?, ?, ?, ?, 1)
        """, (ticker, use_id, dim, val))
    conn.commit()
    conn.close()


def test_export_companies_json(tmp_path: Path):
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


def test_export_sankey_for_ticker(tmp_path: Path):
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
    assert "R&D and Technology" in node_names


def test_export_time_series(tmp_path: Path):
    from hk_ipo.analysis.export import export_time_series

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_time_series(conn)
    conn.close()

    assert isinstance(result, list)
    # 2024 should have Test Corp data
    assert len(result) >= 1


def test_export_by_industry(tmp_path: Path):
    from hk_ipo.analysis.export import export_by_industry

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_by_industry(conn)
    conn.close()

    assert "Software & Services" in result
    assert result["Software & Services"]["companies"] == 1


def test_export_by_geo(tmp_path: Path):
    from hk_ipo.analysis.export import export_by_geo

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_by_geo(conn)
    conn.close()

    assert isinstance(result, dict)


def test_export_cross_dim(tmp_path: Path):
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


def test_export_manifest(tmp_path: Path):
    from hk_ipo.analysis.export import export_manifest

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    result = export_manifest(conn)
    conn.close()

    assert "generated_at" in result
    assert "schema_version" in result
    assert result["company_count"] == 1


def test_export_manifest_generated_at_is_content_derived(tmp_path: Path):
    """PR-016 regression: generated_at must be derived from DB content
    (max companies.updated_at), not from datetime.now(), so two runs
    against an unchanged DB produce byte-identical manifest.json even
    when the runs are separated by time.

    Verify: (a) the value equals the seeded companies.updated_at;
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


def test_full_export_writes_to_disk(tmp_path: Path):
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


def test_export_idempotent(tmp_path: Path):
    from hk_ipo.analysis.export import export_all

    db = tmp_path / "test.db"
    _setup_test_db(db)

    conn = sqlite3.connect(str(db))
    out1 = tmp_path / "out1"; out1.mkdir()
    out2 = tmp_path / "out2"; out2.mkdir()
    export_all(conn, out1)
    export_all(conn, out2)
    conn.close()

    for f in out1.glob("**/*.json"):
        rel = f.relative_to(out1)
        other = out2 / rel
        assert other.exists()
        assert f.read_text(encoding="utf-8") == other.read_text(encoding="utf-8")
```

- [ ] **Step 3: Run tests; verify FAIL**

Run: `python -m pytest tests/test_analysis_export.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `src/hk_ipo/analysis/export.py`**

```python
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

from hk_ipo.taxonomy import PARENT_TREE, PARENT_CATEGORIES, taxonomy_sha


def export_manifest(conn: sqlite3.Connection) -> dict[str, Any]:
    """Build the manifest payload.

    PR-016 fix (A7.4 — byte-identical reruns): `generated_at` is derived
    from the content of the DB (max companies.updated_at) rather than
    wall-clock time. Two L7 runs against an unchanged DB therefore
    produce byte-identical manifest.json output, even when the runs are
    seconds (or days) apart. When the DB is empty, fall back to the
    epoch placeholder so the field remains stable.
    """
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    max_updated = conn.execute(
        "SELECT MAX(updated_at) FROM companies"
    ).fetchone()[0]
    if max_updated:
        generated_at = str(max_updated)
    else:
        generated_at = "1970-01-01T00:00:00Z"
    return {
        "generated_at": generated_at,
        "schema_version": "2.0",
        "company_count": n,
        "taxonomy_sha": taxonomy_sha(),
    }


def export_companies(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("""
        SELECT hk_ticker, company_name_en, listing_date, document_date,
               industry_primary, industry_source, total_net_proceeds,
               currency, needs_human_review
        FROM companies ORDER BY hk_ticker
    """).fetchall()
    companies = [
        {
            "hk_ticker": r[0], "company_name_en": r[1],
            "listing_date": r[2], "document_date": r[3],
            "industry_primary": r[4], "industry_source": r[5],
            "total_net_proceeds": r[6], "currency": r[7],
            "needs_human_review": bool(r[8]),
        }
        for r in rows
    ]
    return {"companies": companies, "count": len(companies)}


def export_taxonomy() -> dict[str, Any]:
    return {"categories": PARENT_TREE, "parent_order": PARENT_CATEGORIES}


def export_sankey(conn: sqlite3.Connection, ticker: str) -> dict[str, Any]:
    rows = conn.execute("""
        SELECT parent_category, main_category, sub_category,
               percentage, amount_hkd_million, description
        FROM uses WHERE hk_ticker = ? ORDER BY use_id
    """, (ticker,)).fetchall()
    if not rows:
        return {"nodes": [], "links": []}

    nodes: list[dict[str, Any]] = [{"name": "Total Net Proceeds"}]
    links: list[dict[str, Any]] = []
    parent_set: dict[str, int] = {}

    total = sum(r[4] or 0 for r in rows)

    for parent, main, sub, pct, amt, desc in rows:
        if parent not in parent_set:
            parent_set[parent] = len(nodes)
            nodes.append({"name": parent})
            links.append({
                "source": "Total Net Proceeds",
                "target": parent,
                "value": round(amt or 0, 1),
            })
        main_key = f"{parent}/{main}"
        main_idx = None
        for idx, n in enumerate(nodes):
            if n["name"] == main_key:
                main_idx = idx
                break
        if main_idx is None:
            main_idx = len(nodes)
            nodes.append({"name": main_key})
        links.append({
            "source": parent, "target": main_key,
            "value": round(amt or 0, 1),
        })
        if sub:
            sub_key = f"{parent}/{main}/{sub}"
            nodes.append({"name": sub_key})
            links.append({
                "source": main_key, "target": sub_key,
                "value": round(amt or 0, 1),
            })

    return {"nodes": nodes, "links": links, "total_net_proceeds": round(total, 1)}


def export_time_series(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("""
        SELECT listing_date, parent_category, SUM(percentage) as pct,
               SUM(amount_hkd_million) as amt
        FROM uses JOIN companies ON uses.hk_ticker = companies.hk_ticker
        WHERE listing_date IS NOT NULL
        GROUP BY listing_date, parent_category
        ORDER BY listing_date
    """).fetchall()
    by_year: dict[str, dict[str, float]] = {}
    for date_str, parent, pct, amt in rows:
        year = (date_str or "")[:4]
        if not year:
            continue
        if year not in by_year:
            by_year[year] = {}
        by_year[year][parent] = by_year[year].get(parent, 0) + round(pct or 0, 2)

    return [
        {"year": y, **parents}
        for y, parents in sorted(by_year.items())
    ]


def export_by_industry(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("""
        SELECT companies.industry_primary, companies.hk_ticker,
               COUNT(DISTINCT companies.hk_ticker) as n_companies,
               SUM(uses.amount_hkd_million) as total_amt,
               uses.parent_category, SUM(uses.percentage) as pct
        FROM uses JOIN companies ON uses.hk_ticker = companies.hk_ticker
        WHERE companies.industry_primary IS NOT NULL
        GROUP BY companies.industry_primary, uses.parent_category
        ORDER BY companies.industry_primary
    """).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for ind, ticker, n_co, total_amt, parent, pct in rows:
        if ind not in result:
            result[ind] = {"companies": n_co, "parents": {}}
        result[ind]["parents"][parent] = round(pct or 0, 2)
    return result


def export_by_geo(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("""
        SELECT use_tags.value, SUM(uses.amount_hkd_million) as total_amt,
               COUNT(DISTINCT use_tags.hk_ticker) as n_companies
        FROM use_tags
        JOIN uses ON use_tags.hk_ticker = uses.hk_ticker
            AND use_tags.use_id = uses.use_id
        WHERE use_tags.dimension = 'geo'
        GROUP BY use_tags.value
    """).fetchall()
    return {
        r[0]: {"total_hkd_million": round(r[1] or 0, 1), "companies": r[2]}
        for r in rows
    }


def export_cross_dim(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("""
        SELECT c.hk_ticker, c.industry_primary,
               c.listing_date, c.total_net_proceeds,
               u.use_id, u.parent_category, u.percentage,
               u.amount_hkd_million
        FROM uses u JOIN companies c ON u.hk_ticker = c.hk_ticker
    """).fetchall()

    # Fetch ALL 8 enrichment dimensions per use for client-side cross-filtering
    tag_rows = conn.execute("""
        SELECT hk_ticker, use_id, dimension, value
        FROM use_tags WHERE dimension IN (
            'geo', 'country', 'specificity', 'timeline',
            'capex_opex', 'esg_tag', 'commitment'
        )
    """).fetchall()

    # Also fetch company-level tags (industry is already on companies row)
    company_tag_rows = conn.execute("""
        SELECT hk_ticker, dimension, value
        FROM company_tags WHERE dimension = 'industry'
    """).fetchall()
    company_industry_override: dict[str, str] = {}
    for ticker, _dim, val in company_tag_rows:
        company_industry_override[ticker] = val

    tags_by_use: dict[tuple[str, str], dict[str, list[str]]] = {}
    for ticker, use_id, dim, val in tag_rows:
        key = (ticker, use_id)
        if key not in tags_by_use:
            tags_by_use[key] = {}
        tags_by_use[key].setdefault(dim, []).append(val)

    # Scalar dimensions (take first value if multiple exist for a use_id)
    SCALAR_DIMS = {"geo", "specificity", "timeline", "capex_opex", "esg_tag", "commitment"}
    # List dimensions
    LIST_DIMS = {"country"}

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

        result.append({
            "hk_ticker": ticker, "industry": industry_val,
            "listing_date": r[2], "total_net_proceeds": r[3],
            "use_id": use_id, "parent_category": r[5],
            "percentage": r[6], "amount_hkd_million": r[7],
            "geo": geo_val,
            "countries": countries_val,
            "specificity": specificity_val,
            "timeline": timeline_val,
            "capex_opex": capex_opex_val,
            "esg_tag": esg_tag_val,
            "commitment": commitment_val,
        })
    return result


def export_all(
    conn: sqlite3.Connection,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sankey_dir = output_dir / "sankey"
    sankey_dir.mkdir(parents=True, exist_ok=True)

    tickers = [
        r[0] for r in conn.execute("SELECT hk_ticker FROM companies").fetchall()
    ]

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
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"[L7] {path.name}")

    for ticker in tickers:
        sankey_data = export_sankey(conn, ticker)
        (sankey_dir / f"{ticker}.json").write_text(
            json.dumps(sankey_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"[L7] sankey/ {len(tickers)} tickers")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L7: export SQLite to dashboard JSON")
    parser.add_argument("--db", default="data/ipo.db")
    parser.add_argument("--out", default="frontend/public/data")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    conn = sqlite3.connect(str(db_path))
    try:
        export_all(conn, out_dir)
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests; verify PASS**

Run: `python -m pytest tests/test_analysis_export.py -v`

Expected: All tests pass.

- [ ] **Step 6: Run full suite (except e2e)**

Run: `python -m pytest -q --ignore=tests/e2e`
