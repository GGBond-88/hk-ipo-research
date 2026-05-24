"""L5 enrichment: deployment timeline (0-12m / 12-24m / 24-36m / 36m+ / unspecified).

Rules-based: scans text for month/year horizons and phrases like "near-term,"
"medium-term," "long-term."
"""

from __future__ import annotations

import argparse
import json as _json
import re
import sys
from pathlib import Path
from typing import Any



from hk_ipo.enrichments.base import (
    load_enriched_or_categorized,
    merge_enrichment_block,
    save_enriched,
)

DIMENSION = "timeline"
VERSION = 1

# Numeric patterns: specific month/year mentions (checked first, longest to shortest)
_SHORT_NUMERIC_RE = re.compile(
    r"\b(12[\s-]*months?\b|within[\s-]*(a|1)[\s-]*year\b|first[\s-]*year\b"
    r"|6[\s-]*months?\b|12[\s-]*mo\b)",
    re.IGNORECASE,
)
_MEDIUM_NUMERIC_RE = re.compile(
    r"\b(1[3-9][\s-]*months?\b|2[0-4][\s-]*months?\b"
    r"|two[\s-]*years?\b|2[\s-]*years?\b)",
    re.IGNORECASE,
)
_LONG_NUMERIC_RE = re.compile(
    r"\b(three[\s-]*years?\b|3[\s-]*years?\b|36[\s-]*months?\b"
    r"|2[5-9][\s-]*months?\b|3[0-6][\s-]*months?\b)",
    re.IGNORECASE,
)
_VERY_LONG_NUMERIC_RE = re.compile(
    r"\b(four[\s-]*years?\b|4[\s-]*years?\b|five[\s-]*years?\b|5[\s-]*years?\b"
    r"|[6-9][\s-]*years?\b|\d{2}[\s-]*years?\b|3[7-9]\+?[\s-]*months?\b"
    r"|[4-9]\d\+?[\s-]*months?\b)",
    re.IGNORECASE,
)

# Qualitative patterns: checked only if no numeric match is found
_SHORT_QUAL_RE = re.compile(
    r"\b(near[\s-]term|short[\s-]term|immediate)",
    re.IGNORECASE,
)
_MEDIUM_QUAL_RE = re.compile(
    r"\b(medium[\s-]term|mid[\s-]term)",
    re.IGNORECASE,
)
_LONG_QUAL_RE = re.compile(
    r"\b(long[\s-]term)",
    re.IGNORECASE,
)
_VERY_LONG_QUAL_RE = re.compile(
    r"\b(very[\s-]*long|extended[\s-]*(period|horizon|timeline))",
    re.IGNORECASE,
)


def classify_timeline(item: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(item.get("description") or ""),
            str(item.get("source_text") or ""),
        ]
    )
    # Phase 1: explicit numeric mentions �?longest horizon wins
    if _VERY_LONG_NUMERIC_RE.search(text):
        return "36m+"
    if _LONG_NUMERIC_RE.search(text):
        return "24-36m"
    if _MEDIUM_NUMERIC_RE.search(text):
        return "12-24m"
    if _SHORT_NUMERIC_RE.search(text):
        return "0-12m"
    # Phase 2: qualitative phrases �?only if no numeric match
    if _VERY_LONG_QUAL_RE.search(text):
        return "36m+"
    if _LONG_QUAL_RE.search(text):
        return "24-36m"
    if _MEDIUM_QUAL_RE.search(text):
        return "12-24m"
    if _SHORT_QUAL_RE.search(text):
        return "0-12m"
    return "unspecified"


def _enrich_one(
    record: dict[str, Any],
    enriched_dir: Path,
    dimension: str,
    *,
    force: bool = False,
    ticker: str | None = None,
) -> dict[str, Any]:
    """Enrich a single record. Returns the enrichment block."""
    existing = record.get("enrichments", {}).get(dimension)
    if not force and existing and existing.get("version") == VERSION:
        return existing
    by_use_id: dict[str, str] = {}
    for u in record.get("uses", []):
        by_use_id[u.get("use_id", "")] = classify_timeline(u)
    block = {"version": VERSION, "by_use_id": by_use_id}
    merge_enrichment_block(record, dimension, block)
    tick = ticker or record.get("hk_ticker", "unknown")
    save_enriched(record, enriched_dir, tick)
    print(f"[timeline] {tick}: {len(by_use_id)} uses tagged")
    return block


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    enriched_dir.mkdir(parents=True, exist_ok=True)

    if ticker:
        record = load_enriched_or_categorized(
            enriched_dir if (enriched_dir / f"{ticker}.json").exists() else categorized_dir,
            ticker,
        )
        return _enrich_one(record, enriched_dir, DIMENSION, force=force, ticker=ticker)
    if all_files:
        jsons = sorted(
            (
                enriched_dir
                if enriched_dir.exists() and any(enriched_dir.glob("*.json"))
                else categorized_dir
            ).glob("*.json"),
        )
        results: dict[str, Any] = {}
        for jf in jsons:
            record = _json.loads(jf.read_text(encoding="utf-8"))
            tick = record.get("hk_ticker") or jf.stem
            results[tick] = _enrich_one(record, enriched_dir, DIMENSION, force=force, ticker=tick)
        return results
    return None


if __name__ == "__main__":
    from hk_ipo.enrichments.base import run_cli

    run_cli(
        dimension=DIMENSION,
        enrich_one=_enrich_one,
        run_fn=run,
        single_kwargs_fn=lambda a: {"dimension": DIMENSION},
    )
