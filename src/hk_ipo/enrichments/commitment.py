"""L5 enrichment: commitment strength (committed vs discretionary).

Rules-based: checks source text for binding vs tentative language patterns.
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

DIMENSION = "commitment"
VERSION = 1

_COMMITTED_KW = re.compile(
    r"\b(committed|obligated|mandatory|binding|agreed|contracted"
    r"|signed|executed|irrevocable|guaranteed|covenant|undertak\w*"
    r"|required\s+to|will\s+(invest|spend|allocate|use|deploy|repay)"
    r"|has\s+(committed|agreed|entered|signed)|shall\s+(invest|use))"
    r"\b",
    re.IGNORECASE,
)
_DISCRETIONARY_KW = re.compile(
    r"\b(may|might|could|subject\s+to|conditional|contingen\w*"
    r"|discretionary|optional|if\s+(conditions?|market|approved|permitted)"
    r"|pending|at\s+(our|the)\s*(discretion|option)|proposed|intended"
    r"|expected|anticipated|planned|potential|possible)\b",
    re.IGNORECASE,
)


def classify_commitment(item: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(item.get("description", "")),
            str(item.get("source_text", "")),
        ]
    )
    n_committed = len(_COMMITTED_KW.findall(text))
    n_discretionary = len(_DISCRETIONARY_KW.findall(text))
    if n_discretionary > n_committed:
        return "discretionary"
    return "committed"


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
    by_use_id: dict[str, str] = {}
    for u in record.get("uses", []):
        by_use_id[u["use_id"]] = classify_commitment(u)
    block = {"version": VERSION, "by_use_id": by_use_id}
    merge_enrichment_block(record, DIMENSION, block)
    tick = ticker or record.get("hk_ticker", "unknown")
    save_enriched(record, enriched_dir, tick)
    n_comm = sum(1 for v in by_use_id.values() if v == "committed")
    print(f"[commitment] {tick}: {n_comm}/{len(by_use_id)} uses committed")
    return block


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    """Run commitment enrichment on one ticker or all."""
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
