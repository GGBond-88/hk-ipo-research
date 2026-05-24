# P2-3 — Centralize raw SQL from export.py into storage/queries.py

Status: done
Priority: P2
Effort: S (30–45 min)

## Goal
Move the hand-written SQL strings scattered across [src/hk_ipo/analysis/export.py](../../src/hk_ipo/analysis/export.py) into a single module `src/hk_ipo/storage/queries.py`.

## Why
Easier to audit, refactor, and unit test. Today the export functions interleave business logic with raw SQL. See revise_plan.md §P2-3.

## Files touched
- Modify: `src/hk_ipo/analysis/export.py`
- Create: `src/hk_ipo/storage/queries.py`

## Steps
1. Read `export.py` end to end; collect each `cur.execute("SELECT ...")` literal.
2. For each query, write a top-level constant in `queries.py`:
   ```python
   COMPANIES_OVERVIEW = """
   SELECT ticker, company_name, ...
   FROM companies
   ORDER BY ticker
   """
   ```
3. Replace the literal in `export.py` with the constant import.
4. Run `pytest tests/test_analysis_export.py -v`. Output must match byte-for-byte (idempotency unchanged).

## Acceptance
- [ ] `export.py` contains no inline `SELECT`/`INSERT`/`UPDATE` strings (all imported from `queries`).
- [ ] `queries.py` constants are alphabetically sorted and docstring'd with one line each.
- [ ] `test_analysis_export.py` passes.

## Out of scope
- Migrating to an ORM.
- Changing query semantics.

## Dependencies
None.

---
## Resolution
Status: done
Created: src/hk_ipo/storage/queries.py (12 SQL constants)
Modified: src/hk_ipo/analysis/export.py (all inline SQL replaced with imports)
Tests pass.
