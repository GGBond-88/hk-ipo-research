"""L5 enrichment: purpose specificity (specific / general / vague).

Rules-based classifier: scores each use item on presence of concrete details
(numbers, dates, locations, named entities) in description + source_text.
"""

from __future__ import annotations

import argparse
import json as _json
import re
import sys
from pathlib import Path
from typing import Any



from hk_ipo.enrichments.base import (
    iter_records_for_enrichment,
    load_enriched_or_categorized,
    merge_enrichment_block,
    save_enriched,
)

DIMENSION = "specificity"
VERSION = 1

# Indicators of specificity: numeric ranges, dates, proper nouns, compound details
_SPECIFICITY_MARKERS = re.compile(
    r"(\b\d{4}\b|\bQ[1-4]\b|\bsq[.]?\s*ft\b|\bsquare\s*meters?\b"
    r"|\bfloor\s*\d|\bfloors\b|\bphase\b|\bstage\b"
    r"|\baddress\b|\blocated\sin\b|\bunit\s*\d|\block-up\b"
    r"|\bindependent\s*third\b|\bproprietary\b|\bpatent\b|\bcertification\b"
    r"|\btimeline\b|\bmilestone\b|\btarget\b|\bdeadline\b)",
    re.IGNORECASE,
)
_GENERAL_MARKERS = re.compile(
    r"(\bgeneral\b|\bworking\s*capital\b|\bcorporate\s*purposes?\b"
    r"|\bunspecified\b|\bdiscretionary\b|\bcontingen(?:t|cy|cies?)\b|\breserves?\b)",
    re.IGNORECASE,
)


def classify_specificity(item: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(item.get("description") or ""),
            str(item.get("source_text") or ""),
        ]
    ).strip()
    if not text or len(text) < 10:
        return "vague"
    n_specific = len(_SPECIFICITY_MARKERS.findall(text))
    n_general = len(_GENERAL_MARKERS.findall(text))
    if n_specific >= 2:
        return "specific"
    if n_specific >= 1 and n_general == 0:
        return "specific"
    if n_general >= 1:
        return "general"
    # Heuristic: longer text usually more specific
    if len(text) > 300:
        return "specific"
    if len(text) > 100:
        return "general"
    return "vague"


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    """Run specificity enrichment on one ticker or all."""
    enriched_dir.mkdir(parents=True, exist_ok=True)

    if ticker:
        record = load_enriched_or_categorized(categorized_dir, ticker)
        return _enrich_one(record, enriched_dir, force=force)
    if all_files:
        results: dict[str, Any] = {}
        for tick, record in iter_records_for_enrichment(categorized_dir, enriched_dir):
            results[tick] = _enrich_one(record, enriched_dir, force=force)
        return results
    return None


def _enrich_one(
    record: dict[str, Any],
    enriched_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Enrich a single record. Returns the enrichment block."""
    existing = record.get("enrichments", {}).get(DIMENSION)
    if not force and existing and existing.get("version") == VERSION:
        return existing

    by_use_id: dict[str, str] = {}
    for u in record.get("uses", []):
        by_use_id[u.get("use_id", "")] = classify_specificity(u)

    block = {"version": VERSION, "by_use_id": by_use_id}
    merge_enrichment_block(record, DIMENSION, block)
    tick = record.get("hk_ticker", "unknown")
    save_enriched(record, enriched_dir, tick)
    print(f"[specificity] {tick}: {len(by_use_id)} uses tagged")
    return block


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from hk_ipo.enrichments.base import run_cli

    run_cli(dimension=DIMENSION, enrich_one=_enrich_one, run_fn=run, passes_ticker=False)
