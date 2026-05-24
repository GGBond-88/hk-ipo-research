# P2-8 — Enforce enrichment `version` bump on schema change

Status: done
Priority: P2
Effort: S (30 min)

## Goal
Add a CI / test check that the enrichment block's `version` field bumps whenever its schema's key set or value-domain changes.

## Why
Currently SI-014 assumes "schema changes ⇒ version bump" but nothing enforces it. Each enrichment writes `block["version"] = VERSION`; if VERSION constant isn't touched, downstream consumers can't detect the breaking change. See revise_plan.md §P2-8.

## Files touched
- Create: `tests/test_enrichment_versions.py`
- (Optional) Add `EXPECTED_KEYS` constant per enrichment module to make the assertion explicit.

## Steps
1. For each enrichment module, define the expected key set in the test file:
   ```python
   EXPECTED = {
       "geo": ({"version", "domestic_hk_pct", "mainland_pct", "overseas_pct"}, "1"),
       "country": ({"version", "countries"}, "1"),
       ...
   }
   ```
2. Test produces a fixture record, runs `_enrich_one`, then asserts:
   - block keys exactly match `EXPECTED[dim][0]`
   - `block["version"] == EXPECTED[dim][1]`
3. Failure of either part is the signal that the developer must bump `VERSION` (in the source module) AND update `EXPECTED` (in the test) in the same PR.

## Acceptance
- [ ] One test per enrichment module, all green.
- [ ] Editing any enrichment's output shape without updating both `VERSION` and `EXPECTED` fails the test.

## Dependencies
None.

---
## Resolution
Status: done
Created: tests/test_enrichment_versions.py
Coverage: 8 enrichment dimensions, each tested for VERSION string and key set.
All 8 pass.
