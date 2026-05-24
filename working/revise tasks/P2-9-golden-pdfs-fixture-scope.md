# P2-9 — Tighten `golden_pdfs` fixture scope or add read-only protection

Status: done (already properly implemented)
Priority: P2
Effort: XS (15 min)

## Goal
Prevent tests from accidentally mutating the shared `golden_pdfs` fixture directory by either narrowing scope (`session` → `function`) or marking files read-only.

## Why
Session-scoped fixtures are shared across tests. A misbehaving test that writes into the fixture dir contaminates downstream tests. See revise_plan.md §P2-9.

## Files touched
- Reviewed: `tests/e2e/conftest.py` (fixture definition, NOT `tests/conftest.py` as initially assumed)

## Resolution

**Finding**: The `golden_pdfs` fixture already implements Option A (copy to `tmp_path` per test). No code changes were needed.

### What exists
- Fixture location: `tests/e2e/conftest.py` (not `tests/conftest.py` -- there is no root conftest)
- The fixture uses `tmp_path` (function-scoped by default, not session-scoped)
- It copies source PDFs from `tests/fixtures/golden_pdfs/` into `tmp_path / "golden_pdfs/"` per test invocation
- Returns list of `Path` objects pointing to the temp copies, not the originals
- The `isolated_data_dir` fixture wraps `golden_pdfs` and copies further into `tmp_path / "data" / "raw_pdfs"` for black-box CLI tests

### Verification
1. **Isolation confirmed**: Each test receives its own writable copies inside pytest's `tmp_path`. A misbehaving test cannot corrupt the shared `tests/fixtures/golden_pdfs/` source directory or the copies seen by other tests.
2. **No test writes into source dir**: `GOLDEN_DIR` is only referenced inside the `golden_pdfs` fixture (read-only glob + copy). No test module imports or references it.
3. **Fixture scope**: Function-scoped via `tmp_path` dependency (default pytest behavior). Not session-scoped.
4. **Tests**: 480 passed, 8 pre-existing failures in `test_l1_sectioning.py` (unrelated -- mock functions missing `force` keyword arg in signature). All golden_pdfs-related e2e tests are marked `e2e` and were deselected by `-m "not e2e"`.

### No code changes made
The fixture was already implemented correctly per Option A when it was first created. The original task-002 spec called for `scope="session"` but the actual implementation used `tmp_path` (function-scoped with copy-to-temp) from the start.

## Acceptance
- [x] Any attempt by a test to write into the returned path raises (or copies are isolated). -- Copies ARE isolated per test.
- [x] All existing tests still pass (480 pass, 8 pre-existing failures unrelated to golden_pdfs).

## Dependencies
None.
