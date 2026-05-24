# Changes: Task-018

## Files
- [mod] src/hk_ipo/config.py
- [mod] src/hk_ipo/storage/loader.py
- [mod] tests/test_storage_loader.py

## Summary
Fixed 9 review issues (1 spec review + 8 code review) against the L6 SQLite loader implementation. Key changes: (1) wrapped upsert() DML operations in explicit BEGIN/COMMIT/ROLLBACK transaction for atomicity, (2) removed unused conn parameter from dry_run_preview(), (3) fixed process_all() to not increment loaded counter in dry-run mode, (4) added input validation for required fields (hk_ticker, uses) in process_single(), (5) added 15 new tests covering process_single, process_all, CLI, and enhanced idempotency test with full data comparison, (6) removed unused hashlib import and moved imports to module level, (7) added ENRICHED_DIR constant to config.py.

Second round fixes (3 Pending issues): (8) fixed dry_run_preview tag counting to use identical filtering logic as upsert (normalize to list, filter falsy values), (9) moved create_tables(conn) call inside non-dry-run branch in process_single(), updated dry-run tests to verify no user tables via sqlite_master, (10) added --enriched-dir CLI argument and rewrote test_cli_all_flag to invoke actual CLI subprocess with --all --enriched-dir, exercising argparse mutually-exclusive group and --all branch.
