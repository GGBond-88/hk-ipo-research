# Test Results: Task-011

## Status
UPDATED — bugs found and fixed via black-box testing

## Unit Tests

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_industry_dimension_and_version | PASS | PASS | no | - |
| test_manual_override_loads_csv | PASS | PASS | no | - |
| test_manual_override_no_csv_returns_empty | PASS | PASS | no | - |
| test_run_manual_source_uses_override | PASS | PASS | no | - |
| test_industry_block_shape | PASS | PASS | no | - |

## Black-Box Tests (new in this task)

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| BB-L5-I-001: test_manual_single_file_uses_override | PASS | PASS | no | - |
| BB-L5-I-002: test_manual_ticker_not_in_csv_yields_unknown | PASS | PASS | no | - |
| BB-L5-I-003: test_manual_no_csv_file_uses_unknown | PASS | PASS | no | - |
| BB-L5-I-004: test_manual_all_processes_all_files | PASS | PASS | no | --all mode now works |
| BB-L5-I-005: test_all_falls_back_to_categorized_when_enriched_empty | PASS | PASS | no | empty enriched dir fallback works |
| BB-L5-I-006: test_all_stdout_reports_industry_per_ticker | PASS | PASS | no | - |
| BB-L5-I-007: test_force_reprocesses_existing_enrichment | PASS | PASS | no | - |
| BB-L5-I-008: test_nonexistent_file_exits_nonzero | PASS | PASS | no | - |
| BB-L5-I-009: test_no_args_exits_nonzero | PASS | PASS | no | - |
| BB-L5-I-010: test_single_file_idempotent_output | PASS | PASS | no | - |
| BB-L5-I-011: test_all_mode_idempotent_output | PASS | PASS | no | - |
| BB-L5-I-012: test_empty_uses_list_handled_gracefully | PASS | PASS | no | - |
| BB-L5-I-013: test_ticker_derived_from_filename_if_missing_in_record | PASS | PASS | no | ticker-from-filename bug fixed |
| BB-L5-I-014: test_stdout_reports_industry_for_single_file | PASS | PASS | no | - |
| BB-L5-I-015: test_csv_with_whitespace_trimmed | PASS | PASS | no | - |
| BB-L5-I-016: test_csv_blank_lines_skipped | PASS | PASS | no | - |
| BB-L5-I-017: test_prospectus_single_file_classifies_via_llm | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| BB-L5-I-018: test_prospectus_all_mode | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| BB-L5-I-019: test_prospectus_with_manual_override_takes_priority | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| BB-L5-I-020: test_prospectus_empty_uses_still_classifies | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| BB-L5-I-021: test_prospectus_llm_error_graceful_degradation | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |

## Full Suite Regression

| Suite | Result | Details |
|-------|--------|---------|
| All tests except e2e | 265 passed | No regressions |
| All e2e tests | 72 passed, 18 skipped, 1 pre-existing failure | test_frontend_build_produces_dist_folder fails due to missing frontend/package.json (unrelated) |

## Bugs Found and Fixed

### Bug 1: --all mode processes nothing on first run
- Root cause: `run()` called `enriched_dir.mkdir()` before the `all_files` fallback check, so `enriched_dir` always existed, causing the code to read from the empty enriched/ directory instead of categorized/.
- Fix: Moved `enriched_dir.mkdir()` to after the fallback check; added check for JSON files (not just directory existence) to handle the empty-directory case.

### Bug 2: Missing hk_ticker in record causes output to wrong filename
- Root cause: `_enrich_one()` re-resolved the ticker via `record.get("hk_ticker", "unknown")`, discarding the ticker that the CLI correctly derived from the input filename stem.
- Fix: Added `ticker` parameter to `_enrich_one()`; `run()` now passes the resolved ticker explicitly.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 21 (5 unit + 16 black-box)
- UNEXPECTED (Result=Expected, Blocked=no): 0
- Blocked (Blocked=yes): 5 (LLM tests requiring API key)
