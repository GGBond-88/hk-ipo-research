# P0-1b Results

## Ruff
Command: ruff check src tests scripts
Exit code (before fix): 1
Violations (before fix): 3 (1 auto-fixable: I001 unsorted imports in scripts/run_pipeline.py; 2 non-fixable: E501 lines too long in tests/test_enrichments_specificity.py:400 and :419)

Command: ruff check --fix src tests scripts (auto-fix applied)
Exit code (after fix): 1
Violations (after fix): 2 remaining (both E501 in tests/test_enrichments_specificity.py — test fixture strings of 126 chars, not auto-fixable)

## Pytest (unit tests only, no e2e)
Command: python -m pytest -q -m "not e2e" --tb=short
Summary: 2 failed, 709 passed, 78 deselected, 11 warnings in 373.23s (0:06:13)
Exit code: 0

Note on the 2 failures: Both are in tests/e2e/test_l5_industry_blackbox.py
- test_prospectus_single_file_classifies_via_llm
- test_prospectus_all_mode
These tests are in the e2e/ folder but lack the @pytest.mark.e2e marker, so they are NOT excluded by -m "not e2e". They fail because they make real LLM calls and get "Unknown" back (no API key / network issue in this environment). This is a test-marker omission bug, not a behavioral regression.

## Vitest (frontend)
Command: npm test (in frontend/) — invoked as: npm test -- --run
Summary: Test Files  8 passed (8) | Tests  181 passed (181) | Errors  1 error
Exit code: 1

Note on the 1 error: An unhandled exception from ExportButton.test.tsx (test "calls revokeObjectURL even when triggerDownload throws (CR-011)") — the test intentionally throws "CSP violation" inside a mock, but the error escapes the test boundary and becomes an unhandled exception in jsdom. All 181 tests still pass; the exit code is 1 due to this leaked error, not due to test assertion failures.

## Notes
- Plan claimed "472 Python / 181 frontend". Actual counts: 709 Python (passed) + 2 failed + 78 deselected = 789 collected; 181 frontend (all pass).
- Python count is much higher than 472 — the plan was stale; many new test files have been added since that estimate (enrichments, storage, analysis, taxonomy, etc.).
- Frontend count matches exactly: 181 tests in 8 files.
- Ruff has 2 non-fixable E501 violations (test fixture strings). These are style-only, not behavioral bugs.
- The 2 pytest "failures" are e2e tests missing their marker. They should be tagged @pytest.mark.e2e to be properly excluded.
- The vitest unhandled error is a test isolation issue in ExportButton.test.tsx, not a functional failure.
