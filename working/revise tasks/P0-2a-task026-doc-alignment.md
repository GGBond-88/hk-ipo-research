# P0-2a — Align task-026 implement-review-results.md with code reality

Status: done
Priority: P0
Effort: XS (15 min)

## Goal
Mark CR-001/CR-002/CR-003 as **Resolved** in task-026 review doc (they're fixed in code but doc says Pending), and write a Decision Reason for SR-001 (the OOM partial-fix case).

## Why
Second-pass verification confirms the four "Pending" items in [working/plan/task-026/implement-review-results.md](../plan/task-026/implement-review-results.md) are actually fixed in code (3 of 4) or partially mitigated by design (1 of 4). The doc drift makes the review look incomplete when work is actually done. See revise_plan.md §P0-2.

## Files touched
- Modify: [working/plan/task-026/implement-review-results.md](../plan/task-026/implement-review-results.md)

## Steps
For each of the four review items, edit the existing `Status:` and `Decision Reason:` lines:

### SR-001 — Frontend/Playwright OOM
- Status: `Resolved (mitigated)`
- Decision Reason: `_maybe_skip_oom() in tests/e2e/conftest.py detects V8 OOM patterns and converts the test to pytest.skip(). Residual FAIL cases on 4GB-RAM hosts are an environmental constraint documented in EI-001 (working/env-issues.md); resolving them requires Node memory tuning tracked separately in revise task P1-2. Not blocking task-026 closure.`

### CR-001 — timeline.py CLI prior-enrichment preservation
- Status: `Resolved`
- Decision Reason: `Fixed in [src/hk_ipo/enrichments/timeline.py:173-175](../../src/hk_ipo/enrichments/timeline.py). CLI __main__ now checks ENRICHED / f"{ticker}.json" and loads prior enriched record before _enrich_one. Regression test added in revise task P0-2b.`

### CR-002 — geo/country/specificity CLI same bug pattern
- Status: `Resolved`
- Decision Reason: `Fixed in: [geo.py:160-162](../../src/hk_ipo/enrichments/geo.py), [country.py:196-198](../../src/hk_ipo/enrichments/country.py), [specificity.py:145-147](../../src/hk_ipo/enrichments/specificity.py). Each CLI __main__ checks enriched_file.exists() and loads prior record. Regression tests added in revise task P0-2b.`

### CR-003 — test_loader_dry_run_does_not_modify_db uses wrong enriched dir
- Status: `Resolved`
- Decision Reason: `Fixed in [tests/e2e/test_pipeline_e2e.py:223-224](../../tests/e2e/test_pipeline_e2e.py). Test now passes --enriched-dir str(isolated_data_dir / "enriched") to scope the loader to the test's isolated tmp directory.`

## Acceptance
- [ ] All four review items in implement-review-results.md show `Status: Resolved` (or `Resolved (mitigated)` for SR-001).
- [ ] Each has a non-empty Decision Reason with concrete file:line references.
- [ ] No claims remain that contradict the current code state.

## Out of scope
- Do NOT add new tests here — that is [P0-2b](P0-2b-prior-enrichment-regression-tests.md).
- Do NOT modify source code — fixes already in place.

## Dependencies
None.

---
## Resolution
Status: done
All 4 items in working/plan/task-026/implement-review-results.md updated to Resolved with Decision Reasons.
