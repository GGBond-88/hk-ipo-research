"""Quick post-run audit: sample N files from each pipeline stage and summarize."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sample(paths: list[Path], n: int, seed: int = 42) -> list[Path]:
    if len(paths) <= n:
        return paths
    random.seed(seed)
    return random.sample(paths, n)


def audit_sections(n: int = 20) -> None:
    files = sorted((DATA / "sections").glob("*.json"))
    print(f"\n=== L1 SECTIONS ({len(files)} files) ===")
    if not files:
        return
    lang_counts: dict[str, int] = {}
    method_counts: dict[str, int] = {}
    skipped_count = 0
    empty_text_count = 0
    for f in files:
        try:
            d = _load(f)
        except Exception as e:
            print(f"  PARSE FAIL: {f.name}: {e}")
            continue
        lang_counts[d.get("language", "?")] = lang_counts.get(d.get("language", "?"), 0) + 1
        method_counts[d.get("extraction_method", "?")] = method_counts.get(d.get("extraction_method", "?"), 0) + 1
        if d.get("skipped"):
            skipped_count += 1
        if not (d.get("text") or "").strip():
            empty_text_count += 1
    print(f"  language: {lang_counts}")
    print(f"  method:   {method_counts}")
    print(f"  skipped:  {skipped_count}")
    print(f"  empty text: {empty_text_count}")
    print(f"\n  Sample of {min(n, len(files))} random sections:")
    for f in sample(files, n):
        d = _load(f)
        print(f"    {f.name:<25} lang={d.get('language'):<7} method={d.get('extraction_method'):<8} "
              f"pages={d.get('start_page')}-{d.get('end_page')} text={len(d.get('text') or '')}ch "
              f"tables={len(d.get('tables') or [])}")


def audit_extracted(n: int = 20) -> None:
    files = sorted([f for f in (DATA / "extracted").glob("*.json")
                    if not f.stem.endswith(".validated")])
    print(f"\n=== L2 EXTRACTED ({len(files)} primary files) ===")
    if not files:
        return
    review_count = 0
    no_uses_count = 0
    total_uses = 0
    pct_sums = []
    for f in files:
        try:
            d = _load(f)
        except Exception as e:
            print(f"  PARSE FAIL: {f.name}: {e}")
            continue
        if d.get("needs_human_review"):
            review_count += 1
        uses = d.get("uses") or []
        if not uses:
            no_uses_count += 1
        else:
            total_uses += len(uses)
            s = sum((u.get("percentage") or 0) for u in uses)
            pct_sums.append(s)
    print(f"  needs_human_review: {review_count} / {len(files)}")
    print(f"  zero-uses extractions: {no_uses_count}")
    print(f"  total uses across all: {total_uses}  (avg {total_uses/max(1,len(files)-no_uses_count):.1f}/pdf)")
    if pct_sums:
        in_range = sum(1 for s in pct_sums if 99 <= s <= 101)
        print(f"  pct sum in [99,101]: {in_range} / {len(pct_sums)} ({100*in_range/len(pct_sums):.0f}%)")
    print(f"\n  Sample of {min(n, len(files))} random extractions:")
    for f in sample(files, n):
        d = _load(f)
        uses = d.get("uses") or []
        s = sum((u.get("percentage") or 0) for u in uses)
        print(f"    {f.name:<25} uses={len(uses):<3} pct_sum={s:<6.1f} "
              f"review={d.get('needs_human_review', False)} "
              f"total_proceeds={d.get('total_net_proceeds_hkd_million')}")


def audit_categorized(n: int = 20) -> None:
    files = sorted((DATA / "categorized").glob("*.json"))
    print(f"\n=== L4 CATEGORIZED ({len(files)} files) ===")
    if not files:
        return
    parent_dist: dict[str, int] = {}
    violations_total = 0
    rebalanced_total = 0
    files_with_violations = 0
    files_rebalanced = 0
    for f in files:
        try:
            d = _load(f)
        except Exception as e:
            print(f"  PARSE FAIL: {f.name}: {e}")
            continue
        meta = d.get("categorization_metadata") or {}
        if (meta.get("violations") or 0) > 0:
            files_with_violations += 1
            violations_total += meta.get("violations", 0)
        if (meta.get("rebalanced") or 0) > 0:
            files_rebalanced += 1
            rebalanced_total += meta.get("rebalanced", 0)
        for u in d.get("uses", []) or []:
            p = (u.get("category_parent") or "?")
            parent_dist[p] = parent_dist.get(p, 0) + 1
    print(f"  parent distribution: {parent_dist}")
    print(f"  files with violations: {files_with_violations}  (total violations: {violations_total})")
    print(f"  files rebalanced:      {files_rebalanced}  (total rebalanced: {rebalanced_total})")
    print(f"\n  Sample of {min(n, len(files))} random categorized:")
    for f in sample(files, n):
        d = _load(f)
        meta = d.get("categorization_metadata") or {}
        uses = d.get("uses") or []
        parent_sum = sum((u.get("percentage") or 0) for u in uses)
        print(f"    {f.name:<25} uses={len(uses):<3} parent_sum={parent_sum:<6.1f} "
              f"viol={meta.get('violations',0)} reb={meta.get('rebalanced',0)} "
              f"model={meta.get('model_used','?')}")


def audit_enriched(n: int = 20) -> None:
    files = sorted((DATA / "enriched").glob("*.json"))
    print(f"\n=== L5 ENRICHED ({len(files)} files) ===")
    if not files:
        return
    dim_counts: dict[str, int] = {}
    for f in files:
        d = _load(f)
        enrich = d.get("enrichments") or {}
        for dim in enrich:
            dim_counts[dim] = dim_counts.get(dim, 0) + 1
    print(f"  dimensions present per ticker: {dim_counts}")
    print(f"\n  Per-file dimension coverage:")
    for f in files:
        d = _load(f)
        enrich = d.get("enrichments") or {}
        dims = sorted(enrich.keys())
        print(f"    {f.name:<20} dims={','.join(dims) if dims else '(none)'}")


def audit_db() -> None:
    import sqlite3
    db = DATA / "ipo.db"
    print(f"\n=== L6 SQLITE ({db.name}, {db.stat().st_size//1024} KB) ===")
    conn = sqlite3.connect(str(db))
    try:
        for table in ("companies", "uses", "pipeline_runs"):
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"  {table}: {n} rows")
            except Exception as e:
                print(f"  {table}: <error: {e}>")
        print()
        print("  Recent pipeline_runs (last 30 rows):")
        cur = conn.execute(
            "SELECT stage, status, COUNT(*) FROM pipeline_runs "
            "WHERE run_id = (SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1) "
            "GROUP BY stage, status ORDER BY stage, status"
        )
        for stage, status, c in cur.fetchall():
            print(f"    {stage:<14} {status:<10} {c}")
    finally:
        conn.close()


def audit_dashboard() -> None:
    d = ROOT / "frontend" / "public" / "data"
    print(f"\n=== L7 DASHBOARD JSON ({d}) ===")
    for f in sorted(d.glob("*.json")):
        try:
            content = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(content, list):
                size_desc = f"list[{len(content)}]"
            elif isinstance(content, dict):
                size_desc = f"dict[{len(content)} keys: {list(content.keys())[:5]}]"
            else:
                size_desc = type(content).__name__
            print(f"  {f.name:<22}  {size_desc}")
        except Exception as e:
            print(f"  {f.name:<22}  ERROR: {e}")
    sankey = d / "sankey"
    if sankey.exists():
        print(f"  sankey/  ({len(list(sankey.glob('*.json')))} files)")


if __name__ == "__main__":
    audit_sections(20)
    audit_extracted(20)
    audit_categorized(20)
    audit_enriched(20)
    audit_db()
    audit_dashboard()
