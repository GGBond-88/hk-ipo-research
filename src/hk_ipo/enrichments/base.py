"""Shared enrichment runner contract and file I/O helpers.

Each L5 enrichment tool:
  - Reads data/categorized/<ticker>.json (or data/enriched/<ticker>.json if
    a previous enrichment already wrote it).
  - Adds or updates ONLY its own `enrichments.<dim>` block.
  - Writes the result to data/enriched/<ticker>.json.
  - Is idempotent: re-running with the same inputs produces the same outputs.
"""

from __future__ import annotations

import argparse as _argparse
import json as _json
import sys as _sys
from pathlib import Path as _Path
from typing import Any, Callable, Protocol




class EnrichmentRunner(Protocol):
    """Protocol for individual enrichment tool modules."""

    DIMENSION: str
    VERSION: int

    def run(self, record: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single record. Returns the enrichment block to merge."""
        ...


def load_enriched_or_categorized(
    data_dir: _Path,
    ticker: str,
) -> dict[str, Any]:
    """Load the most recent record for `ticker`.

    Lookup order:
      1) <data_dir>/enriched/<ticker>.json
      2) <data_dir>/categorized/<ticker>.json
      3) <data_dir>/<ticker>.json   (bare directory — e.g. when caller
         passes the enriched_dir or categorized_dir directly).
    """
    candidates = [
        data_dir / "enriched" / f"{ticker}.json",
        data_dir / "categorized" / f"{ticker}.json",
        data_dir / f"{ticker}.json",
    ]
    for path in candidates:
        if path.exists():
            return _json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"No record for ticker {ticker} in {data_dir}")


def merge_enrichment_block(
    record: dict[str, Any],
    dimension: str,
    block: dict[str, Any],
) -> None:
    """Set or overwrite record['enrichments'][dimension] with `block`."""
    if "enrichments" not in record:
        record["enrichments"] = {}
    record["enrichments"][dimension] = block


def save_enriched(
    record: dict[str, Any],
    enriched_dir: _Path,
    ticker: str,
) -> None:
    """Write the enriched record to data/enriched/<ticker>.json."""
    enriched_dir.mkdir(parents=True, exist_ok=True)
    out_path = enriched_dir / f"{ticker}.json"
    out_path.write_text(_json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def iter_records_for_enrichment(
    categorized_dir: _Path,
    enriched_dir: _Path,
):
    """Iterate (ticker, record) pairs for batch enrichment.

    Always iterates **categorized_dir** as the source of truth for which
    tickers exist (all L4 outputs). For each ticker, yields the
    ``enriched/<ticker>.json`` record if it already exists — so prior
    enrichment blocks (from earlier L5 sub-stages) are preserved —
    otherwise yields the categorized record.

    Replaces the pre-fix pattern where each enrichment chose between
    enriched_dir OR categorized_dir based on whether enriched_dir had
    any files. That pattern caused new tickers to be silently skipped
    whenever even one stale enriched file existed.
    """
    for cat_file in sorted(categorized_dir.glob("*.json")):
        ticker = cat_file.stem
        enriched_file = enriched_dir / f"{ticker}.json"
        src = enriched_file if enriched_file.exists() else cat_file
        record = _json.loads(src.read_text(encoding="utf-8"))
        yield record.get("hk_ticker") or ticker, record


def run_cli(
    *,
    dimension: str,
    enrich_one: Callable[..., Any],
    run_fn: Callable[..., Any],
    extra_args: Callable[[_argparse.ArgumentParser], None] | None = None,
    all_kwargs_fn: Callable[..., dict[str, Any]] | None = None,
    single_kwargs_fn: Callable[..., dict[str, Any]] | None = None,
    passes_ticker: bool = True,
) -> None:
    """Shared CLI scaffold for L5 enrichment modules.

    Eliminates the duplicated argparse + record-loading + dispatch boilerplate
    that previously existed in all 8 enrichment modules' ``__main__`` blocks.

    Parameters
    ----------
    dimension:
        Enrichment dimension name (e.g. "geo", "country").
    enrich_one:
        Single-record enrichment function. Called as::
            enrich_one(record, enriched_dir, *, force, ticker=..., **single_kwargs)
    run_fn:
        Batch enrichment function. Called as::
            run_fn(categorized_dir, enriched_dir, *,
                   all_files=True, force=..., **all_kwargs)
    extra_args:
        Optional callback to add extra argparse arguments (e.g. ``--source``).
    all_kwargs_fn:
        Optional callback ``(args: Namespace) -> dict`` returning extra keyword
        arguments for ``run_fn`` in ``--all`` mode.
    single_kwargs_fn:
        Optional callback ``(args: Namespace) -> dict`` returning extra keyword
        arguments for ``enrich_one`` in single-file mode.
    passes_ticker:
        Whether ``enrich_one`` accepts a ``ticker`` keyword argument.
        Set to ``False`` for modules whose ``_enrich_one`` derives the ticker
        from the record directly (geo, specificity).
    """
    parser = _argparse.ArgumentParser(description=f"L5 {dimension} enrichment")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("categorized", nargs="?")
    parser.add_argument("--force", action="store_true")
    if extra_args:
        extra_args(parser)
    args = parser.parse_args()

    from hk_ipo.config import CATEGORIZED_DIR, DATA_DIR

    ENRICHED = DATA_DIR / "enriched"

    if args.all:
        all_extras = all_kwargs_fn(args) if all_kwargs_fn else {}
        run_fn(CATEGORIZED_DIR, ENRICHED, all_files=True, force=args.force, **all_extras)
    else:
        sf = _Path(args.categorized)
        if not sf.exists():
            print(f"[ERROR] Not found: {sf}", file=_sys.stderr)
            _sys.exit(1)
        record = _json.loads(sf.read_text(encoding="utf-8"))
        ticker = record.get("hk_ticker") or sf.stem
        # CR-001/CR-002: preserve prior enrichment blocks
        enriched_file = ENRICHED / f"{ticker}.json"
        if enriched_file.exists():
            record = _json.loads(enriched_file.read_text(encoding="utf-8"))
        single_extras = single_kwargs_fn(args) if single_kwargs_fn else {}
        if passes_ticker:
            enrich_one(record, ENRICHED, force=args.force, ticker=ticker, **single_extras)
        else:
            enrich_one(record, ENRICHED, force=args.force, **single_extras)
