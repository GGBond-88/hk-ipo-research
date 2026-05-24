# Changes: Task-011

## Files
- [new] src/hk_ipo/enrichments/industry.py
- [new] tests/test_enrichments_industry.py
- [new] tests/e2e/test_l5_industry_blackbox.py

## Summary
Implemented L5 industry enrichment tool that assigns a GICS industry name to each company. Supports LLM-based classification (default) and manual CSV override (--source manual). Followed TDD: wrote failing tests first, then implemented to pass.

Black-box tests (21 test cases) were created covering: single-file mode, --all mode, --force flag, --source manual with CSV overrides, --source prospectus via LLM (skipped without API key), error paths, idempotency, and edge cases.

## Bug Fixes (found during black-box testing)
1. **--all mode fallback bug**: `enriched_dir.mkdir()` was called before the fallback check in `run()`, causing `enriched_dir` to always be considered non-empty. Fixed by moving the mkdir and checking for actual JSON files.
2. **Ticker derivation bug**: `_enrich_one()` re-resolved ticker from `record.get("hk_ticker", "unknown")`, losing the ticker derived from the filename stem by the CLI. Fixed by adding a `ticker` parameter to `_enrich_one()`.
