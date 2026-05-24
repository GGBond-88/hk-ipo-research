# Changes: Task-010

## Files
- [new] src/hk_ipo/enrichments/country.py
- [new] tests/test_enrichments_country.py
- [mod] working/task-issues.md

## Summary
Implemented L5 country enrichment tool that scans use-item text for ISO 2-letter country mentions and tags each item with country codes. Removed "hong kong" from _COUNTRY_MAP to align with test expectation (HK is not a foreign country in HKEX context). Followed TDD: tests written first, verified red (ModuleNotFoundError), implemented, verified green (all 6 pass), full suite verified (260 pass, no regressions).

## SR-001 Resolution
- **Status**: Don't Fix. Task spec Step 3 includes `"hong kong": "HK"` in `_COUNTRY_MAP` but Step 1's `test_extract_countries_no_match` expects `[]` for "Hong Kong" text. HKEX context: HK is home market, not foreign country. TI-002 documents the rationale. Three approaches attempted and documented in implement-review-results.md.

## Review Fixes (post-review)
- **CR-001**: Changed `extract_countries` from plain substring matching (`in` operator) to regex word-boundary matching (`\b` patterns) to prevent false positives for short codes like "uk" inside words like "Luke" or "dukedom".
- **CR-002**: `import re` is now used (by CR-001 fix), no longer a dead import.
- **CR-003**: `run(all_files=True)` now returns a `dict[str, Any]` keyed by ticker (previously returned `None`), consistent with geo.py.
- **CR-004**: `all_files` glob logic now checks for actual JSON files in `enriched_dir` before using it, falling back to `categorized_dir` when enriched_dir exists but is empty. Matches geo.py behavior.
- **CR-005**: Extracted nested `_do` closure to module-level `_enrich_one` function with explicit parameters. Now directly testable and consistent with geo.py's `_enrich_one` pattern.
