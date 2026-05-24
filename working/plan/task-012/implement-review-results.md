# Implement Review Results: Task-012

## Spec Review Issues

No spec review issues found. The implementation matches the task specification line for line, all 5 tests pass, and the full test suite (270 tests, excluding e2e) passes with zero regressions.

## Code Review Issues

### CR-001: `_do` nested closure prevents independent unit testing
- Status: Resolved
- Description: All sibling enrichment modules (`geo.py`, `country.py`, `industry.py`) define `_enrich_one` at module level, making the per-record enrichment logic directly testable (see `test_enrich_one_directly_callable` in `tests/test_enrichments_country.py:177`). `specificity.py:70-82` instead defines `_do` as a nested closure inside `run()`, making it impossible to unit-test the enrichment logic in isolation. This is a structural inconsistency with the codebase pattern and reduces testability.
- Decision Reason:

### CR-002: `all_files` branch has coarser directory fallback than sibling modules
- Status: Resolved
- Description: `specificity.py:88` uses `enriched_dir if enriched_dir.exists() else categorized_dir` to select the glob source. Sibling modules (`geo.py:95-97`, `country.py:83-85`) additionally check `any(enriched_dir.glob("*.json"))`. When `enriched_dir` exists but contains no JSON files, specificity silently processes zero files, while geo and country fall back to `categorized_dir`. This can cause silent data loss in batch processing scenarios.
- Decision Reason:

### CR-003: Regex boundary gaps in `_SPECIFICITY_MARKERS` and `_GENERAL_MARKERS`
- Status: Resolved
- Description: `specificity.py:30` — `independent\s*third` has no word boundaries at all, meaning it matches substrings like "xindependent thirdy". `specificity.py:36` — `\bcontingen` lacks a trailing word boundary, so it matches any prefix starting with "contingen" rather than only valid words (contingent, contingency, contingencies). These imprecisions can produce false positive classifications on compound or non-standard text.
- Decision Reason:

### CR-004: Missing test coverage for `all_files`, `force`, and idempotency paths
- Status: Resolved
- Description: `tests/test_enrichments_specificity.py` has only 5 tests: 3 classification happy-path tests, 1 metadata check, and 1 integration test (ticker path only). Sibling modules (`tests/test_enrichments_geo.py`, `tests/test_enrichments_country.py`) include tests for `all_files=True`, `force=True`, idempotency, and `all_files` with empty enriched_dir fallback. specificity.py has none of these, leaving its batch processing and force-overwrite code paths untested.
- Decision Reason:

### CR-005: CLI single-file path re-loads record instead of calling `_enrich_one` directly
- Status: Resolved
- Description: `specificity.py:135` — The CLI single-file path loads the record from the user-specified file path (`sf`), extracts the ticker, then calls `run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force)`. Inside `run()` at line 72, `load_enriched_or_categorized(CATEGORIZED_DIR, ticker)` re-loads the record, discarding the originally loaded data. Sibling modules `geo.py:151` and `country.py:152` avoid this by calling `_enrich_one(record, ENRICHED, ...)` directly, ensuring the record from the user-specified file is the one that gets enriched. If a user passes a file path outside `CATEGORIZED_DIR`, the specificity CLI may enrich a different record than the one the user specified, because `load_enriched_or_categorized` searches for the ticker within `CATEGORIZED_DIR`'s subtree, not at the user's specified path. This is a pattern inconsistency and a correctness bug in the edge case.
- Decision Reason: Changed CLI single-file path to call `_enrich_one(record, ENRICHED, force=args.force)` directly instead of `run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force)`. This matches the pattern in geo.py and country.py, ensures the record from the user-specified file is the one that gets enriched, and eliminates the redundant re-load.

### CR-006: `_GENERAL_MARKERS` regex `\bcontingen\w*\b` is overly permissive with suffix matching
- Status: Resolved
- Description: `specificity.py:35` — The regex pattern `\bcontingen\w*\b` is intended to match "contingent", "contingency", and "contingencies" but the `\w*` quantifier accepts ANY sequence of word characters (e.g., "contingentx", "contingentabc123"). While the CR-003 fix correctly added a word boundary at both ends, the `\w*` in the middle is less precise than it could be. An alternation such as `\bcontingen(?:t|cy|cies?)\b` would match only the valid English word forms and prevent false positives on non-word suffixes. In practice, non-word strings like "contingentx" are unlikely in real prospectus text, so the practical risk is low, but the pattern sacrifices precision unnecessarily.
- Decision Reason: Replaced `\bcontingen\w*\b` with `\bcontingen(?:t|cy|cies?)\b` in _GENERAL_MARKERS. This matches only valid English word forms (contingent, contingency, contingencies) and prevents false positives on non-word suffixes like "contingentx".

### CR-007: Test `test_specificity_no_false_positive_substring` has misleading comment and permissive assertion
- Status: Resolved
- Description: `test_enrichments_specificity.py:219` — The doc-comment for the "contingentx" subtest says "verify 'contingentx' doesn't match" but the assertion at line 225 (`assert result2 in ("general", "vague")`) actually accepts "general" as a valid outcome. Since `\bcontingen\w*\b` DOES match "contingentx" (see CR-006), this subtest returns "general" and passes. The test therefore does NOT verify the stated intent of non-matching behavior. It only verifies that the classifier does not return "specific". This masks the regex imprecision and could mislead future maintainers who read the comment but not the assertion. The assertion should either test for exactly "vague" (if non-matching is truly required) or the comment should accurately describe what is being verified.
- Decision Reason: Updated the comment to accurately describe what is being verified ("contingentx" must not match the tightened regex, should not trigger "general") and changed assertion from `assert result2 in ("general", "vague")` to `assert result2 == "vague"`. With the CR-006 regex fix applied, "contingentx" no longer matches _GENERAL_MARKERS, and the short text falls through all classifier rules to return "vague".

### CR-008: `proprietary`, `patent`, `certification` in `_SPECIFICITY_MARKERS` missing word boundaries
- Status: Resolved
- Description: `specificity.py:29` — The regex alternations `proprietary`, `patent`, and `certification` lack `\b` word boundaries. Unlike the other 17 patterns in `_SPECIFICITY_MARKERS` (which all have `\b` at both ends), these three match ANY substring occurrence. For example, `patent` would match inside the real English word "patently" (as in "patently obvious"), causing a false-positive specificity signal. `proprietary` would match substrings like "xproprietaryy". This is the same class of bug identified in CR-003 (which was marked Resolved after fixing `independent\s*third` and `\bcontingen`), but CR-003 did not mention these three patterns, so they remain unfixed. The existing test `test_specificity_no_false_positive_substring` tests the `independent\s*third` and `contingen` boundary fixes but does not cover `proprietary`, `patent`, or `certification` substring matching.
- Decision Reason: Added `\b` word boundaries to all three patterns (`\bproprietary\b`, `\bpatent\b`, `\bcertification\b`) matching the convention of the other 17 patterns in `_SPECIFICITY_MARKERS`. Added three subtest cases to `test_specificity_no_false_positive_substring` covering "patently" (should not match "patent"), "xproprietaryy" (should not match "proprietary"), and "xcertificationy" (should not match "certification"). All tests pass.
