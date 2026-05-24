# Implement Review Results: Task-020
## Spec Review Issues

### SR-001: `--model` argument added but not in task specification
- Status: Resolved
- Description: The `--model` argument was registered at line 183-184 of `scripts/run_pipeline.py` (`parser.add_argument("--model", default=None, help="Override LLM model for L4 categorisation")`). The task objective (line 11) explicitly lists the flags to support: `--skip`, `--only`, `--limit`, `--force`, `--dry-run-cost`, `--build-frontend`, `--db`, `--json`. `--model` is not in this list. Furthermore, Step 3 of the task provides the exact replacement code which intentionally uses `getattr(args, "model", None)` without registering `--model` in ArgumentParser -- a forward-looking pattern that does not expose the flag to users. Adding `--model` as a user-facing CLI flag is scope creep beyond what the task specification requires.
- Decision Reason:

## Code Review Issues

### CR-001: Unused `hashlib` import
- Status: Resolved
- Description: `scripts/run_pipeline.py:12` imports `hashlib` which is never used anywhere in the file. This is dead import that adds unnecessary noise and could confuse readers about the module's dependencies. The import should be removed to keep the codebase clean.
- Decision Reason:

### CR-002: `--model` argument not registered in ArgumentParser but accessed via `getattr`
- Status: Don't Fix
- Description: `scripts/run_pipeline.py:319` calls `getattr(args, "model", None)` but no `--model` argument is defined in the `ArgumentParser` (lines 173-185 — verified no `--model` exists). The `model` parameter passed to `l4_process_all()` will unconditionally be `None`, making this dead code. The changes.md claims this was fixed by adding `--model` to ArgumentParser, but the current code has no such argument. Either the fix was not applied, or it was reverted. If this is intentionally a forward-looking placeholder (as the task spec suggests), the Decision Reason should explain this. Otherwise, the `getattr` call should be removed or a real argument should be registered.
- Decision Reason: The `getattr(args, "model", None)` pattern is intentionally specified in the Task-020 Step 3 template code. It serves as a forward-looking placeholder so that a future task can add `--model` without changing the L4 invocation site. Attempted approaches: (1) Register `--model` argument -- rejected because it is scope creep beyond the task-specified flags (SR-001). (2) Remove `getattr` and hardcode `None` -- rejected because the task template explicitly includes this forward-looking pattern. (3) Leave as-is per task spec -- accepted as the design intent from the task template.

### CR-003: L5 enrichment return values are discarded and failure count is always hardcoded to zero
- Status: Resolved
- Description: `scripts/run_pipeline.py:349` calls `mod.run(...)` for each L5 enrichment sub-stage but discards the return value (`dict[str, Any] | None`). Immediately afterward at line 351, `stats[stage_key] = {"ok": n_enriched, "failed": 0}` hardcodes `"failed": 0` regardless of what actually occurred inside the enrichment module. If any enrichment module encounters errors (e.g., malformed JSON, missing fields, processing exceptions), the orchestrator will neither detect nor report the failure. Furthermore, the enrichment `run()` functions in `src/hk_ipo/enrichments/` do not wrap individual file processing in try/except, so exceptions propagate as unhandled crashes rather than aggregated failure counts. This means L5 sub-stage errors either go completely undetected (if the module silently skips failures) or crash the entire pipeline (if an exception is raised). Either outcome violates the pipeline's design intent of per-ticker non-blocking error reporting.
- Decision Reason:

### CR-004: L7 `OUT_DIR` hardcoded to `PROJECT_ROOT` breaks path derivation consistency
- Status: Resolved
- Description: `scripts/run_pipeline.py:419` defines `OUT_DIR = config.PROJECT_ROOT / "frontend" / "public" / "data"`, using the project-configured path directly. Every other stage (L1-L6) derives its input/output directories from `data_root` (computed from `--pdf-dir` at line 194), which allows E2E tests to isolate pipeline runs to temporary directories. L7 bypasses this isolation and always writes to the real project's `frontend/public/data/` directory. During parallel or E2E test runs with `--pdf-dir` pointing to a `tmp_path`, L7 output will land in the shared project directory, potentially interfering with concurrent tests or polluting the repository. If L7 truly must write to the project frontend directory (because the frontend dev server serves from there), this decision should be documented with an explicit comment explaining why it intentionally differs from all other stages. Otherwise, it should follow the same `data_root`-based derivation pattern.
- Decision Reason:

### CR-005: industry.py returns None for all_files=True, undermining CR-003 fix
- Status: Resolved
- Description: `src/hk_ipo/enrichments/industry.py:132-141` -- when `all_files=True`, the `run()` function loops through all JSON files calling `_enrich_one()` but returns `None` instead of a results dict keyed by ticker. All 7 other enrichment modules (geo, country, specificity, timeline, capex_opex, esg_tag, commitment) correctly return `dict[str, Any]` keyed by ticker. Because the orchestrator at `scripts/run_pipeline.py:354-360` checks `isinstance(results, dict)`, the industry enrichment always falls through to the `else` branch which hardcodes `n_failed = 0` and counts all enriched JSON files as `n_ok`. Any industry enrichment failures (e.g., LLM API call failures caught at industry.py:98-100 and converted to `primary = "Unknown"`) are silently undetected by the orchestrator. This partially defeats the CR-003 fix which was intended to capture real ok/failed counts from L5 enrichment return values.
- Decision Reason:

### CR-006: L5 aggregate log status diverges from _log_stage_result pattern when all tickers fail
- Status: Resolved
- Description: `scripts/run_pipeline.py:361` uses `"ok" if n_ok > 0 else "skipped"` to determine the aggregate log status for L5 enrichment stages. This diverges from the project-standard `_log_stage_result()` logic at line 147: `"failed" if fail > 0 and ok == 0 else ("skipped" if ok == 0 else "ok")`. When all L5 tickers fail (n_ok=0, n_failed>0), the orchestrator logs aggregate status `"skipped"` instead of `"failed"`, misrepresenting the outcome. The subsequent error line at 362-363 writes an aggregate `"failed"` entry with the error message, producing two conflicting JSONL entries for the `*` ticker with different status values (`"skipped"` then `"failed"`). This inconsistency would confuse downstream log consumers that read the first or last status per (stage, ticker). The fix should either call `_log_stage_result` with a properly-shaped stats dict, or replicate its three-way status logic inline.
- Decision Reason:

### CR-007: No exception handling around L5 enrichment mod.run() calls
- Status: Resolved
- Description: `scripts/run_pipeline.py:350` calls `mod.run(categorized_dir, enriched_dir, all_files=True, force=args.force)` for each L5 enrichment sub-stage without a try/except wrapper. The `industry` enrichment module makes live LLM API calls via `_classify_via_llm()` at `industry.py:66-71`. If the LLM call raises a network error, timeout, or unexpected API exception that is not caught by the bare `except Exception` at industry.py:98, the exception propagates to the orchestrator and crashes the entire pipeline with an unhandled traceback. All other pipeline stages (L1-L4, L6) handle errors internally via their `process_all` functions, which aggregate per-ticker failures rather than aborting the whole run. Additionally, if `importlib.import_module(module_name)` at line 349 fails (e.g., missing module, circular import), the ImportError also crashes the pipeline without recording any failure in the run log or database. The orchestrator should wrap each enrichment call in try/except and log failures to the run log and pipeline_runs table instead of crashing.
- Decision Reason:

### CR-008: --build-frontend stats only reflect last command's return code
- Status: Resolved
- Description: `scripts/run_pipeline.py:399-405` runs both `npm install` and `npm run build` in a for loop, but `stats["frontend"] = {"ok": 1 if result.returncode == 0 else 0}` at line 405 only checks `result` from the final iteration (`npm run build`). If `npm install` fails but `npm run build` succeeds (e.g., dependencies were already installed from a prior run), the stats incorrectly report success for the full build step. Additionally, the pipeline unconditionally proceeds from `npm install` to `npm run build` even when install fails, which can produce confusing cascading error output. The code should track both command results independently, or short-circuit on install failure.
- Decision Reason:

### CR-009: Redundant import sqlite3 inside L7 stage
- Status: Resolved
- Description: `scripts/run_pipeline.py:379` imports `import sqlite3 as _sqlite` inside the L7 stage body, but sqlite3 is already imported at the module level (line 19) as `_sqlite3`. The inner-scope import creates an unnecessary second alias and adds a runtime import step that has no benefit. The L7 code at lines 386 and 391 should use the existing `_sqlite3` binding instead, and the redundant import at line 379 should be removed. While functionally harmless (Python rebinds the same module object), it is dead code that misleads readers into thinking a different sqlite3 interface is required.
- Decision Reason:

### CR-010: L6 `_record_stage_sweep` uses same set for attempted and succeeded
- Status: Resolved
- Description: `scripts/run_pipeline.py:370` calls `_record_stage_sweep(db_path, run_id, "L6", l6_attempted, l6_attempted)` passing the same set (`_tickers_from_dir(enriched_dir)`) for both attempted and succeeded. This unconditionally records every ticker in enriched_dir as "ok" in the pipeline_runs table, regardless of whether `l6_process_all()` (line 367) actually succeeded in loading them into SQLite. The stats dict returned by `l6_process_all` may contain `"failed"` counts, but these are ignored by the sweep. Contrast with L1/L2/L4 which compare input tickers against output tickers to detect per-ticker failures. Any L6 load failures are silently omitted from pipeline_runs tracking.
- Decision Reason:

### CR-011: L1 `_log_stage` called before failed count correction
- Status: Resolved
- Description: `scripts/run_pipeline.py:252` logs L1 aggregate status as `"ok" if n_sections > 0 else "skipped"` based on the initial `n_sections` count (line 250). However, the failed count is computed LATER at line 257 (`l1_failed_count = len(l1_attempted - l1_succeeded)`). When any PDFs fail sectioning, the JSONL log incorrectly records aggregate status as `"ok"` (since `n_sections > 0`) even though there were per-ticker failures. For comparison, L2/L3/L4 all call `_log_stage_result()` AFTER computing the full stats dict. The `_log_stage("L1", ...)` call on line 252 should be moved to after the failed correction, using `_log_stage_result("L1", stats["L1"])` to match the pattern of other stages.
- Decision Reason:

### CR-012: L5 per-sub-stage `_record_stage_sweep` conflates output from all enrichment modules
- Status: Resolved
- Description: `scripts/run_pipeline.py:360` computes `l5_succeeded = _tickers_from_dir(enriched_dir)` for each L5 sub-stage. Since all 8 L5 enrichment sub-stages (geo, country, industry, specificity, timeline, capex_opex, esg_tag, commitment) write their output to the same `enriched_dir`, the sweep for each sub-stage finds ALL enriched tickers -- including those enriched by OTHER sub-stages, not just the current one. For example, if L5.geo succeeds for ticker X but L5.country crashes for ticker X, the L5.country sweep still records X as "succeeded" because X already exists in enriched_dir (from geo). This makes per-sub-stage pipeline_runs tracking unreliable. The sweep should use a per-sub-stage success indicator (e.g., check that the record's enrichment block contains the sub-stage's dimension) rather than bare file existence.
- Decision Reason:

### CR-013: L6 stats and JSONL log disagree with pipeline_runs table when tickers fail to load
- Status: Resolved
- Description: `scripts/run_pipeline.py:380` does `failed = results.get("failed", 0)`, but `l6_process_all()` in `src/hk_ipo/storage/loader.py:172-195` returns only `{"loaded": N, "total": N}` — it never includes a `failed` key (individual load errors are caught internally at loader.py:188 but not counted). Consequently `stats["L6"]["failed"]` is always 0, and `_log_stage_result` at line 383 logs aggregate status as "ok" even when tickers failed. The CR-010 DB query workaround (lines 390-399) correctly identifies per-ticker failures for `_record_stage_sweep`, so pipeline_runs gets accurate per-ticker status — but the stats dict and JSONL run log remain stale with `failed=0`. This creates a split-brain where `_print_summary` shows no failures, the JSONL log aggregate entry shows no failures, yet pipeline_runs shows individual failed rows for the same run. The orchestrator should update `stats["L6"]` after the DB query discovery, or the L6 `process_all` should return a `failed` count, so all three output channels (summary, log, pipeline_runs) are consistent.
- Decision Reason: Restructured L6 block to compute `l6_succeeded` via DB query BEFORE constructing stats and calling `_log_stage_result`. Failed count is now derived as `len(l6_attempted - l6_succeeded)` from the DB-verified success set rather than `results.get("failed", 0)` which was always 0. Also relaxed `loaded == total` to `loaded >= total` in the early-return guard to handle edge cases. All three output channels (stats dict, JSONL log, pipeline_runs) now derive from the same DB-verified data.

### CR-014: Duplicated ok-count extraction logic across `_log_stage_result` and `_print_summary`
- Status: Resolved
- Description: `scripts/run_pipeline.py:145` (`_log_stage_result`) and `scripts/run_pipeline.py:160` (`_print_summary`) contain nearly identical nested `.get()` chains for extracting the ok count from stage stats dicts: `stats.get("succeeded", stats.get("passed", stats.get("loaded", stats.get("ok", 0))))`. This identical logic is duplicated in two functions 15 lines apart. If a future stage introduces a new key name (e.g., "success", "ok_count"), both locations must be updated, creating a maintenance hazard and risking divergent interpretations of the same data. Extract to a shared helper function `_stat_ok(stats) -> int` and `_stat_fail(stats) -> int` used by both callers.
- Decision Reason: Extracted `_stat_ok(s: dict[str, Any]) -> int` and `_stat_fail(s: dict[str, Any]) -> int` as module-level helper functions placed between `_log_stage` and `_log_stage_result`. Both `_log_stage_result` and `_print_summary` now call these shared helpers, eliminating the duplicated nested `.get()` chain. Future changes to stats key names only need to update the two helpers in one place.

### CR-015: `import importlib` placed inside L5 enrichment for loop instead of module-level
- Status: Resolved
- Description: `scripts/run_pipeline.py:344` imports `importlib` inside the `for stage_key in stages_to_run` loop body. While Python caches imports so this is functionally a no-op after the first iteration, it violates PEP 8 (imports at top of file) and deviates from every other import in the file (`argparse`, `json`, `subprocess`, `sys`, `uuid`, `datetime`, `timezone`, `Path`, `Any`, `_sqlite3` are all at module level). Move the `import importlib` statement to the module-level import block (around line 11) for consistency and style compliance.
- Decision Reason: Moved `import importlib` to the module-level import block (line 12, alphabetically between `import argparse` and `import json`). Removed the redundant import from inside the L5 for loop body. All imports now follow PEP 8 and are consistent with the rest of the file.
