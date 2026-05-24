"""L5 enrichment: ESG / sustainability tags (green / social / governance).

Optional per-use tags. An item may have 0, 1, 2, or all 3 tags.
Rules-based keyword matching.
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

DIMENSION = "esg_tag"
VERSION = 1

# Multi-word keywords use a unified [\s-]+ separator convention:
#   [\s-]+  �?at least one space/hyphen required (default for most terms)
#   [\s-]?  �?optional separator, for terms whose merged form is standard English
#             (e.g. "microfinance", "anticorruption", "antibribery", "wastewater")
_GREEN_KW = re.compile(
    r"\b(green|renewable|solar|wind|clean[\s-]+energy|carbon|carbon[\s-]+neutral"
    r"|net[\s-]+zero|emissions?|climate|sustainable|sustainability|environments?"
    r"|recycl(?:e|ed|es|ing)|waste[\s-]?water|biodiversity|conservation|electric[\s-]+vehicles?"
    r"|evs?|energy[\s-]+efficien(?:t|cy|cies|tly)|pollution|eco[\s-]+friendly|organic"
    r"|low[\s-]+carbon|decarboni(?:zation|sation|zing|sing|zed|sed|zes|ses|ze|se))\b",
    re.IGNORECASE,
)

_SOCIAL_KW = re.compile(
    r"\b(social|affordable[\s-]+housing|healthcare|education|communit(?:y|ies)"
    r"|public[\s-]+health|inclusion|diversity|equity|access[\s-]+to"
    r"|patients?|hospitals?|clinics?|schools?|universit(?:y|ies)|vocational|training"
    r"|micro[\s-]?finance|financial[\s-]+inclusion|underserved|rural"
    r"|poverty|charit(?:y|ies|able)|philanthrop(?:y|ic|ist|ists|ies)|welfare)\b",
    re.IGNORECASE,
)

_GOVERNANCE_KW = re.compile(
    r"\b(governance|compliance|regulatory|transparency|anti[\s-]?corruption"
    r"|anti[\s-]?bribery|ethics|accountability|audits?|risk[\s-]+management"
    r"|internal[\s-]+controls?|shareholder[\s-]+rights?|data[\s-]+privacy|cybersecurity"
    r"|whistleblowers?)\b",
    re.IGNORECASE,
)


def classify_esg(item: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(item.get("description") or ""),
            str(item.get("category_raw") or ""),
            str(item.get("source_text") or ""),
        ]
    )
    tags: list[str] = []
    if _GREEN_KW.search(text):
        tags.append("green")
    if _SOCIAL_KW.search(text):
        tags.append("social")
    if _GOVERNANCE_KW.search(text):
        tags.append("governance")
    return tags


def _enrich_one(
    record: dict[str, Any],
    enriched_dir: Path,
    force: bool = False,
    ticker: str | None = None,
) -> dict[str, Any]:
    """Enrich a single record. Returns the enrichment block."""
    existing = record.get("enrichments", {}).get(DIMENSION)
    if not force and existing and existing.get("version") == VERSION:
        return existing
    by_use_id: dict[str, list[str]] = {}
    any_esg = False
    for u in record.get("uses", []):
        tags = classify_esg(u)
        by_use_id[u.get("use_id", "")] = tags
        if tags:
            any_esg = True
    block = {"version": VERSION, "any_esg": any_esg, "by_use_id": by_use_id}
    merge_enrichment_block(record, DIMENSION, block)
    tick = ticker or record.get("hk_ticker", "unknown")
    save_enriched(record, enriched_dir, tick)
    esg_count = sum(1 for v in by_use_id.values() if v)
    print(f"[esg_tag] {tick}: {esg_count}/{len(by_use_id)} uses have ESG tags")
    return block


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    """Run esg_tag enrichment on one ticker or all."""
    enriched_dir.mkdir(parents=True, exist_ok=True)

    if ticker:
        record = load_enriched_or_categorized(
            enriched_dir if (enriched_dir / f"{ticker}.json").exists() else categorized_dir,
            ticker,
        )
        return _enrich_one(record, enriched_dir, force=force, ticker=ticker)
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
            results[tick] = _enrich_one(record, enriched_dir, force=force, ticker=tick)
        return results
    return None


if __name__ == "__main__":
    from hk_ipo.enrichments.base import run_cli

    run_cli(dimension=DIMENSION, enrich_one=_enrich_one, run_fn=run)
