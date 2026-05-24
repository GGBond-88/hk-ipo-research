# P0-2b — Add prior-enrichment regression tests for 4 enrichments

Status: done
Priority: P0
Effort: M (60–90 min)

## Goal
Add `test_cli_preserves_prior_enrichments` blackbox tests for `timeline`, `country`, `geo`, and `specificity` so the CR-001/CR-002 fixes are guarded against regression.

## Why
Code fixes for CR-001/CR-002 (CLI `__main__` paths now load existing enriched file before re-enriching) exist in 4 modules but only `capex_opex` and `esg_tag` have a corresponding test. Without coverage these can silently regress. See revise_plan.md §P0-2.

## Reference implementation
[tests/e2e/test_l5_capex_opex_blackbox.py](../../tests/e2e/test_l5_capex_opex_blackbox.py) — search for `test_cli_preserves_prior_enrichments` (test id BB-L5-CO-028). Use the same shape:
1. Seed `data/enriched/<ticker>.json` with a record containing a prior `enrichments` block from a sibling dimension (e.g., a geo block).
2. Invoke the module's CLI on the categorized single file.
3. Assert the resulting enriched file still contains both the prior block AND the new block.

## Files touched
- Modify: [tests/e2e/test_l5_timeline_blackbox.py](../../tests/e2e/test_l5_timeline_blackbox.py) — add one new test method
- Modify: [tests/e2e/test_l5_country_blackbox.py](../../tests/e2e/test_l5_country_blackbox.py) — add one new test method
- Create: `tests/e2e/test_l5_geo_blackbox.py` — new file modeled on `test_l5_country_blackbox.py` shape
- Create: `tests/e2e/test_l5_specificity_blackbox.py` — new file modeled on `test_l5_country_blackbox.py` shape

## Steps
1. Open the reference test in `test_l5_capex_opex_blackbox.py` and read the prior-enrichment test end to end.
2. For `timeline` and `country`: copy the test method, change the module under test (`hk_ipo.enrichments.timeline` / `.country`) and the asserted enrichment dimension key.
3. For `geo` and `specificity`: create a new blackbox file. Minimum content: a class `TestL5GeoBlackbox` / `TestL5SpecificityBlackbox` with at least the `test_cli_preserves_prior_enrichments` method. Imports and fixtures mirror `test_l5_country_blackbox.py`.
4. Each test seeds a prior block from a *different* dimension (e.g., timeline test seeds a prior `geo` block; geo test seeds a prior `industry` block) so the test exercises the "preserve" logic, not self-overwrite.
5. Run only the new tests:
   ```powershell
   python -m pytest tests/e2e/test_l5_timeline_blackbox.py::TestL5TimelineBlackbox::test_cli_preserves_prior_enrichments tests/e2e/test_l5_country_blackbox.py::TestL5CountryBlackbox::test_cli_preserves_prior_enrichments tests/e2e/test_l5_geo_blackbox.py tests/e2e/test_l5_specificity_blackbox.py -v
   ```
6. All 4 must pass without an API key (CLI uses categorized → enriched flow; LLM calls in these dims are gated by env/mock — confirm by reading the module's `_enrich_one`).

## Acceptance
- [ ] 4 new test methods exist and pass.
- [ ] Each test deliberately mutates an existing enriched file with a foreign-dimension block and asserts both blocks coexist after the CLI run.
- [ ] No flaky network dependencies — tests run offline (use the same mocking pattern as capex_opex reference test).
- [ ] `pytest -q` total count increases by exactly 4.

## Out of scope
- Do NOT add regression tests for industry / commitment — industry CLI uses `run(ticker=...)` which already routes through `load_enriched_or_categorized()`; commitment already has full coverage.
- Do NOT touch the enrichment source files — only tests.

## Dependencies
None. Best run before [P0-1b](P0-1b-ruff-and-pytest.md) so the recorded test count reflects the +4.

---
## Resolution
Status: done
Added test_cli_preserves_prior_enrichments to: test_l5_timeline_blackbox.py, test_l5_country_blackbox.py
Created: tests/e2e/test_l5_geo_blackbox.py, tests/e2e/test_l5_specificity_blackbox.py
All 4 new tests pass.
