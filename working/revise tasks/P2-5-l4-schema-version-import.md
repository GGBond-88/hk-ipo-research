# P2-5 — Replace L4's hardcoded `"2.0"` with `SCHEMA_VERSION` import

Status: done
Priority: P2
Effort: XS (5 min)

## Goal
Stop hardcoding the schema version string in L4 output; use the canonical constant from `schema.py`.

## Why
[src/hk_ipo/l4_categorize.py:413](../../src/hk_ipo/l4_categorize.py) writes `output["schema_version"] = "2.0"` as a literal. When the schema bumps, this site silently lies. See revise_plan.md §P2-5.

## Files touched
- Modify: [src/hk_ipo/l4_categorize.py](../../src/hk_ipo/l4_categorize.py)

## Steps
1. At the top of `l4_categorize.py`, add:
   ```python
   from hk_ipo.schema import SCHEMA_VERSION
   ```
   (Verify the name in `schema.py`; if it's something like `CURRENT_SCHEMA_VERSION`, use that.)
2. Change line 413: `output["schema_version"] = SCHEMA_VERSION`.
3. `Grep -n '"2.0"' src/hk_ipo/` — confirm no other accidental literals; if any, fix them in the same patch.
4. Run `pytest -m "not e2e" -q` — green.

## Acceptance
- [ ] No `"2.0"` literal in `l4_categorize.py`.
- [ ] Tests pass without modification.

## Dependencies
None.

---
## Resolution
Status: done
Changed l4_categorize.py line 413 to use SCHEMA_VERSION from schema.py.
Other "2.0" literals found: src/hk_ipo/taxonomy.py:18 (its own SCHEMA_VERSION definition), src/hk_ipo/storage/loader.py:70 (fallback default in record.get(), not a stale hardcode)
Tests pass.
