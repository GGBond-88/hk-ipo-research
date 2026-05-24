# P2-1 — Narrow `except Exception:` to specific exception types

Status: complete
Priority: P2
Effort: S (30–45 min)

## Goal
Replace broad `except Exception:` blocks with the actual exception classes they need to catch, and use `logger.exception(...)` so stack traces are preserved.

## Why
Broad excepts hide bugs and break debugging. The two worst offenders are documented in revise_plan.md §P2-1.

## Files touched
- [src/hk_ipo/l2_extraction.py](../../src/hk_ipo/l2_extraction.py) around line 412
- [src/hk_ipo/l4_categorize.py](../../src/hk_ipo/l4_categorize.py) around line 659
- (Optionally sweep other `except Exception:` occurrences across `src/`)

## Steps
1. `Grep -n "except Exception" src/hk_ipo/`. Triage each hit.
2. For each: identify what can actually raise (e.g., `openai.APIError`, `json.JSONDecodeError`, `OSError`, `ValueError`). Catch those, re-raise unexpected ones.
3. Replace `logger.error(f"... {e}")` patterns with `logger.exception("...")` (auto-includes traceback).
4. Run `pytest -m "not e2e" -q` — green required.

## Acceptance
- [ ] No `except Exception:` remains in `src/hk_ipo/l2_extraction.py` or `src/hk_ipo/l4_categorize.py`.
- [ ] Any retained broad excepts elsewhere have a comment explaining why (e.g., outermost CLI guard).
- [ ] All tests pass.

## Dependencies
None. Best done after [P1-4](P1-4-llm-client-unification.md) — `LLMClient` may consolidate some of these.

## Resolution

**Status**: complete

**What was changed**:

| File | Change |
|---|---|
| `src/hk_ipo/l2_extraction.py` (3 sites) | `except Exception` narrowed to `except (openai.APIError, ValueError, json.JSONDecodeError)` (self-correction fallback) and `except (openai.APIError, ValueError, json.JSONDecodeError, OSError)` (process_single and process_all workers). Also changed `logger.warning` to `logger.exception` in the self-correction handler to auto-include traceback. |
| `src/hk_ipo/l4_categorize.py` (2 sites) | `except Exception` narrowed to `except openai.APIError` (_llm_assign_parent LLM fallback) and `except (OSError, ValueError, json.JSONDecodeError, openai.APIError)` (process_all batch loop). Added `import openai` at module level. |
| `src/hk_ipo/schema_review.py` (1 site) | `except Exception` narrowed to `except (json.JSONDecodeError, OSError)` (file read + JSON parse). |
| `src/hk_ipo/l4_legacy_analysis.py` (1 site) | `except Exception` narrowed to `except (json.JSONDecodeError, OSError)` (file read + JSON parse). |
| `src/hk_ipo/enrichments/industry.py` (1 site) | `except Exception` narrowed to `except (openai.APIError, ValueError)` (LLM classify call). Added `import openai` at module level. |
| `src/hk_ipo/storage/loader.py` (2 sites) | `except Exception` narrowed to `except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error)` (batch loop). Added explanatory comment on the retained broad `except Exception` guarding the DB transaction rollback (must catch everything to guarantee rollback). |
| `src/hk_ipo/l3_validation.py` (1 site) | Retained broad `except Exception` with comment: "outermost CLI batch loop guard". |
| `src/hk_ipo/l1_sectioning.py` (1 site) | Retained broad `except Exception` with comment: "outermost CLI batch loop guard". |

**Note on `logger.error` -> `logger.exception`**: No `logger.error(f"... {e}")` patterns existed in the codebase. One `logger.warning(..., exc)` call in l2_extraction.py was upgraded to `logger.exception(...)` which auto-includes traceback.

**Test results**: `python -m pytest -m "not e2e" -q` -- 495 passed, 1 pre-existing failure. The single failure (`test_cli_missing_file_errors` in test_enrichments_capex_opex.py) is a pre-existing bug (CLI calls `sys.exit(string)` instead of `sys.exit(1)`) unrelated to these changes. Excluding that file, 419 tests pass with zero failures.
