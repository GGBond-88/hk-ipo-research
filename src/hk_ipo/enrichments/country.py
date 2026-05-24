"""L5 enrichment: country mentions (ISO 2-letter codes).

Scans each use item's text fields for country/region mentions and normalizes
them to ISO 3166-1 alpha-2 codes.
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

DIMENSION = "country"
VERSION = 1

# ── Country name → ISO 3166-1 alpha-2 ─────────────────────────────────────

_COUNTRY_MAP: dict[str, str] = {
    "united states": "US",
    "america": "US",
    "usa": "US",
    "china": "CN",
    "mainland china": "CN",
    "prc": "CN",
    "japan": "JP",
    "korea": "KR",
    "south korea": "KR",
    "singapore": "SG",
    "vietnam": "VN",
    "thailand": "TH",
    "indonesia": "ID",
    "malaysia": "MY",
    "philippines": "PH",
    "india": "IN",
    "australia": "AU",
    "new zealand": "NZ",
    "united kingdom": "GB",
    "uk": "GB",
    "england": "GB",
    "germany": "DE",
    "france": "FR",
    "canada": "CA",
    "italy": "IT",
    "spain": "ES",
    "netherlands": "NL",
    "switzerland": "CH",
    "brazil": "BR",
    "mexico": "MX",
    "taiwan": "TW",
    "russia": "RU",
    "uae": "AE",
    "saudi arabia": "SA",
    "south africa": "ZA",
    "turkey": "TR",
    "poland": "PL",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "belgium": "BE",
    "austria": "AT",
    "ireland": "IE",
    "portugal": "PT",
    "egypt": "EG",
    "israel": "IL",
    "pakistan": "PK",
    "bangladesh": "BD",
    "myanmar": "MM",
    "cambodia": "KH",
    "laos": "LA",
    "brunei": "BN",
}

# Pre-compiled regex patterns with word boundaries for each country name.
# Multi-word names longer than single-word names must be checked first
# to avoid shorter matches shadowing longer ones (e.g. "united states"
# before "america").
_COUNTRY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE), code)
    for name, code in sorted(_COUNTRY_MAP.items(), key=lambda x: -len(x[0]))
]


def extract_countries(text: str) -> list[str]:
    """Extract ISO 2-letter country codes from text. No duplicates."""
    found: set[str] = set()
    for pattern, code in _COUNTRY_PATTERNS:
        if pattern.search(text) and code not in found:
            found.add(code)
    return sorted(found)


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    """Run country enrichment on one ticker or all."""
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

    all_countries: set[str] = set()
    by_use_id: dict[str, list[str]] = {}
    for u in record.get("uses", []):
        combined = " ".join(
            [
                str(u.get("description") or ""),
                str(u.get("category_raw") or ""),
                str(u.get("source_text") or ""),
            ]
        )
        codes = extract_countries(combined)
        by_use_id[u.get("use_id", "")] = codes
        all_countries.update(codes)

    tick = ticker or record.get("hk_ticker", "unknown")
    block = {
        "version": VERSION,
        "countries": sorted(all_countries),
        "by_use_id": by_use_id,
    }
    merge_enrichment_block(record, DIMENSION, block)
    save_enriched(record, enriched_dir, tick)
    print(f"[country] {tick}: {len(all_countries)} countries")
    return block


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from hk_ipo.enrichments.base import run_cli

    run_cli(dimension=DIMENSION, enrich_one=_enrich_one, run_fn=run)
