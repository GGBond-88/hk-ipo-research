# Changes: Task-002

## Files
- [new] tests/e2e/__init__.py
- [new] tests/e2e/conftest.py
- [new] tests/e2e/test_pipeline_e2e.py
- [new] tests/e2e/test_dashboard_build_e2e.py
- [new] tests/fixtures/golden_pdfs/README.md
- [mod] pyproject.toml

## Summary
Created end-to-end black-box test suite for the HK IPO pipeline as the RED phase of the outer TDD loop. Added `e2e` pytest marker, shared fixtures (golden PDFs, isolated data dir, API key check, CLI helpers), and 7 black-box tests covering full pipeline output, Chinese PDF skip, corrupt PDF resilience, idempotent re-run, dry-run-cost, loader dry-run, and frontend dashboard build.

**SR-001 fix:** Fixed `test_frontend_build_produces_dist_folder` to resolve npm via `shutil.which("npm")` and call it by full path. On Windows, bare `"npm"` resolves to a `.CMD` file that `CreateProcess` cannot execute directly, causing a spurious `FileNotFoundError`. The test now fails for the correct reason: `frontend/package.json` does not exist (frontend project not yet created). Verified working.

**CR-001 fix:** Replaced `npm_exe: str = shutil.which("npm")  # type: ignore[assignment]` with untyped `npm_exe = shutil.which("npm")` followed by `assert npm_exe is not None, "npm not found in PATH (skipif guard should have caught this)"`. Eliminates type-safety bypass, makes the invariant explicit, and provides a clear diagnostic if the guard invariant is ever violated.

All 7 e2e tests are in expected RED state: 1 FAIL (missing frontend), 6 SKIP (no golden PDFs). All 140 existing unit tests pass with no regressions.
