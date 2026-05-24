# Changes: Task-020

## Files
- [mod] scripts/run_pipeline.py

## Summary
Extended the pipeline orchestrator from L1-L4 to full L1-L7 pipeline with support for: --skip, --only, --limit, --force, --dry-run-cost, --build-frontend, --db, --json structured run report. Added JSONL run logging, pipeline_runs SQLite tracking per-ticker per-stage, cost estimation, and L5 enrichment sub-stages (geo, country, industry, specificity, timeline, capex_opex, esg_tag, commitment). Added smoke test for cost estimation config requirements.

## CR Fixes Applied
- CR-001: Removed unused `hashlib` import
- CR-002: Kept forward-looking `getattr(args, "model", None)` pattern per task spec (Don't Fix — intentional placeholder)
- CR-003: Captured L5 `run()` return values to compute actual ok/failed counts instead of hardcoding `failed: 0`
- CR-004: Documented L7 intentional PROJECT_ROOT usage with explanatory comment
- CR-005: industry.py already returns results dict when all_files=True (Resolved in prior review cycle)
- CR-006: L5 already uses `_log_stage_result()` (Resolved in prior review cycle via PR-019)
- CR-007: Added try/except around L5 enrichment `importlib.import_module()` and `mod.run()` calls; on failure, records all attempted tickers as failed in stats, run log, and pipeline_runs table
- CR-008: Track both `npm install` and `npm run build` results independently; short-circuit on install failure; compute `all_ok` from both results
- CR-009: Removed redundant `import sqlite3 as _sqlite` inside L7 stage; use module-level `_sqlite3` binding instead
- CR-010: L6 sweep now queries `companies` table for actually-loaded tickers (when loaded < total); falls back to assuming all loaded on query error
- CR-011: Moved L1 `_log_stage` call to after failed count computation; uses `_log_stage_result()` matching L2/L3/L4 pattern
- CR-012: L5 per-sub-stage sweep now uses `results.keys()` as succeeded set when `run()` returns a dict (per-sub-stage indicator); falls back to `_tickers_from_dir(enriched_dir)` only when results is not a dict
- CR-013: Restructured L6 block to compute DB-verified `l6_succeeded` BEFORE stats/logging; `failed` count now derived as `len(l6_attempted - l6_succeeded)` from actual per-ticker DB presence rather than the always-0 `results.get("failed", 0)`. All three output channels (stats, JSONL, pipeline_runs) now derive from the same DB-verified source.
- CR-014: Extracted `_stat_ok()` and `_stat_fail()` helper functions to eliminate duplicated nested `.get()` chains in `_log_stage_result` and `_print_summary`. Future stats key name changes require updating only these two helpers.
- CR-015: Moved `import importlib` from inside the L5 for loop body to the module-level import block (PEP 8 compliance).
