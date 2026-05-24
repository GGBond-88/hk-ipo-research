"""L5 enrichment: CAPEX vs OPEX vs financial classification.

Rules-based keyword classifier for use-of-proceeds items.
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

DIMENSION = "capex_opex"
VERSION = 1

_FINANCIAL_KW = re.compile(
    r"\b(debt(s)?|repay(ment|ing|s)?|loan(s)?|bond(s)?|note(s)?"
    r"|refinanc(ing|e|ed)?|interest(s)?|borrowing(s)?"
    r"|redemption(s)?|matur(e|ing|ed|ity)|leverag(e|ing|ed)?)"
    r"\b",
    re.IGNORECASE,
)
_OPEX_KW = re.compile(
    r"\b(working\s*capital|operating\s*expenses?|opex|payroll(s)?"
    r"|salar(y|ies)|wage(s)?|rent(s|als?|ing|ed)?|leas(e|ing|es|ed)?"
    r"|utilit(y|ies)|marketing\s*campaigns?|advertis(e|ed|ing|ements?)?"
    r"|sales\s*forces?|sales\s*teams?|day[\s-]to[\s-]day|general\s*purposes?"
    r"|recruit(ment|ing|s)?|hiring(s)?|training(s)?"
    r"|maintenance(?!\s*(of|capital|new)))"
    r"\b",
    re.IGNORECASE,
)
_CAPEX_KW = re.compile(
    r"\b(construct(ions?|ing|ed|s)?|build(ings?|s)?"
    r"|acquir(e|ing|ed|e(?:ment|s))|acquisition(s)?"
    r"|purchas(e|ing|ed|es)?|buy(ing|s)?"
    r"|install(?:ing|ed|s|ations?)?|equipment(s)?|machiner(y|ies)"
    r"|plant(s)?|facilit(y|ies)|factor(y|ies)"
    r"|warehous(e(?:s)?|ing|ed)?|propert(y|ies)|real\s*estate"
    r"|land(s)?|data\s*centers?|server(s)?|hardware(s)?"
    r"|infrastructure(s)?|r\s*&\s*d\s*(centers?|facilit(y|ies)|labs?)"
    r"|manufacturing\s*(plants?|lines?|facilit(y|ies))"
    r"|expand(ing|ed|s)?|expansion(s)?"
    r"|upgrad(e|ing|ed|es)?"
    r"|renovat(e|ing|ed|ion|ions)?|fit[\s-]outs?"
    r"|new\s*(stores?|branch(es)?|offices?)|fleet(s)?|vehicle(s)?|vessel(s)?)"
    r"\b",
    re.IGNORECASE,
)


def classify_capex_opex(item: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(item.get("description") or ""),
            str(item.get("category_raw") or ""),
            str(item.get("source_text") or ""),
        ]
    )
    if _FINANCIAL_KW.search(text):
        return "financial"
    if _OPEX_KW.search(text):
        return "opex"
    if _CAPEX_KW.search(text):
        return "capex"
    return "capex"  # default: UoP is typically capex for IPOs


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
        by_use_id[u.get("use_id", "")] = classify_capex_opex(u)
    block = {"version": VERSION, "by_use_id": by_use_id}
    merge_enrichment_block(record, DIMENSION, block)
    tick = ticker or record.get("hk_ticker", "unknown")
    save_enriched(record, enriched_dir, tick)
    print(f"[capex_opex] {tick}: {len(by_use_id)} uses tagged")
    return block


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    """Run capex_opex enrichment on one ticker or all."""
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


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from hk_ipo.enrichments.base import run_cli

    run_cli(dimension=DIMENSION, enrich_one=_enrich_one, run_fn=run)
