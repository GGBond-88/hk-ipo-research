"""L5 enrichment: geographic scope tag (domestic_hk / mainland / overseas).

Maps each use item to one of three geographic scopes by scanning the item's
text fields for keywords. No LLM call — this is a rules-based tagger.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any



from hk_ipo.enrichments.base import (
    load_enriched_or_categorized,
    merge_enrichment_block,
    save_enriched,
)

DIMENSION = "geo"
VERSION = 1

# ── Keyword sets ───────────────────────────────────────────────────────────

_MAINLAND_KW = re.compile(
    r"\b(mainland\s*china|china|prc|shenzhen|guangdong|beijing|shanghai"
    r"|guangzhou|chengdu|hangzhou|wuhan|nanjing|tianjin|chongqing"
    r"|中国|中华|内地)\b",
    re.IGNORECASE,
)

_OVERSEAS_KW = re.compile(
    r"\b(overseas|international|global|abroad|foreign"
    r"|united states|america|europe|european|southeast asia|asean"
    r"|japan|korea|india|australia|singapore|vietnam|thailand"
    r"|indonesia|malaysia|philippines|uk|germany|france|canada"
    r"|海外|国际|欧洲|东南亚"
    r"|美国|日本|韩国)\b",
    re.IGNORECASE,
)

_DOMESTIC_KW = re.compile(
    r"\b(hong\s*kong|hk|hongkong|香港)\b",
    re.IGNORECASE,
)


def classify_geo(
    item: dict[str, Any],
    company_name: str = "",
) -> str:
    """Classify a use item as domestic_hk, mainland, or overseas."""
    text = " ".join(
        [
            str(item.get("description") or ""),
            str(item.get("category_raw") or ""),
            str(item.get("source_text") or ""),
        ]
    )

    overseas = bool(_OVERSEAS_KW.search(text))
    mainland = bool(_MAINLAND_KW.search(text))
    domestic = bool(_DOMESTIC_KW.search(text))

    if overseas and not mainland:
        return "overseas"
    if mainland and not overseas:
        return "mainland"
    if domestic and not overseas and not mainland:
        return "domestic_hk"
    if overseas and mainland:
        return "overseas"  # both → overseas (broader scope)
    # No strong signal — default to domestic_hk for HK-listed companies
    return "domestic_hk"


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    """Run geo enrichment on one ticker or all."""
    enriched_dir.mkdir(parents=True, exist_ok=True)

    if ticker:
        record = load_enriched_or_categorized(categorized_dir, ticker)
        return _enrich_one(record, enriched_dir, force=force)
    if all_files:
        # PR-015 fix: callers pass categorized_dir as the BARE directory
        # containing <ticker>.json files (not a parent with categorized/
        # subdir). Prefer enriched_dir when it has files, else fall back
        # to categorized_dir. This matches the pattern used by the other
        # seven enrichment tools (country, specificity, etc.).
        jsons = sorted(
            (
                enriched_dir
                if enriched_dir.exists() and any(enriched_dir.glob("*.json"))
                else categorized_dir
            ).glob("*.json")
        )
        results = {}
        for jf in jsons:
            record = json.loads(jf.read_text(encoding="utf-8"))
            tick = record.get("hk_ticker") or jf.stem
            results[tick] = _enrich_one(record, enriched_dir, force=force)
        return results
    return None


def _enrich_one(
    record: dict[str, Any],
    enriched_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    existing = record.get("enrichments", {}).get(DIMENSION)
    if not force and existing and existing.get("version") == VERSION:
        return existing

    ticker = record.get("hk_ticker") or "unknown"
    company = record.get("company_name_en", "")
    by_use_id: dict[str, str] = {}
    for u in record.get("uses", []):
        by_use_id[u.get("use_id", "")] = classify_geo(u, company)

    block = {"version": VERSION, "by_use_id": by_use_id}
    merge_enrichment_block(record, DIMENSION, block)
    save_enriched(record, enriched_dir, ticker)
    print(f"[geo] {ticker}: {len(by_use_id)} uses tagged")
    return block


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from hk_ipo.enrichments.base import run_cli

    run_cli(dimension=DIMENSION, enrich_one=_enrich_one, run_fn=run, passes_ticker=False)
