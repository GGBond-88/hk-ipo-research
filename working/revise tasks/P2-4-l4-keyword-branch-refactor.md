# P2-4 — Refactor `assign_parent()` keyword branches in l4_categorize.py

Status: done
Priority: P2
Effort: M (60–90 min)

## Goal
Replace the long `if/elif` keyword tree in `assign_parent()` with a data-driven lookup against the taxonomy module, falling back to an LLM call only when the lookup misses.

## Why
Keyword chains are brittle and hidden from the canonical taxonomy. Centralizing them in `taxonomy.py` keeps one source of truth. See revise_plan.md §P2-4.

## Files touched
- Modify: [src/hk_ipo/l4_categorize.py](../../src/hk_ipo/l4_categorize.py) — `assign_parent()`
- Modify: [src/hk_ipo/taxonomy.py](../../src/hk_ipo/taxonomy.py) — add `parent_for_main(main_category: str) -> str | None`
- Modify: tests `tests/test_l4_categorize.py` and `tests/test_taxonomy.py`

## Steps
1. In `taxonomy.py`, build a `MAIN_TO_PARENT: dict[str, str]` from the existing taxonomy schema (Growth, Financing, Working Capital, Others).
2. Add `def parent_for_main(name: str) -> str | None: return MAIN_TO_PARENT.get(name)`.
3. In `assign_parent()`, first try `parent_for_main(main)`. If `None`, fall back to current LLM call.
4. Delete the dead `if/elif` keyword branches.
5. Re-run `pytest tests/test_l4_categorize.py -v` + `tests/test_taxonomy.py`.

## Acceptance
- [x] `assign_parent()` body shrinks by ≥ 50%.
- [x] All L4 tests pass.
- [x] Coverage for `parent_for_main` added in `tests/test_taxonomy.py` (one test per Parent).

## Dependencies
None.

## Resolution

### What was changed

**`src/hk_ipo/taxonomy.py`**:
- Added `parent_for_main(name: str) -> str | None` function that looks up a Main
  category name in the existing `MAIN_TO_PARENT` dict and returns its Parent
  category, or None if unknown.

**`src/hk_ipo/l4_categorize.py`**:
- Replaced the 65-line keyword `if/elif` tree in `assign_parent()` with a
  data-driven lookup: first tries `parent_for_main(main)` for an exact taxonomy
  match, then falls back to `_llm_assign_parent()` (new helper) when the Main is
  not in the closed vocabulary.
- Deleted all hardcoded keyword lists (Growth: 28 keywords, Financing: 9 keywords,
  Working Capital: 6 keywords).
- Added `_llm_assign_parent(main, parent_categories) -> str | None` helper that
  queries the LLM for novel/non-canonical Main labels with a minimal prompt
  (temperature=0, max_tokens=32).
- Function signature unchanged (takes a string + `parent_categories` list,
  returns a Parent string), but the first parameter semantics shifted from raw
  category text to a Main category name.

**`tests/test_l4_categorize.py`**:
- Replaced the 2 old `assign_parent` tests (which passed raw keyword text) with
  5 new tests covering:
  - Known Main -> correct Parent (exact taxonomy lookup, no LLM)
  - Known Main -> Others when Parent not in supplied list
  - Unknown Main -> LLM fallback returns a valid Parent
  - Unknown Main -> Others when LLM returns None
  - Unknown Main -> Others when LLM returns an invalid Parent

**`tests/test_taxonomy.py`**:
- Added 6 new tests for `parent_for_main()`:
  - `test_parent_for_main_growth_mains` (7 assertions)
  - `test_parent_for_main_financing_mains` (3 assertions)
  - `test_parent_for_main_working_capital_mains` (4 assertions)
  - `test_parent_for_main_others_mains` (3 assertions)
  - `test_parent_for_main_unknown_returns_none` (3 assertions)

### Test results
64 passed in 2.01s — all L4 categorize and taxonomy tests pass.
