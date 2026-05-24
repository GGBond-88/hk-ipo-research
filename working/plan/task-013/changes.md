# Changes: Task-013

## Files
- [new] src/hk_ipo/enrichments/timeline.py
- [mod] src/hk_ipo/enrichments/timeline.py
- [mod] tests/test_enrichments_timeline.py

## Summary

### Original implementation
L5 timeline enrichment module that classifies each use-of-proceeds item into a 5-bucket deployment horizon (0-12m, 12-24m, 24-36m, 36m+, unspecified) using rules-based regex matching. Used two-phase matching: explicit numeric mentions (checked longest to shortest first) take priority over qualitative phrases. This fixes TI-003 where "long-term" (qualitative) in the original task code would shadow "5 years" (numeric very-long). Followed existing enrichment module patterns (base I/O helpers, run/enrich pipeline, CLI entry point).

### Fix round (review issues SR-001, SR-002, CR-005)

**SR-001 (Resolved):** Accepted the two-phase algorithm as correct. Documented as TI-003 in task-issues.md. The spec's single-phase ordering is buggy (qualitative "long-term" shadows numeric "5 years").

**SR-002 (Resolved):** Removed `?` from `two?`, `three?`, `four?`, `five?` in numeric regex patterns. The `?` quantifier only applies to the preceding single character (making "tw", "thre", "fou", "fiv" matchable), which is semantically incorrect. Changed to literal `two`, `three`, `four`, `five` matching the task spec's intent. Added `test_spelled_out_word_numbers` unit test.

**CR-005 (Resolved):** Changed all `\s*` to `[\s-]*` in numeric regex patterns (`_SHORT_NUMERIC_RE`, `_MEDIUM_NUMERIC_RE`, `_LONG_NUMERIC_RE`, `_VERY_LONG_NUMERIC_RE`). This enables matching hyphenated forms ("12-month", "5-year", "3-year") which are common in HKEX prospectus text, in addition to space-separated forms. Added four hyphenated-form unit tests.

### Fix round 2 (review issues CR-006, CR-007, CR-008)

**CR-006 (Resolved):** Changed CLI `__main__` block to call `_enrich_one(record, ENRICHED, DIMENSION, force=args.force, ticker=ticker)` directly instead of `run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force)`. The old code reloaded the record from standard paths, discarding the user-supplied file content. Now matches the `country.py` pattern. Added `test__enrich_one_processes_arbitrary_record` and `test_run_ticker_mode_uses_categorized_fallback` unit tests.

**CR-007 (Resolved):** Changed `\s*` to `[\s-]*` in `_VERY_LONG_QUAL_RE` for both `very[\s-]*long` and `extended[\s-]*(period|horizon|timeline)`. This enables matching hyphenated qualitative forms ("very-long", "extended-horizon") which were previously classified as "unspecified". Added `test_hyphenated_very_long_qualitative` and `test_hyphenated_extended_horizon` unit tests.

**CR-008 (Resolved):** Added trailing `\b` to three sub-patterns in `_SHORT_NUMERIC_RE`: `within[\s-]*(a|1)[\s-]*year\b`, `first[\s-]*year\b`, and `12[\s-]*mo\b`. This prevents false-positive matching on words like "yearly", "yearbook", "model", and "mother" that contain the pattern stems as substrings. Added `test_yearly_not_matched_as_year`, `test_model_not_matched_as_mo`, and `test_first_yearbook_not_matched` unit tests.
