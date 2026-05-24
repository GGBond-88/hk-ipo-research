# Changes: Task-012

## Files
- [mod] src/hk_ipo/enrichments/specificity.py
- [mod] tests/test_enrichments_specificity.py

## Summary
Implement L5 enrichment specificity classifier. Rules-based classifier that scores each use item's description and source_text as `specific`, `general`, or `vague` based on regex marker patterns. Includes `run` function for batch/ticker processing that integrates with the enrichment pipeline, and CLI support.

### Initial implementation

- Created `src/hk_ipo/enrichments/specificity.py` with `classify_specificity()`, `run()`, `_enrich_one()`, and CLI.
- Created 5 tests in `tests/test_enrichments_specificity.py`.

### Fixes applied (implement-review-results.md CR-001 through CR-004)

- **CR-001**: Extracted `_do` nested closure to module-level `_enrich_one` function, matching the pattern used by `geo.py`, `country.py`, and `industry.py`.
- **CR-002**: Fixed `all_files` branch to check `any(enriched_dir.glob("*.json"))` before falling back to `categorized_dir`, and to return a `dict[str, Any]` keyed by ticker instead of `None`.
- **CR-003**: Fixed regex boundaries: added `\b` around `independent\s*third` and changed `\bcontingen` to `\bcontingen\w*\b` for proper word-boundary matching on contingency/contingent/contingencies.
- **CR-004**: Added 6 new tests covering idempotency, `force=True`, `all_files` returns dict, `all_files` empty enriched_dir fallback, `_enrich_one` direct callability, and false-positive substring guarding.

### Fixes applied (implement-review-results.md CR-005 through CR-007)

- **CR-005**: Fixed CLI single-file path to call `_enrich_one(record, ENRICHED, force=args.force)` directly instead of `run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force)`. Matches pattern in geo.py and country.py; eliminates redundant record re-load and ensures user-specified file contents are enriched.
- **CR-006**: Tightened `_GENERAL_MARKERS` regex from `\bcontingen\w*\b` to `\bcontingen(?:t|cy|cies?)\b` to match only valid English word forms (contingent, contingency, contingencies) and prevent false positives on non-word suffixes.
- **CR-007**: Fixed misleading test comment and assertion in `test_specificity_no_false_positive_substring` for the "contingentx" subtest. Changed assertion from `result2 in ("general", "vague")` to `result2 == "vague"` and updated comment to accurately describe expected behavior after CR-006 regex fix.
- **CR-008**: Added `\b` word boundaries to `proprietary`, `patent`, and `certification` in `_SPECIFICITY_MARKERS`, matching the convention of the other 17 patterns. Added three subtest cases covering "patently" (should not match "patent"), "xproprietaryy" (should not match "proprietary"), and "xcertificationy" (should not match "certification").
