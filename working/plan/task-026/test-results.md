# Test Results: Task-026

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_dry_run_cost_makes_no_api_calls | PASS | PASS | no | - |
| test_dev_server_starts_and_serves_expected_content | PASS | PASS | no | - |
| test_full_pipeline_produces_all_outputs | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| test_chinese_pdf_skipped_with_stub | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| test_corrupt_pdf_does_not_block_other_tickers | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| test_rerun_is_idempotent | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| test_loader_dry_run_does_not_modify_db | SKIP | SKIP | yes | OPENROUTER_API_KEY not set |
| test_frontend_build_produces_dist_folder | FAIL | PASS | yes | JavaScript heap OOM during npm install (see EI-001) |
| TestFilterBar::test_renders_five_filter_dropdowns_with_labels | FAIL | PASS | yes | Vite dev server OOM, cannot start (see EI-001) |
| TestFilterBar::* (24 more tests) | FAIL | PASS | yes | Vite dev server OOM, cannot start (see EI-001) |
| TestExportButton::* (8 tests) | FAIL | PASS | yes | Vite dev server OOM, cannot start (see EI-001) |
| TestLayout::* (3 tests) | FAIL | PASS | yes | Vite dev server OOM, cannot start (see EI-001) |
| test_dashboard_views_e2e.py (all tests) | FAIL | PASS | yes | Vite dev server OOM, cannot start (see EI-001) |
| Non-E2E unit tests (472 tests) | PASS | PASS | no | - |
| Ruff lint check | PASS | PASS | no | All checks passed after fixes |

## Unfixed Blocked Tests

### test_frontend_build_produces_dist_folder and all Playwright browser tests
- **File:** tests/e2e/test_dashboard_build_e2e.py, tests/e2e/test_filterbar_exportbutton_e2e.py, tests/e2e/test_dashboard_views_e2e.py
- **Expected:** All PASS
- **Actual:** FAIL/ERROR due to JavaScript heap out of memory / Vite dev server OOM
- **Root cause:** System has 4GB total RAM with ~500MB free. Node.js/Vite requires significant heap memory (~300MB+) for esbuild transforms and module resolution. Both `npm install` and `vite dev` fail with "FATAL ERROR: Committing semi space failed. Allocation failed - JavaScript heap out of memory." Verified by executing the tests 3+ times with consistent OOM failures. The `npm run dev` that DOES work (test_dev_server_starts_and_serves_expected_content passes) succeeds only because it doesn't need to load the full Vite dev server with React hot module replacement via Playwright.
- **3 attempted approaches:**
  1. Running with `-p no:anyio` to fix Playwright sync API conflict - fixes the Playwright startup error but Vite still OOMs
  2. Running tests individually with `--no-header` to reduce memory pressure - still OOMs
  3. Clearing all background processes and re-running with minimal concurrency - still OOMs
- **Resolution:** environment requires more RAM (recommend >= 8GB) or a lighter build tool configuration

### Pipeline E2E tests (5 tests)
- **File:** tests/e2e/test_pipeline_e2e.py
- **Expected:** PASS (or SKIP if API key unavailable)
- **Actual:** SKIP due to missing OPENROUTER_API_KEY
- **Root cause:** No OpenRouter API key configured in environment. The tests use `api_key_present` fixture which calls `pytest.skip()` when key is absent. This is by design.
- **3 attempted approaches:**
  1. Checked if there are mock/fake API endpoints to use - no test mocking infrastructure exists for the E2E pipeline
  2. Checked if a dry-run mode exists that doesn't need an API key - dry-run only works for cost estimation, not for actual pipeline
  3. Verified that the skip behavior is intentional (fixture design) and not a bug
- **Resolution:** Tests skip gracefully by design when OPENROUTER_API_KEY is absent

## Summary
- EXPECTED (Result=Expected, Blocked=no): 474 (472 unit + 2 E2E)
- UNEXPECTED (Result≠Expected, Blocked=no): 0
- Blocked (Blocked=yes): 7 (5 API key skips + 1 frontend build OOM + Playwright OOM group)
