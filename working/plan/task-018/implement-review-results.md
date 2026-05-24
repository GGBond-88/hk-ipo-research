# Implement Review Results: Task-018

## Spec Review Issues

### SR-001: Missing explicit transaction wrapping for atomic upsert
- Status: Resolved
- Description: The `upsert()` function performs DELETE operations on `uses` and `company_tags` followed by INSERT into `companies`, `uses`, and `use_tags`, but does NOT wrap these operations in an explicit `BEGIN TRANSACTION` / `COMMIT` block. In Python's `sqlite3` default autocommit mode (`isolation_level=''`), each DML statement auto-commits independently. This means the sequence is not atomic -- if a mid-sequence failure occurs (e.g., `companies` upsert succeeds but a `uses` INSERT fails), the DELETEs and partial INSERTs are already committed, leaving the database in an inconsistent state. The task objective explicitly requires "per-ticker transaction-based upsert" and the module docstring claims "in a single transaction." Without explicit transaction boundaries, concurrent readers could also observe a ticker with deleted uses rows before new ones are inserted.

## Code Review Issues

### CR-001: dry_run_preview has unused conn parameter
- Status: Resolved
- Description: `src/hk_ipo/storage/loader.py:120` -- The `conn` parameter of `dry_run_preview(conn, record)` is never referenced in the function body (lines 121-133). The function only inspects the `record` dict. This is misleading: a reader would reasonably expect `conn` to be used for something (checking current DB state, computing diffs, etc.). Should either use the connection or remove the parameter.
- Decision Reason:

### CR-002: process_all miscounts loaded records in dry-run mode
- Status: Resolved
- Description: `src/hk_ipo/storage/loader.py:166-169` -- In `process_all()`, `loaded += 1` executes unconditionally after `process_single()` returns, regardless of `dry_run`. When `dry_run=True`, the summary at line 173 will print e.g. "L6 complete: 5 loaded (of 5 total)" even though nothing was actually written to the database. This produces a misleading user-facing summary. Either track a separate counter for dry-run mode or skip incrementing `loaded` when `dry_run=True`.
- Decision Reason:

### CR-003: No input validation on JSON record before upsert
- Status: Resolved
- Description: `src/hk_ipo/storage/loader.py:142` -- `process_single()` loads JSON via `json.loads()` but performs zero validation on the record structure. If the JSON file is missing `hk_ticker`, is malformed, or has unexpected types, the failure surfaces as a cryptic `KeyError` or `TypeError` deep inside `upsert()` (e.g., line 27: `ticker = record["hk_ticker"]`). At minimum, required fields (`hk_ticker`, `uses`) should be validated before calling `upsert()`, with a clear error message identifying the problematic file.
- Decision Reason:

### CR-004: process_all / process_single / CLI have zero test coverage
- Status: Resolved
- Description: `tests/test_storage_loader.py` -- The 6 tests only exercise the internal functions `upsert()` and `dry_run_preview()`. The following public API surfaces are completely untested: (a) `process_single()` -- direct call with real/empty JSON file, (b) `process_all()` -- batch processing with multiple files, empty directory, partial failures, (c) CLI (`__main__` block) -- `--all`, single-file, `--dry-run`, `--db`, missing file error, mutually exclusive group validation. These are the primary interfaces users will interact with; leaving them untested means regressions in argument parsing, file handling, or error propagation will not be caught.
- Decision Reason:

### CR-005: Unused imports in test file
- Status: Resolved
- Description: `tests/test_storage_loader.py:4-5` -- `import hashlib` and `import json` are imported at the top of the file but never used in any test function. Dead imports suggest incomplete test coverage (perhaps a planned content-hash-based idempotency check was never implemented) and add noise.
- Decision Reason:

### CR-006: Inline imports in test functions mask import-time errors
- Status: Resolved
- Description: `tests/test_storage_loader.py:58,78,98,118,140,161` -- Every test function imports `upsert` (and sometimes `dry_run_preview`) from `hk_ipo.storage.loader` inside the function body rather than at module level. If the loader module has a syntax error or an unresolvable import, `pytest` collection succeeds but the test fails with a `ModuleNotFoundError` or `SyntaxError` at runtime. Module-level imports would surface such errors during collection, giving earlier and clearer feedback. Additionally, the repeated inline imports are boilerplate that a module-level import (or a fixture) would eliminate.
- Decision Reason:

### CR-007: test_upsert_idempotent only checks row counts, not data stability
- Status: Resolved
- Description: `tests/test_storage_loader.py:117-136` -- The task spec requires "loading the same enriched JSON twice yields byte-identical DB state." The test `test_upsert_idempotent` only asserts that `COUNT(*)` from `uses` and `use_tags` stays the same after a second upsert. It does not verify that column values are identical (e.g., that `amount_hkd_million`, `percentage`, or `review_reasons` match). For instance, if the second upsert silently dropped the `amount_hkd_million` column or changed `review_reasons` serialization, this test would still pass. The test should compare full row contents (or at least a hash of key columns) across the two upserts.
- Decision Reason:

### CR-008: Hardcoded enriched path in __main__ instead of config constant
- Status: Resolved
- Description: `src/hk_ipo/storage/loader.py:187` -- The CLI block hardcodes `ENRICHED_DIR = DATA_DIR / "enriched"`, but other data directories (raw_pdfs, sections, extracted, reports, categorized) are defined as constants in `src/hk_ipo/config.py`. This is inconsistent and would require code changes if the enriched directory path ever needs to change. Define `ENRICHED_DIR` in `config.py` and import it.
- Decision Reason:

### SR-002: test_cli_all_flag bypasses argparse, leaving --all CLI path untested
- Status: Resolved
- Description: `tests/test_storage_loader.py:383-416` -- The test named `test_cli_all_flag` spawns a subprocess that imports the loader module and calls `process_all()` directly via inline Python code. It never invokes the CLI entry point with `--all` (e.g., `python -m hk_ipo.storage.loader --all --db ...`). This means the `__main__` block's `--all` argument parsing (argparse mutually-exclusive group validation, argument-to-flag mapping) and the `if args.all: process_all(ENRICHED_DIR, db_path, dry_run=args.dry_run)` branch have zero test coverage in the standard test suite. The e2e test at `tests/e2e/test_pipeline_e2e.py:192` does use `--all`, but that suite is excluded from the standard run (`--ignore=tests/e2e`). The test name is misleading -- it claims to test the CLI `--all` flag but exercises an entirely different code path.
- Decision Reason: Added --enriched-dir CLI argument and rewrote test_cli_all_flag to invoke actual CLI with subprocess.run([sys.executable, "-m", "hk_ipo.storage.loader", "--all", "--enriched-dir", ...]), exercising the argparse mutually-exclusive group and --all branch.

### CR-009: dry_run_preview tag count diverges from upsert insertion count
- Status: Resolved
- Description: `src/hk_ipo/storage/loader.py:131` vs `loader.py:114` -- The `dry_run_preview` function counts tags with `len(v) if isinstance(v, list)` (taking the raw list length without filtering), while `upsert()` filters falsy values per element: `for val in (v for v in vals if v)`. If an enrichment's `by_use_id` maps a use_id to a list containing empty strings (e.g., `["mainland", ""]`), the preview reports 2 tags but upsert inserts only 1. The two code paths should use identical filtering logic to ensure the preview is an accurate representation of what will be written.
- Decision Reason: Rewrote dry_run_preview tag counting to use identical filtering logic as upsert: normalize values to list with `values if isinstance(values, list) else [values]`, then count with `sum(1 for v in vals if v)` to filter falsy values.

### CR-010: process_single creates database schema during dry-run (unnecessary side effect)
- Status: Resolved
- Description: `src/hk_ipo/storage/loader.py:158-167` -- `process_single` calls `create_tables(conn)` on line 160 before the `dry_run` check on line 161. Since `dry_run_preview` no longer requires a database connection (the `conn` parameter was removed per CR-001), calling `create_tables` in dry-run mode is unnecessary. It creates the SQLite database file and writes the full schema (6 tables, 6 indices) even when the user passes `--dry-run`. While `CREATE TABLE IF NOT EXISTS` makes this idempotent (no harm on subsequent real runs), it violates the contract of dry-run as read-only preview. The `create_tables` call should be moved inside the non-dry-run branch, or the dry-run path should open the connection differently to avoid schema side effects.
- Decision Reason: Moved create_tables(conn) call inside the non-dry-run branch in process_single(). Updated test_process_single_dry_run_does_not_modify_db, test_process_all_dry_run_does_not_load, and test_cli_dry_run_flag to verify no user tables exist (query sqlite_master) rather than checking companies row count.
