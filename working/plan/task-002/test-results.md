# Test Results: Task-002

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_frontend_build_produces_dist_folder | FAIL | FAIL | no | RED phase: missing frontend/package.json -- frontend project not yet created (correct failure reason) |
| test_full_pipeline_produces_all_outputs | SKIP | SKIP | yes | Need >=3 PDFs in golden_pdfs (0 present); OPENROUTER_API_KEY also not set |
| test_chinese_pdf_skipped_with_stub | SKIP | SKIP | yes | Need >=3 PDFs in golden_pdfs (0 present); OPENROUTER_API_KEY also not set |
| test_corrupt_pdf_does_not_block_other_tickers | SKIP | SKIP | yes | Need >=3 PDFs in golden_pdfs (0 present); OPENROUTER_API_KEY also not set |
| test_rerun_is_idempotent | SKIP | SKIP | yes | Need >=3 PDFs in golden_pdfs (0 present); OPENROUTER_API_KEY also not set |
| test_dry_run_cost_makes_no_api_calls | SKIP | SKIP | yes | Need >=3 PDFs in golden_pdfs (0 present) |
| test_loader_dry_run_does_not_modify_db | SKIP | SKIP | yes | Need >=3 PDFs in golden_pdfs (0 present); OPENROUTER_API_KEY also not set |

## Unfixed Blocked Tests

### test_full_pipeline_produces_all_outputs (and 5 other pipeline tests)
- **File:** tests/e2e/test_pipeline_e2e.py (all 6 tests)
- **Expected:** Run full pipeline via CLI, assert each stage's outputs exist on disk and DB has all required tables
- **Actual:** SKIP -- fewer than 3 PDFs in tests/fixtures/golden_pdfs/
- **root cause:** The golden_pdfs session-scoped fixture requires >=3 PDF files in `tests/fixtures/golden_pdfs/`, but 0 PDF files are present. The task spec (Step 2) explicitly states "Do NOT commit PDF binaries here. Each task that needs to run the e2e suite must copy three files from `data/raw_pdfs/`." This is by design for the RED phase -- the task spec Step 7 explicitly accepts skips for this reason. The tests will transition to actual execution when golden PDFs are provisioned in Task 026.
- **3 attempted approaches:** (1) Verified data/raw_pdfs/ contains 6 real PDFs that could serve as golden corpus, but task spec requires specific naming convention (03690.pdf, zh_demo.pdf, plus one other). (2) Considered creating symlinks from data/raw_pdfs/ to golden_pdfs/ -- Windows requires admin privileges for symlinks. (3) Considered copying PDFs directly -- but task spec defers PDF provisioning to later tasks (Task 026) when the pipeline modules exist and tests need to transition from RED to GREEN.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 1
- UNEXPECTED (Result≠Expected, Blocked=no): 0
- Blocked (Blocked=yes): 6
