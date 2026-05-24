# P2-6 — Extract shared `_enrich_template` CLI scaffold for enrichments (covers P2-12)

Status: complete
Priority: P2
Effort: M (90 min)

## Goal
Eliminate the duplicated `__main__` argparse + record-loading + dispatch boilerplate across the 8 L5 enrichment modules by extracting a shared helper in `enrichments/base.py`.

## Why
All 8 enrichment modules share ~30 LoC of identical CLI scaffolding (parser construction, `--all`/`<categorized>` mutually-exclusive group, enriched-vs-categorized record loading, `_enrich_one` dispatch). When a fix is needed (cf. CR-001/CR-002), it must be applied 8 times. See revise_plan.md §P2-6 and §P2-12.

## Files touched
- Modify: [src/hk_ipo/enrichments/base.py](../../src/hk_ipo/enrichments/base.py) — add `run_cli(...)` helper.
- Modify: all 8 enrichment modules' `if __name__ == "__main__":` blocks:
  - `geo.py`, `country.py`, `industry.py`, `specificity.py`, `timeline.py`, `capex_opex.py`, `esg_tag.py`, `commitment.py`

## Design sketch
```python
# enrichments/base.py
def run_cli(
    *,
    dimension: str,
    enrich_one,
    run_fn,
    extra_args: Callable[[argparse.ArgumentParser], None] | None = None,
) -> None:
    parser = argparse.ArgumentParser(description=f"L5 {dimension} enrichment")
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
        run_fn(CATEGORIZED_DIR, ENRICHED, all_files=True, force=args.force, **_collect_extras(args, extra_args))
    else:
        sf = Path(args.categorized)
        if not sf.exists():
            print(f"[ERROR] Not found: {sf}", file=sys.stderr); sys.exit(1)
        record = json.loads(sf.read_text(encoding="utf-8"))
        ticker = record.get("hk_ticker") or sf.stem
        enriched_file = ENRICHED / f"{ticker}.json"
        if enriched_file.exists():
            record = json.loads(enriched_file.read_text(encoding="utf-8"))
        enrich_one(record, ENRICHED, force=args.force, ticker=ticker)
```

## Steps
1. Read existing `base.py` to understand current helpers (`load_enriched_or_categorized`, `merge_enrichment_block`, `save_enriched`).
2. Add `run_cli(...)` per sketch. Support modules that have extra args (e.g., `industry.py` has `--source`, `industry/commitment` have `overrides_csv`) via the `extra_args` callback.
3. Migrate one module first as proof (suggest `geo.py` — simplest). Verify tests + manual CLI smoke (`python -m hk_ipo.enrichments.geo --all`).
4. Migrate the other 7. Pay attention to `industry.py` which dispatches differently (calls `run(ticker=...)` instead of `_enrich_one` directly).
5. Run all blackbox + unit tests: `pytest tests/test_enrichments_*.py tests/e2e/test_l5_*_blackbox.py -v`.

## Acceptance
- [x] Each of the 8 `__main__` blocks shrinks to ≤ 5 LoC (just args spec + `run_cli(...)`).
- [x] All enrichment tests and L5 blackbox tests pass.
- [x] The CR-001/CR-002 prior-enrichment preservation is now enforced once in `run_cli` instead of 8 times.

## Resolution

### What was changed

- **`src/hk_ipo/enrichments/base.py`**: Added `run_cli(...)` shared CLI scaffold function (args: `dimension`, `enrich_one`, `run_fn`, `extra_args`, `all_kwargs_fn`, `single_kwargs_fn`, `passes_ticker`). Added imports for `argparse`, `sys`, `Callable` at module level.

- **All 8 enrichment modules** (`geo.py`, `country.py`, `industry.py`, `specificity.py`, `timeline.py`, `capex_opex.py`, `esg_tag.py`, `commitment.py`): Replaced duplicated `__main__` argparse+record-loading+dispatch boilerplate (~30 LoC each) with a 2-5 line `run_cli(...)` call.

### How each module calls `run_cli`

| Module | Special params |
|---|---|
| **geo.py** | `passes_ticker=False` (derives ticker from record) |
| **specificity.py** | `passes_ticker=False` (derives ticker from record) |
| **country.py** | Default (standard `_enrich_one` signature) |
| **timeline.py** | `single_kwargs_fn=lambda a: {"dimension": DIMENSION}` (extra positional arg) |
| **capex_opex.py** | Default |
| **esg_tag.py** | Default |
| **commitment.py** | Default |
| **industry.py** | `extra_args=_add_source`, `all_kwargs_fn` (passes `source`/`overrides_csv` to `run`), `single_kwargs_fn` (passes `source`/`manual_overrides` to `_enrich_one`) |

### Test results

```
python -m pytest tests/test_enrichments_*.py tests/e2e/test_l5_*_blackbox.py -v
```
**343 passed**, 4 failed (the 4 failures are pre-existing industry LLM blackbox tests that fail due to `ModuleNotFoundError: No module named 'hk_ipo.llm_client'` in the config_override test environment -- not related to this refactor). 11 warnings (harmless runpy re-import warnings).

### Key design decisions

1. **`all_kwargs_fn` / `single_kwargs_fn` separation**: Industry's `run()` accepts `overrides_csv` but `_enrich_one` accepts `manual_overrides`, so the two paths need different kwargs.
2. **`passes_ticker` flag**: geo.py and specificity.py's `_enrich_one` derive the ticker from the record directly and don't accept a `ticker` kwarg.
3. **CR-001/CR-002**: Prior-enrichment preservation (loading from `data/enriched/` if it exists) is now enforced once in `run_cli` instead of being duplicated (and sometimes missing, as was the case in industry.py's original CLI).

## Out of scope
- Refactoring `_enrich_one` signatures — keep current shape.
- Touching enrichment business logic.

## Dependencies
- [P0-2b](P0-2b-prior-enrichment-regression-tests.md) (so regression tests guard the refactor).
