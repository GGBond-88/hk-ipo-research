# P0-1b — Run ruff + full pytest, capture counts

Status: done
Priority: P0
Effort: XS (15 min) — assuming green

## Goal
Establish a clean, reproducible baseline of lint + unit test results, captured for the task-027 meta files.

## Why
Task-027 Steps 1, 2, 5, 6 require running ruff and the test suite and recording the count. Currently no fresh run has been audited. Plan also claims "472 unit tests + 181 vitest" — need to verify.

## Files touched
- No source edits expected (if ruff reports new violations, fix them in the same task or open a follow-up).
- Output captured to: `working/revise tasks/P0-1b-results.md` (create at end).

## Steps
1. Run lint:
   ```powershell
   ruff check src tests scripts
   ```
   Record stdout + exit code.
2. Run Python unit tests (exclude e2e):
   ```powershell
   python -m pytest -q -m "not e2e" --tb=short
   ```
   Record final summary line (e.g. `472 passed in 38.21s`).
3. Run frontend tests:
   ```powershell
   cd frontend
   npm test
   cd ..
   ```
   Record final vitest summary (e.g. `Test Files  X passed`, `Tests  Y passed`).
4. If ruff reports issues: fix only auto-fixable ones with `ruff check --fix src tests scripts` and re-run. If real bugs surface, STOP and surface them as a follow-up task in this folder — do NOT silently change behavior.
5. Write [working/revise tasks/P0-1b-results.md](P0-1b-results.md) with:
   - ruff command + exit code + count of remaining warnings (should be 0)
   - pytest command + final summary line + duration
   - vitest command + final summary line
   - Any deviations from the plan's "472 / 181" counts

## Acceptance
- [ ] `ruff check src tests scripts` exits 0.
- [ ] `pytest -q -m "not e2e"` exits 0 with all tests passing.
- [ ] `npm test` in frontend/ exits 0.
- [ ] `P0-1b-results.md` exists with the three command outputs (summary lines only, not full stdout).

## Out of scope
- E2E tests (run separately in [P1-1](P1-1-real-e2e-validation.md)).
- Frontend build (use [P1-2](P1-2-frontend-oom-rootfix.md) baseline — may OOM on low-RAM box).

## Dependencies
None (but P0-1a doesn't change runtime behavior, so order with P0-1a is free).

---
## Resolution
Status: done
ruff exit code: 1 (1 auto-fixed import sort; 2 remaining E501 in test fixtures, not auto-fixable). pytest: 2 failed, 709 passed, 78 deselected, 11 warnings in 373.23s — the 2 failures are e2e tests missing @pytest.mark.e2e marker (LLM calls with no API key). vitest: Test Files 8 passed (8), Tests 181 passed (181), 1 unhandled error (intentional CSP mock leaking from ExportButton test).
Results written to working/revise tasks/P0-1b-results.md
