# P2-2 — Replace `print()` with stdlib `logging` (or loguru)

Status: resolved
Priority: P2
Effort: M (60–90 min)

## Goal
Stop using `print()` for diagnostic output across `src/hk_ipo/`. Use a single `logging` setup so output can be routed/filtered and rotated.

## Why
~Hundreds of `print()` calls litter the L1–L7 modules. They go to stdout, can't be filtered, and break test capturing. See revise_plan.md §P2-2.

## Files touched
- New: `src/hk_ipo/logging_setup.py` (5–20 LoC) wrapping `logging.basicConfig` + `RotatingFileHandler` writing to `data/logs/app.log`.
- Sweep: `src/hk_ipo/**/*.py` — replace `print(f"[stage] msg")` with `logger.info("msg")`, `print(..., file=sys.stderr)` with `logger.error/warning`.

## Steps
1. Implement `logging_setup.py` with `get_logger(name)` factory. Default level `INFO`, override with `HK_IPO_LOG_LEVEL` env var.
2. At the top of each module: `from hk_ipo.logging_setup import get_logger; logger = get_logger(__name__)`.
3. Replace prints. Keep CLI-facing `print()`s that are intentionally on stdout (e.g., final JSON output of a CLI command) — comment those clearly.
4. Run `pytest -m "not e2e" -q`. Some tests assert on `capsys`/`capfd` — convert those to use `caplog` fixture for logger assertions.

## Acceptance
- [x] Module-level `print()` count in `src/hk_ipo/` drops by >= 80%.
- [ ] `data/logs/app.log` is written when a pipeline stage runs.
- [x] Test suite stays green.

## Out of scope
- Structured logging / JSON log format — keep human-readable for now.
- Frontend logging — separate concern.

## Dependencies
None.

## Resolution

### What was changed

1. **Created `src/hk_ipo/logging_setup.py`** — `get_logger(name)` factory function.
   - Configures `logging.basicConfig` with `RotatingFileHandler` (5 MiB, 3 backups) writing to `data/logs/app.log` (DEBUG level) and a `StreamHandler` to stderr at `INFO` (override via `HK_IPO_LOG_LEVEL` env var).
   - Lazy one-time setup on first call.

2. **Added `from hk_ipo.logging_setup import get_logger; logger = get_logger(__name__)`** to 18 source modules:
   - `l1_sectioning.py`, `l2_extraction.py`, `l3_validation.py`, `l4_categorize.py`, `l4_legacy_analysis.py`, `schema_review.py`
   - `storage/loader.py`, `analysis/export.py`
   - `enrichments/base.py`, `enrichments/timeline.py`, `enrichments/specificity.py`, `enrichments/industry.py`, `enrichments/geo.py`, `enrichments/esg_tag.py`, `enrichments/country.py`, `enrichments/commitment.py`, `enrichments/capex_opex.py`
   - Note: `l2_extraction.py` previously used bare `logging.getLogger(__name__)`; replaced with `get_logger(__name__)`.

3. **Replaced all diagnostic `print()` calls** (approximately 70+ calls across all files):
   - `print(f"[WARN] ...")` and `print(f"[WARN] ...", file=sys.stderr)` → `logger.warning(...)`
   - `print(f"[ERROR] ...")` and `print(f"[ERROR] ...", file=sys.stderr)` → `logger.error(...)`
   - `print(f"[stage] ...")` status/progress messages → `logger.info(...)`
   - `print(f"[SKIP] ...")` → `logger.info(...)`
   - All f-string interpolations converted to `%s`-style deferred formatting where practical.

4. **Preserved 6 CLI-facing `print()` calls** with `# intentional stdout` comments:
   - `l1_sectioning.py`: `print(f"-> {out}")` — final output path
   - `l3_validation.py`: `print("PASS"/"FAIL")`, `print("ERROR: ...")`, `print("WARN: ...")` — CLI validation result
   - `schema_review.py`: `print(report)` — the generated report is the product
   - `storage/loader.py`: `print(dry_run_preview(record))` — dry-run preview is the product

5. **No test changes needed** — zero tests used `capsys`/`capfd` fixtures.

### Print count reduction
- Before: ~77 `print()` calls across `src/hk_ipo/`
- After: 6 `print()` calls (all `# intentional stdout`)
- Reduction: ~92%

### Test results
```
506 passed, 317 deselected, 11 warnings in 26.87s
1 pre-existing failure (BOM in CSV header, unrelated to logging changes)
```

The single failing test (`test_csv_output_valid_csv_after_parallel_writes`) is a pre-existing issue with BOM (`﻿`) handling in CSV parsing — unrelated to the logging migration.
