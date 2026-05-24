# Task 026: E2E black-box verification + bug fixes (GREEN)

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** All layers now exist. This task runs the end-to-end black-box tests from Task 002 and fixes any bugs that prevent them from passing.
- **Tech Stack:** Python 3.10+, pytest, SQLite.

## Task Objective

Run the full end-to-end test suite against a golden 3-PDF corpus. Fix bugs exposed by the tests, following TDD for each fix. By the end of this task, all E2E tests must pass or skip with a documented reason.

This is Task 26 of 27.

---

**Files:**
- (Bug fix targets determined at runtime — any file in `src/hk_ipo/` or `scripts/` or `tests/e2e/`)

- [ ] **Step 1: Prepare the golden PDF corpus**

Copy 3 PDFs into `tests/fixtures/golden_pdfs/`:

```
tests/fixtures/golden_pdfs/
  - 03690.pdf   (Meituan — copy from data/raw_pdfs/ if present)
  - One additional English HKEX prospectus from data/raw_pdfs/
  - zh_demo.pdf (any Chinese-dominant PDF from original corpus if available;
                 if none exists, create a placeholder Chinese PDF for the skip test)
```

Run (PowerShell):
```powershell
$golden = "tests\fixtures\golden_pdfs"
New-Item -ItemType Directory -Force -Path $golden | Out-Null
Copy-Item "data\raw_pdfs\03690.pdf" $golden -Force -ErrorAction SilentlyContinue
# Copy a second English PDF
Get-ChildItem "data\raw_pdfs\*.pdf" | Select-Object -First 3 | ForEach-Object { Copy-Item $_.FullName $golden -Force }
```

- [ ] **Step 2: Run the E2E test suite and capture failures**

Run: `python -m pytest tests/e2e -m e2e -v --tb=long 2>&1 | Select-Object -Last 200`

If `OPENROUTER_API_KEY` is not set, tests will skip. Set it to a valid key or accept skips.

Expected: Some tests FAIL (not SKIP). Record the failures.

- [ ] **Step 3: Triage each failure**

For each failing test, determine:
- **Test bug:** the test's assertion is wrong for the actual behavior. Fix the test (TDD: write fix -> verify).
- **Implementation bug:** the code doesn't do what the spec requires. Fix the code (TDD: write a failing unit test -> implement fix -> verify).
- **E2E skip:** the test requires infrastructure that's not available (e.g., no golden PDFs, no API key). This is acceptable — tasks may skip.

- [ ] **Step 4: Fix bugs found — follow TDD for each**

For each implementation bug:

1. Write a failing unit test that isolates the bug in the relevant module.
2. Run the unit test to confirm it fails for the expected reason.
3. Implement the fix.
4. Run the unit test to confirm it passes.
5. Re-run the E2E test to confirm the larger scenario passes.

Common bugs to expect:
- `hk_ipo.enrichments.*` imports may fail if `config.CATEGORIZED_DIR` not defined yet (fixed in Task 008)
- Orchestrator `--only` / `--skip` flags may reference stage names that don't yet exist
- Loader may fail on records missing `enrichments` key
- Export functions may fail on NULL fields from SQLite
- L4 may try to set `needs_human_review` and get key errors if not pre-existing in record

- [ ] **Step 5: Run the full test suite after all fixes**

Run: `python -m pytest -q`

Expected: All non-e2e tests pass. E2E tests pass or skip.

- [ ] **Step 6: Run ruff check**

Run: `ruff check src/ tests/`

Expected: No lint errors. If there are any, fix them.

- [ ] **Step 7: Final E2E run**

Run: `python -m pytest tests/e2e -m e2e -v`

Expected: All E2E tests PASS or SKIP with documented reasons (missing API key, insufficient golden PDFs).

- [ ] **Step 8: Document any unresolvable issues**

If any E2E test cannot be made to pass because of environment constraints:
- Record the issue in `working/env-issues.md` with the `EI-XXX` format.
- The test must still skip gracefully (not error).
