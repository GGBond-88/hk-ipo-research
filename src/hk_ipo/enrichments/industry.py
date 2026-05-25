"""L5 enrichment: company industry classification (GICS).

Default source: LLM reads the prospectus text to determine the primary
industry. With --source manual, reads `data/industry_overrides.csv`.
The result is a company-level (not per-use) enrichment tag.
"""

from __future__ import annotations

import argparse
import csv
import json as _json
import sys
from pathlib import Path
from typing import Any

import openai



from hk_ipo.enrichments.base import (
    iter_records_for_enrichment,
    load_enriched_or_categorized,
    merge_enrichment_block,
    save_enriched,
)

DIMENSION = "industry"
VERSION = 1


def load_manual_overrides(csv_path: Path) -> dict[str, str]:
    """Load ticker -> industry from a CSV file. Returns empty dict if missing."""
    if not csv_path.exists():
        return {}
    result: dict[str, str] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("ticker") or "").strip()
            ind = (row.get("industry") or "").strip()
            if t and ind:
                result[t] = ind
    return result


def _classify_via_llm(record: dict[str, Any]) -> str:
    """Use LLM to determine the company's GICS industry from the section text."""
    from hk_ipo import config as cfg
    from hk_ipo.llm_client import LLMClient

    ticker = record.get("hk_ticker", "unknown")
    name = record.get("company_name_en", "")
    uses_text = " ".join(
        f"{u.get('description', '')} {u.get('category_raw', '')} {u.get('source_text', '')}"
        for u in record.get("uses", [])
    )[:6000]
    prompt = (
        f"Company: {name} (HK ticker: {ticker})\n\n"
        f"Prospectus excerpt:\n{uses_text}\n\n"
        "Based on the company's described business and use of proceeds, "
        "classify the company into a single GICS Industry name (e.g. "
        "'Software & Services', 'Pharmaceuticals', 'Real Estate', "
        "'Banks', 'Capital Goods', 'Consumer Services', 'Retailing', "
        "'Food Beverage & Tobacco', 'Semiconductors', 'Health Care Equipment'). "
        "Return ONLY the industry name, no extra text."
    )
    response = LLMClient.get().chat(
        stage="L5/industry",
        model=cfg.L2_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=128,
    )
    return (response.choices[0].message.content or "Unknown").strip()


def _enrich_one(
    record: dict[str, Any],
    enriched_dir: Path,
    force: bool = False,
    manual_overrides: dict[str, str] | None = None,
    source: str = "prospectus",
    ticker: str | None = None,
) -> dict[str, Any]:
    existing = record.get("enrichments", {}).get(DIMENSION)
    if not force and existing and existing.get("version") == VERSION:
        return existing

    resolved_ticker = ticker or record.get("hk_ticker", "unknown")
    overrides = manual_overrides or {}

    if source == "manual" and resolved_ticker in overrides:
        primary = overrides[resolved_ticker]
    elif source == "prospectus":
        if resolved_ticker in overrides:
            primary = overrides[resolved_ticker]
            source = "manual"
        else:
            try:
                primary = _classify_via_llm(record)
            except (openai.APIError, ValueError) as exc:
                print(f"[industry] LLM call failed for {resolved_ticker}: {exc}")
                primary = "Unknown"
    else:
        primary = "Unknown"

    block = {
        "version": VERSION,
        "primary": primary,
        "source": source,
    }
    merge_enrichment_block(record, DIMENSION, block)
    save_enriched(record, enriched_dir, resolved_ticker)
    print(f"[industry] {resolved_ticker}: {primary} (source={source})")
    return block


def run(
    categorized_dir: Path,
    enriched_dir: Path,
    ticker: str | None = None,
    all_files: bool = False,
    force: bool = False,
    source: str = "prospectus",
    overrides_csv: Path | None = None,
) -> dict[str, Any] | None:
    manual = {}
    if overrides_csv:
        manual = load_manual_overrides(overrides_csv)

    if ticker:
        record = load_enriched_or_categorized(categorized_dir, ticker)
        return _enrich_one(
            record, enriched_dir, force=force, manual_overrides=manual, source=source, ticker=ticker
        )
    if all_files:
        results: dict[str, Any] = {}
        for t, record in iter_records_for_enrichment(categorized_dir, enriched_dir):
            results[t] = _enrich_one(
                record, enriched_dir, force=force, manual_overrides=manual, source=source, ticker=t
            )
        return results
    return None


if __name__ == "__main__":
    from hk_ipo.config import DATA_DIR
    from hk_ipo.enrichments.base import run_cli

    OVERRIDES_CSV = DATA_DIR / "industry_overrides.csv"

    def _add_source(p):
        p.add_argument(
            "--source",
            choices=["prospectus", "manual"],
            default="prospectus",
            help="Industry classification source",
        )

    run_cli(
        dimension=DIMENSION,
        enrich_one=_enrich_one,
        run_fn=run,
        extra_args=_add_source,
        all_kwargs_fn=lambda a: {"source": a.source, "overrides_csv": OVERRIDES_CSV},
        single_kwargs_fn=lambda a: {
            "source": a.source,
            "manual_overrides": load_manual_overrides(OVERRIDES_CSV),
        },
    )
